import math
import os
from datetime import date, timedelta

import pandas as pd
import ta

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
from engines.institutional_engine import calculate_institutional_analysis, load_weights
from engines.engine_utils import has_valid_market_data, safe_float
from engines.trade_plan_engine import calculate_trade_plan
from backtesting.runner import run_backtest
from coach.coach_engine import analyze_completed_trade
from saas.middleware import RateLimitReadyMiddleware
from saas.router import router as saas_router
from saas.invites import router as beta_invites_router
from briefing import build_daily_briefing
from universe.universe_registry import (
    all_universe_health,
    scan_jobs,
    universe_health,
)
from validation.validation_engine import validation_store
from providers import get_market_data_provider
from providers.market_transparency import build_market_data_transparency
from strategies import StrategyNotFoundError, StrategyUnavailableError, strategy_registry

_previous_debug_scores: dict[str, dict] = {}

app = FastAPI(title="BEAU AI TRADER API")
app.add_middleware(RateLimitReadyMiddleware)
app.include_router(saas_router)
app.include_router(beta_invites_router)


class BacktestRequest(BaseModel):
    ticker: str
    start_date: date
    end_date: date
    minimum_confidence: int = Field(default=65, ge=0, le=100)
    account_size: float = Field(default=10000, gt=0)
    risk_percent: float = Field(default=1, gt=0, le=100)


class CoachTradeRequest(BaseModel):
    ticker: str
    entry: float
    exit: float
    stop_loss: float
    target_1: float
    pnl: float
    realized_rr: float
    confidence_score: float = Field(ge=0, le=100)
    recommendation: str
    exit_reason: str


class ScanJobRequest(BaseModel):
    market: str = Field(default="stocks")
    universe: str = Field(default="demo")
    custom_symbols: list[str] | None = None

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
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://127.0.0.1:5173,http://localhost:5173",
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {"status": "running"}


@app.get("/strategies")
def list_strategies():
    return strategy_registry.serialize()


@app.get("/universes/health")
def list_universe_health(market: str = Query(default="stocks")):
    try:
        return {"market": market, "universes": all_universe_health(market)}
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/universes/{market}/{universe}/health")
def get_universe_health(market: str, universe: str):
    try:
        return universe_health(market, universe)
    except ValueError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/briefing")
def daily_briefing():
    return build_daily_briefing(WATCHLIST, get_stock_data)


@app.get("/scan")
def scan(
    market: str = Query(default="stocks"),
    universe: str = Query(default="demo"),
    strategy: str | None = Query(default=None),
):
    if strategy is not None:
        try:
            strategy_registry.require_usable(strategy)
        except StrategyNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except StrategyUnavailableError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    if market != "stocks" or universe != "demo":
        try:
            job = scan_jobs.start(market, universe)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        if job.status != "completed":
            return {"job": job.summary(), "results": []}
        return job.results

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
        validation_store.record(ticker, score["score"], score["recommendation"], float(current["Close"]), score["support"], score["resistance"], "Unknown")

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


@app.post("/scan/jobs")
def create_scan_job(request: ScanJobRequest):
    try:
        return scan_jobs.start(request.market, request.universe, request.custom_symbols).summary()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/scan/jobs/{job_id}")
def get_scan_job(job_id: str):
    job = scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return job.summary()


@app.get("/scan/jobs/{job_id}/results")
def get_scan_job_results(job_id: str):
    job = scan_jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Scan job not found")
    return {
        "job": job.summary(),
        "results": job.results,
        "failed_symbols": job.failures,
        "failure_reasons": job.failure_reasons,
    }


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
        "latest_timestamp": df.index[-1].isoformat(),
    }


@app.get("/market-data/{ticker}/transparency")
def get_market_data_transparency(ticker: str):
    """Return quote and completed-candle provenance without changing signals."""

    normalized_ticker = ticker.upper()
    provider = get_market_data_provider()
    quote = provider.get_quote_transparency(normalized_ticker)
    daily_history = provider.get_history(
        normalized_ticker,
        period="1mo",
        interval="1d",
    )
    if quote is None and (daily_history is None or daily_history.empty):
        raise HTTPException(status_code=404, detail="No market data found")
    return build_market_data_transparency(
        ticker=normalized_ticker,
        provider=provider,
        quote=quote,
        daily_history=daily_history,
    )


