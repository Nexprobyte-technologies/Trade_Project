"""Application entry point for the validated Dhan dashboard."""

import json
import time
from datetime import datetime

from config import (
    EXCLUDED_STOCKS, IST, NIFTY50_INSTRUMENTS,
    NIFTY50_SECURITY_IDS, NIFTY_ID, SENSEX_ID, VERIFIED_STOCK_COUNT,
)
from dhan_client import (
    credentials_configured, get_ltp, get_ohlc, get_option_chain,
    get_option_expiries, valid_price,
)


def _timestamp():
    return datetime.now(IST).strftime("%H:%M:%S")


def dhan_output(value):
    print(f"@@DHAN_OUTPUT {json.dumps(value, allow_nan=False)}")


def _value(data, *keys):
    if not isinstance(data, dict):
        return None
    for key in keys:
        value = data.get(key)
        if valid_price(value):
            return value
    return None


def _ohlc_details(data):
    nested = data.get("ohlc") if isinstance(data, dict) else None
    return nested if isinstance(nested, dict) else data


def _option_value(data, key):
    value = data.get(key) if isinstance(data, dict) else None
    return value if valid_price(value) or value == 0 else None


def _option_field(data, *keys):
    for key in keys:
        value = _option_value(data, key)
        if value is not None:
            return value
    return None


def _nearest_expiry(expiries):
    today = datetime.now(IST).date().isoformat()
    valid = sorted(expiry for expiry in expiries if expiry >= today)
    return valid[0] if valid else None


def _market_status(now):
    return (
        "CLOSED"
        if now.hour > 15 or (now.hour == 15 and now.minute >= 30)
        else "OPEN"
    )


def fetch_option_details(stock, underlying_segment="NSE_EQ"):
    """Fetch the nearest valid ATM CE/PE pair, or an explicit unavailable result."""
    unavailable = {
        "status": "Option Data Unavailable",
        "reason": "No valid F&O expiry or option-chain response",
    }
    expiries = get_option_expiries(
        stock["security_id"], underlying_segment
    )
    expiry = _nearest_expiry(expiries)
    if not expiry:
        return unavailable
    time.sleep(3)
    response = get_option_chain(
        stock["security_id"], expiry, underlying_segment
    )
    data = response.get("data", {}) if isinstance(response, dict) else {}
    chain = data.get("oc", {}) if isinstance(data, dict) else {}
    if not isinstance(chain, dict):
        return unavailable
    strikes = []
    for raw_strike, pair in chain.items():
        try:
            strike = float(raw_strike)
        except (TypeError, ValueError):
            continue
        if isinstance(pair, dict) and isinstance(pair.get("ce"), dict) and isinstance(pair.get("pe"), dict):
            strikes.append((abs(strike - stock["ltp"]), strike, pair))
    if not strikes:
        return unavailable
    _, strike, pair = min(strikes, key=lambda item: item[0])
    ce, pe = pair["ce"], pair["pe"]
    fields = {
        "underlying": stock["name"],
        "expiry": expiry,
        "strike": strike,
        "CE_LTP": _option_value(ce, "last_price"),
        "CE_best_bid": _option_value(ce, "top_bid_price"),
        "CE_best_ask": _option_value(ce, "top_ask_price"),
        "CE_option_sell_exit_price": _option_value(ce, "top_bid_price"),
        "PE_LTP": _option_value(pe, "last_price"),
        "PE_best_bid": _option_value(pe, "top_bid_price"),
        "PE_best_ask": _option_value(pe, "top_ask_price"),
        "PE_option_sell_exit_price": _option_value(pe, "top_bid_price"),
        "CE_open_interest": ce.get("oi"),
        "PE_open_interest": pe.get("oi"),
        "CE_volume": ce.get("volume"),
        "PE_volume": pe.get("volume"),
        "status": "ok",
    }
    if not all(valid_price(fields[key]) for key in
               ("CE_LTP", "CE_best_bid", "CE_best_ask",
                "PE_LTP", "PE_best_bid", "PE_best_ask")):
        return unavailable
    return fields


