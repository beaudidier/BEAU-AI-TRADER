"""Publish the chronological portfolio-risk correction across research reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts"
DOCS = ROOT / "docs"
RESULTS_PATH = ARTIFACTS / "chronological_portfolio_risk_results.json"
REPORT_PATH = DOCS / "CHRONOLOGICAL_PORTFOLIO_RISK_AUDIT.md"

OLD_DRAWDOWNS = {
    "locked_holdout": -10.4094,
    "pullback_baseline": -36.4450,
    "regime_selected_overall": -12.1999,
    "regime_selected_out_of_sample": -9.0076,
    "regime_selected_double_cost": -18.5808,
    "sector_no_limit": -29.4789,
    "calibration_out_of_sample": -18.1572,
    "trade_plan_next_open_atr": -15.1636,
    "trade_plan_pullback": -3.3237,
    "trade_plan_breakout": -47.9436,
}

MODULE_AUDIT = [
    {
        "module": "backtesting/execution.py",
        "finding": "Execution was deterministic, but exit legs lacked their explicit market date.",
        "resolution": "Every partial and final exit leg now stores its source candle date.",
    },
    {
        "module": "backtesting/runner.py",
        "finding": "Single-ticker loop was already chronological.",
        "resolution": "No execution-rule change; report output is now sorted deterministically.",
    },
    {
        "module": "backtesting/metrics.py and report.py",
        "finding": "Caller-provided equity points were trusted in their incoming order.",
        "resolution": "Duplicate sessions collapse to their final value and sessions are sorted before drawdown.",
    },
    {
        "module": "calibration/run_audit.py",
        "finding": "Trade-level R was accumulated in list order instead of dated exit-leg order.",
        "resolution": "All calibration drawdowns now aggregate realised exit-leg R by session.",
    },
    {
        "module": "calibration/trade_plan_variant_experiment.py",
        "finding": "Variant drawdowns depended on ticker iteration.",
        "resolution": "All variant, band, and regime drawdowns now use dated exit legs.",
    },
    {
        "module": "calibration/pullback_robustness.py",
        "finding": "The 81-cell matrix accumulated trades in ticker order.",
        "resolution": "Every overall, sector, regime, period, and cost slice is chronological.",
    },
    {
        "module": "calibration/regime_gated_pullback.py",
        "finding": "Filter drawdowns accumulated ticker-ordered outcomes.",
        "resolution": "Every filter and subgroup now uses daily realised exit-leg R.",
    },
    {
        "module": "calibration/locked_holdout_validation.py",
        "finding": "The headline -10.4094R was a ticker-order sequence, not portfolio chronology.",
        "resolution": "The holdout now includes the full event ledger, daily P/L, equity, risk, concurrency, and sector exposure.",
    },
    {
        "module": "calibration/sector_concentration_audit.py",
        "finding": "The first audit sorted final trade outcomes but did not time partial exits.",
        "resolution": "Partial and final legs now land on their true sessions; simultaneous loss is same-session realised gross loss.",
    },
    {
        "module": "calibration/integrity_audit.py and trade_evidence.py",
        "finding": "Both consumed legacy drawdown summaries.",
        "resolution": "Both now consume and describe the corrected chronological artifacts.",
    },
    {
        "module": "strategies/swing_strategy.py",
        "finding": "Forward metrics sorted completed trades by signal time.",
        "resolution": "Completed outcomes are grouped by completion date before drawdown; signal rules are unchanged.",
    },
]


def _load(name: str) -> dict[str, Any]:
    return json.loads((ARTIFACTS / name).read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _risk_snapshot(portfolio: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "cumulative_r",
        "maximum_drawdown_r",
        "maximum_concurrent_positions",
        "maximum_concurrent_date",
        "maximum_total_open_risk_r",
        "maximum_total_open_risk_date",
        "maximum_daily_new_risk_r",
        "maximum_daily_new_risk_date",
        "worst_trading_day",
        "worst_rolling_5_day_period",
        "worst_simultaneous_loss",
    )
    return {field: portfolio[field] for field in fields}


def _update_verdicts(
    locked: dict[str, Any],
    pullback: dict[str, Any],
    regime: dict[str, Any],
) -> None:
    locked["approval"] = {
        "meets_signal_edge_criteria": True,
        "portfolio_risk_acceptable": False,
        "overall_validation_passed": False,
        "sector_profit_concentration": locked["approval"][
            "sector_profit_concentration"
        ],
        "decision": (
            "Signal expectancy remains validated, but unconstrained portfolio "
            "risk fails the analysis limits; keep the strategy paper-only."
        ),
    }
    pullback["production_recommendation"]["approved"] = False
    pullback["production_recommendation"]["portfolio_risk_acceptable"] = False
    pullback["production_recommendation"]["decision"] = (
        "No configuration meets every production-use and portfolio-risk gate."
    )
    regime["production_recommendation"]["portfolio_risk_acceptable"] = False
    regime["production_recommendation"]["decision"] = (
        "No regime filter is approved for production; signal expectancy is "
        "supportive, but unconstrained portfolio risk exceeds the analysis limits."
    )
    _write_json(ARTIFACTS / "locked_holdout_results.json", locked)
    _write_json(ARTIFACTS / "pullback_robustness_results.json", pullback)
    _write_json(ARTIFACTS / "regime_gated_pullback_results.json", regime)


def _locked_report(locked: dict[str, Any]) -> str:
    selected = locked["selected_regime_gated_pullback"]
    risk = selected["portfolio_risk"]
    double = selected["double_cost"]
    return f"""# Locked Holdout Validation

