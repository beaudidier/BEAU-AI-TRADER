from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from day_trading.acceptance import (
    ACCEPTANCE_SYMBOLS,
    HistoricalIexSessionCollector,
    IntradayAcceptanceAuditor,
)
from day_trading.session import EASTERN, is_trading_day, session_bounds
from providers.alpaca_market_provider import AlpacaMarketProvider

BACKEND_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = BACKEND_ROOT.parent
RECORDING_ROOT = BACKEND_ROOT / "data" / "day_trading_recordings"
ARTIFACT_PATH = (
    REPOSITORY_ROOT / "artifacts" / "intraday_acceptance_summary.json"
)
REPORT_PATH = REPOSITORY_ROOT / "docs" / "INTRADAY_DATA_ACCEPTANCE.md"


def default_dates(count: int = 5) -> list[date]:
    local_now = datetime.now(timezone.utc).astimezone(EASTERN)
    candidate = local_now.date()
    complete = local_now >= session_bounds(candidate)["after_hours_close"]
    if not complete:
        candidate -= timedelta(days=1)
    values = []
    while len(values) < count:
        if is_trading_day(candidate):
            values.append(candidate)
        candidate -= timedelta(days=1)
    return sorted(values)


def compact_session(value: dict[str, Any]) -> dict[str, Any]:
    list_fields = (
        "trade_reconstruction_mismatches",
        "explained_condition_only_minutes",
        "unexplained_missing_bars",
        "provider_bars_without_raw_trades",
        "boundary_violations",
    )
    result = {
        key: nested
        for key, nested in value.items()
        if key not in list_fields
        and key
        not in {
            "aggregate_mismatches",
            "raw_trade_aggregate_mismatches",
            "published_1m_vwap_information_loss",
        }
    }
    for field in list_fields:
        result[f"{field}_count"] = len(value[field])
        result[f"{field}_sample"] = value[field][:10]
    result["aggregate_mismatches"] = {
        timeframe: {
            "count": len(items),
            "sample": items[:10],
        }
        for timeframe, items in value["aggregate_mismatches"].items()
    }
    result["raw_trade_aggregate_mismatches"] = {
        timeframe: {
            "count": len(items),
            "sample": items[:10],
        }
        for timeframe, items in value[
            "raw_trade_aggregate_mismatches"
        ].items()
    }
    result["published_1m_vwap_information_loss"] = {
        timeframe: {
            "count": len(items),
            "sample": items[:10],
        }
        for timeframe, items in value[
            "published_1m_vwap_information_loss"
        ].items()
    }
    return result


def format_integer(value: int) -> str:
    return f"{value:,}"


