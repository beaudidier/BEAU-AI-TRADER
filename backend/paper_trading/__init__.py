"""Paper-trading calculations and portfolio reporting."""

from .engine import build_close_preview, build_portfolio_summary, build_trade_coach_payload
from .validation import validate_long_paper_trade

__all__ = ["build_close_preview", "build_portfolio_summary", "build_trade_coach_payload", "validate_long_paper_trade"]
