from __future__ import annotations

import gzip
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from threading import Event, RLock, Thread, current_thread
from time import monotonic
from typing import Any, Literal

from .bar_aggregator import BarAggregator
from .models import Bar, Completeness
from .session import as_utc, classify_market_session

ReplaySpeed = Literal["original", "10x", "maximum"]


def _time(value: str) -> datetime:
    return as_utc(
        datetime.fromisoformat(
            value.replace(
                "Z",
                "+00:00",
            )
        )
    )


def _event_time(event: dict[str, Any]) -> datetime:
    value = event.get("receipt_timestamp") or event.get(
        "provider_timestamp"
    )
    if not value:
        raise ValueError("Recorded event timestamp is missing.")
    return _time(str(value))


def _provider_time(event: dict[str, Any]) -> datetime:
    value = event.get("provider_timestamp") or event.get(
        "receipt_timestamp"
    )
    if not value:
        raise ValueError("Recorded event timestamp is missing.")
    return _time(str(value))


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


@dataclass
class ReplayOrder:
    id: str
    symbol: str
    side: str
    order_type: str
    quantity: float
    remaining: float
    submitted_at: datetime
    eligible_at: datetime
    limit_price: float | None = None
    stop_price: float | None = None
    status: str = "pending"
    filled_quantity: float = 0.0
    average_fill_price: float | None = None
    rejection_reason: str | None = None

    def serialize(self) -> dict[str, Any]:
        result = asdict(self)
        result["submitted_at"] = self.submitted_at.isoformat()
        result["eligible_at"] = self.eligible_at.isoformat()
        return result


