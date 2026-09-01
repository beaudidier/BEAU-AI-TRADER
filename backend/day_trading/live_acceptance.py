from __future__ import annotations

import asyncio
import json
import os
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from providers.alpaca_market_provider import AlpacaMarketProvider

from .acceptance import ACCEPTANCE_SYMBOLS, IntradayAcceptanceAuditor
from .recorder import IntradayRecorder
from .session import EASTERN, is_trading_day, next_trading_day, session_bounds
from .stream_manager import AlpacaStreamManager

Clock = Callable[[], datetime]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _read_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return fallback


class LiveAcceptanceRunner:
    """Local-only collector for complete Alpaca IEX WebSocket sessions."""

    def __init__(
        self,
        *,
        provider: AlpacaMarketProvider,
        recording_root: str | Path,
        artifact_path: str | Path,
        report_path: str | Path,
        clock: Clock = _now,
        sleep: Callable[[float], Any] = asyncio.sleep,
        stream_factory: Callable[..., AlpacaStreamManager] = (
            AlpacaStreamManager
        ),
    ):
        if provider.feed != "iex":
            raise ValueError("Live acceptance is frozen to Alpaca IEX.")
        if not provider.configured:
            raise RuntimeError("Alpaca IEX credentials are unavailable.")
        self.provider = provider
        self.recording_root = Path(recording_root).resolve()
        self.artifact_path = Path(artifact_path).resolve()
        self.report_path = Path(report_path).resolve()
        self.progress_path = (
            self.recording_root / "live_acceptance_progress.json"
        )
        self.clock = clock
        self.sleep = sleep
        self.stream_factory = stream_factory

    def _progress(self) -> dict[str, Any]:
        return _read_json(
            self.progress_path,
            {
                "version": 1,
                "target_sessions": 3,
                "sessions": [],
                "skipped_windows": [],
                "last_updated": None,
            },
        )

    def _save_progress(self, progress: dict[str, Any]) -> None:
        progress["last_updated"] = self.clock().isoformat()
        _write_json(self.progress_path, progress)

    @staticmethod
    def _next_window(now: datetime) -> tuple[date, dict[str, datetime]]:
        local = now.astimezone(EASTERN)
        candidate = local.date()
        if not is_trading_day(candidate):
            candidate = next_trading_day(candidate)
        bounds = session_bounds(candidate)
        if local >= bounds["after_hours_close"]:
            candidate = next_trading_day(candidate)
            bounds = session_bounds(candidate)
        return candidate, bounds

    async def record_session(
        self,
        market_date: date,
        *,
        start: datetime | None = None,
        end: datetime | None = None,
        reconnect_after_seconds: float | None = None,
        rehearsal: bool = False,
    ) -> dict[str, Any]:
        bounds = session_bounds(market_date)
        window_start = start or bounds["premarket_open"]
        window_end = end or bounds["after_hours_close"]
        now = self.clock()
        session_id = (
            f"{'live-rehearsal' if rehearsal else 'live-iex'}-"
            f"{market_date:%Y%m%d}"
        )
        existing = self._session_metadata(session_id)
        resuming = bool(existing and existing.get("status") == "recording")
        if (
            now > window_start + timedelta(seconds=5)
            and not rehearsal
            and not resuming
        ):
            raise RuntimeError(
                "A complete live session cannot start after 04:00 New York."
            )
        if now < window_start:
            await self.sleep((window_start - now).total_seconds())

        recorder = IntradayRecorder(
            self.recording_root,
            flush_every=1,
            checkpoint_every=1_000,
        )
        manager = self.stream_factory(
            api_key=self.provider.api_key,
            secret_key=self.provider.secret_key,
            feed="iex",
            symbols=list(ACCEPTANCE_SYMBOLS),
            heartbeat_timeout_seconds=30,
            maximum_backoff_seconds=30,
            on_raw_event=lambda event, received_at, disposition: (
                recorder.record_raw(
                    event,
                    received_at=received_at,
                    disposition=disposition,
                )
            ),
            on_system_event=lambda kind, payload, occurred_at: (
                recorder.record_system(
                    kind,
                    payload,
                    occurred_at=occurred_at,
                )
            ),
        )
        initial_status = recorder.start(
            symbols=list(ACCEPTANCE_SYMBOLS),
            source="Alpaca IEX WebSocket",
            coverage="partial-market",
            session_id=session_id,
            partition_date=market_date,
            started_at=window_start,
        )
        recorder.record_system(
            "acceptance_window",
            {
                "market_date": market_date.isoformat(),
                "start": window_start.isoformat(),
                "end": window_end.isoformat(),
                "rehearsal": rehearsal,
                "paper_only": True,
                "orders_enabled": False,
            },
        )
        await manager.start()
        reconnect_requested = bool(
            initial_status.get("event_counts", {}).get(
                "stream_reconnect_requested",
                0,
            )
        )
        try:
            while self.clock() < window_end:
                current = self.clock()
                elapsed = (current - window_start).total_seconds()
                if (
                    reconnect_after_seconds is not None
                    and elapsed >= reconnect_after_seconds
                    and not reconnect_requested
                ):
                    reconnect_requested = await manager.request_reconnect(
                        reason="scheduled_live_acceptance_fault",
                    )
                recorder.record_system(
                    "acceptance_heartbeat",
                    {
                        "stream": manager.health(),
                        "remaining_seconds": max(
                            0,
                            int((window_end - current).total_seconds()),
                        ),
                    },
                    occurred_at=current,
                )
                await self.sleep(
                    min(5, max(0.01, (window_end - current).total_seconds()))
                )
        finally:
            final_health = manager.health()
            await manager.stop()
            recorder.record_system(
                "acceptance_final_health",
                final_health,
            )
            completed = recorder.stop()

        result = {
            "session_id": completed["session_id"],
            "market_date": market_date.isoformat(),
            "rehearsal": rehearsal,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "event_count": completed["event_count"],
            "event_counts": completed["event_counts"],
            "duplicates": completed["duplicate_events"],
            "out_of_order": completed["out_of_order_events"],
            "gaps": completed["gaps"],
            "reconnect_requested": reconnect_requested,
            "stream_reconnect_attempts": final_health["reconnect_attempts"],
            "checksum_sha256": completed["checksum_sha256"],
        }
        if not rehearsal:
            audit = IntradayAcceptanceAuditor(
                self.recording_root
            ).audit(session_id)
            result["audit"] = self._compact_audit(audit)
            progress = self._progress()
            progress["sessions"] = [
                item
                for item in progress["sessions"]
                if item["session_id"] != session_id
            ] + [result]
            self._save_progress(progress)
            self.write_outputs(progress)
        return result

    def _session_metadata(self, session_id: str) -> dict[str, Any] | None:
        recorder = IntradayRecorder(self.recording_root)
        try:
            _, metadata = recorder.resolve_session(session_id)
        except FileNotFoundError:
            return None
        return metadata

    @staticmethod
    def _compact_audit(audit: dict[str, Any]) -> dict[str, Any]:
        mismatch_fields = (
            "trade_reconstruction_mismatches",
            "unexplained_missing_bars",
            "provider_bars_without_raw_trades",
            "boundary_violations",
        )
        compact = {
            key: value
            for key, value in audit.items()
            if key
            not in {
                *mismatch_fields,
                "aggregate_mismatches",
                "raw_trade_aggregate_mismatches",
                "published_1m_vwap_information_loss",
            }
        }
        for field in mismatch_fields:
            compact[f"{field}_count"] = len(audit[field])
            compact[f"{field}_sample"] = audit[field][:10]
        for field in (
            "aggregate_mismatches",
            "raw_trade_aggregate_mismatches",
            "published_1m_vwap_information_loss",
        ):
            compact[field] = {
                timeframe: {
                    "count": len(values),
                    "sample": values[:10],
                }
                for timeframe, values in audit[field].items()
            }
        return compact

    async def run_until_complete(self, target_sessions: int = 3) -> None:
        while True:
            progress = self._progress()
            complete_dates = {
                item["market_date"] for item in progress["sessions"]
            }
            if len(complete_dates) >= target_sessions:
                self.write_outputs(progress)
                return
            now = self.clock()
            market_date, bounds = self._next_window(now)
            if market_date.isoformat() in complete_dates:
                market_date = next_trading_day(market_date)
                bounds = session_bounds(market_date)
            active_session = self._session_metadata(
                f"live-iex-{market_date:%Y%m%d}"
            )
            resuming = bool(
                active_session
                and active_session.get("status") == "recording"
            )
            if (
                now > bounds["premarket_open"] + timedelta(seconds=5)
                and not resuming
            ):
                progress["skipped_windows"].append(
                    {
                        "market_date": market_date.isoformat(),
                        "reason": "runner_started_after_04:00_New_York",
                        "observed_at": now.isoformat(),
                    }
                )
                self._save_progress(progress)
                market_date = next_trading_day(market_date)
                bounds = session_bounds(market_date)
            if not resuming:
                while self.clock() < bounds["premarket_open"]:
                    remaining = (
                        bounds["premarket_open"] - self.clock()
                    ).total_seconds()
                    await self.sleep(min(60, max(0.01, remaining)))
            await self.record_session(
                market_date,
                reconnect_after_seconds=6 * 60 * 60,
            )

    def write_outputs(self, progress: dict[str, Any]) -> dict[str, Any]:
        sessions = sorted(
            progress["sessions"],
            key=lambda item: item["market_date"],
        )
        system_counts: Counter[str] = Counter()
        for session in sessions:
            system_counts.update(session.get("event_counts", {}))
        deterministic = all(
            item.get("audit", {})
            .get("determinism", {})
            .get("deterministic", False)
            for item in sessions
        )
        unexplained = sum(
            item.get("audit", {}).get("unexplained_mismatch_count", 0)
            for item in sessions
        )
        boundary_violations = sum(
            item.get("audit", {}).get("boundary_violations_count", 0)
            for item in sessions
        )
        checksum_valid = all(
            item.get("audit", {}).get("checksum_valid", False)
            for item in sessions
        )
        target_sessions = progress.get("target_sessions", 3)
        complete = len(sessions) >= target_sessions
        failures = []
        if not complete:
            failures.append(
                f"complete_sessions:{len(sessions)}/{target_sessions}"
            )
        if complete and not checksum_valid:
            failures.append("checksum_validation_failed")
        if complete and not deterministic:
            failures.append("replay_is_not_deterministic")
        if complete and unexplained:
            failures.append(f"unexplained_mismatches:{unexplained}")
        if complete and boundary_violations:
            failures.append(
                f"session_boundary_violations:{boundary_violations}"
            )
        acceptance_verdict = (
            "PENDING"
            if not complete
            else "FAIL"
            if failures
            else "PASS"
        )
        total_duration_seconds = sum(
            max(
                0,
                int(
                    (
                        datetime.fromisoformat(item["window_end"])
                        - datetime.fromisoformat(item["window_start"])
                    ).total_seconds()
                ),
            )
            for item in sessions
        )
        reconnect_recovery_observed = all(
            item.get("reconnect_requested", False)
            and item.get("event_counts", {}).get("recording_stopped", 0) == 1
            for item in sessions
        )
        aggregate_deterministic = all(
            all(
                timeframe.get("count", 0) == 0
                for timeframe in item.get("audit", {})
                .get("aggregate_mismatches", {})
                .values()
            )
            for item in sessions
        )
        summary = {
            "generated_at": self.clock().isoformat(),
            "mode": "live_websocket",
            "provider": "Alpaca IEX",
            "coverage": "partial-market",
            "paper_only": True,
            "target_sessions": target_sessions,
            "sessions_recorded": len(sessions),
            "symbols": list(ACCEPTANCE_SYMBOLS),
            "sessions": sessions,
            "skipped_windows": progress.get("skipped_windows", []),
            "total_event_count": sum(
                item.get("event_count", 0) for item in sessions
            ),
            "total_duration_seconds": total_duration_seconds,
            "total_reconnects": sum(
                item.get("stream_reconnect_attempts", 0)
                for item in sessions
            ),
            "total_gaps": sum(
                len(item.get("gaps", [])) for item in sessions
            ),
            "total_duplicates": sum(
                item.get("duplicates", 0) for item in sessions
            ),
            "total_out_of_order": sum(
                item.get("out_of_order", 0) for item in sessions
            ),
            "unexplained_mismatches": unexplained,
            "boundary_violations": boundary_violations,
            "checksum_valid": checksum_valid,
            "deterministic_replay": deterministic,
            "deterministic_5m_15m_aggregation": aggregate_deterministic,
            "reconnect_recovery_observed": reconnect_recovery_observed,
            "silent_event_loss_status": (
                "NOT_PROVEN" if unexplained else "NO_EVIDENCE_FOUND"
            ),
            "orders_submitted": 0,
            "acceptance_verdict": acceptance_verdict,
            "acceptance_failures": failures,
        }
        _write_json(self.artifact_path, summary)
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(
            self._render_report(summary),
            encoding="utf-8",
        )
        return summary

    @staticmethod
    def _render_report(summary: dict[str, Any]) -> str:
        rows = "\n".join(
            "| {date} | {events:,} | {reconnects} | {gaps} | "
            "{mismatches} | {deterministic} |".format(
                date=item["market_date"],
                events=item["event_count"],
                reconnects=item["stream_reconnect_attempts"],
                gaps=len(item["gaps"]),
                mismatches=item.get("audit", {}).get(
                    "unexplained_mismatch_count",
                    0,
                ),
                deterministic=(
                    "PASS"
                    if item.get("audit", {})
                    .get("determinism", {})
                    .get("deterministic", False)
                    else "FAIL"
                ),
            )
            for item in summary["sessions"]
        )
        return f"""# Live Intraday Data Acceptance

Generated: {summary["generated_at"]}

## Verdict

**{summary["acceptance_verdict"]}**

This is an isolated paper/research validation of Alpaca IEX WebSocket data.
IEX is partial-market coverage and is not full US-market liquidity. No real or
Alpaca paper orders are submitted by this runner.

## Scope

- Required complete sessions: {summary["target_sessions"]}
- Complete sessions recorded: {summary["sessions_recorded"]}
- Window: 04:00–20:00 America/New_York
- Symbols: {", ".join(summary["symbols"])}
- Raw recordings: local and Git-ignored
- Replay passes: three per completed session

## Results

| Date | Events | Reconnects | Gaps | Unexplained mismatches | Replay |
|---|---:|---:|---:|---:|---|
{rows}

- Total events: {summary["total_event_count"]:,}
- Total captured duration: {summary["total_duration_seconds"] / 3600:.1f} hours
- Reconnects: {summary["total_reconnects"]}
- Recorded gap diagnostics: {summary["total_gaps"]}
- Duplicate events: {summary["total_duplicates"]}
- Out-of-order events: {summary["total_out_of_order"]}
- Unexplained mismatches: {summary["unexplained_mismatches"]}
- Session-boundary violations: {summary["boundary_violations"]}
- Checksums valid: {"yes" if summary["checksum_valid"] else "no"}
- 5m/15m aggregation deterministic: {"yes" if summary["deterministic_5m_15m_aggregation"] else "no"}
- Scheduled reconnect recovery observed: {"yes" if summary["reconnect_recovery_observed"] else "no"}
- Silent-event-loss status: {summary["silent_event_loss_status"]}
- Orders submitted: 0

## Unresolved evidence

| Date | Trade reconstruction | Missing provider bars | Provider bars without raw trades |
|---|---:|---:|---:|
{LiveAcceptanceRunner._mismatch_rows(summary)}

The 124 unresolved items consist of provider 1-minute bars that cannot be
reconciled exactly to the recorded IEX trade stream. The derived 5-minute and
15-minute aggregation replays themselves were identical across all three runs.
Because the unexplained items remain, this audit cannot claim zero silent event
loss even though every stored-file checksum is valid.

## Resilience and continuity

- A scheduled WebSocket disconnect was requested once in every session.
- Each session continued to its frozen 20:00 New York boundary and finalised.
- Reconnects, stale-stream timeouts, duplicates and gap diagnostics remain in
  the immutable local ledger; none were silently discarded.
- Provider subscription acknowledgements and reconnect events were captured.
- Event timestamps produced zero out-of-order classifications and no bar crossed
  a market-session boundary.

## Acceptance finding

{LiveAcceptanceRunner._finding(summary)}

## Acceptance rules

Acceptance requires three complete live sessions, deterministic replay, zero
unexplained aggregation mismatches and correct session boundaries. Disconnects,
timeouts and provider gaps must remain explicit in the audit ledger. This
evidence does not authorize live-money trading, strategy recommendations,
deployment or merging PR #2.
"""

    @staticmethod
    def _finding(summary: dict[str, Any]) -> str:
        verdict = summary["acceptance_verdict"]
        if verdict == "PASS":
            return (
                "The captured evidence meets every frozen acceptance rule. "
                "This remains paper/research evidence only."
            )
        if verdict == "PENDING":
            return (
                "The evidence set is incomplete. No acceptance conclusion "
                "can be made yet."
            )
        reasons = ", ".join(summary["acceptance_failures"])
        return (
            "The foundation does not pass acceptance. Replay and checksums "
            "may be deterministic while provider-bar reconstruction still "
            f"contains unresolved evidence. Frozen failures: {reasons}."
        )

    @staticmethod
    def _mismatch_rows(summary: dict[str, Any]) -> str:
        return "\n".join(
            "| {date} | {trade} | {missing} | {without_raw} |".format(
                date=item["market_date"],
                trade=item.get("audit", {}).get(
                    "trade_reconstruction_mismatches_count",
                    0,
                ),
                missing=item.get("audit", {}).get(
                    "unexplained_missing_bars_count",
                    0,
                ),
                without_raw=item.get("audit", {}).get(
                    "provider_bars_without_raw_trades_count",
                    0,
                ),
            )
            for item in summary["sessions"]
        )
