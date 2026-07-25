"""Scheduled orchestration for the frozen paper-only swing strategy."""

from __future__ import annotations

import json
import math
import os
import time as monotonic_time
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Protocol
from zoneinfo import ZoneInfo

import pandas as pd

from engines.engine_utils import REQUIRED_MARKET_COLUMNS, safe_float
from decision_rules import recommendation_for_score
from paper_trading.portfolio_risk import (
    account_risk_unit,
    admit_ranked_signals,
    build_portfolio_risk_dashboard,
    risk_day,
)
from providers import get_market_data_provider
from providers.provider import MarketDataProvider
from strategies import strategy_registry
from strategies.swing_strategy import ENTRY_WAIT, evaluate_signal
from universe.universe_registry import PROVIDERS as UNIVERSE_PROVIDERS
from universe.universe_registry import universe_symbols

from .data_loader import ForwardValidationDataLoader, LoaderConfig
from .health import (
    EXCLUSION_OUTCOMES,
    MINIMUM_HISTORY_ROWS,
    classify_data_error,
    health_summary,
    insufficient_history_outcome,
    symbol_outcome,
)
from .setup_clarity import setup_status_from_outcome

RUNNER_VERSION = "forward-validation-runner-v2.2.0"
ACTIVE_UNIVERSE = "sp500"
ACTIVE_MARKET = "stocks"
SCHEDULE_HOUR_UTC = 22
SCHEDULE_MINUTE_UTC = 30
MARKET_TIMEZONE = ZoneInfo("America/New_York")
MARKET_CLOSE_BUFFER = time(16, 15)
TERMINAL_STATUSES = {
    "expired",
    "TP2_hit",
    "stopped",
    "completed",
    "portfolio_blocked",
}
REPLAY_ARTIFACT = (
    Path(__file__).resolve().parents[2]
    / "artifacts"
    / "production_path_replay.json"
)


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
    def list_paper_trades(self, user_id: str) -> list[dict[str, Any]]: ...
    def get_paper_account(self, user_id: str) -> dict[str, Any]: ...
    def list_risk_rejections(self, user_id: str) -> list[dict[str, Any]]: ...
    def create_risk_rejection(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def open_automatic_paper_trade(self, values: dict[str, Any]) -> dict[str, Any]: ...
    def update_paper_trade_by_signal(self, signal_id: str, values: dict[str, Any]) -> dict[str, Any]: ...
    def close_automatic_paper_trade(self, signal_id: str, realized_r: float, completed_at: str) -> dict[str, Any]: ...
    def update_paper_trade(self, trade_id: str, values: dict[str, Any]) -> dict[str, Any]: ...


def _data(response: Any) -> list[dict[str, Any]]:
    return response.data or []


def _one(response: Any) -> dict[str, Any]:
    data = response.data
    if isinstance(data, list):
        return data[0] if data else {}
    return data or {}


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

    def list_paper_trades(self, user_id: str) -> list[dict[str, Any]]:
        return _data(
            self.client.table("paper_trades")
            .select("*")
            .eq("user_id", user_id)
            .order("opened_at", desc=True)
            .execute()
        )

    def get_paper_account(self, user_id: str) -> dict[str, Any]:
        account = _one(
            self.client.table("paper_accounts")
            .select("*")
            .eq("user_id", user_id)
            .maybe_single()
            .execute()
        )
        if account:
            return account
        return _one(
            self.client.table("paper_accounts")
            .insert({"user_id": user_id})
            .execute()
        )

    def list_risk_rejections(self, user_id: str) -> list[dict[str, Any]]:
        return _data(
            self.client.table("portfolio_risk_rejections")
            .select("*")
            .eq("user_id", user_id)
            .order("rejected_at", desc=True)
            .limit(100)
            .execute()
        )

    def create_risk_rejection(
        self, values: dict[str, Any]
    ) -> dict[str, Any]:
        return _one(
            self.client.table("portfolio_risk_rejections")
            .upsert(
                values,
                on_conflict="user_id,source,deduplication_key",
                ignore_duplicates=True,
            )
            .execute()
        )

    def open_automatic_paper_trade(
        self, values: dict[str, Any]
    ) -> dict[str, Any]:
        return _one(
            self.client.rpc(
                "open_forward_validation_paper_trade", values
            ).execute()
        )

    def update_paper_trade_by_signal(
        self, signal_id: str, values: dict[str, Any]
    ) -> dict[str, Any]:
        return _one(
            self.client.table("paper_trades")
            .update(values)
            .eq("forward_validation_signal_id", signal_id)
            .eq("status", "OPEN")
            .execute()
        )

    def close_automatic_paper_trade(
        self,
        signal_id: str,
        realized_r: float,
        completed_at: str,
    ) -> dict[str, Any]:
        return _one(
            self.client.rpc(
                "close_forward_validation_paper_trade",
                {
                    "p_signal_id": signal_id,
                    "p_realized_r": realized_r,
                    "p_completed_at": completed_at,
                },
            ).execute()
        )

    def update_paper_trade(self, trade_id: str, values: dict[str, Any]) -> dict[str, Any]:
        return _one(self.client.table("paper_trades").update(values).eq("id", trade_id).execute())


def configured_universe() -> list[str]:
    configured = os.getenv("FORWARD_VALIDATION_UNIVERSE", ACTIVE_UNIVERSE).strip()
    if "," in configured:
        return list(
            dict.fromkeys(
                symbol.strip().upper()
                for symbol in configured.split(",")
                if symbol.strip()
            )
        )
    return universe_symbols(ACTIVE_MARKET, configured or ACTIVE_UNIVERSE)


def configured_universe_id() -> str:
    configured = os.getenv("FORWARD_VALIDATION_UNIVERSE", ACTIVE_UNIVERSE).strip()
    return "custom" if "," in configured else configured or ACTIVE_UNIVERSE


def universe_snapshot_diagnostics(universe_id: str | None = None) -> dict[str, Any]:
    selected = universe_id or configured_universe_id()
    provider = UNIVERSE_PROVIDERS[ACTIVE_MARKET]
    if selected == "custom":
        symbols = configured_universe()
        return {
            "universe_id": selected,
            "snapshot_version": "custom-runtime",
            "expected_symbols": len(symbols),
            "source_timestamp": None,
        }
    snapshot = provider.snapshot(selected)
    return {
        "universe_id": selected,
        "snapshot_version": str(snapshot["snapshot_sha256"]),
        "expected_symbols": int(snapshot["expected_count"]),
        "source_timestamp": str(snapshot["source"]["timestamp"]),
    }


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


def latest_completed_market_date(now: datetime | None = None) -> date:
    eastern = (now or datetime.now(timezone.utc)).astimezone(MARKET_TIMEZONE)
    candidate = eastern.date()
    if not is_us_trading_day(candidate) or eastern.time() < MARKET_CLOSE_BUFFER:
        candidate -= timedelta(days=1)
        while not is_us_trading_day(candidate):
            candidate -= timedelta(days=1)
    return candidate


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
    if all(column in result.columns for column in REQUIRED_MARKET_COLUMNS):
        complete_rows = result.loc[:, list(REQUIRED_MARKET_COLUMNS)].apply(
            lambda column: column.map(lambda value: safe_float(value) is not None)
        ).all(axis=1)
        result = result.loc[complete_rows]
    if result.empty:
        return result
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


def _automatic_quantity(
    account: dict[str, Any],
    entry_price: float,
    stop_loss: float,
) -> int:
    risk_per_share = entry_price - stop_loss
    cash = _finite(account.get("cash_balance")) or 0.0
    if risk_per_share <= 0 or entry_price <= 0 or cash <= 0:
        return 0
    risk_sized = math.floor(account_risk_unit(account) / risk_per_share)
    cash_sized = math.floor(cash / entry_price)
    return max(0, min(risk_sized, cash_sized))


def _signal_rejection_values(
    user_id: str,
    signal: dict[str, Any],
    decision: dict[str, Any],
) -> dict[str, Any]:
    return {
        "user_id": user_id,
        "deduplication_key": (
            f"{signal.get('ticker')}:{signal.get('strategy_version')}:"
            f"{signal.get('data_timestamp')}"
        ),
        "source": "forward_validation_signal",
        "ticker": str(signal.get("ticker") or "").upper(),
        "signal_id": None,
        "rejection_reason": decision["rejection_reason"],
        "current_open_positions": decision["current_open_positions"],
        "current_open_risk_r": decision["current_open_risk_r"],
        "daily_new_risk_r": decision["daily_new_risk_r"],
        "proposed_risk_r": decision["proposed_risk_r"],
        "signal_rank": decision["signal_rank"],
        "limiting_reference": decision["limiting_reference"],
        "capacity_resets_at": decision["capacity_resets_at"],
        "signal_snapshot": signal,
        "rejected_at": decision["timestamp"],
    }


def _run_values(
    user_id: str,
    now: datetime,
    symbols: list[str],
    trigger: str,
    universe: dict[str, Any],
    resumed_from_run_id: str | None,
) -> dict[str, Any]:
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
        "eligible_symbols": [],
        "completed_eligible_symbols": [],
        "excluded_symbols": {},
        "genuine_failures": {},
        "symbol_outcomes": {},
        "signals_created": 0,
        "duplicates_prevented": 0,
        "outcomes_updated": 0,
        "universe_id": universe["universe_id"],
        "universe_snapshot_version": universe["snapshot_version"],
        "expected_symbols": universe["expected_symbols"],
        "scanned_symbols": 0,
        "cached_symbols": 0,
        "provider_request_count": 0,
        "retry_count": 0,
        "runtime_seconds": 0,
        "batches_completed": 0,
        "total_batches": 0,
        "completion_percentage": 0,
        "provider_health": "running",
        "rejection_reasons": {},
        "checkpoint": {},
        "resumed_from_run_id": resumed_from_run_id,
    }


