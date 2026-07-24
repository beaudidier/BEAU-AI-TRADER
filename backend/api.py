import math

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from config import WATCHLIST
from data import get_stock_data
from indicators import add_indicators
from atr import add_atr
from volume import add_volume_analysis
from scoring import calculate_score
from support_resistance import calculate_support_resistance

app = FastAPI(title="BEAU AI TRADER API")

TIMEFRAMES = {
    "1D": {"period": "1d", "interval": "5m"},
    "1W": {"period": "5d", "interval": "30m"},
    "1M": {"period": "1mo", "interval": "1h"},
    "3M": {"period": "3mo", "interval": "1d"},
    "6M": {"period": "6mo", "interval": "1d"},
    "1Y": {"period": "1y", "interval": "1d"},
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "running"}


@app.get("/scan")
def scan():

    results = []

    for ticker in WATCHLIST:

        df = get_stock_data(ticker)

        if df is None:
            continue

        df = add_indicators(df)
        df = add_atr(df)
        df = add_volume_analysis(df)

        score = calculate_score(df)

        current = df.iloc[-1]

        results.append(
            {
                "ticker": ticker,
                "price": round(float(current["Close"]), 2),
                "ema20": round(float(current["EMA20"]), 2),
                "ema50": round(float(current["EMA50"]), 2),
                "rsi": round(float(current["RSI"]), 2),
                "atr": round(float(current["ATR"]), 2),
                "support": score["support"],
                "resistance": score["resistance"],
                "score": score["score"],
                "recommendation": score["recommendation"],
                "reasons": score["reasons"],
            }
        )

    results.sort(key=lambda x: x["score"], reverse=True)

    return results


@app.get("/stocks/{ticker}/history")
def get_stock_history(ticker: str, timeframe: str = "6M"):
    """Return chart-ready OHLC and indicator data for a stock."""

    normalized_timeframe = timeframe.upper()
    settings = TIMEFRAMES.get(normalized_timeframe)

    if settings is None:
        raise HTTPException(status_code=400, detail="Unsupported timeframe")

    df = get_stock_data(ticker.upper(), **settings)

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No market data found")

    df = add_indicators(df)
    levels = calculate_support_resistance(df)

    candles = []
    ema20 = []
    ema50 = []

    for timestamp, row in df.iterrows():
        time = int(timestamp.timestamp())
        candles.append(
            {
                "time": time,
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
            }
        )

        if not math.isnan(float(row["EMA20"])):
            ema20.append({"time": time, "value": round(float(row["EMA20"]), 2)})

        if not math.isnan(float(row["EMA50"])):
            ema50.append({"time": time, "value": round(float(row["EMA50"]), 2)})

    return {
        "ticker": ticker.upper(),
        "timeframe": normalized_timeframe,
        "candles": candles,
        "ema20": ema20,
        "ema50": ema50,
        "support": levels["support"],
        "resistance": levels["resistance"],
    }
