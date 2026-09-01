from __future__ import annotations

import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

from day_trading.recorder import IntradayRecorder
from day_trading.replay import (
    DeterministicReplayEngine,
    ReplayExecutionSimulator,
)

BASE = datetime(2026, 7, 27, 14, 30, tzinfo=timezone.utc)
SYMBOLS = ["AAPL", "NVDA"]


def quote_event(
    *,
    timestamp: datetime = BASE,
    bid: float = 100,
    ask: float = 100.10,
) -> dict:
    return {
        "T": "q",
        "S": "AAPL",
        "t": timestamp.isoformat(),
        "bp": bid,
        "ap": ask,
        "bs": 10,
        "as": 12,
        "bx": "V",
        "ax": "V",
    }


def trade_event(
    *,
    timestamp: datetime,
    price: float,
    size: float,
    identifier: int,
) -> dict:
    return {
        "T": "t",
        "S": "AAPL",
        "t": timestamp.isoformat(),
        "p": price,
        "s": size,
        "i": identifier,
        "x": "V",
        "c": ["@"],
    }


class RecorderReplayTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.recorder = IntradayRecorder(self.temporary.name)

    def record_session(self, *, session_id: str = "test-session") -> str:
        self.recorder.start(
            symbols=SYMBOLS,
            source="Alpaca IEX",
            coverage="partial-market",
            session_id=session_id,
        )
        self.recorder.record_raw(
            quote_event(),
            received_at=BASE + timedelta(milliseconds=5),
            disposition="accepted",
        )
        self.recorder.record_raw(
            trade_event(
                timestamp=BASE + timedelta(seconds=1),
                price=100.05,
                size=4,
                identifier=1,
            ),
            received_at=BASE + timedelta(seconds=1, milliseconds=5),
            disposition="accepted",
        )
        self.recorder.record_raw(
            trade_event(
                timestamp=BASE + timedelta(seconds=2),
                price=100.04,
                size=6,
                identifier=2,
            ),
            received_at=BASE + timedelta(seconds=2, milliseconds=5),
            disposition="accepted",
        )
        self.recorder.record_raw(
            {
                "T": "b",
                "S": "AAPL",
                "t": BASE.isoformat(),
                "o": 100.05,
                "h": 100.05,
                "l": 100.04,
                "c": 100.04,
                "v": 10,
                "vw": 100.044,
            },
            received_at=BASE + timedelta(minutes=1, milliseconds=10),
            disposition="accepted",
        )
        return self.recorder.stop()["session_id"]

    def test_append_only_recording_checksum_and_recovery(self):
        session_id = self.record_session()
        verification = self.recorder.verify(session_id)
        self.assertTrue(verification["checksum_valid"])
        self.assertFalse(verification["secrets_present"])
        original_count = verification["event_count"]
        session = self.recorder.sessions()[0]
        self.assertGreater(session["symbol_counts"]["AAPL"], 0)

        recovered = IntradayRecorder(self.temporary.name)
        status = recovered.start(
            symbols=SYMBOLS,
            source="Alpaca IEX",
            coverage="partial-market",
            session_id=session_id,
        )
        self.assertTrue(status["recovered"])
        recovered.record_system("recovered_heartbeat", {"healthy": True})
        recovered.stop()
        after = recovered.verify(session_id)
        self.assertTrue(after["checksum_valid"])
        self.assertGreater(after["event_count"], original_count)

    def test_interrupted_recorder_resumes_latest_append_only_session(self):
        started = self.recorder.start(
            symbols=SYMBOLS,
            source="Alpaca IEX",
            coverage="partial-market",
        )
        self.recorder.record_raw(
            quote_event(),
            received_at=BASE,
            disposition="accepted",
        )
        self.recorder._writer.close()
        self.recorder._writer = None

        recovered = IntradayRecorder(self.temporary.name)
        resumed = recovered.start(
            symbols=SYMBOLS,
            source="Alpaca IEX",
            coverage="partial-market",
        )
        self.assertEqual(resumed["session_id"], started["session_id"])
        self.assertTrue(resumed["recovered"])
        completed = recovered.stop()
        self.assertEqual(completed["status"], "completed")
        self.assertTrue(
            recovered.verify(started["session_id"])["checksum_valid"]
        )

    def test_duplicate_out_of_order_and_gap_events_remain_auditable(self):
        self.recorder.start(
            symbols=SYMBOLS,
            source="Alpaca IEX",
            coverage="partial-market",
        )
        self.recorder.record_raw(
            quote_event(timestamp=BASE + timedelta(seconds=2)),
            received_at=BASE + timedelta(seconds=2),
            disposition="accepted",
        )
        self.recorder.record_raw(
            quote_event(timestamp=BASE + timedelta(seconds=1)),
            received_at=BASE + timedelta(seconds=3),
            disposition="out_of_order",
        )
        self.recorder.record_raw(
            quote_event(timestamp=BASE + timedelta(seconds=2)),
            received_at=BASE + timedelta(seconds=4),
            disposition="duplicate",
        )
        result = self.recorder.stop()
        self.assertEqual(result["out_of_order_events"], 1)
        self.assertEqual(result["duplicate_events"], 1)
        self.assertEqual(result["event_counts"]["quote"], 3)
        replay = DeterministicReplayEngine(self.recorder)
        completed = replay.run_to_completion(result["session_id"])
        self.assertEqual(completed["quotes"]["AAPL"]["bid"], 100)

    def test_session_lookup_rejects_path_and_glob_input(self):
        for unsafe in ("../secret", "*", "session?.json"):
            with self.assertRaises(FileNotFoundError):
                self.recorder.resolve_session(unsafe)
            with self.assertRaises(ValueError):
                self.recorder.start(
                    symbols=SYMBOLS,
                    source="Alpaca IEX",
                    coverage="partial-market",
                    session_id=unsafe,
                )

    def test_sensitive_system_fields_are_never_written(self):
        self.recorder.start(
            symbols=SYMBOLS,
            source="Alpaca IEX",
            coverage="partial-market",
        )
        with self.assertRaisesRegex(ValueError, "Sensitive fields"):
            self.recorder.record_system(
                "unsafe",
                {"api_key": "must-not-be-written"},
            )
        completed = self.recorder.stop()
        self.assertFalse(completed["secrets_present"])
        self.assertEqual(completed["blocked_sensitive_events"], 1)
        verification = self.recorder.verify(
            completed["session_id"]
        )
        self.assertFalse(verification["secrets_present"])

    def test_three_replays_are_identical_and_bars_are_rebuilt(self):
        session_id = self.record_session()
        replay = DeterministicReplayEngine(self.recorder)
        result = replay.verify_determinism(session_id, runs=3)
        self.assertTrue(result["deterministic"])
        self.assertEqual(len(set(result["event_digests"])), 1)
        completed = replay.run_to_completion(session_id)
        self.assertEqual(completed["bars"]["1m"], 1)
        verification = replay.verify_bars(session_id)
        self.assertEqual(verification["provider_bars"], 1)
        self.assertEqual(verification["bar_mismatches"], [])
        self.assertEqual(verification["duplicate_events"], 0)
        self.assertEqual(
            verification["incomplete_bars_treated_as_closed"],
            0,
        )

    def test_pause_seek_resume_and_reset(self):
        session_id = self.record_session()
        replay = DeterministicReplayEngine(self.recorder)
        replay.start(session_id, speed="original")
        time.sleep(0.01)
        paused = replay.pause()
        self.assertIn(paused["status"], {"paused", "completed"})
        if paused["status"] == "paused":
            self.assertEqual(replay.resume()["status"], "running")
        replay.seek(BASE + timedelta(seconds=1))
        self.assertEqual(replay.status()["status"], "paused")
        seek_cursor = replay.status()["cursor"]
        self.assertGreaterEqual(seek_cursor, 1)
        replay.resume()
        time.sleep(0.02)
        replay.pause()
        self.assertGreater(replay.status()["cursor"], seek_cursor)
        self.assertEqual(replay.reset()["status"], "idle")

    def test_incomplete_provider_bar_is_not_closed(self):
        self.recorder.start(
            symbols=SYMBOLS,
            source="Alpaca IEX",
            coverage="partial-market",
            session_id="incomplete",
        )
        self.recorder.record_raw(
            {
                "T": "b",
                "S": "AAPL",
                "t": BASE.isoformat(),
                "o": 100,
                "h": 101,
                "l": 99,
                "c": 100.5,
                "v": 10,
            },
            received_at=BASE + timedelta(seconds=30),
            disposition="accepted",
        )
        self.recorder.stop()
        replay = DeterministicReplayEngine(self.recorder)
        replay.run_to_completion("incomplete")
        bar = replay.aggregator.bars("AAPL", "1m")[0]
        self.assertEqual(bar.completeness.value, "incomplete")

    def test_replay_uses_receipt_time_and_never_reveals_bar_early(self):
        self.recorder.start(
            symbols=SYMBOLS,
            source="Alpaca IEX",
            coverage="partial-market",
            session_id="no-lookahead",
        )
        self.recorder.record_raw(
            {
                "T": "b",
                "S": "AAPL",
                "t": BASE.isoformat(),
                "o": 100,
                "h": 101,
                "l": 99,
                "c": 100.5,
                "v": 10,
            },
            received_at=BASE + timedelta(minutes=1),
            disposition="accepted",
        )
        self.recorder.stop()
        replay = DeterministicReplayEngine(self.recorder)
        replay.run_to_completion("no-lookahead")
        replay.seek(BASE + timedelta(seconds=30))
        self.assertEqual(replay.aggregator.bars("AAPL", "1m"), [])
        replay.seek(BASE + timedelta(minutes=1, seconds=1))
        self.assertEqual(len(replay.aggregator.bars("AAPL", "1m")), 1)
        replay.reset()


