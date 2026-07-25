import unittest

import pandas as pd

from calibration.run_audit import _simulate, _validate_history


class CalibrationAuditTests(unittest.TestCase):
    def test_stop_wins_same_candle_target_ambiguity(self):
        data = pd.DataFrame({"Open": [100], "High": [112], "Low": [94], "Close": [105]})
        result = _simulate(data, 0, 100, 95, 110, 120)
        self.assertTrue(result["stop_hit"])
        self.assertEqual(result["exit_price"], 95)
        self.assertTrue(result["tp1_hit"] is False)

    def test_dataset_validation_rejects_duplicate_and_incomplete_candles(self):
        index = pd.date_range("2024-01-01", periods=600, freq="D").append(pd.DatetimeIndex([pd.Timestamp("2024-01-01")]))
        duplicate = pd.DataFrame({"Open": [1] * len(index), "High": [2] * len(index), "Low": [1] * len(index), "Close": [1] * len(index), "Volume": [1] * len(index)}, index=index)
        self.assertIn("duplicate", _validate_history(duplicate, pd.Timestamp("2026-07-25").date()))
        index = pd.date_range("2024-01-04", periods=599, freq="D").append(pd.DatetimeIndex([pd.Timestamp("2026-07-25")]))
        incomplete = pd.DataFrame({"Open": [1] * len(index), "High": [2] * len(index), "Low": [1] * len(index), "Close": [1] * len(index), "Volume": [1] * len(index)}, index=index)
        self.assertIn("incomplete", _validate_history(incomplete, pd.Timestamp("2026-07-25").date()))


if __name__ == "__main__":
    unittest.main()
