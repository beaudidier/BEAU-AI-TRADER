"""Paper-trading calculations and portfolio reporting."""

from .engine import build_close_preview, build_portfolio_summary, build_trade_coach_payload
from .portfolio_risk import (
    admit_ranked_signals,
    build_portfolio_risk_dashboard,
    evaluate_admission,
)
from .validation import validate_long_paper_trade

__all__ = [
    "admit_ranked_signals",
    "build_close_preview",
    "build_portfolio_risk_dashboard",
    "build_portfolio_summary",
    "build_trade_coach_payload",
    "evaluate_admission",
    "validate_long_paper_trade",
]
