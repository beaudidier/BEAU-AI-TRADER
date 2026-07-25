"""Deterministic chronological portfolio-risk accounting.

The engine is analysis-only. It consumes already executed trades and their
net-of-cost exit legs; it never changes signal, entry, stop, target, sizing, or
production admission behavior.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

import pandas as pd


ENTRY_PRIORITY = 0
PARTIAL_EXIT_PRIORITY = 1
FINAL_EXIT_PRIORITY = 2


@dataclass(frozen=True)
class PortfolioRiskLimits:
    """Analysis thresholds expressed in units of initial trade risk."""

    maximum_total_open_risk_r: float = 10.0
    maximum_concurrent_positions: int = 10
    maximum_daily_new_risk_r: float = 3.0


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _timestamp(value: Any) -> pd.Timestamp:
    result = pd.Timestamp(value)
    if result.tzinfo is not None:
        result = result.tz_convert("UTC").tz_localize(None)
    return result.normalize()


def _trade_id(trade: dict[str, Any], index: int) -> str:
    return str(
        trade.get("trade_id")
        or f"{trade.get('ticker', 'UNKNOWN')}-{trade.get('entry_date')}-{index}"
    )


def _leg_date(leg: dict[str, Any], trade: dict[str, Any], is_final: bool) -> Any:
    value = leg.get("exit_date") or leg.get("date")
    if value is not None:
        return value
    if is_final:
        return trade.get("exit_date") or trade.get("completed_at")
    raise ValueError(
        f"Partial exit date is missing for trade {trade.get('trade_id')}."
    )


def _leg_r_multiple(
    leg: dict[str, Any],
    trade: dict[str, Any],
    *,
    only_leg: bool,
) -> float:
    if leg.get("r_multiple") is not None:
        return _finite(leg["r_multiple"])
    if leg.get("pnl") is not None:
        initial_risk = _finite(
            trade.get("initial_risk")
            or trade.get("risk_amount")
            or (
                (
                    _finite(trade.get("entry_price") or trade.get("entry"))
                    - _finite(trade.get("stop_loss"))
                )
                * _finite(trade.get("shares"), 1.0)
            )
        )
        if initial_risk > 0:
            return _finite(leg["pnl"]) / initial_risk
    if only_leg:
        return _finite(
            trade.get("r_multiple", trade.get("realized_rr", 0.0))
        )
    raise ValueError(
        f"Exit-leg R is missing for trade {trade.get('trade_id')}."
    )


def build_portfolio_events(
    trades: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build immutable entry/partial/final events in deterministic order."""

    events: list[dict[str, Any]] = []
    for trade_index, trade in enumerate(trades):
        trade_id = _trade_id(trade, trade_index)
        entry_value = trade.get("entry_date") or trade.get("entry_timestamp")
        if entry_value is None:
            raise ValueError(f"Entry timestamp is missing for {trade_id}.")
        ticker = str(trade.get("ticker") or "UNKNOWN")
        sector = str(trade.get("sector") or "Unknown")
        legs = list(trade.get("exit_legs") or [])
        if not legs:
            legs = [{
                "leg": str(trade.get("exit_reason") or "FINAL"),
                "exit_date": (
                    trade.get("exit_date") or trade.get("completed_at")
                ),
                "shares": trade.get("shares", 1),
                "r_multiple": trade.get(
                    "r_multiple", trade.get("realized_rr", 0.0)
                ),
            }]

        leg_shares = [_finite(leg.get("shares"), 0.0) for leg in legs]
        initial_shares = _finite(trade.get("shares"), sum(leg_shares))
        if initial_shares <= 0:
            initial_shares = sum(leg_shares) or 1.0
        initial_risk_r = _finite(trade.get("initial_risk_r"), 1.0)
        if initial_risk_r <= 0:
            raise ValueError(f"Initial risk is invalid for {trade_id}.")

        events.append({
            "timestamp": _timestamp(entry_value),
            "priority": ENTRY_PRIORITY,
            "event_type": "entry",
            "trade_id": trade_id,
            "ticker": ticker,
            "sector": sector,
            "realized_r": 0.0,
            "initial_risk_r": initial_risk_r,
            "remaining_fraction": 1.0,
            "entry_transaction_cost": _finite(
                trade.get("entry_transaction_cost")
            ),
            "slippage_is_embedded": True,
        })

        remaining_shares = initial_shares
        for leg_index, leg in enumerate(legs):
            is_final = leg_index == len(legs) - 1
            quantity = _finite(leg.get("shares"), 0.0)
            if quantity <= 0:
                quantity = remaining_shares if is_final else 0.0
            remaining_shares = max(0.0, remaining_shares - quantity)
            events.append({
                "timestamp": _timestamp(_leg_date(leg, trade, is_final)),
                "priority": (
                    FINAL_EXIT_PRIORITY if is_final else PARTIAL_EXIT_PRIORITY
                ),
                "event_type": "final_exit" if is_final else "partial_exit",
                "trade_id": trade_id,
                "ticker": ticker,
                "sector": sector,
                "leg": str(leg.get("leg") or leg.get("reason") or "EXIT"),
                "realized_r": _leg_r_multiple(
                    leg, trade, only_leg=len(legs) == 1
                ),
                "remaining_fraction": (
                    remaining_shares / initial_shares
                    if initial_shares
                    else 0.0
                ),
                "allocated_entry_cost": _finite(
                    leg.get("allocated_entry_cost")
                ),
                "exit_transaction_cost": _finite(
                    leg.get("exit_transaction_cost")
                ),
                "slippage_is_embedded": True,
            })

    return sorted(
        events,
        key=lambda event: (
            event["timestamp"],
            event["priority"],
            event["trade_id"],
            event.get("leg", ""),
        ),
    )


