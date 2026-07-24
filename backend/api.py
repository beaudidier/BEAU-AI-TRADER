from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import WATCHLIST
from data import get_stock_data
from indicators import add_indicators
from atr import add_atr
from volume import add_volume_analysis
from scoring import calculate_score

app = FastAPI(title="BEAU AI TRADER API")

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