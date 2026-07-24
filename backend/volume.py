import pandas as pd


def add_volume_analysis(df, period=20):
    """
    Voegt volume-analyse toe aan de dataframe.
    """

    df = df.copy()

    df["Volume_MA"] = df["Volume"].rolling(period).mean()

    df["HighVolume"] = df["Volume"] > df["Volume_MA"]

    return df


def get_volume_score(df):
    """
    Geeft een volumescore terug.
    """

    current = df.iloc[-1]

    if bool(current["HighVolume"]):
        return 10

    return 0