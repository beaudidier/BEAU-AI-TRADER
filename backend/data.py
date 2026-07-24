import yfinance as yf
import pandas as pd

from config import PERIOD, INTERVAL


def get_stock_data(ticker, period=PERIOD, interval=INTERVAL, start=None, end=None):
    """
    Download historische koersdata van Yahoo Finance.
    """

    try:
        download_options = {
            "tickers": ticker,
            "interval": interval,
            "progress": False,
            "auto_adjust": True,
            "group_by": "column",
        }

        if start is not None:
            download_options["start"] = start
            download_options["end"] = end
        else:
            download_options["period"] = period

        df = yf.download(**download_options)

        if df.empty:
            return None

        # Nieuwere versies van yfinance geven soms een MultiIndex terug.
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Zorg dat alle kolommen echte Series zijn
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in df.columns:
                df[col] = df[col].squeeze()

        return df

    except Exception as e:
        print(f"Fout bij ophalen van {ticker}: {e}")
        return None
