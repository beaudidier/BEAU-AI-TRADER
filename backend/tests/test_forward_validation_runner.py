from __future__ import annotations

import unittest
from copy import deepcopy
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from forward_validation.runner import (
    RUNNER_VERSION,
    _one,
    market_session_closed,
    next_scheduled_run,
    run_for_user,
    runner_health,
    signal_expiry_date,
)


def _history(end: str = "2026-07-27", rows: int = 240) -> pd.DataFrame:
    dates = pd.bdate_range(end=end, periods=rows)
    return pd.DataFrame(
        {
            "Open": [100.0] * rows,
            "High": [101.0] * rows,
            "Low": [99.0] * rows,
            "Close": [100.0] * rows,
            "Volume": [1_000_000] * rows,
        },
        index=dates,
    )


class FakeProvider:
    def __init__(self, histories: dict[str, pd.DataFrame | None]):
        self.histories = histories

    def get_history(self, ticker: str, **_kwargs):
        value = self.histories.get(ticker)
        if isinstance(value, Exception):
            raise value
        return value.copy() if value is not None else None


class FakeStrategy:
    def scan(self, *, ticker, history, benchmark, signal_timestamp):
        del benchmark
        return {
            "ticker": ticker,
            "signal_timestamp": signal_timestamp,
            "signal_price": 100.0,
            "proposed_pullback_entry": 99.0,
            "expected_entry_fill": 99.0495,
            "stop_loss": 95.0,
            "target_1": 107.1485,
            "target_2": 115.2475,
            "market_regime": "Risk-on",
            "market_regime_score": 70.0,
            "confidence": 82.0,
            "strategy_version": "regime-gated-pullback-v1.0.0",
            "data_timestamp": pd.Timestamp(history.index[-1]).isoformat(),
        }


class MemoryStore:
    def __init__(self):
        self.runs: list[dict] = []
        self.signals: list[dict] = []
        self.outcomes: dict[str, dict] = {}
        self.paper_trades: list[dict] = []

    def create_run(self, values):
        row = {"id": f"run-{len(self.runs) + 1}", **deepcopy(values)}
        self.runs.append(row)
        return deepcopy(row)

    def finish_run(self, run_id, values):
        row = next(item for item in self.runs if item["id"] == run_id)
        row.update(deepcopy(values))
        return deepcopy(row)

    def list_runs(self, user_id):
        return deepcopy([item for item in self.runs if item["user_id"] == user_id])

    def list_user_ids(self):
        return ["user-1"]

    def list_signals(self, user_id):
        return deepcopy([item for item in self.signals if item["user_id"] == user_id])

    def list_outcomes(self, user_id):
        return deepcopy([item for item in self.outcomes.values() if item["user_id"] == user_id])

    def find_signal(self, user_id, ticker, strategy_version, data_timestamp):
        return next(
            (
                deepcopy(item)
                for item in self.signals
                if item["user_id"] == user_id
                and item["ticker"] == ticker
                and item["strategy_version"] == strategy_version
                and item["data_timestamp"] == data_timestamp
            ),
            None,
        )

    def create_signal(self, values):
        row = {"id": f"signal-{len(self.signals) + 1}", **deepcopy(values)}
        self.signals.append(row)
        return deepcopy(row)

    def save_outcome(self, values):
        row = {**self.outcomes.get(values["signal_id"], {}), **deepcopy(values)}
        self.outcomes[values["signal_id"]] = row
        return deepcopy(row)

    def list_open_paper_trades(self, user_id):
        return deepcopy([item for item in self.paper_trades if item["user_id"] == user_id and item["status"] == "OPEN"])

    def update_paper_trade(self, trade_id, values):
        row = next(item for item in self.paper_trades if item["id"] == trade_id)
        row.update(deepcopy(values))
        return deepcopy(row)