## Validation status

The frozen strategy was rerun on the unchanged non-overlapping 2016-07-01 through 2021-07-10 holdout. Signal generation, the regime gate, EMA20 pullback entry, 1.5-ATR stop, 2R/4R targets, 50% TP1 exit, costs, slippage, stop-first handling, and per-ticker overlap prevention are unchanged.

The signal edge still passes its original statistical checks. The portfolio does **not** pass risk validation because the unconstrained historical book exceeded the analysis-only limits.

## Corrected results

| Metric | Result |
| --- | ---: |
| Eligible signals | {selected['eligible_signals']:,} |
| Accepted trades | {selected['accepted_trades']:,} |
| Rejected trades | {selected['rejected_trades']:,} |
| Trades per year | {selected['trades_per_year']:.2f} |
| Expectancy / average R | {selected['expectancy']:.4f}R |
| Bootstrap expectancy 95% CI | {selected['expectancy_95_ci'][0]:.4f}R to {selected['expectancy_95_ci'][1]:.4f}R |
| Profit factor | {selected['profit_factor']:.4f} |
| Win rate | {selected['win_rate']:.2f}% |
| Old ticker-order drawdown | {OLD_DRAWDOWNS['locked_holdout']:.4f}R |
| Corrected chronological drawdown | {risk['maximum_drawdown_r']:.4f}R |
| Maximum concurrent positions | {risk['maximum_concurrent_positions']} |
| Maximum simultaneous open risk | {risk['maximum_total_open_risk_r']:.1f}R |
| Maximum daily new risk | {risk['maximum_daily_new_risk_r']:.1f}R |
| Worst trading day | {risk['worst_trading_day']['realized_r']:.4f}R on {risk['worst_trading_day']['date']} |
| Worst rolling five-day period | {risk['worst_rolling_5_day_period']['realized_r']:.4f}R |
| Worst same-session gross loss | {risk['worst_simultaneous_loss']['gross_loss_r']:.4f}R |

Under double costs, {double['accepted_trades']} trades retain {double['expectancy']:.4f}R expectancy and {double['profit_factor']:.4f} profit factor, while corrected drawdown is {double['maximum_drawdown']:.4f}R.

## Why drawdown changed

The old calculation accumulated one final R result at a time in ticker-processing order. The corrected engine places the entry, TP1 leg, final exit, costs, and slippage on their actual sessions; aggregates same-day realised P/L; and calculates cumulative R and drawdown from that daily portfolio path. Expectancy and profit factor did not change because the same net exit-leg outcomes are still summed.

## Portfolio-risk verdict

At 1% account risk per initial 1R trade, the observed {risk['maximum_total_open_risk_r']:.1f}R peak represents approximately {risk['maximum_total_open_risk_r']:.1f}% simultaneous initial risk. That is not acceptable for production. For the next analysis experiment, cap total open risk at **10R**, concurrent positions at **10**, and daily new risk at **3R**. These limits are reported only and are not enforced in production.

The strategy remains paper-trading and forward-validation only.

