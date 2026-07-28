from __future__ import annotations

import gzip
import hashlib
import json
import tempfile
import unittest
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

from day_trading.verify_live_sessions import LiveSessionVerifier

BASE = datetime(2026, 7, 28, 14, 30, tzinfo=timezone.utc)


def event(
    index: int,
    event_type: str,
    receipt: datetime,
    *,
    symbol: str | None = None,
    provider: datetime | None = None,
    payload: dict | None = None,
    disposition: str = "observed",
    sequence: int | None = None,
) -> dict:
    return {
        "index": index,
        "provider_timestamp": provider.isoformat() if provider else None,
        "receipt_timestamp": receipt.isoformat(),
        "symbol": symbol,
        "event_type": event_type,
        "sequence": sequence,
        "disposition": disposition,
        "source": "Alpaca IEX WebSocket",
        "coverage": "partial-market",
        "payload": payload or {},
    }


def valid_events() -> list[dict]:
    return [
        event(0, "recording_started", BASE),
        event(
            1,
            "quote",
            BASE + timedelta(seconds=1),
            symbol="AAPL",
            provider=BASE + timedelta(seconds=1),
            payload={"bp": 100, "ap": 100.1, "bs": 1, "as": 1},
            disposition="accepted",
        ),
        event(
            2,
            "bar_1m",
            BASE + timedelta(minutes=1),
            symbol="AAPL",
            provider=BASE,
            payload={
                "o": 100,
                "h": 101,
                "l": 99,
                "c": 100.5,
                "v": 10,
                "vw": 100.25,
            },
            disposition="accepted",
        ),
        event(3, "recording_stopped", BASE + timedelta(minutes=2)),
    ]


class LiveSessionVerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / "recordings"
        self.output = Path(self.temporary.name) / "reports"

    def write_session(
        self,
        session_id: str = "live-iex-20260728",
        *,
        events: list[dict] | None = None,
        status: str = "completed",
        checksum_valid: bool = True,
        truncate: bool = False,
        include_manifest: bool = True,
        include_checksum: bool = True,
    ) -> tuple[Path, Path]:
        values = events or valid_events()
        partition = self.root / "2026-07-28"
        partition.mkdir(parents=True, exist_ok=True)
        data_path = partition / f"{session_id}.jsonl.gz"
        raw = [
            (
                json.dumps(
                    value,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode()
            for value in values
        ]
        with gzip.open(data_path, "wb") as destination:
            for line in raw:
                destination.write(line)
        if truncate:
            content = data_path.read_bytes()
            data_path.write_bytes(content[:-8])
        manifest_path = partition / f"{session_id}.meta.json"
        if include_manifest:
            counts = Counter(item["event_type"] for item in values)
            digest = hashlib.sha256(b"".join(raw)).hexdigest()
            manifest = {
                "session_id": session_id,
                "status": status,
                "symbols": ["AAPL"],
                "source": "Alpaca IEX WebSocket",
                "coverage": "partial-market",
                "started_at": BASE.isoformat(),
                "market_date": "2026-07-28",
                "completed_at": (
                    (BASE + timedelta(minutes=2)).isoformat()
                    if status == "completed"
                    else None
                ),
                "event_count": len(values),
                "event_counts": dict(counts),
                "checksum_sha256": (
                    digest if checksum_valid else "0" * 64
                )
                if include_checksum
                else None,
                "compressed_file": data_path.name,
                "gaps": [],
            }
            manifest_path.write_text(
                json.dumps(manifest),
                encoding="utf-8",
            )
        return data_path, manifest_path

    def verifier(self, **kwargs) -> LiveSessionVerifier:
        return LiveSessionVerifier(self.root, self.output, **kwargs)

    def test_valid_finalised_session_passes(self):
        self.write_session()
        summary = self.verifier().scan()
        self.assertEqual(summary["passed_sessions"], 1)
        self.assertEqual(summary["failed_sessions"], 0)
        report = summary["reports"][0]
        self.assertTrue(report["gzip_integrity"])
        self.assertTrue(report["checksum_result"]["valid"])
        self.assertTrue(report["replay"]["deterministic"])
        self.assertEqual(report["rebuilt_state"]["bar_counts"]["1m"], 1)

    def test_active_session_is_ignored_without_reading_or_changing_it(self):
        data_path, _ = self.write_session(status="recording")
        before = (data_path.stat().st_size, data_path.stat().st_mtime_ns)
        summary = self.verifier().scan()
        after = (data_path.stat().st_size, data_path.stat().st_mtime_ns)
        self.assertEqual(before, after)
        self.assertEqual(summary["finalised_sessions"], 0)
        self.assertEqual(
            summary["skipped"][0]["reason"],
            "active_or_incomplete",
        )

    def test_missing_final_manifest_is_skipped(self):
        self.write_session(include_manifest=False)
        summary = self.verifier().scan()
        self.assertEqual(summary["finalised_sessions"], 0)
        self.assertEqual(
            summary["skipped"][0]["reason"],
            "missing_final_manifest",
        )

    def test_checksum_failure_is_reported(self):
        self.write_session(checksum_valid=False)
        report = self.verifier().scan()["reports"][0]
        self.assertFalse(report["passed"])
        self.assertIn("checksum_mismatch", report["failure_reasons"])

    def test_truncated_gzip_is_reported(self):
        self.write_session(truncate=True)
        report = self.verifier().scan()["reports"][0]
        self.assertFalse(report["passed"])
        self.assertIn(
            "gzip_or_json_integrity_failure",
            report["failure_reasons"],
        )

    def test_unrepaired_reconnect_gap_is_reported(self):
        values = valid_events()
        values.insert(
            2,
            event(
                2,
                "stream_disconnected",
                BASE + timedelta(seconds=2),
            ),
        )
        values.insert(
            3,
            event(
                3,
                "stream_connected",
                BASE + timedelta(seconds=3),
            ),
        )
        for index, value in enumerate(values):
            value["index"] = index
        self.write_session(events=values)
        report = self.verifier().scan()["reports"][0]
        self.assertIn(
            "unrepaired_reconnect_gap",
            report["failure_reasons"],
        )

    def test_timestamp_regression_is_reported(self):
        values = valid_events()
        values[2]["receipt_timestamp"] = (
            BASE - timedelta(seconds=1)
        ).isoformat()
        self.write_session(events=values)
        report = self.verifier().scan()["reports"][0]
        self.assertIn(
            "receipt_timestamp_regression",
            report["failure_reasons"],
        )

    def test_nondeterministic_replay_is_reported(self):
        self.write_session()
        counter = {"value": 0}

        def changing_replay(_raw):
            counter["value"] += 1
            value = str(counter["value"])
            return {
                "event_digest": value,
                "state_digest": value,
                "simulated_fill_digest": value,
            }

        report = self.verifier(replay_pass=changing_replay).scan()[
            "reports"
        ][0]
        self.assertIn(
            "nondeterministic_replay",
            report["failure_reasons"],
        )

    def test_secret_like_field_is_detected(self):
        values = valid_events()
        values[1]["payload"]["access_token"] = "must-not-appear"
        self.write_session(events=values)
        report = self.verifier().scan()["reports"][0]
        self.assertTrue(report["secrets_present"])
        self.assertIn(
            "secret_like_field_detected",
            report["failure_reasons"],
        )

    def test_repeated_execution_produces_identical_report(self):
        self.write_session()
        verifier = self.verifier()
        verifier.scan()
        report_path = self.output / "live-iex-20260728.json"
        first = report_path.read_bytes()
        verifier.scan()
        self.assertEqual(first, report_path.read_bytes())


if __name__ == "__main__":
    unittest.main()
