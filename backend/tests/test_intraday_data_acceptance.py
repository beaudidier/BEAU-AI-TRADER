from __future__ import annotations

import gzip
import json
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx

from day_trading.acceptance import (
    HistoricalIexSessionCollector,
    IntradayAcceptanceAuditor,
)
from day_trading.recorder import IntradayRecorder
from day_trading.session import (
    classify_market_session,
    regular_close_for,
    session_bounds,
)
from providers.alpaca_market_provider import AlpacaMarketProvider


class FakeResponse:
    def __init__(self, payload, status_code=200, headers=None):
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

    def json(self):
        return self._payload


class AcceptanceClient:
    def __init__(self):
        self.fail_once = False
        self.calls = []

    def get(self, url, *, params, headers):
        self.calls.append((url, dict(params)))
        if self.fail_once:
            self.fail_once = False
            raise httpx.ConnectError("simulated outage")
        timestamp = "2026-07-20T13:30:00Z"
        if url.endswith("/quotes"):
            payload = {
                "quotes": {
                    "AAPL": [
                        {
                            "t": timestamp,
                            "bp": 99.9,
                            "ap": 100.1,
                            "bs": 10,
                            "as": 10,
                            "bx": "V",
                            "ax": "V",
                        }
                    ]
                }
            }
        elif url.endswith("/trades"):
            payload = {
                "trades": {
                    "AAPL": [
                        {
                            "t": timestamp,
                            "p": 100.0,
                            "s": 4,
                            "x": "V",
                            "c": ["@"],
                            "i": 1,
                            "z": "C",
                        },
                        {
                            "t": "2026-07-20T13:30:30Z",
                            "p": 100.1,
                            "s": 6,
                            "x": "V",
                            "c": ["@"],
                            "i": 2,
                            "z": "C",
                        },
                    ]
                }
            }
        else:
            payload = {
                "bars": {
                    "AAPL": [
                        {
                            "t": timestamp,
                            "o": 100.0,
                            "h": 100.1,
                            "l": 100.0,
                            "c": 100.1,
                            "v": 10,
                            "vw": 100.06,
                            "n": 2,
                        }
                    ]
                }
            }
        payload["next_page_token"] = None
        return FakeResponse(payload)


class IntradayAcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.client = AcceptanceClient()
        self.provider = AlpacaMarketProvider(
            api_key="test-key",
            secret_key="test-secret",
            feed="iex",
            client=self.client,
        )

    def collector(self):
        return HistoricalIexSessionCollector(
            self.provider,
            self.root,
            symbols=["AAPL"],
            request_interval_seconds=0,
            maximum_retries=2,
        )

    def test_historical_collection_and_three_replays_are_deterministic(self):
        result = self.collector().collect(date(2026, 7, 20))
        self.assertEqual(result["source_mode"], "historical_rest")
        recorder = IntradayRecorder(self.root)
        verification = recorder.verify(result["session_id"])
        self.assertTrue(verification["checksum_valid"])
        self.assertFalse(verification["secrets_present"])

        audit = IntradayAcceptanceAuditor(self.root).audit(
            result["session_id"]
        )
        self.assertTrue(audit["determinism"]["deterministic"])
        self.assertEqual(audit["determinism"]["runs"], 3)
        self.assertEqual(audit["unexplained_mismatch_count"], 0)
        self.assertEqual(
            audit["raw_trade_aggregate_mismatches"]["5m"],
            [],
        )
        self.assertEqual(
            audit["raw_trade_aggregate_mismatches"]["15m"],
            [],
        )
        self.assertEqual(audit["boundary_violations"], [])
        self.assertEqual(audit["paper_orders_submitted"], 0)
        self.assertEqual(audit["live_orders_submitted"], 0)

    def test_temporary_network_outage_retries_without_secret_output(self):
        self.client.fail_once = True
        result = self.collector().collect(date(2026, 7, 20))
        self.assertGreaterEqual(result["retries"], 1)
        metadata_path = next(self.root.glob("*/*.meta.json"))
        content = metadata_path.read_text(encoding="utf-8")
        self.assertNotIn("test-key", content)
        self.assertNotIn("test-secret", content)

    def test_corrupted_checkpoint_is_quarantined_and_refetched(self):
        collector = self.collector()
        parts = self.root / ".acceptance_parts" / "2026-07-20"
        parts.mkdir(parents=True)
        checkpoint = parts / "quote.checkpoint.json"
        checkpoint.write_text("{broken", encoding="utf-8")
        bounds = session_bounds(date(2026, 7, 20))
        collector._fetch_event_type(
            parts=parts,
            event_type="quote",
            start=bounds["premarket_open"].astimezone(timezone.utc),
            end=bounds["after_hours_close"].astimezone(timezone.utc),
        )
        self.assertTrue((parts / "quote.checkpoint.corrupt").exists())
        recovered = json.loads(checkpoint.read_text(encoding="utf-8"))
        self.assertTrue(recovered["complete"])

    def test_storage_interruption_is_explicit_and_does_not_advance_ledger(self):
        recorder = IntradayRecorder(self.root)
        recorder.start(
            symbols=["AAPL"],
            source="Alpaca IEX",
            coverage="partial-market",
            session_id="storage-test",
        )
        before = recorder.status()["event_count"]

        class FailedWriter:
            def write(self, value):
                raise OSError("simulated storage interruption")

        original = recorder._writer
        recorder._writer = FailedWriter()
        with self.assertRaisesRegex(OSError, "storage interruption"):
            recorder.record_raw(
                {
                    "T": "q",
                    "S": "AAPL",
                    "t": "2026-07-20T13:30:00Z",
                    "bp": 99.9,
                    "ap": 100.1,
                },
                received_at=datetime(
                    2026,
                    7,
                    20,
                    13,
                    30,
                    tzinfo=timezone.utc,
                ),
                disposition="accepted",
            )
        self.assertEqual(recorder.status()["event_count"], before)
        recorder._writer = original
        recorder.stop()

    def test_partition_date_and_append_only_recovery(self):
        recorder = IntradayRecorder(
            self.root,
            flush_every=10,
            checkpoint_every=10,
            compresslevel=1,
        )
        started = datetime(2026, 7, 20, 8, tzinfo=timezone.utc)
        recorder.start(
            symbols=["AAPL"],
            source="Alpaca IEX historical",
            coverage="partial-market",
            session_id="historical-partition",
            partition_date=date(2026, 7, 20),
            started_at=started,
        )
        recorder.stop()
        self.assertTrue(
            (
                self.root
                / "2026-07-20"
                / "historical-partition.meta.json"
            ).exists()
        )

    def test_session_boundaries_dst_and_early_close(self):
        summer = session_bounds(date(2026, 7, 20))
        winter = session_bounds(date(2026, 12, 1))
        self.assertEqual(
            summer["regular_open"].astimezone(timezone.utc).hour,
            13,
        )
        self.assertEqual(
            winter["regular_open"].astimezone(timezone.utc).hour,
            14,
        )
        early = date(2026, 11, 27)
        self.assertEqual(regular_close_for(early).hour, 13)
        close = session_bounds(early)["regular_close"]
        self.assertEqual(
            classify_market_session(close - timedelta(seconds=1)).value,
            "regular",
        )
        self.assertEqual(
            classify_market_session(close).value,
            "after-hours",
        )

    def test_duplicate_and_delayed_events_remain_auditable(self):
        recorder = IntradayRecorder(self.root)
        recorder.start(
            symbols=["AAPL"],
            source="Alpaca IEX",
            coverage="partial-market",
        )
        later = datetime(2026, 7, 20, 13, 30, 2, tzinfo=timezone.utc)
        earlier = later - timedelta(seconds=1)
        raw = {
            "T": "q",
            "S": "AAPL",
            "t": later.isoformat(),
            "bp": 99.9,
            "ap": 100.1,
        }
        recorder.record_raw(
            raw,
            received_at=later,
            disposition="accepted",
        )
        recorder.record_raw(
            {**raw, "t": earlier.isoformat()},
            received_at=later + timedelta(seconds=1),
            disposition="out_of_order",
        )
        recorder.record_raw(
            raw,
            received_at=later + timedelta(seconds=2),
            disposition="duplicate",
        )
        result = recorder.stop()
        self.assertEqual(result["duplicate_events"], 1)
        self.assertEqual(result["out_of_order_events"], 1)
        with gzip.open(
            next(self.root.glob("*/*.jsonl.gz")),
            "rt",
            encoding="utf-8",
        ) as source:
            dispositions = {
                json.loads(line)["disposition"] for line in source
            }
        self.assertIn("duplicate", dispositions)
        self.assertIn("out_of_order", dispositions)


if __name__ == "__main__":
    unittest.main()
