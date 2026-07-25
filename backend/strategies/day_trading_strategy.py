"""Day-trading strategy placeholder with no executable recommendation logic."""

from .base_strategy import BaseStrategy, StrategyStatus


day_trading_strategy = BaseStrategy(
    id="day_trading",
    name="Day Trading",
    status=StrategyStatus.COMING_SOON,
    asset_classes=("US stocks",),
    supported_timeframes=(),
    required_data=(),
    scanner_rules=("No scanner rules are enabled until this strategy is validated.",),
    entry_rules=("No entry rules are enabled.",),
    stop_rules=("No stop rules are enabled.",),
    target_rules=("No target rules are enabled.",),
    holding_period="Not defined",
    risk_limits=("No risk model is enabled.",),
)