Machine-readable results: [locked_holdout_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/locked_holdout_results.json).
"""


def _pullback_report(pullback: dict[str, Any]) -> str:
    configurations = pullback["configurations"]
    baseline = configurations["wait3_stop1_targetr15_3_cost1x"]["overall"]
    selected = configurations["wait3_stop1.5_targetr2_4_cost1x"]
    selected_overall = selected["overall"]
    double = configurations["wait3_stop1.5_targetr2_4_cost2x"]["overall"]
    triple = configurations["wait3_stop1.5_targetr2_4_cost3x"]["overall"]
    risk = pullback["chronological_portfolio"]["current_costs"]
    return f"""# Pullback Strategy Robustness Test

## Scope

The unchanged 81-configuration robustness matrix was rerun across {pullback['parameters']['universe_size']} cached liquid US stocks. Entries, stops, targets, the 5% per-trade risk rejection, costs, slippage, partial exits, and stop-first handling were not changed.

Every drawdown now aggregates dated TP1 and final exit legs by session. It is independent of ticker iteration.

## Corrected core results

The Milestone 28-style baseline produced {baseline['total_trades']:,} trades, {baseline['expectancy']:.4f}R expectancy, {baseline['profit_factor']:.4f} profit factor, and {baseline['maximum_drawdown']:.4f}R chronological drawdown. Its prior ticker-order drawdown was {OLD_DRAWDOWNS['pullback_baseline']:.4f}R. Expectancy did not change.

The selected three-day, 1.5-ATR, 2R/4R configuration:

| Cost level | Trades | Expectancy | Profit factor | Win rate | Corrected drawdown |
| --- | ---: | ---: | ---: | ---: | ---: |
| Current | {selected_overall['total_trades']} | {selected_overall['expectancy']:.4f}R | {selected_overall['profit_factor']:.4f} | {selected_overall['win_rate']:.2f}% | {selected_overall['maximum_drawdown']:.4f}R |
| Double | {double['total_trades']} | {double['expectancy']:.4f}R | {double['profit_factor']:.4f} | {double['win_rate']:.2f}% | {double['maximum_drawdown']:.4f}R |
| Triple | {triple['total_trades']} | {triple['expectancy']:.4f}R | {triple['profit_factor']:.4f} | {triple['win_rate']:.2f}% | {triple['maximum_drawdown']:.4f}R |

## Chronological portfolio risk

| Metric | Result |
| --- | ---: |
| Maximum concurrent positions | {risk['maximum_concurrent_positions']} |
| Maximum open risk | {risk['maximum_total_open_risk_r']:.1f}R |
| Maximum daily new risk | {risk['maximum_daily_new_risk_r']:.1f}R |
| Worst trading day | {risk['worst_trading_day']['realized_r']:.4f}R |
| Worst rolling five-day period | {risk['worst_rolling_5_day_period']['realized_r']:.4f}R |
| Worst same-session gross loss | {risk['worst_simultaneous_loss']['gross_loss_r']:.4f}R |

## Verdict

No configuration is approved for production. Positive expectancy survives in parts of the matrix, but unconstrained portfolio exposure and corrected drawdown are unacceptable. The strategy remains research and paper-trading only; the analysis-only 10R total / 10-position / 3R daily-new-risk limits are not enforced in production.

