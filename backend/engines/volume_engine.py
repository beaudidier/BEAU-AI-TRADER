import pandas as pd


def calculate_volume_score(df: pd.DataFrame) -> int:
    """Score current volume relative to its 20-period moving average."""

    volume_sma20 = df["Volume"].rolling(20).mean().iloc[-1]

    if pd.isna(volume_sma20) or volume_sma20 <= 0:
        return 50

    relative_volume = float(df["Volume"].iloc[-1] / volume_sma20)

    if relative_volume >= 1.5:
        return 100
    if relative_volume >= 1.2:
        return 85
    if relative_volume >= 1.0:
        return 70
    if relative_volume >= 0.8:
        return 45
    return 20
