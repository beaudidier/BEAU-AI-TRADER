"""Shared contracts for every trading strategy exposed by the application."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class StrategyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    FORWARD_VALIDATION = "FORWARD_VALIDATION"
    COMING_SOON = "COMING_SOON"
    DISABLED = "DISABLED"


class StrategyUnavailableError(ValueError):
    """Raised when a strategy must not produce scanner recommendations."""


@dataclass(frozen=True)
class BaseStrategy:
    id: str
    name: str
    status: StrategyStatus
    asset_classes: tuple[str, ...]
    supported_timeframes: tuple[str, ...]
    required_data: tuple[str, ...]
    scanner_rules: tuple[str, ...]
    entry_rules: tuple[str, ...]
    stop_rules: tuple[str, ...]
    target_rules: tuple[str, ...]
    holding_period: str
    risk_limits: tuple[str, ...]

    @property
    def is_usable(self) -> bool:
        return self.status in {StrategyStatus.ACTIVE, StrategyStatus.FORWARD_VALIDATION}

    def ensure_usable(self) -> None:
        if self.is_usable:
            return
        if self.status is StrategyStatus.COMING_SOON:
            raise StrategyUnavailableError("Coming soon. This engine is not yet validated.")
        raise StrategyUnavailableError("This strategy is currently disabled.")

    def scan(self, **_: Any) -> dict[str, Any] | None:
        """Produce a strategy signal only when a validated implementation exists."""

        self.ensure_usable()
        raise NotImplementedError(f"{self.name} does not implement scanner recommendations.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "asset_classes": list(self.asset_classes),
            "supported_timeframes": list(self.supported_timeframes),
            "required_data": list(self.required_data),
            "scanner_rules": list(self.scanner_rules),
            "entry_rules": list(self.entry_rules),
            "stop_rules": list(self.stop_rules),
            "target_rules": list(self.target_rules),
            "holding_period": self.holding_period,
            "risk_limits": list(self.risk_limits),
        }
