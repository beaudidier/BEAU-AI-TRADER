"""Presentation-only clarity for immutable forward-validation setups."""

from __future__ import annotations

import json
import math
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

SETUP_STATUSES = (
    "waiting_for_entry",
    "entry_triggered",
    "expired",
    "invalidated",
    "completed",
)

OUTCOME_STATUS_MAP = {
    "waiting_for_entry": "waiting_for_entry",
    "entered": "entry_triggered",
    "TP1_hit": "entry_triggered",
    "expired": "expired",
    "invalidated": "invalidated",
    "data_error": "invalidated",
    "TP2_hit": "completed",
    "stopped": "completed",
    "completed": "completed",
}

RELATED_SECTOR_THEMES = {
    "Rate-sensitive assets": frozenset({"Utilities", "Real Estate"}),
    "Growth equities": frozenset(
        {"Information Technology", "Communication Services", "Consumer Discretionary"}
    ),
    "Defensive equities": frozenset(
        {"Consumer Staples", "Health Care", "Utilities"}
    ),
    "Cyclical equities": frozenset(
        {"Consumer Discretionary", "Energy", "Industrials", "Materials"}
    ),
}

UNIVERSE_PATH = (
    Path(__file__).resolve().parents[1]
    / "universe"
    / "data"
    / "stock_universes.json"
)


def _positive_number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def setup_status_from_outcome(status: Any) -> str:
    """Map detailed execution outcomes to one beginner-facing setup status."""

    return OUTCOME_STATUS_MAP.get(str(status), "invalidated")


def distance_to_entry_percent(current_price: Any, planned_entry: Any) -> float | None:
    """Return signed distance: positive above entry and negative below entry."""

    current = _positive_number(current_price)
    entry = _positive_number(planned_entry)
    if current is None or entry is None:
        return None
    return round((current - entry) / entry * 100, 4)


def distance_to_entry_label(distance: float | None) -> str:
    if distance is None:
        return "Unavailable"
    if abs(distance) < 0.005:
        return "At the planned entry"
    direction = "above" if distance > 0 else "below"
    return f"{abs(distance):.2f}% {direction} planned entry"


@lru_cache(maxsize=1)
def sector_by_ticker() -> dict[str, str]:
    payload = json.loads(UNIVERSE_PATH.read_text(encoding="utf-8"))
    constituents = payload["universes"]["sp500"]["constituents"]
    return {
        str(item["symbol"]): str(item.get("sector") or "Unclassified")
        for item in constituents
    }


