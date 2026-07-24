import unittest

import pandas as pd

from calibration.run_audit import _simulate


class CalibrationAuditTests(unittest.TestCase):
    def test_stop_wins_same_candle_target_ambiguity(self):
        data = pd.DataFrame({"Open": [100], "High": [112], "Low": [94], "Close": [105]})
        result = _simulate(data, 0, 100, 95, 110, 120)
        self.assertTrue(result["stop_hit"])
        self.assertEqual(result["exit_price"], 95)
        self.assertTrue(result["tp1_hit"] is False)


if __name__ == "__main__":
    unittest.main()
