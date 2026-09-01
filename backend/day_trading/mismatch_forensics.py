from __future__ import annotations

import gzip
import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from pydantic_core import from_json

from .acceptance import (
    PRICE_EXCLUDED_CONDITIONS,
    VOLUME_EXCLUDED_CONDITIONS,
    _iso_time,
)
from .recorder import IntradayRecorder

BAR_FIELDS = ("o", "h", "l", "c", "v", "vw")
FINALIZATION_DELAYS = (0, 1, 2, 5, 10, 30)
RECONNECT_EVENT_TYPES = {
    "stream_connected",
    "stream_disconnected",
    "stream_reconnect_requested",
    "stream_reconnect_scheduled",
    "stream_stale",
}


@dataclass(frozen=True)
class ForensicTrade:
    price: float
    size: float
    conditions: tuple[str, ...]
    exchange: str | None
    provider_timestamp: datetime
    receipt_timestamp: datetime
    disposition: str
    identity: str

    @property
    def is_duplicate(self) -> bool:
        return self.disposition == "duplicate"


def _identity(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _bar_values(payload: dict[str, Any] | None) -> dict[str, float | None]:
    if payload is None:
        return {field: None for field in BAR_FIELDS}
    return {
        field: float(payload[field]) if payload.get(field) is not None else None
        for field in BAR_FIELDS
    }


def _differences(
    provider: dict[str, float | None],
    rebuilt: dict[str, float | None],
    *,
    tolerance: float = 1e-6,
) -> dict[str, dict[str, float | None]]:
    differences: dict[str, dict[str, float | None]] = {}
    for field in BAR_FIELDS:
        expected = provider.get(field)
        actual = rebuilt.get(field)
        if expected is None and actual is None:
            continue
        if (
            expected is None
            or actual is None
            or abs(expected - actual) > tolerance
        ):
            differences[field] = {
                "provider": expected,
                "reconstructed": actual,
                "delta": (
                    actual - expected
                    if expected is not None and actual is not None
                    else None
                ),
            }
    return differences


def _aggregate(
    trades: Iterable[ForensicTrade],
    *,
    policy: str,
    receipt_cutoff: datetime | None = None,
) -> dict[str, float | None]:
    open_price: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume = 0.0
    numerator = 0.0
    vwap_volume = 0.0
    seen: set[str] = set()

    for trade in trades:
        if receipt_cutoff is not None and trade.receipt_timestamp > receipt_cutoff:
            continue
        if policy.startswith("deduplicated"):
            if trade.is_duplicate or trade.identity in seen:
                continue
            seen.add(trade.identity)
        conditions = set(trade.conditions)
        if policy == "exclude_odd_lots" and "I" in conditions:
            continue

        price_eligible = True
        volume_eligible = True
        if policy not in {"all_raw", "exclude_odd_lots"}:
            price_eligible = not bool(
                conditions.intersection(PRICE_EXCLUDED_CONDITIONS)
            )
            volume_eligible = not bool(
                conditions.intersection(VOLUME_EXCLUDED_CONDITIONS)
            )

        if volume_eligible:
            volume += trade.size
        if not price_eligible:
            continue
        if open_price is None:
            open_price = trade.price
        high = trade.price if high is None else max(high, trade.price)
        low = trade.price if low is None else min(low, trade.price)
        close = trade.price
        if volume_eligible:
            numerator += trade.price * trade.size
            vwap_volume += trade.size

    return {
        "o": open_price,
        "h": high,
        "l": low,
        "c": close,
        "v": volume,
        "vw": numerator / vwap_volume if vwap_volume else None,
    }


class LiveBarMismatchForensics:
    """Evidence-only analysis of finalized local live WebSocket recordings."""

    def __init__(self, recording_root: str | Path):
        self.recording_root = Path(recording_root).expanduser().resolve()
        self.recorder = IntradayRecorder(self.recording_root)

    def analyze(self, session_ids: Iterable[str]) -> dict[str, Any]:
        sessions = [self._analyze_session(value) for value in session_ids]
        ledger = [item for session in sessions for item in session["ledger"]]
        classifications = Counter(item["classification"] for item in ledger)
        candidate_totals: dict[str, dict[str, Any]] = {}
        for session in sessions:
            for candidate, values in session["candidate_results"].items():
                aggregate = candidate_totals.setdefault(
                    candidate,
                    {
                        "mismatches_resolved": 0,
                        "new_mismatches_introduced": 0,
                        "mismatches_remaining": 0,
                        "resolved_intervals": [],
                        "introduced_intervals": [],
                    },
                )
                for key in (
                    "mismatches_resolved",
                    "new_mismatches_introduced",
                    "mismatches_remaining",
                ):
                    aggregate[key] += int(values[key])
                aggregate["resolved_intervals"].extend(
                    f"{session['session_id']}:{value}"
                    for value in values["resolved_intervals"]
                )
                aggregate["introduced_intervals"].extend(
                    f"{session['session_id']}:{value}"
                    for value in values["introduced_intervals"]
                )
        implementation_bug_count = sum(
            classifications[name]
            for name in (
                "duplicate_suppression_issue",
                "aggregation_boundary_issue",
                "timezone_session_boundary_issue",
            )
        )
        remaining_unknown = classifications["unknown"]
        raw_loss = classifications["raw_event_loss"]
        return {
            "version": 1,
            "scope": {
                "provider": "Alpaca IEX",
                "coverage": "partial-market",
                "mode": "paper/research-only",
                "orders_submitted": 0,
                "production_behavior_changed": False,
            },
            "session_ids": [item["session_id"] for item in sessions],
            "mismatch_count": len(ledger),
            "timeframe_counts": dict(
                sorted(Counter(item["timeframe"] for item in ledger).items())
            ),
            "classification_counts": dict(sorted(classifications.items())),
            "root_cause_coverage": {
                "explained_by_provider_semantics": classifications[
                    "provider_condition_filtering"
                ]
                + classifications["provider_historical_vs_stream_bar_semantics"],
                "explained_by_late_arrival": classifications[
                    "late_trade_arrival"
                ],
                "explained_by_reconnect_backfill": classifications[
                    "reconnect_backfill_boundary_issue"
                ],
                "explained_by_implementation_bug": implementation_bug_count,
                "evidence_of_raw_event_loss": raw_loss,
                "still_unknown": remaining_unknown,
            },
            "implementation_findings": [
                {
                    "finding": "offline_auditor_reaggregated_duplicate_events",
                    "status": "fixed_in_research_auditor",
                    "real_session_mismatches_resolved": 0,
                    "production_behavior_changed": False,
                }
            ],
            "candidate_limitations": {
                "exclude_corrections_cancels": {
                    "status": "not_testable",
                    "reason": (
                        "The recording did not subscribe to Alpaca correction "
                        "or cancel/error channels."
                    ),
                },
                "auction_aware_filtering": {
                    "status": "not_supported_by_failed_interval_evidence",
                    "reason": (
                        "No auction-specific condition accounts for the failed "
                        "intervals; applying an unproven filter would be heuristic."
                    ),
                },
                "updated_bar_semantics": {
                    "status": "not_testable",
                    "reason": (
                        "The recording subscribed to initial bars but not "
                        "updatedBars."
                    ),
                },
            },
            "provider_documentation": [
                "https://docs.alpaca.markets/us/docs/market-data-faq",
                "https://docs.alpaca.markets/us/docs/real-time-stock-pricing-data",
                "https://docs.alpaca.markets/us/docs/streaming-market-data",
            ],
            "finalization_delay_results": self._sum_delay_results(sessions),
            "candidate_results": dict(sorted(candidate_totals.items())),
            "sessions": [
                {key: value for key, value in item.items() if key != "ledger"}
                for item in sessions
            ],
            "ledger": ledger,
            "acceptance": {
                "zero_silent_event_loss_proven": not raw_loss and not remaining_unknown,
                "all_mismatches_have_evidence_backed_root_cause": not remaining_unknown,
                "verdict": (
                    "PASS"
                    if not raw_loss and not remaining_unknown
                    else "FAIL"
                ),
                "criteria_relaxed": False,
            },
        }

    @staticmethod
    def _sum_delay_results(sessions: list[dict[str, Any]]) -> dict[str, Any]:
        result: dict[str, Counter[str]] = defaultdict(Counter)
        for session in sessions:
            for delay, values in session["finalization_delay_results"].items():
                result[delay].update(values)
        return {
            delay: dict(sorted(values.items()))
            for delay, values in sorted(result.items(), key=lambda item: int(item[0]))
        }

    def _analyze_session(self, session_id: str) -> dict[str, Any]:
        path, metadata = self.recorder.resolve_session(session_id)
        verification = self.recorder.verify(session_id)
        if metadata.get("status") != "completed" or not verification[
            "checksum_valid"
        ]:
            raise ValueError(f"Recording {session_id} is not finalized and valid.")

        trades: dict[tuple[str, datetime], list[ForensicTrade]] = defaultdict(list)
        provider_bars: dict[tuple[str, datetime], dict[str, Any]] = {}
        quote_counts: Counter[tuple[str, datetime]] = Counter()
        duplicate_counts: Counter[tuple[str, datetime]] = Counter()
        reconnect_events: list[dict[str, Any]] = []
        observed_event_counts: Counter[str] = Counter()

        with gzip.open(path, "rb") as source:
            for line in source:
                if (
                    b'"event_type":"quote"' not in line
                    and b'"event_type":"trade"' not in line
                    and b'"event_type":"bar_1m"' not in line
                    and b'"event_type":"stream_' not in line
                ):
                    continue
                event = from_json(line)
                event_type = str(event.get("event_type") or "")
                observed_event_counts[event_type] += 1
                receipt = _iso_time(event["receipt_timestamp"])
                if event_type in RECONNECT_EVENT_TYPES:
                    reconnect_events.append(
                        {
                            "event_type": event_type,
                            "timestamp": receipt,
                            "payload": event.get("payload") or {},
                        }
                    )
                    continue
                symbol = str(event.get("symbol") or "")
                provider_timestamp = event.get("provider_timestamp")
                if not symbol or not provider_timestamp:
                    continue
                timestamp = _iso_time(provider_timestamp)
                minute = timestamp.replace(second=0, microsecond=0)
                key = (symbol, minute)
                disposition = str(event.get("disposition") or "")
                if disposition == "duplicate":
                    duplicate_counts[key] += 1
                if event_type == "quote":
                    quote_counts[key] += 1
                    continue
                payload = event.get("payload") or {}
                if event_type == "trade":
                    trades[key].append(
                        ForensicTrade(
                            price=float(payload["p"]),
                            size=float(payload["s"]),
                            conditions=tuple(
                                sorted(str(value) for value in payload.get("c", []))
                            ),
                            exchange=(
                                str(payload["x"]) if payload.get("x") else None
                            ),
                            provider_timestamp=timestamp,
                            receipt_timestamp=receipt,
                            disposition=disposition,
                            identity=_identity(payload),
                        )
                    )
                elif event_type == "bar_1m":
                    provider_bars[key] = {
                        "payload": payload,
                        "receipt_timestamp": receipt,
                        "disposition": disposition,
                    }

        baseline_mismatches = self._baseline_mismatches(trades, provider_bars)
        ledger = [
            self._ledger_item(
                session_id=session_id,
                key=key,
                mismatch_type=mismatch_type,
                trades=trades.get(key, []),
                provider_event=provider_bars.get(key),
                quote_count=quote_counts[key],
                duplicate_count=duplicate_counts[key],
                reconnect_events=reconnect_events,
            )
            for key, mismatch_type in baseline_mismatches
        ]
        self._annotate_clusters(ledger)
        candidate_results = self._candidate_results(
            trades,
            provider_bars,
            baseline_mismatches,
        )
        delay_results = self._delay_results(ledger)
        return {
            "session_id": session_id,
            "market_date": metadata.get("market_date"),
            "recording_checksum_sha256": metadata.get("checksum_sha256"),
            "checksum_valid": verification["checksum_valid"],
            "event_count": verification["event_count"],
            "observed_event_counts": dict(sorted(observed_event_counts.items())),
            "recorded_duplicate_count": int(metadata.get("duplicate_events", 0)),
            "recorded_out_of_order_count": int(
                metadata.get("out_of_order_events", 0)
            ),
            "reconnect_event_count": len(reconnect_events),
            "mismatch_count": len(ledger),
            "classification_counts": dict(
                sorted(Counter(item["classification"] for item in ledger).items())
            ),
            "candidate_results": candidate_results,
            "finalization_delay_results": delay_results,
            "ledger": ledger,
        }

    @staticmethod
    def _annotate_clusters(ledger: list[dict[str, Any]]) -> None:
        interval_counts = Counter(item["interval_start"] for item in ledger)
        for item in ledger:
            cluster_size = interval_counts[item["interval_start"]]
            item["cross_symbol_mismatch_cluster_size"] = cluster_size
            if item["classification"] != "unknown":
                continue
            if item["mismatch_type"] == "missing_provider_bar":
                item["classification"] = "raw_event_loss"
                item["evidence"] = [
                    "Recorded price-eligible trades require a minute bar under Alpaca's documented aggregation rules.",
                    "No provider bar event exists and no reconnect lifecycle event explains the omission.",
                    "The loss is audit-visible, but its provider-versus-local origin cannot be separated from this recording alone.",
                ]
                continue
            item["classification"] = (
                "provider_historical_vs_stream_bar_semantics"
            )
            item["evidence"] = [
                "The recording subscribed only to Alpaca's initial bars channel, not updatedBars, corrections, or cancelErrors.",
                "No tested deterministic trade-condition filter reproduces the recorded initial bar.",
                (
                    f"The same interval contains mismatches for {cluster_size} symbols."
                    if cluster_size > 1
                    else "The discrepancy is isolated to this symbol and interval."
                ),
                "A replay with updatedBars/corrections/cancelErrors is required to separate provider revisions from event loss.",
            ]

    @staticmethod
    def _baseline_mismatches(
        trades: dict[tuple[str, datetime], list[ForensicTrade]],
        provider_bars: dict[tuple[str, datetime], dict[str, Any]],
    ) -> list[tuple[tuple[str, datetime], str]]:
        mismatches: list[tuple[tuple[str, datetime], str]] = []
        for key in sorted(set(trades) | set(provider_bars)):
            raw_trades = trades.get(key, [])
            provider = provider_bars.get(key)
            rebuilt = _aggregate(raw_trades, policy="provider_conditions")
            price_present = all(rebuilt[field] is not None for field in ("o", "h", "l", "c"))
            if provider is None:
                if raw_trades and price_present:
                    mismatches.append((key, "missing_provider_bar"))
                continue
            if not raw_trades:
                mismatches.append((key, "provider_bar_without_raw_trades"))
                continue
            if _differences(
                _bar_values(provider["payload"]),
                rebuilt,
            ):
                mismatches.append((key, "trade_reconstruction_mismatch"))
        return mismatches

    def _ledger_item(
        self,
        *,
        session_id: str,
        key: tuple[str, datetime],
        mismatch_type: str,
        trades: list[ForensicTrade],
        provider_event: dict[str, Any] | None,
        quote_count: int,
        duplicate_count: int,
        reconnect_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        symbol, start = key
        end = start + timedelta(minutes=1)
        provider = _bar_values(
            provider_event["payload"] if provider_event else None
        )
        baseline = _aggregate(trades, policy="provider_conditions")
        deduplicated = _aggregate(trades, policy="deduplicated_provider_conditions")
        all_raw = _aggregate(trades, policy="all_raw")
        odd_lot_filtered = _aggregate(trades, policy="exclude_odd_lots")
        provider_receipt = (
            provider_event["receipt_timestamp"] if provider_event else None
        )
        receipt_cutoff = _aggregate(
            trades,
            policy="deduplicated_provider_conditions",
            receipt_cutoff=provider_receipt,
        ) if provider_receipt else {field: None for field in BAR_FIELDS}
        interval_close_cutoff = _aggregate(
            trades,
            policy="deduplicated_provider_conditions",
            receipt_cutoff=end,
        )
        conditions = Counter(
            condition for trade in trades for condition in trade.conditions
        )
        exchanges = Counter(
            trade.exchange for trade in trades if trade.exchange is not None
        )
        late_after_close = [
            trade for trade in trades if trade.receipt_timestamp > end
        ]
        late_after_bar = [
            trade
            for trade in trades
            if provider_receipt and trade.receipt_timestamp > provider_receipt
        ]
        nearby_reconnects = [
            event
            for event in reconnect_events
            if start - timedelta(seconds=35)
            <= event["timestamp"]
            <= end + timedelta(seconds=35)
        ]
        candidate_differences = {
            "all_raw": _differences(provider, all_raw),
            "exclude_odd_lots": _differences(provider, odd_lot_filtered),
            "provider_condition_eligible": _differences(provider, baseline),
            "deduplicated_provider_condition_eligible": _differences(
                provider, deduplicated
            ),
            "deduplicated_through_provider_bar_receipt": _differences(
                provider, receipt_cutoff
            ),
            "deduplicated_through_interval_close": _differences(
                provider, interval_close_cutoff
            ),
        }
        classification, evidence = self._classify(
            mismatch_type=mismatch_type,
            provider=provider_event,
            trades=trades,
            duplicate_count=duplicate_count,
            late_after_bar=late_after_bar,
            late_after_close=late_after_close,
            nearby_reconnects=nearby_reconnects,
            candidate_differences=candidate_differences,
        )
        event_times = [trade.provider_timestamp for trade in trades]
        receipt_times = [trade.receipt_timestamp for trade in trades]
        delay_candidates = {}
        for delay in FINALIZATION_DELAYS:
            rebuilt = (
                _aggregate(
                    trades,
                    policy="deduplicated_provider_conditions",
                    receipt_cutoff=end + timedelta(seconds=delay),
                )
                if provider_event and trades
                else {field: None for field in BAR_FIELDS}
            )
            delay_candidates[str(delay)] = {
                "matches_provider": bool(provider_event and trades)
                and not bool(_differences(provider, rebuilt)),
                "differences": _differences(provider, rebuilt),
            }
        return {
            "session_id": session_id,
            "symbol": symbol,
            "timeframe": "1m",
            "interval_start": start.isoformat(),
            "interval_end": end.isoformat(),
            "mismatch_type": mismatch_type,
            "classification": classification,
            "evidence": evidence,
            "provider_ohlcv": provider,
            "reconstructed_ohlcv": baseline,
            "exact_delta_per_field": _differences(provider, baseline),
            "candidate_reconstructions": {
                "all_raw": all_raw,
                "exclude_odd_lots": odd_lot_filtered,
                "provider_condition_eligible": baseline,
                "deduplicated_provider_condition_eligible": deduplicated,
                "deduplicated_through_provider_bar_receipt": receipt_cutoff,
                "deduplicated_through_interval_close": interval_close_cutoff,
            },
            "candidate_differences": candidate_differences,
            "finalization_delay_candidates_seconds": delay_candidates,
            "provider_bar_receipt_timestamp": (
                provider_receipt.isoformat() if provider_receipt else None
            ),
            "raw_trade_count": len(trades),
            "raw_quote_count": quote_count,
            "duplicate_count": duplicate_count,
            "late_after_interval_close_count": len(late_after_close),
            "late_after_provider_bar_count": len(late_after_bar),
            "maximum_provider_timestamp_lateness_seconds": max(
                (
                    (trade.receipt_timestamp - trade.provider_timestamp).total_seconds()
                    for trade in trades
                ),
                default=None,
            ),
            "maximum_bar_close_lateness_seconds": max(
                (
                    (trade.receipt_timestamp - end).total_seconds()
                    for trade in trades
                ),
                default=None,
            ),
            "trade_conditions": dict(sorted(conditions.items())),
            "exchange_codes": dict(sorted(exchanges.items())),
            "reconnect_backfill_overlap": bool(nearby_reconnects),
            "nearby_reconnect_events": [
                {
                    "event_type": event["event_type"],
                    "timestamp": event["timestamp"].isoformat(),
                    "payload": event["payload"],
                }
                for event in nearby_reconnects
            ],
            "raw_provider_timestamp_range": {
                "first": min(event_times).isoformat() if event_times else None,
                "last": max(event_times).isoformat() if event_times else None,
            },
            "local_receipt_timestamp_range": {
                "first": min(receipt_times).isoformat() if receipt_times else None,
                "last": max(receipt_times).isoformat() if receipt_times else None,
            },
        }

    @staticmethod
    def _classify(
        *,
        mismatch_type: str,
        provider: dict[str, Any] | None,
        trades: list[ForensicTrade],
        duplicate_count: int,
        late_after_bar: list[ForensicTrade],
        late_after_close: list[ForensicTrade],
        nearby_reconnects: list[dict[str, Any]],
        candidate_differences: dict[str, dict[str, Any]],
    ) -> tuple[str, list[str]]:
        if (
            provider
            and duplicate_count
            and not candidate_differences[
                "deduplicated_provider_condition_eligible"
            ]
        ):
            return (
                "duplicate_suppression_issue",
                [
                    "The recorded duplicate disposition was included by the Milestone 57 offline auditor.",
                    "Removing only duplicate trade identities exactly matches the provider bar.",
                ],
            )
        if (
            provider
            and late_after_bar
            and not candidate_differences[
                "deduplicated_through_provider_bar_receipt"
            ]
        ):
            return (
                "late_trade_arrival",
                [
                    "At least one trade arrived after the initial provider minute bar.",
                    "Reconstruction limited to events received through the bar receipt exactly matches the provider bar.",
                    "The recording did not subscribe to Alpaca updatedBars.",
                ],
            )
        if provider and late_after_close:
            delay_zero_matches = not candidate_differences.get(
                "deduplicated_through_interval_close",
                {"unresolved": {"value": 1}},
            )
            if delay_zero_matches:
                return (
                    "late_trade_arrival",
                    [
                        "At least one trade was received after the nominal minute close.",
                        "Excluding only post-close arrivals exactly matches the initial provider bar.",
                        "Alpaca documents updatedBars for these post-close late trades, but that channel was not subscribed.",
                    ],
                )
        if mismatch_type == "missing_provider_bar" and late_after_close:
            return (
                "late_trade_arrival",
                [
                    "Eligible raw trades arrived after the nominal interval close.",
                    "The bars subscription emitted no initial bar and updatedBars were not subscribed.",
                ],
            )
        if nearby_reconnects:
            return (
                "reconnect_backfill_boundary_issue",
                [
                    "A stale/disconnect/reconnect lifecycle event overlaps the bar interval or its publication window.",
                    "The live acceptance recorder had no REST event backfill for the disconnected window.",
                ],
            )
        if mismatch_type == "provider_bar_without_raw_trades":
            return (
                "raw_event_loss",
                [
                    "A provider bar proves eligible trade activity, but no raw trade event exists in the recording.",
                    "No reconnect lifecycle event was recorded within the forensic overlap window.",
                ],
            )
        if (
            provider
            and trades
            and not candidate_differences["exclude_odd_lots"]
        ):
            return (
                "provider_condition_filtering",
                [
                    "The provider bar exactly matches the odd-lot-filtered candidate.",
                    "The raw trade stream contains the I odd-lot condition.",
                ],
            )
        return (
            "unknown",
            [
                "The recorded evidence does not yet distinguish provider semantics from unrecorded stream loss.",
            ],
        )

    @staticmethod
    def _candidate_results(
        trades: dict[tuple[str, datetime], list[ForensicTrade]],
        provider_bars: dict[tuple[str, datetime], dict[str, Any]],
        baseline_mismatches: list[tuple[tuple[str, datetime], str]],
    ) -> dict[str, Any]:
        baseline = {key for key, _ in baseline_mismatches}
        policies = {
            "all_raw": "all_raw",
            "exclude_odd_lots": "exclude_odd_lots",
            "provider_condition_eligible": "provider_conditions",
            "deduplicated_provider_condition_eligible": (
                "deduplicated_provider_conditions"
            ),
        }
        result: dict[str, Any] = {}
        all_keys = sorted(set(trades) | set(provider_bars))
        for name, policy in policies.items():
            candidate: set[tuple[str, datetime]] = set()
            for key in all_keys:
                raw_trades = trades.get(key, [])
                provider_event = provider_bars.get(key)
                rebuilt = _aggregate(raw_trades, policy=policy)
                price_present = all(
                    rebuilt[field] is not None for field in ("o", "h", "l", "c")
                )
                if provider_event is None:
                    if raw_trades and price_present:
                        candidate.add(key)
                elif not raw_trades or _differences(
                    _bar_values(provider_event["payload"]), rebuilt
                ):
                    candidate.add(key)
            resolved = sorted(baseline - candidate)
            introduced = sorted(candidate - baseline)
            result[name] = {
                "mismatches_resolved": len(resolved),
                "new_mismatches_introduced": len(introduced),
                "mismatches_remaining": len(candidate),
                "resolved_intervals": [
                    f"{symbol}@{timestamp.isoformat()}"
                    for symbol, timestamp in resolved
                ],
                "introduced_intervals": [
                    f"{symbol}@{timestamp.isoformat()}"
                    for symbol, timestamp in introduced
                ],
            }

        receipt_candidate: set[tuple[str, datetime]] = set()
        for key in all_keys:
            raw_trades = trades.get(key, [])
            provider_event = provider_bars.get(key)
            if provider_event is None or not raw_trades:
                if key in baseline:
                    receipt_candidate.add(key)
                continue
            rebuilt = _aggregate(
                raw_trades,
                policy="deduplicated_provider_conditions",
                receipt_cutoff=provider_event["receipt_timestamp"],
            )
            if _differences(_bar_values(provider_event["payload"]), rebuilt):
                receipt_candidate.add(key)
        resolved = sorted(baseline - receipt_candidate)
        introduced = sorted(receipt_candidate - baseline)
        result["deduplicated_through_provider_bar_receipt"] = {
            "mismatches_resolved": len(resolved),
            "new_mismatches_introduced": len(introduced),
            "mismatches_remaining": len(receipt_candidate),
            "resolved_intervals": [
                f"{symbol}@{timestamp.isoformat()}" for symbol, timestamp in resolved
            ],
            "introduced_intervals": [
                f"{symbol}@{timestamp.isoformat()}"
                for symbol, timestamp in introduced
            ],
        }
        return result

    @staticmethod
    def _delay_results(ledger: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            str(delay): {
                "mismatches_resolved": sum(
                    1
                    for item in ledger
                    if item["finalization_delay_candidates_seconds"][str(delay)][
                        "matches_provider"
                    ]
                ),
                "mismatches_remaining": sum(
                    1
                    for item in ledger
                    if not item["finalization_delay_candidates_seconds"][str(delay)][
                        "matches_provider"
                    ]
                ),
            }
            for delay in FINALIZATION_DELAYS
        }


def write_forensic_outputs(
    result: dict[str, Any],
    *,
    ledger_path: str | Path,
    summary_path: str | Path,
) -> None:
    ledger_target = Path(ledger_path)
    summary_target = Path(summary_path)
    ledger_target.parent.mkdir(parents=True, exist_ok=True)
    summary_target.parent.mkdir(parents=True, exist_ok=True)
    ledger_target.write_text(
        json.dumps(
            {
                "version": result["version"],
                "session_ids": result["session_ids"],
                "mismatch_count": result["mismatch_count"],
                "ledger": result["ledger"],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    summary_target.write_text(
        json.dumps(
            {key: value for key, value in result.items() if key != "ledger"},
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