class ReplayExecutionSimulator:
    """Deterministic, local-only execution model used during replay."""

    def __init__(
        self,
        *,
        slippage_bps: float = 2,
        latency_ms: int = 100,
        stale_quote_seconds: int = 15,
    ):
        self.slippage_bps = max(0.0, float(slippage_bps))
        self.latency = timedelta(milliseconds=max(0, int(latency_ms)))
        self.stale_quote = timedelta(seconds=max(1, stale_quote_seconds))
        self.orders: dict[str, ReplayOrder] = {}
        self.fills: list[dict[str, Any]] = []
        self.quotes: dict[str, dict[str, Any]] = {}
        self._order_counter = 0

    def reset(self) -> None:
        self.orders.clear()
        self.fills.clear()
        self.quotes.clear()
        self._order_counter = 0

    def submit(
        self,
        *,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        submitted_at: datetime,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> dict[str, Any]:
        now = as_utc(submitted_at)
        self._order_counter += 1
        order_id = hashlib.sha256(
            (
                f"{self._order_counter}|{symbol.upper()}|{side}|"
                f"{order_type}|{quantity}|{now.isoformat()}|"
                f"{limit_price}|{stop_price}"
            ).encode()
        ).hexdigest()[:24]
        order = ReplayOrder(
            id=order_id,
            symbol=symbol.upper(),
            side=side,
            order_type=order_type,
            quantity=float(quantity),
            remaining=float(quantity),
            submitted_at=now,
            eligible_at=now + self.latency,
            limit_price=limit_price,
            stop_price=stop_price,
        )
        quote = self.quotes.get(order.symbol)
        if side not in {"buy", "sell"}:
            order.status = "rejected"
            order.rejection_reason = "Invalid side."
        elif order_type not in {"market", "limit", "stop"}:
            order.status = "rejected"
            order.rejection_reason = "Invalid order type."
        elif quantity <= 0:
            order.status = "rejected"
            order.rejection_reason = "Quantity must be positive."
        elif classify_market_session(now).value != "regular":
            order.status = "rejected"
            order.rejection_reason = "Outside the regular US session."
        elif quote is None or now - quote["timestamp"] > self.stale_quote:
            order.status = "rejected"
            order.rejection_reason = "Quote is stale or unavailable."
        self.orders[order.id] = order
        return order.serialize()

    def cancel(self, order_id: str) -> dict[str, Any]:
        order = self.orders[order_id]
        if order.status in {"pending", "partially_filled"}:
            order.status = "cancelled"
        return order.serialize()

    def on_event(self, event: dict[str, Any]) -> None:
        symbol = str(event.get("symbol") or "").upper()
        if not symbol:
            return
        payload = event.get("payload") or {}
        timestamp = _event_time(event)
        if event.get("event_type") == "quote":
            bid = float(payload.get("bp", 0))
            ask = float(payload.get("ap", 0))
            if 0 < bid <= ask:
                self.quotes[symbol] = {
                    "bid": bid,
                    "ask": ask,
                    "timestamp": timestamp,
                }
        if event.get("event_type") not in {"trade", "quote"}:
            return
        trade_price = (
            float(payload.get("p", 0))
            if event.get("event_type") == "trade"
            else None
        )
        trade_size = (
            float(payload.get("s", 0))
            if event.get("event_type") == "trade"
            else 0
        )
        for order in self.orders.values():
            if (
                order.symbol != symbol
                or order.status not in {"pending", "partially_filled"}
                or timestamp < order.eligible_at
            ):
                continue
            quote = self.quotes.get(symbol)
            if quote is None or timestamp - quote["timestamp"] > self.stale_quote:
                continue
            executable = False
            reference = quote["ask"] if order.side == "buy" else quote["bid"]
            if order.order_type == "market":
                executable = True
            elif order.order_type == "limit" and trade_price is not None:
                executable = (
                    trade_price <= float(order.limit_price)
                    if order.side == "buy"
                    else trade_price >= float(order.limit_price)
                )
                reference = min(reference, float(order.limit_price)) if (
                    order.side == "buy"
                ) else max(reference, float(order.limit_price))
            elif order.order_type == "stop" and trade_price is not None:
                executable = (
                    trade_price >= float(order.stop_price)
                    if order.side == "buy"
                    else trade_price <= float(order.stop_price)
                )
            if not executable:
                continue
            available = (
                trade_size
                if trade_size > 0
                else order.remaining
            )
            fill_quantity = min(order.remaining, available)
            slippage = reference * self.slippage_bps / 10_000
            fill_price = (
                reference + slippage
                if order.side == "buy"
                else reference - slippage
            )
            previous_value = (
                (order.average_fill_price or 0) * order.filled_quantity
            )
            order.filled_quantity += fill_quantity
            order.remaining -= fill_quantity
            order.average_fill_price = (
                previous_value + fill_price * fill_quantity
            ) / order.filled_quantity
            order.status = (
                "filled" if order.remaining <= 1e-9 else "partially_filled"
            )
            self.fills.append(
                {
                    "order_id": order.id,
                    "symbol": symbol,
                    "timestamp": timestamp.isoformat(),
                    "quantity": fill_quantity,
                    "price": round(fill_price, 8),
                    "slippage_bps": self.slippage_bps,
                    "paper_only": True,
                }
            )


class DeterministicReplayEngine:
    def __init__(self, recorder):
        self.recorder = recorder
        self._lock = RLock()
        self._thread: Thread | None = None
        self._pause = Event()
        self._stop = Event()
        self.events: list[dict[str, Any]] = []
        self.cursor = 0
        self.speed: ReplaySpeed = "maximum"
        self.state = "idle"
        self.session_id: str | None = None
        self.current_timestamp: datetime | None = None
        self.last_quotes: dict[str, dict[str, Any]] = {}
        self.aggregator = BarAggregator()
        self.execution = ReplayExecutionSimulator()
        self.processed_digest = hashlib.sha256()
        self.error: str | None = None

    def _load(self, session_id: str) -> list[dict[str, Any]]:
        path, metadata = self.recorder.resolve_session(session_id)
        if metadata.get("status") != "completed":
            raise ValueError("Only completed recordings can be replayed.")
        values = []
        with gzip.open(path, "rt", encoding="utf-8") as source:
            for line in source:
                values.append(json.loads(line))
        return sorted(
            values,
            key=lambda event: (
                _event_time(event),
                int(event.get("index", 0)),
            ),
        )

    def start(
        self,
        session_id: str,
        *,
        speed: ReplaySpeed = "maximum",
    ) -> dict[str, Any]:
        if speed not in {"original", "10x", "maximum"}:
            raise ValueError("Replay speed must be original, 10x, or maximum.")
        with self._lock:
            self.reset()
            self.events = self._load(session_id)
            self.session_id = session_id
            self.speed = speed
            self.state = "running"
            self._pause.set()
            self._stop.clear()
            self._start_thread()
            return self.status()

    def _start_thread(self) -> None:
        self._thread = Thread(
            target=self._run,
            name="intraday-replay",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        try:
            previous: datetime | None = None
            while self.cursor < len(self.events) and not self._stop.is_set():
                self._pause.wait()
                if self._stop.is_set():
                    break
                event = self.events[self.cursor]
                current = _event_time(event)
                if previous is not None and self.speed != "maximum":
                    divisor = 10 if self.speed == "10x" else 1
                    delay = max(
                        0.0,
                        (current - previous).total_seconds() / divisor,
                    )
                    if delay and not self._wait_delay(delay):
                        break
                self._process(event)
                previous = current
                self.cursor += 1
            if not self._stop.is_set():
                self.state = "completed"
        except Exception as error:  # pragma: no cover - defensive boundary
            self.error = f"{type(error).__name__}: {error}"
            self.state = "error"

    def _wait_delay(self, delay: float) -> bool:
        remaining = delay
        while remaining > 0:
            self._pause.wait()
            if self._stop.is_set():
                return False
            started = monotonic()
            if self._stop.wait(min(0.1, remaining)):
                return False
            if self._pause.is_set():
                remaining -= monotonic() - started
        return True

    def _process(self, event: dict[str, Any]) -> None:
        self.current_timestamp = _event_time(event)
        symbol = str(event.get("symbol") or "").upper()
        payload = event.get("payload") or {}
        kind = event.get("event_type")
        self.processed_digest.update(
            (_stable(event) + "\n").encode()
        )
        if (
            kind in {"trade", "quote", "bar_1m"}
            and event.get("disposition") != "accepted"
        ):
            return
        if kind == "quote" and symbol:
            bid = float(payload.get("bp", 0))
            ask = float(payload.get("ap", 0))
            if 0 < bid <= ask:
                midpoint = (bid + ask) / 2
                self.last_quotes[symbol] = {
                    "ticker": symbol,
                    "bid": bid,
                    "ask": ask,
                    "bid_size": float(payload.get("bs", 0)),
                    "ask_size": float(payload.get("as", 0)),
                    "spread": ask - bid,
                    "spread_percent": (
                        ((ask - bid) / midpoint) * 100 if midpoint > 0 else 0
                    ),
                    "timestamp": _provider_time(event).isoformat(),
                    "source": event.get("source"),
                    "coverage": event.get("coverage"),
                }
        elif kind == "bar_1m" and symbol:
            received_at = _time(event.get("receipt_timestamp"))
            bar_timestamp = _provider_time(event).replace(
                second=0,
                microsecond=0,
            )
            self.aggregator.add_minute_bar(
                Bar(
                    ticker=symbol,
                    timeframe="1m",
                    open=float(payload["o"]),
                    high=float(payload["h"]),
                    low=float(payload["l"]),
                    close=float(payload["c"]),
                    volume=float(payload["v"]),
                    vwap=(
                        float(payload["vw"])
                        if payload.get("vw") is not None
                        else None
                    ),
                    timestamp=bar_timestamp,
                    source=str(event.get("source", "alpaca_iex")),
                    completeness=(
                        Completeness.CLOSED
                        if received_at
                        >= bar_timestamp + timedelta(minutes=1)
                        else Completeness.INCOMPLETE
                    ),
                ),
                received_at=max(
                    bar_timestamp + timedelta(minutes=1),
                    received_at,
                ),
                historical_backfill=True,
            )
        self.execution.on_event(event)

    def pause(self) -> dict[str, Any]:
        self._pause.clear()
        if self.state == "running":
            self.state = "paused"
        return self.status()

    def resume(self) -> dict[str, Any]:
        if self.state == "paused":
            self.state = "running"
            self._pause.set()
        return self.status()

    def seek(self, timestamp: datetime) -> dict[str, Any]:
        target = as_utc(timestamp)
        with self._lock:
            self._stop.set()
            self._pause.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=2)
            session_id = self.session_id
            speed = self.speed
            events = list(self.events)
            self.reset()
            self.events = events
            self.session_id = session_id
            self.speed = speed
            while (
                self.cursor < len(self.events)
                and _event_time(self.events[self.cursor]) < target
            ):
                self._process(self.events[self.cursor])
                self.cursor += 1
            self.state = "paused"
            self._stop.clear()
            self._pause.clear()
            self._start_thread()
            return self.status()

    def reset(self) -> dict[str, Any]:
        self._stop.set()
        self._pause.set()
        if (
            self._thread
            and self._thread.is_alive()
            and self._thread is not current_thread()
        ):
            self._thread.join(timeout=2)
        self._thread = None
        self.events = []
        self.cursor = 0
        self.state = "idle"
        self.session_id = None
        self.current_timestamp = None
        self.last_quotes = {}
        self.aggregator = BarAggregator()
        self.execution.reset()
        self.processed_digest = hashlib.sha256()
        self.error = None
        self._stop.clear()
        self._pause.clear()
        return self.status()

    def run_to_completion(self, session_id: str) -> dict[str, Any]:
        return self._run_loaded_to_completion(
            session_id,
            self._load(session_id),
        )

    def _run_loaded_to_completion(
        self,
        session_id: str,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        self.reset()
        self.events = events
        self.session_id = session_id
        self.speed = "maximum"
        self.state = "running"
        for event in self.events:
            self._process(event)
            self.cursor += 1
        self.state = "completed"
        return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "status": self.state,
            "session_id": self.session_id,
            "speed": self.speed,
            "cursor": self.cursor,
            "total_events": len(self.events),
            "progress_percent": round(
                self.cursor / len(self.events) * 100,
                2,
            ) if self.events else 0,
            "current_replay_timestamp": (
                self.current_timestamp.isoformat()
                if self.current_timestamp
                else None
            ),
            "digest_sha256": self.processed_digest.hexdigest(),
            "quotes": self.last_quotes,
            "bars": {
                timeframe: sum(
                    len(self.aggregator.bars(symbol, timeframe))
                    for symbol in {
                        str(event.get("symbol") or "").upper()
                        for event in self.events
                        if event.get("symbol")
                    }
                )
                for timeframe in ("1m", "5m", "15m")
            },
            "simulated_orders": [
                order.serialize() for order in self.execution.orders.values()
            ],
            "simulated_fills": list(self.execution.fills),
            "error": self.error,
            "paper_only": True,
            "live_order_routing": False,
        }

    def _state_snapshot(self) -> dict[str, Any]:
        symbols = sorted(
            {
                str(event.get("symbol") or "").upper()
                for event in self.events
                if event.get("symbol")
            }
        )
        return {
            "quotes": self.last_quotes,
            "bars": {
                symbol: {
                    timeframe: [
                        bar.serialize()
                        for bar in self.aggregator.bars(
                            symbol,
                            timeframe,
                        )
                    ]
                    for timeframe in ("1m", "5m", "15m")
                }
                for symbol in symbols
            },
            "fills": self.execution.fills,
            "event_order_digest": self.processed_digest.hexdigest(),
        }

    def verify_determinism(
        self,
        session_id: str,
        *,
        runs: int = 3,
    ) -> dict[str, Any]:
        digests = []
        snapshots = []
        events = self._load(session_id)
        for _ in range(max(1, runs)):
            result = self._run_loaded_to_completion(
                session_id,
                events,
            )
            digests.append(result["digest_sha256"])
            snapshots.append(
                hashlib.sha256(
                    _stable(self._state_snapshot()).encode()
                ).hexdigest()
            )
        return {
            "session_id": session_id,
            "runs": len(digests),
            "event_digests": digests,
            "state_digests": snapshots,
            "deterministic": (
                len(set(digests)) == 1 and len(set(snapshots)) == 1
            ),
        }

    def verify_bars(self, session_id: str) -> dict[str, Any]:
        events = self._load(session_id)
        provider: dict[tuple[str, datetime], dict[str, Any]] = {}
        trades: dict[tuple[str, datetime], list[dict[str, Any]]] = {}
        provider_aggregator = BarAggregator()
        duplicates = 0
        seen: set[str] = set()
        incomplete_expected: set[tuple[str, datetime]] = set()
        for event in events:
            identity = hashlib.sha256(
                _stable(
                    {
                        "provider_timestamp": event.get("provider_timestamp"),
                        "symbol": event.get("symbol"),
                        "event_type": event.get("event_type"),
                        "payload": event.get("payload"),
                    }
                ).encode()
            ).hexdigest()
            if identity in seen or event.get("disposition") == "duplicate":
                duplicates += 1
            seen.add(identity)
            symbol = str(event.get("symbol") or "").upper()
            timestamp = _provider_time(event).replace(
                second=0,
                microsecond=0,
            )
            if (
                event.get("event_type") == "bar_1m"
                and event.get("disposition") == "accepted"
            ):
                provider[(symbol, timestamp)] = event["payload"]
                payload = event["payload"]
                received_at = _time(event.get("receipt_timestamp"))
                completeness = (
                    Completeness.CLOSED
                    if received_at >= timestamp + timedelta(minutes=1)
                    else Completeness.INCOMPLETE
                )
                if completeness == Completeness.INCOMPLETE:
                    incomplete_expected.add((symbol, timestamp))
                provider_aggregator.add_minute_bar(
                    Bar(
                        ticker=symbol,
                        timeframe="1m",
                        open=float(payload["o"]),
                        high=float(payload["h"]),
                        low=float(payload["l"]),
                        close=float(payload["c"]),
                        volume=float(payload["v"]),
                        vwap=(
                            float(payload["vw"])
                            if payload.get("vw") is not None
                            else None
                        ),
                        timestamp=timestamp,
                        source=str(event.get("source", "alpaca_iex")),
                        completeness=completeness,
                    ),
                    received_at=max(
                        received_at,
                        timestamp + timedelta(minutes=1),
                    ),
                    historical_backfill=True,
                )
            elif (
                event.get("event_type") == "trade"
                and event.get("disposition") == "accepted"
            ):
                trades.setdefault((symbol, timestamp), []).append(
                    event["payload"]
                )
        provider_replay_mismatches = []
        replayed = {
            (bar.ticker, bar.timestamp): bar
            for symbol in {key[0] for key in provider}
            for bar in provider_aggregator.bars(symbol, "1m")
        }
        for key, payload in provider.items():
            bar = replayed.get(key)
            differences = {}
            if bar is None:
                differences["bar"] = {
                    "provider": "present",
                    "rebuilt": "missing",
                }
            else:
                fields = {
                    "o": bar.open,
                    "h": bar.high,
                    "l": bar.low,
                    "c": bar.close,
                    "v": bar.volume,
                    "vw": bar.vwap,
                }
                differences = {
                    field: {
                        "provider": payload.get(field),
                        "rebuilt": fields[field],
                    }
                    for field in fields
                    if payload.get(field) is not None
                    and (
                        fields[field] is None
                        or abs(
                            float(payload[field])
                            - float(fields[field])
                        )
                        > 1e-6
                    )
                }
            if differences:
                provider_replay_mismatches.append(
                    {
                        "symbol": key[0],
                        "timestamp": key[1].isoformat(),
                        "differences": differences,
                    }
                )
        trade_mismatches = []
        missing = []
        for key, bar in provider.items():
            ticks = trades.get(key, [])
            if not ticks:
                missing.append(
                    {"symbol": key[0], "timestamp": key[1].isoformat()}
                )
                continue
            prices = [float(tick["p"]) for tick in ticks]
            sizes = [float(tick["s"]) for tick in ticks]
            rebuilt = {
                "o": prices[0],
                "h": max(prices),
                "l": min(prices),
                "c": prices[-1],
                "v": sum(sizes),
                "vw": (
                    sum(price * size for price, size in zip(prices, sizes))
                    / sum(sizes)
                    if sum(sizes) > 0
                    else None
                ),
            }
            differences = {
                field: {
                    "provider": bar.get(field),
                    "rebuilt": rebuilt[field],
                }
                for field in ("o", "h", "l", "c", "v", "vw")
                if bar.get(field) is not None
                and abs(float(bar[field]) - float(rebuilt[field])) > 1e-6
            }
            if differences:
                trade_mismatches.append(
                    {
                        "symbol": key[0],
                        "timestamp": key[1].isoformat(),
                        "differences": differences,
                    }
                )
        return {
            "session_id": session_id,
            "provider_bars": len(provider),
            "rebuilt_trade_bars": len(trades),
            "bar_mismatches": provider_replay_mismatches,
            "trade_reconstruction_mismatches": trade_mismatches,
            "missing_trade_intervals": missing,
            "duplicate_events": duplicates,
            "incomplete_bars_treated_as_closed": sum(
                replayed.get(key) is not None
                and replayed[key].completeness == Completeness.CLOSED
                for key in incomplete_expected
            ),
            "rebuilt_5m_bars": sum(
                len(provider_aggregator.bars(symbol, "5m"))
                for symbol in {key[0] for key in provider}
            ),
            "rebuilt_15m_bars": sum(
                len(provider_aggregator.bars(symbol, "15m"))
                for symbol in {key[0] for key in provider}
            ),
        }
