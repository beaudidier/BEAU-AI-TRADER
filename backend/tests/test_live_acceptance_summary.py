from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from day_trading.summarize_live_acceptance import (
    EXIT_CODES,
    FAIL,
    INCOMPLETE,
    PASS,
    LiveAcceptanceSummaryGate,
)


def report(
    session_id: str,
    *,
    opening: bool = False,
    close: bool = False,
    premarket: bool = False,
    after_hours: bool = False,
) -> dict:
    return {
        "schema_version": 1,
        "session_id": session_id,
        "passed": True,
        "failure_reasons": [],
        "recording_completeness": "finalised",
        "checksum_result": {"algorithm": "sha256", "valid": True},
        "counts": {
            "trade": 10,
            "quote": 20,
            "bar_1m": 5,
            "bar_5m_provider": 1,
            "bar_15m_provider": 1,
        },
        "gaps": {
            "manifest": [],
            "sequence": [],
            "unrepaired_reconnects": [],
        },
        "repairs": [],
        "duplicates": 0,
        "out_of_order": 0,
        "boundary_violations": [],
        "stale_periods": [],
        "secrets_present": False,
        "coverage": {
            "duration_seconds": 28_800,
            "opening_0925_1030": opening,
            "close_1530_1610": close,
            "premarket": premarket,
            "after_hours": after_hours,
        },
        "mismatches": {"unexplained": 0},
        "silent_data_loss": 0,
        "orders_submitted": 0,
        "continuity": {
            "restart_tested": True,
            "state_restored": True,
        },
        "replay": {"runs": 3, "deterministic": True},
    }


class LiveAcceptanceSummaryGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.reports = root / "reports"
        self.reports.mkdir()
        self.output = root / "summary.json"

    def write(self, value: dict) -> Path:
        path = self.reports / f"{value['session_id']}.json"
        path.write_text(
            json.dumps(value, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return path

    def complete_set(self) -> list[dict]:
        return [
            report(
                "live-iex-20260729",
                opening=True,
                premarket=True,
            ),
            report(
                "live-iex-20260730",
                close=True,
                after_hours=True,
            ),
            report("live-iex-20260731"),
        ]

    def run_gate(self) -> dict:
        return LiveAcceptanceSummaryGate(
            self.reports,
            self.output,
        ).run()

    def test_complete_sessions_pass(self):
        for value in self.complete_set():
            self.write(value)
        summary = self.run_gate()
        self.assertEqual(summary["verdict"], PASS)
        self.assertEqual(EXIT_CODES[summary["verdict"]], 0)
        self.assertEqual(summary["eligible_sessions"], 3)
        self.assertEqual(summary["metrics"]["total_events"], 111)
        self.assertEqual(summary["metrics"]["trades"], 30)
        self.assertEqual(summary["metrics"]["quotes"], 60)

    def test_missing_third_session_is_incomplete(self):
        for value in self.complete_set()[:2]:
            self.write(value)
        summary = self.run_gate()
        self.assertEqual(summary["verdict"], INCOMPLETE)
        self.assertEqual(EXIT_CODES[summary["verdict"]], 2)
        self.assertIn("eligible_sessions:2/3", summary["unmet_criteria"])

    def assert_missing_coverage(self, field: str):
        values = self.complete_set()
        for value in values:
            value["coverage"][field] = False
            self.write(value)
        summary = self.run_gate()
        self.assertEqual(summary["verdict"], INCOMPLETE)
        self.assertIn(
            f"missing_coverage:{field}",
            summary["unmet_criteria"],
        )

    def test_missing_opening_coverage_is_incomplete(self):
        self.assert_missing_coverage("opening_0925_1030")

    def test_missing_close_coverage_is_incomplete(self):
        self.assert_missing_coverage("close_1530_1610")

    def test_missing_premarket_coverage_is_incomplete(self):
        self.assert_missing_coverage("premarket")

    def test_missing_after_hours_coverage_is_incomplete(self):
        self.assert_missing_coverage("after_hours")

    def assert_hard_failure(
        self,
        update,
        expected_reason: str,
    ):
        values = self.complete_set()
        update(values[0])
        for value in values:
            self.write(value)
        summary = self.run_gate()
        self.assertEqual(summary["verdict"], FAIL)
        self.assertEqual(EXIT_CODES[summary["verdict"]], 1)
        self.assertIn(
            f"live-iex-20260729:{expected_reason}",
            summary["unmet_criteria"],
        )

    def test_unrepaired_gap_fails(self):
        self.assert_hard_failure(
            lambda value: value["gaps"]["unrepaired_reconnects"].append(
                {"from": "a", "to": "b"}
            ),
            "unrepaired_reconnect_gap",
        )

    def test_checksum_failure_fails(self):
        self.assert_hard_failure(
            lambda value: value["checksum_result"].update(valid=False),
            "checksum_failure",
        )

    def test_nondeterministic_replay_fails(self):
        self.assert_hard_failure(
            lambda value: value["replay"].update(deterministic=False),
            "replay_mismatch",
        )

    def test_unexplained_bar_mismatch_fails(self):
        self.assert_hard_failure(
            lambda value: value["mismatches"].update(unexplained=1),
            "unexplained_bar_mismatch",
        )

    def test_boundary_violation_fails(self):
        self.assert_hard_failure(
            lambda value: value["boundary_violations"].append(
                {"timeframe": "5m"}
            ),
            "boundary_violation",
        )

    def test_failed_restart_recovery_fails(self):
        self.assert_hard_failure(
            lambda value: value["continuity"].update(
                state_restored=False
            ),
            "continuity_not_restored",
        )

    def test_silent_data_loss_fails(self):
        self.assert_hard_failure(
            lambda value: value.update(silent_data_loss=1),
            "silent_data_loss",
        )

    def test_secret_finding_fails(self):
        self.assert_hard_failure(
            lambda value: value.update(secrets_present=True),
            "secret_detected",
        )

    def test_order_submission_fails(self):
        self.assert_hard_failure(
            lambda value: value.update(orders_submitted=1),
            "orders_submitted",
        )

    def test_output_is_deterministic_and_sources_are_unchanged(self):
        paths = [self.write(value) for value in self.complete_set()]
        before = {
            path.name: path.read_bytes()
            for path in paths
        }
        first = self.run_gate()
        first_bytes = self.output.read_bytes()
        second = self.run_gate()
        self.assertEqual(first, second)
        self.assertEqual(first_bytes, self.output.read_bytes())
        self.assertEqual(
            before,
            {path.name: path.read_bytes() for path in paths},
        )

    def test_ineligible_reports_are_ignored(self):
        historical = report("historical-20260729")
        rehearsal = report("rehearsal-20260729")
        active = report("live-iex-active")
        active["recording_completeness"] = "active"
        for value in (historical, rehearsal, active):
            self.write(value)
        summary = self.run_gate()
        self.assertEqual(summary["eligible_sessions"], 0)
        self.assertEqual(len(summary["ignored_reports"]), 3)


if __name__ == "__main__":
    unittest.main()
