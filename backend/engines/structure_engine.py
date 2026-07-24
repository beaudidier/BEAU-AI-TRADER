import pandas as pd


def calculate_structure_score(df: pd.DataFrame) -> int:
    """Score market structure from recent higher and lower highs and lows."""

    data = df.tail(20)

    if len(data) < 20:
        return 50

    previous = data.iloc[:10]
    recent = data.iloc[10:]
    higher_high = recent["High"].max() > previous["High"].max()
    higher_low = recent["Low"].min() > previous["Low"].min()
    lower_high = recent["High"].max() < previous["High"].max()
    lower_low = recent["Low"].min() < previous["Low"].min()

    if higher_high and higher_low:
        return 100
    if higher_high:
        return 70
    if higher_low:
        return 65
    if lower_high and lower_low:
        return 10
    if lower_high or lower_low:
        return 30
    return 50
