from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any


class MarketSession(StrEnum):
    PREMARKET = "premarket"
    REGULAR = "regular"
    AFTER_HOURS = "after-hours"
    CLOSED = "closed"


class Completeness(StrEnum):
    INCOMPLETE = "incomplete"
    CLOSED = "closed"
    GAP = "gap"


class StreamState(StrEnum):
    DISABLED = "disabled"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    STALE = "stale"
    ERROR = "error"
    STOPPED = "stopped"


class OrderType(StrEnum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(StrEnum):
    PENDING = "pending"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True)
class TradeTick:
    ticker: str
    price: float
    size: float
    timestamp: datetime
    event_id: str
    source: str = "alpaca_iex"


@dataclass(frozen=True)
class Quote:
    ticker: str
    bid: float
    ask: float
    bid_size: float
    ask_size: float
    timestamp: datetime
    event_id: str
    source: str = "alpaca_iex"
    coverage: str = "partial-market"

    @property
    def midpoint(self) -> float:
        return (self.bid + self.ask) / 2

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_percent(self) -> float:
        return (self.spread / self.midpoint) * 100 if self.midpoint > 0 else 0.0

    def serialize(self, *, stale: bool = False) -> dict[str, Any]:
        return {
            "ticker": self.ticker,
            "bid": round(self.bid, 6),
            "ask": round(self.ask, 6),
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "midpoint": round(self.midpoint, 6),
            "spread": round(self.spread, 6),
            "spread_percent": round(self.spread_percent, 4),
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "coverage": self.coverage,
            "stale": stale,
        }


@dataclass(frozen=True)
class Bar:
    ticker: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime
    source: str
    completeness: Completeness
    vwap: float | None = None

    def serialize(self) -> dict[str, Any]:
        result = asdict(self)
        result["timestamp"] = self.timestamp.isoformat()
        result["completeness"] = self.completeness.value
        return result


@dataclass(frozen=True)
class PaperOrderRequest:
    ticker: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    idempotency_key: str
    limit_price: float | None = None
    stop_price: float | None = None
    protective_stop: float | None = None


@dataclass
class PaperOrder:
    id: str
    request: PaperOrderRequest
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    fill_price: float | None = None
    filled_at: datetime | None = None
    rejection_reason: str | None = None

    def serialize(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "ticker": self.request.ticker,
            "side": self.request.side.value,
            "order_type": self.request.order_type.value,
            "quantity": self.request.quantity,
            "limit_price": self.request.limit_price,
            "stop_price": self.request.stop_price,
            "protective_stop": self.request.protective_stop,
            "idempotency_key": self.request.idempotency_key,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "fill_price": self.fill_price,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "rejection_reason": self.rejection_reason,
        }


@dataclass
class PaperPosition:
    ticker: str
    quantity: int
    entry_price: float
    protective_stop: float
    opened_at: datetime
    current_price: float
    unrealized_pnl: float = 0.0

    def serialize(self) -> dict[str, Any]:
        result = asdict(self)
        result["opened_at"] = self.opened_at.isoformat()
        return result


@dataclass
class ClosedPaperPosition:
    ticker: str
    quantity: int
    entry_price: float
    exit_price: float
    opened_at: datetime
    closed_at: datetime
    realized_pnl: float
    reason: str

    def serialize(self) -> dict[str, Any]:
        result = asdict(self)
        result["opened_at"] = self.opened_at.isoformat()
        result["closed_at"] = self.closed_at.isoformat()
        return result


@dataclass
class StreamDiagnostics:
    state: StreamState = StreamState.DISABLED
    connected_at: datetime | None = None
    last_event_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    reconnect_attempts: int = 0
    duplicate_events: int = 0
    out_of_order_events: int = 0
    invalid_events: int = 0
    messages_received: int = 0
    last_error: str | None = None
    subscriptions: list[str] = field(default_factory=list)

    def serialize(self) -> dict[str, Any]:
        result = asdict(self)
        result["state"] = self.state.value
        for key in ("connected_at", "last_event_at", "last_heartbeat_at"):
            value = result[key]
            result[key] = value.isoformat() if value else None
        return result
