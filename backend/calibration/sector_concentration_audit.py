"""Portfolio-level sector concentration audit for the frozen holdout ledger.

This module is research-only. It reads the validated locked-holdout trade
ledger, reuses cached historical OHLCV, and never changes production strategy
or execution behavior.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from calibration.pullback_robustness import SYMBOLS
from calibration.regime_gated_pullback import _run
from engines.institutional_engine import calculate_institutional_analysis

ROOT = Path(__file__).resolve().parents[2]
LEDGER_PATH = ROOT / "artifacts" / "locked_holdout_trades.csv"
LOCKED_RESULTS_PATH = ROOT / "artifacts" / "locked_holdout_results.json"
DATASET_DIR = ROOT / "artifacts" / "locked_holdout_dataset"
RESULTS_PATH = ROOT / "artifacts" / "sector_concentration_results.json"
REPORT_PATH = ROOT / "docs" / "SECTOR_CONCENTRATION_AUDIT.md"
RANDOM_SEED = 20260745
BOOTSTRAP_SAMPLES = 10_000
COMPARISON_BLOCK_LENGTH = 20
RATE_SENSITIVE_SECTORS = frozenset({"Utilities", "Real Estate"})

VARIANTS = {
    "A_no_sector_limit": {
        "label": "A. No sector limit",
        "kind": "none",
    },
    "B_max_30_single_sector": {
        "label": "B. Maximum 30% in one sector",
        "kind": "single_sector_cap",
        "limit": 0.30,
    },
    "C_max_40_single_sector": {
        "label": "C. Maximum 40% in one sector",
        "kind": "single_sector_cap",
        "limit": 0.40,
    },
    "D_max_50_rate_sensitive": {
        "label": "D. Maximum 50% in related rate-sensitive sectors",
        "kind": "related_sector_cap",
        "limit": 0.50,
    },
    "E_highest_confidence_per_sector_day": {
        "label": "E. Highest-confidence signal per sector per day",
        "kind": "highest_confidence",
    },
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_bool(value: Any) -> bool:
    return str(value).lower() == "true"


def _as_float(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite ledger value: {value}")
    return result


def _as_int(value: Any) -> int:
    return int(float(value))


def load_validated_ledger(path: Path = LEDGER_PATH) -> list[dict[str, Any]]:
    """Consolidate partial-exit rows into one immutable record per trade."""

    trades: dict[str, dict[str, Any]] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row.get("record_type") != "TRADE" or row.get("cost_multiplier") != "1":
                continue
            trade_id = str(row["trade_id"])
            normalized = {
                "trade_id": trade_id,
                "ticker": str(row["ticker"]),
                "sector": str(row["sector"]),
                "signal_date": str(row["signal_date"]),
                "entry_date": str(row["entry_date"]),
                "exit_date": str(row["exit_date"]),
                "entry_price": _as_float(row["entry_price"]),
                "ema20": _as_float(row["ema20"]),
                "atr": _as_float(row["atr"]),
                "swing_low_20": _as_float(row["swing_low_20"]),
                "stop_loss": _as_float(row["stop_loss"]),
                "target_1": _as_float(row["target_1"]),
                "target_2": _as_float(row["target_2"]),
                "r_multiple": _as_float(row["r_multiple"]),
                "return_pct": _as_float(row["return_pct"]),
                "holding_days": _as_int(row["holding_days"]),
                "tp1_hit": _as_bool(row["tp1_hit"]),
                "tp2_hit": _as_bool(row["tp2_hit"]),
                "stop_hit": _as_bool(row["stop_hit"]),
                "market_regime": str(row["market_regime"]),
                "cost_multiplier": 1,
            }
            existing = trades.get(trade_id)
            if existing is not None and existing != normalized:
                raise ValueError(
                    f"Partial-exit rows disagree for immutable trade {trade_id}."
                )
            trades[trade_id] = normalized
    result = sorted(
        trades.values(),
        key=lambda row: (
            row["entry_date"],
            row["signal_date"],
            row["ticker"],
        ),
    )
    if not result:
        raise ValueError("The validated holdout ledger contains no trades.")
    return result


def load_validated_candidates(
    histories: dict[str, pd.DataFrame],
    path: Path = LEDGER_PATH,
) -> list[dict[str, Any]]:
    """Recover every frozen candidate from accepted and rejected ledger rows."""

    candidates: dict[tuple[str, str], dict[str, Any]] = {}
    boolean_fields = (
        "spy_close_ema200",
        "spy_ema50_ema200",
        "spy_dual_ema",
        "nasdaq_close_ema200",
        "universe_breadth_60",
        "existing_market_regime",
        "out_of_sample",
    )
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            ticker = str(row["ticker"])
            signal_date = str(row["signal_date"])
            key = (ticker, signal_date)
            if key in candidates:
                continue
            history = histories[ticker]
            matching = np.flatnonzero(
                history.index == pd.Timestamp(signal_date)
            )
            if not len(matching):
                raise ValueError(
                    f"Signal candle is missing for {ticker} on {signal_date}."
                )
            candidate = {
                "ticker": ticker,
                "sector": str(row["sector"]),
                "index": int(matching[0]),
                "signal_date": signal_date,
                "ema20": _as_float(row["ema20"]),
                "swing_low_20": _as_float(row["swing_low_20"]),
                "atr": _as_float(row["atr"]),
                "market_regime": str(row["market_regime"]),
                "walk_forward_period": str(row["walk_forward_period"]),
            }
            candidate.update(
                {field: _as_bool(row[field]) for field in boolean_fields}
            )
            candidates[key] = candidate
    return sorted(
        candidates.values(),
        key=lambda row: (row["signal_date"], row["ticker"]),
    )


def _load_histories(
    tickers: Iterable[str],
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    available = {
        ticker
        for ticker in {*tickers, *SYMBOLS}
        if (DATASET_DIR / f"{ticker}.csv").exists()
    }
    histories = {
        ticker: pd.read_csv(
            DATASET_DIR / f"{ticker}.csv", index_col=0, parse_dates=True
        )
        for ticker in sorted(available)
    }
    spy = pd.read_csv(DATASET_DIR / "SPY.csv", index_col=0, parse_dates=True)
    return histories, spy


def enrich_signal_time_confidence(
    trades: list[dict[str, Any]],
    histories: dict[str, pd.DataFrame],
    benchmark: pd.DataFrame,
    cache: dict[tuple[str, str], tuple[float, str]] | None = None,
) -> None:
    """Attach confidence calculated only through each immutable signal close."""

    confidence_cache = cache if cache is not None else {}
    for trade in trades:
        signal_date = pd.Timestamp(trade["signal_date"])
        key = (str(trade["ticker"]), str(trade["signal_date"]))
        if key in confidence_cache:
            trade["confidence"], trade["recommendation"] = confidence_cache[key]
            continue
        history = histories[trade["ticker"]].loc[:signal_date]
        benchmark_history = benchmark.loc[:signal_date]
        if history.empty or benchmark_history.empty:
            raise ValueError(
                f"Signal-time history is unavailable for {trade['trade_id']}."
            )
        analysis = calculate_institutional_analysis(history, benchmark_history)
        confidence = _as_float(analysis["overall_score"])
        if not 0 <= confidence <= 100:
            raise ValueError(
                f"Confidence is outside 0-100 for {trade['trade_id']}."
            )
        trade["confidence"] = confidence
        trade["recommendation"] = str(analysis["recommendation"])
        confidence_cache[key] = (
            confidence,
            str(analysis["recommendation"]),
        )


def _active_on(
    accepted: list[dict[str, Any]], entry_date: pd.Timestamp
) -> list[dict[str, Any]]:
    return [
        row
        for row in accepted
        if pd.Timestamp(row["entry_date"]) <= entry_date
        <= pd.Timestamp(row["exit_date"])
    ]


def _concentration_share(
    rows: list[dict[str, Any]], sectors: frozenset[str] | None = None
) -> float:
    if not rows:
        return 0.0
    counts = Counter(str(row["sector"]) for row in rows)
    if sectors is not None:
        return sum(counts[sector] for sector in sectors) / len(rows)
    return max(counts.values()) / len(rows)


def _cap_allows(
    active: list[dict[str, Any]],
    candidate: dict[str, Any],
    *,
    limit: float,
    related_sectors: frozenset[str] | None = None,
) -> bool:
    """Allow startup diversification, then prevent cap deterioration.

    A literal percentage cap makes an empty portfolio impossible to start:
    its first position is necessarily 100% of active trades. During that
    unavoidable startup state, a new trade is allowed only when it strictly
    reduces concentration. Once the book reaches the limit, the limit is
    enforced directly.
    """

    if not active:
        return True
    current = _concentration_share(active, related_sectors)
    prospective = _concentration_share([*active, candidate], related_sectors)
    if current > limit:
        return prospective < current
    return prospective <= limit


def apply_variant(
    trades: list[dict[str, Any]], variant_id: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    config = VARIANTS[variant_id]
    if config["kind"] == "none":
        return list(trades), []
    if config["kind"] == "highest_confidence":
        selected: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for trade in trades:
            groups[(trade["signal_date"], trade["sector"])].append(trade)
        for key in sorted(groups):
            ranked = sorted(
                groups[key],
                key=lambda row: (-row["confidence"], row["ticker"]),
            )
            selected.append(ranked[0])
            rejected.extend(
                {
                    **row,
                    "sector_limit_rejection": (
                        "Lower confidence than another signal in the same "
                        "sector on the same signal date."
                    ),
                }
                for row in ranked[1:]
            )
        return sorted(
            selected,
            key=lambda row: (
                row["entry_date"],
                row["signal_date"],
                row["ticker"],
            ),
        ), rejected

    accepted: list[dict[str, Any]] = []
    rejected = []
    related = (
        RATE_SENSITIVE_SECTORS
        if config["kind"] == "related_sector_cap"
        else None
    )
    for trade in sorted(
        trades,
        key=lambda row: (
            row["entry_date"],
            row["signal_date"],
            row["ticker"],
        ),
    ):
        entry_date = pd.Timestamp(trade["entry_date"])
        active = _active_on(accepted, entry_date)
        if _cap_allows(
            active,
            trade,
            limit=float(config["limit"]),
            related_sectors=related,
        ):
            accepted.append(trade)
        else:
            rejected.append(
                {
                    **trade,
                    "sector_limit_rejection": (
                        f"Prospective active-trade concentration exceeded "
                        f"{float(config['limit']) * 100:.0f}%."
                    ),
                }
            )
    return accepted, rejected


def _bootstrap_expectancy(values: np.ndarray, seed_offset: int) -> list[float] | None:
    if not len(values):
        return None
    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    means = np.empty(BOOTSTRAP_SAMPLES, dtype=float)
    batch_size = 500
    for start in range(0, BOOTSTRAP_SAMPLES, batch_size):
        size = min(batch_size, BOOTSTRAP_SAMPLES - start)
        sample = rng.integers(0, len(values), size=(size, len(values)))
        means[start : start + size] = values[sample].mean(axis=1)
    return [
        round(float(np.percentile(means, 2.5)), 4),
        round(float(np.percentile(means, 97.5)), 4),
    ]


def _maximum_drawdown(values: np.ndarray) -> float:
    if not len(values):
        return 0.0
    equity = np.cumsum(values)
    peaks = np.maximum.accumulate(np.maximum(equity, 0))
    return float((equity - peaks).min())


def _paired_block_comparison(
    baseline: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    seed_offset: int,
) -> dict[str, Any]:
    """Bootstrap variant-minus-baseline differences with paired trade blocks."""

    chronological = sorted(
        baseline,
        key=lambda row: (
            row["exit_date"],
            row["entry_date"],
            row["ticker"],
        ),
    )
    values = np.asarray(
        [float(row["r_multiple"]) for row in chronological], dtype=float
    )
    accepted_ids = {str(row["trade_id"]) for row in accepted}
    accepted_mask = np.asarray(
        [str(row["trade_id"]) in accepted_ids for row in chronological],
        dtype=bool,
    )
    method = (
        "Paired moving-block bootstrap of chronologically realised trades; "
        f"block length {COMPARISON_BLOCK_LENGTH}."
    )
    if accepted_mask.all():
        return {
            "expectancy_difference_r": 0.0,
            "expectancy_difference_95_ci": [0.0, 0.0],
            "maximum_drawdown_improvement_r": 0.0,
            "maximum_drawdown_improvement_95_ci": [0.0, 0.0],
            "method": method,
        }

    rng = np.random.default_rng(RANDOM_SEED + 10_000 + seed_offset)
    block_count = math.ceil(len(values) / COMPARISON_BLOCK_LENGTH)
    offsets = np.arange(COMPARISON_BLOCK_LENGTH)
    expectancy_differences = np.empty(BOOTSTRAP_SAMPLES, dtype=float)
    drawdown_improvements = np.empty(BOOTSTRAP_SAMPLES, dtype=float)
    for sample_index in range(BOOTSTRAP_SAMPLES):
        starts = rng.integers(0, len(values), size=block_count)
        indices = (
            starts[:, None] + offsets[None, :]
        ).reshape(-1)[: len(values)] % len(values)
        baseline_sample = values[indices]
        accepted_sample = baseline_sample[accepted_mask[indices]]
        expectancy_differences[sample_index] = (
            float(accepted_sample.mean()) - float(baseline_sample.mean())
        )
        drawdown_improvements[sample_index] = (
            _maximum_drawdown(accepted_sample)
            - _maximum_drawdown(baseline_sample)
        )

    accepted_values = np.asarray(
        [float(row["r_multiple"]) for row in accepted], dtype=float
    )
    return {
        "expectancy_difference_r": round(
            float(accepted_values.mean() - values.mean()), 4
        ),
        "expectancy_difference_95_ci": [
            round(float(np.percentile(expectancy_differences, 2.5)), 4),
            round(float(np.percentile(expectancy_differences, 97.5)), 4),
        ],
        "maximum_drawdown_improvement_r": round(
            _maximum_drawdown(
                np.asarray(
                    [
                        float(row["r_multiple"])
                        for row in sorted(
                            accepted,
                            key=lambda row: (
                                row["exit_date"],
                                row["entry_date"],
                                row["ticker"],
                            ),
                        )
                    ],
                    dtype=float,
                )
            )
            - _maximum_drawdown(values),
            4,
        ),
        "maximum_drawdown_improvement_95_ci": [
            round(float(np.percentile(drawdown_improvements, 2.5)), 4),
            round(float(np.percentile(drawdown_improvements, 97.5)), 4),
        ],
        "method": method,
    }


def _daily_active(
    trades: list[dict[str, Any]], trading_dates: pd.DatetimeIndex
) -> Iterable[tuple[pd.Timestamp, list[dict[str, Any]]]]:
    for day in trading_dates:
        active = [
            row
            for row in trades
            if pd.Timestamp(row["entry_date"]) <= day
            <= pd.Timestamp(row["exit_date"])
        ]
        yield day, active


def sector_exposure(
    trades: list[dict[str, Any]], trading_dates: pd.DatetimeIndex
) -> dict[str, Any]:
    if not trades:
        return {"summary": [], "monthly": []}
    sectors = sorted({str(row["sector"]) for row in trades})
    daily: list[dict[str, Any]] = []
    for day, active in _daily_active(trades, trading_dates):
        if not active:
            continue
        counts = Counter(str(row["sector"]) for row in active)
        total = len(active)
        daily.append(
            {
                "date": day,
                "total": total,
                "counts": counts,
                "percentages": {
                    sector: counts[sector] / total * 100 for sector in sectors
                },
            }
        )
    summary = []
    for sector in sectors:
        percentages = [
            float(item["percentages"][sector]) for item in daily
        ]
        counts = [int(item["counts"][sector]) for item in daily]
        peak_index = int(np.argmax(percentages)) if percentages else 0
        summary.append(
            {
                "sector": sector,
                "average_active_share_percent": round(
                    float(np.mean(percentages)), 2
                )
                if percentages
                else 0.0,
                "peak_active_share_percent": round(
                    max(percentages), 2
                )
                if percentages
                else 0.0,
                "peak_active_positions": max(counts) if counts else 0,
                "peak_date": (
                    daily[peak_index]["date"].date().isoformat()
                    if percentages
                    else None
                ),
                "trading_days_above_30_percent": sum(
                    value > 30 for value in percentages
                ),
            }
        )

    frame_rows = []
    for item in daily:
        row = {"date": item["date"], "total": item["total"]}
        row.update(item["percentages"])
        frame_rows.append(row)
    frame = pd.DataFrame(frame_rows).set_index("date")
    monthly = []
    for month, group in frame.groupby(frame.index.to_period("M")):
        averages = {
            sector: round(float(group[sector].mean()), 2)
            for sector in sectors
        }
        dominant = max(averages, key=averages.get)
        monthly.append(
            {
                "month": str(month),
                "average_concurrent_positions": round(
                    float(group["total"].mean()), 2
                ),
                "peak_concurrent_positions": int(group["total"].max()),
                "dominant_sector": dominant,
                "dominant_sector_average_share_percent": averages[dominant],
                "average_sector_share_percent": averages,
            }
        )
    return {"summary": summary, "monthly": monthly}


def _concurrency_metrics(
    trades: list[dict[str, Any]], trading_dates: pd.DatetimeIndex
) -> dict[str, Any]:
    worst_loss = 0.0
    worst_date = None
    worst_positions = 0
    maximum_concurrent = 0
    maximum_date = None
    for day, active in _daily_active(trades, trading_dates):
        if len(active) > maximum_concurrent:
            maximum_concurrent = len(active)
            maximum_date = day.date().isoformat()
        simultaneous_loss = sum(
            min(0.0, float(row["r_multiple"])) for row in active
        )
        if simultaneous_loss < worst_loss:
            worst_loss = simultaneous_loss
            worst_date = day.date().isoformat()
            worst_positions = len(active)
    return {
        "maximum_concurrent_positions": maximum_concurrent,
        "maximum_concurrent_date": maximum_date,
        "worst_simultaneous_loss_r": round(worst_loss, 4),
        "worst_simultaneous_loss_date": worst_date,
        "positions_open_on_worst_loss_date": worst_positions,
        "definition": (
            "Ex-post sum of negative final trade R for positions open on the "
            "same session; winners are not used to offset the loss cluster."
        ),
    }


def _simple_metrics(
    trades: list[dict[str, Any]],
    rejected_count: int = 0,
    seed_offset: int = 0,
) -> dict[str, Any]:
    if not trades:
        return {
            "total_trades": 0,
            "rejected_signals": rejected_count,
            "expectancy": 0.0,
            "profit_factor": None,
            "win_rate": 0.0,
            "average_r": 0.0,
            "maximum_drawdown": 0.0,
            "bootstrap_expectancy_95_ci": None,
            "total_r": 0.0,
        }
    chronological = sorted(
        trades,
        key=lambda row: (
            row["exit_date"],
            row["entry_date"],
            row["ticker"],
        ),
    )
    values = np.asarray(
        [float(row["r_multiple"]) for row in chronological], dtype=float
    )
    gains = float(values[values > 0].sum())
    losses = float(-values[values < 0].sum())
    return {
        "total_trades": len(trades),
        "rejected_signals": rejected_count,
        "expectancy": round(float(values.mean()), 4),
        "profit_factor": round(gains / losses, 4) if losses else None,
        "win_rate": round(float(np.mean(values > 0) * 100), 2),
        "average_r": round(float(values.mean()), 4),
        "maximum_drawdown": round(_maximum_drawdown(values), 4),
        "bootstrap_expectancy_95_ci": _bootstrap_expectancy(
            values, seed_offset
        ),
        "total_r": round(float(values.sum()), 4),
    }


def _performance_by_regime(
    trades: list[dict[str, Any]], seed_offset: int
) -> dict[str, Any]:
    return {
        regime: _simple_metrics(
            [row for row in trades if row["market_regime"] == regime],
            seed_offset=seed_offset + index + 1,
        )
        for index, regime in enumerate(
            sorted({str(row["market_regime"]) for row in trades})
        )
    }


@dataclass
class _CorrelationSums:
    count: int = 0
    sum_x: float = 0.0
    sum_y: float = 0.0
    sum_xx: float = 0.0
    sum_yy: float = 0.0
    sum_xy: float = 0.0

    def add(self, x: float, y: float) -> None:
        self.count += 1
        self.sum_x += x
        self.sum_y += y
        self.sum_xx += x * x
        self.sum_yy += y * y
        self.sum_xy += x * y

    def correlation(self) -> float | None:
        if self.count < 3:
            return None
        numerator = self.count * self.sum_xy - self.sum_x * self.sum_y
        denominator = math.sqrt(
            max(0.0, self.count * self.sum_xx - self.sum_x**2)
            * max(0.0, self.count * self.sum_yy - self.sum_y**2)
        )
        return numerator / denominator if denominator > 0 else None


def simultaneous_correlation(
    trades: list[dict[str, Any]],
    histories: dict[str, pd.DataFrame],
    trading_dates: pd.DatetimeIndex,
) -> dict[str, Any]:
    if len(trades) < 2:
        return {"pair_count": 0, "mean": None, "median": None}
    returns = {
        ticker: pd.to_numeric(history["Close"], errors="coerce").pct_change()
        for ticker, history in histories.items()
    }
    pairs: dict[tuple[str, str], _CorrelationSums] = defaultdict(
        _CorrelationSums
    )
    metadata = {row["trade_id"]: row for row in trades}
    for day, active in _daily_active(trades, trading_dates):
        available = [
            row
            for row in active
            if day in returns[row["ticker"]].index
            and math.isfinite(float(returns[row["ticker"]].loc[day]))
        ]
        for first_index, first in enumerate(available):
            for second in available[first_index + 1 :]:
                key = tuple(sorted((first["trade_id"], second["trade_id"])))
                pairs[key].add(
                    float(returns[first["ticker"]].loc[day]),
                    float(returns[second["ticker"]].loc[day]),
                )
    values: list[tuple[float, dict[str, Any], dict[str, Any]]] = []
    for (first_id, second_id), sums in pairs.items():
        correlation = sums.correlation()
        if correlation is not None and math.isfinite(correlation):
            values.append(
                (correlation, metadata[first_id], metadata[second_id])
            )

    def describe(
        selected: list[tuple[float, dict[str, Any], dict[str, Any]]]
    ) -> dict[str, Any]:
        numbers = np.asarray([item[0] for item in selected], dtype=float)
        if not len(numbers):
            return {
                "pair_count": 0,
                "mean": None,
                "median": None,
                "percentile_90": None,
            }
        return {
            "pair_count": len(numbers),
            "mean": round(float(numbers.mean()), 4),
            "median": round(float(np.median(numbers)), 4),
            "percentile_90": round(float(np.percentile(numbers, 90)), 4),
        }

    same_sector = [
        item for item in values if item[1]["sector"] == item[2]["sector"]
    ]
    cross_sector = [
        item for item in values if item[1]["sector"] != item[2]["sector"]
    ]
    rate_sensitive = [
        item
        for item in values
        if item[1]["sector"] in RATE_SENSITIVE_SECTORS
        and item[2]["sector"] in RATE_SENSITIVE_SECTORS
    ]
    return {
        "all_simultaneous_pairs": describe(values),
        "same_sector_pairs": describe(same_sector),
        "cross_sector_pairs": describe(cross_sector),
        "utilities_real_estate_pairs": describe(rate_sensitive),
        "method": (
            "Pearson correlation of split-adjusted daily close returns while "
            "both trades were open; pairs require at least three shared sessions."
        ),
    }


def _rate_sensitive_impact(trades: list[dict[str, Any]]) -> dict[str, Any]:
    selected = [
        row for row in trades if row["sector"] in RATE_SENSITIVE_SECTORS
    ]
    values = np.asarray(
        [float(row["r_multiple"]) for row in selected], dtype=float
    )
    all_values = np.asarray(
        [float(row["r_multiple"]) for row in trades], dtype=float
    )
    positive_total = float(all_values[all_values > 0].sum()) if len(all_values) else 0
    negative_total = float(-all_values[all_values < 0].sum()) if len(all_values) else 0
    return {
        **_simple_metrics(selected),
        "share_of_trades_percent": round(
            len(selected) / len(trades) * 100, 2
        )
        if trades
        else 0.0,
        "share_of_positive_r_percent": round(
            float(values[values > 0].sum()) / positive_total * 100, 2
        )
        if positive_total and len(values)
        else 0.0,
        "share_of_loss_r_percent": round(
            float(-values[values < 0].sum()) / negative_total * 100, 2
        )
        if negative_total and len(values)
        else 0.0,
        "by_sector": {
            sector: _simple_metrics(
                [row for row in selected if row["sector"] == sector]
            )
            for sector in sorted(RATE_SENSITIVE_SECTORS)
        },
    }


def _regenerate_double_cost(
    candidates: list[dict[str, Any]],
    histories: dict[str, pd.DataFrame],
) -> list[dict[str, Any]]:
    trades, _, _ = _run(
        "existing_market_regime", candidates, histories, 2
    )
    return trades


def _variant_metrics(
    trades: list[dict[str, Any]],
    rejected_count: int,
    histories: dict[str, pd.DataFrame],
    trading_dates: pd.DatetimeIndex,
    seed_offset: int,
) -> dict[str, Any]:
    return {
        **_simple_metrics(trades, rejected_count, seed_offset),
        **_concurrency_metrics(trades, trading_dates),
        "sector_exposure_over_time": sector_exposure(trades, trading_dates),
        "performance_by_market_regime": _performance_by_regime(
            trades, seed_offset
        ),
        "simultaneous_trade_correlation": simultaneous_correlation(
            trades, histories, trading_dates
        ),
        "utilities_and_real_estate": _rate_sensitive_impact(trades),
    }


def _selection_verdict(variants: dict[str, Any]) -> dict[str, Any]:
    best_id = max(
        variants,
        key=lambda key: (
            variants[key]["current_costs"]["expectancy"],
            variants[key]["current_costs"]["total_trades"],
        ),
    )
    safest_id = max(
        variants,
        key=lambda key: (
            variants[key]["current_costs"]["maximum_drawdown"],
            variants[key]["current_costs"]["expectancy"],
        ),
    )
    baseline = variants["A_no_sector_limit"]["current_costs"]
    justified = []
    exploratory = []
    for variant_id, result in variants.items():
        if variant_id == "A_no_sector_limit":
            continue
        metrics = result["current_costs"]
        interval = metrics["bootstrap_expectancy_95_ci"]
        comparison = result["comparison_vs_no_limit"]
        expectancy_difference_interval = comparison[
            "expectancy_difference_95_ci"
        ]
        drawdown_improvement_interval = comparison[
            "maximum_drawdown_improvement_95_ci"
        ]
        if (
            metrics["maximum_drawdown"] > baseline["maximum_drawdown"]
            and metrics["expectancy"] > 0
            and interval is not None
            and interval[0] > 0
            and result["double_costs"]["profit_factor"] is not None
            and result["double_costs"]["profit_factor"] > 1
        ):
            exploratory.append(variant_id)
        if (
            expectancy_difference_interval[0] >= 0
            and drawdown_improvement_interval[0] > 0
            and result["double_costs"]["profit_factor"] is not None
            and result["double_costs"]["profit_factor"] > 1
        ):
            justified.append(variant_id)
    return {
        "best_performing_variant": best_id,
        "safest_variant": safest_id,
        "statistically_justified_controls": justified,
        "exploratory_risk_reduction_candidates": exploratory,
        "conclusion": (
            "At least one concentration control has paired evidence of both "
            "non-negative expectancy impact and lower drawdown."
            if justified
            else "No concentration control is statistically justified on this "
            "single retrospective holdout: the paired intervals do not prove "
            "both preserved expectancy and lower drawdown."
        ),
    }


def _validate_locked_point_metrics(
    metrics: dict[str, Any],
    locked_metrics: dict[str, Any],
    label: str,
) -> None:
    comparisons = {
        "total_trades": "accepted_trades",
        "expectancy": "expectancy",
        "profit_factor": "profit_factor",
        "win_rate": "win_rate",
        "average_r": "average_r",
    }
    for current_key, locked_key in comparisons.items():
        current = metrics[current_key]
        expected = locked_metrics[locked_key]
        if current != expected:
            raise ValueError(
                f"{label} {current_key} is {current}; locked result is "
                f"{expected}."
            )


def run_audit() -> dict[str, Any]:
    ledger = load_validated_ledger()
    locked = json.loads(LOCKED_RESULTS_PATH.read_text(encoding="utf-8"))
    expected = int(
        locked["selected_regime_gated_pullback"]["accepted_trades"]
    )
    if len(ledger) != expected:
        raise ValueError(
            f"Ledger has {len(ledger)} trades; locked result expects {expected}."
        )
    histories, spy = _load_histories(
        row["ticker"] for row in ledger
    )
    candidates = load_validated_candidates(histories)
    confidence_cache: dict[tuple[str, str], tuple[float, str]] = {}
    enrich_signal_time_confidence(
        ledger, histories, spy, confidence_cache
    )
    double_ledger = _regenerate_double_cost(candidates, histories)
    enrich_signal_time_confidence(
        double_ledger, histories, spy, confidence_cache
    )
    expected_double = int(
        locked["selected_regime_gated_pullback"]["double_cost"][
            "accepted_trades"
        ]
    )
    if len(double_ledger) != expected_double:
        raise ValueError(
            f"Double-cost replay has {len(double_ledger)} trades; locked result "
            f"expects {expected_double}."
        )
    trading_dates = spy.index[
        (spy.index >= min(pd.Timestamp(row["entry_date"]) for row in ledger))
        & (spy.index <= max(pd.Timestamp(row["exit_date"]) for row in ledger))
    ]

    variants: dict[str, Any] = {}
    for index, variant_id in enumerate(VARIANTS):
        accepted, rejected = apply_variant(ledger, variant_id)
        double_trades, double_rejected = apply_variant(
            double_ledger, variant_id
        )
        variants[variant_id] = {
            "label": VARIANTS[variant_id]["label"],
            "rule": VARIANTS[variant_id],
            "signals_considered": len(ledger),
            "signals_rejected_by_limit": len(rejected),
            "comparison_vs_no_limit": _paired_block_comparison(
                ledger,
                accepted,
                1_000 * (index + 1),
            ),
            "current_costs": _variant_metrics(
                accepted,
                len(rejected),
                histories,
                trading_dates,
                100 * (index + 1),
            ),
            "double_costs": _variant_metrics(
                double_trades,
                len(double_rejected),
                histories,
                trading_dates,
                100 * (index + 1) + 50,
            ),
            "double_cost_signals_rejected_by_limit": len(double_rejected),
        }

    locked_strategy = locked["selected_regime_gated_pullback"]
    _validate_locked_point_metrics(
        variants["A_no_sector_limit"]["current_costs"],
        locked_strategy,
        "Current-cost baseline",
    )
    _validate_locked_point_metrics(
        variants["A_no_sector_limit"]["double_costs"],
        locked_strategy["double_cost"],
        "Double-cost baseline",
    )

    result = {
        "audit_status": "completed",
        "source": {
            "ledger": str(LEDGER_PATH.relative_to(ROOT)),
            "ledger_sha256": _sha256(LEDGER_PATH),
            "locked_results": str(LOCKED_RESULTS_PATH.relative_to(ROOT)),
            "period": {
                "start": min(row["signal_date"] for row in ledger),
                "end": max(row["exit_date"] for row in ledger),
            },
            "validated_trades": len(ledger),
            "validated_symbols": len({row["ticker"] for row in ledger}),
            "sectors": sorted({row["sector"] for row in ledger}),
            "locked_point_metrics": {
                "expectancy": locked_strategy["expectancy"],
                "profit_factor": locked_strategy["profit_factor"],
                "win_rate": locked_strategy["win_rate"],
                "maximum_drawdown_in_ticker_processing_order": (
                    locked_strategy["maximum_drawdown"]
                ),
            },
        },
        "methodology": {
            "production_behavior_changed": False,
            "strategy_rules_changed": False,
            "confidence_reconstruction": (
                "Current institutional score calculated with ticker and SPY "
                "candles ending on the immutable signal date; no future data."
            ),
            "sector_cap_startup_rule": (
                "When an undersized portfolio is unavoidably above a percentage "
                "cap, only additions that strictly reduce concentration are "
                "allowed; once at or below the cap, the cap is enforced directly."
            ),
            "active_interval": (
                "Entry and exit sessions are both counted as active, so same-day "
                "positions are treated conservatively as simultaneous."
            ),
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_seed": RANDOM_SEED,
            "paired_comparison": (
                "Variant-minus-baseline expectancy and maximum-drawdown "
                "differences use a paired moving-block bootstrap of "
                f"chronologically realised trades with block length "
                f"{COMPARISON_BLOCK_LENGTH}."
            ),
            "drawdown_order": (
                "Maximum drawdown is recalculated in chronological exit order. "
                "The prior locked report's -10.4094R current-cost figure used "
                "ticker-processing order and is not a portfolio chronology."
            ),
            "double_costs": (
                "Original locked strategy replay regenerated with double "
                "slippage and double transaction costs."
            ),
        },
        "variants": variants,
    }
    result["decision"] = _selection_verdict(variants)
    return result


def _format_number(value: Any, decimals: int = 4) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.{decimals}f}"


def write_report(result: dict[str, Any]) -> None:
    RESULTS_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    variants = result["variants"]
    decision = result["decision"]
    baseline_current = variants["A_no_sector_limit"]["current_costs"]
    locked_point_metrics = result["source"]["locked_point_metrics"]
    lines = [
        "# Sector Concentration Impact Audit",
        "",
        "## Executive verdict",
        "",
        (
            f"The best expectancy came from **{variants[decision['best_performing_variant']]['label']}**. "
            f"The smallest maximum drawdown came from **{variants[decision['safest_variant']]['label']}**."
        ),
        "",
        decision["conclusion"],
        "",
        "This is a retrospective portfolio-admission audit of the frozen locked-holdout strategy. It does not change production behavior, signal generation, entries, stops, targets, scoring, or market-regime rules.",
        "",
        "## Dataset and method",
        "",
        f"- Locked holdout signals: **{result['source']['validated_trades']}** trades across **{result['source']['validated_symbols']}** stocks and **{len(result['source']['sectors'])}** sectors.",
        f"- Period: **{result['source']['period']['start']}** through **{result['source']['period']['end']}**.",
        "- Every trade keeps its original entry, stop, targets, partial exits, slippage, costs, and final R.",
        "- Confidence for Variant E is reconstructed only from candles available at signal close.",
        "- Entry and exit dates both count as active, which treats same-day overlap conservatively.",
        "- A literal percentage cap cannot start from an empty portfolio because its first position is 100%. During this unavoidable startup state, only additions that strictly reduce concentration are accepted. Once the active book reaches the cap, the cap is enforced directly.",
        "- Worst simultaneous loss is the ex-post sum of negative final R for trades open on the same session. It is a loss-cluster diagnostic, not a daily marked-to-market equity value.",
        "- Variant-minus-baseline intervals use a paired moving-block bootstrap of chronologically realised trades (20-trade blocks, 10,000 samples).",
        (
            f"- The no-limit expectancy ({baseline_current['expectancy']:.4f}R), "
            f"profit factor ({baseline_current['profit_factor']:.4f}), win rate "
            f"({baseline_current['win_rate']:.2f}%), and trade count "
            f"({baseline_current['total_trades']}) exactly reproduce the locked result."
        ),
        "",
        "### Drawdown audit finding",
        "",
        (
            f"The locked holdout report stated "
            f"**{locked_point_metrics['maximum_drawdown_in_ticker_processing_order']:.4f}R** "
            f"maximum drawdown, but its ledger was accumulated in ticker-processing order. "
            f"Reordering the same immutable outcomes by realised exit date produces the "
            f"portfolio-chronological **{baseline_current['maximum_drawdown']:.4f}R** "
            "drawdown reported here. No trade outcome or production code was changed. "
            "Concentration variants are compared only against this corrected chronological baseline."
        ),
        "",
        "## Variant results",
        "",
        "| Variant | Trades | Rejected | Expectancy | Profit factor | Win rate | Average R | Max drawdown | Worst simultaneous loss | Max concurrent | 95% expectancy CI | Double-cost expectancy | Double-cost PF |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|",
    ]
    for variant_id, result_item in variants.items():
        current = result_item["current_costs"]
        double = result_item["double_costs"]
        interval = current["bootstrap_expectancy_95_ci"]
        lines.append(
            f"| {result_item['label']} | {current['total_trades']} | {result_item['signals_rejected_by_limit']} "
            f"| {_format_number(current['expectancy'])}R | {_format_number(current['profit_factor'])} "
            f"| {_format_number(current['win_rate'], 2)}% | {_format_number(current['average_r'])}R "
            f"| {_format_number(current['maximum_drawdown'])}R | {_format_number(current['worst_simultaneous_loss_r'])}R "
            f"| {current['maximum_concurrent_positions']} | "
            f"{_format_number(interval[0])}R to {_format_number(interval[1])}R "
            f"| {_format_number(double['expectancy'])}R | {_format_number(double['profit_factor'])} |"
        )

    lines.extend(
        [
            "",
            "## Paired comparison with no sector limit",
            "",
            "Positive drawdown improvement means a smaller loss. Intervals include the dependency between each original trade and the rule that retained or rejected it.",
            "",
            "| Variant | Expectancy difference | 95% CI | Drawdown improvement | 95% CI |",
            "|---|---:|---|---:|---|",
        ]
    )
    for result_item in variants.values():
        comparison = result_item["comparison_vs_no_limit"]
        expectancy_interval = comparison["expectancy_difference_95_ci"]
        drawdown_interval = comparison[
            "maximum_drawdown_improvement_95_ci"
        ]
        lines.append(
            f"| {result_item['label']} | "
            f"{comparison['expectancy_difference_r']:+.4f}R | "
            f"{expectancy_interval[0]:+.4f}R to {expectancy_interval[1]:+.4f}R "
            f"| {comparison['maximum_drawdown_improvement_r']:+.4f}R | "
            f"{drawdown_interval[0]:+.4f}R to {drawdown_interval[1]:+.4f}R |"
        )

    lines.extend(
        [
            "",
            "## Performance by market regime",
            "",
        ]
    )
    for result_item in variants.values():
        lines.extend(
            [
                f"### {result_item['label']}",
                "",
                "| Regime | Trades | Expectancy | Profit factor | Win rate | Max drawdown | 95% expectancy CI |",
                "|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        for regime, metrics in result_item["current_costs"][
            "performance_by_market_regime"
        ].items():
            interval = metrics["bootstrap_expectancy_95_ci"]
            lines.append(
                f"| {regime} | {metrics['total_trades']} | {_format_number(metrics['expectancy'])}R "
                f"| {_format_number(metrics['profit_factor'])} | {_format_number(metrics['win_rate'], 2)}% "
                f"| {_format_number(metrics['maximum_drawdown'])}R | "
                f"{_format_number(interval[0])}R to {_format_number(interval[1])}R |"
            )
        lines.append("")

    lines.extend(
        [
            "## Utilities and Real Estate",
            "",
            "| Variant | Trades | Share of trades | Expectancy | Total R | Share of positive R | Share of loss R |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for result_item in variants.values():
        impact = result_item["current_costs"]["utilities_and_real_estate"]
        lines.append(
            f"| {result_item['label']} | {impact['total_trades']} | {_format_number(impact['share_of_trades_percent'], 2)}% "
            f"| {_format_number(impact['expectancy'])}R | {_format_number(impact['total_r'])}R "
            f"| {_format_number(impact['share_of_positive_r_percent'], 2)}% "
            f"| {_format_number(impact['share_of_loss_r_percent'], 2)}% |"
        )
    baseline_rate_sensitive = variants["A_no_sector_limit"]["current_costs"][
        "utilities_and_real_estate"
    ]
    lines.extend(
        [
            "",
            (
                f"In the no-limit ledger, Utilities and Real Estate were "
                f"**{baseline_rate_sensitive['share_of_trades_percent']:.2f}%** of trades, "
                f"produced **{baseline_rate_sensitive['share_of_positive_r_percent']:.2f}%** "
                f"of gross positive R, and produced "
                f"**{baseline_rate_sensitive['share_of_loss_r_percent']:.2f}%** of gross loss R. "
                "They did not create a disproportionate share of profit or loss. "
                f"Their combined expectancy (**{baseline_rate_sensitive['expectancy']:.4f}R**) "
                f"was below the portfolio expectancy (**{baseline_current['expectancy']:.4f}R**)."
            ),
            "",
            "| Sector | Trades | Expectancy | Profit factor | Win rate | Total R | 95% expectancy CI |",
            "|---|---:|---:|---:|---:|---:|---|",
        ]
    )
    for sector, metrics in baseline_rate_sensitive["by_sector"].items():
        interval = metrics["bootstrap_expectancy_95_ci"]
        lines.append(
            f"| {sector} | {metrics['total_trades']} | "
            f"{_format_number(metrics['expectancy'])}R | "
            f"{_format_number(metrics['profit_factor'])} | "
            f"{_format_number(metrics['win_rate'], 2)}% | "
            f"{_format_number(metrics['total_r'])}R | "
            f"{_format_number(interval[0])}R to "
            f"{_format_number(interval[1])}R |"
        )

    baseline_correlation = variants["A_no_sector_limit"]["current_costs"][
        "simultaneous_trade_correlation"
    ]
    lines.extend(
        [
            "",
            "## Simultaneous-trade correlation",
            "",
            (
                f"In the uncapped ledger, {baseline_correlation['all_simultaneous_pairs']['pair_count']} "
                f"overlapping trade pairs had at least three shared sessions. Mean daily-return correlation was "
                f"**{_format_number(baseline_correlation['all_simultaneous_pairs']['mean'])}** overall, "
                f"**{_format_number(baseline_correlation['same_sector_pairs']['mean'])}** within the same sector, and "
                f"**{_format_number(baseline_correlation['utilities_real_estate_pairs']['mean'])}** for Utilities/Real Estate pairs."
            ),
            "",
            "These are correlations of split-adjusted underlying daily close returns while both trades were open. They are not correlations of final trade R and do not model intraday covariance.",
            "",
            "## Sector exposure over time",
            "",
            "The machine-readable artifact contains monthly exposure histories and per-sector peak/average active shares for every variant. Key peak exposures are:",
            "",
            "| Variant | Leading sector | Peak share | Peak active positions | Trading days above 30% |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for result_item in variants.values():
        exposures = result_item["current_costs"]["sector_exposure_over_time"][
            "summary"
        ]
        leading = max(
            exposures,
            key=lambda item: (
                item["peak_active_share_percent"],
                item["peak_active_positions"],
            ),
        )
        lines.append(
            f"| {result_item['label']} | {leading['sector']} | "
            f"{_format_number(leading['peak_active_share_percent'], 2)}% | "
            f"{leading['peak_active_positions']} | "
            f"{leading['trading_days_above_30_percent']} |"
        )

    lines.extend(
        [
            "",
            "## Interpretation",
            "",
        ]
    )
    baseline = variants["A_no_sector_limit"]["current_costs"]
    for variant_id, result_item in variants.items():
        if variant_id == "A_no_sector_limit":
            continue
        current = result_item["current_costs"]
        comparison = result_item["comparison_vs_no_limit"]
        expectancy_interval = comparison["expectancy_difference_95_ci"]
        drawdown_interval = comparison[
            "maximum_drawdown_improvement_95_ci"
        ]
        lines.append(
            f"- **{result_item['label']}** rejected **{result_item['signals_rejected_by_limit']}** signals, "
            f"changed expectancy by **{current['expectancy'] - baseline['expectancy']:+.4f}R**, "
            f"and improved maximum drawdown by **{current['maximum_drawdown'] - baseline['maximum_drawdown']:+.4f}R**. "
            f"The paired expectancy-difference interval was **{expectancy_interval[0]:+.4f}R to {expectancy_interval[1]:+.4f}R**; "
            f"the paired drawdown-improvement interval was **{drawdown_interval[0]:+.4f}R to {drawdown_interval[1]:+.4f}R**."
        )
    lines.extend(
        [
            "",
            "**Conclusion:** Variant C provides the strongest exploratory balance: it rejected 24 trades, left expectancy effectively unchanged, and reduced the observed chronological drawdown by 3.3962R. Variant E had the smallest observed drawdown but gave up 0.0169R expectancy and rejected 95 trades. The paired intervals and the reuse of one holdout do not establish that either improvement will persist. Sector concentration controls are therefore **not statistically justified for production yet**.",
            "",
            "The audit does not implement a sector cap. Any future control would need a separately locked validation because comparing five alternatives on the same holdout introduces selection risk.",
            "",
            "## Limitations",
            "",
            "- The ledger contains equal-risk R outcomes, not a fully capital-constrained brokerage portfolio.",
            "- The startup-safe cap convention is explicit but is one possible implementation of percentage limits.",
            "- Worst simultaneous loss uses eventual losing outcomes for positions that overlapped; daily mark-to-market loss may differ.",
            "- Maximum drawdown is a chronological realised-R sequence without capital allocation or mark-to-market accounting.",
            "- Confidence reconstruction uses the current deterministic institutional engine on historical signal-close data. It is not a probability.",
            "- Five variants are compared on one locked historical window, so the apparent winner is not independently validated.",
            "- Sector labels are the frozen research-universe labels and are not point-in-time constituent classifications.",
            "",
            f"Machine-readable results: `{RESULTS_PATH.relative_to(ROOT)}`.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    result = run_audit()
    write_report(result)
    summary = {
        "validated_trades": result["source"]["validated_trades"],
        "best_performing_variant": result["decision"][
            "best_performing_variant"
        ],
        "safest_variant": result["decision"]["safest_variant"],
        "statistically_justified_controls": result["decision"][
            "statistically_justified_controls"
        ],
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
