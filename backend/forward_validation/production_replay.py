"""Isolated historical replay of the production forward-validation signal path.

This module deliberately has no write access to forward-validation or paper
trading tables. It runs the registered frozen strategy against a completed
historical session and stores results only in local audit artifacts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from atr import add_atr
from backtesting.execution import entry_fill_price
from engines.engine_utils import has_valid_market_data, safe_float
from engines.institutional_engine import calculate_institutional_analysis
from providers import get_market_data_provider
from providers.provider import MarketDataProvider
from strategies import strategy_registry
from strategies.swing_strategy import (
    MAX_RISK_PCT,
    SLIPPAGE_BPS,
    STOP_ATR,
    STRATEGY_VERSION,
    TARGET_1_R,
    TARGET_2_R,
)

from .runner import (
    MARKET_CLOSE_BUFFER,
    MARKET_TIMEZONE,
    RUNNER_VERSION,
    completed_daily_history,
    configured_universe,
    signal_expiry_date,
)

REPLAY_VERSION = "production-path-replay-v1.0.0"
SIGNAL_COMPARISON_FIELDS = (
    "ticker",
    "signal_timestamp",
    "signal_price",
    "proposed_pullback_entry",
    "expected_entry_fill",
    "stop_loss",
    "target_1",
    "target_2",
    "market_regime",
    "market_regime_score",
    "confidence",
    "strategy_version",
    "data_timestamp",
)
LIVE_TABLES = (
    "forward_validation_runs",
    "forward_validation_signals",
    "forward_validation_outcomes",
    "paper_trades",
)


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _through_session(history: pd.DataFrame | None, session: date) -> pd.DataFrame | None:
    if history is None or history.empty:
        return history
    result = history.copy()
    result.index = pd.to_datetime(result.index).tz_localize(None)
    return result.loc[result.index.date <= session]


def _signal_timestamp(session: date) -> str:
    return datetime.combine(session, MARKET_CLOSE_BUFFER, MARKET_TIMEZONE).astimezone(timezone.utc).isoformat()


def _standalone_calculation(
    ticker: str,
    history: pd.DataFrame,
    benchmark: pd.DataFrame,
    signal_timestamp: str,
) -> dict[str, Any]:
    diagnostics: dict[str, Any] = {
        "history_rows": len(history),
        "benchmark_rows": len(benchmark),
        "raw_data_timestamp": pd.Timestamp(history.index[-1]).isoformat() if not history.empty else None,
    }
    if not has_valid_market_data(history, minimum_rows=200):
        return {
            "decision": "rejected",
            "reasons": ["Fewer than 200 valid completed daily OHLCV candles were available."],
            "diagnostics": diagnostics,
            "signal": None,
        }
    if not has_valid_market_data(benchmark, minimum_rows=200):
        return {
            "decision": "rejected",
            "reasons": ["Fewer than 200 valid completed SPY benchmark candles were available."],
            "diagnostics": diagnostics,
            "signal": None,
        }

    enriched = add_atr(history.copy())
    atr = safe_float(enriched["ATR"].iloc[-1])
    diagnostics["atr"] = round(_number(atr), 6) if atr is not None else None
    if atr is None or atr <= 0:
        return {
            "decision": "rejected",
            "reasons": ["ATR was missing, invalid, or non-positive."],
            "diagnostics": diagnostics,
            "signal": None,
        }

    analysis = calculate_institutional_analysis(history, benchmark)
    market = analysis["engines"]["market_regime"]
    regime_score = _number(market.get("score"))
    regime_explanation = str(market.get("explanation") or "Risk-on")
    confidence = _number(analysis.get("overall_score"))
    close = pd.to_numeric(history["Close"], errors="coerce")
    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    expected_fill = entry_fill_price(ema20, SLIPPAGE_BPS)
    swing_low = float(pd.to_numeric(history["Low"], errors="coerce").tail(20).min())
    stop = swing_low - STOP_ATR * atr
    risk = expected_fill - stop
    risk_percent = risk / expected_fill if expected_fill > 0 else math.inf
    diagnostics.update(
        {
            "market_regime": regime_explanation,
            "market_regime_score": round(regime_score, 2),
            "confidence": round(confidence, 2),
            "ema20": round(ema20, 6),
            "swing_low_20": round(swing_low, 6),
            "expected_entry_fill": round(expected_fill, 6),
            "stop_loss": round(stop, 6),
            "risk_per_share": round(risk, 6),
            "risk_percent": round(risk_percent * 100, 6) if math.isfinite(risk_percent) else None,
            "candidate_target_1": round(expected_fill + TARGET_1_R * risk, 6) if risk > 0 else None,
            "candidate_target_2": round(expected_fill + TARGET_2_R * risk, 6) if risk > 0 else None,
        }
    )

    rejection_reasons = []
    if regime_score < 65:
        rejection_reasons.append(
            f"Market-regime score {regime_score:.2f} was below the frozen minimum of 65."
        )
    if stop <= 0:
        rejection_reasons.append(f"Calculated stop {stop:.6f} was not positive.")
    if risk <= 0:
        rejection_reasons.append(f"Risk per share {risk:.6f} was not positive.")
    if risk_percent > MAX_RISK_PCT:
        rejection_reasons.append(
            f"Per-share risk {risk_percent * 100:.2f}% exceeded the frozen 5% maximum."
        )
    if rejection_reasons:
        return {
            "decision": "rejected",
            "reasons": rejection_reasons,
            "diagnostics": diagnostics,
            "signal": None,
        }

    signal = {
        "ticker": ticker.upper(),
        "signal_timestamp": signal_timestamp,
        "signal_price": round(float(close.iloc[-1]), 6),
        "proposed_pullback_entry": round(ema20, 6),
        "expected_entry_fill": round(expected_fill, 6),
        "stop_loss": round(stop, 6),
        "target_1": round(expected_fill + TARGET_1_R * risk, 6),
        "target_2": round(expected_fill + TARGET_2_R * risk, 6),
        "market_regime": regime_explanation,
        "market_regime_score": round(regime_score, 2),
        "confidence": round(confidence, 2),
        "strategy_version": STRATEGY_VERSION,
        "data_timestamp": pd.Timestamp(history.index[-1]).isoformat(),
    }
    return {
        "decision": "signal",
        "reasons": [
            f"Market-regime score {regime_score:.2f} met the frozen minimum of 65.",
            f"ATR {atr:.6f} and the 20-session swing low produced a valid stop.",
            f"Per-share risk {risk_percent * 100:.2f}% stayed within the frozen 5% maximum.",
        ],
        "diagnostics": diagnostics,
        "signal": signal,
    }


def _compare_production_and_standalone(
    production_signal: dict[str, Any] | None,
    standalone: dict[str, Any],
) -> list[str]:
    standalone_signal = standalone.get("signal")
    if production_signal is None and standalone_signal is None:
        return []
    if production_signal is None:
        return ["Production rejected the setup while the standalone calculation produced a signal."]
    if standalone_signal is None:
        return ["Production produced a signal while the standalone calculation rejected the setup."]
    return [
        field
        for field in SIGNAL_COMPARISON_FIELDS
        if production_signal.get(field) != standalone_signal.get(field)
    ]


def run_production_path_replay(
    *,
    provider: MarketDataProvider | None = None,
    symbols: list[str] | None = None,
    now: datetime | None = None,
    replay_date: date | None = None,
) -> dict[str, Any]:
    """Run production signal selection without constructing any writable store."""

    market_provider = provider or get_market_data_provider()
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    requested = [
        symbol.strip().upper()
        for symbol in (symbols if symbols is not None else configured_universe())
        if symbol and symbol.strip()
    ]
    benchmark_full = completed_daily_history(market_provider, "SPY", moment)
    if benchmark_full is None or benchmark_full.empty:
        raise RuntimeError("A completed SPY benchmark history is required for replay.")
    session = replay_date or pd.Timestamp(benchmark_full.index[-1]).date()
    benchmark = _through_session(benchmark_full, session)
    if benchmark is None or benchmark.empty or pd.Timestamp(benchmark.index[-1]).date() != session:
        raise RuntimeError(f"SPY does not contain the requested completed replay session {session.isoformat()}.")

    strategy = strategy_registry.require_usable("swing_trading")
    generated_signal_timestamp = _signal_timestamp(session)
    results: list[dict[str, Any]] = []
    provider_errors: dict[str, str] = {}
    completed: list[str] = []
    failed: list[str] = []
    seen: set[str] = set()
    duplicate_requests = 0

    for ticker in requested:
        if ticker in seen:
            duplicate_requests += 1
            results.append(
                {
                    "ticker": ticker,
                    "status": "duplicate",
                    "reasons": ["Duplicate ticker request was ignored before market data was fetched."],
                    "mismatches": [],
                }
            )
            continue
        seen.add(ticker)
        try:
            history_full = completed_daily_history(market_provider, ticker, moment)
            history = _through_session(history_full, session)
            if history is None or history.empty:
                raise ValueError("No completed daily OHLCV history was returned.")
            raw_timestamp = pd.Timestamp(history.index[-1])
            if raw_timestamp.date() != session:
                raise ValueError(
                    f"Latest completed candle {raw_timestamp.date().isoformat()} did not match replay session {session.isoformat()}."
                )
            production_signal = strategy.scan(
                ticker=ticker,
                history=history,
                benchmark=benchmark,
                signal_timestamp=generated_signal_timestamp,
            )
            standalone = _standalone_calculation(
                ticker,
                history,
                benchmark,
                generated_signal_timestamp,
            )
            mismatches = _compare_production_and_standalone(production_signal, standalone)
            completed.append(ticker)
            results.append(
                {
                    "ticker": ticker,
                    "status": "signal" if production_signal is not None else "rejected",
                    "replay_date": session.isoformat(),
                    "raw_data_timestamp": raw_timestamp.isoformat(),
                    "expiry_date": signal_expiry_date(session).isoformat() if production_signal else None,
                    "production_signal": production_signal,
                    "standalone_signal": standalone.get("signal"),
                    "diagnostics": standalone["diagnostics"],
                    "reasons": standalone["reasons"],
                    "mismatches": mismatches,
                }
            )
        except Exception as error:
            reason = str(error) or type(error).__name__
            provider_errors[ticker] = reason
            failed.append(ticker)
            results.append(
                {
                    "ticker": ticker,
                    "status": "provider_error",
                    "reasons": [reason],
                    "mismatches": [],
                }
            )

    signal_count = sum(item["status"] == "signal" for item in results)
    rejected_count = sum(item["status"] == "rejected" for item in results)
    mismatches = [
        {"ticker": item["ticker"], "fields": item["mismatches"]}
        for item in results
        if item.get("mismatches")
    ]
    return {
        "replay_version": REPLAY_VERSION,
        "runner_version": RUNNER_VERSION,
        "strategy_version": STRATEGY_VERSION,
        "generated_at": moment.isoformat(),
        "replay_date": session.isoformat(),
        "signal_timestamp": generated_signal_timestamp,
        "benchmark_data_timestamp": pd.Timestamp(benchmark.index[-1]).isoformat(),
        "summary": {
            "symbols_requested": requested,
            "requested_count": len(requested),
            "symbols_completed": completed,
            "completed_count": len(completed),
            "symbols_failed": failed,
            "failed_count": len(failed),
            "signals_found": signal_count,
            "rejected_setups": rejected_count,
            "duplicate_requests_prevented": duplicate_requests,
            "provider_errors": provider_errors,
            "mismatch_count": len(mismatches),
        },
        "results": results,
        "mismatches": mismatches,
    }


def capture_live_table_fingerprints(client: Any) -> dict[str, dict[str, Any]]:
    """Read and hash live tables without returning or persisting their contents."""

    fingerprints = {}
    for table_name in LIVE_TABLES:
        rows = client.table(table_name).select("*").execute().data or []
        canonical_rows = sorted(
            json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
            for row in rows
        )
        canonical = json.dumps(canonical_rows, separators=(",", ":"))
        fingerprints[table_name] = {
            "row_count": len(rows),
            "sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        }
    return fingerprints


def attach_live_table_proof(
    result: dict[str, Any],
    before: dict[str, dict[str, Any]] | None,
    after: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    if before is None or after is None:
        result["live_table_proof"] = {
            "checked": False,
            "unchanged": None,
            "tables": {},
        }
        return result
    table_checks = {
        table_name: {
            "before": before[table_name],
            "after": after[table_name],
            "unchanged": before[table_name] == after[table_name],
        }
        for table_name in LIVE_TABLES
    }
    result["live_table_proof"] = {
        "checked": True,
        "unchanged": all(item["unchanged"] for item in table_checks.values()),
        "tables": table_checks,
    }
    return result


def render_report(result: dict[str, Any]) -> str:
    summary = result["summary"]
    proof = result.get("live_table_proof") or {}
    lines = [
        "# Production-Path Historical Replay",
        "",
        "## Executive result",
        "",
        f"- Replay date: **{result['replay_date']}**",
        f"- Frozen strategy: **{result['strategy_version']}**",
        f"- Production runner: **{result['runner_version']}**",
        f"- Symbols requested: **{summary['requested_count']}**",
        f"- Symbols completed: **{summary['completed_count']}**",
        f"- Symbols failed: **{summary['failed_count']}**",
        f"- Signals found: **{summary['signals_found']}**",
        f"- Rejected setups: **{summary['rejected_setups']}**",
        f"- Duplicate requests prevented: **{summary['duplicate_requests_prevented']}**",
        f"- Production/standalone mismatches: **{summary['mismatch_count']}**",
        f"- Live production tables unchanged: **{'YES' if proof.get('unchanged') else 'NO' if proof.get('checked') else 'NOT CHECKED'}**",
        "",
        "This replay used real completed daily OHLCV data and the registered production `swing_trading` strategy. "
        "Every ticker history and SPY benchmark was cut off at the replay session before the signal calculation, so no later candle was available to either calculation.",
        "",
        "## Universe accounting",
        "",
        f"- Requested: {', '.join(summary['symbols_requested']) or 'None'}",
        f"- Completed: {', '.join(summary['symbols_completed']) or 'None'}",
        f"- Failed: {', '.join(summary['symbols_failed']) or 'None'}",
        "",
        "## Per-symbol audit",
        "",
        "| Ticker | Result | Raw timestamp | Regime | Confidence | EMA20 entry | Swing low | Stop | TP1 | TP2 | Expiry | Comparison |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|",
    ]
    for item in result["results"]:
        diagnostics = item.get("diagnostics") or {}
        signal = item.get("production_signal") or {}
        comparison = "MATCH" if not item.get("mismatches") else ", ".join(item["mismatches"])
        values = [
            item["ticker"],
            item["status"],
            item.get("raw_data_timestamp") or "—",
            str(diagnostics.get("market_regime_score", "—")),
            str(diagnostics.get("confidence", "—")),
            str(signal.get("proposed_pullback_entry", diagnostics.get("ema20", "—"))),
            str(diagnostics.get("swing_low_20", "—")),
            str(signal.get("stop_loss", diagnostics.get("stop_loss", "—"))),
            str(signal.get("target_1", diagnostics.get("candidate_target_1", "—"))),
            str(signal.get("target_2", diagnostics.get("candidate_target_2", "—"))),
            item.get("expiry_date") or "—",
            comparison,
        ]
        lines.append("| " + " | ".join(values) + " |")
    lines.extend(["", "## Explanations", ""])
    for item in result["results"]:
        lines.append(f"### {item['ticker']} — {item['status']}")
        lines.append("")
        for reason in item.get("reasons") or ["No explanation recorded."]:
            lines.append(f"- {reason}")
        lines.append("")

    lines.extend(["## Provider failures", ""])
    if summary["provider_errors"]:
        for ticker, reason in summary["provider_errors"].items():
            lines.append(f"- {ticker}: {reason}")
    else:
        lines.append("- None.")

    lines.extend(["", "## Production versus standalone comparison", ""])
    if result["mismatches"]:
        for mismatch in result["mismatches"]:
            lines.append(f"- {mismatch['ticker']}: {', '.join(mismatch['fields'])}")
    else:
        lines.append(
            f"- All {summary['completed_count']} completed ticker calculations matched their direct standalone calculations."
        )
    lines.extend(
        [
            "",
            "The comparison covers the decision plus signal timestamp, signal price, EMA20 pullback entry, expected fill, stop, TP1, TP2, market regime, confidence, strategy version, and raw data timestamp.",
            "For rejected setups, candidate TP1 and TP2 levels are shown for arithmetic audit only. The production strategy correctly does not emit them as executable chart levels after a rejection rule fires.",
            "",
            "## Live-table immutability proof",
            "",
        ]
    )
    if proof.get("checked"):
        lines.append("| Table | Rows before | Rows after | Hash unchanged |")
        lines.append("|---|---:|---:|---|")
        for table_name, item in proof["tables"].items():
            lines.append(
                f"| {table_name} | {item['before']['row_count']} | {item['after']['row_count']} | {'YES' if item['unchanged'] else 'NO'} |"
            )
    else:
        lines.append("- Live-table fingerprints were not supplied for this replay.")
    lines.extend(
        [
            "",
            "Replay output was written only to the audit artifact and this report. The replay module exposes no insert, update, upsert, delete, paper-trade, or signal-store operation.",
            "",
            "## Limitations",
            "",
            "- This verifies deterministic signal generation on one completed market session, not future profitability.",
            "- Candidate TP1 and TP2 values for rejected setups are diagnostic only; no production signal or executable chart level was created.",
            "- Yahoo Finance remains a development data source and can return temporary provider errors.",
            "",
        ]
    )
    return "\n".join(lines)


def _supabase_client_from_environment() -> Any | None:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    from supabase import create_client

    return create_client(url, key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default="artifacts/production_path_replay.json")
    parser.add_argument("--report", default="docs/PRODUCTION_PATH_REPLAY.md")
    args = parser.parse_args()

    client = _supabase_client_from_environment()
    before = capture_live_table_fingerprints(client) if client is not None else None
    result = run_production_path_replay()
    after = capture_live_table_fingerprints(client) if client is not None else None
    attach_live_table_proof(result, before, after)

    output_path = Path(args.output)
    report_path = Path(args.report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    report_path.write_text(render_report(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "replay_date": result["replay_date"],
                "symbols_completed": result["summary"]["completed_count"],
                "signals_found": result["summary"]["signals_found"],
                "rejected_setups": result["summary"]["rejected_setups"],
                "provider_failures": result["summary"]["failed_count"],
                "mismatches": result["summary"]["mismatch_count"],
                "live_tables_unchanged": result["live_table_proof"]["unchanged"],
            },
            indent=2,
        )
    )
    return 0 if result["summary"]["mismatch_count"] == 0 and result["live_table_proof"].get("unchanged") is not False else 1


if __name__ == "__main__":
    raise SystemExit(main())
