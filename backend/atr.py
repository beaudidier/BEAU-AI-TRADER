import ta


def add_atr(df, period=14):
    """
    Voegt de Average True Range (ATR) toe aan de dataframe.
    """

    df = df.copy()

    df["ATR"] = ta.volatility.average_true_range(
        high=df["High"],
        low=df["Low"],
        close=df["Close"],
        window=period,
    )

    return df