@app.get("/analysis/{ticker}")
def get_stock_analysis(ticker: str):
    """Return a weighted multi-engine confidence score for a ticker."""

    df = get_stock_data(ticker.upper(), period="2y", interval="1d")

    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No market data found")
    if not has_valid_market_data(df, minimum_rows=200):
        raise HTTPException(status_code=422, detail="Insufficient valid market data for analysis")

    benchmark_df = get_stock_data("SPY", period="2y", interval="1d")
    analysis = calculate_institutional_analysis(df, benchmark_df)
    levels = calculate_support_resistance(df)
    validation_store.record(ticker, analysis["overall_score"], analysis["recommendation"], float(df["Close"].iloc[-1]), levels["support"], levels["resistance"], "Risk-on" if analysis["engines"]["market_regime"]["score"] >= 60 else "Defensive")
    return analysis


@app.get("/debug/score/{ticker}")
def debug_score(ticker: str):
    """Expose the existing deterministic score calculation without changing it."""

    df = get_stock_data(ticker.upper(), period="2y", interval="1d")
    if df is None or df.empty:
        raise HTTPException(status_code=404, detail="No market data found")
    benchmark = get_stock_data("SPY", period="2y", interval="1d")
    analysis = calculate_institutional_analysis(df, benchmark)
    close = pd.to_numeric(df["Close"], errors="coerce")
    macd = ta.trend.MACD(close=close)
    levels = calculate_support_resistance(df)
    latest = df.iloc[-1]
    weights = {name: round(weight * 100, 2) for name, weight in load_weights().items()}
    raw = {"open": safe_float(latest.get("Open")), "high": safe_float(latest.get("High")), "low": safe_float(latest.get("Low")), "close": safe_float(latest.get("Close")), "volume": safe_float(latest.get("Volume")), "ema20": safe_float(close.ewm(span=20, adjust=False).mean().iloc[-1]), "ema50": safe_float(close.ewm(span=50, adjust=False).mean().iloc[-1]), "ema200": safe_float(close.ewm(span=200, adjust=False).mean().iloc[-1]), "rsi14": safe_float(ta.momentum.rsi(close=close, window=14).iloc[-1]), "macd": safe_float(macd.macd().iloc[-1]), "macd_signal": safe_float(macd.macd_signal().iloc[-1]), "volume_sma20": safe_float(pd.to_numeric(df["Volume"], errors="coerce").rolling(20).mean().iloc[-1]), "atr14": safe_float(ta.volatility.average_true_range(high=df["High"], low=df["Low"], close=df["Close"], window=14).iloc[-1]), "support": levels["support"], "resistance": levels["resistance"]}
    missing = [name for name, value in raw.items() if value is None]
    contributions = {name: round(result["score"] * (weights[name] / 100), 2) for name, result in analysis["engines"].items()}
    previous = _previous_debug_scores.get(ticker.upper())
    changes = ["No previous debug scan is available for this ticker."] if previous is None else [f"{name.replace('_', ' ')} changed by {analysis['engines'][name]['score'] - previous['engines'][name]['score']:+.0f} points." for name in analysis["engines"] if analysis["engines"][name]["score"] != previous["engines"][name]["score"]] or ["No engine score changed from the previous debug scan."]
    response = {"provider": type(get_market_data_provider()).__name__, "data_timestamp": df.index[-1].isoformat(), "timeframe": {"period": "2y", "interval": "1d"}, "raw_indicator_values": raw, "engine_scores": analysis["engines"], "weights": weights, "weighted_contributions": contributions, "final_score": analysis["overall_score"], "final_recommendation": analysis["recommendation"], "missing_or_invalid_fields": missing, "reasons_score_changed_from_previous_scan": changes}
    _previous_debug_scores[ticker.upper()] = analysis
    return response


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
        plan = calculate_trade_plan(
            ticker=ticker,
            df=df,
            account_size=account_size,
            risk_percent=risk_percent,
            confidence_output=calculate_confidence(df),
            support=levels["support"],
            resistance=levels["resistance"],
            atr=atr,
        )
        validation_store.record(ticker, plan["confidence_score"], plan["recommendation"], plan["entry"], plan["stop_loss"], plan["target_1"], "Unknown")
        return plan
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.get("/validation/dashboard")
def validation_dashboard():
    validation_store.refresh(get_market_data_provider().get_history)
    return validation_store.dashboard()


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


@app.post("/coach/analyze")
def analyze_trade_coach(trade: CoachTradeRequest):
    """Return a deterministic post-trade coaching assessment."""

    try:
        return analyze_completed_trade(trade.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
