"""Paper-trading calculations and portfolio reporting."""

from .engine import build_portfolio_summary, build_trade_coach_payload

__all__ = ["build_portfolio_summary", "build_trade_coach_payload"]
