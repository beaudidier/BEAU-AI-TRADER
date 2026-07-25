"""Versioned, provider-normalized US stock universes.

Runtime requests read only the committed local snapshot. Network access is
isolated in ``universe.update_constituents`` so a scan never scrapes a source
and a failed refresh cannot replace the last known-good constituent set.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .symbol_utils import VALID_PROVIDER_SYMBOL, normalize_stock_symbol
from .universe_provider import UniverseProvider

SNAPSHOT_FILE = Path(__file__).resolve().parent / "data" / "stock_universes.json"


def _load_snapshot(path: Path = SNAPSHOT_FILE) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "The cached stock-universe snapshot is missing or invalid. "
            "Run the constituent updater before starting the API."
        ) from error
    if payload.get("schema_version") != 1 or not isinstance(payload.get("universes"), dict):
        raise RuntimeError("The cached stock-universe snapshot schema is unsupported.")
    return payload


class StockUniverseProvider(UniverseProvider):
    market = "stocks"

    def __init__(self, snapshot_path: Path = SNAPSHOT_FILE) -> None:
        self.snapshot_path = snapshot_path
        self._snapshot = _load_snapshot(snapshot_path)
        self._scan_failures: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def supported_universes(self) -> set[str]:
        return {"demo", "sp500", "nasdaq100", "dow30", "custom", "all_us"}

    def snapshot(self, universe: str) -> dict[str, Any]:
        value = self._snapshot["universes"].get(universe)
        if not isinstance(value, dict):
            raise ValueError("Unsupported stock universe")
        return value

    def symbols(self, universe: str, custom_symbols: list[str] | None = None) -> list[str]:
        if universe == "custom":
            return _unique(custom_symbols or [])
        if universe not in self.supported_universes():
            return []
        return [str(item["symbol"]) for item in self.snapshot(universe)["constituents"]]

    def constituent_metadata(self, universe: str) -> dict[str, dict[str, Any]]:
        return {
            str(item["symbol"]): item.copy()
            for item in self.snapshot(universe)["constituents"]
        }

    def record_scan_result(
        self,
        universe: str,
        requested: list[str],
        failed: list[str],
        completed_at: str | None,
    ) -> None:
        if universe not in self._snapshot["universes"]:
            return
        normalized_failed = sorted(set(_unique(failed)))
        with self._lock:
            self._scan_failures[universe] = {
                "validated_at": completed_at or datetime.now(timezone.utc).isoformat(),
                "requested_count": len(set(requested)),
                "failed_symbols": normalized_failed,
            }

    def health(self, universe: str) -> dict[str, Any]:
        snapshot = self.snapshot(universe)
        constituents = [str(item["symbol"]) for item in snapshot["constituents"]]
        actual_count = len(constituents)
        expected_count = int(snapshot["expected_count"])
        duplicates = sorted(
            symbol for symbol in set(constituents) if constituents.count(symbol) > 1
        )
        invalid = sorted(
            symbol for symbol in constituents if not VALID_PROVIDER_SYMBOL.fullmatch(symbol)
        )
        source_failures = list(snapshot.get("unavailable_market_data") or [])
        with self._lock:
            latest_scan = self._scan_failures.get(universe)
        failed_symbols = (
            list(latest_scan["failed_symbols"]) if latest_scan is not None else source_failures
        )
        source_timestamp = str(snapshot["source"]["timestamp"])
        try:
            age_days = (
                datetime.now(timezone.utc)
                - datetime.fromisoformat(source_timestamp.replace("Z", "+00:00"))
            ).total_seconds() / 86400
        except ValueError:
            age_days = float("inf")
        freshness = "fresh" if age_days <= 45 else "stale"
        missing_count = max(0, expected_count - actual_count)
        unavailable = sorted(set(failed_symbols))
        if (
            actual_count != expected_count
            or duplicates
            or invalid
            or snapshot.get("missing_tickers")
        ):
            status = "unhealthy"
        elif freshness == "stale" or unavailable:
            status = "degraded"
        else:
            status = "healthy"
        return {
            "market": "stocks",
            "universe": universe,
            "name": snapshot["name"],
            "expected_count": expected_count,
            "actual_count": actual_count,
            "available_count": max(0, actual_count - len(unavailable)),
            "failed_count": len(unavailable),
            "failed_symbols": unavailable,
            "duplicates": duplicates,
            "invalid_tickers": invalid,
            "delisted_or_stale_tickers": list(
                snapshot.get("delisted_or_stale_tickers") or []
            ),
            "missing_tickers": list(snapshot.get("missing_tickers") or []),
            "missing_count": missing_count,
            "freshness": freshness,
            "source": snapshot["source"]["name"],
            "source_url": snapshot["source"]["url"],
            "last_constituent_update_timestamp": source_timestamp,
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "provider": self._snapshot["provider"],
            "provider_validation_timestamp": (
                latest_scan["validated_at"]
                if latest_scan is not None
                else snapshot.get("provider_validation_timestamp")
            ),
            "health_status": status,
        }

    def all_health(self) -> list[dict[str, Any]]:
        return [
            self.health(universe)
            for universe in ("demo", "dow30", "nasdaq100", "sp500", "all_us")
        ]


def _unique(symbols: list[str]) -> list[str]:
    result = []
    seen = set()
    for raw in symbols:
        normalized = normalize_stock_symbol(raw)
        if (
            normalized
            and VALID_PROVIDER_SYMBOL.fullmatch(normalized)
            and normalized not in seen
        ):
            result.append(normalized)
            seen.add(normalized)
    return result


_default_provider = StockUniverseProvider()
DOW30 = _default_provider.symbols("dow30")
NASDAQ100 = _default_provider.symbols("nasdaq100")
SP500 = _default_provider.symbols("sp500")
ALL_US = _default_provider.symbols("all_us")


def stock_constituent_metadata() -> dict[str, dict[str, Any]]:
    metadata: dict[str, dict[str, Any]] = {}
    for universe in ("all_us", "sp500", "nasdaq100", "dow30", "demo"):
        metadata.update(_default_provider.constituent_metadata(universe))
    return metadata
