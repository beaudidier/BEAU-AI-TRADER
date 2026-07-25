import unittest

from calibration.integrity_audit import _bootstrap, _summary


class BacktestIntegrityAuditTests(unittest.TestCase):
    def test_bootstrap_is_deterministic(self):
        rows = [{"r_multiple": "1"}, {"r_multiple": "-1"}, {"r_multiple": "0.5"}]
        self.assertEqual(_bootstrap(rows), _bootstrap(rows))

    def test_return_summary_uses_final_trade_outcomes(self):
        summary = _summary([1.0, -0.5, 0.0])
        self.assertEqual(summary["trades"], 3)
        self.assertEqual(summary["win_rate"], 33.3333)
        self.assertEqual(summary["profit_factor"], 2.0)


if __name__ == "__main__":
    unittest.main()
