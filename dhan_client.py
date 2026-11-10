"""Small, defensive wrapper around the Dhan HTTP API."""

import time
from datetime import datetime
from math import isfinite

import requests

from config import ACCESS_TOKEN, BASE_URL, CLIENT_ID, IST


def _timestamp():
    return datetime.now(IST).strftime("%H:%M:%S")


def credentials_configured():
    placeholders = {
        "", "{{CLIENT_ID}}", "{{ACCESS_TOKEN}}",
        "your_client_id", "your_new_access_token",
    }
    return CLIENT_ID not in placeholders and ACCESS_TOKEN not in placeholders


def _headers():
    return {
        "access-token": ACCESS_TOKEN,
        "client-id": CLIENT_ID,
        "Content-Type": "application/json",
    }


def _request(method, path, payload=None, retries=2):
    if not credentials_configured():
        return None

    for attempt in range(retries + 1):
        try:
            response = requests.request(
                method, f"{BASE_URL}{path}", headers=_headers(),
                json=payload, timeout=10,
            )
        except requests.RequestException as exc:
            print(f"[{_timestamp()}] {method} network error: {exc}")
            return None

        if response.status_code == 200:
            try:
                data = response.json()
            except ValueError:
                print(f"[{_timestamp()}] {method} returned invalid JSON.")
                return None
            if isinstance(data, dict) and data.get("status") == "failed":
                error = data.get("errorMessage") or data.get("data") or "request failed"
                print(f"[{_timestamp()}] {method} {path} failed: {error}")
                return None
            return data

        if response.status_code in (401, 403):
            print(f"[{_timestamp()}] Authentication failed. "
                  "Regenerate the Dhan access token and verify the client ID.")
            return None
        if response.status_code == 429 and attempt < retries:
            time.sleep(2 ** attempt)
            continue

        detail = response.text[:300]
        print(f"[{_timestamp()}] {method} {path} -> "
              f"HTTP {response.status_code}: {detail}")
        return None
    return None


def _market_data(path, segment_map):
    response = _request("POST", path, segment_map)
    if not isinstance(response, dict):
        return {}
    data = response.get("data", response)
    if not isinstance(data, dict):
        return {}
    requested = {
        int(security_id)
        for security_ids in segment_map.values()
        for security_id in security_ids
    }
    result = {}
    for segment, values in data.items():
        if segment == "status" or not isinstance(values, dict):
            continue
        for security_id, details in values.items():
            try:
                parsed_id = int(security_id)
            except (TypeError, ValueError):
                continue
            if parsed_id in requested and isinstance(details, dict):
                result[parsed_id] = details
    return result


def valid_price(value):
    return isinstance(value, (int, float)) and isfinite(value) and value > 0


def get_ltp(segment_map):
    return _market_data("/marketfeed/ltp", segment_map)


def get_ohlc(segment_map):
    return _market_data("/marketfeed/ohlc", segment_map)


def get_intraday_candles(security_id, segment, instrument, interval="5"):
    now = datetime.now(IST)
    body = {
        "securityId": str(security_id),
        "exchangeSegment": segment,
        "instrument": instrument,
        "interval": interval,
        "fromDate": now.replace(
            hour=9, minute=15, second=0, microsecond=0
        ).strftime("%Y-%m-%d %H:%M:%S"),
        "toDate": now.strftime("%Y-%m-%d %H:%M:%S"),
    }
    return _request("POST", "/charts/intraday", body)


def get_fund_limit():
    return _request("GET", "/fundlimit")


def get_option_expiries(underlying_scrip, underlying_segment="NSE_EQ"):
    response = _request(
        "POST",
        "/optionchain/expirylist",
        {
            "UnderlyingScrip": underlying_scrip,
            "UnderlyingSeg": underlying_segment,
        },
    )
    if not isinstance(response, dict) or not isinstance(response.get("data"), list):
        return []
    return [expiry for expiry in response["data"] if isinstance(expiry, str)]


def get_option_chain(underlying_scrip, expiry, underlying_segment="NSE_EQ"):
    return _request(
        "POST",
        "/optionchain",
        {
            "UnderlyingScrip": underlying_scrip,
            "UnderlyingSeg": underlying_segment,
            "Expiry": expiry,
        },
    )
