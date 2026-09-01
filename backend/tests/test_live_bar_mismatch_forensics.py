from __future__ import annotations

import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone

from day_trading.acceptance import IntradayAcceptanceAuditor
from day_trading.mismatch_forensics import LiveBarMismatchForensics
from day_trading.recorder import IntradayRecorder


class LiveBarMismatchForensicsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = self.temporary.name
        self.recorder = IntradayRecorder(self.root)
        self.start = datetime(2026, 8, 19, 13, 30, tzinfo=timezone.utc)
        self.recorder.start(
            symbols=["AAPL"],
            source="Alpaca IEX WebSocket",
            coverage="partial-market",
            session_id="forensic-fixture",
            partition_date=date(2026, 8, 19),
            started_at=self.start,
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def trade(timestamp: datetime, *, identifier: int, size: int = 100):
        return {
            "T": "t",
            "S": "AAPL",
            "t": timestamp.isoformat(),
            "p": 100.0,
            "s": size,
            "x": "V",
            "c": ["@"],
            "i": identifier,
        }

    @staticmethod
    def bar(timestamp: datetime, *, volume: int = 100):
        return {
            "T": "b",
            "S": "AAPL",
            "t": timestamp.isoformat(),
            "o": 100.0,
            "h": 100.0,
            "l": 100.0,
            "c": 100.0,
            "v": volume,
            "vw": 100.0,
        }

    def test_classifies_late_duplicate_reconnect_and_visible_loss(self):
        late_minute = self.start
        first = self.trade(late_minute + timedelta(seconds=10), identifier=1)
        late = self.trade(
            late_minute + timedelta(seconds=59, milliseconds=900),
            identifier=2,
            size=50,
        )
        self.recorder.record_raw(
            first,
            received_at=late_minute + timedelta(seconds=10, milliseconds=20),
            disposition="unsupported",
        )
        self.recorder.record_raw(
            self.bar(late_minute),
            received_at=late_minute + timedelta(minutes=1, milliseconds=100),
            disposition="unsupported",
        )
        self.recorder.record_raw(
            late,
            received_at=late_minute + timedelta(minutes=1, milliseconds=50),
            disposition="unsupported",
        )

        duplicate_minute = self.start + timedelta(minutes=2)
        duplicate_trade = self.trade(
            duplicate_minute + timedelta(seconds=10), identifier=3
        )
        self.recorder.record_raw(
            duplicate_trade,
            received_at=duplicate_minute + timedelta(seconds=10),
            disposition="unsupported",
        )
        self.recorder.record_raw(
            duplicate_trade,
            received_at=duplicate_minute + timedelta(seconds=11),
            disposition="duplicate",
        )
        self.recorder.record_raw(
            self.bar(duplicate_minute),
            received_at=duplicate_minute + timedelta(minutes=1),
            disposition="unsupported",
        )

        reconnect_minute = self.start + timedelta(minutes=4)
        self.recorder.record_raw(
            self.trade(reconnect_minute + timedelta(seconds=10), identifier=4),
            received_at=reconnect_minute + timedelta(seconds=10),
            disposition="unsupported",
        )
        self.recorder.record_system(
            "stream_disconnected",
            {"error_type": "TimeoutError"},
            occurred_at=reconnect_minute + timedelta(seconds=30),
        )

        loss_minute = self.start + timedelta(minutes=6)
        self.recorder.record_raw(
            self.trade(loss_minute + timedelta(seconds=10), identifier=5),
            received_at=loss_minute + timedelta(seconds=10),
            disposition="unsupported",
        )
        self.recorder.stop()

        result = LiveBarMismatchForensics(self.root).analyze(
            ["forensic-fixture"]
        )

        self.assertEqual(result["mismatch_count"], 4)
        self.assertEqual(
            result["classification_counts"],
            {
                "duplicate_suppression_issue": 1,
                "late_trade_arrival": 1,
                "raw_event_loss": 1,
                "reconnect_backfill_boundary_issue": 1,
            },
        )
        self.assertEqual(result["scope"]["orders_submitted"], 0)
        self.assertEqual(result["acceptance"]["verdict"], "FAIL")
        late_item = next(
            item
            for item in result["ledger"]
            if item["classification"] == "late_trade_arrival"
        )
        self.assertEqual(late_item["late_after_interval_close_count"], 1)
        self.assertTrue(
            late_item["finalization_delay_candidates_seconds"]["0"][
                "matches_provider"
            ]
        )

    def test_acceptance_auditor_skips_duplicate_market_events(self):
        trade = self.trade(self.start + timedelta(seconds=10), identifier=10)
        self.recorder.record_raw(
            trade,
            received_at=self.start + timedelta(seconds=10),
            disposition="unsupported",
        )
        self.recorder.record_raw(
            trade,
            received_at=self.start + timedelta(seconds=11),
            disposition="duplicate",
        )
        self.recorder.record_raw(
            self.bar(self.start),
            received_at=self.start + timedelta(minutes=1),
            disposition="unsupported",
        )
        self.recorder.stop()

        audit = IntradayAcceptanceAuditor(self.root).audit(
            "forensic-fixture"
        )

        self.assertEqual(audit["duplicate_market_events_skipped"], 1)
        self.assertEqual(audit["trade_reconstruction_mismatches"], [])
        self.assertEqual(audit["unexplained_mismatch_count"], 0)


if __name__ == "__main__":
    unittest.main()