def _completion_health(expected: int, completed: int) -> tuple[str, float]:
    summary = health_summary(expected, completed)
    return str(summary["health"]), float(summary["completion_percentage"])


def _resume_checkpoint(
    runs: list[dict[str, Any]],
    universe_snapshot_version: str,
) -> tuple[str | None, list[str]]:
    for run in sorted(
        runs, key=lambda item: str(item.get("started_at") or ""), reverse=True
    ):
        if (
            run.get("runner_version") == RUNNER_VERSION
            and run.get("universe_snapshot_version") == universe_snapshot_version
            and run.get("status") in {"running", "partial", "failed"}
        ):
            checkpoint = run.get("checkpoint") or {}
            return str(run.get("id") or "") or None, list(
                checkpoint.get("symbols_completed") or []
            )
    return None, []


def run_for_user(
    store: ForwardValidationStore,
    user_id: str,
    *,
    provider: MarketDataProvider | None = None,
    now: datetime | None = None,
    symbols: list[str] | None = None,
    trigger: str = "manual",
) -> dict[str, Any]:
    workflow_started = monotonic_time.monotonic()
    provider = provider or get_market_data_provider()
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    universe = symbols or configured_universe()
    universe_id = configured_universe_id() if symbols is None else "custom"
    snapshot = universe_snapshot_diagnostics(universe_id)
    if symbols is not None:
        snapshot["snapshot_version"] = "explicit-symbols"
        snapshot["expected_symbols"] = len(set(universe))
    prior_runs = store.list_runs(user_id)
    resumed_from_run_id, resume_completed = _resume_checkpoint(
        prior_runs, snapshot["snapshot_version"]
    )
    run = store.create_run(
        _run_values(
            user_id,
            moment,
            universe,
            trigger,
            snapshot,
            resumed_from_run_id,
        )
    )
    if not run.get("id"):
        raise RuntimeError("Forward-validation run could not be recorded.")

    completed: list[str] = []
    failed: list[str] = []
    provider_errors: dict[str, str] = {}
    eligible: list[str] = []
    excluded: dict[str, dict[str, str]] = {}
    genuine_failures: dict[str, dict[str, str]] = {}
    symbol_outcomes: dict[str, dict[str, str]] = {}
    created = duplicates = outcomes_updated = 0
    cached_symbols: list[str] = []
    provider_request_count = retry_count = batches_completed = total_batches = 0
    rejection_reasons: dict[str, int] = {}
    runtime_seconds = 0.0
    data_timestamp: str | None = None
    status = "success"
    message = "Forward validation completed."
    try:
        eastern = moment.astimezone(MARKET_TIMEZONE)
        closed, reason = market_session_closed(moment, None)
        if (
            not is_us_trading_day(eastern.date())
            or eastern.time() < MARKET_CLOSE_BUFFER
        ):
            status, message = "skipped", reason
            return store.finish_run(
                str(run["id"]),
                {
                    "status": status,
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "provider_errors": {"session": reason},
                    "provider_health": "waiting",
                    "runtime_seconds": round(
                        monotonic_time.monotonic() - workflow_started, 3
                    ),
                    "message": reason,
                },
            )

        loader_config = LoaderConfig.from_environment()

        def fetch_history(ticker: str) -> pd.DataFrame | None:
            return completed_daily_history(provider, ticker, moment)

        def fetch_histories(tickers: list[str]) -> dict[str, pd.DataFrame]:
            return provider.get_histories(
                tickers,
                period="2y",
                interval="1d",
            )

        benchmark_loader = ForwardValidationDataLoader(
            fetch_history,
            eastern.date(),
            batch_fetcher=(
                fetch_histories
                if callable(getattr(provider, "get_histories", None))
                else None
            ),
            config=loader_config,
        )
        benchmark_result = benchmark_loader.load(["SPY"])
        benchmark = benchmark_result.histories.get("SPY")
        closed, reason = market_session_closed(moment, benchmark)
        if not closed:
            raise RuntimeError(reason)

        data_timestamp = pd.Timestamp(benchmark.index[-1]).isoformat()
        signals = sorted(
            store.list_signals(user_id),
            key=lambda item: (
                -(_finite(item.get("confidence")) or 0),
                str(item.get("ticker") or ""),
                str(item.get("signal_timestamp") or ""),
            ),
        )
        outcomes = {str(item["signal_id"]): item for item in store.list_outcomes(user_id)}
        paper_account = store.get_paper_account(user_id)
        paper_trades = store.list_paper_trades(user_id)
        open_trades = [
            trade
            for trade in paper_trades
            if str(trade.get("status")).upper() == "OPEN"
        ]
        paper_by_signal = {
            str(trade["forward_validation_signal_id"]): trade
            for trade in paper_trades
            if trade.get("forward_validation_signal_id")
        }
        required_symbols = list(dict.fromkeys([*universe, *(str(item["ticker"]) for item in signals), *(str(item["ticker"]) for item in open_trades)]))

        def save_checkpoint(values: dict[str, object]) -> None:
            store.finish_run(
                str(run["id"]),
                {
                    "symbols_completed": values["symbols_completed"],
                    "symbols_failed": values["symbols_failed"],
                    "cached_symbols": len(values["cached_symbols"]),
                    "provider_request_count": (
                        benchmark_result.provider_request_count
                        + int(values["provider_request_count"])
                    ),
                    "retry_count": (
                        benchmark_result.retry_count + int(values["retry_count"])
                    ),
                    "runtime_seconds": values["runtime_seconds"],
                    "batches_completed": values["batches_completed"],
                    "total_batches": values["total_batches"],
                    "checkpoint": values,
                },
            )

        data_loader = ForwardValidationDataLoader(
            fetch_history,
            pd.Timestamp(benchmark.index[-1]).date(),
            batch_fetcher=(
                fetch_histories
                if callable(getattr(provider, "get_histories", None))
                else None
            ),
            config=loader_config,
            checkpoint=save_checkpoint,
        )
        loaded = data_loader.load(
            required_symbols,
            resume_completed=resume_completed,
        )
        histories = loaded.histories
        completed = sorted(histories)
        symbol_outcomes = {
            ticker: outcome
            for ticker, outcome in loaded.symbol_outcomes.items()
            if ticker in set(universe)
        }
        genuine_failures = {
            ticker: outcome
            for ticker, outcome in symbol_outcomes.items()
            if outcome["status"] not in {"completed", *EXCLUSION_OUTCOMES}
        }
        failed = sorted(genuine_failures)
        provider_errors = {
            ticker: outcome["reason"]
            for ticker, outcome in genuine_failures.items()
            if outcome["status"] == "provider_failure"
        }
        cached_symbols = sorted(
            set(benchmark_result.cached_symbols + loaded.cached_symbols)
        )
        provider_request_count = (
            benchmark_result.provider_request_count + loaded.provider_request_count
        )
        retry_count = benchmark_result.retry_count + loaded.retry_count
        batches_completed = loaded.batches_completed
        total_batches = loaded.total_batches
        duplicates += loaded.duplicate_requests_prevented

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
                    "setup_status": "invalidated",
                    "invalidation_reason": (
                        "Completed market data is unavailable, so the pending "
                        "setup is not actionable."
                    ),
                    "last_evaluated_at": moment.isoformat(),
                }
            else:
                evaluation = evaluate_signal(signal, history)
                current_price = _finite(history.iloc[-1]["Close"])
                update = {
                    "signal_id": signal_id,
                    "user_id": user_id,
                    **evaluation,
                    "setup_status": setup_status_from_outcome(
                        evaluation.get("status")
                    ),
                    "current_price": (
                        round(current_price, 6)
                        if current_price is not None
                        else None
                    ),
                    "current_price_timestamp": pd.Timestamp(
                        history.index[-1]
                    ).isoformat(),
                    "invalidation_reason": None,
                    "last_evaluated_at": moment.isoformat(),
                }
                entered = evaluation.get("entry_price") is not None
                paper_trade = paper_by_signal.get(signal_id)
                if entered and paper_trade is None:
                    entry_price = float(evaluation["entry_price"])
                    stop_loss = float(signal["stop_loss"])
                    quantity = _automatic_quantity(
                        paper_account, entry_price, stop_loss
                    )
                    if quantity <= 0:
                        update.update(
                            {
                                "status": "portfolio_blocked",
                                "setup_status": "invalidated",
                                "invalidation_reason": (
                                    "The paper account has no safe position size "
                                    "or available simulated cash."
                                ),
                            }
                        )
                    else:
                        opened = store.open_automatic_paper_trade(
                            {
                                "p_user_id": user_id,
                                "p_signal_id": signal_id,
                                "p_ticker": signal["ticker"],
                                "p_entry_price": entry_price,
                                "p_stop_loss": stop_loss,
                                "p_target_1": signal["target_1"],
                                "p_target_2": signal["target_2"],
                                "p_quantity": quantity,
                                "p_confidence_score": signal["confidence"],
                                "p_recommendation": recommendation_for_score(
                                    signal["confidence"]
                                ),
                                "p_market_regime": signal["market_regime"],
                                "p_sector": signal.get("sector") or "Unknown",
                                "p_signal_rank": int(
                                    signal.get("portfolio_signal_rank") or 1
                                ),
                                "p_risk_admitted_at": (
                                    evaluation.get("entry_timestamp")
                                    or moment.isoformat()
                                ),
                            }
                        )
                        if opened.get("blocked"):
                            update.update(
                                {
                                    "status": "portfolio_blocked",
                                    "setup_status": "invalidated",
                                    "invalidation_reason": (
                                        opened.get("rejection_reason")
                                        or "Validated portfolio capacity is unavailable."
                                    ),
                                }
                            )
                        elif opened.get("id"):
                            paper_trade = opened
                            paper_by_signal[signal_id] = opened
                            paper_account["cash_balance"] = (
                                (_finite(paper_account.get("cash_balance")) or 0)
                                - entry_price * quantity
                            )
                if paper_trade and update["status"] == "TP1_hit":
                    initial_risk = _finite(
                        paper_trade.get("initial_risk_r")
                    ) or 0
                    store.update_paper_trade_by_signal(
                        signal_id,
                        {
                            "remaining_fraction": evaluation[
                                "remaining_fraction"
                            ],
                            "remaining_risk_r": round(
                                initial_risk
                                * float(evaluation["remaining_fraction"]),
                                6,
                            ),
                        },
                    )
                if (
                    paper_trade
                    and update["status"]
                    in {"TP2_hit", "stopped", "completed"}
                ):
                    store.close_automatic_paper_trade(
                        signal_id,
                        float(evaluation["realized_r"]),
                        str(
                            evaluation.get("completed_at")
                            or moment.isoformat()
                        ),
                    )
            store.save_outcome(update)
            outcomes_updated += 1

        strategy = strategy_registry.require_usable("swing_trading")
        candidate_signals: list[dict[str, Any]] = []
        for ticker in universe:
            history = histories.get(ticker)
            if history is None:
                continue
            if len(history) < MINIMUM_HISTORY_ROWS:
                outcome = insufficient_history_outcome(len(history))
                symbol_outcomes[ticker] = outcome
                excluded[ticker] = outcome
                genuine_failures.pop(ticker, None)
                provider_errors.pop(ticker, None)
                continue
            eligible.append(ticker)
            ticker_timestamp = pd.Timestamp(history.index[-1]).isoformat()
            if ticker_timestamp != data_timestamp:
                outcome = classify_data_error(
                    "The symbol does not have the same completed session as SPY."
                )
                symbol_outcomes[ticker] = outcome
                genuine_failures[ticker] = outcome
                continue
            try:
                signal = strategy.scan(
                    ticker=ticker,
                    history=history,
                    benchmark=benchmark,
                    signal_timestamp=moment.isoformat(),
                )
            except Exception as error:
                outcome = symbol_outcome(
                    "incomplete_data",
                    f"Strategy calculation could not use the completed data: "
                    f"{str(error) or type(error).__name__}",
                )
                symbol_outcomes[ticker] = outcome
                genuine_failures[ticker] = outcome
                continue
            symbol_outcomes[ticker] = symbol_outcome(
                "completed",
                "The symbol passed data-quality gates and strategy evaluation completed.",
            )
            if signal is None:
                rejection_reasons["frozen_strategy_rejected"] = (
                    rejection_reasons.get("frozen_strategy_rejected", 0) + 1
                )
                continue
            if store.find_signal(user_id, ticker, signal["strategy_version"], signal["data_timestamp"]):
                duplicates += 1
                continue
            candidate_signals.append(signal)

        paper_account = store.get_paper_account(user_id)
        paper_trades = store.list_paper_trades(user_id)
        risk_dashboard = build_portfolio_risk_dashboard(
            paper_account,
            paper_trades,
            now=moment,
        )
        signal_outcome_by_id = outcomes
        admitted_today = sum(
            1
            for item in signals
            if risk_day(item.get("signal_timestamp")) == risk_day(moment)
            and signal_outcome_by_id.get(
                str(item.get("id")), {}
            ).get("status")
            != "portfolio_blocked"
        )
        risk_dashboard["daily_new_risk_used_r"] = max(
            risk_dashboard["daily_new_risk_used_r"],
            float(admitted_today),
        )
        risk_dashboard["remaining_daily_risk_budget_r"] = max(
            0.0,
            1.0 - risk_dashboard["daily_new_risk_used_r"],
        )
        admitted_signals, portfolio_rejected = admit_ranked_signals(
            candidate_signals,
            risk_dashboard,
            timestamp=moment.isoformat(),
        )
        for rejected_signal in portfolio_rejected:
            decision = rejected_signal["portfolio_rejection"]
            store.create_risk_rejection(
                _signal_rejection_values(
                    user_id, rejected_signal, decision
                )
            )
            rejection_reasons["portfolio_limit_rejected"] = (
                rejection_reasons.get("portfolio_limit_rejected", 0) + 1
            )

        for signal in admitted_signals:
            signal_day = pd.Timestamp(signal["data_timestamp"]).date()
            try:
                saved = store.create_signal(
                    {
                        "user_id": user_id,
                        **signal,
                        "expiry_date": signal_expiry_date(signal_day).isoformat(),
                        "initial_status": "waiting_for_entry",
                        "portfolio_signal_rank": signal[
                            "portfolio_signal_rank"
                        ],
                    }
                )
            except Exception:
                if store.find_signal(
                    user_id,
                    signal["ticker"],
                    signal["strategy_version"],
                    signal["data_timestamp"],
                ):
                    duplicates += 1
                    continue
                raise
            if saved:
                store.save_outcome(
                    {
                        "signal_id": saved["id"],
                        "user_id": user_id,
                        "status": "waiting_for_entry",
                        "setup_status": "waiting_for_entry",
                        "current_price": signal["signal_price"],
                        "current_price_timestamp": signal["data_timestamp"],
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

        failed = sorted(genuine_failures)
        universe_completed = sorted(
            ticker
            for ticker in universe
            if symbol_outcomes.get(ticker, {}).get("status") == "completed"
        )
        eligible = sorted(set(eligible))
        excluded = {
            ticker: outcome
            for ticker, outcome in symbol_outcomes.items()
            if outcome["status"] in EXCLUSION_OUTCOMES
        }
        genuine_failures = {
            ticker: outcome
            for ticker, outcome in symbol_outcomes.items()
            if outcome["status"] not in {"completed", *EXCLUSION_OUTCOMES}
        }
        provider_errors = {
            ticker: outcome["reason"]
            for ticker, outcome in genuine_failures.items()
            if outcome["status"] == "provider_failure"
        }
        coverage = health_summary(
            int(snapshot["expected_symbols"]),
            len(universe_completed),
            eligible_symbols=len(eligible),
            excluded_symbols=len(excluded),
            genuine_failures=len(genuine_failures),
        )
        health = str(coverage["health"])
        completion_percentage = float(coverage["completion_percentage"])
        status = (
            "success"
            if health == "healthy"
            else "partial"
            if health == "degraded"
            else "failed"
        )
        runtime_seconds = round(
            monotonic_time.monotonic() - workflow_started, 3
        )
        message = (
            "Forward validation completed."
            if health == "healthy"
            else "Forward validation completed with incomplete market data."
            if health == "degraded"
            else "Forward validation failed the minimum market-data coverage threshold."
        )
        return store.finish_run(
            str(run["id"]),
            {
                "status": status,
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "data_timestamp": data_timestamp,
                "symbols_completed": universe_completed,
                "symbols_failed": failed,
                "provider_errors": provider_errors,
                "eligible_symbols": eligible,
                "completed_eligible_symbols": universe_completed,
                "excluded_symbols": excluded,
                "genuine_failures": genuine_failures,
                "symbol_outcomes": symbol_outcomes,
                "signals_created": created,
                "duplicates_prevented": duplicates,
                "outcomes_updated": outcomes_updated,
                "scanned_symbols": len(universe_completed),
                "cached_symbols": len(cached_symbols),
                "provider_request_count": provider_request_count,
                "retry_count": retry_count,
                "runtime_seconds": runtime_seconds,
                "batches_completed": batches_completed,
                "total_batches": total_batches,
                "completion_percentage": completion_percentage,
                "provider_health": health,
                "last_complete_market_date": pd.Timestamp(
                    benchmark.index[-1]
                ).date().isoformat(),
                "rejection_reasons": rejection_reasons,
                "checkpoint": {
                    "batches_completed": batches_completed,
                    "total_batches": total_batches,
                    "symbols_completed": universe_completed,
                    "symbols_failed": failed,
                    "eligible_symbols": eligible,
                    "excluded_symbols": excluded,
                    "genuine_failures": genuine_failures,
                    "symbol_outcomes": symbol_outcomes,
                    "cached_symbols": cached_symbols,
                    "provider_request_count": provider_request_count,
                    "retry_count": retry_count,
                    "runtime_seconds": runtime_seconds,
                },
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
                "eligible_symbols": sorted(set(eligible)),
                "completed_eligible_symbols": sorted(
                    set(completed) - set(failed)
                ),
                "excluded_symbols": excluded,
                "genuine_failures": genuine_failures,
                "symbol_outcomes": symbol_outcomes,
                "signals_created": created,
                "duplicates_prevented": duplicates,
                "outcomes_updated": outcomes_updated,
                "scanned_symbols": len(set(universe) & set(completed) - set(failed)),
                "cached_symbols": len(cached_symbols),
                "provider_request_count": provider_request_count,
                "retry_count": retry_count,
                "runtime_seconds": round(
                    monotonic_time.monotonic() - workflow_started, 3
                ),
                "batches_completed": batches_completed,
                "total_batches": total_batches,
                "provider_health": "failed",
                "rejection_reasons": rejection_reasons,
                "message": "Forward validation could not complete.",
            },
        )
        raise


def runner_health(runs: list[dict[str, Any]], now: datetime | None = None) -> dict[str, Any]:
    ordered = sorted(runs, key=lambda item: str(item.get("started_at") or ""), reverse=True)
    last = ordered[0] if ordered else None
    successful = next((item for item in ordered if item.get("status") == "success"), None)
    if last is None:
        health = "waiting"
    elif last.get("status") in {"failed"} or last.get("provider_health") == "failed":
        health = "failed"
    elif last.get("status") in {"running"}:
        health = "running"
    elif last.get("status") == "partial" or last.get("provider_health") == "degraded":
        health = "degraded"
    else:
        health = "healthy"
    snapshot = universe_snapshot_diagnostics()
    latest_replay = None
    try:
        replay = json.loads(REPLAY_ARTIFACT.read_text(encoding="utf-8"))
        replay_summary = replay["summary"]
        latest_replay = {
            "replay_date": replay["replay_date"],
            "expected_symbols": replay_summary["requested_count"],
            "completed_symbols": replay_summary["completed_count"],
            "eligible_symbols": replay_summary.get(
                "eligible_count", replay_summary["completed_count"]
            ),
            "completed_eligible_symbols": replay_summary.get(
                "completed_eligible_count", replay_summary["completed_count"]
            ),
            "excluded_symbols": replay_summary.get("excluded_symbols", {}),
            "genuine_failures": replay_summary.get("genuine_failures", {}),
            "completion_percentage": replay_summary["completion_percentage"],
            "health": replay_summary["workflow_health"],
            "signals_found": replay_summary["signals_found"],
            "runtime_seconds": replay_summary.get("runtime_seconds", 0),
            "last_complete_market_date": replay_summary.get(
                "last_complete_market_date", replay["replay_date"]
            ),
        }
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        latest_replay = None
    return {
        "health": health,
        "last_run": last,
        "last_successful_run": successful,
        "next_scheduled_run": next_scheduled_run(now),
        "schedule": "22:30 UTC on US trading weekdays",
        "runner_version": RUNNER_VERSION,
        "latest_replay": latest_replay,
        "active_universe": {
            "id": snapshot["universe_id"],
            "name": "S&P 500",
            "expected_symbols": snapshot["expected_symbols"],
            "snapshot_version": snapshot["snapshot_version"],
        },
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
        "failure_types": sorted(
            {
                str(item["error"])
                for item in results
                if item["status"] == "failed" and item.get("error")
            }
        ),
    }


if __name__ == "__main__":
    summary = run_scheduled()
    print(json.dumps(summary, indent=2))
    if summary["users_failed"]:
        raise SystemExit(1)
