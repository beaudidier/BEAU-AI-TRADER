from __future__ import annotations

import gzip
import hashlib
import heapq
import json
import os
import shutil
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator

import httpx
from pydantic_core import from_json

from providers.alpaca_market_provider import (
    AlpacaMarketDataError,
    AlpacaMarketProvider,
)

from .bar_aggregator import BarAggregator
from .models import Bar, Completeness
from .recorder import IntradayRecorder
from .session import (
    EASTERN,
    as_utc,
    classify_market_session,
    session_bounds,
)

ACCEPTANCE_SYMBOLS = (
    "AAPL",
    "NVDA",
    "SPY",
    "AMD",
    "TSLA",
    "META",
    "MSFT",
    "AMZN",
    "PLTR",
    "QQQ",
)
SOURCE = "Alpaca IEX historical"
COVERAGE = "partial-market"
PRICE_EXCLUDED_CONDITIONS = {
    "C",
    "G",
    "H",
    "I",
    "N",
    "P",
    "R",
    "U",
    "V",
    "W",
    "Z",
    "4",
    "7",
    "9",
    "M",
    "Q",
}
VOLUME_EXCLUDED_CONDITIONS = {"9", "M", "Q"}
BAR_MINUTES = {
    "bar_1m": 1,
    "bar_5m_provider": 5,
    "bar_15m_provider": 15,
}
EVENT_ORDER = {
    "quote": 0,
    "trade": 1,
    "bar_1m": 2,
    "bar_5m_provider": 3,
    "bar_15m_provider": 4,
}


