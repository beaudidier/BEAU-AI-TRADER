"""Canonical confidence-based trade recommendations.

All application surfaces must derive a recommendation from this module rather
than maintaining their own threshold logic.
"""

from __future__ import annotations

import math
from typing import Any


def normalized_score(value: Any) -> int:
    """Return a safe whole-number confidence score within the 0–100 range."""

    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(score):
        return 0
    return max(0, min(100, round(score)))


def recommendation_for_score(value: Any) -> str:
    """Map confidence to the application's single recommendation taxonomy."""

    score = normalized_score(value)
    if score >= 90:
        return "STRONG BUY"
    if score >= 75:
        return "BUY"
    if score >= 60:
        return "WATCH"
    return "SKIP"


def is_actionable_score(value: Any) -> bool:
    """Whether the canonical decision permits a long trade entry."""

    return recommendation_for_score(value) in {"BUY", "STRONG BUY"}


def next_threshold_for_score(value: Any) -> tuple[int, str] | None:
    """Return the next recommendation tier without duplicating rule thresholds."""

    score = normalized_score(value)
    for threshold, recommendation in ((60, "WATCH"), (75, "BUY"), (90, "STRONG BUY")):
        if score < threshold:
            return threshold, recommendation
    return None