def fetch_index_option_chain(security_id, name, segment, ltp, market_status):
    unavailable = {
        "status": "Option Chain Unavailable",
        "underlying": name,
        "quote_timestamp": _timestamp(),
        "quote_status": (
            "last_available_market_data"
            if market_status == "CLOSED" else "live_market_data"
        ),
    }
    if ltp is None:
        unavailable["reason"] = "Underlying LTP unavailable"
        return unavailable

    expiries = get_option_expiries(security_id, segment)
    expiry = _nearest_expiry(expiries)
    if not expiry:
        unavailable["reason"] = "No upcoming expiry returned by Dhan"
        return unavailable
    time.sleep(3)
    response = get_option_chain(security_id, expiry, segment)
    data = response.get("data", {}) if isinstance(response, dict) else {}
    chain = data.get("oc", {}) if isinstance(data, dict) else {}
    if not isinstance(chain, dict):
        unavailable["reason"] = "Dhan returned no option-chain strikes"
        return unavailable

    strikes = []
    for raw_strike, pair in chain.items():
        try:
            strike = float(raw_strike)
        except (TypeError, ValueError):
            continue
        if not isinstance(pair, dict):
            continue
        if isinstance(pair.get("ce"), dict) and isinstance(pair.get("pe"), dict):
            strikes.append((strike, pair))
    strikes.sort(key=lambda item: item[0])
    if not strikes:
        unavailable["reason"] = "No valid CE/PE strike pairs returned"
        return unavailable

    strike_values = [item[0] for item in strikes]
    atm_index = min(
        range(len(strike_values)),
        key=lambda index: abs(strike_values[index] - ltp),
    )
    intervals = [
        strike_values[index + 1] - strike_values[index]
        for index in range(len(strike_values) - 1)
        if strike_values[index + 1] > strike_values[index]
    ]
    strike_interval = min(intervals) if intervals else None
    selected = strikes[max(0, atm_index - 5):atm_index + 6]

    quote_now = datetime.now(IST)
    quote_date = quote_now.date().isoformat()
    quote_time = quote_now.strftime("%H:%M:%S")
    rows = []
    for strike, pair in selected:
        ce, pe = pair["ce"], pair["pe"]
        for option_type, option in (("CE", ce), ("PE", pe)):
            rows.append({
                "Date": quote_date,
                "Time": quote_time,
                "Strike": strike,
                "Option Type": option_type,
                "Open": _option_field(option, "open", "open_price"),
                "High": _option_field(option, "high", "high_price"),
                "Low": _option_field(option, "low", "low_price"),
                "LTP": _option_field(option, "last_price", "LTP", "ltp"),
                "strike": strike,
                "CE_LTP": _option_value(ce, "last_price"),
                "CE_best_bid": _option_value(ce, "top_bid_price"),
                "CE_best_ask": _option_value(ce, "top_ask_price"),
                "CE_sell_exit_price": _option_value(ce, "top_bid_price"),
                "CE_open_interest": ce.get("oi"),
                "CE_volume": ce.get("volume"),
                "PE_LTP": _option_value(pe, "last_price"),
                "PE_best_bid": _option_value(pe, "top_bid_price"),
                "PE_best_ask": _option_value(pe, "top_ask_price"),
                "PE_sell_exit_price": _option_value(pe, "top_bid_price"),
                "PE_open_interest": pe.get("oi"),
                "PE_volume": pe.get("volume"),
            })

    return {
        "status": "ok",
        "underlying": name,
        "underlying_ltp": ltp,
        "expiry": expiry,
        "atm_strike": strike_values[atm_index],
        "strike_interval": strike_interval,
        "quote_timestamp": _timestamp(),
        "quote_status": (
            "last_available_market_data"
            if market_status == "CLOSED" else "live_market_data"
        ),
        "strikes": rows,
    }


def analyse_index(security_id, name, option_segment, market_status):
    ltp_data = get_ltp({"IDX_I": [security_id]}).get(security_id, {})
    ohlc_data = _ohlc_details(
        get_ohlc({"IDX_I": [security_id]}).get(security_id, {})
    )
    ltp = _value(ltp_data, "last_price", "LTP", "ltp")
    open_price = _value(ohlc_data, "open", "open_price")
    high_price = _value(ohlc_data, "high", "high_price")
    low_price = _value(ohlc_data, "low", "low_price")
    previous_close = _value(
        ohlc_data, "close", "close_price", "prev_close", "previousClose"
    )
    result = {
        "name": name, "open": open_price, "high": high_price,
        "low": low_price, "ltp": ltp,
        "prev_close": previous_close, "change": None, "change_pct": None,
        "CE": "NO_DATA", "PE": "NO_DATA",
    }
    if ltp is not None and previous_close is not None:
        result["change"] = round(ltp - previous_close, 2)
        result["change_pct"] = round(result["change"] / previous_close * 100, 2)
        if result["change"] > 0:
            result.update({"CE": "BUY", "PE": "SELL"})
        elif result["change"] < 0:
            result.update({"CE": "SELL", "PE": "BUY"})
        else:
            result.update({"CE": "HOLD", "PE": "HOLD"})
    result["option_chain"] = fetch_index_option_chain(
        security_id, name, option_segment, ltp, market_status
    )
    return result


