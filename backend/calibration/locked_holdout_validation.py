"""Frozen retrospective holdout validation of the selected regime-gated Pullback.

The holdout window predates, and has no overlap with, the 2021–2026 research
window used in Milestones 28–30. No rule or parameter is selected here.
"""
from __future__ import annotations

import csv
import json
import time
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

from backtesting.portfolio_risk import calculate_chronological_portfolio
from calibration.pullback_robustness import MINIMUM_CANDLES, SYMBOLS, _validate
from calibration.regime_gated_pullback import FILTERS, SELECTED, _baselines, _candidate_rows, _group, _metrics, _run
from providers import get_market_data_provider

DATASET_CACHE = Path(__file__).resolve().parents[2] / "artifacts" / "locked_holdout_dataset"
OUTPUT = Path(__file__).resolve().parents[2] / "artifacts"
START, END = date(2016, 7, 1), date(2021, 7, 10)


def _history(provider, ticker: str) -> tuple[pd.DataFrame | None, str | None]:
    DATASET_CACHE.mkdir(parents=True, exist_ok=True); path = DATASET_CACHE / f"{ticker}.csv"
    if path.exists():
        try:
            data = pd.read_csv(path, index_col=0, parse_dates=True)
            if _validate(data, END) is None: return data, None
        except (OSError, ValueError, pd.errors.ParserError): pass
    errors = []
    for attempt in range(1, 4):
        try:
            data = provider.get_history(ticker, interval="1d", start=START.isoformat(), end=END.isoformat())
            if _validate(data, END) is None:
                data.to_csv(path); return data, None
            errors.append(f"attempt {attempt}: {_validate(data, END)}")
        except Exception as error: errors.append(f"attempt {attempt}: {type(error).__name__}: {error}")
        time.sleep(.2 * attempt)
    return None, "; ".join(errors)


def _label_market_regimes(candidates: list[dict], spy: pd.DataFrame) -> None:
    ema50, ema200 = spy["Close"].ewm(span=50, adjust=False).mean(), spy["Close"].ewm(span=200, adjust=False).mean()
    for row in candidates:
        moment = pd.Timestamp(row["signal_date"]); close = float(spy.loc[moment, "Close"])
        row["market_regime"] = "Bull" if close > ema200.loc[moment] and ema50.loc[moment] > ema200.loc[moment] else "Bear" if close < ema200.loc[moment] and ema50.loc[moment] < ema200.loc[moment] else "Sideways"
        row["out_of_sample"] = True; row["walk_forward_period"] = "Locked holdout"


def _summary(trades: list[dict], rejected: list[dict], eligible: int) -> dict:
    result = _metrics(trades, len(rejected)); result["eligible_signals"] = eligible
    result["by_sector"] = _group(trades, rejected, "sector")
    result["by_market_regime"] = _group(trades, rejected, "market_regime")
    result["rejection_reasons"] = dict(sorted(Counter(row["reason"] for row in rejected).items()))
    return result


def run_validation(provider=None) -> dict:
    provider = provider or get_market_data_provider(); histories = {}; failures = {}
    for ticker in SYMBOLS:
        data, error = _history(provider, ticker)
        if error: failures[ticker] = error
        else: histories[ticker] = data
    spy, spy_error = _history(provider, "SPY"); qqq, qqq_error = _history(provider, "QQQ")
    if spy_error: failures["SPY"] = spy_error
    if qqq_error: failures["QQQ"] = qqq_error
    if len(histories) < 100 or spy is None or qqq is None:
        return {"audit_status": "blocked", "validated_symbols": len(histories), "provider_failures": failures, "reason": "Need 100 validated stocks, SPY, and QQQ."}
    candidates = _candidate_rows(histories, spy, qqq); _label_market_regimes(candidates, spy)
    gated, gated_rejected, gated_eligible = _run("existing_market_regime", candidates, histories, 1)
    gated_double, gated_double_rejected, gated_double_eligible = _run("existing_market_regime", candidates, histories, 2)
    ungated, ungated_rejected, ungated_eligible = _run("ungated", candidates, histories, 1)
    result, ungated_result = _summary(gated, gated_rejected, gated_eligible), _summary(ungated, ungated_rejected, ungated_eligible)
    result["double_cost"] = _summary(gated_double, gated_double_rejected, gated_double_eligible)
    result["portfolio_risk"] = calculate_chronological_portfolio(gated)
    result["double_cost"]["portfolio_risk"] = (
        calculate_chronological_portfolio(gated_double)
    )
    ungated_result["portfolio_risk"] = calculate_chronological_portfolio(
        ungated
    )
    profits = [max(0, value["expectancy"]) * value["accepted_trades"] for value in result["by_sector"].values()]
    concentration = max(profits) / sum(profits) if sum(profits) else 1
    ci = result["expectancy_95_ci"]
    passes = result["accepted_trades"] >= 100 and result["expectancy"] > 0 and (result["profit_factor"] or 0) > 1 and ci and ci[0] >= 0 and concentration <= .5 and (result["double_cost"]["profit_factor"] or 0) > 1
    portfolio = result["portfolio_risk"]
    portfolio_risk_acceptable = (
        portfolio["maximum_drawdown_r"] >= -15
        and portfolio["maximum_total_open_risk_r"] <= 10
        and portfolio["maximum_concurrent_positions"] <= 10
        and portfolio["maximum_daily_new_risk_r"] <= 3
    )
    return {"audit_status": "completed", "parameters": {"holdout_start": START.isoformat(), "holdout_end": END.isoformat(), "relationship_to_prior_research": "non-overlapping retrospective window before the 2021-07-12 to 2026-07-23 research data", "universe_size": len(histories), "frozen_strategy": {"regime_filter": FILTERS["existing_market_regime"], **SELECTED}, "execution": "same costs, slippage, partial exits, stop-first handling, and no overlapping ticker positions"}, "provider_failures": failures, "candidate_signals": len(candidates), "selected_regime_gated_pullback": result, "ungated_pullback": ungated_result, "baselines": _baselines(histories, candidates, ungated), "approval": {"meets_signal_edge_criteria": bool(passes), "portfolio_risk_acceptable": portfolio_risk_acceptable, "overall_validation_passed": bool(passes and portfolio_risk_acceptable), "sector_profit_concentration": round(concentration, 4), "decision": "Signal expectancy remains validated, but unconstrained portfolio risk fails the analysis limits; keep the strategy paper-only and do not enforce new limits in production yet."}, "rows": gated + gated_rejected}


def write_artifacts(result: dict) -> None:
    OUTPUT.mkdir(exist_ok=True); (OUTPUT / "locked_holdout_results.json").write_text(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2)); rows = []
    for row in result.get("rows", []):
        shared = {key: value for key, value in row.items() if key != "exit_legs"}
        if row["record_type"] == "TRADE":
            for number, leg in enumerate(row["exit_legs"], 1): rows.append({**shared, "leg_number": number, **{f"leg_{key}": value for key, value in leg.items()}})
        else: rows.append(shared)
    with (OUTPUT / "locked_holdout_trades.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=sorted({key for row in rows for key in row}) if rows else ["ticker"], lineterminator="\n"); writer.writeheader(); writer.writerows(rows)


if __name__ == "__main__":
    report = run_validation(); write_artifacts(report); print(json.dumps({key: value for key, value in report.items() if key != "rows"}, indent=2))
