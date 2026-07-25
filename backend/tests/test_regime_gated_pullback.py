from __future__ import annotations

import unittest
import pandas as pd

from calibration.regime_gated_pullback import _breadth


class RegimeGatedPullbackTests(unittest.TestCase):
    def test_breadth_uses_only_cross_sectional_closes(self):
        first = pd.DataFrame({"Close": [10] * 200 + [12]}, index=pd.date_range("2020-01-01", periods=201))
        second = pd.DataFrame({"Close": [10] * 200 + [8]}, index=first.index)
        breadth = _breadth({"A": first, "B": second})
        self.assertAlmostEqual(float(breadth.iloc[-1]), .5)


if __name__ == "__main__": unittest.main()
