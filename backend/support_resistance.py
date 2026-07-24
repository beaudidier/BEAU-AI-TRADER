import pandas as pd


def calculate_support_resistance(df, lookback=20):
    """
    Berekent eenvoudige support en resistance.
    """

    data = df.tail(lookback)

    support = float(data["Low"].min())
    resistance = float(data["High"].max())

    return {
        "support": round(support, 2),
        "resistance": round(resistance, 2),
    }