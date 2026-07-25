"""Run a chronological, next-open calibration audit of the current decision engine.

Usage from repository root: PYTHONPATH=backend python3 -m calibration.run_audit
"""

from __future__ import annotations

import csv
import json
import time
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from atr import add_atr
from backtesting.execution import TP1_PORTION, entry_fill_price, simulate_long_trade
from engines.engine_utils import safe_float
from engines.institutional_engine import calculate_institutional_analysis
from engines.trade_plan_engine import calculate_trade_plan
from providers import get_market_data_provider
from support_resistance import calculate_support_resistance

TICKERS = {"AAPL": "Technology", "MSFT": "Technology", "NVDA": "Technology", "AVGO": "Technology", "ORCL": "Technology", "AMZN": "Consumer Discretionary", "TSLA": "Consumer Discretionary", "HD": "Consumer Discretionary", "JPM": "Financials", "BAC": "Financials", "GS": "Financials", "UNH": "Health Care", "LLY": "Health Care", "JNJ": "Health Care", "XOM": "Energy", "CVX": "Energy", "CAT": "Industrials", "GE": "Industrials", "HON": "Industrials", "WMT": "Consumer Staples", "COST": "Consumer Staples", "KO": "Consumer Staples", "NEE": "Utilities", "DUK": "Utilities", "AMT": "Real Estate", "PLD": "Real Estate", "V": "Financials", "META": "Communication Services", "GOOGL": "Communication Services", "LIN": "Materials"}
SLIPPAGE_BPS = 5
TRANSACTION_COST_BPS = 5
MAX_HOLDING_DAYS = 30
WARMUP_BARS = 200
OUTPUT = Path(__file__).resolve().parents[2] / "artifacts"
DATASET_CACHE = OUTPUT / "calibration_dataset"
MINIMUM_CANDLES = 600
DOWNLOAD_RETRIES = 3


def _band(score: int) -> str:
    return "0-59" if score < 60 else "60-74" if score < 75 else "75-89" if score < 90 else "90-100"


