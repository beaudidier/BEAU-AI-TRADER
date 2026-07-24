import ta

from config import EMA_FAST, EMA_SLOW, RSI_PERIOD


def add_indicators(df):
    """
    Voegt alle technische indicatoren toe aan de dataframe.
    """

    df = df.copy()

    # EMA's
    df["EMA20"] = ta.trend.ema_indicator(
        close=df["Close"],
        window=EMA_FAST
    )

    df["EMA50"] = ta.trend.ema_indicator(
        close=df["Close"],
        window=EMA_SLOW
    )

    # RSI
    df["RSI"] = ta.momentum.rsi(
        close=df["Close"],
        window=RSI_PERIOD
    )

    return df