def _drawdown(equity_values: list[float]) -> float:
    peak = 0.0
    maximum_drawdown = 0.0
    for value in equity_values:
        peak = max(peak, value)
        maximum_drawdown = min(maximum_drawdown, value - peak)
    return maximum_drawdown


def chronological_drawdown_r(trades: Iterable[dict[str, Any]]) -> float:
    """Return realised-R drawdown after aggregating every dated exit leg."""

    daily_realized: dict[pd.Timestamp, float] = defaultdict(float)
    for event in build_portfolio_events(trades):
        if event["event_type"] != "entry":
            daily_realized[event["timestamp"]] += event["realized_r"]
    cumulative = 0.0
    equity_values = []
    for timestamp in sorted(daily_realized):
        cumulative += daily_realized[timestamp]
        equity_values.append(cumulative)
    return round(_drawdown(equity_values), 4)


def _rolling_five_day(daily: list[dict[str, Any]]) -> tuple[str | None, str | None, float]:
    if not daily:
        return None, None, 0.0
    values = pd.Series(
        {pd.Timestamp(row["date"]): row["realized_r"] for row in daily},
        dtype=float,
    )
    calendar = pd.bdate_range(values.index.min(), values.index.max())
    window = (
        values.reindex(calendar, fill_value=0.0)
        .rolling(5, min_periods=1)
        .sum()
    )
    end = window.idxmin()
    start = end - pd.offsets.BDay(4)
    return start.date().isoformat(), end.date().isoformat(), float(window.loc[end])


