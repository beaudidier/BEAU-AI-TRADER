"""Explainable, deterministic learning rules for completed paper trades."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from typing import Any

from decision_rules import recommendation_for_score


def _number(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _label(score: float, high: str, neutral: str, low: str) -> str:
    return high if score >= 65 else low if score < 45 else neutral


def build_learning_context(ticker: str, confidence: float, recommendation: str, analysis: dict[str, Any] | None, company: dict[str, Any] | None) -> dict[str, Any]:
    """Create a compact setup snapshot when a simulated trade is opened."""

    engines = (analysis or {}).get("engines", {})
    trend_score = _number((engines.get("trend") or {}).get("score"), 50)
    momentum_score = _number((engines.get("momentum") or {}).get("score"), 50)
    regime_score = _number((engines.get("market_regime") or {}).get("score"), 50)
    confidence = max(0, min(100, _number(confidence, 50)))
    recommendation = recommendation_for_score(confidence)
    return {
        "ticker": ticker.upper(),
        "setup_quality": "High quality" if recommendation == "STRONG BUY" else "Qualified" if recommendation == "BUY" else "Watchlist",
        "market_regime": _label(regime_score, "Risk-on", "Neutral", "Defensive"),
        "trend": _label(trend_score, "Bullish", "Mixed", "Bearish"),
        "momentum": _label(momentum_score, "Positive", "Neutral", "Weak"),
        "sector": str((company or {}).get("sector") or "Unknown"),
    }


def build_learning_trade_update(trade: dict[str, Any], coach: dict[str, Any]) -> dict[str, Any]:
    """Produce persisted learning facts for a just-completed paper trade."""

    entry = _number(trade.get("entry_price"))
    stop = _number(trade.get("stop_loss"))
    quantity = _number(trade.get("quantity"))
    pnl = _number(trade.get("realized_pnl"))
    risk = abs(entry - stop) * quantity
    rr = pnl / risk if risk > 0 else 0.0
    mistakes = [str(item) for item in coach.get("mistakes", []) if str(item).strip()]
    if pnl > 0:
        summary = f"Profitable {rr:.2f}R outcome. Preserve the conditions that produced this setup."
    else:
        summary = f"Loss of {rr:.2f}R. Review the recorded mistakes before repeating this setup."
    return {"realized_rr": round(rr, 2), "mistakes": mistakes, "learning_summary": summary}


def _win_rate(trades: list[dict[str, Any]]) -> float:
    return round(sum(1 for trade in trades if _number(trade.get("realized_pnl")) > 0) / len(trades) * 100, 1) if trades else 0.0


def _group_win_rates(trades: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        groups[str(trade.get(key) or "Unknown")].append(trade)
    return [{"label": label, "trades": len(items), "win_rate": _win_rate(items), "average_rr": round(sum(_number(item.get("realized_rr")) for item in items) / len(items), 2)} for label, items in sorted(groups.items())]


def _confidence_bucket(value: float) -> str:
    return "80–100" if value >= 80 else "65–79" if value >= 65 else "Below 65"


def _holding_bucket(minutes: float) -> str:
    return "Under 1 hour" if minutes < 60 else "1–24 hours" if minutes <= 1440 else "Over 1 day"


def build_learning_dashboard(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a user's completed paper trades into actionable learning metrics."""

    completed = [trade for trade in trades if str(trade.get("status", "CLOSED")).upper() == "CLOSED"]
    confidence_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    holding_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    monthly_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    mistakes: Counter[str] = Counter()
    for trade in completed:
        confidence_groups[_confidence_bucket(_number(trade.get("confidence_score")))].append(trade)
        holding_groups[_holding_bucket(_number(trade.get("holding_minutes")))].append(trade)
        monthly_groups[str(trade.get("closed_at") or "")[:7] or "Unknown"].append(trade)
        mistakes.update(str(item) for item in (trade.get("mistakes") or []) if str(item).strip())

    confidence_rows = [{"label": label, "trades": len(items), "win_rate": _win_rate(items), "average_rr": round(sum(_number(item.get("realized_rr")) for item in items) / len(items), 2)} for label, items in [*confidence_groups.items()]]
    holding_rows = [{"label": label, "trades": len(items), "win_rate": _win_rate(items), "average_rr": round(sum(_number(item.get("realized_rr")) for item in items) / len(items), 2)} for label, items in [*holding_groups.items()]]
    setup_rows = _group_win_rates(completed, "setup_quality")
    sorted_setups = sorted(setup_rows, key=lambda item: (item["win_rate"], item["average_rr"]), reverse=True)
    monthly_progress = [{"month": month, "trades": len(items), "win_rate": _win_rate(items), "pnl": round(sum(_number(item.get("realized_pnl")) for item in items), 2)} for month, items in sorted(monthly_groups.items())]
    average_rr = round(sum(_number(trade.get("realized_rr")) for trade in completed) / len(completed), 2) if completed else 0.0
    recommendations: list[str] = []
    if not completed:
        recommendations.append("Complete paper trades to establish your personal performance baseline.")
    else:
        best = sorted_setups[0] if sorted_setups else None
        worst = sorted_setups[-1] if sorted_setups else None
        if best: recommendations.append(f"Your strongest setup is {best['label']} at a {best['win_rate']:.1f}% win rate.")
        if worst and worst["trades"] >= 2: recommendations.append(f"Review {worst['label']} setups before allocating more simulated risk.")
        if mistakes: recommendations.append(f"Address the recurring issue: {mistakes.most_common(1)[0][0]}")

    return {
        "personal_statistics": {"total_trades": len(completed), "wins": sum(1 for trade in completed if _number(trade.get("realized_pnl")) > 0), "losses": sum(1 for trade in completed if _number(trade.get("realized_pnl")) <= 0), "win_rate": _win_rate(completed), "average_rr": average_rr, "average_holding_minutes": round(sum(_number(trade.get("holding_minutes")) for trade in completed) / len(completed), 1) if completed else 0.0},
        "winrate_by_confidence": confidence_rows,
        "winrate_by_market_regime": _group_win_rates(completed, "market_regime"),
        "winrate_by_holding_time": holding_rows,
        "best_performing_setups": sorted_setups[:3],
        "worst_performing_setups": list(reversed(sorted_setups[-3:])),
        "most_common_mistakes": [{"mistake": mistake, "count": count} for mistake, count in mistakes.most_common(5)],
        "ai_recommendations": recommendations,
        "monthly_progress": monthly_progress,
    }
