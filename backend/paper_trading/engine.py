"""Provider-independent calculations for simulated equity trading."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from decision_rules import recommendation_for_score


def _value(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _round(value: float) -> float:
    return round(value, 2)


def _side_multiplier(side: str) -> int:
    return 1 if str(side).upper() == "BUY" else -1


def build_trade_coach_payload(trade: dict[str, Any]) -> dict[str, Any]:
    """Map a persisted paper trade to the stable Coach input contract."""

    entry = _value(trade.get("entry_price"))
    stop = _value(trade.get("stop_loss"))
    quantity = _value(trade.get("quantity"))
    pnl = _value(trade.get("realized_pnl"))
    risk = abs(entry - stop) * quantity
    return {
        "ticker": str(trade.get("ticker") or "").upper(),
        "entry": entry,
        "exit": _value(trade.get("exit_price")),
        "stop_loss": stop,
        "target_1": _value(trade.get("target_1")),
        "pnl": pnl,
        "realized_rr": pnl / risk if risk > 0 else 0,
        "confidence_score": _value(trade.get("confidence_score")),
        "recommendation": recommendation_for_score(trade.get("confidence_score")),
        "exit_reason": "Paper trade closed at market",
    }


def build_close_preview(trade: dict[str, Any], latest_quote: float, quote_timestamp: str) -> dict[str, Any]:
    """Build the non-mutating price and P/L values shown before a market close."""

    quantity = _value(trade.get("quantity"))
    entry = _value(trade.get("entry_price"))
    quote = _value(latest_quote)
    side = str(trade.get("side") or "BUY").upper()
    return {
        "trade_id": str(trade.get("id") or ""),
        "ticker": str(trade.get("ticker") or "").upper(),
        "side": side,
        "latest_quote": _round(quote),
        "quote_timestamp": quote_timestamp,
        "estimated_exit_value": _round(quote * quantity),
        "realized_pnl_estimate": _round((quote - entry) * quantity * _side_multiplier(side)),
    }


def build_portfolio_summary(account: dict[str, Any], open_trades: list[dict[str, Any]], closed_trades: list[dict[str, Any]], quotes: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Calculate portfolio metrics from persisted trades and provider quotes."""

    cash_balance = _value(account.get("cash_balance"))
    initial_balance = _value(account.get("initial_balance"), 10000.0)
    unrealized_pnl = 0.0
    today_pnl = 0.0
    open_positions: list[dict[str, Any]] = []

    for trade in open_trades:
        ticker = str(trade.get("ticker") or "").upper()
        entry = _value(trade.get("entry_price"))
        quantity = _value(trade.get("quantity"))
        side = str(trade.get("side") or "BUY").upper()
        quote = quotes.get(ticker, {})
        market_price = _value(quote.get("price"), entry)
        previous_close = _value(quote.get("previous_close"), market_price)
        multiplier = _side_multiplier(side)
        position_pnl = (market_price - entry) * quantity * multiplier
        initial_risk = abs(entry - _value(trade.get("stop_loss"))) * quantity
        daily_pnl = (market_price - previous_close) * quantity * multiplier
        unrealized_pnl += position_pnl
        today_pnl += daily_pnl
        open_positions.append({
            **trade,
            "market_price": _round(market_price),
            "unrealized_pnl": _round(position_pnl),
            "unrealized_r": round(position_pnl / initial_risk, 4) if initial_risk > 0 else 0,
            "market_value": _round(market_price * quantity * multiplier),
            "latest_quote_timestamp": quote.get("timestamp") or quote.get("latest_timestamp"),
        })

    realized_pnl = sum(_value(trade.get("realized_pnl")) for trade in closed_trades)
    today = datetime.now(timezone.utc).date().isoformat()
    today_pnl += sum(_value(trade.get("realized_pnl")) for trade in closed_trades if str(trade.get("closed_at") or "").startswith(today))
    wins = sum(1 for trade in closed_trades if _value(trade.get("realized_pnl")) > 0)
    portfolio_balance = cash_balance + sum(_value(position["market_value"]) for position in open_positions)
    recent_trades = sorted([*open_positions, *closed_trades], key=lambda trade: str(trade.get("closed_at") or trade.get("opened_at") or ""), reverse=True)[:5]

    return {
        "initial_balance": _round(initial_balance),
        "cash_balance": _round(cash_balance),
        "portfolio_balance": _round(portfolio_balance),
        "open_position_value": _round(sum(abs(_value(position["market_value"])) for position in open_positions)),
        "unrealized_pnl": _round(unrealized_pnl),
        "realized_pnl": _round(realized_pnl),
        "today_pnl": _round(today_pnl),
        "win_rate": _round((wins / len(closed_trades) * 100) if closed_trades else 0),
        "open_positions": open_positions,
        "closed_positions": closed_trades,
        "recent_trades": recent_trades,
    }