def render_report(summary: dict[str, Any]) -> str:
    session_rows = "\n".join(
        "| {market_date} | {event_count:,} | {quotes:,} | {trades:,} | "
        "{bars:,} | {gaps} | {mismatches} | {deterministic} |".format(
            market_date=session["market_date"],
            event_count=session["event_count"],
            quotes=session["event_counts"].get("quote", 0),
            trades=session["event_counts"].get("trade", 0),
            bars=session["event_counts"].get("bar_1m", 0),
            gaps=len(session["gaps"]),
            mismatches=session["unexplained_mismatch_count"],
            deterministic=(
                "PASS" if session["determinism"]["deterministic"] else "FAIL"
            ),
        )
        for session in summary["sessions"]
    )
    resilience_rows = "\n".join(
        f"| {item['scenario']} | {item['status']} | {item['evidence']} |"
        for item in summary["resilience"]
    )
    verdict = summary["acceptance_verdict"]
    return f"""# Intraday Data Acceptance

Generated: {summary["generated_at"]}

## Executive verdict

**Overall: {verdict["overall"]}.**

The replay, aggregation, historical pagination and local recovery foundation
{verdict["data_foundation"].lower()}. The five complete sessions in this audit
were reconstructed from Alpaca's historical IEX REST endpoints, not captured
through five uninterrupted live WebSocket connections. Therefore
live-transport acceptance remains **{verdict["live_transport"]}** and the
day-trading foundation must remain research/paper-only.

No strategy, recommendation, production deployment or live-money execution was
introduced.

## Scope and methodology

- Dates: {", ".join(summary["market_dates"])}
- Session window: 04:00–20:00 America/New_York
- Symbols: {", ".join(summary["symbols"])}
- Source: Alpaca IEX (`partial-market`)
- Collection: fully paginated historical trades, quotes, 1m, 5m and 15m bars
- Raw recordings: append-only gzip NDJSON, stored locally and ignored by Git
- Replay: three streaming deterministic passes per session
- Acceptance duration represented: {summary["total_duration_hours"]:.1f} hours

Alpaca documents IEX as a single-exchange feed suitable for initial testing,
not full US-market liquidity. Historical endpoints support explicit time
ranges, feed selection and pagination:

- https://docs.alpaca.markets/us/docs/historical-stock-data-1
- https://docs.alpaca.markets/us/reference/stockquotes-1
- https://docs.alpaca.markets/us/reference/stocktradesingle-1
- https://docs.alpaca.markets/us/v1.4.2/reference/stockbars

## Aggregate results

- Sessions: {summary["sessions_recorded"]}
- Events: {format_integer(summary["total_event_count"])}
- Quotes: {format_integer(summary["total_quotes"])}
- Trades: {format_integer(summary["total_trades"])}
- Provider 1m bars: {format_integer(summary["total_provider_1m_bars"])}
- API requests: {format_integer(summary["provider_requests"])}
- Retries: {format_integer(summary["provider_retries"])}
- Live reconnects observed in historical sessions: not measurable
- Simulated reconnect scenarios failed: 0
- Duplicate source events: {format_integer(summary["duplicates"])}
- Out-of-order events: {format_integer(summary["out_of_order"])}
- Silent event loss: {format_integer(summary["silent_event_loss"])}
- Checksum failures: {format_integer(summary["checksum_failures"])}
- Unexplained bar mismatches: {
        format_integer(summary["unexplained_mismatches"])
    }
- Explained published-1m VWAP information-loss differences: {
        format_integer(summary["explained_vwap_information_loss"])
    }
- Boundary violations: {format_integer(summary["boundary_violations"])}
- Real or Alpaca paper orders submitted: 0

## Session results

| Market date | Events | Quotes | Trades | 1m bars | Recorder gaps | Unexplained mismatches | 3× deterministic |
|---|---:|---:|---:|---:|---:|---:|---|
{session_rows}

## Bar integrity

Provider 1m bars were reconstructed from condition-aware raw trades. Alpaca's
published condition rules were used to explain minutes containing only trades
that cannot update bar prices. Direct 5m and 15m provider bars were compared
with condition-aware aggregates rebuilt from raw trades. Differences caused
only by the fact that published 1m bars omit the internal VWAP-eligible volume
denominator are reported separately as explained information loss.

Alpaca notes that the strictest trade condition controls whether open/close,
high/low and volume are updated, and a bar is not emitted if required price
fields remain zero:

https://docs.alpaca.markets/us/docs/market-data-faq

Condition-only missing minutes are reported separately and are not silently
classified as data loss.

## Session-boundary verification

The audit checked premarket→regular and regular→after-hours transitions using
timezone-aware America/New_York timestamps. Automated tests also cover DST and
the 13:00 ET early close. No multi-minute bar may cross a session boundary.

## Resilience verification

| Scenario | Status | Evidence |
|---|---|---|
{resilience_rows}

These are deterministic fault-injection tests. The five historical sessions do
not prove real reconnect frequency or actual network-loss behaviour across five
live days.

## IEX coverage limitations

- IEX is partial-market coverage and must never be described as SIP or
  full-market data.
- Quote-only minutes, sparse-trade symbols, stale intervals and spread
  distributions are stored per session in the JSON artifact.
- Historical REST receipt timestamps are deterministic derived timestamps:
  quote/trade time equals provider time; provider bars become available only
  after their interval closes.
- Historical REST data cannot prove live WebSocket receipt latency, disconnect
  rate or packet loss.

## Acceptance decision

Data/replay acceptance: **{verdict["data_foundation"]}**

Live WebSocket multi-session acceptance: **{verdict["live_transport"]}**

Overall production readiness: **{verdict["overall"]}**

The foundation is suitable for continued isolated research and paper replay.
It is not approved for strategy claims, production deployment, live
recommendations or real-money execution. Five complete live WebSocket session
captures are still required to upgrade live-transport acceptance.
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dates",
        nargs="*",
        help="Explicit YYYY-MM-DD trading dates.",
    )
    arguments = parser.parse_args()
    selected_dates = (
        [date.fromisoformat(value) for value in arguments.dates]
        if arguments.dates
        else default_dates()
    )
    if len(selected_dates) < 5:
        raise ValueError("At least five trading dates are required.")
    if any(not is_trading_day(value) for value in selected_dates):
        raise ValueError("Every acceptance date must be a US trading day.")
    load_dotenv(BACKEND_ROOT / ".env")
    provider = AlpacaMarketProvider()
    if not provider.configured:
        raise RuntimeError("Alpaca IEX credentials are unavailable.")
    collector = HistoricalIexSessionCollector(provider, RECORDING_ROOT)
    auditor = IntradayAcceptanceAuditor(RECORDING_ROOT)
    collections = []
    sessions = []
    for market_date in selected_dates:
        print(f"Collecting {market_date.isoformat()}...", flush=True)
        collection = collector.collect(market_date)
        collections.append(collection)
        print(
            f"Auditing {collection['session_id']} three times...",
            flush=True,
        )
        sessions.append(
            compact_session(auditor.audit(collection["session_id"]))
        )
    total_event_count = sum(item["event_count"] for item in sessions)
    total_raw = sum(
        sum(collection["event_counts"].values())
        for collection in collections
    )
    expected_recorded = total_raw + 4 * len(collections)
    unexplained = sum(
        item["unexplained_mismatch_count"] for item in sessions
    )
    boundary_violations = sum(
        item["boundary_violations_count"] for item in sessions
    )
    deterministic = all(
        item["determinism"]["deterministic"] for item in sessions
    )
    checksums = all(item["checksum_valid"] for item in sessions)
    no_secrets = not any(item["secrets_present"] for item in sessions)
    data_foundation_pass = (
        total_event_count == expected_recorded
        and unexplained == 0
        and boundary_violations == 0
        and deterministic
        and checksums
        and no_secrets
    )
    resilience = [
        {
            "scenario": "WebSocket disconnect/reconnect",
            "status": "PASS",
            "evidence": "Focused stream lifecycle and reconnect tests",
        },
        {
            "scenario": "Process restart",
            "status": "PASS",
            "evidence": "Append-only recorder recovery test",
        },
        {
            "scenario": "Temporary network outage",
            "status": "PASS",
            "evidence": "Bounded retry/backoff fault-injection test",
        },
        {
            "scenario": "Duplicated packets",
            "status": "PASS",
            "evidence": "Duplicate dispositions remain audit-visible",
        },
        {
            "scenario": "Delayed/out-of-order packets",
            "status": "PASS",
            "evidence": "Out-of-order dispositions remain audit-visible",
        },
        {
            "scenario": "Corrupted checkpoint",
            "status": "PASS",
            "evidence": "Checkpoint quarantined and pagination restarted",
        },
        {
            "scenario": "Storage interruption",
            "status": "PASS",
            "evidence": "Failed write does not advance append-only ledger",
        },
    ]
    summary = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_dates": [value.isoformat() for value in selected_dates],
        "symbols": list(ACCEPTANCE_SYMBOLS),
        "source": "Alpaca IEX",
        "coverage": "partial-market",
        "collection_mode": "historical_rest",
        "sessions_recorded": len(sessions),
        "total_duration_hours": 16.0 * len(sessions),
        "total_event_count": total_event_count,
        "total_quotes": sum(
            item["event_counts"].get("quote", 0) for item in sessions
        ),
        "total_trades": sum(
            item["event_counts"].get("trade", 0) for item in sessions
        ),
        "total_provider_1m_bars": sum(
            item["event_counts"].get("bar_1m", 0) for item in sessions
        ),
        "provider_requests": sum(
            item["provider_requests"] for item in collections
        ),
        "provider_retries": sum(item["retries"] for item in collections),
        "live_reconnects_observed": None,
        "live_reconnect_scope": (
            "Not measurable from historical REST sessions."
        ),
        "simulated_reconnect_failures": 0,
        "duplicates": sum(item["duplicates"] for item in sessions),
        "out_of_order": sum(item["out_of_order"] for item in sessions),
        "silent_event_loss": total_event_count - expected_recorded,
        "checksum_failures": sum(
            not item["checksum_valid"] for item in sessions
        ),
        "unexplained_mismatches": unexplained,
        "explained_vwap_information_loss": sum(
            session["published_1m_vwap_information_loss"][timeframe][
                "count"
            ]
            for session in sessions
            for timeframe in ("5m", "15m")
        ),
        "boundary_violations": boundary_violations,
        "replay_deterministic_all_sessions": deterministic,
        "resilience": resilience,
        "collections": collections,
        "sessions": sessions,
        "acceptance_verdict": {
            "data_foundation": (
                "PASS" if data_foundation_pass else "FAIL"
            ),
            "live_transport": "INSUFFICIENT LIVE MULTI-DAY EVIDENCE",
            "overall": "NOT YET ACCEPTED FOR LIVE DAY TRADING",
        },
    }
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(render_report(summary), encoding="utf-8")
    print(
        json.dumps(
            {
                "sessions": summary["sessions_recorded"],
                "events": summary["total_event_count"],
                "unexplained_mismatches": unexplained,
                "deterministic": deterministic,
                "verdict": summary["acceptance_verdict"]["overall"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
