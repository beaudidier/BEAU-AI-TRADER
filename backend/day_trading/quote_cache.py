from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import RLock

from .models import Quote
from .session import as_utc


class QuoteValidationError(ValueError):
    pass


class QuoteCache:
    def __init__(
        self,
        *,
        stale_after_seconds: int = 15,
        future_tolerance_seconds: int = 2,
    ):
        self.stale_after = timedelta(seconds=stale_after_seconds)
        self.future_tolerance = timedelta(seconds=future_tolerance_seconds)
        self._quotes: dict[str, Quote] = {}
        self._event_ids: set[str] = set()
        self._lock = RLock()
        self.duplicates = 0
        self.out_of_order = 0
        self.invalid = 0

    def put(
        self,
        quote: Quote,
        *,
        received_at: datetime | None = None,
    ) -> bool:
        now = as_utc(received_at or datetime.now(timezone.utc))
        timestamp = as_utc(quote.timestamp)
        if (
            quote.bid <= 0
            or quote.ask <= 0
            or quote.ask < quote.bid
            or quote.bid_size < 0
            or quote.ask_size < 0
            or timestamp > now + self.future_tolerance
        ):
            self.invalid += 1
            raise QuoteValidationError("Invalid bid/ask quote.")
        ticker = quote.ticker.upper()
        with self._lock:
            if quote.event_id in self._event_ids:
                self.duplicates += 1
                return False
            current = self._quotes.get(ticker)
            if current and timestamp < as_utc(current.timestamp):
                self.out_of_order += 1
                return False
            self._quotes[ticker] = quote
            self._event_ids.add(quote.event_id)
            if len(self._event_ids) > 50_000:
                self._event_ids = {item.event_id for item in self._quotes.values()}
        return True

    def get(self, ticker: str) -> Quote | None:
        with self._lock:
            return self._quotes.get(ticker.upper())

    def is_stale(
        self,
        ticker: str,
        *,
        now: datetime | None = None,
    ) -> bool:
        quote = self.get(ticker)
        if quote is None:
            return True
        current = as_utc(now or datetime.now(timezone.utc))
        return current - as_utc(quote.timestamp) > self.stale_after

    def snapshot(
        self,
        ticker: str,
        *,
        now: datetime | None = None,
    ) -> dict | None:
        quote = self.get(ticker)
        return (
            quote.serialize(stale=self.is_stale(ticker, now=now))
            if quote
            else None
        )
