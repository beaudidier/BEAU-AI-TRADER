"""Audit cached universe integrity and optional Yahoo market-data availability."""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from .stock_universe import SNAPSHOT_FILE, StockUniverseProvider

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "artifacts" / "universe_integrity_results.json"
DEFAULT_REPORT = ROOT / "docs" / "UNIVERSE_INTEGRITY_AUDIT.md"
DEFAULT_VALIDATION_CACHE = ROOT / "artifacts" / "universe_market_availability_cache.json"
PREVIOUS_COUNTS = {
    "demo": 10,
    "dow30": 30,
    "nasdaq100": 30,
    "sp500": 51,
    "all_us": 71,
}
LEGACY_TRUNCATED = {
    "demo": "MU NVDA AMD TSLA AAPL MSFT META AMZN GOOGL PLTR".split(),
    "dow30": "AAPL AMGN AMZN AXP BA CAT CRM CSCO CVX DIS GS HD HON IBM INTC JNJ JPM KO MCD MMM MRK MSFT NKE NVDA PG SHW TRV UNH V WMT".split(),
    "nasdaq100": "NVDA MSFT AAPL AMZN META AVGO GOOGL GOOG TSLA COST NFLX AMD ADBE PEP CSCO TMUS INTC CMCSA INTU QCOM AMGN TXN HON AMAT BKNG SBUX VRTX PANW ADP GILD".split(),
    "sp500": "AAPL MSFT NVDA AMZN META GOOGL GOOG BRK-B AVGO TSLA LLY JPM V UNH XOM MA COST PG JNJ HD MRK ABBV CVX KO PEP ADBE CRM WMT BAC NFLX AMD CSCO TMO ACN MCD LIN ABT DHR ORCL QCOM TXN PM IBM AMGN GE CAT INTU NOW ISRG GS SPGI".split(),
}
LEGACY_TRUNCATED["all_us"] = list(
    dict.fromkeys(
        [
            *LEGACY_TRUNCATED["sp500"],
            *LEGACY_TRUNCATED["nasdaq100"],
            *LEGACY_TRUNCATED["dow30"],
            *LEGACY_TRUNCATED["demo"],
        ]
    )
)


