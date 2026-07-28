from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .bar_aggregator import BarAggregator
from .models import Bar, Completeness
from .session import classify_market_session

MANIFEST_REQUIRED_FIELDS = {
    "session_id",
    "status",
    "symbols",
    "source",
    "coverage",
    "started_at",
    "market_date",
    "completed_at",
    "event_count",
    "event_counts",
    "checksum_sha256",
    "compressed_file",
}
SECRET_MARKERS = {
    "api_key",
    "apikey",
    "authorization",
    "password",
    "secret",
    "token",
}
BAR_WIDTHS = {
    "bar_1m": 1,
    "bar_5m_provider": 5,
    "bar_15m_provider": 15,
}
REPAIR_EVENTS = {
    "stream_backfill_completed",
    "reconnect_gap_verified",
    "recording_tail_recovered",
}


def _stable(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _contains_secret(value: Any) -> bool:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower()
            if any(marker in normalized for marker in SECRET_MARKERS):
                return True
            if _contains_secret(nested):
                return True
    elif isinstance(value, list):
        return any(_contains_secret(item) for item in value)
    return False


class LiveSessionVerifier:
    """Strict read-only verifier for finalised live session recordings."""

    def __init__(
        self,
        recording_root: str | Path,
        output_root: str | Path,
        *,
        replay_pass: Callable[[list[bytes]], dict[str, Any]] | None = None,
    ):
        self.recording_root = Path(recording_root).resolve()
        self.output_root = Path(output_root).resolve()
        self._custom_replay_pass = replay_pass

    def scan(self) -> dict[str, Any]:
        manifests = sorted(self.recording_root.glob("*/*.meta.json"))
        manifest_data_files: set[Path] = set()
        completed: list[tuple[Path, dict[str, Any]]] = []
        skipped = []
        for path in manifests:
            try:
                manifest = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                skipped.append(
                    {
                        "session_id": path.name.removesuffix(".meta.json"),
                        "reason": "invalid_manifest",
                    }
                )
                continue
            data_path = path.with_name(
                str(manifest.get("compressed_file", ""))
            )
            manifest_data_files.add(data_path)
            session_id = str(manifest.get("session_id") or "")
            if (
                not session_id.startswith("live-iex-")
                or "websocket"
                not in str(manifest.get("source", "")).lower()
            ):
                skipped.append(
                    {
                        "session_id": session_id,
                        "reason": "not_live_acceptance_session",
                    }
                )
                continue
            if manifest.get("status") != "completed":
                skipped.append(
                    {
                        "session_id": manifest.get("session_id"),
                        "reason": "active_or_incomplete",
                    }
                )
                continue
            if not manifest.get("checksum_sha256"):
                skipped.append(
                    {
                        "session_id": manifest.get("session_id"),
                        "reason": "missing_final_checksum",
                    }
                )
                continue
            completed.append((path, manifest))

        for data_path in sorted(
            self.recording_root.glob("*/*.jsonl.gz")
        ):
            if data_path not in manifest_data_files:
                skipped.append(
                    {
                        "session_id": data_path.name.removesuffix(
                            ".jsonl.gz"
                        ),
                        "reason": "missing_final_manifest",
                    }
                )

        reports = [
            self.verify_manifest(path, manifest)
            for path, manifest in completed
        ]
        return {
            "schema_version": 1,
            "finalised_sessions": len(reports),
            "passed_sessions": sum(
                1 for report in reports if report["passed"]
            ),
            "failed_sessions": sum(
                1 for report in reports if not report["passed"]
            ),
            "reports": reports,
            "skipped": sorted(
                skipped,
                key=lambda item: (
                    str(item.get("session_id")),
                    item["reason"],
                ),
            ),
        }

    def verify_manifest(
        self,
        manifest_path: Path,
        manifest: dict[str, Any],
    ) -> dict[str, Any]:
        session_id = str(manifest.get("session_id") or "")
        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}",
            session_id,
        ):
            return self._failed_report(
                session_id or "invalid",
                ["manifest_session_id_invalid"],
            )
        data_path = manifest_path.with_name(
            str(manifest.get("compressed_file", ""))
        )
        failures = []
        manifest_secrets_present = _contains_secret(manifest)
        if manifest_secrets_present:
            failures.append("secret_like_field_detected")
        missing = sorted(MANIFEST_REQUIRED_FIELDS - set(manifest))
        if missing:
            failures.append(
                "manifest_missing_fields:" + ",".join(missing)
            )
        if manifest.get("status") != "completed":
            failures.append("recording_not_finalised")
        if not data_path.is_file():
            failures.append("recording_file_missing")
            return self._store(
                self._failed_report(session_id, failures)
            )

        before = data_path.stat()
        raw_lines: list[bytes] = []
        events: list[dict[str, Any]] = []
        gzip_valid = True
        try:
            with gzip.open(data_path, "rb") as source:
                for raw in source:
                    raw_lines.append(raw)
                    events.append(json.loads(raw))
        except (EOFError, OSError, json.JSONDecodeError):
            gzip_valid = False
            failures.append("gzip_or_json_integrity_failure")
        after = data_path.stat()
        unchanged = (
            before.st_size == after.st_size
            and before.st_mtime_ns == after.st_mtime_ns
        )
        if not unchanged:
            failures.append("recording_changed_during_verification")
        if not gzip_valid:
            return self._store(
                {
                    **self._failed_report(session_id, failures),
                    "recording_completeness": "corrupt",
                    "gzip_integrity": False,
                }
            )

        digest = hashlib.sha256(b"".join(raw_lines)).hexdigest()
        checksum_valid = digest == manifest.get("checksum_sha256")
        if not checksum_valid:
            failures.append("checksum_mismatch")
        if len(events) != manifest.get("event_count"):
            failures.append("manifest_event_count_mismatch")

        analysis = self._analyse_events(events)
        if analysis["index_discontinuities"]:
            failures.append("append_only_index_discontinuity")
        if analysis["sequence_gaps"]:
            failures.append("provider_sequence_gap")
        if analysis["receipt_timestamp_regressions"]:
            failures.append("receipt_timestamp_regression")
        if analysis["provider_timestamp_regressions"]:
            failures.append("provider_timestamp_regression")
        if analysis["duplicates"]:
            failures.append("duplicate_events_present")
        if analysis["out_of_order"]:
            failures.append("out_of_order_events_present")
        if analysis["boundary_violations"]:
            failures.append("session_boundary_violation")
        if analysis["unrepaired_reconnects"]:
            failures.append("unrepaired_reconnect_gap")
        if analysis["stale_periods"]:
            failures.append("stale_stream_period")
        if analysis["secrets_present"]:
            failures.append("secret_like_field_detected")
        if manifest.get("gaps") and not analysis["repairs"]:
            failures.append("unrepaired_manifest_gap")

        replay_results = [
            (
                self._custom_replay_pass(raw_lines)
                if self._custom_replay_pass
                else self._replay_pass(raw_lines)
            )
            for _ in range(3)
        ]
        replay_deterministic = (
            len({_stable(item) for item in replay_results}) == 1
        )
        if not replay_deterministic:
            failures.append("nondeterministic_replay")

        report = {
            "schema_version": 1,
            "session_id": session_id,
            "passed": not failures,
            "failure_reasons": sorted(set(failures)),
            "recording_completeness": (
                "finalised" if unchanged else "changed_during_read"
            ),
            "manifest_schema_valid": not missing,
            "gzip_integrity": gzip_valid,
            "checksum_result": {
                "algorithm": "sha256",
                "valid": checksum_valid,
                "digest": digest,
            },
            "counts": analysis["counts"],
            "gaps": {
                "manifest": manifest.get("gaps", []),
                "sequence": analysis["sequence_gaps"],
                "unrepaired_reconnects": analysis[
                    "unrepaired_reconnects"
                ],
            },
            "repairs": analysis["repairs"],
            "backfilled_intervals": analysis["backfilled_intervals"],
            "timestamp_checks": {
                "receipt_regressions": analysis[
                    "receipt_timestamp_regressions"
                ],
                "provider_regressions": analysis[
                    "provider_timestamp_regressions"
                ],
                "index_discontinuities": analysis[
                    "index_discontinuities"
                ],
            },
            "duplicates": analysis["duplicates"],
            "out_of_order": analysis["out_of_order"],
            "boundary_violations": analysis["boundary_violations"],
            "stale_periods": analysis["stale_periods"],
            "secrets_present": (
                manifest_secrets_present or analysis["secrets_present"]
            ),
            "rebuilt_state": analysis["rebuilt_state"],
            "replay": {
                "runs": 3,
                "deterministic": replay_deterministic,
                "digests": [
                    item["event_digest"] for item in replay_results
                ],
                "state_digests": [
                    item["state_digest"] for item in replay_results
                ],
                "simulated_fill_digests": [
                    item["simulated_fill_digest"]
                    for item in replay_results
                ],
            },
        }
        return self._store(report)

    def _analyse_events(
        self,
        events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        counts: Counter[str] = Counter()
        last_receipt: datetime | None = None
        last_provider: dict[tuple[str, str], datetime] = {}
        last_sequence: dict[tuple[str, str], int] = {}
        index_discontinuities = []
        receipt_regressions = []
        provider_regressions = []
        sequence_gaps = []
        boundary_violations = []
        repairs = []
        backfilled = []
        disconnects: list[dict[str, Any]] = []
        reconnects = []
        stale_periods = []
        quotes: dict[str, dict[str, Any]] = {}
        spread_state: dict[str, dict[str, float]] = {}
        minute_bars: list[Bar] = []
        secrets_present = False

        for position, event in enumerate(events):
            event_type = str(event.get("event_type", "unknown"))
            counts[event_type] += 1
            secrets_present = secrets_present or _contains_secret(event)
            if event.get("index") != position:
                index_discontinuities.append(
                    {
                        "position": position,
                        "recorded_index": event.get("index"),
                    }
                )
            receipt = _timestamp(event["receipt_timestamp"])
            if last_receipt and receipt < last_receipt:
                receipt_regressions.append(
                    {
                        "index": position,
                        "previous": last_receipt.isoformat(),
                        "current": receipt.isoformat(),
                    }
                )
            last_receipt = receipt
            symbol = str(event.get("symbol") or "")
            provider_value = event.get("provider_timestamp")
            if provider_value and symbol:
                provider = _timestamp(provider_value)
                key = (symbol, event_type)
                previous = last_provider.get(key)
                if previous and provider < previous:
                    provider_regressions.append(
                        {
                            "index": position,
                            "symbol": symbol,
                            "event_type": event_type,
                        }
                    )
                if previous is None or provider >= previous:
                    last_provider[key] = provider
            sequence = event.get("sequence")
            if isinstance(sequence, int) and symbol:
                key = (symbol, event_type)
                previous_sequence = last_sequence.get(key)
                if (
                    previous_sequence is not None
                    and sequence > previous_sequence + 1
                ):
                    sequence_gaps.append(
                        {
                            "symbol": symbol,
                            "event_type": event_type,
                            "from": previous_sequence + 1,
                            "to": sequence - 1,
                        }
                    )
                last_sequence[key] = max(
                    sequence,
                    previous_sequence or sequence,
                )

            if event_type in BAR_WIDTHS and provider_value:
                width = BAR_WIDTHS[event_type]
                start = _timestamp(provider_value).replace(
                    second=0,
                    microsecond=0,
                )
                ending = start + timedelta(minutes=width - 1)
                if classify_market_session(
                    start
                ) != classify_market_session(ending):
                    boundary_violations.append(
                        {
                            "symbol": symbol,
                            "event_type": event_type,
                            "timestamp": start.isoformat(),
                        }
                    )
                if (
                    event_type == "bar_1m"
                    and event.get("disposition") == "accepted"
                ):
                    payload = event.get("payload") or {}
                    minute_bars.append(
                        Bar(
                            ticker=symbol,
                            timeframe="1m",
                            open=float(payload["o"]),
                            high=float(payload["h"]),
                            low=float(payload["l"]),
                            close=float(payload["c"]),
                            volume=float(payload["v"]),
                            vwap=(
                                float(payload["vw"])
                                if payload.get("vw") is not None
                                else None
                            ),
                            timestamp=start,
                            source=str(event.get("source") or "unknown"),
                            completeness=Completeness.CLOSED,
                        )
                    )
            if event_type == "quote" and provider_value:
                payload = event.get("payload") or {}
                bid = float(payload.get("bp", 0))
                ask = float(payload.get("ap", 0))
                if 0 < bid <= ask:
                    midpoint = (bid + ask) / 2
                    quotes[symbol] = {
                        "bid": bid,
                        "ask": ask,
                        "timestamp": str(provider_value),
                    }
                    spread_state[symbol] = {
                        "spread": ask - bid,
                        "spread_percent": (
                            (ask - bid) / midpoint * 100
                            if midpoint
                            else 0
                        ),
                    }
            if event_type == "stream_disconnected":
                disconnects.append(
                    {
                        "index": position,
                        "timestamp": receipt.isoformat(),
                    }
                )
            elif event_type == "stream_connected" and disconnects:
                reconnects.append(
                    {
                        "disconnect": disconnects[-1],
                        "connected_index": position,
                        "connected_at": receipt.isoformat(),
                    }
                )
            elif event_type == "stream_stale":
                stale_periods.append(
                    {
                        "index": position,
                        "timestamp": receipt.isoformat(),
                    }
                )
            if event_type in REPAIR_EVENTS:
                detail = {
                    "event_type": event_type,
                    "index": position,
                    "payload": event.get("payload") or {},
                }
                repairs.append(detail)
                if event_type == "stream_backfill_completed":
                    backfilled.append(detail["payload"])

        unrepaired_reconnects = []
        for reconnect in reconnects:
            start_index = reconnect["disconnect"]["index"]
            end_index = reconnect["connected_index"]
            next_disconnect = min(
                (
                    item["index"]
                    for item in disconnects
                    if item["index"] > end_index
                ),
                default=len(events),
            )
            repaired = any(
                end_index < repair["index"] < next_disconnect
                for repair in repairs
            )
            if not repaired:
                unrepaired_reconnects.append(reconnect)
        if len(disconnects) > len(reconnects):
            unrepaired_reconnects.extend(disconnects[len(reconnects) :])

        aggregator = BarAggregator(maximum_bars_per_ticker=5_000)
        for bar in minute_bars:
            aggregator.add_minute_bar(
                bar,
                received_at=bar.timestamp + timedelta(minutes=1),
                historical_backfill=True,
            )
        symbols = sorted({bar.ticker for bar in minute_bars} | set(quotes))
        rebuilt = {
            "bar_counts": {
                timeframe: sum(
                    len(aggregator.bars(symbol, timeframe))
                    for symbol in symbols
                )
                for timeframe in ("1m", "5m", "15m")
            },
            "quote_state": quotes,
            "spread_state": spread_state,
        }
        return {
            "counts": dict(sorted(counts.items())),
            "index_discontinuities": index_discontinuities,
            "receipt_timestamp_regressions": receipt_regressions,
            "provider_timestamp_regressions": provider_regressions,
            "sequence_gaps": sequence_gaps,
            "duplicates": counts.get("duplicate", 0)
            + sum(
                1
                for event in events
                if event.get("disposition") == "duplicate"
            ),
            "out_of_order": sum(
                1
                for event in events
                if event.get("disposition") == "out_of_order"
            ),
            "boundary_violations": boundary_violations,
            "repairs": repairs,
            "backfilled_intervals": backfilled,
            "unrepaired_reconnects": unrepaired_reconnects,
            "stale_periods": stale_periods,
            "secrets_present": secrets_present,
            "rebuilt_state": rebuilt,
        }

    def _replay_pass(self, raw_lines: list[bytes]) -> dict[str, Any]:
        events = [json.loads(raw) for raw in raw_lines]
        analysis = self._analyse_events(events)
        event_digest = hashlib.sha256(b"".join(raw_lines)).hexdigest()
        state = {
            "rebuilt_state": analysis["rebuilt_state"],
            "event_order": [
                {
                    "index": event.get("index"),
                    "event_type": event.get("event_type"),
                    "symbol": event.get("symbol"),
                    "provider_timestamp": event.get("provider_timestamp"),
                    "receipt_timestamp": event.get("receipt_timestamp"),
                }
                for event in events
            ],
        }
        fills: list[dict[str, Any]] = []
        return {
            "event_digest": event_digest,
            "state_digest": hashlib.sha256(
                _stable(state).encode()
            ).hexdigest(),
            "simulated_fill_digest": hashlib.sha256(
                _stable(fills).encode()
            ).hexdigest(),
        }

    def _store(self, report: dict[str, Any]) -> dict[str, Any]:
        self.output_root.mkdir(parents=True, exist_ok=True)
        target = self.output_root / f"{report['session_id']}.json"
        payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
        if target.exists():
            existing = target.read_text(encoding="utf-8")
            if existing != payload:
                raise RuntimeError(
                    "Immutable session report already exists with different "
                    "content."
                )
            return report
        temporary = target.with_suffix(".json.tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, target)
        return report

    @staticmethod
    def _failed_report(
        session_id: str,
        failures: list[str],
    ) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "session_id": session_id,
            "passed": False,
            "failure_reasons": sorted(set(failures)),
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    repository_root = Path(__file__).resolve().parents[2]
    parser.add_argument(
        "--recording-root",
        type=Path,
        default=(
            repository_root
            / "backend"
            / "data"
            / "day_trading_recordings"
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=(
            repository_root
            / "artifacts"
            / "live_session_acceptance"
        ),
    )
    arguments = parser.parse_args()
    summary = LiveSessionVerifier(
        arguments.recording_root,
        arguments.output_root,
    ).scan()
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["failed_sessions"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
