import time
import unittest
from unittest.mock import patch

from universe.universe_registry import ScanJob, ScanJobRegistry, universe_symbols


class UniverseScanTests(unittest.TestCase):
    def test_demo_and_crypto_universes_are_separated(self):
        demo = universe_symbols("stocks", "demo")
        crypto = universe_symbols("crypto", "top50")
        self.assertEqual(len(demo), 10)
        self.assertEqual(len(crypto), 50)
        self.assertTrue(all(symbol.endswith("-USD") for symbol in crypto))
        self.assertFalse(set(demo) & set(crypto))

    @patch("universe.universe_registry._scan_symbol")
    def test_batch_scan_keeps_partial_results_and_progress(self, scan_symbol):
        scan_symbol.side_effect = lambda symbol: (_ for _ in ()).throw(ValueError("provider unavailable")) if symbol == "AMD" else {"ticker": symbol, "score": 80}
        registry = ScanJobRegistry(batch_size=2, concurrency_limit=2, retries=0)
        job = ScanJob(job_id="job", market="stocks", universe="custom", symbols=["NVDA", "AMD", "MSFT"])
        registry._run(job, "custom")
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.completed_symbols, 2)
        self.assertEqual(job.failed_symbols, 1)
        self.assertEqual(job.summary()["progress_percentage"], 100)
        self.assertEqual([item["ticker"] for item in job.results], ["NVDA", "MSFT"])

    def test_cached_scan_is_reused_without_new_provider_request(self):
        registry = ScanJobRegistry(cache_seconds=300)
        symbols = universe_symbols("stocks", "demo")
        key = f"stocks:demo:{','.join(symbols)}"
        registry.cache[key] = (time.monotonic(), [{"ticker": "NVDA", "score": 80}])
        job = registry.start("stocks", "demo")
        self.assertEqual(job.status, "completed")
        self.assertEqual(job.results[0]["ticker"], "NVDA")


if __name__ == "__main__":
    unittest.main()
