"""Research-only validation of chronological portfolio admission constraints.

The experiment consumes the frozen locked-holdout trades after their entry and
exit prices have already been determined. It changes only which simultaneous
signals an analysis portfolio accepts; production strategy behavior is not
modified.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from backtesting.portfolio_risk import (
    PARTIAL_EXIT_PRIORITY,
    build_portfolio_events,
    calculate_chronological_portfolio,
)
from calibration.sector_concentration_audit import (
    _load_histories,
    _regenerate_double_cost,
    enrich_signal_time_confidence,
    load_validated_candidates,
    load_validated_ledger,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS_PATH = ROOT / "artifacts" / "portfolio_constraint_results.json"
REPORT_PATH = ROOT / "docs" / "PORTFOLIO_CONSTRAINT_VALIDATION.md"
LOCKED_RESULTS_PATH = ROOT / "artifacts" / "locked_holdout_results.json"
LEDGER_PATH = ROOT / "artifacts" / "locked_holdout_trades.csv"

MAXIMUM_POSITIONS = (5, 10, 15, 20)
MAXIMUM_OPEN_RISK_R = (5.0, 10.0, 15.0, 20.0)
MAXIMUM_DAILY_NEW_RISK_R = (1.0, 2.0, 3.0, 5.0)
RANKING_METHODS = (
    "highest_confidence",
    "best_risk_reward",
    "lowest_risk_percentage",
    "one_highest_ranked_per_sector",
)
RANDOM_SEED = 20260747
BOOTSTRAP_SAMPLES = 5_000
MATERIAL_DRAWDOWN_REDUCTION = 0.25


@dataclass(frozen=True)
class ConstraintConfiguration:
    maximum_concurrent_positions: int
    maximum_total_open_risk_r: float
    maximum_daily_new_risk_r: float
    ranking_method: str

    @property
    def id(self) -> str:
        return (
            f"positions_{self.maximum_concurrent_positions}"
            f"__risk_{self.maximum_total_open_risk_r:g}R"
            f"__daily_{self.maximum_daily_new_risk_r:g}R"
            f"__{self.ranking_method}"
        )


def configurations() -> Iterable[ConstraintConfiguration]:
    for positions in MAXIMUM_POSITIONS:
        for open_risk in MAXIMUM_OPEN_RISK_R:
            for daily_risk in MAXIMUM_DAILY_NEW_RISK_R:
                for ranking in RANKING_METHODS:
                    yield ConstraintConfiguration(
                        positions,
                        open_risk,
                        daily_risk,
                        ranking,
                    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def planned_risk_reward(trade: dict[str, Any]) -> float:
    entry = _finite(trade.get("entry_price"))
    stop = _finite(trade.get("stop_loss"))
    target = _finite(trade.get("target_1"))
    risk = entry - stop
    return (target - entry) / risk if risk > 0 else float("-inf")


def position_risk_percentage(trade: dict[str, Any]) -> float:
    entry = _finite(trade.get("entry_price"))
    stop = _finite(trade.get("stop_loss"))
    return (entry - stop) / entry * 100 if entry > stop > 0 else float("inf")


def rank_daily_signals(
    trades: list[dict[str, Any]], ranking_method: str
) -> list[dict[str, Any]]:
    """Return a deterministic admission order for signals sharing an entry day."""

    stable = lambda row: (str(row["ticker"]), str(row["trade_id"]))
    if ranking_method == "highest_confidence":
        return sorted(
            trades,
            key=lambda row: (-_finite(row.get("confidence")), *stable(row)),
        )
    if ranking_method == "best_risk_reward":
        return sorted(
            trades,
            key=lambda row: (-planned_risk_reward(row), *stable(row)),
        )
    if ranking_method == "lowest_risk_percentage":
        return sorted(
            trades,
            key=lambda row: (position_risk_percentage(row), *stable(row)),
        )
    if ranking_method != "one_highest_ranked_per_sector":
        raise ValueError(f"Unknown ranking method: {ranking_method}")

    # Sector round-robin: the highest-confidence signal from every represented
    # sector is considered before a second signal from any sector.
    by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        by_sector[str(trade.get("sector") or "Unknown")].append(trade)
    for sector in by_sector:
        by_sector[sector].sort(
            key=lambda row: (-_finite(row.get("confidence")), *stable(row))
        )
    ranked: list[dict[str, Any]] = []
    depth = 0
    while any(depth < len(rows) for rows in by_sector.values()):
        round_rows = [
            rows[depth]
            for rows in by_sector.values()
            if depth < len(rows)
        ]
        ranked.extend(
            sorted(
                round_rows,
                key=lambda row: (
                    -_finite(row.get("confidence")),
                    str(row.get("sector") or "Unknown"),
                    *stable(row),
                ),
            )
        )
        depth += 1
    return ranked


def apply_constraints(
    trades: list[dict[str, Any]],
    config: ConstraintConfiguration,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Admit trades chronologically without changing any trade plan."""

    entry_groups: dict[pd.Timestamp, list[dict[str, Any]]] = defaultdict(list)
    by_id = {str(trade["trade_id"]): trade for trade in trades}
    if len(by_id) != len(trades):
        raise ValueError("Constraint ledger contains duplicate trade IDs.")
    for trade in trades:
        entry_groups[pd.Timestamp(trade["entry_date"]).normalize()].append(trade)

    exits_by_day: dict[pd.Timestamp, list[dict[str, Any]]] = defaultdict(list)
    for event in build_portfolio_events(trades):
        if event["event_type"] != "entry":
            exits_by_day[event["timestamp"]].append(event)

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    active: dict[str, float] = {}
    all_dates = sorted({*entry_groups, *exits_by_day})
    for day in all_dates:
        daily_new_risk = 0.0
        for trade in rank_daily_signals(
            entry_groups.get(day, []), config.ranking_method
        ):
            trade_id = str(trade["trade_id"])
            proposed_risk = 1.0
            reasons = []
            if len(active) + 1 > config.maximum_concurrent_positions:
                reasons.append("maximum_concurrent_positions")
            if (
                sum(active.values()) + proposed_risk
                > config.maximum_total_open_risk_r + 1e-9
            ):
                reasons.append("maximum_total_open_risk")
            if (
                daily_new_risk + proposed_risk
                > config.maximum_daily_new_risk_r + 1e-9
            ):
                reasons.append("maximum_daily_new_risk")
            if reasons:
                rejected.append(
                    {
                        **trade,
                        "portfolio_rejection_reasons": reasons,
                    }
                )
                continue
            accepted.append(trade)
            active[trade_id] = proposed_risk
            daily_new_risk += proposed_risk

        # Milestone 46 ordering is explicit: same-session entries precede every
        # partial or final exit. Rejected trades never enter the active book.
        for event in sorted(
            exits_by_day.get(day, []),
            key=lambda row: (
                row["priority"],
                row["trade_id"],
                row.get("leg", ""),
            ),
        ):
            trade_id = str(event["trade_id"])
            if trade_id not in active:
                continue
            if event["event_type"] == "final_exit":
                del active[trade_id]
            elif event["priority"] == PARTIAL_EXIT_PRIORITY:
                active[trade_id] = _finite(event["remaining_fraction"])

    accepted.sort(
        key=lambda row: (
            row["entry_date"],
            row["signal_date"],
            row["ticker"],
        )
    )
    rejected.sort(
        key=lambda row: (
            row["entry_date"],
            row["signal_date"],
            row["ticker"],
        )
    )
    if len(accepted) + len(rejected) != len(by_id):
        raise AssertionError("Constraint admission did not classify every trade.")
    return accepted, rejected