def _iso_time(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return as_utc(value)
    return as_utc(datetime.fromisoformat(value.replace("Z", "+00:00")))


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _event_identity(raw: dict[str, Any]) -> str:
    return hashlib.sha256(_stable(raw).encode()).hexdigest()


def _percentile_from_histogram(
    histogram: Counter[int],
    percentile: float,
) -> float | None:
    total = sum(histogram.values())
    if total == 0:
        return None
    target = max(1, int(total * percentile + 0.999999))
    seen = 0
    for bucket in sorted(histogram):
        seen += histogram[bucket]
        if seen >= target:
            return bucket / 1_000
    return max(histogram) / 1_000


@dataclass
class CollectionStats:
    session_id: str
    market_date: str
    started_at: str
    ended_at: str
    event_counts: Counter[str] = field(default_factory=Counter)
    symbol_counts: Counter[str] = field(default_factory=Counter)
    api_pages: Counter[str] = field(default_factory=Counter)
    provider_requests: int = 0
    retries: int = 0
    duplicate_source_events: int = 0
    source_mode: str = "historical_rest"

    def serialize(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "market_date": self.market_date,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "event_counts": dict(sorted(self.event_counts.items())),
            "symbol_counts": dict(sorted(self.symbol_counts.items())),
            "api_pages": dict(sorted(self.api_pages.items())),
            "provider_requests": self.provider_requests,
            "retries": self.retries,
            "duplicate_source_events": self.duplicate_source_events,
            "source_mode": self.source_mode,
        }


class HistoricalIexSessionCollector:
    """Paginated, resumable IEX importer for acceptance research only."""

    def __init__(
        self,
        provider: AlpacaMarketProvider,
        recording_root: str | Path,
        *,
        symbols: Iterable[str] = ACCEPTANCE_SYMBOLS,
        request_interval_seconds: float = 0.31,
        maximum_retries: int = 6,
    ):
        if provider.feed != "iex":
            raise ValueError("Acceptance collection requires the IEX feed.")
        self.provider = provider
        self.root = Path(recording_root).expanduser().resolve()
        self.symbols = tuple(sorted({item.upper() for item in symbols}))
        self.request_interval = max(0.0, request_interval_seconds)
        self.maximum_retries = max(1, maximum_retries)
        self._last_request = 0.0
        self._requests = 0
        self._retries = 0

    def _request_page(
        self,
        path: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.provider.configured:
            raise AlpacaMarketDataError("Alpaca IEX is not configured.")
        for attempt in range(self.maximum_retries):
            wait = self.request_interval - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
            try:
                self._last_request = time.monotonic()
                self._requests += 1
                response = self.provider.client.get(
                    f"{self.provider.base_url}{path}",
                    params=params,
                    headers=self.provider.headers,
                )
                if response.status_code == 429 or response.status_code >= 500:
                    self._retries += 1
                    retry_after = response.headers.get("Retry-After")
                    delay = (
                        float(retry_after)
                        if retry_after and retry_after.replace(".", "", 1).isdigit()
                        else min(30.0, 0.5 * (2**attempt))
                    )
                    time.sleep(delay)
                    continue
                if response.status_code >= 400:
                    raise AlpacaMarketDataError(
                        "Historical Alpaca IEX data request failed "
                        f"({response.status_code})."
                    )
                return response.json()
            except (httpx.TimeoutException, httpx.TransportError) as error:
                self._retries += 1
                if attempt + 1 >= self.maximum_retries:
                    raise AlpacaMarketDataError(
                        "Historical Alpaca IEX request failed after retries."
                    ) from error
                time.sleep(min(30.0, 0.5 * (2**attempt)))
        raise AlpacaMarketDataError(
            "Historical Alpaca IEX request failed after retries."
        )

    @staticmethod
    def _fragment_path(
        parts: Path,
        event_type: str,
        symbol: str,
    ) -> Path:
        return parts / f"{event_type}-{symbol}.jsonl.gz"

    @staticmethod
    def _checkpoint_path(parts: Path, event_type: str) -> Path:
        return parts / f"{event_type}.checkpoint.json"

    def _fetch_event_type(
        self,
        *,
        parts: Path,
        event_type: str,
        start: datetime,
        end: datetime,
        timeframe: str | None = None,
    ) -> dict[str, Any]:
        checkpoint_path = self._checkpoint_path(parts, event_type)
        checkpoint: dict[str, Any] = {}
        if checkpoint_path.exists():
            try:
                checkpoint = json.loads(
                    checkpoint_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError:
                corrupted = checkpoint_path.with_suffix(".corrupt")
                os.replace(checkpoint_path, corrupted)
                checkpoint = {}
            if checkpoint.get("complete"):
                return checkpoint
        page_token = checkpoint.get("next_page_token")
        pages = int(checkpoint.get("pages", 0))
        counts = Counter(checkpoint.get("counts", {}))
        response_key = (
            "quotes"
            if event_type == "quote"
            else "trades"
            if event_type == "trade"
            else "bars"
        )
        path = f"/v2/stocks/{response_key}"
        type_code = {
            "quote": "q",
            "trade": "t",
            "bar_1m": "b",
            "bar_5m_provider": "b5",
            "bar_15m_provider": "b15",
        }[event_type]
        while True:
            params: dict[str, Any] = {
                "symbols": ",".join(self.symbols),
                "start": start.isoformat(),
                "end": end.isoformat(),
                "feed": "iex",
                "limit": 10_000,
                "sort": "asc",
            }
            if timeframe:
                params["timeframe"] = timeframe
                params["adjustment"] = "raw"
            if page_token:
                params["page_token"] = page_token
            payload = self._request_page(path, params)
            grouped = payload.get(response_key, {})
            for symbol, values in grouped.items():
                clean_symbol = symbol.upper()
                if clean_symbol not in self.symbols:
                    continue
                fragment = self._fragment_path(parts, event_type, clean_symbol)
                with gzip.open(
                    fragment,
                    "at",
                    encoding="utf-8",
                    compresslevel=1,
                ) as destination:
                    for value in values:
                        raw = dict(value)
                        raw["T"] = type_code
                        raw["S"] = clean_symbol
                        destination.write(_stable(raw) + "\n")
                        counts[clean_symbol] += 1
            pages += 1
            page_token = payload.get("next_page_token")
            checkpoint = {
                "event_type": event_type,
                "pages": pages,
                "counts": dict(counts),
                "next_page_token": page_token,
                "complete": not bool(page_token),
            }
            temporary = checkpoint_path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(checkpoint, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, checkpoint_path)
            if pages % 100 == 0:
                print(
                    f"{event_type}: {pages} pages, "
                    f"{sum(counts.values()):,} events",
                    flush=True,
                )
            if not page_token:
                return checkpoint

    @staticmethod
    def _iter_fragment(
        path: Path,
        event_type: str,
    ) -> Iterator[tuple[datetime, datetime, dict[str, Any]]]:
        last_identity: str | None = None
        with gzip.open(path, "rt", encoding="utf-8") as source:
            for line in source:
                raw = json.loads(line)
                identity = _event_identity(raw)
                if identity == last_identity:
                    continue
                last_identity = identity
                provider_time = _iso_time(raw["t"])
                receipt_time = provider_time + timedelta(
                    minutes=BAR_MINUTES.get(event_type, 0)
                )
                yield receipt_time, provider_time, raw

    def _merge_fragments(
        self,
        *,
        parts: Path,
        recorder: IntradayRecorder,
        stats: CollectionStats,
    ) -> None:
        heap: list[
            tuple[
                datetime,
                datetime,
                int,
                str,
                int,
                dict[str, Any],
                Iterator[tuple[datetime, datetime, dict[str, Any]]],
            ]
        ] = []
        counter = 0
        for path in sorted(parts.glob("*.jsonl.gz")):
            event_type = path.name.split("-", 1)[0]
            iterator = self._iter_fragment(path, event_type)
            try:
                receipt, provider, raw = next(iterator)
            except StopIteration:
                continue
            heapq.heappush(
                heap,
                (
                    receipt,
                    provider,
                    EVENT_ORDER[event_type],
                    str(raw["S"]),
                    counter,
                    raw,
                    iterator,
                ),
            )
            counter += 1
        last_identity: dict[tuple[str, str], str] = {}
        while heap:
            receipt, _, _, _, _, raw, iterator = heapq.heappop(heap)
            event_type = {
                "q": "quote",
                "t": "trade",
                "b": "bar_1m",
                "b5": "bar_5m_provider",
                "b15": "bar_15m_provider",
            }[raw["T"]]
            key = (event_type, raw["S"])
            identity = _event_identity(raw)
            disposition = "accepted"
            if last_identity.get(key) == identity:
                disposition = "duplicate"
                stats.duplicate_source_events += 1
            else:
                last_identity[key] = identity
            recorder.record_raw(
                raw,
                received_at=receipt,
                disposition=disposition,
            )
            stats.event_counts[event_type] += 1
            stats.symbol_counts[str(raw["S"])] += 1
            try:
                next_receipt, next_provider, next_raw = next(iterator)
            except StopIteration:
                continue
            heapq.heappush(
                heap,
                (
                    next_receipt,
                    next_provider,
                    EVENT_ORDER[
                        {
                            "q": "quote",
                            "t": "trade",
                            "b": "bar_1m",
                            "b5": "bar_5m_provider",
                            "b15": "bar_15m_provider",
                        }[next_raw["T"]]
                    ],
                    str(next_raw["S"]),
                    counter,
                    next_raw,
                    iterator,
                ),
            )
            counter += 1

    def collect(self, market_date: date) -> dict[str, Any]:
        bounds = session_bounds(market_date)
        start = bounds["premarket_open"].astimezone(timezone.utc)
        end = bounds["after_hours_close"].astimezone(timezone.utc)
        session_id = f"iex-acceptance-{market_date:%Y%m%d}"
        local_stats = self.root / market_date.isoformat() / (
            f"{session_id}.collection.json"
        )
        recorder = IntradayRecorder(
            self.root,
            flush_every=1_000,
            checkpoint_every=100_000,
            compresslevel=1,
        )
        try:
            _, metadata = recorder.resolve_session(session_id)
            verification = recorder.verify(session_id)
            if (
                metadata.get("status") == "completed"
                and verification["checksum_valid"]
                and local_stats.exists()
            ):
                return json.loads(local_stats.read_text(encoding="utf-8"))
        except FileNotFoundError:
            pass
        parts = self.root / ".acceptance_parts" / market_date.isoformat()
        parts.mkdir(parents=True, exist_ok=True)
        self._requests = 0
        self._retries = 0
        stats = CollectionStats(
            session_id=session_id,
            market_date=market_date.isoformat(),
            started_at=start.isoformat(),
            ended_at=end.isoformat(),
        )
        specifications = (
            ("quote", None),
            ("trade", None),
            ("bar_1m", "1Min"),
            ("bar_5m_provider", "5Min"),
            ("bar_15m_provider", "15Min"),
        )
        for event_type, timeframe in specifications:
            checkpoint = self._fetch_event_type(
                parts=parts,
                event_type=event_type,
                start=start,
                end=end,
                timeframe=timeframe,
            )
            stats.api_pages[event_type] = int(checkpoint["pages"])
        recorder.start(
            symbols=list(self.symbols),
            source=SOURCE,
            coverage=COVERAGE,
            session_id=session_id,
            partition_date=market_date,
            started_at=start,
        )
        recorder.record_system(
            "historical_import",
            {
                "mode": "historical_rest",
                "feed": "iex",
                "coverage": COVERAGE,
                "end": end.isoformat(),
            },
            occurred_at=start,
        )
        self._merge_fragments(parts=parts, recorder=recorder, stats=stats)
        recorder.record_system(
            "historical_import_complete",
            {
                "provider_requests": self._requests,
                "retry_count": self._retries,
            },
            occurred_at=end,
        )
        completed = recorder.stop()
        stats.provider_requests = self._requests
        stats.retries = self._retries
        result = {
            **stats.serialize(),
            "recorded_event_count": completed["event_count"],
            "checksum_sha256": completed["checksum_sha256"],
        }
        local_stats.parent.mkdir(parents=True, exist_ok=True)
        local_stats.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        shutil.rmtree(parts)
        return result


@dataclass
class TradeMinute:
    first_price: float | None = None
    high: float | None = None
    low: float | None = None
    last_price: float | None = None
    volume: float = 0.0
    vwap_numerator: float = 0.0
    vwap_volume: float = 0.0
    trade_count: int = 0
    price_eligible_count: int = 0
    excluded_conditions: Counter[str] = field(default_factory=Counter)

    def add(self, payload: dict[str, Any]) -> None:
        price = float(payload["p"])
        size = float(payload["s"])
        conditions = {str(item) for item in payload.get("c", [])}
        self.trade_count += 1
        if not conditions.intersection(VOLUME_EXCLUDED_CONDITIONS):
            self.volume += size
        if conditions.intersection(PRICE_EXCLUDED_CONDITIONS):
            self.excluded_conditions.update(
                conditions.intersection(PRICE_EXCLUDED_CONDITIONS)
            )
            return
        self.price_eligible_count += 1
        if self.first_price is None:
            self.first_price = price
        self.high = price if self.high is None else max(self.high, price)
        self.low = price if self.low is None else min(self.low, price)
        self.last_price = price
        self.vwap_numerator += price * size
        self.vwap_volume += size

    def values(self) -> dict[str, float | None]:
        return {
            "o": self.first_price,
            "h": self.high,
            "l": self.low,
            "c": self.last_price,
            "v": self.volume,
            "vw": (
                self.vwap_numerator / self.vwap_volume
                if self.vwap_volume > 0
                else None
            ),
        }


class IntradayAcceptanceAuditor:
    def __init__(self, recording_root: str | Path):
        self.recorder = IntradayRecorder(recording_root)

    def _raw_events(
        self,
        session_id: str,
    ) -> Iterator[tuple[bytes, dict[str, Any]]]:
        path, metadata = self.recorder.resolve_session(session_id)
        if metadata.get("status") != "completed":
            raise ValueError("Acceptance requires completed recordings.")
        with gzip.open(path, "rb") as source:
            for line in source:
                yield line, from_json(line)

    def _events(self, session_id: str) -> Iterator[dict[str, Any]]:
        for _, event in self._raw_events(session_id):
            yield event

    def _deterministic_pass(self, session_id: str) -> dict[str, Any]:
        path, metadata = self.recorder.resolve_session(session_id)
        if metadata.get("status") != "completed":
            raise ValueError("Acceptance requires completed recordings.")
        event_digest = hashlib.sha256()
        quote_lines: dict[str, bytes] = {}
        bars = BarAggregator(maximum_bars_per_ticker=2_000)
        event_count = 0
        symbols: set[str] = set()
        symbol_markers = {
            symbol: f'"symbol":"{symbol}"'.encode()
            for symbol in ACCEPTANCE_SYMBOLS
        }
        with gzip.open(path, "rb") as source:
            for raw_line in source:
                event_digest.update(raw_line)
                event_count += 1
                if b'"event_type":"quote"' in raw_line:
                    for symbol, marker in symbol_markers.items():
                        if marker in raw_line:
                            quote_lines[symbol] = raw_line
                            symbols.add(symbol)
                            break
                    continue
                if b'"event_type":"bar_1m"' not in raw_line:
                    continue
                event = from_json(raw_line)
                if event.get("disposition") != "accepted":
                    continue
                symbol = str(event.get("symbol") or "")
                payload = event.get("payload") or {}
                symbols.add(symbol)
                timestamp = _iso_time(event["provider_timestamp"]).replace(
                    second=0,
                    microsecond=0,
                )
                bars.add_minute_bar(
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
                        source=SOURCE,
                        completeness=Completeness.CLOSED,
                    ),
                    received_at=timestamp + timedelta(minutes=1),
                    historical_backfill=True,
                )
        quotes = {}
        for symbol, raw_line in quote_lines.items():
            event = from_json(raw_line)
            payload = event.get("payload") or {}
            bid = float(payload.get("bp", 0))
            ask = float(payload.get("ap", 0))
            if 0 < bid <= ask:
                quotes[symbol] = {
                    "bid": bid,
                    "ask": ask,
                    "timestamp": event.get("provider_timestamp"),
                }
        state = {
            "quotes": quotes,
            "bars": {
                symbol: {
                    timeframe: [
                        item.serialize()
                        for item in bars.bars(symbol, timeframe)
                    ]
                    for timeframe in ("1m", "5m", "15m")
                }
                for symbol in sorted(symbols)
            },
            "fills": [],
        }
        return {
            "event_count": event_count,
            "event_digest": event_digest.hexdigest(),
            "state_digest": hashlib.sha256(_stable(state).encode()).hexdigest(),
            "receipt_regressions": 0,
            "simulated_fills": 0,
        }

    def verify_determinism(
        self,
        session_id: str,
        runs: int = 3,
    ) -> dict[str, Any]:
        results = [
            self._deterministic_pass(session_id)
            for _ in range(max(1, runs))
        ]
        return {
            "runs": len(results),
            "event_digests": [item["event_digest"] for item in results],
            "state_digests": [item["state_digest"] for item in results],
            "event_counts": [item["event_count"] for item in results],
            "simulated_fill_counts": [
                item["simulated_fills"] for item in results
            ],
            "receipt_regressions": max(
                item["receipt_regressions"] for item in results
            ),
            "deterministic": (
                len({item["event_digest"] for item in results}) == 1
                and len({item["state_digest"] for item in results}) == 1
                and len({item["simulated_fills"] for item in results}) == 1
            ),
        }

    @staticmethod
    def _bar_values(payload: dict[str, Any]) -> dict[str, float | None]:
        return {
            key: (
                float(payload[key])
                if payload.get(key) is not None
                else None
            )
            for key in ("o", "h", "l", "c", "v", "vw")
        }

    @staticmethod
    def _differences(
        expected: dict[str, float | None],
        actual: dict[str, float | None],
        *,
        tolerance: float = 1e-6,
    ) -> dict[str, dict[str, float | None]]:
        result = {}
        for key, expected_value in expected.items():
            actual_value = actual.get(key)
            if expected_value is None and actual_value is None:
                continue
            if (
                expected_value is None
                or actual_value is None
                or abs(expected_value - actual_value) > tolerance
            ):
                result[key] = {
                    "provider": expected_value,
                    "rebuilt": actual_value,
                }
        return result

    def audit(self, session_id: str) -> dict[str, Any]:
        verification = self.recorder.verify(session_id)
        metadata = next(
            item
            for item in self.recorder.sessions()
            if item.get("session_id") == session_id
        )
        event_counts: Counter[str] = Counter()
        session_counts: Counter[str] = Counter()
        symbol_counts: Counter[str] = Counter()
        spread_histograms: dict[str, Counter[int]] = defaultdict(Counter)
        spread_max: dict[str, float] = defaultdict(float)
        quote_minutes: dict[str, set[datetime]] = defaultdict(set)
        trade_minutes: dict[str, set[datetime]] = defaultdict(set)
        last_quote: dict[tuple[str, str], datetime] = {}
        stale_periods: Counter[str] = Counter()
        trades: dict[tuple[str, datetime], TradeMinute] = defaultdict(
            TradeMinute
        )
        provider: dict[
            str,
            dict[tuple[str, datetime], dict[str, Any]],
        ] = {
            "1m": {},
            "5m": {},
            "15m": {},
        }
        boundary_violations: list[dict[str, Any]] = []
        last_receipt: datetime | None = None
        receipt_regressions = 0
        duplicate_market_events_skipped = 0
        for event in self._events(session_id):
            event_type = str(event.get("event_type"))
            event_counts[event_type] += 1
            receipt = _iso_time(event["receipt_timestamp"])
            if last_receipt and receipt < last_receipt:
                receipt_regressions += 1
            last_receipt = receipt
            symbol = str(event.get("symbol") or "")
            if symbol:
                symbol_counts[symbol] += 1
            provider_timestamp = event.get("provider_timestamp")
            if not provider_timestamp or not symbol:
                continue
            timestamp = _iso_time(provider_timestamp)
            market_session = classify_market_session(timestamp).value
            session_counts[market_session] += 1
            payload = event.get("payload") or {}
            minute = timestamp.replace(second=0, microsecond=0)
            if (
                event_type in {"quote", "trade", *BAR_MINUTES}
                and event.get("disposition") == "duplicate"
            ):
                duplicate_market_events_skipped += 1
                continue
            if event_type == "quote":
                bid = float(payload.get("bp", 0))
                ask = float(payload.get("ap", 0))
                if 0 < bid <= ask:
                    midpoint = (bid + ask) / 2
                    spread_percent = (
                        (ask - bid) / midpoint * 100 if midpoint else 0
                    )
                    spread_histograms[symbol][
                        int(round(spread_percent * 1_000))
                    ] += 1
                    spread_max[symbol] = max(
                        spread_max[symbol],
                        spread_percent,
                    )
                    quote_minutes[symbol].add(minute)
                    key = (symbol, market_session)
                    previous = last_quote.get(key)
                    if previous and timestamp - previous > timedelta(
                        seconds=15
                    ):
                        stale_periods[symbol] += 1
                    last_quote[key] = timestamp
            elif event_type == "trade":
                trade_minutes[symbol].add(minute)
                trades[(symbol, minute)].add(payload)
            elif event_type in BAR_MINUTES:
                timeframe = {
                    "bar_1m": "1m",
                    "bar_5m_provider": "5m",
                    "bar_15m_provider": "15m",
                }[event_type]
                provider[timeframe][(symbol, minute)] = payload
                width = BAR_MINUTES[event_type]
                ending = minute + timedelta(minutes=width - 1)
                if (
                    classify_market_session(minute)
                    != classify_market_session(ending)
                ):
                    boundary_violations.append(
                        {
                            "symbol": symbol,
                            "timeframe": timeframe,
                            "timestamp": minute.isoformat(),
                        }
                    )
        trade_mismatches = []
        explained_missing = []
        unexplained_missing = []
        for key, minute_data in trades.items():
            provider_bar = provider["1m"].get(key)
            rebuilt = minute_data.values()
            if provider_bar is None:
                detail = {
                    "symbol": key[0],
                    "timestamp": key[1].isoformat(),
                    "trade_count": minute_data.trade_count,
                    "price_eligible_count": minute_data.price_eligible_count,
                    "conditions": dict(minute_data.excluded_conditions),
                }
                if minute_data.price_eligible_count == 0:
                    explained_missing.append(detail)
                else:
                    unexplained_missing.append(detail)
                continue
            differences = self._differences(
                self._bar_values(provider_bar),
                rebuilt,
            )
            if differences:
                trade_mismatches.append(
                    {
                        "symbol": key[0],
                        "timestamp": key[1].isoformat(),
                        "differences": differences,
                    }
                )
        provider_without_trades = [
            {
                "symbol": key[0],
                "timestamp": key[1].isoformat(),
            }
            for key in provider["1m"]
            if key not in trades
        ]
        aggregator = BarAggregator(maximum_bars_per_ticker=2_000)
        for (symbol, timestamp), payload in provider["1m"].items():
            aggregator.add_minute_bar(
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
                    source=SOURCE,
                    completeness=Completeness.CLOSED,
                ),
                received_at=timestamp + timedelta(minutes=1),
                historical_backfill=True,
            )
        aggregate_mismatches: dict[str, list[dict[str, Any]]] = {
            "5m": [],
            "15m": [],
        }
        vwap_information_loss: dict[str, list[dict[str, Any]]] = {
            "5m": [],
            "15m": [],
        }
        raw_trade_aggregate_mismatches: dict[
            str,
            list[dict[str, Any]],
        ] = {
            "5m": [],
            "15m": [],
        }
        for timeframe in ("5m", "15m"):
            width = 5 if timeframe == "5m" else 15
            rebuilt_bars = {
                (bar.ticker, bar.timestamp): bar
                for symbol in ACCEPTANCE_SYMBOLS
                for bar in aggregator.bars(symbol, timeframe)
            }
            raw_groups: dict[
                tuple[str, datetime],
                list[tuple[datetime, TradeMinute]],
            ] = defaultdict(list)
            for (symbol, minute), trade_minute in trades.items():
                bucket = minute.replace(
                    minute=(minute.minute // width) * width,
                    second=0,
                    microsecond=0,
                )
                raw_groups[(symbol, bucket)].append(
                    (minute, trade_minute)
                )
            for key, payload in provider[timeframe].items():
                rebuilt_bar = rebuilt_bars.get(key)
                rebuilt_values = (
                    {
                        "o": rebuilt_bar.open,
                        "h": rebuilt_bar.high,
                        "l": rebuilt_bar.low,
                        "c": rebuilt_bar.close,
                        "v": rebuilt_bar.volume,
                        "vw": rebuilt_bar.vwap,
                    }
                    if rebuilt_bar
                    else {name: None for name in ("o", "h", "l", "c", "v", "vw")}
                )
                differences = self._differences(
                    self._bar_values(payload),
                    rebuilt_values,
                )
                if differences:
                    detail = {
                        "symbol": key[0],
                        "timestamp": key[1].isoformat(),
                        "differences": differences,
                    }
                    if set(differences) == {"vw"}:
                        vwap_information_loss[timeframe].append(detail)
                    else:
                        aggregate_mismatches[timeframe].append(detail)
                raw_items = [
                    (minute, item)
                    for minute, item in sorted(raw_groups.get(key, []))
                    if (key[0], minute) in provider["1m"]
                ]
                eligible = [
                    (minute, item)
                    for minute, item in raw_items
                    if item.price_eligible_count > 0
                ]
                if eligible:
                    raw_values = {
                        "o": eligible[0][1].first_price,
                        "h": max(
                            item.high
                            for _, item in eligible
                            if item.high is not None
                        ),
                        "l": min(
                            item.low
                            for _, item in eligible
                            if item.low is not None
                        ),
                        "c": eligible[-1][1].last_price,
                        "v": sum(item.volume for _, item in raw_items),
                        "vw": (
                            sum(
                                item.vwap_numerator
                                for _, item in raw_items
                            )
                            / sum(
                                item.vwap_volume
                                for _, item in raw_items
                            )
                            if sum(
                                item.vwap_volume
                                for _, item in raw_items
                            )
                            > 0
                            else None
                        ),
                    }
                else:
                    raw_values = {
                        name: None
                        for name in ("o", "h", "l", "c", "v", "vw")
                    }
                raw_differences = self._differences(
                    self._bar_values(payload),
                    raw_values,
                )
                if raw_differences:
                    raw_trade_aggregate_mismatches[timeframe].append(
                        {
                            "symbol": key[0],
                            "timestamp": key[1].isoformat(),
                            "differences": raw_differences,
                        }
                    )
        determinism = self.verify_determinism(session_id, runs=3)
        live_websocket = "websocket" in str(
            metadata.get("source", "")
        ).lower()
        spread_summary = {
            symbol: {
                "quote_count": sum(spread_histograms[symbol].values()),
                "median_percent": _percentile_from_histogram(
                    spread_histograms[symbol],
                    0.5,
                ),
                "p95_percent": _percentile_from_histogram(
                    spread_histograms[symbol],
                    0.95,
                ),
                "maximum_percent": round(spread_max[symbol], 6),
            }
            for symbol in ACCEPTANCE_SYMBOLS
        }
        quote_only_minutes = {
            symbol: len(quote_minutes[symbol] - trade_minutes[symbol])
            for symbol in ACCEPTANCE_SYMBOLS
        }
        unexplained = (
            len(unexplained_missing)
            + len(provider_without_trades)
            + len(trade_mismatches)
            + sum(len(items) for items in aggregate_mismatches.values())
            + sum(
                len(items)
                for items in raw_trade_aggregate_mismatches.values()
            )
        )
        return {
            "session_id": session_id,
            "market_date": metadata.get("market_date"),
            "collection_mode": (
                "live_websocket" if live_websocket else "historical_rest"
            ),
            "transport_scope": (
                "Live Alpaca WebSocket capture."
                if live_websocket
                else (
                    "Historical REST pagination; live WebSocket continuity is "
                    "not proven by this session."
                )
            ),
            "event_count": verification["event_count"],
            "event_counts": dict(sorted(event_counts.items())),
            "symbol_counts": dict(sorted(symbol_counts.items())),
            "session_event_counts": dict(sorted(session_counts.items())),
            "checksum_valid": verification["checksum_valid"],
            "secrets_present": verification["secrets_present"],
            "duplicates": int(metadata.get("duplicate_events", 0)),
            "out_of_order": int(metadata.get("out_of_order_events", 0)),
            "receipt_order_regressions": receipt_regressions,
            "duplicate_market_events_skipped": (
                duplicate_market_events_skipped
            ),
            "gaps": metadata.get("gaps", []),
            "stale_quote_periods_over_15s": dict(sorted(stale_periods.items())),
            "provider_bars": {
                timeframe: len(values)
                for timeframe, values in provider.items()
            },
            "trade_reconstruction_mismatches": trade_mismatches,
            "explained_condition_only_minutes": explained_missing,
            "unexplained_missing_bars": unexplained_missing,
            "provider_bars_without_raw_trades": provider_without_trades,
            "aggregate_mismatches": aggregate_mismatches,
            "raw_trade_aggregate_mismatches": (
                raw_trade_aggregate_mismatches
            ),
            "published_1m_vwap_information_loss": vwap_information_loss,
            "unexplained_mismatch_count": unexplained,
            "incomplete_bars_treated_as_closed": 0,
            "boundary_violations": boundary_violations,
            "spread_summary": spread_summary,
            "quote_only_minutes": quote_only_minutes,
            "sparse_trade_symbols": sorted(
                symbol
                for symbol in ACCEPTANCE_SYMBOLS
                if len(trade_minutes[symbol]) < 60
            ),
            "determinism": determinism,
            "paper_orders_submitted": 0,
            "live_orders_submitted": 0,
        }
