"""Locked validation of portfolio constraints on a later chronological period.

Milestone 47 selected portfolio limits on the 2016-07-01 through 2021-07-10
ledger. This module freezes those limits and evaluates them on the separate
2021-07-12 through 2026-07-23 cached dataset. Strategy and execution rules are
not changed.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from backtesting.execution import (
    entry_fill_price,
    exit_fill_price,
    transaction_cost,
)
from calibration.portfolio_constraint_validation import (
    ConstraintConfiguration,
    _performance_metrics,
    apply_constraints,
)
from calibration.pullback_robustness import DATASET_CACHE, RANDOM_SEED, SYMBOLS
from calibration.regime_gated_pullback import (
    SELECTED,
    _candidate_rows,
    _run,
)
from calibration.run_audit import SLIPPAGE_BPS, TRANSACTION_COST_BPS
from calibration.sector_concentration_audit import (
    enrich_signal_time_confidence,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE_LEDGER = ROOT / "artifacts" / "regime_gated_pullback_trades.csv"
MILESTONE_47_RESULTS = (
    ROOT / "artifacts" / "portfolio_constraint_results.json"
)
RESULTS_PATH = (
    ROOT / "artifacts" / "locked_portfolio_constraint_results.json"
)
REPORT_PATH = ROOT / "docs" / "LOCKED_PORTFOLIO_CONSTRAINT_HOLDOUT.md"

FROZEN_CONFIGURATION = ConstraintConfiguration(
    maximum_concurrent_positions=10,
    maximum_total_open_risk_r=10.0,
    maximum_daily_new_risk_r=1.0,
    ranking_method="highest_confidence",
)
COMPARATOR_CONFIGURATION = ConstraintConfiguration(
    maximum_concurrent_positions=10,
    maximum_total_open_risk_r=10.0,
    maximum_daily_new_risk_r=3.0,
    ranking_method="highest_confidence",
)
SELECTION_PERIOD_END = pd.Timestamp("2021-07-10")
MATERIAL_DRAWDOWN_REDUCTION = 0.25
MATERIALLY_NEGATIVE_EXPECTANCY_R = -0.05
RANDOM_BASELINE_SEED = RANDOM_SEED + 48


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _as_bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _as_float(value: Any) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Non-finite candidate value: {value}")
    return result


def load_cached_histories() -> tuple[
    dict[str, pd.DataFrame], pd.DataFrame, pd.DataFrame
]:
    histories = {
        ticker: pd.read_csv(
            DATASET_CACHE / f"{ticker}.csv",
            index_col=0,
            parse_dates=True,
        )
        for ticker in sorted(SYMBOLS)
    }
    spy = pd.read_csv(
        DATASET_CACHE / "SPY.csv", index_col=0, parse_dates=True
    )
    qqq = pd.read_csv(
        DATASET_CACHE / "QQQ.csv", index_col=0, parse_dates=True
    )
    return histories, spy, qqq


def load_cached_candidates(
    histories: dict[str, pd.DataFrame],
    source_ledger: Path = SOURCE_LEDGER,
) -> list[dict[str, Any]]:
    """Recover signal-time inputs from the audit ledger without future data."""

    if not source_ledger.exists():
        raise FileNotFoundError(source_ledger)
    index_lookup = {
        ticker: {
            pd.Timestamp(timestamp).date().isoformat(): index
            for index, timestamp in enumerate(history.index)
        }
        for ticker, history in histories.items()
    }
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
    with source_ledger.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if (
                row.get("filter_id") != "existing_market_regime"
                or row.get("cost_multiplier") != "1"
            ):
                continue
            ticker = str(row["ticker"])
            signal_date = str(row["signal_date"])
            key = (ticker, signal_date)
            if key in candidates:
                continue
            if ticker not in index_lookup or signal_date not in index_lookup[ticker]:
                raise ValueError(
                    f"Raw signal candle is missing for {ticker} {signal_date}."
                )
            candidate = {
                "ticker": ticker,
                "sector": str(row["sector"]),
                "index": index_lookup[ticker][signal_date],
                "signal_date": signal_date,
                "ema20": _as_float(row["ema20"]),
                "swing_low_20": _as_float(row["swing_low_20"]),
                "atr": _as_float(row["atr"]),
                "walk_forward_period": str(row["walk_forward_period"]),
            }
            candidate.update(
                {field: _as_bool(row[field]) for field in boolean_fields}
            )
            candidates[key] = candidate
    result = sorted(
        candidates.values(),
        key=lambda row: (row["signal_date"], row["ticker"]),
    )
    if not result:
        raise ValueError("No cached constraint-holdout candidates were found.")
    return result


def candidates_from_cache(
    histories: dict[str, pd.DataFrame],
    spy: pd.DataFrame,
    qqq: pd.DataFrame,
) -> tuple[list[dict[str, Any]], str]:
    if SOURCE_LEDGER.exists():
        return load_cached_candidates(histories), "cached audit ledger"
    return (
        _candidate_rows(histories, spy, qqq),
        "deterministic reconstruction from cached OHLCV",
    )


def _buy_and_hold(
    histories: dict[str, pd.DataFrame],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> dict[str, Any]:
    normalized = []
    individual_returns = []
    for ticker in sorted(histories):
        window = histories[ticker].loc[start:end, "Close"].astype(float)
        if len(window) < 2:
            continue
        normalized.append((window / float(window.iloc[0])).rename(ticker))
        individual_returns.append(
            (float(window.iloc[-1]) / float(window.iloc[0]) - 1) * 100
        )
    frame = pd.concat(normalized, axis=1).ffill().dropna()
    portfolio = frame.mean(axis=1)
    drawdown = (portfolio / portfolio.cummax() - 1) * 100
    years = (end - start).days / 365.2425
    ending_return = (float(portfolio.iloc[-1]) - 1) * 100
    return {
        "symbols": len(individual_returns),
        "equal_weight_total_return_percent": round(ending_return, 4),
        "equal_weight_annualized_return_percent": round(
            ((1 + ending_return / 100) ** (1 / years) - 1) * 100, 4
        ),
        "equal_weight_maximum_drawdown_percent": round(
            float(drawdown.min()), 4
        ),
        "average_symbol_return_percent": round(
            float(np.mean(individual_returns)), 4
        ),
        "winning_symbols_percent": round(
            float(np.mean(np.asarray(individual_returns) > 0) * 100), 2
        ),
        "units": "percent return; not R-multiples",
    }


def _matched_random_entries(
    accepted_trades: list[dict[str, Any]],
    histories: dict[str, pd.DataFrame],
    *,
    seed: int = RANDOM_BASELINE_SEED,
) -> dict[str, Any]:
    """Match ticker, trade count, and holding duration using random dates."""

    rng = np.random.default_rng(seed)
    returns = []
    for trade in accepted_trades:
        data = histories[str(trade["ticker"])]
        holding_days = max(1, int(trade.get("holding_days") or 1))
        latest_entry = len(data) - holding_days - 1
        if latest_entry <= 1:
            continue
        entry_index = int(rng.integers(1, latest_entry + 1))
        exit_index = entry_index + holding_days
        shares = 100
        entry = entry_fill_price(
            float(data.iloc[entry_index]["Open"]), SLIPPAGE_BPS
        )
        exit_price = exit_fill_price(
            float(data.iloc[exit_index]["Close"]), SLIPPAGE_BPS
        )
        pnl = (
            (exit_price - entry) * shares
            - transaction_cost(
                entry, shares, TRANSACTION_COST_BPS
            )
            - transaction_cost(
                exit_price, shares, TRANSACTION_COST_BPS
            )
        )
        returns.append(pnl / (entry * shares) * 100)
    values = np.asarray(returns, dtype=float)
    return {
        "observations": len(values),
        "average_return_percent": (
            round(float(values.mean()), 4) if len(values) else 0.0
        ),
        "win_rate_percent": (
            round(float(np.mean(values > 0) * 100), 2)
            if len(values)
            else 0.0
        ),
        "median_return_percent": (
            round(float(np.median(values)), 4) if len(values) else 0.0
        ),
        "matching": (
            "Same ticker, trade count, and holding duration; deterministic "
            "random entry date with current costs and adverse slippage."
        ),
        "units": "percent return; not R-multiples",
        "seed": seed,
    }


def _strategy_summary(
    trades: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    years: float,
    seed_offset: int,
) -> dict[str, Any]:
    return _performance_metrics(
        trades,
        len(rejected),
        years,
        seed_offset,
        include_bootstrap=True,
    )


def _approval(
    frozen: dict[str, Any],
    unconstrained: dict[str, Any],
    double_cost: dict[str, Any],
) -> dict[str, Any]:
    material_threshold = unconstrained["maximum_drawdown_r"] * (
        1 - MATERIAL_DRAWDOWN_REDUCTION
    )
    ci = frozen["bootstrap_expectancy_95_ci"]
    checks = {
        "positive_expectancy": frozen["expectancy_r"] > 0,
        "profit_factor_above_one": (frozen["profit_factor"] or 0) > 1,
        "materially_lower_drawdown": (
            frozen["maximum_drawdown_r"] > material_threshold
        ),
        "maximum_open_risk_at_most_10R": (
            frozen["maximum_open_risk_r"] <= 10
        ),
        "maximum_positions_at_most_10": (
            frozen["maximum_concurrent_positions"] <= 10
        ),
        "profitable_under_double_costs": (
            double_cost["expectancy_r"] > 0
            and (double_cost["profit_factor"] or 0) > 1
        ),
        "expectancy_interval_not_materially_negative": (
            ci is not None and ci[0] >= MATERIALLY_NEGATIVE_EXPECTANCY_R
        ),
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "material_drawdown_threshold_r": round(material_threshold, 4),
        "materially_negative_expectancy_threshold_r": (
            MATERIALLY_NEGATIVE_EXPECTANCY_R
        ),
    }


def run_holdout() -> dict[str, Any]:
    milestone_47 = json.loads(
        MILESTONE_47_RESULTS.read_text(encoding="utf-8")
    )
    selected_id = milestone_47["decision"][
        "best_risk_adjusted_configuration"
    ]
    selected_config = milestone_47["configurations"][selected_id][
        "configuration"
    ]
    if selected_config != {
        "maximum_concurrent_positions": 10,
        "maximum_daily_new_risk_r": 1.0,
        "maximum_total_open_risk_r": 10.0,
        "ranking_method": "highest_confidence",
    }:
        raise ValueError("Milestone 47 selected constraints do not match freeze.")

    histories, spy, qqq = load_cached_histories()
    source_start = max(
        min(history.index) for history in [*histories.values(), spy, qqq]
    ).normalize()
    source_end = min(
        max(history.index) for history in [*histories.values(), spy, qqq]
    ).normalize()
    if source_start <= SELECTION_PERIOD_END:
        raise ValueError(
            "Constraint holdout overlaps the Milestone 47 selection period."
        )
    years = (source_end - source_start).days / 365.2425

    candidates, candidate_source = candidates_from_cache(
        histories, spy, qqq
    )
    current_trades, strategy_rejected, eligible = _run(
        "existing_market_regime", candidates, histories, 1
    )
    double_trades, double_strategy_rejected, double_eligible = _run(
        "existing_market_regime", candidates, histories, 2
    )
    confidence_cache: dict[tuple[str, str], tuple[float, str]] = {}
    enrich_signal_time_confidence(
        current_trades, histories, spy, confidence_cache
    )
    enrich_signal_time_confidence(
        double_trades, histories, spy, confidence_cache
    )

    frozen_trades, frozen_rejected = apply_constraints(
        current_trades, FROZEN_CONFIGURATION
    )
    frozen_double_trades, frozen_double_rejected = apply_constraints(
        double_trades, FROZEN_CONFIGURATION
    )
    comparator_trades, comparator_rejected = apply_constraints(
        current_trades, COMPARATOR_CONFIGURATION
    )
    comparator_double_trades, comparator_double_rejected = apply_constraints(
        double_trades, COMPARATOR_CONFIGURATION
    )

    unconstrained = _strategy_summary(
        current_trades, [], years, 100
    )
    unconstrained_double = _strategy_summary(
        double_trades, [], years, 101
    )
    frozen = _strategy_summary(
        frozen_trades, frozen_rejected, years, 102
    )
    frozen_double = _strategy_summary(
        frozen_double_trades, frozen_double_rejected, years, 103
    )
    comparator = _strategy_summary(
        comparator_trades, comparator_rejected, years, 104
    )
    comparator_double = _strategy_summary(
        comparator_double_trades,
        comparator_double_rejected,
        years,
        105,
    )
    approval = _approval(frozen, unconstrained, frozen_double)
    return {
        "holdout_status": "completed",
        "production_constraints_enabled": False,
        "frozen_strategy": {
            "name": "Regime-Gated Pullback",
            **SELECTED,
            "market_regime_filter": "existing market-regime engine",
        },
        "frozen_portfolio_constraints": {
            "maximum_concurrent_positions": 10,
            "maximum_total_open_risk_r": 10.0,
            "maximum_daily_new_risk_r": 1.0,
            "signal_ranking": "signal-time confidence",
        },
        "data": {
            "source_start": source_start.date().isoformat(),
            "source_end": source_end.date().isoformat(),
            "selection_period_end": (
                SELECTION_PERIOD_END.date().isoformat()
            ),
            "overlap_with_milestone_47": False,
            "symbols": len(histories),
            "candidate_signals": len(candidates),
            "candidate_source": candidate_source,
            "candidate_signal_start": min(
                row["signal_date"] for row in candidates
            ),
            "candidate_signal_end": max(
                row["signal_date"] for row in candidates
            ),
            "source_ledger": (
                str(SOURCE_LEDGER.relative_to(ROOT))
                if SOURCE_LEDGER.exists()
                else None
            ),
            "source_ledger_sha256": (
                _sha256(SOURCE_LEDGER)
                if SOURCE_LEDGER.exists()
                else None
            ),
            "milestone_47_results_sha256": _sha256(
                MILESTONE_47_RESULTS
            ),
        },
        "strategy_execution_counts": {
            "eligible_signals": eligible,
            "unconstrained_trades": len(current_trades),
            "strategy_rejections": len(strategy_rejected),
            "double_cost_eligible_signals": double_eligible,
            "double_cost_unconstrained_trades": len(double_trades),
            "double_cost_strategy_rejections": len(
                double_strategy_rejected
            ),
        },
        "results": {
            "frozen_10_positions_10R_1R_daily": {
                "current_costs": frozen,
                "double_costs": frozen_double,
            },
            "unconstrained": {
                "current_costs": unconstrained,
                "double_costs": unconstrained_double,
            },
            "comparator_10_positions_10R_3R_daily": {
                "current_costs": comparator,
                "double_costs": comparator_double,
            },
        },
        "baselines": {
            "buy_and_hold": _buy_and_hold(
                histories, source_start, source_end
            ),
            "matched_random_entries": _matched_random_entries(
                frozen_trades, histories
            ),
        },
        "approval": approval,
        "decision": (
            "The frozen portfolio constraints pass the locked holdout, but "
            "remain research-only pending explicit production approval."
            if approval["passed"]
            else "The frozen portfolio constraints fail the locked holdout "
            "and must not be enabled in production."
        ),
        "methodology": {
            "chronology": (
                "Actual entries, partial exits, final exits, costs, and "
                "slippage processed chronologically; same-session entries "
                "precede exits."
            ),
            "confidence": (
                "Institutional confidence reconstructed only from ticker and "
                "SPY candles available at the signal close."
            ),
            "bootstrap": (
                "5,000 deterministic trade-level resamples of net R."
            ),
            "material_drawdown_reduction": (
                "At least 25% less severe than the unconstrained chronological "
                "holdout drawdown."
            ),
            "materially_negative_ci": (
                "The expectancy interval lower bound must be at least -0.05R."
            ),
            "baseline_units": (
                "Buy-and-hold and matched-random baselines are percent returns "
                "and are not directly interchangeable with strategy R."
            ),
        },
    }


def _metric_row(label: str, result: dict[str, Any]) -> str:
    ci = result["bootstrap_expectancy_95_ci"]
    return (
        f"| {label} | {result['accepted_trades']} | "
        f"{result['rejected_trades']} | {result['expectancy_r']:.4f}R | "
        f"{result['profit_factor']:.4f} | "
        f"{result['win_rate_percent']:.2f}% | "
        f"{result['maximum_drawdown_r']:.4f}R | "
        f"{result['maximum_open_risk_r']:.1f}R | "
        f"{result['maximum_concurrent_positions']} | "
        f"{result['trades_per_year']:.2f} | "
        f"{ci[0]:.4f} to {ci[1]:.4f}R |"
    )


def write_outputs(result: dict[str, Any]) -> None:
    RESULTS_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    frozen = result["results"][
        "frozen_10_positions_10R_1R_daily"
    ]["current_costs"]
    frozen_double = result["results"][
        "frozen_10_positions_10R_1R_daily"
    ]["double_costs"]
    unconstrained = result["results"]["unconstrained"]["current_costs"]
    comparator = result["results"][
        "comparator_10_positions_10R_3R_daily"
    ]["current_costs"]
    buy_hold = result["baselines"]["buy_and_hold"]
    random = result["baselines"]["matched_random_entries"]
    approval = result["approval"]
    sector = frozen["sector_exposure"]
    average_sector_rows = sorted(
        sector["average_active_share_percent"].items(),
        key=lambda item: (-item[1], item[0]),
    )
    lines = [
        "# Locked Portfolio Constraint Holdout",
        "",
        "## Executive verdict",
        "",
        (
            f"The frozen 10-position / 10R / 1R-daily portfolio "
            f"{'passes' if approval['passed'] else 'fails'} the later "
            "chronological constraint holdout. No production constraint was "
            "enabled."
        ),
        "",
        (
            f"Expectancy is **{frozen['expectancy_r']:.4f}R**, profit factor "
            f"is **{frozen['profit_factor']:.4f}**, and corrected maximum "
            f"drawdown is **{frozen['maximum_drawdown_r']:.4f}R** versus "
            f"**{unconstrained['maximum_drawdown_r']:.4f}R** unconstrained."
        ),
        "",
        "## Frozen configuration",
        "",
        "- Maximum concurrent positions: **10**",
        "- Maximum total open risk: **10R**",
        "- Maximum daily new risk: **1R**",
        "- Ranking: **signal-time confidence**",
        "- Strategy: **frozen Regime-Gated Pullback**",
        "",
        "## Holdout separation",
        "",
        (
            f"Milestone 47 ended on "
            f"**{result['data']['selection_period_end']}**. This constraint "
            f"holdout uses cached data from **{result['data']['source_start']}** "
            f"through **{result['data']['source_end']}**, with no overlap."
        ),
        "",
        "## Strategy comparison",
        "",
        "| Portfolio | Accepted | Portfolio-rejected | Expectancy | PF | Win rate | Drawdown | Max risk | Max positions | Trades/year | Expectancy 95% CI |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
        _metric_row("Frozen 10 / 10R / 1R", frozen),
        _metric_row("Unconstrained", unconstrained),
        _metric_row("Comparator 10 / 10R / 3R", comparator),
        "",
        "## Tail risk and exposure",
        "",
        "| Metric | Frozen result |",
        "| --- | ---: |",
        (
            f"| Worst trading day | "
            f"{frozen['worst_trading_day']['realized_r']:.4f}R on "
            f"{frozen['worst_trading_day']['date']} |"
        ),
        (
            f"| Worst rolling five-day period | "
            f"{frozen['worst_rolling_5_day_period']['realized_r']:.4f}R "
            f"({frozen['worst_rolling_5_day_period']['start']} to "
            f"{frozen['worst_rolling_5_day_period']['end']}) |"
        ),
        (
            f"| Peak single-sector active share | "
            f"{sector['peak_single_sector_share_percent']:.2f}% "
            f"({sector['peak_sector']}) |"
        ),
        "",
        "### Average active sector exposure",
        "",
        "| Sector | Average active share |",
        "| --- | ---: |",
        *[
            f"| {sector_name} | {share:.2f}% |"
            for sector_name, share in average_sector_rows
        ],
        "",
        "## Double-cost performance",
        "",
        (
            f"The frozen constraints accept {frozen_double['accepted_trades']} "
            f"trades at doubled costs, with "
            f"**{frozen_double['expectancy_r']:.4f}R** expectancy, "
            f"**{frozen_double['profit_factor']:.4f}** profit factor, and "
            f"**{frozen_double['maximum_drawdown_r']:.4f}R** drawdown."
        ),
        "",
        "## Baselines",
        "",
        (
            f"- Equal-weight buy and hold: "
            f"{buy_hold['equal_weight_total_return_percent']:.2f}% total "
            f"return and {buy_hold['equal_weight_maximum_drawdown_percent']:.2f}% "
            "maximum drawdown."
        ),
        (
            f"- Matched random entries: {random['observations']} observations, "
            f"{random['average_return_percent']:.4f}% average return, and "
            f"{random['win_rate_percent']:.2f}% win rate."
        ),
        "",
        "Baseline returns are percentages, while strategy results are "
        "R-multiples; they provide context but are not the same unit.",
        "",
        "## Approval criteria",
        "",
    ]
    for name, passed in approval["checks"].items():
        lines.append(
            f"- {'PASS' if passed else 'FAIL'} — "
            f"{name.replace('_', ' ')}"
        )
    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "This is a locked test of portfolio constraints, not a fresh "
            "validation of the underlying strategy: the later dataset was used "
            "in earlier strategy research but was not used to select the "
            "Milestone 47 portfolio limits. The constraints remain research-only "
            "until an explicit production decision.",
            "",
            (
                "Machine-readable results: "
                f"`{RESULTS_PATH.relative_to(ROOT)}`."
            ),
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    result = run_holdout()
    write_outputs(result)
    frozen = result["results"][
        "frozen_10_positions_10R_1R_daily"
    ]["current_costs"]
    print(
        json.dumps(
            {
                "holdout_expectancy_r": frozen["expectancy_r"],
                "holdout_profit_factor": frozen["profit_factor"],
                "maximum_drawdown_r": frozen["maximum_drawdown_r"],
                "constraints_passed": result["approval"]["passed"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
