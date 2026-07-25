from __future__ import annotations

import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import pandas as pd

from atr import add_atr
from calibration.trade_evidence import (
    CATEGORY_QUOTAS,
    SOURCE_LEDGER,
    _deterministic_stratified_selections,
    _population_rows,
)
from engines.institutional_engine import calculate_institutional_analysis

ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = ROOT / "artifacts" / "trade_evidence_summary.json"
LEDGER_PATH = ROOT / "artifacts" / "trade_evidence" / "selected_trade_ledger.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class HistoricalTradeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = json.loads(SUMMARY_PATH.read_text())
        cls.ledger = json.loads(LEDGER_PATH.read_text())
        cls.examples = cls.summary["examples"]
        cls.source_by_id = {record["evidence_id"]: record for record in cls.ledger["records"]}
        cls.histories = {
            ticker: pd.read_csv(ROOT / source["path"], index_col=0, parse_dates=True)
            for ticker, source in cls.summary["sources"]["raw_files"].items()
        }

    def test_distribution_classification_and_raw_sources_are_complete(self):
        self.assertEqual(self.summary["example_count"], 30)
        self.assertEqual(
            self.summary["distribution"],
            {"WINNER": 10, "LOSER": 10, "EXPIRED": 5, "REJECTED": 5},
        )
        self.assertEqual(set(self.summary["coverage"]["market_regimes"]), {"Bull", "Bear", "Sideways"})
        self.assertEqual(self.summary["coverage"]["years"], [2017, 2018, 2019, 2020, 2021])
        self.assertGreaterEqual(len(self.summary["coverage"]["sectors"]), 10)
        self.assertTrue(self.summary["all_audit_checks_passed"])
        self.assertFalse(self.summary["future_profitability_guaranteed"])
        self.assertEqual(_sha256(SOURCE_LEDGER), self.ledger["source_sha256"])
        for example in self.examples:
            self.assertTrue(example["classification"]["retrospective_holdout"])
            self.assertTrue(example["classification"]["out_of_sample"])
            self.assertFalse(example["classification"]["forward_validation"])
            self.assertTrue(all(example["audit_checks"].values()))
            self.assertTrue(example["audit_checks"]["sector_matches_frozen_universe"])
            self.assertTrue(example["audit_checks"]["historical_regime_matches_raw_spy"])
            self.assertTrue(example["audit_checks"]["outcome_class_matches_source_record"])
        for ticker, source in self.summary["sources"]["raw_files"].items():
            self.assertEqual(_sha256(ROOT / source["path"]), source["sha256"], ticker)

    def test_selection_is_deterministic_and_uses_the_full_oos_population(self):
        ledger = pd.read_csv(SOURCE_LEDGER, low_memory=False)
        population = _population_rows(ledger)
        first, first_manifest = _deterministic_stratified_selections(population)
        second, second_manifest = _deterministic_stratified_selections(population)
        self.assertEqual(first, second)
        self.assertEqual(first_manifest, second_manifest)
        self.assertEqual(first_manifest["candidate_population"], 111348)
        self.assertEqual(first_manifest["quotas"], CATEGORY_QUOTAS)
        self.assertEqual(first_manifest["selected_keys_sha256"], self.summary["selection"]["selected_keys_sha256"])
        self.assertEqual(first_manifest["selected_keys"], self.ledger["selection"]["selected_keys"])
        self.assertTrue(self.summary["selection"]["deterministic_replay_verified"])
        self.assertFalse(self.summary["selection"]["milestone_34_audit"]["manual_record_ids_used"])

    def test_frontend_payload_and_charts_match_the_audited_artifacts(self):
        frontend = json.loads((ROOT / "frontend" / "public" / "evidence" / "summary.json").read_text())
        self.assertEqual(frontend, self.summary)
        for example in self.examples:
            source = ROOT / example["chart"]["file"]
            public = ROOT / "frontend" / "public" / example["chart"]["public_url"].lstrip("/")
            self.assertEqual(_sha256(source), _sha256(public), example["id"])

    def test_chart_values_and_markers_match_evidence_ledger(self):
        for example in self.examples:
            with self.subTest(example=example["id"]):
                levels = example["levels"]
                chart = example["chart"]
                self.assertEqual(chart["lines"]["proposed_pullback_entry"], levels["proposed_pullback_entry"])
                self.assertEqual(chart["lines"]["swing_low_20"], levels["swing_low_20"])
                self.assertEqual(chart["lines"]["stop_loss"], levels["stop_loss"])
                self.assertEqual(chart["lines"]["target_1"], levels["target_1"])
                self.assertEqual(chart["lines"]["target_2"], levels["target_2"])
                root = ET.parse(ROOT / chart["file"]).getroot()
                self.assertAlmostEqual(float(root.attrib["data-entry"]), levels["expected_entry_fill"], places=6)
                self.assertAlmostEqual(float(root.attrib["data-stop"]), levels["stop_loss"], places=6)
                self.assertAlmostEqual(float(root.attrib["data-target-1"]), levels["target_1"], places=6)
                self.assertAlmostEqual(float(root.attrib["data-target-2"]), levels["target_2"], places=6)
                self.assertAlmostEqual(float(root.attrib["data-swing-low"]), levels["swing_low_20"], places=6)
                self.assertEqual(root.attrib["data-signal-timestamp"], example["data_timestamp"])

                source_rows = self.source_by_id[example["id"]]["source_rows"]
                source = source_rows[0]
                self.assertAlmostEqual(levels["ema20"], source["ema20"], places=6)
                self.assertAlmostEqual(levels["atr"], source["atr"], places=6)
                self.assertAlmostEqual(levels["swing_low_20"], source["swing_low_20"], places=6)
                if example["actual_entry_date"]:
                    self.assertAlmostEqual(example["actual_entry_price"], source["entry_price"], places=6)
                    self.assertAlmostEqual(levels["stop_loss"], source["stop_loss"], places=6)
                    self.assertAlmostEqual(levels["target_1"], source["target_1"], places=6)
                    self.assertAlmostEqual(levels["target_2"], source["target_2"], places=6)
                    self.assertEqual(chart["markers"]["entry"]["date"], example["actual_entry_date"])
                    self.assertEqual(
                        [(marker["date"], marker["label"]) for marker in chart["markers"]["exits"]],
                        [(leg["exit_date"], leg["leg"]) for leg in example["exit_legs"]],
                    )
                else:
                    self.assertIsNone(chart["markers"]["entry"])
                    self.assertEqual(chart["markers"]["exits"], [])

    def test_entry_and_exit_dates_match_raw_candles(self):
        for example in self.examples:
            data = self.histories[example["ticker"]]
            signal_date = pd.Timestamp(example["signal_date"])
            with self.subTest(example=example["id"]):
                self.assertIn(signal_date, data.index)
                if not example["actual_entry_date"]:
                    continue
                entry_date = pd.Timestamp(example["actual_entry_date"])
                self.assertIn(entry_date, data.index)
                signal_index = data.index.get_loc(signal_date)
                entry_index = data.index.get_loc(entry_date)
                self.assertIn(entry_index - signal_index, range(1, 4))
                candle = data.loc[entry_date]
                self.assertLessEqual(float(candle["Low"]), example["levels"]["proposed_pullback_entry"])
                self.assertGreaterEqual(float(candle["High"]), example["levels"]["proposed_pullback_entry"])
                for leg in example["exit_legs"]:
                    exit_date = pd.Timestamp(leg["exit_date"])
                    self.assertIn(exit_date, data.index)
                    exit_candle = data.loc[exit_date]
                    if leg["leg"] == "STOP":
                        self.assertLessEqual(float(exit_candle["Low"]), example["levels"]["stop_loss"])
                    elif leg["leg"] == "TP1":
                        self.assertGreaterEqual(float(exit_candle["High"]), example["levels"]["target_1"])
                    elif leg["leg"] == "TP2":
                        self.assertGreaterEqual(float(exit_candle["High"]), example["levels"]["target_2"])
                    else:
                        self.assertEqual(leg["leg"], "TIME")

    def test_r_cost_and_slippage_calculations_are_correct(self):
        for example in self.examples:
            with self.subTest(example=example["id"]):
                if not example["actual_entry_date"]:
                    self.assertIsNone(example["final_r_result"])
                    self.assertEqual(example["total_pnl_gbp"], 0)
                    continue
                sizing = example["position_sizing"]
                legs = example["exit_legs"]
                maximum_risk = sizing["risk_per_share"] * sizing["position_size_shares"]
                total_pnl = sum(leg["pnl"] for leg in legs)
                total_exit_cost = sum(leg["exit_transaction_cost"] for leg in legs)
                total_exit_slippage = sum(leg["slippage_amount_gbp"] for leg in legs)
                self.assertAlmostEqual(maximum_risk, sizing["maximum_monetary_risk_gbp"], delta=1e-6)
                self.assertAlmostEqual(total_pnl, example["total_pnl_gbp"], places=6)
                self.assertAlmostEqual(total_pnl / maximum_risk, example["final_r_result"], places=6)
                self.assertAlmostEqual(
                    example["costs_and_slippage"]["entry_transaction_cost_gbp"] + total_exit_cost,
                    example["costs_and_slippage"]["total_transaction_cost_gbp"],
                    places=6,
                )
                self.assertAlmostEqual(
                    example["costs_and_slippage"]["entry_slippage_gbp"] + total_exit_slippage,
                    example["costs_and_slippage"]["total_slippage_gbp"],
                    places=6,
                )

    def test_rejected_and_expired_signals_were_never_entered(self):
        for category in ("REJECTED", "EXPIRED"):
            selected = [example for example in self.examples if example["category"] == category]
            self.assertEqual(len(selected), 5)
            for example in selected:
                with self.subTest(example=example["id"]):
                    self.assertIsNone(example["actual_entry_date"])
                    self.assertIsNone(example["actual_entry_price"])
                    self.assertEqual(example["holding_period_candles"], 0)
                    self.assertEqual(example["exit_legs"], [])
                    self.assertIsNone(example["final_r_result"])
                    self.assertTrue(example["rejection_or_expiry_reason"])
                    if category == "EXPIRED":
                        data = self.histories[example["ticker"]]
                        signal_index = data.index.get_loc(pd.Timestamp(example["signal_date"]))
                        level = example["levels"]["proposed_pullback_entry"]
                        next_three = data.iloc[signal_index + 1:signal_index + 4]
                        self.assertEqual(len(next_three), 3)
                        self.assertFalse(((next_three["Low"] <= level) & (next_three["High"] >= level)).any())

    def test_signal_analysis_uses_no_lookahead_data(self):
        benchmark = self.histories["SPY"]
        for example in self.examples:
            with self.subTest(example=example["id"]):
                data = self.histories[example["ticker"]]
                signal_date = pd.Timestamp(example["signal_date"])
                signal_history = data.loc[:signal_date]
                benchmark_history = benchmark.loc[:signal_date]
                self.assertEqual(signal_history.index[-1].isoformat(), example["data_timestamp"])
                self.assertEqual(example["analysis_input"]["end"], example["data_timestamp"])
                self.assertEqual(example["analysis_input"]["rows"], len(signal_history))
                self.assertFalse(example["analysis_input"]["later_candles_supplied"])
                close = pd.to_numeric(signal_history["Close"], errors="coerce")
                ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
                ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
                atr = float(add_atr(signal_history)["ATR"].iloc[-1])
                swing_low = float(signal_history.tail(20)["Low"].min())
                self.assertAlmostEqual(ema20, example["levels"]["ema20"], places=6)
                self.assertAlmostEqual(ema50, example["levels"]["ema50"], places=6)
                self.assertAlmostEqual(atr, example["levels"]["atr"], places=6)
                self.assertAlmostEqual(swing_low, example["levels"]["swing_low_20"], places=6)
                analysis = calculate_institutional_analysis(signal_history, benchmark_history)
                self.assertEqual(analysis["overall_score"], example["confidence"])
                self.assertEqual(analysis["recommendation"], example["recommendation"])
                self.assertEqual(
                    analysis["engines"]["market_regime"]["score"],
                    example["market_regime"]["engine_score"],
                )


if __name__ == "__main__":
    unittest.main()