def _bootstrap_expectancy(
    values: np.ndarray, seed_offset: int
) -> list[float] | None:
    if not len(values):
        return None
    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    means = np.empty(BOOTSTRAP_SAMPLES, dtype=float)
    batch_size = 250
    for start in range(0, BOOTSTRAP_SAMPLES, batch_size):
        size = min(batch_size, BOOTSTRAP_SAMPLES - start)
        samples = rng.integers(0, len(values), size=(size, len(values)))
        means[start : start + size] = values[samples].mean(axis=1)
    return [
        round(float(np.percentile(means, 2.5)), 4),
        round(float(np.percentile(means, 97.5)), 4),
    ]


def _positive_r_concentration(
    trades: list[dict[str, Any]], field: str
) -> dict[str, Any]:
    positive = defaultdict(float)
    for trade in trades:
        value = max(0.0, _finite(trade.get("r_multiple")))
        if field == "year":
            key = str(pd.Timestamp(trade["entry_date"]).year)
        else:
            key = str(trade.get(field) or "Unknown")
        positive[key] += value
    total = sum(positive.values())
    shares = {
        key: round(value / total * 100, 2) if total else 0.0
        for key, value in sorted(positive.items())
    }
    leader = max(shares, key=shares.get) if shares else None
    return {
        "leader": leader,
        "leader_share_percent": shares.get(leader, 0.0) if leader else 0.0,
        "shares_percent": shares,
    }


