from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import pandas as pd

from forward_validation.latest_signal_evidence import (
    ARTIFACT_PATH,
    PUBLIC_SUMMARY_PATH,
    REPLAY_PATH,
    ROOT,
    generate_latest_signal_evidence,
)


class LatestSignalEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.summary = generate_latest_signal_evidence()
        cls.replay = json.loads(REPLAY_PATH.read_text(encoding="utf-8"))

    def test_every_latest_replay_signal_is_audited_once(self):
        replay_tickers = sorted(
            item["ticker"]
            for item in self.replay["results"]
            if item["status"] == "signal"
        )
        audited_tickers = sorted(item["ticker"] for item in self.summary["signals"])
        self.assertEqual(len(audited_tickers), 12)
        self.assertEqual(audited_tickers, replay_tickers)
        self.assertEqual(len(audited_tickers), len(set(audited_tickers)))

    def test_all_validation_checks_pass(self):
        self.assertTrue(self.summary["all_checks_passed"])
        self.assertEqual(self.summary["missing_raw_data"], [])
        self.assertEqual(self.summary["mismatches"], [])
        self.assertEqual(self.summary["duplicate_signals"], [])
        for signal in self.summary["signals"]:
            self.assertTrue(all(signal["checks"].values()), signal["ticker"])
            self.assertLessEqual(signal["risk_percent"], 5)

    def test_raw_candles_match_signal_and_indicator_ledger(self):
        for signal in self.summary["signals"]:
            history = pd.read_csv(
                ROOT / signal["raw_ohlcv"]["file"],
                index_col=0,
                parse_dates=True,
            )
            history = history.loc[
                history.index <= pd.Timestamp(signal["signal_date"])
            ]
            close = pd.to_numeric(history["Close"], errors="raise")
            with self.subTest(ticker=signal["ticker"]):
                self.assertEqual(
                    history.index[-1].date().isoformat(), signal["signal_date"]
                )
                self.assertAlmostEqual(
                    float(close.iloc[-1]), signal["signal_price"], places=5
                )
                self.assertAlmostEqual(
                    float(close.ewm(span=20, adjust=False).mean().iloc[-1]),
                    signal["levels"]["ema20"],
                    places=5,
                )
                self.assertAlmostEqual(
                    float(close.ewm(span=50, adjust=False).mean().iloc[-1]),
                    signal["levels"]["ema50"],
                    places=5,
                )
                self.assertAlmostEqual(
                    float(
                        pd.to_numeric(history["Low"], errors="raise")
                        .tail(20)
                        .min()
                    ),
                    signal["levels"]["swing_low"],
                    places=5,
                )

    def test_chart_values_match_the_audit_ledger(self):
        for signal in self.summary["signals"]:
            chart_path = ROOT / signal["chart"]["file"]
            svg = chart_path.read_text(encoding="utf-8")
            with self.subTest(ticker=signal["ticker"]):
                self.assertIn(signal["ticker"], svg)
                self.assertIn(
                    f'Regime score {signal["market_regime_score"]:.0f}', svg
                )
                for name, value in signal["chart"]["values"].items():
                    match = re.search(
                        rf'data-{re.escape(name)}="([^"]+)"', svg
                    )
                    self.assertIsNotNone(match, name)
                    self.assertEqual(match.group(1), str(value))

    def test_public_payload_matches_audit_artifact(self):
        artifact = json.loads(ARTIFACT_PATH.read_text(encoding="utf-8"))
        public = json.loads(PUBLIC_SUMMARY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(public, artifact)
        self.assertEqual(public, self.summary)


if __name__ == "__main__":
    unittest.main()
