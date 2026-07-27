from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from threading import RLock

from .models import Bar, Completeness
from .session import as_utc

SUPPORTED_TIMEFRAMES = {"1m": 1, "5m": 5, "15m": 15}


class BarAggregator:
    def __init__(
        self,
        *,
        future_tolerance_seconds: int = 2,
        maximum_bars_per_ticker: int = 2_000,
    ):
        self.future_tolerance = timedelta(seconds=future_tolerance_seconds)
        self.maximum_bars_per_ticker = maximum_bars_per_ticker
        self._minutes: dict[str, dict[datetime, Bar]] = defaultdict(dict)
        self._event_keys: set[tuple[str, datetime]] = set()
        self._lock = RLock()
        self.duplicates = 0
        self.out_of_order = 0
        self.invalid = 0
        self.gaps: dict[str, list[dict[str, str]]] = defaultdict(list)

    def add_minute_bar(
        self,
        bar: Bar,
        *,
        received_at: datetime | None = None,
    ) -> bool:
        now = as_utc(received_at or datetime.now(timezone.utc))
        timestamp = as_utc(bar.timestamp).replace(second=0, microsecond=0)
        if (
            bar.timeframe != "1m"
            or min(bar.open, bar.high, bar.low, bar.close) <= 0
            or bar.volume < 0
            or bar.high < max(bar.open, bar.close, bar.low)
            or bar.low > min(bar.open, bar.close, bar.high)
            or timestamp > now + self.future_tolerance
        ):
            self.invalid += 1
            raise ValueError("Invalid or future one-minute bar.")
        ticker = bar.ticker.upper()
        key = (ticker, timestamp)
        with self._lock:
            if key in self._event_keys:
                self.duplicates += 1
                return False
            existing = self._minutes[ticker]
            if existing:
                latest = max(existing)
                if timestamp < latest:
                    self.out_of_order += 1
                    return False
                if timestamp > latest + timedelta(minutes=1):
                    self.gaps[ticker].append(
                        {
                            "from": (latest + timedelta(minutes=1)).isoformat(),
                            "to": (timestamp - timedelta(minutes=1)).isoformat(),
                        }
                    )
            existing[timestamp] = Bar(
                ticker=ticker,
                timeframe="1m",
                open=bar.open,
                high=bar.high,
                low=bar.low,
                close=bar.close,
                volume=bar.volume,
                vwap=bar.vwap,
                timestamp=timestamp,
                source=bar.source,
                completeness=bar.completeness,
            )
            self._event_keys.add(key)
            while len(existing) > self.maximum_bars_per_ticker:
                oldest = min(existing)
                del existing[oldest]
                self._event_keys.discard((ticker, oldest))
        return True

    @staticmethod
    def _bucket(timestamp: datetime, minutes: int) -> datetime:
        return timestamp.replace(
            minute=(timestamp.minute // minutes) * minutes,
            second=0,
            microsecond=0,
        )

    def bars(self, ticker: str, timeframe: str = "1m") -> list[Bar]:
        if timeframe not in SUPPORTED_TIMEFRAMES:
            raise ValueError("Timeframe must be 1m, 5m, or 15m.")
        with self._lock:
            source = [
                self._minutes[ticker.upper()][key]
                for key in sorted(self._minutes[ticker.upper()])
            ]
        if timeframe == "1m":
            return source
        minutes = SUPPORTED_TIMEFRAMES[timeframe]
        groups: dict[datetime, list[Bar]] = defaultdict(list)
        for bar in source:
            groups[self._bucket(bar.timestamp, minutes)].append(bar)
        result = []
        for bucket in sorted(groups):
            items = sorted(groups[bucket], key=lambda item: item.timestamp)
            expected = [
                bucket + timedelta(minutes=offset)
                for offset in range(minutes)
            ]
            timestamps = [item.timestamp for item in items]
            complete = (
                timestamps == expected
                and all(
                    item.completeness == Completeness.CLOSED
                    for item in items
                )
            )
            has_gap = len(items) > 1 and any(
                timestamps[index] - timestamps[index - 1]
                != timedelta(minutes=1)
                for index in range(1, len(timestamps))
            )
            completeness = (
                Completeness.CLOSED
                if complete
                else Completeness.GAP
                if has_gap
                else Completeness.INCOMPLETE
            )
            volume = sum(item.volume for item in items)
            weighted_vwap = (
                sum((item.vwap or item.close) * item.volume for item in items)
                / volume
                if volume > 0
                else None
            )
            result.append(
                Bar(
                    ticker=ticker.upper(),
                    timeframe=timeframe,
                    open=items[0].open,
                    high=max(item.high for item in items),
                    low=min(item.low for item in items),
                    close=items[-1].close,
                    volume=volume,
                    vwap=weighted_vwap,
                    timestamp=bucket,
                    source=items[0].source,
                    completeness=completeness,
                )
            )
        return result

    def serialized(
        self,
        ticker: str,
        timeframe: str,
        *,
        limit: int = 300,
    ) -> dict:
        values = self.bars(ticker, timeframe)[-limit:]
        raw_source = values[0].source if values else "alpaca_iex"
        feed = raw_source.removeprefix("alpaca_").upper()
        return {
            "ticker": ticker.upper(),
            "timeframe": timeframe,
            "source": f"Alpaca {feed}",
            "coverage": (
                "partial-market" if feed == "IEX" else "full-market"
            ),
            "bars": [bar.serialize() for bar in values],
            "gaps": self.gaps[ticker.upper()],
        }