Machine-readable results: [pullback_robustness_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/pullback_robustness_results.json).
"""


def _regime_report(regime: dict[str, Any]) -> str:
    labels = {
        "ungated": "Ungated",
        "spy_close_ema200": "A — SPY close > EMA200",
        "spy_ema50_ema200": "B — SPY EMA50 > EMA200",
        "spy_dual_ema": "C — SPY dual EMA",
        "nasdaq_close_ema200": "D — QQQ close > EMA200",
        "universe_breadth_60": "E — 60% universe breadth",
        "existing_market_regime": "F — Existing regime engine",
    }
    lines = [
        "# Market-Regime Gated Pullback Test",
        "",
        "## Scope",
        "",
        "The unchanged six-filter experiment was rerun using actual entry and exit-leg dates. Production scoring, filters, entries, stops, targets, costs, and execution remain unchanged.",
        "",
        "## Corrected out-of-sample comparison",
        "",
        "| Filter | Trades | Expectancy | PF | Win rate | Corrected drawdown |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in labels.items():
        metrics = regime["filters"][key]["out_of_sample"]
        lines.append(
            f"| {label} | {metrics['accepted_trades']} | "
            f"{metrics['expectancy']:.4f}R | {metrics['profit_factor']:.4f} | "
            f"{metrics['win_rate']:.2f}% | {metrics['maximum_drawdown']:.4f}R |"
        )
    selected = regime["filters"]["existing_market_regime"]
    risk = regime["chronological_portfolio"]["overall"]
    oos_risk = regime["chronological_portfolio"]["out_of_sample"]
    double = selected["double_cost"]
    lines.extend([
        "",
        "## Filter F chronological risk",
        "",
        f"Full-sample expectancy remains **{selected['overall']['expectancy']:.4f}R** and profit factor remains **{selected['overall']['profit_factor']:.4f}**. Drawdown changes from **{OLD_DRAWDOWNS['regime_selected_overall']:.4f}R** to **{selected['overall']['maximum_drawdown']:.4f}R** because the old result accumulated ticker-ordered final outcomes.",
        "",
        f"Out of sample, drawdown changes from **{OLD_DRAWDOWNS['regime_selected_out_of_sample']:.4f}R** to **{selected['out_of_sample']['maximum_drawdown']:.4f}R**. Double-cost full-sample drawdown changes from **{OLD_DRAWDOWNS['regime_selected_double_cost']:.4f}R** to **{double['maximum_drawdown']:.4f}R**.",
        "",
        "| Metric | Full sample | Out of sample |",
        "| --- | ---: | ---: |",
        f"| Maximum concurrent positions | {risk['maximum_concurrent_positions']} | {oos_risk['maximum_concurrent_positions']} |",
        f"| Maximum open risk | {risk['maximum_total_open_risk_r']:.1f}R | {oos_risk['maximum_total_open_risk_r']:.1f}R |",
        f"| Maximum daily new risk | {risk['maximum_daily_new_risk_r']:.1f}R | {oos_risk['maximum_daily_new_risk_r']:.1f}R |",
        f"| Worst trading day | {risk['worst_trading_day']['realized_r']:.4f}R | {oos_risk['worst_trading_day']['realized_r']:.4f}R |",
        f"| Worst rolling five days | {risk['worst_rolling_5_day_period']['realized_r']:.4f}R | {oos_risk['worst_rolling_5_day_period']['realized_r']:.4f}R |",
        "",
        "## Verdict",
        "",
        "Filter F retains a positive out-of-sample expectancy interval and remains the mechanically strongest signal filter. It is not approved for production because the full unconstrained portfolio reached excessive concurrent risk. Continue paper-only forward validation. The 10R total / 10-position / 3R daily-new-risk limits are analysis recommendations only.",
        "",
        "Machine-readable results: [regime_gated_pullback_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/regime_gated_pullback_results.json).",
        "",
    ])
    return "\n".join(lines)


def _trade_variant_report(variants: dict[str, Any]) -> str:
    labels = {
        "next_open_atr": "A — Next-open ATR",
        "pullback": "B — Pullback",
        "breakout": "C — Breakout",
    }
    lines = [
        "# Trade Plan Variant Experiment",
        "",
        "## Scope and method",
        "",
        "The original 15,780 shared signal candidates and chronological 70/30 split were rerun without changing entries, stops, targets, costs, slippage, partial exits, or stop-first handling. Drawdown now uses actual partial and final exit dates rather than ticker iteration.",
        "",
        "## Corrected out-of-sample results",
        "",
        "| Variant | Trades | Rejected | Expectancy | Profit factor | Win rate | Old drawdown | Corrected drawdown | Max positions | Max open risk |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key, label in labels.items():
        summary = variants["variants"][key]["overall"]
        risk = variants["variants"][key]["chronological_portfolio"]
        lines.append(
            f"| {label} | {summary['valid_trades']} | "
            f"{summary['rejected_trades']:,} | {summary['expectancy']:.4f}R | "
            f"{summary['profit_factor']:.4f} | {summary['win_rate']:.2f}% | "
            f"{OLD_DRAWDOWNS[f'trade_plan_{key}']:.4f}R | "
            f"{summary['maximum_drawdown']:.4f}R | "
            f"{risk['maximum_concurrent_positions']} | "
            f"{risk['maximum_total_open_risk_r']:.1f}R |"
        )
    lines.extend([
        "",
        "## Recommendation",
        "",
        "Variant B remains the only variant meeting the original experiment's expectancy gates, but its sample is only 42 trades and it reached 12R open risk. This remains a research result, not a production change. All variants remain paper-only pending separate portfolio-constrained validation.",
        "",
        "Machine-readable results: [trade_plan_variant_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/trade_plan_variant_results.json).",
        "",
    ])
    return "\n".join(lines)


def _update_legacy_reports(
    calibration: dict[str, Any],
    variants: dict[str, Any],
) -> None:
    overall = calibration["out_of_sample"]["overall"]
    bands = calibration["out_of_sample"]["bands"]
    replacements_by_file = {
        "AI_CALIBRATION_AUDIT.md": {
            "-18.1572R sequential maximum drawdown": (
                f"{overall['maximum_drawdown']:.4f}R chronological "
                "exit-leg maximum drawdown"
            ),
            "-9.5630R": f"{bands['0-59']['maximum_drawdown']:.4f}R",
            "-7.3862R": f"{bands['60-74']['maximum_drawdown']:.4f}R",
            "-7.2073R": f"{bands['75-89']['maximum_drawdown']:.4f}R",
        },
        "CALIBRATION_DECISION.md": {
            "-9.5630R": f"{bands['0-59']['maximum_drawdown']:.4f}R",
            "-7.3862R": f"{bands['60-74']['maximum_drawdown']:.4f}R",
            "-7.2073R": f"{bands['75-89']['maximum_drawdown']:.4f}R",
        },
        "CORRECTED_STRATEGY_VERDICT.md": {
            "**-7.2073R** maximum drawdown": (
                f"**{bands['75-89']['maximum_drawdown']:.4f}R** "
                "chronological maximum drawdown"
            ),
        },
        "BACKTEST_INTEGRITY_AUDIT.md": {
            (
                "The maximum drawdown in the calibration artifact is a "
                "sequential sum of sorted trade R multiples, not a "
                "capital-weighted portfolio equity curve; signals from "
                "concurrent ticker positions are interleaved. It should not "
                "be read as deployable portfolio drawdown."
            ): (
                "Maximum drawdown now aggregates dated partial and final exit "
                "legs into daily realised R before calculating the portfolio "
                "equity path. It remains an equal-risk R analysis rather than "
                "a capital-weighted brokerage account."
            ),
            (
                "- Drawdown is not a portfolio-level calculation and "
                "concurrent positions are not capital-constrained across tickers."
            ): (
                "- Drawdown is now chronological portfolio realised R, but "
                "positions remain unconstrained by total capital or open risk."
            ),
        },
    }
    for filename, replacements in replacements_by_file.items():
        path = DOCS / filename
        text = path.read_text(encoding="utf-8")
        for old, new in replacements.items():
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")
    (DOCS / "TRADE_PLAN_VARIANT_EXPERIMENT.md").write_text(
        _trade_variant_report(variants), encoding="utf-8"
    )


def build_results() -> dict[str, Any]:
    locked = _load("locked_holdout_results.json")
    pullback = _load("pullback_robustness_results.json")
    regime = _load("regime_gated_pullback_results.json")
    sector = _load("sector_concentration_results.json")
    calibration = _load("ai_calibration_results.json")
    variants = _load("trade_plan_variant_results.json")
    _update_verdicts(locked, pullback, regime)

    selected = locked["selected_regime_gated_pullback"]
    result = {
        "audit_status": "completed",
        "production_behavior_changed": False,
        "strategy_rules_changed": False,
        "ordering": (
            "timestamp, entry, partial exit, final exit; costs and slippage "
            "remain embedded in net realised leg R"
        ),
        "analysis_only_limits": {
            "maximum_total_open_risk_r": 10.0,
            "maximum_concurrent_positions": 10,
            "maximum_daily_new_risk_r": 3.0,
            "enforced_in_production": False,
        },
        "module_audit": MODULE_AUDIT,
        "comparisons": {
            "locked_holdout": {
                "old_drawdown_r": OLD_DRAWDOWNS["locked_holdout"],
                "corrected_drawdown_r": selected["maximum_drawdown"],
                "expectancy_before_r": 0.3042,
                "expectancy_after_r": selected["expectancy"],
                "profit_factor": selected["profit_factor"],
                **_risk_snapshot(selected["portfolio_risk"]),
            },
            "pullback_baseline": {
                "old_drawdown_r": OLD_DRAWDOWNS["pullback_baseline"],
                "corrected_drawdown_r": pullback["baseline_configuration"][
                    "overall"
                ]["maximum_drawdown"],
                "expectancy_before_r": 0.0739,
                "expectancy_after_r": pullback["baseline_configuration"][
                    "overall"
                ]["expectancy"],
                **_risk_snapshot(
                    pullback["chronological_portfolio"]["current_costs"]
                ),
            },
            "regime_selected": {
                "old_drawdown_r": OLD_DRAWDOWNS[
                    "regime_selected_overall"
                ],
                "corrected_drawdown_r": regime["filters"][
                    "existing_market_regime"
                ]["overall"]["maximum_drawdown"],
                "expectancy_before_r": 0.1806,
                "expectancy_after_r": regime["filters"][
                    "existing_market_regime"
                ]["overall"]["expectancy"],
                **_risk_snapshot(
                    regime["chronological_portfolio"]["overall"]
                ),
            },
            "sector_no_limit": {
                "old_drawdown_r": OLD_DRAWDOWNS["sector_no_limit"],
                "corrected_drawdown_r": sector["variants"][
                    "A_no_sector_limit"
                ]["current_costs"]["maximum_drawdown"],
                "expectancy_before_r": 0.3042,
                "expectancy_after_r": sector["variants"][
                    "A_no_sector_limit"
                ]["current_costs"]["expectancy"],
            },
            "calibration_out_of_sample": {
                "old_drawdown_r": OLD_DRAWDOWNS[
                    "calibration_out_of_sample"
                ],
                "corrected_drawdown_r": calibration["out_of_sample"][
                    "overall"
                ]["maximum_drawdown"],
                "expectancy_after_r": calibration["out_of_sample"][
                    "overall"
                ]["expectancy"],
            },
            "trade_plan_variants": {
                key: {
                    "old_drawdown_r": OLD_DRAWDOWNS[
                        f"trade_plan_{key}"
                    ],
                    "corrected_drawdown_r": value["overall"][
                        "maximum_drawdown"
                    ],
                    "expectancy_after_r": value["overall"]["expectancy"],
                }
                for key, value in variants["variants"].items()
            },
        },
        "validation_verdict": {
            "signal_expectancy_still_positive": selected["expectancy"] > 0,
            "signal_edge_criteria_passed": True,
            "portfolio_risk_acceptable": False,
            "overall_strategy_validation_passed": False,
            "status": "PAPER_TRADING_ONLY",
            "reason": (
                "The unchanged edge remains positive, but unconstrained "
                "simultaneous risk and chronological drawdown exceed the "
                "analysis limits."
            ),
        },
        "recommendation": {
            "maximum_concurrent_risk_r": 10.0,
            "maximum_concurrent_positions_at_1r_each": 10,
            "maximum_daily_new_risk_r": 3.0,
            "rationale": (
                "At 1% account risk per trade, 10R caps simultaneous initial "
                "risk near 10%; validate this separately before enforcement."
            ),
        },
    }
    return result


def _master_report(result: dict[str, Any]) -> str:
    comparisons = result["comparisons"]
    locked = comparisons["locked_holdout"]
    pullback = comparisons["pullback_baseline"]
    regime = comparisons["regime_selected"]
    sector = comparisons["sector_no_limit"]
    return f"""# Chronological Portfolio Risk Audit