def calculate_chronological_portfolio(
    trades: Iterable[dict[str, Any]],
    *,
    limits: PortfolioRiskLimits | None = None,
    include_series: bool = True,
) -> dict[str, Any]:
    """Calculate portfolio metrics from chronologically ordered fill events."""

    source_trades = list(trades)
    analysis_limits = limits or PortfolioRiskLimits()
    if not source_trades:
        empty = {
            "event_count": 0,
            "trade_count": 0,
            "cumulative_r": 0.0,
            "maximum_drawdown_r": 0.0,
            "maximum_concurrent_positions": 0,
            "maximum_concurrent_date": None,
            "maximum_total_open_risk_r": 0.0,
            "maximum_total_open_risk_date": None,
            "maximum_daily_new_risk_r": 0.0,
            "maximum_daily_new_risk_date": None,
            "worst_trading_day": {"date": None, "realized_r": 0.0},
            "worst_rolling_5_day_period": {
                "start": None, "end": None, "realized_r": 0.0
            },
            "worst_simultaneous_loss": {
                "date": None, "gross_loss_r": 0.0
            },
            "analysis_only_constraints": {
                "limits": {
                    "maximum_total_open_risk_r": (
                        analysis_limits.maximum_total_open_risk_r
                    ),
                    "maximum_concurrent_positions": (
                        analysis_limits.maximum_concurrent_positions
                    ),
                    "maximum_daily_new_risk_r": (
                        analysis_limits.maximum_daily_new_risk_r
                    ),
                },
                "violations": {
                    "total_open_risk_days": 0,
                    "concurrent_position_days": 0,
                    "daily_new_risk_days": 0,
                },
                "enforced": False,
            },
            "ordering": (
                "timestamp, entry, partial exit, final exit; costs and adverse "
                "slippage are embedded in each realised exit-leg R"
            ),
        }
        if include_series:
            empty.update({
                "events": [],
                "daily_pnl": [],
                "equity_curve": [],
                "concurrent_exposure": [],
                "sector_exposure": [],
            })
        return empty

    events = build_portfolio_events(source_trades)
    active: dict[str, dict[str, Any]] = {}
    daily_realized: dict[pd.Timestamp, float] = defaultdict(float)
    daily_gross_loss: dict[pd.Timestamp, float] = defaultdict(float)
    daily_new_risk: dict[pd.Timestamp, float] = defaultdict(float)
    daily_snapshots: dict[pd.Timestamp, dict[str, Any]] = {}
    maximum_positions = 0
    maximum_positions_date: pd.Timestamp | None = None
    maximum_open_risk = 0.0
    maximum_open_risk_date: pd.Timestamp | None = None

    events_by_day: dict[pd.Timestamp, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        events_by_day[event["timestamp"]].append(event)
    for timestamp in sorted(events_by_day):
        ordered = sorted(
            events_by_day[timestamp],
            key=lambda event: (
                event["priority"],
                event["trade_id"],
                event.get("leg", ""),
            ),
        )
        for event in ordered:
            trade_id = str(event["trade_id"])
            if event["event_type"] == "entry":
                if trade_id in active:
                    raise ValueError(f"Duplicate entry event for {trade_id}.")
                active[trade_id] = {
                    "ticker": event["ticker"],
                    "sector": event["sector"],
                    "open_risk_r": event["initial_risk_r"],
                    "initial_risk_r": event["initial_risk_r"],
                }
                daily_new_risk[timestamp] += event["initial_risk_r"]
            else:
                position = active.get(trade_id)
                if position is None:
                    raise ValueError(f"Exit precedes entry for {trade_id}.")
                daily_realized[timestamp] += event["realized_r"]
                daily_gross_loss[timestamp] += min(0.0, event["realized_r"])
                if event["event_type"] == "final_exit":
                    del active[trade_id]
                else:
                    position["open_risk_r"] = (
                        position["initial_risk_r"]
                        * event["remaining_fraction"]
                    )

            current_positions = len(active)
            current_open_risk = sum(
                position["open_risk_r"] for position in active.values()
            )
            if current_positions > maximum_positions:
                maximum_positions = current_positions
                maximum_positions_date = timestamp
            if current_open_risk > maximum_open_risk:
                maximum_open_risk = current_open_risk
                maximum_open_risk_date = timestamp

        sector_counts = Counter(
            str(position["sector"]) for position in active.values()
        )
        sector_risk = defaultdict(float)
        for position in active.values():
            sector_risk[str(position["sector"])] += position["open_risk_r"]
        daily_snapshots[timestamp] = {
            "open_positions": len(active),
            "open_risk_r": sum(
                position["open_risk_r"] for position in active.values()
            ),
            "sector_positions": dict(sorted(sector_counts.items())),
            "sector_open_risk_r": {
                sector: round(value, 6)
                for sector, value in sorted(sector_risk.items())
            },
        }

    event_dates = sorted({
        *daily_realized,
        *daily_new_risk,
        *daily_snapshots,
    })
    calendar = pd.bdate_range(min(event_dates), max(event_dates))
    cumulative_r = 0.0
    daily: list[dict[str, Any]] = []
    last_snapshot = {
        "open_positions": 0,
        "open_risk_r": 0.0,
        "sector_positions": {},
        "sector_open_risk_r": {},
    }
    for day in calendar:
        if day in daily_snapshots:
            last_snapshot = daily_snapshots[day]
        realized_r = daily_realized[day]
        cumulative_r += realized_r
        daily.append({
            "date": day.date().isoformat(),
            "realized_r": round(realized_r, 6),
            "gross_loss_r": round(daily_gross_loss[day], 6),
            "cumulative_r": round(cumulative_r, 6),
            "new_risk_r": round(daily_new_risk[day], 6),
            **last_snapshot,
        })

    equity_values = [float(row["cumulative_r"]) for row in daily]
    worst_day = min(daily, key=lambda row: (row["realized_r"], row["date"]))
    worst_simultaneous = min(
        daily, key=lambda row: (row["gross_loss_r"], row["date"])
    )
    rolling_start, rolling_end, rolling_r = _rolling_five_day(daily)
    total_risk_violation_days = sum(
        row["open_risk_r"] > analysis_limits.maximum_total_open_risk_r
        for row in daily
    )
    position_violation_days = sum(
        row["open_positions"] > analysis_limits.maximum_concurrent_positions
        for row in daily
    )
    new_risk_violation_days = sum(
        row["new_risk_r"] > analysis_limits.maximum_daily_new_risk_r
        for row in daily
    )
    result = {
        "event_count": len(events),
        "trade_count": len(source_trades),
        "cumulative_r": round(cumulative_r, 4),
        "maximum_drawdown_r": round(_drawdown(equity_values), 4),
        "maximum_concurrent_positions": maximum_positions,
        "maximum_concurrent_date": (
            maximum_positions_date.date().isoformat()
            if maximum_positions_date is not None
            else None
        ),
        "maximum_total_open_risk_r": round(maximum_open_risk, 4),
        "maximum_total_open_risk_date": (
            maximum_open_risk_date.date().isoformat()
            if maximum_open_risk_date is not None
            else None
        ),
        "maximum_daily_new_risk_r": round(
            max(daily_new_risk.values(), default=0.0), 4
        ),
        "maximum_daily_new_risk_date": (
            min(
                day
                for day, value in daily_new_risk.items()
                if value == max(daily_new_risk.values(), default=0.0)
            ).date().isoformat()
            if daily_new_risk
            else None
        ),
        "worst_trading_day": {
            "date": worst_day["date"],
            "realized_r": round(float(worst_day["realized_r"]), 4),
        },
        "worst_rolling_5_day_period": {
            "start": rolling_start,
            "end": rolling_end,
            "realized_r": round(rolling_r, 4),
        },
        "worst_simultaneous_loss": {
            "date": worst_simultaneous["date"],
            "gross_loss_r": round(
                float(worst_simultaneous["gross_loss_r"]), 4
            ),
        },
        "analysis_only_constraints": {
            "limits": {
                "maximum_total_open_risk_r": (
                    analysis_limits.maximum_total_open_risk_r
                ),
                "maximum_concurrent_positions": (
                    analysis_limits.maximum_concurrent_positions
                ),
                "maximum_daily_new_risk_r": (
                    analysis_limits.maximum_daily_new_risk_r
                ),
            },
            "violations": {
                "total_open_risk_days": total_risk_violation_days,
                "concurrent_position_days": position_violation_days,
                "daily_new_risk_days": new_risk_violation_days,
            },
            "enforced": False,
        },
        "ordering": (
            "timestamp, entry, partial exit, final exit; costs and adverse "
            "slippage are embedded in each realised exit-leg R"
        ),
    }
    if include_series:
        result.update({
            "events": [
                {
                    **event,
                    "timestamp": event["timestamp"].date().isoformat(),
                    "realized_r": round(_finite(event["realized_r"]), 6),
                }
                for event in events
            ],
            "daily_pnl": [
                {
                    "date": row["date"],
                    "realized_r": row["realized_r"],
                    "gross_loss_r": row["gross_loss_r"],
                    "new_risk_r": row["new_risk_r"],
                }
                for row in daily
            ],
            "equity_curve": [
                {"date": row["date"], "cumulative_r": row["cumulative_r"]}
                for row in daily
            ],
            "concurrent_exposure": [
                {
                    "date": row["date"],
                    "open_positions": row["open_positions"],
                    "open_risk_r": round(row["open_risk_r"], 6),
                }
                for row in daily
            ],
            "sector_exposure": [
                {
                    "date": row["date"],
                    "sector_positions": row["sector_positions"],
                    "sector_open_risk_r": row["sector_open_risk_r"],
                }
                for row in daily
            ],
        })
    return result
