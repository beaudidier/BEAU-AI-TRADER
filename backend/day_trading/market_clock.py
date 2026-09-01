from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

from .models import MarketSession
from .session import (
    EASTERN,
    as_utc,
    classify_market_session,
    is_trading_day,
    next_trading_day,
    session_bounds,
)


class MarketClock:
    def __init__(
        self,
        now: Callable[[], datetime] | None = None,
    ):
        self._now = now or (lambda: datetime.now(timezone.utc))

    def current_time(self) -> datetime:
        return as_utc(self._now())

    def session(self) -> MarketSession:
        return classify_market_session(self.current_time())

    def snapshot(self) -> dict:
        current = self.current_time()
        local = current.astimezone(EASTERN)
        session = self.session()
        trading_date = local.date()
        if not is_trading_day(trading_date):
            trading_date = next_trading_day(trading_date)
        elif (
            session == MarketSession.CLOSED
            and current
            >= session_bounds(trading_date)["after_hours_close"].astimezone(
                timezone.utc
            )
        ):
            trading_date = next_trading_day(trading_date)
        bounds = session_bounds(trading_date)
        if session == MarketSession.CLOSED:
            next_transition = bounds["premarket_open"]
        elif session == MarketSession.PREMARKET:
            next_transition = bounds["regular_open"]
        elif session == MarketSession.REGULAR:
            next_transition = bounds["regular_close"]
        else:
            next_transition = bounds["after_hours_close"]
        return {
            "status": session.value,
            "timestamp": current.isoformat(),
            "timezone": str(EASTERN),
            "is_trading_day": is_trading_day(local.date()),
            "is_early_close": (
                bounds["regular_close"].hour == 13
            ),
            "regular_open": bounds["regular_open"].astimezone(
                timezone.utc
            ).isoformat(),
            "regular_close": bounds["regular_close"].astimezone(
                timezone.utc
            ).isoformat(),
            "next_transition": next_transition.astimezone(
                timezone.utc
            ).isoformat(),
        }
