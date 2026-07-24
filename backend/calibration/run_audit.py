"""Run a chronological, next-open calibration audit of the current decision engine.

Usage from repository root: PYTHONPATH=backend python3 -m calibration.run_audit
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from atr import add_atr
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
    if entry <= stop:
        return None
    risk = entry - stop; tp1 = tp2 = stopped = False; high_seen = entry; low_seen = entry; exit_price = None; exit_index = None
    for index in range(entry_index, min(len(data), entry_index + MAX_HOLDING_DAYS)):
        candle = data.iloc[index]; low, high = float(candle["Low"]), float(candle["High"]); high_seen, low_seen = max(high_seen, high), min(low_seen, low)
        # Conservative OHLC assumption: stop wins any same-candle ambiguity.
        if low <= stop:
            stopped, exit_price, exit_index = True, stop, index; break
        if high >= target_1: tp1 = True
        if high >= target_2:
            tp2, exit_price, exit_index = True, target_2, index; break
    if exit_price is None:
        exit_index = min(len(data) - 1, entry_index + MAX_HOLDING_DAYS - 1); exit_price = float(data.iloc[exit_index]["Close"])
    cost = entry * (SLIPPAGE_BPS + TRANSACTION_COST_BPS) / 10_000 + exit_price * (SLIPPAGE_BPS + TRANSACTION_COST_BPS) / 10_000
    return {"tp1_hit": tp1, "tp2_hit": tp2, "stop_hit": stopped, "exit_price": exit_price, "holding_days": exit_index - entry_index + 1, "return_pct": ((exit_price - entry - cost) / entry) * 100, "r_multiple": (exit_price - entry - cost) / risk, "mfe_r": (high_seen - entry) / risk, "mae_r": (low_seen - entry) / risk}


def run_audit(provider=None) -> dict:
    provider = provider or get_market_data_provider(); end = date.today(); start = end - timedelta(days=3 * 365)
    # Yahoo reliably serves this rolling window while explicit future-dated
    # ranges can be rejected by the development provider.
    benchmark = provider.get_history("SPY", period="3y", interval="1d")
    trades: list[dict] = []; failures: list[dict] = []
    for ticker, sector in TICKERS.items():
        data = provider.get_history(ticker, period="3y", interval="1d")
        if data is None or len(data) < WARMUP_BARS + 30:
            failures.append({"ticker": ticker, "reason": "missing or insufficient daily history"}); continue
        for index in range(WARMUP_BARS, len(data) - 1):
            history = data.iloc[:index + 1].copy(); benchmark_history = benchmark.loc[:history.index[-1]].copy() if benchmark is not None else None
            if benchmark_history is not None and len(benchmark_history) < WARMUP_BARS: continue
            try:
                analysis = calculate_institutional_analysis(history, benchmark_history); enriched = add_atr(history); atr = safe_float(enriched["ATR"].iloc[-1]); levels = calculate_support_resistance(enriched)
                if not atr or atr <= 0: continue
                plan = calculate_trade_plan(ticker, enriched, 10_000, 1, {"confidence": analysis["overall_score"]}, levels["support"], levels["resistance"], atr)
                entry = float(data.iloc[index + 1]["Open"]) * (1 + SLIPPAGE_BPS / 10_000)
                outcome = _simulate(data, index + 1, entry, plan["stop_loss"], plan["target_1"], plan["target_2"])
                if outcome is None: continue
            except Exception:
                continue
            # One trade per ticker at a time: signal days inside the next holding window are skipped.
            if trades and trades[-1].get("ticker") == ticker and pd.Timestamp(trades[-1]["exit_date"]) >= data.index[index + 1]: continue
            engines = analysis["engines"]
            trades.append({"ticker": ticker, "sector": sector, "signal_date": str(data.index[index].date()), "entry_date": str(data.index[index + 1].date()), "exit_date": str(data.index[index + outcome["holding_days"]].date()) if index + outcome["holding_days"] < len(data) else str(data.index[-1].date()), "confidence": analysis["overall_score"], "band": _band(analysis["overall_score"]), "verdict": analysis["recommendation"], "market_regime": "Risk-on" if engines["market_regime"]["score"] >= 60 else "Defensive", **{f"{name}_score": result["score"] for name, result in engines.items()}, **outcome})
    trades.sort(key=lambda row: row["signal_date"])
    split = int(len(trades) * .7); calibration, oos = trades[:split], trades[split:]
    grouped = lambda rows, field: {key: _metrics([row for row in rows if str(row[field]) == key]) for key in sorted({str(row[field]) for row in rows})}
    bands = lambda rows: {band: _metrics([row for row in rows if row["band"] == band]) for band in ("0-59", "60-74", "75-89", "90-100")}
    return {"parameters": {"tickers": len(TICKERS), "start": start.isoformat(), "end": end.isoformat(), "split": "chronological 70/30 by generated trade", "slippage_bps_per_side": SLIPPAGE_BPS, "transaction_cost_bps_per_side": TRANSACTION_COST_BPS, "max_holding_days": MAX_HOLDING_DAYS}, "provider_failures": failures, "calibration": {"overall": _metrics(calibration), "bands": bands(calibration)}, "out_of_sample": {"overall": _metrics(oos), "bands": bands(oos), "factors": {name: grouped(oos, f"{name}_score") for name in ("trend", "momentum", "volume", "support_resistance", "volatility", "relative_strength")}, "market_regime": grouped(oos, "market_regime"), "ticker": grouped(oos, "ticker"), "sector": grouped(oos, "sector")}, "trades": trades}


def write_artifacts(results: dict) -> None:
    OUTPUT.mkdir(exist_ok=True); (OUTPUT / "ai_calibration_results.json").write_text(json.dumps({key: value for key, value in results.items() if key != "trades"}, indent=2))
    with (OUTPUT / "ai_calibration_trades.csv").open("w", newline="") as handle:
        rows = results["trades"]; writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}) if rows else ["ticker"]); writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    write_artifacts(run_audit())
