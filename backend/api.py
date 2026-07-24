import math
from datetime import date, timedelta

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import WATCHLIST
from data import get_stock_data
from indicators import add_indicators
from atr import add_atr
from volume import add_volume_analysis
from scoring import calculate_score
from support_resistance import calculate_support_resistance
from engines.confidence_engine import calculate_confidence
from engines.institutional_engine import calculate_institutional_analysis
from engines.engine_utils import has_valid_market_data, safe_float
from engines.trade_plan_engine import calculate_trade_plan
from backtesting.runner import run_backtest
from saas.middleware import RateLimitReadyMiddleware
from saas.router import router as saas_router
from briefing import build_daily_briefing

app = FastAPI(title="BEAU AI TRADER API")
app.add_middleware(RateLimitReadyMiddleware)
app.include_router(saas_router)


class BacktestRequest(BaseModel):
    ticker: str
    start_date: date
    end_date: date
    minimum_confidence: int = Field(default=65, ge=0, le=100)
    account_size: float = Field(default=10000, gt=0)
    risk_percent: float = Field(default=1, gt=0, le=100)

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


@app.get("/briefing")
def daily_briefing():
    return build_daily_briefing(WATCHLIST, get_stock_data)


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


@app.get("/analysis/{ticker}")
def get_stock_analysis(ticker: str):
    """Return a weighted multi-engine confidence score for a ticker."""

    df = get_stock_data(ticker.upper(), period="2y", interval="1d")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No market data found")
    if not has_valid_market_data(df, minimum_rows=200):
        raise HTTPException(status_code=422, detail="Insufficient valid market data for analysis")

    benchmark_df = get_stock_data("SPY", period="2y", interval="1d")
    return calculate_institutional_analysis(df, benchmark_df)


@app.get("/trade-plan/{ticker}")
def get_trade_plan(
    ticker: str,
    account_size: float = Query(default=10000, gt=0),
    risk_percent: float = Query(default=1, gt=0, le=100),
):
    """Return a risk-managed trade plan informed by the confidence engine."""

    df = get_stock_data(ticker.upper(), period="2y", interval="1d")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No market data found")
    if not has_valid_market_data(df, minimum_rows=200):
        raise HTTPException(status_code=422, detail="Insufficient valid market data for trade planning")

    df = add_atr(df)
    atr = safe_float(df["ATR"].iloc[-1])
    levels = calculate_support_resistance(df)

    if atr is None or atr <= 0:
        raise HTTPException(status_code=422, detail="Unable to calculate a valid ATR")

    try:
        return calculate_trade_plan(
            ticker=ticker,
            df=df,
            account_size=account_size,
            risk_percent=risk_percent,
            confidence_output=calculate_confidence(df),
            support=levels["support"],
            resistance=levels["resistance"],
            atr=atr,
        )
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/backtest")
def backtest(request: BacktestRequest):
    """Simulate confidence-driven trade plans over a historical date range."""

    if request.start_date >= request.end_date:
        raise HTTPException(status_code=422, detail="start_date must be before end_date")

    warmup_start = request.start_date - timedelta(days=400)
    df = get_stock_data(
        request.ticker.upper(),
        interval="1d",
        start=warmup_start.isoformat(),
        end=(request.end_date + timedelta(days=1)).isoformat(),
    )

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No market data found")

    return run_backtest(
        ticker=request.ticker,
        data=df,
        start_date=request.start_date,
        end_date=request.end_date,
        minimum_confidence=request.minimum_confidence,
        account_size=request.account_size,
        risk_percent=request.risk_percent,
    )