def _sector_exposure_summary(portfolio: dict[str, Any]) -> dict[str, Any]:
    rows = portfolio.get("sector_exposure", [])
    total_days = 0
    sector_share_sum: Counter[str] = Counter()
    peak_share = 0.0
    peak_sector = None
    peak_date = None
    for row in rows:
        counts = {
            sector: int(count)
            for sector, count in row["sector_positions"].items()
        }
        total = sum(counts.values())
        if total <= 0:
            continue
        total_days += 1
        for sector, count in counts.items():
            share = count / total * 100
            sector_share_sum[sector] += share
            if share > peak_share:
                peak_share = share
                peak_sector = sector
                peak_date = row["date"]
    return {
        "average_active_share_percent": {
            sector: round(value / total_days, 2)
            for sector, value in sorted(sector_share_sum.items())
        }
        if total_days
        else {},
        "peak_single_sector_share_percent": round(peak_share, 2),
        "peak_sector": peak_sector,
        "peak_date": peak_date,
    }


def _performance_metrics(
    trades: list[dict[str, Any]],
    rejected_count: int,
    years: float,
    seed_offset: int,
    *,
    include_bootstrap: bool,
) -> dict[str, Any]:
    values = np.asarray(
        [_finite(trade.get("r_multiple")) for trade in trades], dtype=float
    )
    gains = float(values[values > 0].sum()) if len(values) else 0.0
    losses = float(-values[values < 0].sum()) if len(values) else 0.0
    portfolio = calculate_chronological_portfolio(trades)
    return {
        "accepted_trades": len(trades),
        "rejected_trades": rejected_count,
        "expectancy_r": round(float(values.mean()), 4) if len(values) else 0.0,
        "profit_factor": round(gains / losses, 4) if losses else None,
        "win_rate_percent": (
            round(float(np.mean(values > 0) * 100), 2) if len(values) else 0.0
        ),
        "average_r": round(float(values.mean()), 4) if len(values) else 0.0,
        "total_r": round(float(values.sum()), 4),
        "maximum_drawdown_r": portfolio["maximum_drawdown_r"],
        "maximum_concurrent_positions": portfolio[
            "maximum_concurrent_positions"
        ],
        "maximum_open_risk_r": portfolio["maximum_total_open_risk_r"],
        "worst_trading_day": portfolio["worst_trading_day"],
        "worst_rolling_5_day_period": portfolio[
            "worst_rolling_5_day_period"
        ],
        "trades_per_year": round(len(trades) / years, 2),
        "bootstrap_expectancy_95_ci": (
            _bootstrap_expectancy(values, seed_offset)
            if include_bootstrap
            else None
        ),
        "sector_exposure": _sector_exposure_summary(portfolio),
        "sector_profit_concentration": _positive_r_concentration(
            trades, "sector"
        ),
        "period_profit_concentration": _positive_r_concentration(
            trades, "year"
        ),
    }