def _chunks(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def _batch_availability(symbols: list[str]) -> set[str]:
    if not symbols:
        return set()
    data = yf.download(
        tickers=symbols,
        period="5d",
        interval="1d",
        progress=False,
        auto_adjust=True,
        group_by="ticker",
        threads=8,
    )
    available = set()
    if data is None or data.empty:
        return available
    if len(symbols) == 1 and not isinstance(data.columns, pd.MultiIndex):
        close = pd.to_numeric(data.get("Close"), errors="coerce").dropna()
        return {symbols[0]} if not close.empty else set()
    if not isinstance(data.columns, pd.MultiIndex):
        return available
    level = set(str(value) for value in data.columns.get_level_values(0))
    for symbol in symbols:
        if symbol not in level:
            continue
        try:
            close = pd.to_numeric(data[symbol]["Close"], errors="coerce").dropna()
        except (KeyError, TypeError, ValueError):
            continue
        if not close.empty:
            available.add(symbol)
    return available


def validate_market_data(
    symbols: list[str],
    *,
    batch_size: int = 100,
    retry_batch_size: int = 20,
    cache_path: Path = DEFAULT_VALIDATION_CACHE,
) -> dict[str, Any]:
    """Validate all symbols, then retry every failed symbol in smaller batches."""

    requested = sorted(set(symbols))
    universe_hash = hashlib.sha256("\n".join(requested).encode()).hexdigest()
    available: set[str] = set()
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if cached.get("universe_sha256") == universe_hash:
            available.update(set(cached.get("available_symbols") or []) & set(requested))
    except (OSError, json.JSONDecodeError):
        pass
    batch_errors: list[str] = []
    remaining = sorted(set(requested) - available)
    for batch in _chunks(remaining, batch_size):
        try:
            available.update(_batch_availability(batch))
        except Exception as error:
            batch_errors.append(f"{batch[0]}..{batch[-1]}: {type(error).__name__}")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {
                    "universe_sha256": universe_hash,
                    "available_symbols": sorted(available),
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        time.sleep(0.2)
    missing = sorted(set(requested) - available)
    for batch in _chunks(missing, retry_batch_size):
        try:
            available.update(_batch_availability(batch))
        except Exception as error:
            batch_errors.append(f"retry {batch[0]}..{batch[-1]}: {type(error).__name__}")
    failed = sorted(set(requested) - available)
    return {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "requested_count": len(requested),
        "available_count": len(available),
        "failed_count": len(failed),
        "failed_symbols": failed,
        "batch_errors": batch_errors,
        "method": "Yahoo Finance adjusted 5-day daily history; missing symbols retried in smaller batches",
    }


def store_provider_validation(
    validation: dict[str, Any], snapshot_path: Path = SNAPSHOT_FILE
) -> None:
    payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    failed = set(validation["failed_symbols"])
    for universe in payload["universes"].values():
        symbols = {str(item["symbol"]) for item in universe["constituents"]}
        universe["unavailable_market_data"] = sorted(symbols & failed)
        universe["provider_validation_timestamp"] = validation["validated_at"]
    temporary = snapshot_path.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(snapshot_path)


def build_integrity_result(
    provider: StockUniverseProvider,
    validation: dict[str, Any],
) -> dict[str, Any]:
    universes = {}
    for universe_id in ("demo", "dow30", "nasdaq100", "sp500", "all_us"):
        health = provider.health(universe_id)
        current_symbols = set(provider.symbols(universe_id))
        legacy_symbols = set(LEGACY_TRUNCATED[universe_id])
        universes[universe_id] = {
            **health,
            "previous_actual_count": PREVIOUS_COUNTS[universe_id],
            "corrected_count_change": health["actual_count"]
            - PREVIOUS_COUNTS[universe_id],
            "previous_missing_count": len(current_symbols - legacy_symbols),
            "previous_missing_tickers": sorted(current_symbols - legacy_symbols),
            "previous_stale_tickers": sorted(legacy_symbols - current_symbols),
            "symbols_with_unavailable_market_data": health["failed_symbols"],
        }
    return {
        "audit_version": "universe-integrity-v1.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "provider_validation": validation,
        "universes": universes,
        "runtime_behavior": (
            "API requests read the committed snapshot only. The updater is an explicit "
            "maintenance command and preserves the previous file on any failure."
        ),
    }


def render_report(result: dict[str, Any]) -> str:
    lines = [
        "# Universe Integrity and Completeness Audit",
        "",
        "## Executive result",
        "",
        "| Universe | Previous | Expected | Actual | Duplicates | Invalid | Stale/delisted | Missing | Market-data failures | Health |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for universe in result["universes"].values():
        lines.append(
            "| "
            + " | ".join(
                [
                    universe["name"],
                    str(universe["previous_actual_count"]),
                    str(universe["expected_count"]),
                    str(universe["actual_count"]),
                    str(len(universe["duplicates"])),
                    str(len(universe["invalid_tickers"])),
                    str(len(universe["delisted_or_stale_tickers"])),
                    str(len(universe["missing_tickers"])),
                    str(universe["failed_count"]),
                    universe["health_status"],
                ]
            )
            + " |"
        )
    validation = result["provider_validation"]
    lines.extend(
        [
            "",
            "## Provider availability",
            "",
            f"- Provider: **Yahoo Finance**",
            f"- Validated: **{validation['validated_at']}**",
            f"- Symbols checked: **{validation['requested_count']}**",
            f"- Symbols available: **{validation['available_count']}**",
            f"- Symbols unavailable after retry: **{validation['failed_count']}**",
            f"- Method: {validation['method']}",
            "",
            "Unavailable symbols:",
            "",
            (
                "- " + ", ".join(f"`{symbol}`" for symbol in validation["failed_symbols"])
                if validation["failed_symbols"]
                else "- None."
            ),
            "",
            "## Constituent sources",
            "",
            "| Universe | Source | Source timestamp | Snapshot hash |",
            "|---|---|---|---|",
        ]
    )
    for universe in result["universes"].values():
        lines.append(
            f"| {universe['name']} | {universe['source']} | "
            f"{universe['last_constituent_update_timestamp']} | "
            f"`{universe['snapshot_sha256']}` |"
        )
    lines.extend(
        [
            "",
            "## Per-universe exceptions",
            "",
        ]
    )
    for universe in result["universes"].values():
        lines.extend(
            [
                f"### {universe['name']}",
                "",
                f"- Duplicates: {', '.join(universe['duplicates']) or 'None'}",
                f"- Invalid tickers: {', '.join(universe['invalid_tickers']) or 'None'}",
                f"- Delisted or stale tickers: {', '.join(universe['delisted_or_stale_tickers']) or 'None'}",
                f"- Missing tickers: {', '.join(universe['missing_tickers']) or 'None'}",
                f"- Unavailable market data: {', '.join(universe['failed_symbols']) or 'None'}",
                f"- Missing from the previous truncated snapshot: **{universe['previous_missing_count']}**",
                "- Previous missing examples: "
                + (
                    ", ".join(
                        f"`{symbol}`"
                        for symbol in universe["previous_missing_tickers"][:25]
                    )
                    + (
                        " …"
                        if len(universe["previous_missing_tickers"]) > 25
                        else ""
                    )
                    if universe["previous_missing_tickers"]
                    else "None"
                ),
                f"- Previous symbols no longer current: {', '.join(universe['previous_stale_tickers']) or 'None'}",
                "",
            ]
        )
    lines.extend(
        [
            "## Update mechanism",
            "",
            "- Runtime scans use only `backend/universe/data/stock_universes.json`.",
            "- `python -m universe.update_constituents` performs an explicit refresh.",
            "- Index tables are validated against count ranges and the current Nasdaq Trader US listing directory.",
            "- Symbols are normalized for Yahoo Finance before deduplication (`BRK.B` becomes `BRK-B`).",
            "- A temporary file is atomically promoted only after every source validates.",
            "- A failed refresh leaves the committed snapshot unchanged as the deterministic fallback.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-provider-validation", action="store_true")
    parser.add_argument("--reuse-provider-validation", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    provider = StockUniverseProvider()
    all_us = provider.symbols("all_us")
    if args.reuse_provider_validation:
        try:
            validation = json.loads(args.output.read_text(encoding="utf-8"))[
                "provider_validation"
            ]
        except (OSError, KeyError, json.JSONDecodeError) as error:
            raise RuntimeError(
                "No previous provider validation artifact is available to reuse."
            ) from error
    elif args.skip_provider_validation:
        validation = {
            "validated_at": datetime.now(timezone.utc).isoformat(),
            "requested_count": len(all_us),
            "available_count": len(all_us),
            "failed_count": 0,
            "failed_symbols": [],
            "batch_errors": [],
            "method": "Provider validation skipped",
        }
    else:
        validation = validate_market_data(all_us)
        store_provider_validation(validation)
        provider = StockUniverseProvider()
    result = build_integrity_result(provider, validation)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    args.report.write_text(render_report(result), encoding="utf-8")
    print(
        json.dumps(
            {
                "counts": {
                    key: value["actual_count"]
                    for key, value in result["universes"].items()
                },
                "provider_failures": validation["failed_count"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
