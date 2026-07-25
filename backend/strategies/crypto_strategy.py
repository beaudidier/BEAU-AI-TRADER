"""Crypto strategy placeholder with no executable recommendation logic."""

from .base_strategy import BaseStrategy, StrategyStatus


crypto_strategy = BaseStrategy(
    id="crypto",
    name="Crypto Trading",
    status=StrategyStatus.COMING_SOON,
    asset_classes=("Crypto",),
    supported_timeframes=(),
    required_data=(),
    scanner_rules=("No scanner rules are enabled until this strategy is validated.",),
    entry_rules=("No entry rules are enabled.",),
    stop_rules=("No stop rules are enabled.",),
    target_rules=("No target rules are enabled.",),
    holding_period="Not defined",
    risk_limits=("No risk model is enabled.",),
)
