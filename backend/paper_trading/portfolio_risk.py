"""Validated portfolio limits shared by paper and forward validation.

The module is deterministic and provider-independent. It does not alter trade
plans; it only measures current simulated exposure and decides whether another
paper risk unit can be admitted.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo

MAXIMUM_CONCURRENT_POSITIONS = 10
MAXIMUM_TOTAL_OPEN_RISK_R = 10.0
MAXIMUM_DAILY_NEW_RISK_R = 1.0
ACCOUNT_RISK_PERCENT = 1.0
RISK_TIMEZONE = ZoneInfo("America/New_York")


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _moment(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        result = value
    else:
        try:
            result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def account_risk_unit(account: dict[str, Any]) -> float:
    initial_balance = _number(account.get("initial_balance"), 10_000.0)
    return max(0.01, initial_balance * ACCOUNT_RISK_PERCENT / 100)


def trade_risk_amount(trade: dict[str, Any]) -> float:
    stored = _number(trade.get("initial_risk_amount"), -1)
    if stored >= 0:
        return stored
    entry = _number(trade.get("entry_price"))
    stop = _number(trade.get("stop_loss"))
    quantity = _number(trade.get("quantity"))
    return max(0.0, (entry - stop) * quantity)


def trade_initial_risk_r(
    trade: dict[str, Any], risk_unit_currency: float
) -> float:
    stored = _number(trade.get("initial_risk_r"), -1)
    if stored >= 0:
        return stored
    return (
        trade_risk_amount(trade) / risk_unit_currency
        if risk_unit_currency > 0
        else 0.0
    )


def trade_remaining_risk_r(
    trade: dict[str, Any], risk_unit_currency: float
) -> float:
    stored = _number(trade.get("remaining_risk_r"), -1)
    if stored >= 0:
        return stored
    fraction = min(1.0, max(0.0, _number(trade.get("remaining_fraction"), 1)))
    return trade_initial_risk_r(trade, risk_unit_currency) * fraction


def risk_day(value: Any) -> str | None:
    moment = _moment(value)
    return moment.astimezone(RISK_TIMEZONE).date().isoformat() if moment else None


def next_risk_reset(now: datetime | None = None) -> str:
    moment = (now or datetime.now(timezone.utc)).astimezone(RISK_TIMEZONE)
    tomorrow = (moment + timedelta(days=1)).date()
    reset = datetime.combine(tomorrow, datetime.min.time(), RISK_TIMEZONE)
    return reset.astimezone(timezone.utc).isoformat()


def _equity_metrics(
    account: dict[str, Any],
    trades: list[dict[str, Any]],
    portfolio_balance: float | None,
) -> tuple[float, float, float]:
    initial = _number(account.get("initial_balance"), 10_000.0)
    equity = initial
    peak = initial
    for trade in sorted(
        (item for item in trades if str(item.get("status")).upper() == "CLOSED"),
        key=lambda item: (
            str(item.get("closed_at") or ""),
            str(item.get("id") or ""),
        ),
    ):
        equity += _number(trade.get("realized_pnl"))
        peak = max(peak, equity)
    current = _number(portfolio_balance, equity)
    peak = max(peak, current)
    return current, peak, current - peak


def build_portfolio_risk_dashboard(
    account: dict[str, Any],
    trades: Iterable[dict[str, Any]],
    *,
    now: datetime | None = None,
    portfolio_balance: float | None = None,
) -> dict[str, Any]:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    rows = list(trades)
    risk_unit = account_risk_unit(account)
    open_trades = [
        trade for trade in rows if str(trade.get("status")).upper() == "OPEN"
    ]
    open_risk_r = sum(
        trade_remaining_risk_r(trade, risk_unit) for trade in open_trades
    )
    current_day = risk_day(moment)
    daily_new_risk = sum(
        trade_initial_risk_r(trade, risk_unit)
        for trade in rows
        if risk_day(trade.get("risk_admitted_at") or trade.get("opened_at"))
        == current_day
    )
    open_risk_currency = open_risk_r * risk_unit
    current_equity, peak_equity, current_drawdown = _equity_metrics(
        account, rows, portfolio_balance
    )
    capacity_reasons = []
    if len(open_trades) >= MAXIMUM_CONCURRENT_POSITIONS:
        capacity_reasons.append(
            f"{MAXIMUM_CONCURRENT_POSITIONS} paper positions are already open."
        )
    if open_risk_r >= MAXIMUM_TOTAL_OPEN_RISK_R - 1e-9:
        capacity_reasons.append(
            f"Open paper risk has reached {MAXIMUM_TOTAL_OPEN_RISK_R:g}R."
        )
    if daily_new_risk >= MAXIMUM_DAILY_NEW_RISK_R - 1e-9:
        capacity_reasons.append(
            f"Today's {MAXIMUM_DAILY_NEW_RISK_R:g}R new-risk budget is used."
        )
    utilization = max(
        len(open_trades) / MAXIMUM_CONCURRENT_POSITIONS,
        open_risk_r / MAXIMUM_TOTAL_OPEN_RISK_R,
        daily_new_risk / MAXIMUM_DAILY_NEW_RISK_R,
    )
    status = (
        "BLOCKED"
        if capacity_reasons
        else "CAUTION"
        if utilization >= 0.8
        else "NORMAL"
    )
    limiting_positions = [
        {
            "id": str(trade.get("id") or ""),
            "ticker": str(trade.get("ticker") or "").upper(),
            "remaining_risk_r": round(
                trade_remaining_risk_r(trade, risk_unit), 4
            ),
        }
        for trade in sorted(
            open_trades,
            key=lambda item: (
                -trade_remaining_risk_r(item, risk_unit),
                str(item.get("opened_at") or ""),
                str(item.get("ticker") or ""),
            ),
        )
    ]
    return {
        "limits": {
            "maximum_concurrent_positions": MAXIMUM_CONCURRENT_POSITIONS,
            "maximum_total_open_risk_r": MAXIMUM_TOTAL_OPEN_RISK_R,
            "maximum_daily_new_risk_r": MAXIMUM_DAILY_NEW_RISK_R,
            "ranking": "signal-time confidence",
        },
        "open_positions": len(open_trades),
        "open_risk_r": round(open_risk_r, 4),
        "open_risk_currency": round(open_risk_currency, 2),
        "risk_unit_currency": round(risk_unit, 2),
        "daily_new_risk_used_r": round(daily_new_risk, 4),
        "remaining_daily_risk_budget_r": round(
            max(0.0, MAXIMUM_DAILY_NEW_RISK_R - daily_new_risk), 4
        ),
        "current_equity": round(current_equity, 2),
        "peak_equity": round(peak_equity, 2),
        "current_drawdown": round(current_drawdown, 2),
        "current_drawdown_r": round(current_drawdown / risk_unit, 4),
        "risk_status": status,
        "blocked_reasons": capacity_reasons,
        "capacity_resets_at": next_risk_reset(moment),
        "limiting_positions": limiting_positions,
        "as_of": moment.isoformat(),
    }


def evaluate_admission(
    dashboard: dict[str, Any],
    proposed_risk_r: float,
    *,
    ticker: str,
    signal_rank: int,
    timestamp: str,
) -> dict[str, Any]:
    proposed = _number(proposed_risk_r, -1)
    reasons = []
    if proposed <= 0:
        reasons.append("The proposed paper risk is invalid.")
    if dashboard["open_positions"] + 1 > MAXIMUM_CONCURRENT_POSITIONS:
        reasons.append(
            f"Opening {ticker.upper()} would exceed the "
            f"{MAXIMUM_CONCURRENT_POSITIONS}-position limit."
        )
    if (
        dashboard["open_risk_r"] + max(0.0, proposed)
        > MAXIMUM_TOTAL_OPEN_RISK_R + 1e-9
    ):
        reasons.append(
            f"Opening {ticker.upper()} would exceed the "
            f"{MAXIMUM_TOTAL_OPEN_RISK_R:g}R open-risk limit."
        )
    if (
        dashboard["daily_new_risk_used_r"] + max(0.0, proposed)
        > MAXIMUM_DAILY_NEW_RISK_R + 1e-9
    ):
        reasons.append(
            f"Opening {ticker.upper()} would exceed today's "
            f"{MAXIMUM_DAILY_NEW_RISK_R:g}R new-risk budget."
        )
    limiting = dashboard.get("limiting_positions") or []
    cause = (
        f"{limiting[0]['ticker']} ({limiting[0]['remaining_risk_r']:.2f}R)"
        if limiting
        else "today's previously admitted signal"
    )
    return {
        "allowed": not reasons,
        "rejection_reason": " ".join(reasons) if reasons else None,
        "current_open_positions": dashboard["open_positions"],
        "current_open_risk_r": dashboard["open_risk_r"],
        "daily_new_risk_r": dashboard["daily_new_risk_used_r"],
        "proposed_risk_r": round(max(0.0, proposed), 4),
        "signal_rank": signal_rank,
        "timestamp": timestamp,
        "capacity_resets_at": dashboard["capacity_resets_at"],
        "limiting_reference": cause,
    }


def rank_signals_by_confidence(
    signals: Iterable[dict[str, Any]],
) -> list[dict[str, Any]]:
    return sorted(
        signals,
        key=lambda signal: (
            -_number(signal.get("confidence")),
            str(signal.get("ticker") or ""),
            str(signal.get("data_timestamp") or ""),
        ),
    )


def admit_ranked_signals(
    signals: Iterable[dict[str, Any]],
    dashboard: dict[str, Any],
    *,
    timestamp: str,
    proposed_risk_r: float = 1.0,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    accepted = []
    rejected = []
    working = {
        **dashboard,
        "limiting_positions": list(dashboard.get("limiting_positions") or []),
    }
    for rank, signal in enumerate(rank_signals_by_confidence(signals), start=1):
        decision = evaluate_admission(
            working,
            proposed_risk_r,
            ticker=str(signal.get("ticker") or ""),
            signal_rank=rank,
            timestamp=timestamp,
        )
        if decision["allowed"]:
            accepted.append({**signal, "portfolio_signal_rank": rank})
            working["open_positions"] += 1
            working["open_risk_r"] += proposed_risk_r
            working["daily_new_risk_used_r"] += proposed_risk_r
            working["limiting_positions"].append(
                {
                    "id": str(signal.get("id") or ""),
                    "ticker": str(signal.get("ticker") or "").upper(),
                    "remaining_risk_r": proposed_risk_r,
                }
            )
        else:
            rejected.append(
                {
                    **signal,
                    "portfolio_signal_rank": rank,
                    "portfolio_rejection": decision,
                }
            )
    return accepted, rejected
