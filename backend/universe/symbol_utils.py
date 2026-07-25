"""Shared stock-symbol normalization for snapshots and market-data providers."""

from __future__ import annotations

import re

VALID_PROVIDER_SYMBOL = re.compile(r"^[A-Z][A-Z0-9-]{0,9}$")


def normalize_stock_symbol(symbol: str) -> str:
    """Normalize an exchange symbol for the Yahoo Finance provider."""

    normalized = str(symbol or "").strip().upper().replace("/", "-").replace(".", "-")
    return re.sub(r"\s+", "", normalized)