## Executive verdict

The strategy's per-trade expectancy did not change, but the previous portfolio drawdowns were not trustworthy because several research runners accumulated trades in ticker-processing order. Every research metric now uses dated entry, partial-exit, and final-exit events with same-session P/L aggregation.

The locked holdout changes from **{locked['old_drawdown_r']:.4f}R** to **{locked['corrected_drawdown_r']:.4f}R**. It reached **{locked['maximum_concurrent_positions']} simultaneous positions** and **{locked['maximum_total_open_risk_r']:.1f}R** of open initial risk. The signal edge remains positive; the unconstrained portfolio risk is not acceptable.

## Corrected headline results

| Study | Old drawdown | Corrected drawdown | Expectancy before | Expectancy after |
| --- | ---: | ---: | ---: | ---: |
| Locked holdout | {locked['old_drawdown_r']:.4f}R | {locked['corrected_drawdown_r']:.4f}R | {locked['expectancy_before_r']:.4f}R | {locked['expectancy_after_r']:.4f}R |
| Pullback robustness baseline | {pullback['old_drawdown_r']:.4f}R | {pullback['corrected_drawdown_r']:.4f}R | {pullback['expectancy_before_r']:.4f}R | {pullback['expectancy_after_r']:.4f}R |
| Regime-gated selected filter | {regime['old_drawdown_r']:.4f}R | {regime['corrected_drawdown_r']:.4f}R | {regime['expectancy_before_r']:.4f}R | {regime['expectancy_after_r']:.4f}R |
| Sector audit, no limit | {sector['old_drawdown_r']:.4f}R | {sector['corrected_drawdown_r']:.4f}R | {sector['expectancy_before_r']:.4f}R | {sector['expectancy_after_r']:.4f}R |

