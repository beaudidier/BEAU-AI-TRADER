"""Refresh the committed stock-universe snapshot from public sources.

The updater is intentionally separate from API requests. It writes a new
snapshot only after every source passes count, syntax, duplicate, and listing
cross-checks. If any download or validation fails, the existing local snapshot
remains the deterministic fallback.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import ssl
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import certifi

from config import WATCHLIST

from .symbol_utils import VALID_PROVIDER_SYMBOL, normalize_stock_symbol

SNAPSHOT_FILE = Path(__file__).resolve().parent / "data" / "stock_universes.json"
SOURCES = {
    "sp500": {
        "name": "Wikipedia — List of S&P 500 companies",
        "url": "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies",
        "file": "sp500.html",
        "page": "List of S&P 500 companies",
        "table_id": "constituents",
    },
    "nasdaq100": {
        "name": "Wikipedia — List of Nasdaq-100 companies",
        "url": "https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies",
        "file": "nasdaq100.html",
        "page": "List of NASDAQ-100 companies",
        "table_id": "constituents",
    },
    "dow30": {
        "name": "Wikipedia — Dow Jones Industrial Average constituents",
        "url": "https://en.wikipedia.org/wiki/Dow_Jones_Industrial_Average",
        "file": "dow30.html",
        "page": "Dow Jones Industrial Average",
        "table_id": "constituents",
    },
}
NASDAQ_LISTED = {
    "name": "Nasdaq Trader Symbol Directory",
    "url": "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "file": "nasdaqlisted.txt",
}
OTHER_LISTED = {
    "name": "Nasdaq Trader Other-Exchange Symbol Directory",
    "url": "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
    "file": "otherlisted.txt",
}
EXCLUDED_SECURITY_PATTERNS = (
    r"\bwarrants?\b",
    r"\brights?\b",
    r"\bunits?\b",
    r"\bpreferred\b",
    r"\bpreference\b",
    r"\bpfd\b",
    r"\bnotes?\s+due\b",
    r"\bbonds?\b",
    r"\bdebentures?\b",
    r"\bexchange traded notes?\b",
    r"\betn\b",
    r"\bfunds?\b",
)


class _TableParser(HTMLParser):
    def __init__(self, table_id: str) -> None:
        super().__init__(convert_charrefs=True)
        self.table_id = table_id
        self.table_depth = 0
        self.in_target = False
        self.in_cell = False
        self.cell_parts: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table":
            if self.in_target:
                self.table_depth += 1
            elif attributes.get("id") == self.table_id:
                self.in_target = True
                self.table_depth = 1
        elif self.in_target and tag in {"th", "td"}:
            self.in_cell = True
            self.cell_parts = []
        elif self.in_target and tag == "tr":
            self.row = []

    def handle_endtag(self, tag: str) -> None:
        if not self.in_target:
            return
        if tag in {"th", "td"} and self.in_cell:
            text = re.sub(r"\s+", " ", " ".join(self.cell_parts)).strip()
            self.row.append(text)
            self.in_cell = False
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
            self.row = []
        elif tag == "table":
            self.table_depth -= 1
            if self.table_depth == 0:
                self.in_target = False

    def handle_data(self, data: str) -> None:
        if self.in_target and self.in_cell:
            self.cell_parts.append(data)


def parse_table(html: str, table_id: str) -> list[dict[str, str]]:
    parser = _TableParser(table_id)
    parser.feed(html)
    if len(parser.rows) < 2:
        raise ValueError(f"Constituent table '{table_id}' was not found or was empty.")
    headers = parser.rows[0]
    return [
        {headers[index]: row[index] if index < len(row) else "" for index in range(len(headers))}
        for row in parser.rows[1:]
    ]


def _download(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "BEAU-AI-TRADER/1.0 universe integrity updater"},
    )
    context = ssl.create_default_context(cafile=certifi.where())
    with urllib.request.urlopen(request, timeout=45, context=context) as response:
        return response.read().decode("utf-8-sig")


def _revision_timestamp(page: str) -> str:
    query = urllib.parse.urlencode(
        {
            "action": "query",
            "prop": "revisions",
            "rvprop": "timestamp",
            "titles": page,
            "format": "json",
        }
    )
    payload = json.loads(_download(f"https://en.wikipedia.org/w/api.php?{query}"))
    pages = payload["query"]["pages"]
    return next(iter(pages.values()))["revisions"][0]["timestamp"]


def _directory_timestamp(text: str) -> str:
    match = re.search(r"File Creation Time:\s*(\d{8})(\d{2}):(\d{2})", text)
    if not match:
        raise ValueError("Nasdaq directory creation timestamp is missing.")
    value = datetime.strptime("".join(match.groups()), "%m%d%Y%H%M")
    return value.replace(tzinfo=ZoneInfo("America/New_York")).isoformat()


def _is_supported_stock(symbol: str, name: str, etf: str, test_issue: str) -> bool:
    if etf != "N" or test_issue != "N":
        return False
    # Nasdaq Trader's provider-form hyphen symbols are preferred/debt series.
    # Common-stock class shares use a source dot (for example BRK.B) and are
    # normalized to a Yahoo hyphen only after this instrument-type filter.
    if "-" in symbol:
        return False
    lower_name = name.lower()
    if (
        "depositary shares" in lower_name
        and "american depositary shares" not in lower_name
        and "american depository shares" not in lower_name
    ):
        return False
    if any(re.search(pattern, lower_name) for pattern in EXCLUDED_SECURITY_PATTERNS):
        return False
    normalized = normalize_stock_symbol(symbol)
    return bool(VALID_PROVIDER_SYMBOL.fullmatch(normalized))


def parse_us_listings(nasdaq_text: str, other_text: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rejected: list[str] = []
    for text, exchange_source in (
        (nasdaq_text, "NASDAQ"),
        (other_text, "OTHER"),
    ):
        reader = csv.DictReader(
            (
                line
                for line in io.StringIO(text)
                if not line.startswith("File Creation Time:")
            ),
            delimiter="|",
        )
        for row in reader:
            raw_symbol = (
                row.get("Symbol") or row.get("NASDAQ Symbol") or row.get("ACT Symbol") or ""
            ).strip()
            name = (row.get("Security Name") or "").strip()
            if not _is_supported_stock(
                raw_symbol,
                name,
                (row.get("ETF") or "").strip(),
                (row.get("Test Issue") or "").strip(),
            ):
                if raw_symbol:
                    rejected.append(raw_symbol)
                continue
            rows.append(
                {
                    "symbol": normalize_stock_symbol(raw_symbol),
                    "source_symbol": raw_symbol.upper(),
                    "name": name,
                    "sector": None,
                    "exchange": (
                        "NASDAQ"
                        if exchange_source == "NASDAQ"
                        else (row.get("Exchange") or "OTHER").strip()
                    ),
                }
            )
    unique: dict[str, dict[str, Any]] = {}
    duplicates = []
    for row in sorted(rows, key=lambda item: (item["symbol"], item["source_symbol"])):
        if row["symbol"] in unique:
            duplicates.append(row["source_symbol"])
            continue
        unique[row["symbol"]] = row
    return list(unique.values()), {
        "duplicates": sorted(set(duplicates)),
        "invalid_or_unsupported_source_rows": sorted(set(rejected)),
    }


def _index_constituents(
    universe: str,
    rows: list[dict[str, str]],
    all_us_symbols: set[str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fields = {
        "sp500": ("Symbol", "Security", "GICS Sector"),
        "nasdaq100": ("Ticker", "Company", "ICB Industry [ 1 ]"),
        "dow30": ("Symbol", "Company", "Sector"),
    }
    symbol_field, name_field, sector_field = fields[universe]
    constituents = []
    invalid = []
    duplicates = []
    seen = set()
    for row in rows:
        raw_symbol = row.get(symbol_field, "").strip().upper()
        symbol = normalize_stock_symbol(raw_symbol)
        if not VALID_PROVIDER_SYMBOL.fullmatch(symbol):
            invalid.append(raw_symbol)
            continue
        if symbol in seen:
            duplicates.append(raw_symbol)
            continue
        seen.add(symbol)
        constituents.append(
            {
                "symbol": symbol,
                "source_symbol": raw_symbol,
                "name": row.get(name_field, "").strip(),
                "sector": row.get(sector_field, "").strip() or None,
            }
        )
    constituents.sort(key=lambda item: item["symbol"])
    stale = sorted(item["symbol"] for item in constituents if item["symbol"] not in all_us_symbols)
    return constituents, {
        "duplicates": sorted(set(duplicates)),
        "invalid": sorted(set(invalid)),
        "stale": stale,
    }


def _sha256(constituents: list[dict[str, Any]]) -> str:
    canonical = json.dumps(constituents, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def _source_text(source: dict[str, str], source_dir: Path | None) -> str:
    if source_dir is not None:
        return (source_dir / source["file"]).read_text(encoding="utf-8-sig")
    return _download(source["url"])


def build_snapshot(source_dir: Path | None = None) -> dict[str, Any]:
    nasdaq_text = _source_text(NASDAQ_LISTED, source_dir)
    other_text = _source_text(OTHER_LISTED, source_dir)
    all_us, all_us_diagnostics = parse_us_listings(nasdaq_text, other_text)
    all_us_symbols = {item["symbol"] for item in all_us}
    directory_timestamps = [
        _directory_timestamp(nasdaq_text),
        _directory_timestamp(other_text),
    ]
    directory_timestamp = max(directory_timestamps)
    generated_at = datetime.now(timezone.utc).isoformat()

    universe_payloads: dict[str, dict[str, Any]] = {}
    demo = [
        {
            "symbol": normalize_stock_symbol(symbol),
            "source_symbol": symbol.upper(),
            "name": symbol.upper(),
            "sector": None,
        }
        for symbol in WATCHLIST
    ]
    universe_payloads["demo"] = {
        "name": "Demo 10",
        "expected_count": 10,
        "constituents": demo,
        "duplicates": [],
        "invalid_tickers": [],
        "delisted_or_stale_tickers": sorted(
            item["symbol"] for item in demo if item["symbol"] not in all_us_symbols
        ),
        "missing_tickers": [],
        "unavailable_market_data": [],
        "provider_validation_timestamp": None,
        "source": {
            "name": "BEAU AI Trader configured demo list",
            "url": "backend/config.py",
            "timestamp": generated_at,
        },
        "snapshot_sha256": _sha256(demo),
    }

    for universe_id, source in SOURCES.items():
        html = _source_text(source, source_dir)
        rows = parse_table(html, source["table_id"])
        constituents, diagnostics = _index_constituents(
            universe_id, rows, all_us_symbols
        )
        if universe_id == "dow30" and len(constituents) != 30:
            raise ValueError(f"Dow source returned {len(constituents)} symbols, expected 30.")
        if universe_id == "nasdaq100" and not 100 <= len(constituents) <= 105:
            raise ValueError(
                f"Nasdaq-100 source returned {len(constituents)} securities, expected 100-105."
            )
        if universe_id == "sp500" and not 500 <= len(constituents) <= 510:
            raise ValueError(
                f"S&P 500 source returned {len(constituents)} securities, expected 500-510."
            )
        timestamp = (
            datetime.now(timezone.utc).isoformat()
            if source_dir is not None
            else _revision_timestamp(source["page"])
        )
        universe_payloads[universe_id] = {
            "name": {
                "dow30": "Dow 30",
                "nasdaq100": "Nasdaq 100",
                "sp500": "S&P 500",
            }[universe_id],
            "expected_count": len(constituents),
            "constituents": constituents,
            "duplicates": diagnostics["duplicates"],
            "invalid_tickers": diagnostics["invalid"],
            "delisted_or_stale_tickers": diagnostics["stale"],
            "missing_tickers": [],
            "unavailable_market_data": [],
            "provider_validation_timestamp": None,
            "source": {
                "name": source["name"],
                "url": source["url"],
                "timestamp": timestamp,
            },
            "snapshot_sha256": _sha256(constituents),
        }

    universe_payloads["all_us"] = {
        "name": "All US Stocks",
        "expected_count": len(all_us),
        "constituents": all_us,
        "duplicates": all_us_diagnostics["duplicates"],
        "invalid_tickers": [],
        "delisted_or_stale_tickers": [],
        "missing_tickers": [],
        "unavailable_market_data": [],
        "provider_validation_timestamp": None,
        "source": {
            "name": "Nasdaq Trader daily Nasdaq and other-exchange symbol directories",
            "url": f"{NASDAQ_LISTED['url']} + {OTHER_LISTED['url']}",
            "timestamp": directory_timestamp,
        },
        "snapshot_sha256": _sha256(all_us),
        "excluded_source_row_count": len(
            all_us_diagnostics["invalid_or_unsupported_source_rows"]
        ),
    }
    return {
        "schema_version": 1,
        "provider": "Yahoo Finance",
        "generated_at": generated_at,
        "universes": universe_payloads,
    }


def write_snapshot(payload: dict[str, Any], output: Path = SNAPSHOT_FILE) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    temporary.replace(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=SNAPSHOT_FILE)
    parser.add_argument("--source-dir", type=Path)
    args = parser.parse_args()
    payload = build_snapshot(args.source_dir)
    write_snapshot(payload, args.output)
    print(
        json.dumps(
            {
                key: value["expected_count"]
                for key, value in payload["universes"].items()
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
