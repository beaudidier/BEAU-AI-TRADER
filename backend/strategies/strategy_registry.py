"""Central registry and availability gate for trading strategies."""

from __future__ import annotations

from collections.abc import Iterable

from .base_strategy import BaseStrategy
from .crypto_strategy import crypto_strategy
from .day_trading_strategy import day_trading_strategy
from .long_term_strategy import long_term_strategy
from .swing_strategy import swing_trading_strategy


class StrategyNotFoundError(LookupError):
    """Raised when a strategy id is not registered."""


class StrategyRegistry:
    def __init__(self, strategies: Iterable[BaseStrategy] = ()) -> None:
        self._strategies: dict[str, BaseStrategy] = {}
        for strategy in strategies:
            self.register(strategy)

    def register(self, strategy: BaseStrategy) -> None:
        if strategy.id in self._strategies:
            raise ValueError(f"Strategy '{strategy.id}' is already registered.")
        self._strategies[strategy.id] = strategy

    def get(self, strategy_id: str) -> BaseStrategy | None:
        return self._strategies.get(strategy_id)

    def require(self, strategy_id: str) -> BaseStrategy:
        strategy = self.get(strategy_id)
        if strategy is None:
            raise StrategyNotFoundError("This trading strategy is not available.")
        return strategy

    def require_usable(self, strategy_id: str) -> BaseStrategy:
        strategy = self.require(strategy_id)
        strategy.ensure_usable()
        return strategy

    def all(self) -> tuple[BaseStrategy, ...]:
        return tuple(self._strategies.values())

    def serialize(self) -> list[dict]:
        return [strategy.to_dict() for strategy in self.all()]


strategy_registry = StrategyRegistry(
    (
        day_trading_strategy,
        swing_trading_strategy,
        long_term_strategy,
        crypto_strategy,
    )
)
