from __future__ import annotations

import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

from day_trading.market_clock import MarketClock
from day_trading.models import (
    OrderSide,
    OrderStatus,
    OrderType,
    PaperOrderRequest,
    Quote,
)
from day_trading.paper_broker import PaperBroker, PaperOrderRejected
from day_trading.quote_cache import QuoteCache


REGULAR = datetime(2026, 7, 27, 14, 30, tzinfo=timezone.utc)


class DayTradingPaperBrokerTests(unittest.TestCase):
    def setUp(self):
        self.now = REGULAR
        self.cache = QuoteCache(stale_after_seconds=15)
        self.clock = MarketClock(lambda: self.now)
        self.broker = PaperBroker(
            self.cache,
            self.clock,
            starting_balance=100_000,
            max_spread_percent=0.25,
            orders_enabled=True,
        )

    def add_quote(
        self,
        ticker="AAPL",
        *,
        bid=99.95,
        ask=100.0,
        timestamp=None,
        event_id=None,
    ):
        value = Quote(
            ticker=ticker,
            bid=bid,
            ask=ask,
            bid_size=100,
            ask_size=100,
            timestamp=timestamp or self.now,
            event_id=event_id or f"{ticker}-{timestamp or self.now}",
        )
        self.cache.put(value, received_at=self.now)
        return value

    @staticmethod
    def request(
        ticker="AAPL",
        key="request-1",
        *,
        quantity=10,
        protective_stop=99.0,
        order_type=OrderType.MARKET,
        limit_price=None,
        stop_price=None,
    ):
        return PaperOrderRequest(
            ticker=ticker,
            side=OrderSide.BUY,
            order_type=order_type,
            quantity=quantity,
            idempotency_key=key,
            protective_stop=protective_stop,
            limit_price=limit_price,
            stop_price=stop_price,
        )

    def test_paper_order_idempotency(self):
        self.add_quote()
        request = self.request()
        first = self.broker.submit(request)
        second = self.broker.submit(request)
        self.assertEqual(first.id, second.id)
        self.assertEqual(len(self.broker.positions), 1)
        with self.assertRaisesRegex(PaperOrderRejected, "idempotency key"):
            self.broker.submit(
                self.request(
                    ticker="MSFT",
                    key=request.idempotency_key,
                )
            )

    def test_orders_are_disabled_by_default(self):
        broker = PaperBroker(
            self.cache,
            self.clock,
            starting_balance=100_000,
        )
        self.add_quote()
        with self.assertRaisesRegex(PaperOrderRejected, "emergency switch"):
            broker.submit(self.request())

    def test_stale_quote_and_excessive_spread_are_blocked(self):
        self.add_quote(timestamp=self.now - timedelta(seconds=16))
        with self.assertRaisesRegex(PaperOrderRejected, "stale"):
            self.broker.submit(self.request())

        self.cache = QuoteCache(stale_after_seconds=15)
        self.broker.quote_cache = self.cache
        self.add_quote(bid=99, ask=100)
        with self.assertRaisesRegex(PaperOrderRejected, "spread"):
            self.broker.submit(self.request(key="request-2"))

    def test_risk_limit_and_averaging_down_are_blocked(self):
        self.add_quote()
        with self.assertRaisesRegex(PaperOrderRejected, "0.25%"):
            self.broker.submit(
                self.request(
                    key="high-risk",
                    quantity=100,
                    protective_stop=95,
                )
            )
        self.broker.submit(self.request())
        with self.assertRaisesRegex(PaperOrderRejected, "Averaging"):
            self.broker.submit(self.request(key="request-2"))

    def test_daily_loss_locks_new_orders(self):
        self.add_quote()
        self.broker._trading_day = self.now.date()
        self.broker._day_start_equity = 100_000
        self.broker.cash = 99_499
        with self.assertRaisesRegex(PaperOrderRejected, "Daily loss"):
            self.broker.submit(self.request())

    def test_concurrent_attempts_never_open_more_than_two_positions(self):
        for ticker in ("AAPL", "MSFT", "NVDA"):
            self.add_quote(ticker)
        requests = [
            self.request(ticker, f"concurrent-{ticker}")
            for ticker in ("AAPL", "MSFT", "NVDA")
        ]

        def submit(request):
            try:
                return self.broker.submit(request).status
            except PaperOrderRejected:
                return OrderStatus.REJECTED

        with ThreadPoolExecutor(max_workers=3) as executor:
            statuses = list(executor.map(submit, requests))
        self.assertEqual(statuses.count(OrderStatus.FILLED), 2)
        self.assertEqual(len(self.broker.positions), 2)

    def test_pending_limit_revalidates_risk_at_actual_fill(self):
        self.add_quote()
        order = self.broker.submit(
            self.request(
                key="limit-order",
                quantity=200,
                protective_stop=99,
                order_type=OrderType.LIMIT,
                limit_price=99.5,
            )
        )
        self.assertEqual(order.status, OrderStatus.PENDING)
        self.now += timedelta(seconds=1)
        self.add_quote(
            bid=99.45,
            ask=99.50,
            timestamp=self.now,
            event_id="limit-trigger",
        )
        self.broker.process_quote("AAPL", now=self.now)
        self.assertEqual(order.status, OrderStatus.FILLED)

    def test_pending_stop_and_cancel(self):
        self.add_quote()
        order = self.broker.submit(
            self.request(
                key="stop-order",
                order_type=OrderType.STOP,
                stop_price=101,
            )
        )
        self.assertEqual(order.status, OrderStatus.PENDING)
        self.assertEqual(
            self.broker.cancel(order.id).status,
            OrderStatus.CANCELLED,
        )

    def test_no_positions_are_held_after_market_close(self):
        self.add_quote()
        self.broker.submit(self.request())
        after_hours = datetime(2026, 7, 27, 20, 1, tzinfo=timezone.utc)
        closed = self.broker.enforce_no_overnight(now=after_hours)
        self.assertEqual(closed, 1)
        self.assertFalse(self.broker.positions)
        self.assertEqual(
            self.broker.closed_positions[-1].reason,
            "mandatory market-close flatten",
        )

    def test_pending_orders_expire_after_market_close(self):
        self.add_quote()
        order = self.broker.submit(
            self.request(
                key="pending-close",
                order_type=OrderType.LIMIT,
                limit_price=95,
                protective_stop=94,
            )
        )
        after_hours = datetime(2026, 7, 27, 20, 1, tzinfo=timezone.utc)
        self.broker.enforce_no_overnight(now=after_hours)
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(order.rejection_reason, "Expired at the market close.")

    def test_protective_stop_closes_position(self):
        self.add_quote()
        self.broker.submit(self.request())
        self.now += timedelta(seconds=1)
        self.add_quote(
            bid=98.95,
            ask=99.0,
            timestamp=self.now,
            event_id="stop-hit",
        )
        self.broker.process_quote("AAPL", now=self.now)
        self.assertFalse(self.broker.positions)
        self.assertEqual(
            self.broker.closed_positions[-1].reason,
            "protective stop",
        )


if __name__ == "__main__":
    unittest.main()
