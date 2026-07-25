import unittest

import pandas as pd

from backtesting.execution import simulate_long_trade


def _candles(rows):
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"])


class PartialExitAccountingTests(unittest.TestCase):
    def _simulate(self, rows, **kwargs):
        parameters = {"shares": 100, "max_holding_days": 30, "slippage_bps": 0, "transaction_cost_bps": 0}
        parameters.update(kwargs)
        return simulate_long_trade(_candles(rows), 0, 100, 95, 110, 120, **parameters)

    def test_tp1_then_tp2_realises_two_legs(self):
        result = self._simulate([(100, 111, 99, 108), (108, 121, 107, 120)])
        self.assertEqual([leg["leg"] for leg in result["exit_legs"]], ["TP1", "TP2"])
        self.assertEqual([leg["shares"] for leg in result["exit_legs"]], [50, 50])
        self.assertAlmostEqual(result["total_pnl"], 1500)
        self.assertAlmostEqual(result["r_multiple"], 3)

    def test_tp1_then_stop_includes_both_realised_outcomes(self):
        result = self._simulate([(100, 111, 99, 108), (108, 109, 94, 95)])
        self.assertEqual([leg["leg"] for leg in result["exit_legs"]], ["TP1", "STOP"])
        self.assertAlmostEqual(result["total_pnl"], 250)
        self.assertAlmostEqual(result["r_multiple"], 0.5)

    def test_direct_stop(self):
        result = self._simulate([(100, 109, 94, 95)])
        self.assertEqual([leg["leg"] for leg in result["exit_legs"]], ["STOP"])
        self.assertAlmostEqual(result["r_multiple"], -1)

    def test_direct_tp2_records_tp1_and_tp2_on_the_same_candle(self):
        result = self._simulate([(100, 121, 99, 120)])
        self.assertEqual([leg["leg"] for leg in result["exit_legs"]], ["TP1", "TP2"])
        self.assertAlmostEqual(result["r_multiple"], 3)

    def test_unresolved_trade_exits_at_the_time_cap(self):
        result = self._simulate([(100, 105, 98, 102)], max_holding_days=1)
        self.assertEqual([leg["leg"] for leg in result["exit_legs"]], ["TIME"])
        self.assertAlmostEqual(result["r_multiple"], 0.4)

    def test_stop_wins_same_candle_ambiguity(self):
        result = self._simulate([(100, 121, 94, 100)])
        self.assertEqual([leg["leg"] for leg in result["exit_legs"]], ["STOP"])
        self.assertFalse(result["tp1_hit"])

    def test_costs_and_slippage_are_applied_to_each_fill(self):
        result = simulate_long_trade(
            _candles([(100, 110, 99, 100)]), 0, 100, 95, 110, 120,
            shares=100, max_holding_days=1, slippage_bps=5, transaction_cost_bps=5,
        )
        self.assertEqual([leg["leg"] for leg in result["exit_legs"]], ["TP1", "TIME"])
        self.assertAlmostEqual(result["entry_transaction_cost"], 5.0)
        self.assertAlmostEqual(result["total_transaction_cost"], 10.247375)
        self.assertAlmostEqual(result["exit_legs"][0]["exit_price"], 109.945)


if __name__ == "__main__":
    unittest.main()
