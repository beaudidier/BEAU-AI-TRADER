from __future__ import annotations

import unittest
import pandas as pd

from calibration.locked_holdout_validation import _label_market_regimes


class LockedHoldoutValidationTests(unittest.TestCase):
    def test_regime_labels_use_signal_date_only(self):
        dates = pd.date_range("2020-01-01", periods=201)
        spy = pd.DataFrame({"Close": list(range(1, 202))}, index=dates)
        rows = [{"signal_date": str(dates[-1].date())}]
        _label_market_regimes(rows, spy)
        self.assertEqual(rows[0]["market_regime"], "Bull")
        self.assertTrue(rows[0]["out_of_sample"])


if __name__ == "__main__": unittest.main()
