from __future__ import annotations

import tempfile
import unittest
from datetime import date
from pathlib import Path

import pandas as pd

from forward_validation.data_loader import (
    ForwardValidationDataLoader,
    LoaderConfig,
    validate_completed_history,
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


class ForwardValidationDataLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.config = LoaderConfig(
            batch_size=2,
            concurrency_limit=1,
            symbol_timeout_seconds=2,
            max_retries=2,
            initial_backoff_seconds=0,
            request_pacing_seconds=0,
            maximum_workflow_seconds=10,
            cache_dir=Path(self.temporary.name),
        )

    def tearDown(self):
        self.temporary.cleanup()

    def test_retries_checkpoints_deduplicates_and_reuses_cache(self):
        attempts: dict[str, int] = {}
        checkpoints: list[dict[str, object]] = []

        def fetcher(symbol: str):
            attempts[symbol] = attempts.get(symbol, 0) + 1
            if symbol == "AAPL" and attempts[symbol] == 1:
                raise RuntimeError("temporary provider failure")
            return _history()

        first = ForwardValidationDataLoader(
            fetcher,
            date(2026, 7, 24),
            config=self.config,
            checkpoint=checkpoints.append,
        ).load(["AAPL", "AAPL", "MSFT"])

        self.assertEqual(sorted(first.histories), ["AAPL", "MSFT"])
        self.assertEqual(first.failed_symbols, [])
        self.assertEqual(first.duplicate_requests_prevented, 1)
        self.assertEqual(first.provider_request_count, 3)
        self.assertEqual(first.retry_count, 1)
        self.assertEqual(first.batches_completed, 1)
        self.assertEqual(len(checkpoints), 1)

        second = ForwardValidationDataLoader(
            lambda _symbol: (_ for _ in ()).throw(
                AssertionError("cache should prevent provider access")
            ),
            date(2026, 7, 24),
            config=self.config,
        ).load(["AAPL", "MSFT"], resume_completed=["AAPL", "MSFT"])

        self.assertEqual(second.provider_request_count, 0)
        self.assertEqual(second.cached_symbols, ["AAPL", "MSFT"])
        self.assertEqual(sorted(second.histories), ["AAPL", "MSFT"])

    def test_stale_and_invalid_ohlcv_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Stale market data"):
            validate_completed_history(_history("2026-07-23"), date(2026, 7, 24))

        invalid = _history()
        invalid = invalid.drop(columns=["Volume"])
        with self.assertRaisesRegex(ValueError, "Volume"):
            validate_completed_history(invalid, date(2026, 7, 24))

    def test_incomplete_daily_candle_is_excluded(self):
        history = _history()
        next_day = pd.Timestamp("2026-07-25")
        history.loc[next_day] = [float("nan")] * 5

        result = validate_completed_history(history, date(2026, 7, 24))

        self.assertEqual(pd.Timestamp(result.index[-1]).date(), date(2026, 7, 24))

    def test_bounded_batch_fetch_uses_one_request_per_batch(self):
        batch_calls: list[list[str]] = []

        def batch_fetcher(symbols: list[str]):
            batch_calls.append(symbols)
            return {symbol: _history() for symbol in symbols}

        result = ForwardValidationDataLoader(
            lambda _symbol: (_ for _ in ()).throw(
                AssertionError("individual fallback should not be needed")
            ),
            date(2026, 7, 24),
            batch_fetcher=batch_fetcher,
            config=self.config,
        ).load(["AAPL", "MSFT", "NVDA"])

        self.assertEqual(batch_calls, [["AAPL", "MSFT"], ["NVDA"]])
        self.assertEqual(result.provider_request_count, 2)
        self.assertEqual(sorted(result.histories), ["AAPL", "MSFT", "NVDA"])


if __name__ == "__main__":
    unittest.main()