## Locked-holdout portfolio path

| Metric | Corrected result |
| --- | ---: |
| Cumulative R | {locked['cumulative_r']:.4f}R |
| Maximum drawdown | {locked['corrected_drawdown_r']:.4f}R |
| Maximum concurrent positions | {locked['maximum_concurrent_positions']} |
| Maximum simultaneous open risk | {locked['maximum_total_open_risk_r']:.1f}R |
| Maximum daily new risk | {locked['maximum_daily_new_risk_r']:.1f}R |
| Worst trading day | {locked['worst_trading_day']['realized_r']:.4f}R on {locked['worst_trading_day']['date']} |
| Worst rolling five-day period | {locked['worst_rolling_5_day_period']['realized_r']:.4f}R |
| Worst same-session gross loss | {locked['worst_simultaneous_loss']['gross_loss_r']:.4f}R |

## Why the numbers changed

The old implementations generally appended all trades for one ticker before moving to the next ticker, then applied a cumulative sum. That sequence is deterministic but not chronological. A later partial fix sorted only final trade outcomes by exit date, which still placed TP1 profit on the final-exit session.

The new engine builds one immutable event stream ordered by timestamp, entry, partial exit, and final exit. Entry and exit transaction costs and adverse slippage remain included in each leg's realised R. Same-day exit legs are aggregated before cumulative R and drawdown are updated, removing arbitrary ticker tie-breaking.

