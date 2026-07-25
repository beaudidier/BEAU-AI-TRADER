"""Paper-only forward validation for the frozen regime-gated Pullback strategy."""

from .engine import (
    STRATEGY_METADATA,
    STRATEGY_VERSION,
    build_dashboard,
    build_live_signal,
    evaluate_signal,
)

__all__ = ["STRATEGY_METADATA", "STRATEGY_VERSION", "build_dashboard", "build_live_signal", "evaluate_signal"]
