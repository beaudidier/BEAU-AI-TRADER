from abc import ABC, abstractmethod


class UniverseProvider(ABC):
    """Keeps symbol-universe membership independent from market data providers."""

    market: str

    @abstractmethod
    def symbols(self, universe: str, custom_symbols: list[str] | None = None) -> list[str]: ...

    @abstractmethod
    def supported_universes(self) -> set[str]: ...
