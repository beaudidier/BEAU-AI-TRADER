from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from day_trading.live_acceptance import LiveAcceptanceRunner


def session(
    market_date: str,
    *,
    unexplained: int = 0,
    checksum_valid: bool = True,
    deterministic: bool = True,
) -> dict:
    return {
        "session_id": "live-iex-" + market_date.replace("-", ""),
        "market_date": market_date,
        "window_start": f"{market_date}T04:00:00-04:00",
        "window_end": f"{market_date}T20:00:00-04:00",
        "event_count": 100,
        "event_counts": {
            "quote": 80,
            "trade": 20,
            "recording_stopped": 1,
        },
        "duplicates": 2,
        "out_of_order": 0,
        "gaps": [{"reason": "visible_provider_gap"}],
        "stream_reconnect_attempts": 1,
        "reconnect_requested": True,
        "audit": {
            "checksum_valid": checksum_valid,
            "unexplained_mismatch_count": unexplained,
            "boundary_violations_count": 0,
            "aggregate_mismatches": {
                "5m": {"count": 0, "sample": []},
                "15m": {"count": 0, "sample": []},
            },
            "determinism": {"deterministic": deterministic},
        },
    }


class LiveAcceptanceOutputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.runner = object.__new__(LiveAcceptanceRunner)
        self.runner.artifact_path = root / "summary.json"
        self.runner.report_path = root / "report.md"
        self.runner.clock = lambda: datetime.now(timezone.utc)

    def write(self, sessions: list[dict]) -> dict:
        return self.runner.write_outputs(
            {
                "target_sessions": 3,
                "sessions": sessions,
                "skipped_windows": [],
            }
        )

    def test_incomplete_evidence_is_pending(self):
        summary = self.write(
            [session("2026-08-19"), session("2026-08-20")]
        )
        self.assertEqual(summary["acceptance_verdict"], "PENDING")
        self.assertEqual(
            summary["acceptance_failures"], ["complete_sessions:2/3"]
        )

    def test_complete_clean_evidence_passes(self):
        summary = self.write(
            [
                session("2026-08-19"),
                session("2026-08-20"),
                session("2026-08-31"),
            ]
        )
        self.assertEqual(summary["acceptance_verdict"], "PASS")
        self.assertEqual(summary["acceptance_failures"], [])
        self.assertEqual(summary["total_event_count"], 300)
        self.assertEqual(summary["total_gaps"], 3)
        self.assertEqual(summary["orders_submitted"], 0)

    def test_complete_unexplained_mismatches_fail(self):
        summary = self.write(
            [
                session("2026-08-19", unexplained=28),
                session("2026-08-20", unexplained=36),
                session("2026-08-31", unexplained=60),
            ]
        )
        self.assertEqual(summary["acceptance_verdict"], "FAIL")
        self.assertIn(
            "unexplained_mismatches:124",
            summary["acceptance_failures"],
        )
        report = self.runner.report_path.read_text(encoding="utf-8")
        self.assertIn("does not pass acceptance", report)

    def test_checksum_and_replay_failures_are_explicit(self):
        summary = self.write(
            [
                session("2026-08-19", checksum_valid=False),
                session("2026-08-20", deterministic=False),
                session("2026-08-31"),
            ]
        )
        self.assertEqual(summary["acceptance_verdict"], "FAIL")
        self.assertIn(
            "checksum_validation_failed",
            summary["acceptance_failures"],
        )
        self.assertIn(
            "replay_is_not_deterministic",
            summary["acceptance_failures"],
        )

    def test_output_is_valid_json(self):
        summary = self.write(
            [
                session("2026-08-19"),
                session("2026-08-20"),
                session("2026-08-31"),
            ]
        )
        stored = json.loads(
            self.runner.artifact_path.read_text(encoding="utf-8")
        )
        self.assertEqual(stored, summary)


if __name__ == "__main__":
    unittest.main()
