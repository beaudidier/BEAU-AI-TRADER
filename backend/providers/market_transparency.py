"""Deterministic market-session and market-data timestamp transparency."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
import math
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from .provider import MarketDataProvider

MARKET_TIMEZONE = ZoneInfo("America/New_York")
PREMARKET_OPEN = time(4, 0)
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
DAILY_CANDLE_COMPLETE = time(16, 15)
AFTER_HOURS_CLOSE = time(20, 0)


def _observed_fixed_holiday(value: date) -> date:
    if value.weekday() == 5:
        return value - timedelta(days=1)
    if value.weekday() == 6:
        return value + timedelta(days=1)
    return value


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    value = date(year, month, 1)
    value += timedelta(days=(weekday - value.weekday()) % 7)
    return value + timedelta(weeks=occurrence - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        value = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        value = date(year, month + 1, 1) - timedelta(days=1)
    return value - timedelta(days=(value.weekday() - weekday) % 7)


def _easter_sunday(year: int) -> date:
    """Return Gregorian Easter using the anonymous Gregorian algorithm."""

    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def us_market_holidays(year: int) -> set[date]:
    """Return full-day NYSE holidays needed for deterministic session labels."""

    holidays = {
        _observed_fixed_holiday(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
        _easter_sunday(year) - timedelta(days=2),  # Good Friday
        _last_weekday(year, 5, 0),  # Memorial Day
        _observed_fixed_holiday(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),  # Labor Day
        _nth_weekday(year, 11, 3, 4),  # Thanksgiving
        _observed_fixed_holiday(date(year, 12, 25)),
    }
    if year >= 2022:
        holidays.add(_observed_fixed_holiday(date(year, 6, 19)))
    return holidays


def is_us_trading_day(value: date) -> bool:
    holidays = (
        us_market_holidays(value.year - 1)
        | us_market_holidays(value.year)
        | us_market_holidays(value.year + 1)
    )
    return value.weekday() < 5 and value not in holidays


def market_session(now: datetime | None = None) -> str:
    """Classify the current US equity market session."""

    current = _as_utc(now or datetime.now(timezone.utc)).astimezone(
        MARKET_TIMEZONE
    )
    if not is_us_trading_day(current.date()):
        return "closed"
    local_time = current.time().replace(tzinfo=None)
    if PREMARKET_OPEN <= local_time < REGULAR_OPEN:
        return "premarket"
    if REGULAR_OPEN <= local_time < REGULAR_CLOSE:
        return "open"
    if REGULAR_CLOSE <= local_time < AFTER_HOURS_CLOSE:
        return "after-hours"
    return "closed"


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _timestamp(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    try:
        parsed = pd.Timestamp(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
    return parsed.tz_convert("UTC").to_pydatetime()


def _previous_trading_day(value: date) -> date:
    candidate = value - timedelta(days=1)
    while not is_us_trading_day(candidate):
        candidate -= timedelta(days=1)
    return candidate


def latest_completed_session_date(now: datetime | None = None) -> date:
    current = _as_utc(now or datetime.now(timezone.utc)).astimezone(
        MARKET_TIMEZONE
    )
    local_time = current.time().replace(tzinfo=None)
    if is_us_trading_day(current.date()) and local_time >= DAILY_CANDLE_COMPLETE:
        return current.date()
    return _previous_trading_day(current.date())


def latest_completed_candle_timestamp(
    history: pd.DataFrame | None,
    now: datetime | None = None,
) -> str | None:
    if history is None or history.empty:
        return None
    cutoff = latest_completed_session_date(now)
    valid = [
        pd.Timestamp(index)
        for index in history.index
        if pd.Timestamp(index).date() <= cutoff
    ]
    if not valid:
        return None
    return max(valid).isoformat()


def _quote_is_stale(
    quote_timestamp: datetime | None,
    session: str,
    now: datetime,
) -> bool:
    if quote_timestamp is None:
        return True
    age = max(0.0, (now - quote_timestamp).total_seconds())
    maximum_age = {
        "open": 20 * 60,
        "premarket": 2 * 60 * 60,
        "after-hours": 2 * 60 * 60,
        "closed": 72 * 60 * 60,
    }[session]
    return age > maximum_age


def build_market_data_transparency(
    *,
    ticker: str,
    provider: MarketDataProvider,
    quote: dict[str, Any] | None,
    daily_history: pd.DataFrame | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build read-only provenance without changing any trading calculation."""

    generated_at = _as_utc(now or datetime.now(timezone.utc))
    session = market_session(generated_at)
    quote_timestamp = _timestamp((quote or {}).get("timestamp"))
    completed_timestamp = latest_completed_candle_timestamp(
        daily_history,
        generated_at,
    )
    completed_date = (
        pd.Timestamp(completed_timestamp).date()
        if completed_timestamp is not None
        else None
    )
    expected_date = latest_completed_session_date(generated_at)
    quote_stale = _quote_is_stale(quote_timestamp, session, generated_at)
    candle_stale = completed_date is None or completed_date < expected_date

    warnings: list[str] = []
    if quote_timestamp is None:
        warnings.append(
            "The provider did not supply a timestamp for the indicative quote."
        )
    elif quote_stale:
        warnings.append(
            "The indicative quote is older than expected for the current market session."
        )
    if completed_timestamp is None:
        warnings.append("No completed daily candle is available for validation.")
    elif candle_stale:
        warnings.append(
            "The latest completed daily candle is older than the expected US trading session."
        )

    provider_label = str(
        getattr(provider, "provider_name", type(provider).__name__)
    )
    configured_label = str(
        getattr(provider, "quote_data_label", "unknown")
    ).lower()
    data_label = (
        configured_label
        if configured_label in {"live", "delayed", "unknown"}
        else "unknown"
    )
    quote_price = (quote or {}).get("price")
    try:
        quote_price = float(quote_price)
        if not math.isfinite(quote_price) or quote_price <= 0:
            quote_price = None
    except (TypeError, ValueError):
        quote_price = None

    return {
        "ticker": ticker.upper(),
        "provider": provider_label,
        "market_status": session,
        "market_timezone": str(MARKET_TIMEZONE),
        "generated_at": generated_at.isoformat(),
        "current_quote": {
            "label": "indicative current quote",
            "price": quote_price,
            "last_price_update_timestamp": (
                quote_timestamp.isoformat()
                if quote_timestamp is not None
                else None
            ),
            "data_label": data_label,
            "stale": quote_stale,
        },
        "validated_daily_signal": {
            "label": "validated daily signal",
            "latest_completed_candle_timestamp": completed_timestamp,
            "data_label": "delayed" if completed_timestamp else "unknown",
            "stale": candle_stale,
        },
        "stale_data_warning": " ".join(warnings) if warnings else None,
    }