def scan_stocks():
    ids = list(NIFTY50_SECURITY_IDS.values())
    ltp_data = get_ltp({"NSE_EQ": ids})
    ohlc_data = get_ohlc({"NSE_EQ": ids})
    stocks = []
    excluded = dict(EXCLUDED_STOCKS)

    for symbol, (security_id, name) in NIFTY50_INSTRUMENTS.items():
        ltp = _value(ltp_data.get(security_id, {}), "last_price", "LTP", "ltp")
        ohlc = _ohlc_details(ohlc_data.get(security_id, {}))
        open_price = _value(ohlc, "open", "open_price")
        low_price = _value(ohlc, "low", "low_price")
        previous_close = _value(
            ohlc,
            "close", "close_price", "prev_close", "previousClose",
        )
        if ltp is None:
            excluded[symbol] = "missing or invalid LTP"
            continue
        if previous_close is None:
            excluded[symbol] = "missing or invalid previous close"
            continue
        if open_price is None or low_price is None:
            excluded[symbol] = "missing or invalid open/low"
            continue
        high_price = _value(ohlc, "high", "high_price")
        if high_price is None:
            excluded[symbol] = "missing or invalid high"
            continue
        change = round(ltp - previous_close, 2)
        stocks.append({
            "symbol": symbol, "name": name, "security_id": security_id,
            "exchange_segment": "NSE_EQ", "instrument": "EQUITY",
            "open": open_price, "high": high_price, "low": low_price,
            "ltp": ltp,
            "option_chain": {
                "status": "Option Data Unavailable",
                "reason": "Option chain is fetched for top gainers only",
            },
            "prev_close": previous_close,
            "change": change,
            "change_pct": round(change / previous_close * 100, 2),
        })
    return sorted(stocks, key=lambda item: item["change_pct"], reverse=True), excluded


def main():
    now = datetime.now(IST)
    if not credentials_configured():
        print("ERROR: Dhan credentials are missing or invalid.")
        dhan_output({"status": "failed", "message": "Credentials missing"})
        return

    print("=" * 72)
    print(f"DHAN TRADING DASHBOARD - {now.strftime('%Y-%m-%d %H:%M:%S IST')}")
    print("Mode: SIMULATION (illustrative analysis only)")
    print(f"Verified NIFTY 50 stocks: {VERIFIED_STOCK_COUNT}/50")
    print("=" * 72)

    market_status = _market_status(now)
    nifty = analyse_index(NIFTY_ID, "NIFTY 50", "IDX_I", market_status)
    sensex = analyse_index(SENSEX_ID, "SENSEX", "IDX_I", market_status)
    if nifty["ltp"] is None and sensex["ltp"] is None:
        print("ERROR: No valid index market data was returned.")
        dhan_output({"status": "failed", "message": "Market data unavailable"})
        return

    stocks, excluded = scan_stocks()
    gainers = [item for item in stocks if item["change_pct"] > 0][:10]
    for stock in gainers:
        stock["option_chain"] = fetch_option_details(stock)
    losers = sorted(
        (item for item in stocks if item["change_pct"] < 0),
        key=lambda item: item["change_pct"],
    )[:5]
    payload = {
        "nifty": nifty, "sensex": sensex,
        "verified_stock_count": f"{VERIFIED_STOCK_COUNT}/50",
        "validated_stock_count": len(stocks),
        "top_gainers": gainers, "top_losers": losers,
        "excluded_stocks": excluded,
        "data_timestamp": now.isoformat(),
        "market_status": market_status,
    }
    print(json.dumps(payload, indent=2, allow_nan=False))
    dhan_output({
        "status": "done",
        "result": {
            "nifty_ltp": nifty["ltp"] or 0,
            "sensex_ltp": sensex["ltp"] or 0,
            "nifty_CE": nifty["CE"],
            "nifty_PE": nifty["PE"],
            "sensex_CE": sensex["CE"],
            "sensex_PE": sensex["PE"],
            "verified_stock_count": f"{VERIFIED_STOCK_COUNT}/50",
            "validated_stock_count": len(stocks),
            "excluded_count": len(excluded),
            "data_timestamp": now.isoformat(),
        },
        "message": f"Dashboard updated {_timestamp()}",
    })


if __name__ == "__main__":
    main()
