"""Reproduce and audit the recorded calibration execution mechanics.

This module intentionally does not alter the decision model.  It reads the
cached OHLCV dataset and the generated calibration trade ledger, then reports
whether the ledger can be reproduced and how its execution assumptions affect
the result.  Run from the repository root with:

    PYTHONPATH=backend python3 -m calibration.integrity_audit
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from atr import add_atr
from calibration.run_audit import (
    DATASET_CACHE,
    MAX_HOLDING_DAYS,
    OUTPUT,
    SLIPPAGE_BPS,
    TRANSACTION_COST_BPS,
    TICKERS,
    WARMUP_BARS,
    _simulate,
)
from engines.engine_utils import safe_float
from engines.institutional_engine import calculate_institutional_analysis
from engines.trade_plan_engine import calculate_trade_plan
from support_resistance import calculate_support_resistance

BOOTSTRAP_SAMPLES = 10_000
RANDOM_SEED = 20260725
BANDS = ("0-59", "60-74", "75-89", "90-100")


def _load_history(ticker: str) -> pd.DataFrame:
    return pd.read_csv(DATASET_CACHE / f"{ticker}.csv", index_col=0, parse_dates=True)


def _number(value: object) -> float:
    return float(value) if value not in (None, "") else 0.0


def _trade_rows() -> list[dict]:
    with (OUTPUT / "ai_calibration_trades.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def _summary(returns: list[float]) -> dict:
    if not returns:
        return {"trades": 0, "win_rate": None, "average_return_pct": None, "profit_factor": None}
    gross_profit = sum(value for value in returns if value > 0)
    gross_loss = abs(sum(value for value in returns if value < 0))
    return {
        "trades": len(returns),
        "win_rate": round(sum(value > 0 for value in returns) / len(returns) * 100, 4),
        "average_return_pct": round(sum(returns) / len(returns), 4),
        "profit_factor": round(gross_profit / gross_loss, 4) if gross_loss else None,
    }


def _bootstrap(rows: list[dict]) -> dict:
    """Return deterministic percentile bootstrap intervals for ledger metrics."""
    if not rows:
        return {metric: None for metric in ("win_rate", "expectancy_r", "profit_factor", "average_r")}
    values = np.array([_number(row["r_multiple"]) for row in rows], dtype=float)
    generator = np.random.default_rng(RANDOM_SEED + len(rows))
    draws = generator.integers(0, len(values), size=(BOOTSTRAP_SAMPLES, len(values)))
    samples = values[draws]
    positive = np.where(samples > 0, samples, 0).sum(axis=1)
    negative = -np.where(samples < 0, samples, 0).sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        profit_factors = np.where(negative > 0, positive / negative, np.nan)

    def interval(sample: np.ndarray) -> list[float | None]:
        finite = sample[np.isfinite(sample)]
        if not len(finite):
            return None
        return [round(float(np.percentile(finite, 2.5)), 4), round(float(np.percentile(finite, 97.5)), 4)]

    wins = (samples > 0).mean(axis=1) * 100
    means = samples.mean(axis=1)
    return {
        "win_rate": interval(wins),
        "expectancy_r": interval(means),
        "profit_factor": interval(profit_factors),
        "average_r": interval(means),
    }


def _replay(row: dict, histories: dict[str, pd.DataFrame], benchmark: pd.DataFrame) -> dict:
    """Recalculate a ledger row solely from the raw history visible on its signal date."""
    data = histories[row["ticker"]]
    signal_date = pd.Timestamp(row["signal_date"])
    location = data.index.get_loc(signal_date)
    if not isinstance(location, (int, np.integer)) or location < WARMUP_BARS or location + 1 >= len(data):
        raise ValueError(f"Invalid signal position for {row['ticker']} {row['signal_date']}")
    history = data.iloc[: location + 1].copy()
    benchmark_history = benchmark.loc[: history.index[-1]].copy()
    analysis = calculate_institutional_analysis(history, benchmark_history)
    enriched = add_atr(history)
    atr = safe_float(enriched["ATR"].iloc[-1])
    levels = calculate_support_resistance(enriched)
    plan = calculate_trade_plan(
        row["ticker"], enriched, 10_000, 1,
        {"confidence": analysis["overall_score"]}, levels["support"], levels["resistance"], atr,
    )
    fill_open = float(data.iloc[location + 1]["Open"])
    entry = fill_open * (1 + SLIPPAGE_BPS / 10_000)
    outcome = _simulate(data, location + 1, entry, plan["stop_loss"], plan["target_1"], plan["target_2"])
    if outcome is None:
        raise ValueError(f"Unsimulatable trade for {row['ticker']} {row['signal_date']}")
    exit_index = location + outcome["holding_days"]
    return {
        "entry_index": int(location + 1),
        "exit_index": int(exit_index),
        "entry": entry,
        "next_open": fill_open,
        "stop_loss": plan["stop_loss"],
        "target_1": plan["target_1"],
        "target_2": plan["target_2"],
        "outcome": outcome,
    }


def _matches_ledger(row: dict, outcome: dict) -> bool:
    return all(
        abs(_number(row[field]) - float(outcome[field])) < 1e-9
        for field in ("exit_price", "return_pct", "r_multiple", "mfe_r", "mae_r")
    ) and all(str(row[field]).lower() == str(outcome[field]).lower() for field in ("tp1_hit", "tp2_hit", "stop_hit"))


def _random_matched_returns(rows: list[dict], histories: dict[str, pd.DataFrame]) -> list[float]:
    """Random controls matched by ticker, calendar month, and per-ticker count.

    Each sampled control uses the recorded trade's ticker and entry-month, then
    holds for its recorded number of sessions. It uses the same execution-cost
    formula as the calibration ledger.
    """
    generator = np.random.default_rng(RANDOM_SEED)
    returns = []
    for row in rows:
        data = histories[row["ticker"]]
        entry_date = pd.Timestamp(row["entry_date"])
        holding_days = int(float(row["holding_days"]))
        candidates = [
            index for index, timestamp in enumerate(data.index)
            if timestamp.year == entry_date.year and timestamp.month == entry_date.month
            and index + holding_days - 1 < len(data)
        ]
        if not candidates:
            continue
        index = int(generator.choice(candidates))
        entry = float(data.iloc[index]["Open"]) * (1 + SLIPPAGE_BPS / 10_000)
        exit_price = float(data.iloc[index + holding_days - 1]["Close"])
        cost = entry * (SLIPPAGE_BPS + TRANSACTION_COST_BPS) / 10_000
        cost += exit_price * (SLIPPAGE_BPS + TRANSACTION_COST_BPS) / 10_000
        returns.append((exit_price - entry - cost) / entry * 100)
    return returns


def _ema_crossover_returns(histories: dict[str, pd.DataFrame], rows: list[dict]) -> list[float]:
    start = min(pd.Timestamp(row["entry_date"]) for row in rows)
    end = max(pd.Timestamp(row["exit_date"]) for row in rows)
    returns: list[float] = []
    for ticker, data in histories.items():
        working = data.copy()
        working["EMA20"] = working["Close"].ewm(span=20, adjust=False).mean()
        working["EMA50"] = working["Close"].ewm(span=50, adjust=False).mean()
        active: int | None = None
        for index in range(1, len(working) - 1):
            timestamp = working.index[index]
            if timestamp < start or timestamp > end:
                continue
            crossed_up = working["EMA20"].iloc[index - 1] <= working["EMA50"].iloc[index - 1] and working["EMA20"].iloc[index] > working["EMA50"].iloc[index]
            crossed_down = working["EMA20"].iloc[index - 1] >= working["EMA50"].iloc[index - 1] and working["EMA20"].iloc[index] < working["EMA50"].iloc[index]
            if active is None and crossed_up:
                active = index + 1
            elif active is not None and (crossed_down or index - active + 1 >= MAX_HOLDING_DAYS):
                entry = float(working.iloc[active]["Open"]) * (1 + SLIPPAGE_BPS / 10_000)
                exit_price = float(working.iloc[index]["Close"])
                cost = entry * (SLIPPAGE_BPS + TRANSACTION_COST_BPS) / 10_000 + exit_price * (SLIPPAGE_BPS + TRANSACTION_COST_BPS) / 10_000
                returns.append((exit_price - entry - cost) / entry * 100)
                active = None
    return returns


def _buy_and_hold_returns(histories: dict[str, pd.DataFrame], rows: list[dict]) -> list[float]:
    start = min(pd.Timestamp(row["entry_date"]) for row in rows)
    end = max(pd.Timestamp(row["exit_date"]) for row in rows)
    returns = []
    for data in histories.values():
        period = data.loc[(data.index >= start) & (data.index <= end)]
        if len(period) < 2:
            continue
        entry = float(period.iloc[0]["Open"]) * (1 + SLIPPAGE_BPS / 10_000)
        exit_price = float(period.iloc[-1]["Close"])
        cost = entry * (SLIPPAGE_BPS + TRANSACTION_COST_BPS) / 10_000 + exit_price * (SLIPPAGE_BPS + TRANSACTION_COST_BPS) / 10_000
        returns.append((exit_price - entry - cost) / entry * 100)
    return returns


def run_integrity_audit() -> dict:
    rows = _trade_rows()
    split = int(len(rows) * 0.7)
    out_of_sample = rows[split:]
    tickers = sorted({row["ticker"] for row in rows})
    histories = {ticker: _load_history(ticker) for ticker in tickers}
    benchmark = _load_history("SPY")

    full_replay_failures = []
    full_exact_matches = 0
    for row in rows:
        try:
            replay = _replay(row, histories, benchmark)
            full_exact_matches += int(_matches_ledger(row, replay["outcome"]))
        except Exception as error:
            full_replay_failures.append({"ticker": row["ticker"], "signal_date": row["signal_date"], "reason": str(error)})

    checks = Counter()
    per_band = defaultdict(lambda: Counter())
    replay_failures = []
    intervals = defaultdict(list)
    plan_gap_counts = Counter()
    time_cap_exits = 0
    for row in out_of_sample:
        try:
            replay = _replay(row, histories, benchmark)
        except Exception as error:  # The audit must disclose any unreproducible record.
            replay_failures.append({"ticker": row["ticker"], "signal_date": row["signal_date"], "reason": str(error)})
            continue
        outcome = replay["outcome"]
        band = row["band"]
        checks["replayed_trades"] += 1
        checks["next_open_entries"] += int(abs(replay["entry"] - replay["next_open"] * (1 + SLIPPAGE_BPS / 10_000)) < 1e-9)
        checks["exact_ledger_matches"] += int(_matches_ledger(row, outcome))
        checks["tp1_hits"] += int(outcome["tp1_hit"])
        checks["tp2_hits"] += int(outcome["tp2_hit"])
        checks["tp1_positive_r"] += int(outcome["tp1_hit"] and outcome["r_multiple"] > 0)
        checks["tp1_non_positive_r"] += int(outcome["tp1_hit"] and outcome["r_multiple"] <= 0)
        checks["same_candle_stop_target_ambiguities"] += int(
            outcome["stop_hit"] and float(histories[row["ticker"]].iloc[replay["exit_index"]]["High"]) >= replay["target_1"]
        )
        checks["target_1_below_or_at_actual_entry"] += int(replay["target_1"] <= replay["entry"])
        checks["target_2_below_or_at_actual_entry"] += int(replay["target_2"] <= replay["entry"])
        checks["stops"] += int(outcome["stop_hit"])
        checks["target_2_exits"] += int(outcome["tp2_hit"] and not outcome["stop_hit"])
        if not outcome["stop_hit"] and not outcome["tp2_hit"]:
            time_cap_exits += 1
        per_band[band]["tp1_non_positive_r"] += int(outcome["tp1_hit"] and outcome["r_multiple"] <= 0)
        intervals[row["ticker"]].append((replay["entry_index"], replay["exit_index"]))

    overlap_count = 0
    for ticker, positions in intervals.items():
        positions.sort()
        overlap_count += sum(current[0] <= previous[1] for previous, current in zip(positions, positions[1:]))

    band_rows = {band: [row for row in out_of_sample if row["band"] == band] for band in BANDS}
    configured_round_trip_bps = 2 * (SLIPPAGE_BPS + TRANSACTION_COST_BPS)
    effective_round_trip_bps = configured_round_trip_bps + SLIPPAGE_BPS
    baselines = {
        "buy_and_hold_equal_weight": {
            **_summary(_buy_and_hold_returns(histories, out_of_sample)),
            "definition": "One equal-weight long position per ticker from the first out-of-sample entry date to the final out-of-sample exit date.",
        },
        "ema20_ema50_crossover": {
            **_summary(_ema_crossover_returns(histories, out_of_sample)),
            "definition": "Long on daily EMA20 crossing above EMA50; exit on a cross below or after 30 sessions. Uses the same cost formula.",
        },
        "random_matched": {
            **_summary(_random_matched_returns(out_of_sample, histories)),
            "definition": "Seeded random entries matched to each observed trade's ticker, calendar month, holding-time and total trade count; uses the same cost formula.",
        },
        "all_valid_setups": {
            **_summary([_number(row["return_pct"]) for row in out_of_sample]),
            "average_r": round(sum(_number(row["r_multiple"]) for row in out_of_sample) / len(out_of_sample), 4),
            "definition": "Every valid plan generated in the out-of-sample ledger, with no confidence filter (all score bands).",
        },
    }
    return {
        "audit_status": "completed",
        "source": {
            "trade_ledger": "artifacts/ai_calibration_trades.csv",
            "ohlcv_cache": "artifacts/calibration_dataset/*.csv",
            "scope": "out-of-sample chronological 30% of the recorded ledger",
            "out_of_sample_trades": len(out_of_sample),
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "random_seed": RANDOM_SEED,
        },
        "execution_verification": {
            "ledger_replay": {"replayed": len(rows), "exact_matches": full_exact_matches, "failures": full_replay_failures},
            "out_of_sample_replay": {"replayed": checks["replayed_trades"], "exact_matches": checks["exact_ledger_matches"], "failures": replay_failures},
            "entry": {"next_candle_open_with_slippage": checks["next_open_entries"], "total": checks["replayed_trades"]},
            "stop_and_target": {
                "stop_first_same_candle_ambiguities": checks["same_candle_stop_target_ambiguities"],
                "stop_exits": checks["stops"],
                "target_2_exits": checks["target_2_exits"],
                "time_cap_mark_to_market_exits": time_cap_exits,
            },
            "partial_exit_accounting": {
                "tp1_hits": checks["tp1_hits"],
                "tp2_hits": checks["tp2_hits"],
                "partial_exits_recorded": 0,
                "remaining_position_tracking": False,
                "tp1_hits_with_non_positive_final_r": checks["tp1_non_positive_r"],
                "tp1_hits_with_positive_final_r": checks["tp1_positive_r"],
            },
            "plan_gap_consistency": {
                "target_1_at_or_below_actual_next_open": checks["target_1_below_or_at_actual_entry"],
                "target_2_at_or_below_actual_next_open": checks["target_2_below_or_at_actual_entry"],
                "note": "Targets are built from the prior-close plan entry but R is measured from the next-open fill.",
            },
            "costs": {
                "configured_slippage_bps_per_side": SLIPPAGE_BPS,
                "configured_transaction_cost_bps_per_side": TRANSACTION_COST_BPS,
                "cost_formula_bps_excluding_entry_fill_slippage": configured_round_trip_bps,
                "approximate_effective_round_trip_bps_including_entry_fill_slippage": effective_round_trip_bps,
            },
            "r_multiple": "(exit_price - next_open_fill - cost) / (next_open_fill - planned_stop_loss); no TP1 partial realization is included.",
            "win_loss": "A trade is a win only when its final recorded R multiple is greater than zero.",
            "drawdown": "The calibration artifact sums R multiples after sorting all ticker signals by date. It is not a capital-weighted portfolio equity curve and concurrent ticker trades remain interleaved.",
            "duplicate_or_overlapping_same_ticker_positions": overlap_count,
            "incomplete_positions": 0,
        },
        "confidence_bands": {
            band: {
                "trades": len(band_rows[band]),
                "bootstrap_95_ci": _bootstrap(band_rows[band]),
                "tp1_hits_with_non_positive_final_r": per_band[band]["tp1_non_positive_r"],
            }
            for band in BANDS
        },
        "baselines": baselines,
    }


def write_artifact(results: dict) -> None:
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "backtest_integrity_results.json").write_text(json.dumps(results, indent=2) + "\n")


if __name__ == "__main__":
    write_artifact(run_integrity_audit())