def setup_clarity(
    signal: dict[str, Any],
    outcome: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Add status and guidance without changing any immutable plan value."""

    execution = outcome or {}
    status = setup_status_from_outcome(
        execution.get("setup_status") or execution.get("status") or "waiting_for_entry"
    )
    planned_entry = _positive_number(signal.get("proposed_pullback_entry"))
    current_price = (
        _positive_number(execution.get("current_price"))
        or _positive_number(signal.get("current_price"))
        or _positive_number(signal.get("signal_price"))
    )
    distance = distance_to_entry_percent(current_price, planned_entry)
    expiry = signal.get("expiry_date")
    stop = _positive_number(signal.get("stop_loss"))

    if status == "waiting_for_entry":
        instruction = "Do not buy at market"
        invalidation = (
            f"The setup expires after {expiry} if price never trades through the "
            "fixed pullback entry."
            if expiry
            else "The setup expires after the frozen three-session entry window if the pullback entry is never reached."
        )
        actionable_at_market = False
    elif status == "entry_triggered":
        instruction = "Entry triggered—monitor the original plan"
        invalidation = (
            f"The entered setup is invalidated if price reaches the original stop at ${stop:.4f}."
            if stop
            else "The entered setup is invalidated if price reaches its original stop."
        )
        actionable_at_market = False
    elif status == "expired":
        instruction = "Expired—do not enter"
        invalidation = "The frozen entry window ended without a valid pullback fill."
        actionable_at_market = False
    elif status == "invalidated":
        instruction = "Invalidated—do not enter"
        invalidation = str(
            execution.get("invalidation_reason")
            or "The setup cannot be acted on because valid market data or frozen setup conditions are no longer available."
        )
        actionable_at_market = False
    else:
        instruction = "Completed—no new entry"
        invalidation = "This setup has finished and is retained only as validation evidence."
        actionable_at_market = False

    return {
        "status": status,
        "instruction": instruction,
        "actionable_at_market": actionable_at_market,
        "current_price": current_price,
        "current_price_timestamp": (
            execution.get("current_price_timestamp")
            or signal.get("current_price_timestamp")
            or signal.get("data_timestamp")
        ),
        "planned_entry": planned_entry,
        "distance_to_entry_percent": distance,
        "distance_to_entry_label": distance_to_entry_label(distance),
        "expiry_date": expiry,
        "invalidation": invalidation,
        "beginner_explanation": {
            "why_setup_exists": (
                "The frozen strategy found a risk-on market and a valid long setup, "
                "then placed a pullback level near the signal-time EMA20."
            ),
            "why_waiting_matters": (
                "Waiting keeps the original stop distance, position risk, and reward "
                "targets intact. A market order would be a different trade."
            ),
            "if_price_never_reaches_entry": (
                "No trade is opened. The setup expires after three completed trading "
                "sessions and its original levels are not recalculated."
            ),
            "why_buying_early_changes_risk_reward": (
                "Buying above the planned entry increases the money at risk to the "
                "fixed stop and reduces the reward available to the fixed targets."
            ),
        },
    }


def sector_concentration(signals: list[dict[str, Any]]) -> dict[str, Any]:
    """Measure active-signal concentration using deterministic sector themes."""

    active = [
        signal
        for signal in signals
        if (
            signal.get("setup", {}).get("status")
            or signal.get("setup_status")
            or "waiting_for_entry"
        )
        in {"waiting_for_entry", "entry_triggered"}
    ]
    counts = Counter(
        str(signal.get("sector") or "Unclassified") for signal in active
    )
    total = len(active)
    sectors = [
        {
            "sector": sector,
            "count": count,
            "percentage": round(count / total * 100, 2) if total else 0.0,
        }
        for sector, count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]
    dominant = [item for item in sectors if item["percentage"] > 30]

    theme_candidates: list[dict[str, Any]] = []
    for theme, related_sectors in RELATED_SECTOR_THEMES.items():
        represented = [
            item for item in sectors if item["sector"] in related_sectors
        ]
        top_two = represented[:2]
        count = sum(int(item["count"]) for item in top_two)
        percentage = round(count / total * 100, 2) if total else 0.0
        if len(top_two) == 2 and percentage > 50:
            theme_candidates.append(
                {
                    "theme": theme,
                    "sectors": [item["sector"] for item in top_two],
                    "count": count,
                    "percentage": percentage,
                }
            )
    related_theme = max(
        theme_candidates,
        key=lambda item: (item["percentage"], item["theme"]),
        default=None,
    )
    warnings: list[str] = []
    if dominant:
        leader = dominant[0]
        warnings.append(
            f"Correlation risk: {leader['sector']} represents "
            f"{leader['percentage']:.1f}% of active signals, above the 30% limit."
        )
    if related_theme:
        warnings.append(
            f"Market-theme risk: {', '.join(related_theme['sectors'])} represent "
            f"{related_theme['percentage']:.1f}% of active signals within the "
            f"{related_theme['theme'].lower()} theme."
        )
    return {
        "active_signal_count": total,
        "sectors": sectors,
        "dominant_sector_warning": bool(dominant),
        "related_sector_warning": related_theme is not None,
        "related_theme": related_theme,
        "warnings": warnings,
        "has_warning": bool(warnings),
        "thresholds": {
            "single_sector_percent": 30,
            "two_related_sectors_percent": 50,
        },
    }


def enrich_dashboard(dashboard: dict[str, Any]) -> dict[str, Any]:
    """Attach presentation fields to a forward-validation dashboard."""

    metadata = sector_by_ticker()
    signal_groups = (
        "active_signals",
        "expired_signals",
        "open_paper_trades",
        "completed_trades",
    )
    for group in signal_groups:
        enriched: list[dict[str, Any]] = []
        for original in dashboard.get(group) or []:
            signal = dict(original)
            outcome = dict(signal.get("outcome") or {})
            signal["sector"] = metadata.get(
                str(signal.get("ticker")), "Unclassified"
            )
            signal["setup"] = setup_clarity(signal, outcome)
            enriched.append(signal)
        dashboard[group] = enriched
    active_for_concentration = [
        *dashboard.get("active_signals", []),
        *dashboard.get("open_paper_trades", []),
    ]
    dashboard["concentration"] = sector_concentration(active_for_concentration)
    dashboard["setup_statuses"] = list(SETUP_STATUSES)
    return dashboard
