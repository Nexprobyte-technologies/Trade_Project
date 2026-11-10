"""Validation helpers for market data used by the dashboard."""


def _valid_number(value):
    return (
        isinstance(value, (int, float))
        and value == value
        and value != float("inf")
        and value != float("-inf")
    )


def prepare_candles(raw_data):
    """Validate, deduplicate, and chronologically sort candle columns."""
    if not isinstance(raw_data, dict):
        return []
    columns = [
        raw_data.get(key, [])
        for key in ("timestamp", "open", "high", "low", "close", "volume")
    ]
    if not all(isinstance(column, list) for column in columns):
        return []
    if not columns[0] or len({len(column) for column in columns}) != 1:
        return []

    rows = []
    for row in zip(*columns):
        timestamp, open_, high, low, close, volume = row
        values = (open_, high, low, close, volume)
        if not _valid_number(timestamp) or not all(
            _valid_number(value) for value in values
        ):
            continue
        if min(open_, high, low, close) <= 0 or volume < 0 or low > high:
            continue
        if high < max(open_, close) or low > min(open_, close):
            continue
        rows.append((
            float(timestamp), float(open_), float(high), float(low),
            float(close), float(volume),
        ))

    unique = {row[0]: row for row in rows}
    return [unique[key] for key in sorted(unique)]
