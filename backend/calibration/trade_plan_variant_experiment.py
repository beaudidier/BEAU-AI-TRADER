"""Compare isolated, executable trade-plan variants on the cached audit data.

This is deliberately an experiment runner.  It replays the existing
institutional signals but does not modify the production trade-plan engine,
scoring model, weights, thresholds, or signal dates.

Run from the repository root:
    PYTHONPATH=backend python3 -m calibration.trade_plan_variant_experiment
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from atr import add_atr
from backtesting.execution import entry_fill_price, simulate_long_trade
from backtesting.portfolio_risk import (
    calculate_chronological_portfolio,
    chronological_drawdown_r,
)
from calibration.run_audit import (
    DATASET_CACHE,
    MAX_HOLDING_DAYS,
    OUTPUT,
    SLIPPAGE_BPS,
    TICKERS,
    TRANSACTION_COST_BPS,
    WARMUP_BARS,
    _band,
)
from engines.engine_utils import safe_float
from engines.institutional_engine import calculate_institutional_analysis

BOOTSTRAP_SAMPLES = 10_000
RANDOM_SEED = 20260725
VARIANTS = ("next_open_atr", "pullback", "breakout")
VARIANT_LABELS = {
    "next_open_atr": "Variant A — Next-open ATR",
    "pullback": "Variant B — Pullback",
    "breakout": "Variant C — Breakout",
}


def _load_history(ticker: str) -> pd.DataFrame:
    return pd.read_csv(DATASET_CACHE / f"{ticker}.csv", index_col=0, parse_dates=True)


def _regime(analysis: dict) -> str:
    return "Risk-on" if analysis["engines"]["market_regime"]["score"] >= 60 else "Defensive"


def build_candidates() -> tuple[list[dict], dict[str, pd.DataFrame]]:
    """Generate one immutable set of close-of-candle signals for all variants."""
    histories = {ticker: _load_history(ticker) for ticker in TICKERS}
    benchmark = _load_history("SPY")
    candidates: list[dict] = []
    for ticker, sector in TICKERS.items():
        data = histories[ticker]
        # Three possible entry candles plus the complete 30-session exit window.
        for index in range(WARMUP_BARS, len(data) - MAX_HOLDING_DAYS - 3):
            history = data.iloc[:index + 1].copy()
            benchmark_history = benchmark.loc[:history.index[-1]].copy()
            if len(benchmark_history) < WARMUP_BARS:
                continue
            try:
                analysis = calculate_institutional_analysis(history, benchmark_history)
                atr = safe_float(add_atr(history)["ATR"].iloc[-1])
            except (KeyError, TypeError, ValueError, ArithmeticError):
                continue
            if not atr or atr <= 0:
                continue
            close = float(data.iloc[index]["Close"])
            candidates.append({
                "ticker": ticker,
                "sector": sector,
                "index": index,
                "signal_date": str(data.index[index].date()),
                "confidence": int(analysis["overall_score"]),
                "band": _band(int(analysis["overall_score"])),
                "verdict": analysis["recommendation"],
                "market_regime": _regime(analysis),
                "atr": float(atr),
                "signal_close": close,
                "ema20": float(history["Close"].ewm(span=20, adjust=False).mean().iloc[-1]),
                "swing_low_20": float(history.tail(20)["Low"].min()),
                "signal_high": float(data.iloc[index]["High"]),
                "signal_low": float(data.iloc[index]["Low"]),
            })
    candidates.sort(key=lambda row: (row["signal_date"], row["ticker"]))
    return candidates, histories


def _plan(entry_raw: float, stop: float, candidate: dict) -> tuple[dict | None, str | None]:
    entry = entry_fill_price(entry_raw, SLIPPAGE_BPS)
    risk = entry - stop
    if not np.isfinite(entry) or not np.isfinite(stop) or stop <= 0 or risk <= 0:
        return None, "Invalid entry or stop after executable fill"
    return {
        "entry": entry,
        "stop": stop,
        "target_1": entry + 1.5 * risk,
        "target_2": entry + 3.0 * risk,
    }, None


def next_open_atr_plan(candidate: dict, data: pd.DataFrame) -> tuple[dict | None, str | None]:
    index = candidate["index"] + 1
    return _plan(float(data.iloc[index]["Open"]), float(data.iloc[index]["Open"]) - 1.5 * candidate["atr"], candidate)


def pullback_plan(candidate: dict, data: pd.DataFrame) -> tuple[dict | None, str | None]:
    limit = candidate["ema20"]
    for index in range(candidate["index"] + 1, candidate["index"] + 4):
        candle = data.iloc[index]
        if float(candle["Low"]) <= limit <= float(candle["High"]):
            plan, reason = _plan(limit, candidate["swing_low_20"] - candidate["atr"], candidate)
            if plan is None:
                return None, reason
            if (plan["entry"] - plan["stop"]) / plan["entry"] > 0.05:
                return None, "Position risk exceeds 5% of entry price"
            plan["entry_index"] = index
            return plan, None
    return None, "Pullback limit was not traded within 3 candles"


def breakout_plan(candidate: dict, data: pd.DataFrame) -> tuple[dict | None, str | None]:
    trigger = candidate["signal_high"] + 0.1 * candidate["atr"]
    stop = candidate["signal_low"] - 0.1 * candidate["atr"]
    for index in range(candidate["index"] + 1, candidate["index"] + 4):
        candle = data.iloc[index]
        if float(candle["High"]) >= trigger:
            # A stop order gaps through its trigger at the opening price.
            raw_fill = max(float(candle["Open"]), trigger)
            plan, reason = _plan(raw_fill, stop, candidate)
            if plan is None:
                return None, reason
            if (plan["entry"] - plan["stop"]) / plan["entry"] > 0.05:
                return None, "Position risk exceeds 5% of entry price"
            plan["entry_index"] = index
            return plan, None
    return None, "Breakout trigger was not reached within 3 candles"


def _variant_plan(variant: str, candidate: dict, data: pd.DataFrame) -> tuple[dict | None, str | None]:
    if variant == "next_open_atr":
        plan, reason = next_open_atr_plan(candidate, data)
        if plan is not None:
            plan["entry_index"] = candidate["index"] + 1
        return plan, reason
    if variant == "pullback":
        return pullback_plan(candidate, data)
    return breakout_plan(candidate, data)


def _bootstrap_expectancy(rows: list[dict]) -> list[float] | None:
    if not rows:
        return None
    values = np.array([row["r_multiple"] for row in rows], dtype=float)
    rng = np.random.default_rng(RANDOM_SEED + len(rows))
    draws = rng.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, len(values)))
    means = values[draws].mean(axis=1)
    return [round(float(np.percentile(means, 2.5)), 4), round(float(np.percentile(means, 97.5)), 4)]


def _metrics(rows: list[dict], rejected: int = 0) -> dict:
    if not rows:
        return {"valid_trades": 0, "rejected_trades": rejected, "win_rate": 0, "expectancy": 0, "profit_factor": None, "average_r": 0, "maximum_drawdown": 0, "tp1_rate": 0, "tp2_rate": 0, "stop_rate": 0, "average_holding_time": 0, "expectancy_95_ci": None}
    values = [row["r_multiple"] for row in rows]
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    return {
        "valid_trades": len(rows), "rejected_trades": rejected,
        "win_rate": round(100 * sum(value > 0 for value in values) / len(values), 2),
        "expectancy": round(float(np.mean(values)), 4),
        "profit_factor": round(gains / losses, 4) if losses else None,
        "average_r": round(float(np.mean(values)), 4),
        "maximum_drawdown": chronological_drawdown_r(rows),
        "tp1_rate": round(100 * sum(row["tp1_hit"] for row in rows) / len(rows), 2),
        "tp2_rate": round(100 * sum(row["tp2_hit"] for row in rows) / len(rows), 2),
        "stop_rate": round(100 * sum(row["stop_hit"] for row in rows) / len(rows), 2),
        "average_holding_time": round(float(np.mean([row["holding_days"] for row in rows])), 2),
        "expectancy_95_ci": _bootstrap_expectancy(rows),
    }


def _run_variant(variant: str, candidates: list[dict], histories: dict[str, pd.DataFrame], oos_keys: set[tuple[str, int]]) -> tuple[list[dict], list[dict]]:
    accepted: list[dict] = []
    rejected: list[dict] = []
    active_until: dict[str, int] = defaultdict(lambda: -1)
    for candidate in sorted(candidates, key=lambda row: (row["ticker"], row["index"])):
        shared = {key: value for key, value in candidate.items() if key != "index"}
        shared.update({"variant": variant, "variant_name": VARIANT_LABELS[variant], "trade_id": f"{variant}-{candidate['ticker']}-{candidate['signal_date']}", "out_of_sample": (candidate["ticker"], candidate["index"]) in oos_keys})
        if candidate["index"] + 1 <= active_until[candidate["ticker"]]:
            rejected.append({"record_type": "REJECTED", **shared, "reason": "Overlapping position for ticker"})
            continue
        plan, reason = _variant_plan(variant, candidate, histories[candidate["ticker"]])
        if plan is None:
            rejected.append({"record_type": "REJECTED", **shared, "reason": reason or "Plan could not be executed"})
            continue
        outcome = simulate_long_trade(
            histories[candidate["ticker"]], plan["entry_index"], plan["entry"], plan["stop"], plan["target_1"], plan["target_2"],
            shares=100, max_holding_days=MAX_HOLDING_DAYS, slippage_bps=SLIPPAGE_BPS, transaction_cost_bps=TRANSACTION_COST_BPS,
        )
        if outcome is None:
            rejected.append({"record_type": "REJECTED", **shared, "reason": "Execution simulation rejected invalid trade"})
            continue
        active_until[candidate["ticker"]] = outcome["exit_index"]
        accepted.append({
            "record_type": "TRADE", **shared,
            "entry_date": str(histories[candidate["ticker"]].index[plan["entry_index"]].date()),
            "entry_price": plan["entry"], "stop_loss": plan["stop"], "target_1": plan["target_1"], "target_2": plan["target_2"],
            "exit_date": str(histories[candidate["ticker"]].index[outcome["exit_index"]].date()), **outcome,
        })
    return accepted, rejected


def _oos_summary(trades: list[dict], rejected: list[dict]) -> dict:
    oos_trades = [row for row in trades if row["out_of_sample"]]
    oos_rejected = [row for row in rejected if row["out_of_sample"]]
    by_band = {label: _metrics([row for row in oos_trades if row["band"] == band], sum(row["band"] == band for row in oos_rejected)) for label, band in (("WATCH", "60-74"), ("BUY", "75-89"))}
    regimes = sorted({row["market_regime"] for row in oos_trades + oos_rejected})
    by_regime = {regime: _metrics([row for row in oos_trades if row["market_regime"] == regime], sum(row["market_regime"] == regime for row in oos_rejected)) for regime in regimes}
    return {
        "overall": _metrics(oos_trades, len(oos_rejected)),
        "by_band": by_band,
        "by_market_regime": by_regime,
        "rejection_reasons": dict(sorted(Counter(row["reason"] for row in oos_rejected).items())),
    }


def _recommendation(summaries: dict) -> dict:
    eligible = []
    # M27 BUY expectancy was -0.0531R. A positive lower CI bound is the
    # deliberately stricter, materially-better condition for this experiment.
    for variant, summary in summaries.items():
        metrics = summary["overall"]
        ci = metrics["expectancy_95_ci"]
        passes = bool(metrics["valid_trades"] >= 30 and metrics["expectancy"] > 0 and (metrics["profit_factor"] or 0) > 1 and ci and ci[0] > 0)
        if passes:
            eligible.append((metrics["expectancy"], variant))
    if not eligible:
        return {"recommended_variant": None, "decision": "No variant qualifies for a production recommendation.", "criteria": "Requires >=30 OOS trades, positive expectancy, profit factor above 1, and a positive lower 95% bootstrap expectancy bound."}
    _, variant = max(eligible)
    return {"recommended_variant": variant, "decision": f"{VARIANT_LABELS[variant]} satisfies all pre-defined experiment gates.", "criteria": "Requires >=30 OOS trades, positive expectancy, profit factor above 1, and a positive lower 95% bootstrap expectancy bound."}


def run_experiment() -> dict:
    candidates, histories = build_candidates()
    split = int(len(candidates) * 0.7)
    oos_keys = {(row["ticker"], row["index"]) for row in candidates[split:]}
    details: dict[str, dict] = {}
    all_rows: list[dict] = []
    for variant in VARIANTS:
        trades, rejected = _run_variant(variant, candidates, histories, oos_keys)
        details[variant] = _oos_summary(trades, rejected)
        details[variant]["chronological_portfolio"] = (
            calculate_chronological_portfolio(
                [row for row in trades if row["out_of_sample"]]
            )
        )
        all_rows.extend(trades + rejected)
    return {
        "audit_status": "completed",
        "parameters": {
            "dataset": "existing cached calibration dataset", "signals": "existing close-of-candle institutional signals; unchanged", "split": "chronological 70/30 by shared signal date", "candidate_signals": len(candidates), "out_of_sample_candidate_signals": len(oos_keys), "slippage_bps_per_side": SLIPPAGE_BPS, "transaction_cost_bps_per_side": TRANSACTION_COST_BPS, "max_holding_days": MAX_HOLDING_DAYS, "partial_exit": "50% at TP1; original stop remains for the remainder", "same_candle_rule": "stop first",
        },
        "variants": details,
        "recommendation": _recommendation(details),
        "rows": all_rows,
    }


def write_artifacts(results: dict) -> None:
    OUTPUT.mkdir(exist_ok=True)
    payload = {key: value for key, value in results.items() if key != "rows"}
    (OUTPUT / "trade_plan_variant_results.json").write_text(json.dumps(payload, indent=2))
    rows: list[dict] = []
    for row in results["rows"]:
        shared = {key: value for key, value in row.items() if key != "exit_legs"}
        if row["record_type"] == "TRADE":
            for number, leg in enumerate(row["exit_legs"], start=1):
                rows.append({**shared, "leg_number": number, **{f"leg_{key}": value for key, value in leg.items()}})
        else:
            rows.append(shared)
    with (OUTPUT / "trade_plan_variant_trades.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}) if rows else ["ticker"], lineterminator="\n")
        writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    report = run_experiment()
    write_artifacts(report)
    print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