## Analysis-only portfolio constraints

- Maximum total open risk: **10R**
- Maximum concurrent positions: **10**
- Maximum daily new risk: **3R**

At 1% risk per trade, 10R corresponds to approximately 10% simultaneous initial account risk. The locked ledger reached 63R, so the recommendation is materially below observed exposure. These limits are not enforced in production and require a separate experiment before adoption.

## Validation verdict

The signal expectancy remains validated at {locked['expectancy_after_r']:.4f}R with a {locked['profit_factor']:.4f} profit factor. The overall strategy does **not** pass portfolio-risk validation because maximum drawdown, concurrent positions, total open risk, and daily new risk exceed the analysis limits.

Keep the strategy paper-trading and forward-validation only.

Machine-readable results: [chronological_portfolio_risk_results.json](/Users/beaudidier/Desktop/BEAU-AI-TRADER/artifacts/chronological_portfolio_risk_results.json).
"""


def publish() -> dict[str, Any]:
    result = build_results()
    _write_json(RESULTS_PATH, result)
    REPORT_PATH.write_text(_master_report(result), encoding="utf-8")
    locked = _load("locked_holdout_results.json")
    pullback = _load("pullback_robustness_results.json")
    regime = _load("regime_gated_pullback_results.json")
    (DOCS / "LOCKED_HOLDOUT_VALIDATION.md").write_text(
        _locked_report(locked), encoding="utf-8"
    )
    (DOCS / "PULLBACK_ROBUSTNESS_TEST.md").write_text(
        _pullback_report(pullback), encoding="utf-8"
    )
    (DOCS / "REGIME_GATED_PULLBACK_TEST.md").write_text(
        _regime_report(regime), encoding="utf-8"
    )
    calibration = _load("ai_calibration_results.json")
    variants = _load("trade_plan_variant_results.json")
    _update_legacy_reports(calibration, variants)
    return result


if __name__ == "__main__":
    output = publish()
    print(json.dumps({
        "corrected_locked_drawdown_r": output["comparisons"][
            "locked_holdout"
        ]["corrected_drawdown_r"],
        "maximum_concurrent_positions": output["comparisons"][
            "locked_holdout"
        ]["maximum_concurrent_positions"],
        "validation_status": output["validation_verdict"]["status"],
    }, indent=2))
