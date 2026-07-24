import pandas as pd

from .engine_utils import has_valid_market_data, safe_float


def calculate_volume_score(df: pd.DataFrame) -> int:
    """Score current volume relative to its 20-period moving average."""

    if not has_valid_market_data(df, minimum_rows=20):
        return 50

    volume_sma20 = safe_float(pd.to_numeric(df["Volume"], errors="coerce").rolling(20).mean().iloc[-1])
    current_volume = safe_float(df["Volume"].iloc[-1])

    if volume_sma20 is None or current_volume is None or volume_sma20 <= 0:
        return 50

    relative_volume = current_volume / volume_sma20

    if relative_volume >= 1.5:
        return 100
    if relative_volume >= 1.2:
        return 85
    if relative_volume >= 1.0:
        return 70
    if relative_volume >= 0.8:
        return 45
    return 20
