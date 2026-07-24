import unittest
from datetime import datetime, timezone

import pandas as pd

from validation.validation_engine import RecommendationValidationStore


class ValidationEngineTests(unittest.TestCase):
    def test_records_and_evaluates_forward_windows(self):
        store = RecommendationValidationStore()
        record = store.record("NVDA", 82, "BUY", 100, 95, 110, "Risk-on", datetime(2026, 1, 1, tzinfo=timezone.utc))
        index = pd.date_range("2026-01-02", periods=31, freq="D")
        history = pd.DataFrame({"High": [111] * 31, "Low": [97] * 31}, index=index)
        store.evaluate(record, history)
        self.assertTrue(record["evaluations"]["1"]["tp1_hit"])
        self.assertFalse(record["evaluations"]["1"]["stop_hit"])
        metrics = store.dashboard()
        self.assertEqual(metrics["buy_accuracy"], 100)
        self.assertEqual(metrics["evaluated_observations"], 5)

    def test_same_ticker_and_day_is_recorded_once(self):
        store = RecommendationValidationStore()
        timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = store.record("NVDA", 82, "BUY", 100, 95, 110, "Risk-on", timestamp)
        second = store.record("NVDA", 82, "BUY", 100, 95, 110, "Risk-on", timestamp)
        self.assertEqual(first["id"], second["id"])


if __name__ == "__main__":
    unittest.main()
