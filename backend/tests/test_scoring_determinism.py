import unittest

import numpy as np
import pandas as pd

from engines.institutional_engine import calculate_institutional_analysis


def market_data() -> pd.DataFrame:
    index = pd.date_range("2024-01-01", periods=260, freq="D")
    close = np.linspace(100, 160, 260) + np.sin(np.arange(260))
    return pd.DataFrame({"Open": close - .5, "High": close + 1, "Low": close - 1, "Close": close, "Volume": np.full(260, 1_000_000)}, index=index)


class ScoringDeterminismTests(unittest.TestCase):
    def test_identical_market_data_produces_identical_analysis(self):
        data = market_data()
        first = calculate_institutional_analysis(data.copy(), data.copy())
        second = calculate_institutional_analysis(data.copy(), data.copy())
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
