"""Scheduled orchestration for the frozen paper-only swing strategy."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import pandas as pd

from config import WATCHLIST
from providers import get_market_data_provider
from providers.provider import MarketDataProvider
from strategies import strategy_registry
from strategies.swing_strategy import ENTRY_WAIT, evaluate_signal

RUNNER_VERSION = "forward-validation-runner-v1.0.0"
SCHEDULE_HOUR_UTC = 22
SCHEDULE_MINUTE_UTC = 30
MARKET_TIMEZONE = ZoneInfo("America/New_York")
MARKET_CLOSE_BUFFER = time(16, 15)
TERMINAL_STATUSES = {"expired", "TP2_hit", "stopped", "completed"}


class ForwardValidationStore(Protocol):
    def create_run(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def finish_run(self, run_id: str, values: dict[str, Any]) -> dict[str, Any]: ...
    def list_runs(self, user_id: str) -> list[dict[str, Any]]: ...
    def list_user_ids(self) -> list[str]: ...
    def list_signals(self, user_id: str) -> list[dict[str, Any]]: ...
    def list_outcomes(self, user_id: str) -> list[dict[str, Any]]: ...
    def find_signal(self, user_id: str, ticker: str, strategy_version: str, data_timestamp: str) -> dict[str, Any] | None: ...
    def create_signal(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def save_outcome(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def list_open_paper_trades(self, user_id: str) -> list[dict[str, Any]]: ...
    def update_paper_trade(self, trade_id: str, values: dict[str, Any]) -> dict[str, Any]: ...


def _data(response: Any) -> list[dict[str, Any]]:
    return response.data or []


def _one(response: Any) -> dict[str, Any]:
    return response.data or {}


@dataclass
class SupabaseForwardValidationStore:
    client: Any

    def create_run(self, values: dict[str, Any]) -> dict[str, Any]:
        return _one(self.client.table("forward_validation_runs").insert(values).execute())

    def finish_run(self, run_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return _one(self.client.table("forward_validation_runs").update(values).eq("id", run_id).execute())

    def list_runs(self, user_id: str) -> list[dict[str, Any]]:
        return _data(
            self.client.table("forward_validation_runs")
            .select("*")
            .eq("user_id", user_id)
            .order("started_at", desc=True)
            .limit(20)
            .execute()
        )

    def list_user_ids(self) -> list[str]:
        return [str(row["id"]) for row in _data(self.client.table("profiles").select("id").execute())]

    def list_signals(self, user_id: str) -> list[dict[str, Any]]:
        return _data(
            self.client.table("forward_validation_signals")
            .select("*")
            .eq("user_id", user_id)
            .order("signal_timestamp", desc=True)
            .execute()
        )

    def list_outcomes(self, user_id: str) -> list[dict[str, Any]]:
        return _data(
            self.client.table("forward_validation_outcomes")
            .select("*")
            .eq("user_id", user_id)
            .execute()
        )

    def find_signal(self, user_id: str, ticker: str, strategy_version: str, data_timestamp: str) -> dict[str, Any] | None:
        result = _one(
            self.client.table("forward_validation_signals")
            .select("*")
            .eq("user_id", user_id)
            .eq("ticker", ticker)
            .eq("strategy_version", strategy_version)
            .eq("data_timestamp", data_timestamp)
            .maybe_single()
            .execute()
        )
        return result or None

    def create_signal(self, values: dict[str, Any]) -> dict[str, Any]:
        return _one(self.client.table("forward_validation_signals").insert(values).execute())

    def save_outcome(self, values: dict[str, Any]) -> dict[str, Any]:
        return _one(
            self.client.table("forward_validation_outcomes")
            .upsert(values, on_conflict="signal_id")
            .execute()
        )

    def list_open_paper_trades(self, user_id: str) -> list[dict[str, Any]]:
        return _data(
            self.client.table("paper_trades")
            .select("*")
            .eq("user_id", user_id)
            .eq("status", "OPEN")
            .execute()
        )

    def update_paper_trade(self, trade_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return _one(self.client.table("paper_trades").update(values).eq("id", trade_id).execute())


def configured_universe() -> list[str]:
    configured = os.getenv("FORWARD_VALIDATION_UNIVERSE", "")
    symbols = configured.split(",") if configured.strip() else WATCHLIST
    return list(dict.fromkeys(symbol.strip().upper() for symbol in symbols if symbol.strip()))


def _observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def _nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    current = date(year, month, 1)
    current += timedelta(days=(weekday - current.weekday()) % 7)
    return current + timedelta(weeks=occurrence - 1)


def _last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def _easter(year: int) -> date:
    a, b, c = year % 19, year // 100, year % 100
    d, e = b // 4, b % 4
    f, g = (b + 8) // 25, (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    return date(year, month, (h + l - 7 * m + 114) % 31 + 1)


def us_market_holidays(year: int) -> set[date]:
    holidays = {
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
        holidays.add(_observed(date(year, 6, 19)))
    return holidays


def is_us_trading_day(day: date) -> bool:
    return day.weekday() < 5 and day not in us_market_holidays(day.year)


def next_trading_day(day: date) -> date:
    candidate = day + timedelta(days=1)
    while not is_us_trading_day(candidate):
        candidate += timedelta(days=1)
    return candidate


def signal_expiry_date(signal_day: date) -> date:
    expiry = signal_day
    for _ in range(ENTRY_WAIT):
        expiry = next_trading_day(expiry)
    return expiry


def next_scheduled_run(now: datetime | None = None) -> str:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    candidate = datetime.combine(moment.date(), time(SCHEDULE_HOUR_UTC, SCHEDULE_MINUTE_UTC), timezone.utc)
    if candidate <= moment:
        candidate += timedelta(days=1)
    while not is_us_trading_day(candidate.astimezone(MARKET_TIMEZONE).date()):
        candidate += timedelta(days=1)
    return candidate.isoformat()


def completed_daily_history(
    provider: MarketDataProvider,
    ticker: str,
    now: datetime,
) -> pd.DataFrame | None:
    history = provider.get_history(ticker, period="2y", interval="1d")
    if history is None or history.empty:
        return history
    result = history.copy()
    result.index = pd.to_datetime(result.index).tz_localize(None)
    eastern = now.astimezone(MARKET_TIMEZONE)
    latest_day = pd.Timestamp(result.index[-1]).date()
    if latest_day >= eastern.date() and eastern.time() < MARKET_CLOSE_BUFFER:
        result = result.iloc[:-1]
    return result


def market_session_closed(now: datetime, benchmark: pd.DataFrame | None) -> tuple[bool, str]:
    eastern = now.astimezone(MARKET_TIMEZONE)
    if not is_us_trading_day(eastern.date()):
        return False, "Today is not a US trading session."
    if eastern.time() < MARKET_CLOSE_BUFFER:
        return False, "The US daily market candle is not complete yet."
    if benchmark is None or benchmark.empty:
        return False, "The completed US benchmark candle is unavailable."
    latest = pd.Timestamp(benchmark.index[-1]).date()
    if latest != eastern.date():
        return False, "The market data provider has not published today's completed candle yet."
    return True, ""


def _finite(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _run_values(user_id: str, now: datetime, symbols: list[str], trigger: str) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "runner_version": RUNNER_VERSION,
        "trigger": trigger,
        "status": "running",
        "started_at": now.isoformat(),
        "symbols_requested": symbols,
        "symbols_completed": [],
        "symbols_failed": [],
        "provider_errors": {},
        "signals_created": 0,
        "duplicates_prevented": 0,
        "outcomes_updated": 0,
    }


def run_for_user(
    store: ForwardValidationStore,
    user_id: str,
    *,
    provider: MarketDataProvider | None = None,
    now: datetime | None = None,
    symbols: list[str] | None = None,
    trigger: str = "manual",
) -> dict[str, Any]:
    provider = provider or get_market_data_provider()
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    universe = symbols or configured_universe()
    run = store.create_run(_run_values(user_id, moment, universe, trigger))
    if not run.get("id"):
        raise RuntimeError("Forward-validation run could not be recorded.")

    completed: list[str] = []
    failed: list[str] = []
    provider_errors: dict[str, str] = {}
    created = duplicates = outcomes_updated = 0
    data_timestamp: str | None = None
    status = "success"
    message = "Forward validation completed."
    try:
        benchmark = completed_daily_history(provider, "SPY", moment)
        closed, reason = market_session_closed(moment, benchmark)
        if not closed:
            status, message = "skipped", reason
            return store.finish_run(
                str(run["id"]),
                {
                    "status": status,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "provider_errors": {"session": reason},
                    "message": reason,
                },
            )

        data_timestamp = pd.Timestamp(benchmark.index[-1]).isoformat()
        signals = store.list_signals(user_id)
        outcomes = {str(item["signal_id"]): item for item in store.list_outcomes(user_id)}
        open_trades = store.list_open_paper_trades(user_id)
        required_symbols = list(dict.fromkeys([*universe, *(str(item["ticker"]) for item in signals), *(str(item["ticker"]) for item in open_trades)]))
        histories: dict[str, pd.DataFrame] = {}
        for ticker in required_symbols:
            try:
                history = completed_daily_history(provider, ticker, moment)
                if history is None or history.empty:
                    raise ValueError("No completed daily history was returned.")
                histories[ticker] = history
                completed.append(ticker)
            except Exception as error:
                failed.append(ticker)
                provider_errors[ticker] = str(error) or type(error).__name__

        for signal in signals:
            signal_id = str(signal["id"])
            existing = outcomes.get(signal_id, {})
            if existing.get("status") in TERMINAL_STATUSES:
                continue
            history = histories.get(str(signal["ticker"]))
            if history is None:
                update = {
                    "signal_id": signal_id,
                    "user_id": user_id,
                    "status": "data_error",
                    "last_evaluated_at": moment.isoformat(),
                }
            else:
                update = {
                    "signal_id": signal_id,
                    "user_id": user_id,
                    **evaluate_signal(signal, history),
                    "last_evaluated_at": moment.isoformat(),
                }
            store.save_outcome(update)
            outcomes_updated += 1

        strategy = strategy_registry.require_usable("swing_trading")
        for ticker in universe:
            history = histories.get(ticker)
            if history is None:
                continue
            ticker_timestamp = pd.Timestamp(history.index[-1]).isoformat()
            if ticker_timestamp != data_timestamp:
                failed.append(ticker)
                provider_errors[ticker] = "The symbol does not have the same completed session as SPY."
                continue
            signal = strategy.scan(
                ticker=ticker,
                history=history,
                benchmark=benchmark,
                signal_timestamp=moment.isoformat(),
            )
            if signal is None:
                continue
            if store.find_signal(user_id, ticker, signal["strategy_version"], signal["data_timestamp"]):
                duplicates += 1
                continue
            signal_day = pd.Timestamp(signal["data_timestamp"]).date()
            try:
                saved = store.create_signal(
                    {
                        "user_id": user_id,
                        **signal,
                        "expiry_date": signal_expiry_date(signal_day).isoformat(),
                        "initial_status": "waiting_for_entry",
                    }
                )
            except Exception:
                if store.find_signal(user_id, ticker, signal["strategy_version"], signal["data_timestamp"]):
                    duplicates += 1
                    continue
                raise
            if saved:
                store.save_outcome(
                    {
                        "signal_id": saved["id"],
                        "user_id": user_id,
                        "status": "waiting_for_entry",
                        "last_evaluated_at": moment.isoformat(),
                    }
                )
                created += 1

        for trade in open_trades:
            history = histories.get(str(trade["ticker"]))
            if history is None:
                continue
            market_price = _finite(history.iloc[-1]["Close"])
            entry = _finite(trade.get("entry_price"))
            quantity = _finite(trade.get("quantity"))
            if market_price is None or entry is None or quantity is None:
                continue
            unrealized = (market_price - entry) * quantity
            store.update_paper_trade(
                str(trade["id"]),
                {
                    "market_price": round(market_price, 6),
                    "unrealized_pnl": round(unrealized, 6),
                    "quote_timestamp": pd.Timestamp(history.index[-1]).isoformat(),
                },
            )
            outcomes_updated += 1

        failed = sorted(set(failed))
        status = "partial" if failed else "success"
        message = "Forward validation completed with partial market data." if failed else "Forward validation completed."
        return store.finish_run(
            str(run["id"]),
            {
                "status": status,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "data_timestamp": data_timestamp,
                "symbols_completed": sorted(set(completed) - set(failed)),
                "symbols_failed": failed,
                "provider_errors": provider_errors,
                "signals_created": created,
                "duplicates_prevented": duplicates,
                "outcomes_updated": outcomes_updated,
                "message": message,
            },
        )
    except Exception as error:
        store.finish_run(
            str(run["id"]),
            {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "data_timestamp": data_timestamp,
                "symbols_completed": sorted(set(completed) - set(failed)),
                "symbols_failed": sorted(set(failed)),
                "provider_errors": {**provider_errors, "runner": str(error) or type(error).__name__},
                "signals_created": created,
                "duplicates_prevented": duplicates,
                "outcomes_updated": outcomes_updated,
                "message": "Forward validation could not complete.",
            },
        )
        raise


def runner_health(runs: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    ordered = sorted(runs, key=lambda item: str(item.get("started_at") or ""), reverse=True)
    last = ordered[0] if ordered else None
    successful = next((item for item in ordered if item.get("status") in {"success", "partial"}), None)
    if last is None:
        health = "waiting"
    elif last.get("status") in {"failed"}:
        health = "degraded"
    elif last.get("status") in {"running"}:
        health = "running"
    else:
        health = "healthy"
    return {
        "health": health,
        "last_run": last,
        "last_successful_run": successful,
        "next_scheduled_run": next_scheduled_run(now),
        "schedule": "22:30 UTC on US trading weekdays",
        "runner_version": RUNNER_VERSION,
    }


def run_scheduled() -> dict[str, Any]:
    from supabase import create_client

    url = os.getenv("SUPABASE_URL")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not service_key:
        raise RuntimeError("Scheduled runner database credentials are not configured.")
    store = SupabaseForwardValidationStore(create_client(url, service_key))
    users = store.list_user_ids()
    results = []
    for user_id in users:
        try:
            result = run_for_user(store, user_id, trigger="scheduled")
            results.append({"user_id": user_id, "status": result.get("status")})
        except Exception as error:
            results.append({"user_id": user_id, "status": "failed", "error": type(error).__name__})
    return {
        "runner_version": RUNNER_VERSION,
        "users_requested": len(users),
        "users_completed": sum(item["status"] != "failed" for item in results),
        "users_failed": sum(item["status"] == "failed" for item in results),
    }


if __name__ == "__main__":
    print(json.dumps(run_scheduled(), indent=2))
