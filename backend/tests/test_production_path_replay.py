from __future__ import annotations

import unittest
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from forward_validation.production_replay import (
    attach_live_table_proof,
    capture_live_table_fingerprints,
    render_report,
    run_production_path_replay,
)


def _history(end: str = "2026-07-24", rows: int = 240) -> pd.DataFrame:
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
    def __init__(self, histories):
        self.histories = histories
        self.calls = []

    def get_history(self, ticker, **_kwargs):
        self.calls.append(ticker)
        value = self.histories.get(ticker)
        return value.copy() if value is not None else None


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *_args):
        return self

    def execute(self):
        return SimpleNamespace(data=self.rows)


class ReadOnlyClient:
    def __init__(self, tables):
        self.tables = tables
        self.requested = []

    def table(self, name):
        self.requested.append(name)
        return FakeQuery(self.tables.get(name, []))


def _analysis(regime_score=70):
    return {
        "overall_score": 82,
        "engines": {
            "market_regime": {
                "score": regime_score,
                "explanation": "Risk-on" if regime_score >= 65 else "Defensive",
            }
        },
    }


class ProductionPathReplayTests(unittest.TestCase):
    now = datetime(2026, 7, 25, 14, 0, tzinfo=timezone.utc)

    @patch("forward_validation.production_replay.calculate_institutional_analysis", return_value=_analysis())
    @patch("strategies.swing_strategy.calculate_institutional_analysis", return_value=_analysis())
    def test_production_and_standalone_signal_values_match(self, _production_analysis, _standalone_analysis):
        provider = FakeProvider({"SPY": _history(), "AAPL": _history()})
        result = run_production_path_replay(
            provider=provider,
            symbols=["AAPL"],
            now=self.now,
        )
        item = result["results"][0]
        self.assertEqual(item["status"], "signal")
        self.assertEqual(item["production_signal"], item["standalone_signal"])
        self.assertEqual(item["mismatches"], [])
        self.assertEqual(item["raw_data_timestamp"], "2026-07-24T00:00:00")
        self.assertEqual(item["expiry_date"], "2026-07-29")

    @patch("forward_validation.production_replay.calculate_institutional_analysis", return_value=_analysis(40))
    @patch("strategies.swing_strategy.calculate_institutional_analysis", return_value=_analysis(40))
    def test_rejection_is_explainable_and_matches_production(self, _production_analysis, _standalone_analysis):
        provider = FakeProvider({"SPY": _history(), "AAPL": _history()})
        result = run_production_path_replay(provider=provider, symbols=["AAPL"], now=self.now)
        item = result["results"][0]
        self.assertEqual(item["status"], "rejected")
        self.assertIn("below the frozen minimum", item["reasons"][0])
        self.assertGreater(item["diagnostics"]["candidate_target_2"], item["diagnostics"]["candidate_target_1"])
        self.assertEqual(result["summary"]["mismatch_count"], 0)

    @patch("forward_validation.production_replay.calculate_institutional_analysis", return_value=_analysis())
    @patch("strategies.swing_strategy.calculate_institutional_analysis", return_value=_analysis())
    def test_duplicates_and_provider_failures_are_accounted_for(self, _production_analysis, _standalone_analysis):
        provider = FakeProvider({"SPY": _history(), "AAPL": _history(), "MSFT": None})
        result = run_production_path_replay(
            provider=provider,
            symbols=["AAPL", "AAPL", "MSFT"],
            now=self.now,
        )
        self.assertEqual(result["summary"]["duplicate_requests_prevented"], 1)
        self.assertEqual(result["summary"]["failed_count"], 1)
        self.assertIn("MSFT", result["summary"]["provider_errors"])
        self.assertEqual(provider.calls.count("AAPL"), 1)

    @patch("forward_validation.production_replay.calculate_institutional_analysis", return_value=_analysis())
    @patch("strategies.swing_strategy.calculate_institutional_analysis", return_value=_analysis())
    def test_explicit_replay_date_excludes_later_candles(self, _production_analysis, _standalone_analysis):
        history = _history("2026-07-27", 241)
        provider = FakeProvider({"SPY": history, "AAPL": history})
        result = run_production_path_replay(
            provider=provider,
            symbols=["AAPL"],
            now=datetime(2026, 7, 28, 14, 0, tzinfo=timezone.utc),
            replay_date=date(2026, 7, 24),
        )
        self.assertEqual(result["replay_date"], "2026-07-24")
        self.assertEqual(result["results"][0]["raw_data_timestamp"], "2026-07-24T00:00:00")
        self.assertEqual(result["results"][0]["production_signal"]["data_timestamp"], "2026-07-24T00:00:00")

    def test_live_table_proof_is_read_only_and_reported(self):
        client = ReadOnlyClient(
            {
                "forward_validation_runs": [{"id": "run-1"}],
                "forward_validation_signals": [{"id": "signal-1"}],
                "forward_validation_outcomes": [],
                "paper_trades": [{"id": "trade-1"}],
            }
        )
        before = capture_live_table_fingerprints(client)
        after = capture_live_table_fingerprints(client)
        result = {
            "replay_date": "2026-07-24",
            "strategy_version": "regime-gated-pullback-v1.0.0",
            "runner_version": "forward-validation-runner-v1.0.0",
            "summary": {
                "symbols_requested": ["AAPL"],
                "requested_count": 1,
                "symbols_completed": ["AAPL"],
                "completed_count": 1,
                "symbols_failed": [],
                "failed_count": 0,
                "signals_found": 0,
                "rejected_setups": 1,
                "duplicate_requests_prevented": 0,
                "provider_errors": {},
                "mismatch_count": 0,
            },
            "results": [
                {
                    "ticker": "AAPL",
                    "status": "rejected",
                    "raw_data_timestamp": "2026-07-24T00:00:00",
                    "diagnostics": {},
                    "reasons": ["Test rejection."],
                    "mismatches": [],
                }
            ],
            "mismatches": [],
        }
        attach_live_table_proof(result, before, after)
        self.assertTrue(result["live_table_proof"]["unchanged"])
        self.assertEqual(client.requested.count("forward_validation_signals"), 2)
        self.assertIn("Live production tables unchanged: **YES**", render_report(result))


if __name__ == "__main__":
    unittest.main()
