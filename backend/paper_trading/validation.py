"""Safety checks shared by paper-trade entry points."""

import math
from typing import Any


def _finite_positive(payload: dict[str, Any], field: str) -> float:
    try:
        value = float(payload.get(field))
    except (TypeError, ValueError):
        raise ValueError(f"{field} is missing or invalid") from None
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be greater than zero")
    return value


def validate_long_paper_trade(payload: dict[str, Any]) -> None:
    """Reject short and unsafe entries before simulated cash can be changed."""

    if str(payload.get("side") or "").upper() != "BUY":
        raise ValueError("Only long Paper Buy trades are supported")
    if str(payload.get("recommendation") or "").upper() == "SKIP":
        raise ValueError("SKIP recommendations cannot be paper traded")

    current_price = _finite_positive(payload, "current_price")
    entry = _finite_positive(payload, "entry_price")
    stop_loss = _finite_positive(payload, "stop_loss")
    target_1 = _finite_positive(payload, "target_1")
    _finite_positive(payload, "target_2")
    _finite_positive(payload, "quantity")
    rr = _finite_positive(payload, "risk_reward_target_1")
    try:
        confidence = float(payload.get("confidence_score"))
    except (TypeError, ValueError):
        raise ValueError("confidence_score is missing or invalid") from None
    if not math.isfinite(confidence) or not 0 <= confidence <= 100:
        raise ValueError("confidence_score must be between 0 and 100")

    if stop_loss >= entry or target_1 <= entry:
        raise ValueError("Paper Buy requires a stop below entry and a target above entry")
    if rr < 1.5:
        raise ValueError("Target 1 risk/reward must be at least 1.5")
    if abs(current_price - entry) / entry > 0.5:
        raise ValueError("Current market data is inconsistent with the suggested entry")
