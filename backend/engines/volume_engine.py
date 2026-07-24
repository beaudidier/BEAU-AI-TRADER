import pandas as pd

from .engine_utils import has_valid_market_data, safe_float


def calculate_volume_score(df: pd.DataFrame) -> int:
    """Score current volume relative to its 20-period moving average."""

    return analyze_volume(df)["score"]


def analyze_volume(df: pd.DataFrame) -> dict:
    """Assess relative volume against the 20-session baseline."""

    if not has_valid_market_data(df, minimum_rows=20):
        return {"score": 50, "explanation": "Insufficient valid volume data.", "confidence": 0}

    volume_sma20 = safe_float(pd.to_numeric(df["Volume"], errors="coerce").rolling(20).mean().iloc[-1])
    current_volume = safe_float(df["Volume"].iloc[-1])

    if volume_sma20 is None or current_volume is None or volume_sma20 <= 0:
        return {"score": 50, "explanation": "Volume baseline is unavailable.", "confidence": 0}

    relative_volume = current_volume / volume_sma20

    if relative_volume >= 1.5:
        score = 100
    elif relative_volume >= 1.2:
        score = 85
    elif relative_volume >= 1.0:
        score = 70
    elif relative_volume >= 0.8:
        score = 45
    else:
        score = 20

    return {"score": score, "explanation": f"Relative volume is {relative_volume:.2f}x the 20-day average.", "confidence": 100}