class ReplayExecutionSimulatorTests(unittest.TestCase):
    def setUp(self):
        self.simulator = ReplayExecutionSimulator(
            slippage_bps=2,
            latency_ms=100,
            stale_quote_seconds=15,
        )
        self.simulator.on_event(
            {
                "symbol": "AAPL",
                "event_type": "quote",
                "provider_timestamp": BASE.isoformat(),
                "receipt_timestamp": BASE.isoformat(),
                "payload": {"bp": 100, "ap": 100.10},
            }
        )

    def test_limit_trade_through_partial_fills_latency_and_slippage(self):
        order = self.simulator.submit(
            symbol="AAPL",
            side="buy",
            order_type="limit",
            quantity=10,
            limit_price=100.05,
            submitted_at=BASE,
        )
        self.simulator.on_event(
            {
                "symbol": "AAPL",
                "event_type": "trade",
                "provider_timestamp": (
                    BASE + timedelta(milliseconds=50)
                ).isoformat(),
                "receipt_timestamp": (
                    BASE + timedelta(milliseconds=50)
                ).isoformat(),
                "payload": {"p": 100.04, "s": 10},
            }
        )
        self.assertEqual(
            self.simulator.orders[order["id"]].status,
            "pending",
        )
        for offset, size in ((150, 4), (200, 6)):
            self.simulator.on_event(
                {
                    "symbol": "AAPL",
                    "event_type": "trade",
                    "provider_timestamp": (
                        BASE + timedelta(milliseconds=offset)
                    ).isoformat(),
                    "receipt_timestamp": (
                        BASE + timedelta(milliseconds=offset)
                    ).isoformat(),
                    "payload": {"p": 100.04, "s": size},
                }
            )
        filled = self.simulator.orders[order["id"]]
        self.assertEqual(filled.status, "filled")
        self.assertEqual(len(self.simulator.fills), 2)
        self.assertAlmostEqual(filled.filled_quantity, 10)
        self.assertGreater(filled.average_fill_price, 100.04)

    def test_limit_does_not_fill_without_trade_through_and_cancel_works(self):
        order = self.simulator.submit(
            symbol="AAPL",
            side="buy",
            order_type="limit",
            quantity=1,
            limit_price=99,
            submitted_at=BASE,
        )
        self.simulator.on_event(
            {
                "symbol": "AAPL",
                "event_type": "trade",
                "provider_timestamp": (
                    BASE + timedelta(seconds=1)
                ).isoformat(),
                "receipt_timestamp": (
                    BASE + timedelta(seconds=1)
                ).isoformat(),
                "payload": {"p": 100, "s": 5},
            }
        )
        self.assertEqual(
            self.simulator.orders[order["id"]].status,
            "pending",
        )
        self.assertEqual(
            self.simulator.cancel(order["id"])["status"],
            "cancelled",
        )

    def test_identical_order_input_has_deterministic_replay_id(self):
        first = self.simulator.submit(
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=1,
            submitted_at=BASE,
        )
        second_simulator = ReplayExecutionSimulator()
        second_simulator.on_event(
            {
                "symbol": "AAPL",
                "event_type": "quote",
                "provider_timestamp": BASE.isoformat(),
                "receipt_timestamp": BASE.isoformat(),
                "payload": {"bp": 100, "ap": 100.10},
            }
        )
        second = second_simulator.submit(
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=1,
            submitted_at=BASE,
        )
        self.assertEqual(first["id"], second["id"])

    def test_stop_order_waits_for_trade_trigger(self):
        order = self.simulator.submit(
            symbol="AAPL",
            side="buy",
            order_type="stop",
            quantity=1,
            stop_price=101,
            submitted_at=BASE,
        )
        for seconds, price in ((1, 100.90), (2, 101)):
            self.simulator.on_event(
                {
                    "symbol": "AAPL",
                    "event_type": "trade",
                    "provider_timestamp": (
                        BASE + timedelta(seconds=seconds)
                    ).isoformat(),
                    "receipt_timestamp": (
                        BASE + timedelta(seconds=seconds)
                    ).isoformat(),
                    "payload": {"p": price, "s": 1},
                }
            )
        self.assertEqual(
            self.simulator.orders[order["id"]].status,
            "filled",
        )
        self.assertEqual(len(self.simulator.fills), 1)

    def test_stale_quote_and_session_boundary_rejections(self):
        stale = self.simulator.submit(
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=1,
            submitted_at=BASE + timedelta(seconds=16),
        )
        self.assertEqual(stale["status"], "rejected")
        self.assertIn("stale", stale["rejection_reason"].lower())

        after_hours = datetime(
            2026,
            7,
            27,
            22,
            0,
            tzinfo=timezone.utc,
        )
        self.simulator.on_event(
            {
                "symbol": "AAPL",
                "event_type": "quote",
                "provider_timestamp": after_hours.isoformat(),
                "receipt_timestamp": after_hours.isoformat(),
                "payload": {"bp": 100, "ap": 100.10},
            }
        )
        rejected = self.simulator.submit(
            symbol="AAPL",
            side="buy",
            order_type="market",
            quantity=1,
            submitted_at=after_hours,
        )
        self.assertEqual(rejected["status"], "rejected")
        self.assertIn("regular", rejected["rejection_reason"].lower())


if __name__ == "__main__":
    unittest.main()
