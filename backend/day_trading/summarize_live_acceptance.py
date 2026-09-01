from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any

PASS = "PASS"
FAIL = "FAIL"
INCOMPLETE = "INCOMPLETE"
EXIT_CODES = {PASS: 0, FAIL: 1, INCOMPLETE: 2}


class LiveAcceptanceSummaryGate:
    """Deterministic, read-only gate over immutable verifier reports."""

    def __init__(
        self,
        report_root: str | Path,
        output_path: str | Path,
    ):
        self.report_root = Path(report_root).resolve()
        self.output_path = Path(output_path).resolve()

    def run(self) -> dict[str, Any]:
        reports, ignored = self._reports()
        hard_failures: list[str] = []
        missing: list[str] = []
        if len(reports) < 3:
            missing.append(f"eligible_sessions:{len(reports)}/3")

        coverage = {
            "opening_0925_1030": any(
                report["coverage"].get("opening_0925_1030", False)
                for report in reports
            ),
            "close_1530_1610": any(
                report["coverage"].get("close_1530_1610", False)
                for report in reports
            ),
            "premarket": any(
                report["coverage"].get("premarket", False)
                for report in reports
            ),
            "after_hours": any(
                report["coverage"].get("after_hours", False)
                for report in reports
            ),
        }
        for name, available in coverage.items():
            if not available:
                missing.append(f"missing_coverage:{name}")

        for report in reports:
            session_id = report["session_id"]
            if not report["passed"]:
                hard_failures.append(f"{session_id}:session_verifier_failed")
            if report.get("silent_data_loss", 0) != 0:
                hard_failures.append(f"{session_id}:silent_data_loss")
            if report.get("gaps", {}).get("unrepaired_reconnects"):
                hard_failures.append(
                    f"{session_id}:unrepaired_reconnect_gap"
                )
            if not report.get("checksum_result", {}).get("valid", False):
                hard_failures.append(f"{session_id}:checksum_failure")
            if report.get("mismatches", {}).get("unexplained", 0):
                hard_failures.append(
                    f"{session_id}:unexplained_bar_mismatch"
                )
            if not report.get("replay", {}).get("deterministic", False):
                hard_failures.append(f"{session_id}:replay_mismatch")
            if report.get("boundary_violations"):
                hard_failures.append(f"{session_id}:boundary_violation")
            continuity = report.get("continuity", {})
            if (
                continuity.get("restart_tested")
                and not continuity.get("state_restored")
            ):
                hard_failures.append(
                    f"{session_id}:continuity_not_restored"
                )
            if report.get("orders_submitted", 0) != 0:
                hard_failures.append(f"{session_id}:orders_submitted")
            if report.get("secrets_present", False):
                hard_failures.append(f"{session_id}:secret_detected")

        verdict = (
            FAIL
            if hard_failures
            else INCOMPLETE
            if missing
            else PASS
        )
        event_totals: Counter[str] = Counter()
        for report in reports:
            event_totals.update(report.get("counts", {}))
        summary = {
            "schema_version": 1,
            "verdict": verdict,
            "unmet_criteria": sorted(set(hard_failures + missing)),
            "eligible_sessions": len(reports),
            "session_ids": [
                report["session_id"] for report in reports
            ],
            "ignored_reports": ignored,
            "metrics": {
                "total_duration_seconds": sum(
                    report["coverage"].get("duration_seconds", 0)
                    for report in reports
                ),
                "total_events": sum(
                    report.get("checksum_result", {}).get(
                        "event_count",
                        sum(report.get("counts", {}).values()),
                    )
                    for report in reports
                ),
                "trades": event_totals.get("trade", 0),
                "quotes": event_totals.get("quote", 0),
                "provider_bars": {
                    "1m": event_totals.get("bar_1m", 0),
                    "5m": event_totals.get("bar_5m_provider", 0),
                    "15m": event_totals.get("bar_15m_provider", 0),
                },
                "duplicates": sum(
                    report.get("duplicates", 0) for report in reports
                ),
                "out_of_order": sum(
                    report.get("out_of_order", 0) for report in reports
                ),
                "reconnects": event_totals.get(
                    "stream_disconnected",
                    0,
                ),
                "repaired_gaps": sum(
                    len(report.get("repairs", [])) for report in reports
                ),
                "unrepaired_gaps": sum(
                    len(
                        report.get("gaps", {}).get(
                            "unrepaired_reconnects",
                            [],
                        )
                    )
                    for report in reports
                ),
                "stale_periods": sum(
                    len(report.get("stale_periods", []))
                    for report in reports
                ),
                "checksum_failures": sum(
                    not report.get("checksum_result", {}).get(
                        "valid",
                        False,
                    )
                    for report in reports
                ),
                "unexplained_mismatches": sum(
                    report.get("mismatches", {}).get("unexplained", 0)
                    for report in reports
                ),
                "replay_digest_consistent": all(
                    report.get("replay", {}).get(
                        "deterministic",
                        False,
                    )
                    for report in reports
                ),
                "boundary_coverage": coverage,
                "order_count": sum(
                    report.get("orders_submitted", 0)
                    for report in reports
                ),
                "secret_scan_findings": sum(
                    bool(report.get("secrets_present", False))
                    for report in reports
                ),
            },
        }
        self._write(summary)
        return summary

    def _reports(self) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
        values = []
        ignored = []
        for path in sorted(self.report_root.glob("*.json")):
            try:
                report = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                ignored.append(
                    {"file": path.name, "reason": "invalid_json"}
                )
                continue
            session_id = str(report.get("session_id") or "")
            if (
                not session_id.startswith("live-iex-")
                or report.get("recording_completeness")
                in {"active", "incomplete"}
                or not isinstance(report.get("passed"), bool)
            ):
                ignored.append(
                    {"file": path.name, "reason": "ineligible_report"}
                )
                continue
            values.append(report)
        values.sort(key=lambda item: item["session_id"])
        ignored.sort(key=lambda item: (item["file"], item["reason"]))
        return values, ignored

    def _write(self, summary: dict[str, Any]) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(summary, indent=2, sort_keys=True) + "\n"
        if self.output_path.exists() and (
            self.output_path.read_text(encoding="utf-8") == payload
        ):
            return
        temporary = self.output_path.with_suffix(
            f"{self.output_path.suffix}.tmp"
        )
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.output_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    repository_root = Path(__file__).resolve().parents[2]
    parser.add_argument(
        "--report-root",
        type=Path,
        default=(
            repository_root / "artifacts" / "live_session_acceptance"
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=(
            repository_root
            / "artifacts"
            / "live_websocket_acceptance_summary.json"
        ),
    )
    arguments = parser.parse_args()
    summary = LiveAcceptanceSummaryGate(
        arguments.report_root,
        arguments.output,
    ).run()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return EXIT_CODES[summary["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
