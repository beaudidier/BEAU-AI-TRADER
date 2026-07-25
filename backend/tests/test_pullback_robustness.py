"""Focused tests for isolated pullback robustness accounting."""
from __future__ import annotations
import unittest
import pandas as pd
from calibration.pullback_robustness import _report_regime, _simulate

class PullbackRobustnessTests(unittest.TestCase):
    def test_reports_bull_bear_and_sideways(self):
        self.assertEqual(_report_regime(pd.DataFrame({"Close":list(range(1,202))})),"Bull")
        self.assertEqual(_report_regime(pd.DataFrame({"Close":list(range(202,1,-1))})),"Bear")
        self.assertEqual(_report_regime(pd.DataFrame({"Close":[100]*201})),"Sideways")
    def test_full_target_closes_all_shares(self):
        data=pd.DataFrame({"Open":[100,100],"High":[101,104],"Low":[99,99],"Close":[100,103]}); trade=_simulate(data,0,100,98,103,None,1,0,0)
        self.assertTrue(trade["tp1_hit"]); self.assertEqual(len(trade["exit_legs"]),1); self.assertEqual(trade["exit_legs"][0]["shares"],100)
    def test_stop_is_processed_before_target(self):
        data=pd.DataFrame({"Open":[100],"High":[104],"Low":[97],"Close":[100]}); trade=_simulate(data,0,100,98,103,106,.5,0,0)
        self.assertTrue(trade["stop_hit"]); self.assertFalse(trade["tp1_hit"])

if __name__ == "__main__": unittest.main()