def _metrics(rows: list[dict]) -> dict:
    if not rows:
        return {"signals": 0, "total_trades": 0, "tp1_hit_rate": 0, "tp2_hit_rate": 0, "stop_loss_rate": 0, "win_rate": 0, "average_return": 0, "average_r_multiple": 0, "expectancy": 0, "profit_factor": 0, "maximum_drawdown": 0, "average_holding_time": 0, "maximum_favorable_excursion": 0, "maximum_adverse_excursion": 0}
    returns = [row["return_pct"] for row in rows]; r_values = [row["r_multiple"] for row in rows]
    gross_profit = sum(value for value in r_values if value > 0); gross_loss = abs(sum(value for value in r_values if value < 0))
    equity, peak, drawdown = 0.0, 0.0, 0.0
    for value in r_values:
        equity += value; peak = max(peak, equity); drawdown = min(drawdown, equity - peak)
    return {"signals": len(rows), "total_trades": len(rows), "tp1_hit_rate": round(sum(row["tp1_hit"] for row in rows) / len(rows) * 100, 2), "tp2_hit_rate": round(sum(row["tp2_hit"] for row in rows) / len(rows) * 100, 2), "stop_loss_rate": round(sum(row["stop_hit"] for row in rows) / len(rows) * 100, 2), "win_rate": round(sum(value > 0 for value in r_values) / len(rows) * 100, 2), "average_return": round(sum(returns) / len(rows), 4), "average_r_multiple": round(sum(r_values) / len(rows), 4), "expectancy": round(sum(r_values) / len(rows), 4), "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None, "maximum_drawdown": round(drawdown, 4), "average_holding_time": round(sum(row["holding_days"] for row in rows) / len(rows), 2), "maximum_favorable_excursion": round(sum(row["mfe_r"] for row in rows) / len(rows), 4), "maximum_adverse_excursion": round(sum(row["mae_r"] for row in rows) / len(rows), 4)}


def _simulate(data: pd.DataFrame, entry_index: int, entry: float, stop: float, target_1: float, target_2: float) -> dict | None:
    """Compatibility wrapper for the shared partial-exit execution model."""
    return simulate_long_trade(
        data, entry_index, entry, stop, target_1, target_2,
        shares=100,
        max_holding_days=MAX_HOLDING_DAYS,
        slippage_bps=SLIPPAGE_BPS,
        transaction_cost_bps=TRANSACTION_COST_BPS,
    )


def _validate_history(data: pd.DataFrame | None, end: date) -> str | None:
    if data is None: return "provider returned no data"
    required = {"Open", "High", "Low", "Close", "Volume"}
    if not required.issubset(data.columns): return f"missing required OHLCV columns: {sorted(required - set(data.columns))}"
    if len(data) < MINIMUM_CANDLES: return f"only {len(data)} valid daily candles; minimum is {MINIMUM_CANDLES}"
    if data.index.has_duplicates: return "duplicate daily dates"
    if not data.index.is_monotonic_increasing: return "dates are not chronological"
    values = data.loc[:, sorted(required)].apply(pd.to_numeric, errors="coerce")
    if values.isna().any().any(): return "OHLCV contains missing or non-numeric values"
    if (values <= 0).any().any(): return "OHLCV contains non-positive values"
    if pd.Timestamp(data.index[-1]).date() >= end: return "latest candle may be incomplete"
    return None


def _load_history(provider, ticker: str, start: date, end: date) -> tuple[pd.DataFrame | None, str | None, str]:
    DATASET_CACHE.mkdir(parents=True, exist_ok=True)
    cache = DATASET_CACHE / f"{ticker}.csv"
    if cache.exists():
        try:
            cached = pd.read_csv(cache, index_col=0, parse_dates=True)
            error = _validate_history(cached, end)
            if error is None: return cached, None, "cache"
        except (OSError, ValueError, pd.errors.ParserError):
            pass
    reasons = []
    for attempt in range(1, DOWNLOAD_RETRIES + 1):
        try:
            data = provider.get_history(ticker, interval="1d", start=start.isoformat(), end=end.isoformat())
            error = _validate_history(data, end)
            if error is None:
                data.to_csv(cache)
                return data, None, "provider"
            reasons.append(f"attempt {attempt}: {error}")
        except Exception as error:
            reasons.append(f"attempt {attempt}: {type(error).__name__}: {error}")
        if attempt < DOWNLOAD_RETRIES: time.sleep(attempt * 0.2)
    return None, "; ".join(reasons), "provider"


def run_audit(provider=None) -> dict:
    provider = provider or get_market_data_provider(); end = date.today(); start = end - timedelta(days=3 * 365 + 10)
    benchmark, benchmark_error, benchmark_source = _load_history(provider, "SPY", start, end)
    trades: list[dict] = []; failures: list[dict] = []; histories: dict[str, pd.DataFrame] = {}
    if benchmark_error: failures.append({"ticker": "SPY", "reason": benchmark_error, "source": benchmark_source})
    for ticker, sector in TICKERS.items():
        data, error, source = _load_history(provider, ticker, start, end)
        if error:
            failures.append({"ticker": ticker, "reason": error, "source": source}); continue
        histories[ticker] = data
    parameters = {"tickers": len(TICKERS), "start": start.isoformat(), "end": end.isoformat(), "split": "chronological 70/30 by generated trade", "slippage_bps_per_side": SLIPPAGE_BPS, "transaction_cost_bps_per_side": TRANSACTION_COST_BPS, "tp1_portion": TP1_PORTION, "stop_management": "original stop remains in force after TP1", "max_holding_days": MAX_HOLDING_DAYS, "minimum_valid_symbols": 25, "minimum_candles_per_symbol": MINIMUM_CANDLES, "download_retries": DOWNLOAD_RETRIES}
    if len(histories) < 25 or benchmark is None:
        return {"audit_status": "blocked", "parameters": parameters, "provider_failures": failures, "validated_symbols": sorted(histories), "calibration": {"overall": _metrics([]), "bands": {band: _metrics([]) for band in ("0-59", "60-74", "75-89", "90-100")}}, "out_of_sample": {"overall": _metrics([]), "bands": {band: _metrics([]) for band in ("0-59", "60-74", "75-89", "90-100")}, "factors": {}, "market_regime": {}, "ticker": {}, "sector": {}}, "trades": []}
    for ticker, sector in TICKERS.items():
        data = histories.get(ticker)
        if data is None: continue
        # Require a complete 30-session forward window; partial observations
        # near the dataset end would bias target and stop rates downward.
        for index in range(WARMUP_BARS, len(data) - MAX_HOLDING_DAYS):
            history = data.iloc[:index + 1].copy(); benchmark_history = benchmark.loc[:history.index[-1]].copy() if benchmark is not None else None
            if benchmark_history is not None and len(benchmark_history) < WARMUP_BARS: continue
            try:
                analysis = calculate_institutional_analysis(history, benchmark_history); enriched = add_atr(history); atr = safe_float(enriched["ATR"].iloc[-1]); levels = calculate_support_resistance(enriched)
                if not atr or atr <= 0: continue
                plan = calculate_trade_plan(ticker, enriched, 10_000, 1, {"confidence": analysis["overall_score"]}, levels["support"], levels["resistance"], atr)
                entry = entry_fill_price(float(data.iloc[index + 1]["Open"]), SLIPPAGE_BPS)
                outcome = _simulate(data, index + 1, entry, plan["stop_loss"], plan["target_1"], plan["target_2"])
                if outcome is None: continue
                for leg in outcome["exit_legs"]:
                    leg["exit_date"] = str(data.index[leg["exit_index"]].date())
            except Exception:
                continue
            # One trade per ticker at a time: signal days inside the next holding window are skipped.
            if trades and trades[-1].get("ticker") == ticker and pd.Timestamp(trades[-1]["exit_date"]) >= data.index[index + 1]: continue
            engines = analysis["engines"]
            signal_date = str(data.index[index].date())
            trades.append({"trade_id": f"{ticker}-{signal_date}", "ticker": ticker, "sector": sector, "signal_date": signal_date, "entry_date": str(data.index[index + 1].date()), "exit_date": str(data.index[outcome["exit_index"]].date()), "confidence": analysis["overall_score"], "band": _band(analysis["overall_score"]), "verdict": analysis["recommendation"], "market_regime": "Risk-on" if engines["market_regime"]["score"] >= 60 else "Defensive", **{f"{name}_score": result["score"] for name, result in engines.items()}, **outcome})
    trades.sort(key=lambda row: row["signal_date"])
    split = int(len(trades) * .7); calibration, oos = trades[:split], trades[split:]
    grouped = lambda rows, field: {key: _metrics([row for row in rows if str(row[field]) == key]) for key in sorted({str(row[field]) for row in rows})}
    bands = lambda rows: {band: _metrics([row for row in rows if row["band"] == band]) for band in ("0-59", "60-74", "75-89", "90-100")}
    return {"audit_status": "completed", "parameters": parameters, "provider_failures": failures, "validated_symbols": sorted(histories), "calibration": {"overall": _metrics(calibration), "bands": bands(calibration)}, "out_of_sample": {"overall": _metrics(oos), "bands": bands(oos), "factors": {name: grouped(oos, f"{name}_score") for name in ("trend", "momentum", "volume", "support_resistance", "volatility", "relative_strength")}, "market_regime": grouped(oos, "market_regime"), "ticker": grouped(oos, "ticker"), "sector": grouped(oos, "sector")}, "trades": trades}


def write_artifacts(results: dict) -> None:
    OUTPUT.mkdir(exist_ok=True); (OUTPUT / "ai_calibration_results.json").write_text(json.dumps({key: value for key, value in results.items() if key != "trades"}, indent=2))
    with (OUTPUT / "ai_calibration_trades.csv").open("w", newline="") as handle:
        rows = []
        for trade in results["trades"]:
            shared = {key: value for key, value in trade.items() if key != "exit_legs"}
            for number, leg in enumerate(trade["exit_legs"], start=1):
                rows.append({**shared, "leg_number": number, **{f"leg_{key}": value for key, value in leg.items()}})
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}) if rows else ["ticker"], lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    write_artifacts(run_audit())
