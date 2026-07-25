"""Outcome taxonomy and coverage-based health for forward validation."""

from __future__ import annotations

from typing import Any

SYMBOL_OUTCOMES = {
    "completed",
    "insufficient_history",
    "invalid_symbol",
    "provider_failure",
    "timeout",
    "stale_data",
    "incomplete_data",
}
EXCLUSION_OUTCOMES = {"insufficient_history"}
FAILURE_OUTCOMES = SYMBOL_OUTCOMES - EXCLUSION_OUTCOMES - {"completed"}
MINIMUM_HISTORY_ROWS = 200


def symbol_outcome(status: str, reason: str) -> dict[str, str]:
    if status not in SYMBOL_OUTCOMES:
        raise ValueError(f"Unsupported forward-validation symbol outcome: {status}")
    return {"status": status, "reason": reason}


def classify_data_error(error: Exception | str) -> dict[str, str]:
    """Map provider and quality errors to a stable diagnostic outcome."""

    reason = str(error) or type(error).__name__
    lowered = reason.lower()
    if (
        "timed out" in lowered
        or "maximum workflow duration" in lowered
        or ("exceeded" in lowered and "seconds" in lowered)
    ):
        status = "timeout"
    elif "stale market data" in lowered or "same completed session" in lowered:
        status = "stale_data"
    elif "no completed daily history" in lowered or "no data" in lowered:
        status = "invalid_symbol"
    elif any(
        marker in lowered
        for marker in (
            "required ohlcv",
            "missing",
            "duplicate market dates",
            "chronological order",
            "complete ohlcv",
            "required session",
            "incomplete",
        )
    ):
        status = "incomplete_data"
    else:
        status = "provider_failure"
    return symbol_outcome(status, reason)


def insufficient_history_outcome(
    available_rows: int,
    required_rows: int = MINIMUM_HISTORY_ROWS,
) -> dict[str, str]:
    return symbol_outcome(
        "insufficient_history",
        f"{available_rows} completed daily candles are available; "
        f"the frozen strategy requires at least {required_rows}.",
    )


def health_summary(
    expected_symbols: int,
    completed_symbols: int,
    *,
    eligible_symbols: int | None = None,
    excluded_symbols: int = 0,
    genuine_failures: int = 0,
) -> dict[str, Any]:
    """Classify health strictly by completed coverage of the expected universe."""

    expected = max(0, int(expected_symbols))
    completed = max(0, min(int(completed_symbols), expected))
    percentage = round((completed / expected) * 100, 2) if expected else 100.0
    health = "healthy" if percentage >= 95 else "degraded" if percentage >= 90 else "failed"
    return {
        "expected_symbols": expected,
        "eligible_symbols": (
            max(0, int(eligible_symbols))
            if eligible_symbols is not None
            else completed
        ),
        "completed_eligible_symbols": completed,
        "intentionally_excluded_symbols": max(0, int(excluded_symbols)),
        "genuine_failures": max(0, int(genuine_failures)),
        "completion_percentage": percentage,
        "health": health,
    }
