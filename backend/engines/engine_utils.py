import math

import pandas as pd


REQUIRED_MARKET_COLUMNS = ("Open", "High", "Low", "Close", "Volume")


def safe_float(value) -> float | None:
    """Return a finite float or None for missing and non-finite values."""

    try:
        number = float(value)
    except (TypeError, ValueError):
        return None

    return number if math.isfinite(number) else None


def clamp_score(value, fallback: int = 50) -> int:
    """Normalize an engine result to a JSON-safe integer score from 0 to 100."""

    number = safe_float(value)
    if number is None:
        return fallback

    return max(0, min(100, round(number)))


def has_valid_market_data(df: pd.DataFrame, minimum_rows: int = 1) -> bool:
    """Validate that OHLCV data is present, sufficiently long, and finite."""

    if df is None or len(df) < minimum_rows or any(column not in df for column in REQUIRED_MARKET_COLUMNS):
        return False

    latest = df.loc[:, REQUIRED_MARKET_COLUMNS].iloc[-1]
    return all(safe_float(value) is not None for value in latest)