class ForwardValidationRunnerTests(unittest.TestCase):
    now = datetime(2026, 7, 27, 22, 30, tzinfo=timezone.utc)

    def test_supabase_single_row_responses_are_normalized(self):
        self.assertEqual(_one(SimpleNamespace(data=[{"id": "run-1"}])), {"id": "run-1"})
        self.assertEqual(_one(SimpleNamespace(data=[])), {})
        self.assertEqual(_one(SimpleNamespace(data={"id": "run-1"})), {"id": "run-1"})

    def test_market_close_requires_trading_day_completed_candle(self):
        closed, reason = market_session_closed(
            datetime(2026, 7, 27, 18, 0, tzinfo=timezone.utc),
            _history(),
        )
        self.assertFalse(closed)
        self.assertIn("not complete", reason)
        saturday, reason = market_session_closed(
            datetime(2026, 7, 25, 22, 30, tzinfo=timezone.utc),
            _history("2026-07-24"),
        )
        self.assertFalse(saturday)
        self.assertIn("not a US trading session", reason)

    def test_expiry_and_schedule_skip_non_trading_days(self):
        self.assertEqual(signal_expiry_date(date(2026, 7, 2)), date(2026, 7, 8))
        scheduled = next_scheduled_run(datetime(2026, 7, 24, 23, 0, tzinfo=timezone.utc))
        self.assertTrue(scheduled.startswith("2026-07-27T22:30"))

    @patch("forward_validation.runner.strategy_registry.require_usable", return_value=FakeStrategy())
    def test_records_run_immutable_signal_and_prevents_duplicate(self, _strategy):
        store = MemoryStore()
        provider = FakeProvider({"SPY": _history(), "AAPL": _history()})
        first = run_for_user(store, "user-1", provider=provider, now=self.now, symbols=["AAPL"])
        second = run_for_user(store, "user-1", provider=provider, now=self.now, symbols=["AAPL"])

        self.assertEqual(first["runner_version"], RUNNER_VERSION)
        self.assertEqual(first["status"], "success")
        self.assertEqual(first["signals_created"], 1)
        self.assertEqual(len(store.signals), 1)
        self.assertEqual(store.signals[0]["initial_status"], "waiting_for_entry")
        self.assertEqual(store.signals[0]["expiry_date"], "2026-07-30")
        self.assertEqual(second["signals_created"], 0)
        self.assertEqual(second["duplicates_prevented"], 1)

    @patch("forward_validation.runner.strategy_registry.require_usable", return_value=FakeStrategy())
    def test_partial_provider_failure_is_recorded(self, _strategy):
        store = MemoryStore()
        provider = FakeProvider({"SPY": _history(), "AAPL": _history(), "MSFT": None})
        result = run_for_user(store, "user-1", provider=provider, now=self.now, symbols=["AAPL", "MSFT"])
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["symbols_completed"], ["AAPL"])
        self.assertEqual(result["symbols_failed"], ["MSFT"])
        self.assertIn("MSFT", result["provider_errors"])

    def test_non_trading_day_creates_a_skipped_run(self):
        store = MemoryStore()
        provider = FakeProvider({"SPY": _history("2026-07-24")})
        result = run_for_user(
            store,
            "user-1",
            provider=provider,
            now=datetime(2026, 7, 25, 22, 30, tzinfo=timezone.utc),
            symbols=["AAPL"],
        )
        self.assertEqual(result["status"], "skipped")
        self.assertIn("not a US trading session", result["message"])
        self.assertEqual(len(store.signals), 0)

    @patch("forward_validation.runner.strategy_registry.require_usable", return_value=FakeStrategy())
    def test_updates_signal_outcome_and_paper_mark_to_market(self, _strategy):
        store = MemoryStore()
        signal_history = _history("2026-07-24")
        signal = {
            "id": "signal-1",
            "user_id": "user-1",
            **FakeStrategy().scan(
                ticker="AAPL",
                history=signal_history,
                benchmark=signal_history,
                signal_timestamp="2026-07-24T22:30:00+00:00",
            ),
            "expiry_date": "2026-07-29",
            "initial_status": "waiting_for_entry",
        }
        store.signals.append(signal)
        store.outcomes["signal-1"] = {"signal_id": "signal-1", "user_id": "user-1", "status": "waiting_for_entry"}
        store.paper_trades.append({"id": "paper-1", "user_id": "user-1", "ticker": "AAPL", "status": "OPEN", "entry_price": 95.0, "quantity": 2})
        provider = FakeProvider({"SPY": _history(), "AAPL": _history()})

        result = run_for_user(store, "user-1", provider=provider, now=self.now, symbols=["AAPL"])

        self.assertGreaterEqual(result["outcomes_updated"], 2)
        self.assertEqual(store.outcomes["signal-1"]["status"], "entered")
        self.assertEqual(store.paper_trades[0]["market_price"], 100.0)
        self.assertEqual(store.paper_trades[0]["unrealized_pnl"], 10.0)

    def test_runner_health_reports_last_successful_run(self):
        runs = [
            {"status": "success", "started_at": "2026-07-24T22:30:00+00:00"},
            {"status": "failed", "started_at": "2026-07-25T22:30:00+00:00"},
        ]
        health = runner_health(runs, self.now)
        self.assertEqual(health["health"], "degraded")
        self.assertEqual(health["last_successful_run"]["status"], "success")


if __name__ == "__main__":
    unittest.main()