def _rejection_summary(rejected: list[dict[str, Any]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for trade in rejected:
        counter.update(trade["portfolio_rejection_reasons"])
    return dict(sorted(counter.items()))


def _approval(
    current: dict[str, Any],
    double_cost: dict[str, Any],
    baseline_drawdown: float,
) -> dict[str, Any]:
    material_threshold = baseline_drawdown * (
        1 - MATERIAL_DRAWDOWN_REDUCTION
    )
    checks = {
        "positive_expectancy": current["expectancy_r"] > 0,
        "profit_factor_above_one": (current["profit_factor"] or 0) > 1,
        "materially_lower_drawdown": (
            current["maximum_drawdown_r"] > material_threshold
        ),
        "maximum_open_risk_at_most_10R": (
            current["maximum_open_risk_r"] <= 10
        ),
        "maximum_positions_at_most_10": (
            current["maximum_concurrent_positions"] <= 10
        ),
        "positive_under_double_costs": (
            double_cost["expectancy_r"] > 0
            and (double_cost["profit_factor"] or 0) > 1
        ),
        "no_sector_majority_of_positive_r": (
            current["sector_profit_concentration"][
                "leader_share_percent"
            ]
            < 50
        ),
        "no_period_majority_of_positive_r": (
            current["period_profit_concentration"][
                "leader_share_percent"
            ]
            < 50
        ),
    }
    return {
        "approved": all(checks.values()),
        "checks": checks,
        "material_drawdown_threshold_r": round(material_threshold, 4),
    }


def _compact_configuration(
    config: ConstraintConfiguration,
    current: dict[str, Any],
    double_cost: dict[str, Any],
    rejected: list[dict[str, Any]],
    baseline_expectancy: float,
    baseline_drawdown: float,
) -> dict[str, Any]:
    approval = _approval(current, double_cost, baseline_drawdown)
    drawdown = abs(current["maximum_drawdown_r"])
    return {
        "configuration": {
            "maximum_concurrent_positions": (
                config.maximum_concurrent_positions
            ),
            "maximum_total_open_risk_r": config.maximum_total_open_risk_r,
            "maximum_daily_new_risk_r": config.maximum_daily_new_risk_r,
            "ranking_method": config.ranking_method,
        },
        "current_costs": current,
        "double_costs": double_cost,
        "constraint_rejection_reasons": _rejection_summary(rejected),
        "expectancy_impact_r": round(
            current["expectancy_r"] - baseline_expectancy, 4
        ),
        "drawdown_improvement_r": round(
            current["maximum_drawdown_r"] - baseline_drawdown, 4
        ),
        "risk_adjusted_total_r_to_drawdown": (
            round(current["total_r"] / drawdown, 4) if drawdown else None
        ),
        "approval": approval,
    }


def run_experiment() -> dict[str, Any]:
    locked = json.loads(LOCKED_RESULTS_PATH.read_text(encoding="utf-8"))
    baseline = locked["selected_regime_gated_pullback"]
    baseline_drawdown = float(baseline["maximum_drawdown"])
    baseline_expectancy = float(baseline["expectancy"])
    start = pd.Timestamp(locked["parameters"]["holdout_start"])
    end = pd.Timestamp(locked["parameters"]["holdout_end"])
    years = (end - start).days / 365.2425

    current_trades = load_validated_ledger()
    histories, spy = _load_histories(
        {str(trade["ticker"]) for trade in current_trades}
    )
    confidence_cache: dict[tuple[str, str], tuple[float, str]] = {}
    enrich_signal_time_confidence(
        current_trades, histories, spy, confidence_cache
    )
    candidates = load_validated_candidates(histories)
    double_trades = _regenerate_double_cost(candidates, histories)
    enrich_signal_time_confidence(
        double_trades, histories, spy, confidence_cache
    )

    results: dict[str, Any] = {}
    for index, config in enumerate(configurations()):
        current_accepted, current_rejected = apply_constraints(
            current_trades, config
        )
        double_accepted, double_rejected = apply_constraints(
            double_trades, config
        )
        current_metrics = _performance_metrics(
            current_accepted,
            len(current_rejected),
            years,
            index,
            include_bootstrap=True,
        )
        double_metrics = _performance_metrics(
            double_accepted,
            len(double_rejected),
            years,
            index + 1_000,
            include_bootstrap=False,
        )
        results[config.id] = _compact_configuration(
            config,
            current_metrics,
            double_metrics,
            current_rejected,
            baseline_expectancy,
            baseline_drawdown,
        )

    approved = {
        key: value
        for key, value in results.items()
        if value["approval"]["approved"]
    }
    def canonical_tie_break(value: dict[str, Any]) -> tuple[Any, ...]:
        config = value["configuration"]
        return (
            config["maximum_concurrent_positions"],
            config["maximum_total_open_risk_r"],
            config["maximum_daily_new_risk_r"],
            RANKING_METHODS.index(config["ranking_method"]),
        )

    best_risk_adjusted_id = (
        min(
            approved,
            key=lambda key: (
                -approved[key]["risk_adjusted_total_r_to_drawdown"],
                -approved[key]["current_costs"]["expectancy_r"],
                -approved[key]["current_costs"]["accepted_trades"],
                *canonical_tie_break(approved[key]),
                key,
            ),
        )
        if approved
        else None
    )
    lowest_drawdown_id = (
        min(
            approved,
            key=lambda key: (
                abs(approved[key]["current_costs"]["maximum_drawdown_r"]),
                -approved[key]["current_costs"]["expectancy_r"],
                -approved[key]["current_costs"]["accepted_trades"],
                *canonical_tie_break(approved[key]),
                key,
            ),
        )
        if approved
        else None
    )
    return {
        "experiment_status": "completed",
        "production_behavior_changed": False,
        "combination_count": len(results),
        "methodology": {
            "ledger": str(LEDGER_PATH.relative_to(ROOT)),
            "ledger_sha256": _sha256(LEDGER_PATH),
            "period": {
                "start": start.date().isoformat(),
                "end": end.date().isoformat(),
                "years": round(years, 4),
            },
            "chronology": (
                "Actual entry sessions, then partial exits, final exits, costs "
                "and slippage; same-session entries are admitted before exits."
            ),
            "initial_trade_risk": "Each frozen trade enters with 1R.",
            "ranking": {
                "highest_confidence": (
                    "Descending signal-time institutional score."
                ),
                "best_risk_reward": (
                    "Descending planned TP1 risk/reward; frozen plans are 2R, "
                    "so deterministic ticker order resolves equal values."
                ),
                "lowest_risk_percentage": (
                    "Ascending executable entry-to-stop distance as a "
                    "percentage of entry."
                ),
                "one_highest_ranked_per_sector": (
                    "Daily sector round-robin, highest confidence within each "
                    "sector; it ranks rather than imposes a sector cap."
                ),
            },
            "bootstrap_samples": BOOTSTRAP_SAMPLES,
            "bootstrap_seed": RANDOM_SEED,
            "material_drawdown_reduction_definition": (
                "At least 25% less severe than the unconstrained -33.4002R "
                "chronological drawdown."
            ),
            "double_costs": (
                "Frozen strategy rerun with doubled transaction costs and "
                "adverse slippage before applying identical constraints."
            ),
            "selection_tie_break": (
                "When point metrics are identical because constraints are "
                "redundant, prefer the lower configured position, open-risk, "
                "and daily-risk limits, then the first listed ranking method."
            ),
        },
        "baseline": {
            "accepted_trades": int(baseline["accepted_trades"]),
            "expectancy_r": baseline_expectancy,
            "profit_factor": float(baseline["profit_factor"]),
            "maximum_drawdown_r": baseline_drawdown,
            "maximum_concurrent_positions": int(
                baseline["portfolio_risk"]["maximum_concurrent_positions"]
            ),
            "maximum_open_risk_r": float(
                baseline["portfolio_risk"]["maximum_total_open_risk_r"]
            ),
        },
        "decision": {
            "approved_configuration_count": len(approved),
            "best_risk_adjusted_configuration": best_risk_adjusted_id,
            "lowest_drawdown_viable_configuration": lowest_drawdown_id,
            "production_limits_implemented": False,
        },
        "configurations": results,
    }


def _configuration_line(identifier: str, result: dict[str, Any]) -> str:
    config = result["configuration"]
    current = result["current_costs"]
    doubled = result["double_costs"]
    ci = current["bootstrap_expectancy_95_ci"]
    return (
        f"| `{identifier}` | {current['accepted_trades']} | "
        f"{current['rejected_trades']} | {current['expectancy_r']:.4f}R | "
        f"{current['profit_factor']:.4f} | "
        f"{current['maximum_drawdown_r']:.4f}R | "
        f"{current['maximum_concurrent_positions']} | "
        f"{current['maximum_open_risk_r']:.1f}R | "
        f"{doubled['expectancy_r']:.4f}R | "
        f"{ci[0]:.4f} to {ci[1]:.4f}R | "
        f"{'Yes' if result['approval']['approved'] else 'No'} |"
    )


def write_outputs(result: dict[str, Any]) -> None:
    RESULTS_PATH.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    decision = result["decision"]
    configurations_by_id = result["configurations"]
    best_id = decision["best_risk_adjusted_configuration"]
    low_id = decision["lowest_drawdown_viable_configuration"]
    baseline = result["baseline"]
    lines = [
        "# Portfolio Constraint Validation",
        "",
        "## Executive verdict",
        "",
    ]
    if best_id:
        best = configurations_by_id[best_id]
        lowest = configurations_by_id[low_id]
        best_config = best["configuration"]
        best_metrics = best["current_costs"]
        low_config = lowest["configuration"]
        low_metrics = lowest["current_costs"]
        lines.extend(
            [
                (
                    f"**{decision['approved_configuration_count']} of "
                    f"{result['combination_count']}** tested combinations pass "
                    "every predeclared approval criterion."
                ),
                "",
                (
                    "The best risk-adjusted configuration is "
                    f"**{best_config['maximum_concurrent_positions']} positions, "
                    f"{best_config['maximum_total_open_risk_r']:.0f}R open risk, "
                    f"{best_config['maximum_daily_new_risk_r']:.0f}R daily new "
                    f"risk, ranked by "
                    f"{best_config['ranking_method'].replace('_', ' ')}**. "
                    f"It produces {best_metrics['expectancy_r']:.4f}R "
                    f"expectancy and {best_metrics['maximum_drawdown_r']:.4f}R "
                    "maximum drawdown."
                ),
                "",
                (
                    "The lowest-drawdown viable configuration is "
                    f"**{low_config['maximum_concurrent_positions']} positions, "
                    f"{low_config['maximum_total_open_risk_r']:.0f}R open risk, "
                    f"{low_config['maximum_daily_new_risk_r']:.0f}R daily new "
                    f"risk, ranked by "
                    f"{low_config['ranking_method'].replace('_', ' ')}**, with "
                    f"{low_metrics['maximum_drawdown_r']:.4f}R drawdown and "
                    f"{low_metrics['expectancy_r']:.4f}R expectancy."
                ),
            ]
        )
    else:
        lines.append(
            "None of the 256 combinations passes every approval criterion."
        )
    lines.extend(
        [
            "",
            "No production limits were implemented.",
            "",
            "## Baseline",
            "",
            "| Metric | Unconstrained result |",
            "| --- | ---: |",
            f"| Accepted trades | {baseline['accepted_trades']} |",
            f"| Expectancy | {baseline['expectancy_r']:.4f}R |",
            f"| Profit factor | {baseline['profit_factor']:.4f} |",
            (
                f"| Corrected maximum drawdown | "
                f"{baseline['maximum_drawdown_r']:.4f}R |"
            ),
            (
                f"| Maximum concurrent positions | "
                f"{baseline['maximum_concurrent_positions']} |"
            ),
            (
                f"| Maximum open risk | "
                f"{baseline['maximum_open_risk_r']:.1f}R |"
            ),
            "",
            "## Selected configurations",
            "",
            "| Configuration | Accepted | Rejected | Expectancy | PF | Drawdown | Max positions | Max risk | Double-cost expectancy | Expectancy 95% CI | Approved |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    selected_ids = []
    for identifier in (best_id, low_id):
        if identifier and identifier not in selected_ids:
            selected_ids.append(identifier)
    for identifier in selected_ids:
        lines.append(
            _configuration_line(identifier, configurations_by_id[identifier])
        )
    lines.extend(
        [
            "",
            "## Approval criteria",
            "",
            "A combination passes only when expectancy is positive, profit "
            "factor exceeds 1, drawdown is at least 25% less severe than the "
            "baseline, observed open risk does not exceed 10R, observed "
            "positions do not exceed 10, double-cost expectancy and profit "
            "factor remain positive and above 1, and neither one sector nor one "
            "calendar year supplies 50% of gross positive R.",
            "",
            "## Complete combination results",
            "",
            "All 256 combinations, including win rate, average R, worst day, "
            "worst rolling five-day period, sector exposure, trades per year, "
            "bootstrap interval, rejection reasons, and double-cost performance "
            "are stored in the machine-readable artifact.",
            "",
            "## Methodology",
            "",
            "- The source is the frozen locked-holdout ledger. Signal generation, "
            "entry, stop, target, scoring, thresholds, and regime filtering are "
            "unchanged.",
            "- Admission is evaluated at the actual entry session. Entries occur "
            "before same-session partial or final exits.",
            "- Each new position contributes 1R of initial open risk. TP1 reduces "
            "remaining open risk in proportion to the remaining shares.",
            "- A material drawdown improvement means at least 25% less severe "
            "than the corrected -33.4002R baseline.",
            "- A configuration fails if one sector or calendar year contributes "
            "50% or more of gross positive R.",
            "- Bootstrap intervals use 5,000 deterministic resamples of trade R.",
            "- Double-cost results rerun the frozen execution with doubled costs "
            "and slippage before applying the same constraints.",
            "",
            "## Limitations",
            "",
            "These combinations reuse one historical holdout ledger and therefore "
            "constitute a multiple-comparison experiment. A selected constraint "
            "set requires a new locked validation before production use. Open "
            "risk is expressed in initial R, not a mark-to-market volatility or "
            "gap-risk model. Because every frozen plan has the same 2R TP1, the "
            "best-risk/reward ranking cannot distinguish signals and resolves "
            "ties deterministically by ticker; its lowest-drawdown result must "
            "not be interpreted as evidence that risk/reward ranking adds value.",
            "",
            (
                "Machine-readable results: "
                f"`{RESULTS_PATH.relative_to(ROOT)}`."
            ),
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    result = run_experiment()
    write_outputs(result)
    print(
        json.dumps(
            {
                "combination_count": result["combination_count"],
                **result["decision"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
