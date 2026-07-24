"""Rule-based post-trade coaching.

The public response is intentionally independent of the rule implementation so it
can be replaced by an LLM-backed coach later without changing API consumers.
"""

from __future__ import annotations

import math
from typing import Any


def _number(trade: dict[str, Any], field: str, *, required: bool = True) -> float | None:
    value = trade.get(field)
    try:
        number = float(value)
    except (TypeError, ValueError):
        if required:
            raise ValueError(f"{field} must be a valid number") from None
        return None

    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def _clamp(value: float) -> int:
    return max(0, min(100, round(value)))


def _grade(score: int) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def analyze_completed_trade(trade: dict[str, Any]) -> dict[str, Any]:
    """Evaluate one completed trade using deterministic, explainable rules."""

    ticker = str(trade.get("ticker") or "trade").upper()
    entry = _number(trade, "entry")
    exit_price = _number(trade, "exit")
    stop_loss = _number(trade, "stop_loss")
    target_1 = _number(trade, "target_1")
    pnl = _number(trade, "pnl")
    realized_rr = _number(trade, "realized_rr")
    confidence = _number(trade, "confidence_score")

    if entry <= 0 or exit_price <= 0 or stop_loss <= 0 or target_1 <= 0:
        raise ValueError("trade prices must be greater than zero")
    if not 0 <= confidence <= 100:
        raise ValueError("confidence_score must be between 0 and 100")

    recommendation = str(trade.get("recommendation") or "").upper()
    exit_reason = str(trade.get("exit_reason") or "Completed trade")
    is_win = pnl > 0
    followed_stop = "stop" in exit_reason.lower()
    reached_target = "target" in exit_reason.lower()
    planned_setup = recommendation in {"BUY", "STRONG BUY"}
    high_confidence = confidence >= 70
    risk_per_share = abs(entry - stop_loss)
    valid_stop_distance = risk_per_share > 0 and risk_per_share / entry <= 0.2
    target_rr = abs(target_1 - entry) / risk_per_share if risk_per_share else 0

    positives: list[str] = []
    mistakes: list[str] = []
    improvements: list[str] = []
    discipline = 55.0

    if planned_setup and high_confidence:
        positives.append("The entry aligned with a qualifying confidence signal.")
        discipline += 12
        confidence_alignment = "Entry aligned with the model's qualifying confidence signal."
    elif planned_setup:
        positives.append("The trade followed a documented BUY setup.")
        discipline += 5
        confidence_alignment = "The trade followed a BUY setup, but confidence was below the preferred level."
    else:
        mistakes.append("The completed trade was not backed by a BUY or STRONG BUY recommendation.")
        improvements.append("Wait for a qualified BUY signal before committing risk.")
        discipline -= 12
        confidence_alignment = "The trade was not aligned with a qualifying model recommendation."

    if valid_stop_distance:
        positives.append("The stop loss created a defined and proportionate risk boundary.")
        discipline += 10
    else:
        mistakes.append("The stop loss was missing, invalid, or too far from the entry.")
        improvements.append("Set a valid stop before entry and keep per-trade risk proportionate.")
        discipline -= 15

    if target_rr >= 1.5:
        positives.append("The first target offered a realistic reward relative to the planned risk.")
        discipline += 8
    else:
        mistakes.append("The first target offered less than 1.5R of planned reward.")
        improvements.append("Choose a first target with at least 1.5R potential or skip the setup.")
        discipline -= 10

    if is_win:
        positives.append(f"The trade closed profitably at {realized_rr:.2f}R.")
        discipline += 10
        outcome = f"{ticker} won because it closed above the entry and realized {realized_rr:.2f}R."
    else:
        mistakes.append(f"The trade closed at {realized_rr:.2f}R and did not reach a profitable exit.")
        outcome = f"{ticker} lost because it closed below the entry at {realized_rr:.2f}R."

    if followed_stop:
        positives.append("The exit honored the predefined stop loss.")
        discipline += 12
        emotional_bias = "No clear emotional bias detected: the loss was contained at the planned stop."
    elif reached_target:
        positives.append("The exit followed the planned target process.")
        discipline += 10
        emotional_bias = "No clear emotional bias detected: the exit followed the planned reward objective."
    elif not is_win and realized_rr < -1.1:
        mistakes.append("The loss exceeded the typical one-risk-unit loss expected from a disciplined stop.")
        improvements.append("Exit at the stop instead of allowing a planned loss to expand.")
        discipline -= 20
        emotional_bias = "Potential loss aversion: the loss extended beyond the planned risk boundary."
    elif is_win and realized_rr < 0.5:
        mistakes.append("The profitable exit captured little of the available reward.")
        improvements.append("Use the planned target or a documented trailing rule to avoid taking profits too early.")
        discipline -= 8
        emotional_bias = "Potential profit-taking bias: the trade exited before capturing meaningful planned reward."
    else:
        improvements.append("Record the exit trigger so execution can be measured against the plan.")
        emotional_bias = "No clear emotional bias can be inferred from the recorded exit data."

    if not is_win:
        improvements.append("Review whether price action invalidated the setup before taking a similar entry again.")

    score = _clamp(discipline)
    return {
        "grade": _grade(score),
        "score": score,
        "summary": f"{outcome} {exit_reason} was the recorded exit reason.",
        "mistakes": mistakes,
        "positives": positives,
        "improvements": improvements,
        "confidence_alignment": confidence_alignment,
        "emotional_bias": emotional_bias,
        "discipline_score": score,
    }
