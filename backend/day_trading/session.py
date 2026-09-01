from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from .models import MarketSession

EASTERN = ZoneInfo("America/New_York")
PREMARKET_OPEN = time(4, 0)
REGULAR_OPEN = time(9, 30)
REGULAR_CLOSE = time(16, 0)
EARLY_CLOSE = time(13, 0)
AFTER_HOURS_CLOSE = time(20, 0)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _observed(value: date) -> date:
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
    last = (
        date(year + 1, 1, 1)
        if month == 12
        else date(year, month + 1, 1)
    ) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)


@lru_cache(maxsize=16)
def market_holidays(year: int) -> set[date]:
    values = {
        _observed(date(year, 1, 1)),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _easter(year) - timedelta(days=2),
        _last_weekday(year, 5, 0),
        _observed(date(year, 7, 4)),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed(date(year, 12, 25)),
    }
    if year >= 2022:
        values.add(_observed(date(year, 6, 19)))
    return values


def is_trading_day(value: date) -> bool:
    holidays = (
        market_holidays(value.year - 1)
        | market_holidays(value.year)
        | market_holidays(value.year + 1)
    )
    return value.weekday() < 5 and value not in holidays


@lru_cache(maxsize=16)
def early_close_days(year: int) -> set[date]:
    thanksgiving = _nth_weekday(year, 11, 3, 4)
    candidates = {
        thanksgiving + timedelta(days=1),
        date(year, 12, 24),
        date(year, 7, 3),
    }
    return {value for value in candidates if is_trading_day(value)}


@lru_cache(maxsize=64)
def regular_close_for(value: date) -> time:
    return EARLY_CLOSE if value in early_close_days(value.year) else REGULAR_CLOSE


def classify_market_session(now: datetime | None = None) -> MarketSession:
    local = as_utc(now or datetime.now(timezone.utc)).astimezone(EASTERN)
    if not is_trading_day(local.date()):
        return MarketSession.CLOSED
    current = local.time().replace(tzinfo=None)
    close = regular_close_for(local.date())
    if PREMARKET_OPEN <= current < REGULAR_OPEN:
        return MarketSession.PREMARKET
    if REGULAR_OPEN <= current < close:
        return MarketSession.REGULAR
    if close <= current < AFTER_HOURS_CLOSE:
        return MarketSession.AFTER_HOURS
    return MarketSession.CLOSED


def next_trading_day(value: date) -> date:
    candidate = value + timedelta(days=1)
    while not is_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def session_bounds(value: date) -> dict[str, datetime]:
    close = regular_close_for(value)
    return {
        "premarket_open": datetime.combine(value, PREMARKET_OPEN, EASTERN),
        "regular_open": datetime.combine(value, REGULAR_OPEN, EASTERN),
        "regular_close": datetime.combine(value, close, EASTERN),
        "after_hours_close": datetime.combine(value, AFTER_HOURS_CLOSE, EASTERN),
    }
