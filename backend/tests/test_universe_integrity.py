from __future__ import annotations

import unittest
from unittest.mock import patch

from api import get_universe_health, list_universe_health
from universe.stock_universe import (
    ALL_US,
    DOW30,
    NASDAQ100,
    SP500,
    StockUniverseProvider,
    normalize_stock_symbol,
)
from universe.universe_registry import ScanJob, ScanJobRegistry
from universe.update_constituents import parse_table, parse_us_listings


class UniverseIntegrityTests(unittest.TestCase):
    def test_universe_health_endpoints_return_snapshot_status(self):
        all_health = list_universe_health("stocks")
        self.assertEqual(len(all_health["universes"]), 5)
        sp500 = get_universe_health("stocks", "sp500")
        self.assertEqual(sp500["expected_count"], 503)
        self.assertIn(sp500["health_status"], {"healthy", "degraded"})

    def test_complete_expected_constituent_counts(self):
        self.assertEqual(len(DOW30), 30)
        self.assertEqual(len(NASDAQ100), 103)
        self.assertEqual(len(SP500), 503)
        self.assertEqual(len(ALL_US), 5605)

    def test_snapshots_have_no_duplicates_invalid_or_missing_symbols(self):
        provider = StockUniverseProvider()
        for universe in ("demo", "dow30", "nasdaq100", "sp500", "all_us"):
            health = provider.health(universe)
            self.assertEqual(health["actual_count"], health["expected_count"])
            self.assertEqual(health["duplicates"], [])
            self.assertEqual(health["invalid_tickers"], [])
            self.assertEqual(health["delisted_or_stale_tickers"], [])
            self.assertEqual(health["missing_tickers"], [])

    def test_ticker_normalization_and_custom_deduplication(self):
        self.assertEqual(normalize_stock_symbol(" brk.b "), "BRK-B")
        self.assertEqual(normalize_stock_symbol("BF/B"), "BF-B")
        provider = StockUniverseProvider()
        self.assertEqual(
            provider.symbols("custom", ["brk.b", "BRK-B", " bf/b ", ""]),
            ["BRK-B", "BF-B"],
        )

    def test_committed_snapshot_is_deterministic(self):
        first = StockUniverseProvider()
        second = StockUniverseProvider()
        for universe in ("demo", "dow30", "nasdaq100", "sp500", "all_us"):
            self.assertEqual(first.symbols(universe), second.symbols(universe))
            self.assertEqual(
                first.health(universe)["snapshot_sha256"],
                second.health(universe)["snapshot_sha256"],
            )

    @patch("universe.universe_registry._scan_symbol")
    def test_provider_failure_is_explicit_in_job_and_universe_health(self, scan_symbol):
        scan_symbol.side_effect = lambda symbol: (
            (_ for _ in ()).throw(ValueError("No usable market history"))
            if symbol == "AMD"
            else {"ticker": symbol, "score": 80}
        )
        provider = StockUniverseProvider()
        registry = ScanJobRegistry(batch_size=2, concurrency_limit=1, retries=0)
        job = ScanJob(
            job_id="health-job",
            market="stocks",
            universe="demo",
            symbols=["NVDA", "AMD"],
        )
        with patch.dict(
            "universe.universe_registry.PROVIDERS", {"stocks": provider}, clear=False
        ):
            registry._run(job, "health")
        self.assertEqual(job.failures, ["AMD"])
        self.assertEqual(job.failure_reasons["AMD"], "No usable market history")
        health = provider.health("demo")
        self.assertEqual(health["failed_count"], 1)
        self.assertEqual(health["failed_symbols"], ["AMD"])
        self.assertEqual(health["health_status"], "degraded")

    def test_update_parsers_are_deterministic_and_do_not_misclassify_united(self):
        html = """
        <table id="constituents">
          <tr><th>Symbol</th><th>Company</th><th>Sector</th></tr>
          <tr><td>BRK.B</td><td>Berkshire</td><td>Financials</td></tr>
        </table>
        """
        self.assertEqual(parse_table(html, "constituents"), parse_table(html, "constituents"))
        nasdaq = (
            "Symbol|Security Name|Market Category|Test Issue|Financial Status|"
            "Round Lot Size|ETF|NextShares\n"
            "UAL|United Airlines Holdings, Inc. - Common Stock|Q|N|N|100|N|N\n"
            "TESTW|Example Warrant|S|N|N|100|N|N\n"
            "File Creation Time: 0724202621:31|||||||\n"
        )
        other = (
            "ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
            "Test Issue|NASDAQ Symbol\n"
            "BRK.B|Berkshire Hathaway Class B Common Stock|N|BRK.B|N|100|N|BRK.B\n"
            "File Creation Time: 0724202621:31||||||\n"
        )
        rows, diagnostics = parse_us_listings(nasdaq, other)
        self.assertEqual([row["symbol"] for row in rows], ["BRK-B", "UAL"])
        self.assertIn("TESTW", diagnostics["invalid_or_unsupported_source_rows"])


if __name__ == "__main__":
    unittest.main()
