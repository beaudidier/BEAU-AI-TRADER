from __future__ import annotations

import unittest

from forward_validation.health import (
    classify_data_error,
    health_summary,
    insufficient_history_outcome,
)


class ForwardValidationHealthTests(unittest.TestCase):
    def test_one_hundred_percent_completion_is_healthy(self):
        result = health_summary(503, 503, eligible_symbols=503)
        self.assertEqual(result["health"], "healthy")
        self.assertEqual(result["completion_percentage"], 100.0)

    def test_ninety_nine_percent_with_history_exclusions_is_healthy(self):
        result = health_summary(
            503,
            500,
            eligible_symbols=500,
            excluded_symbols=3,
        )
        self.assertEqual(result["health"], "healthy")
        self.assertEqual(result["completion_percentage"], 99.4)
        self.assertEqual(result["intentionally_excluded_symbols"], 3)

    def test_ninety_four_percent_completion_is_degraded(self):
        result = health_summary(100, 94)
        self.assertEqual(result["health"], "degraded")

    def test_below_ninety_percent_completion_is_failed(self):
        result = health_summary(100, 89)
        self.assertEqual(result["health"], "failed")

    def test_genuine_provider_failure_has_explicit_outcome(self):
        outcome = classify_data_error(RuntimeError("provider connection failed"))
        self.assertEqual(outcome["status"], "provider_failure")
        result = health_summary(100, 99, genuine_failures=1)
        self.assertEqual(result["health"], "healthy")
        self.assertEqual(result["genuine_failures"], 1)

    def test_mixed_exclusions_and_failures_remain_separate(self):
        exclusion = insufficient_history_outcome(120)
        failure = classify_data_error("Stale market data: expected latest session.")
        result = health_summary(
            100,
            94,
            eligible_symbols=94,
            excluded_symbols=3,
            genuine_failures=3,
        )
        self.assertEqual(exclusion["status"], "insufficient_history")
        self.assertEqual(failure["status"], "stale_data")
        self.assertEqual(result["intentionally_excluded_symbols"], 3)
        self.assertEqual(result["genuine_failures"], 3)
        self.assertEqual(result["health"], "degraded")

    def test_every_data_failure_category_is_stable(self):
        cases = {
            "invalid_symbol": "No completed daily history was returned.",
            "provider_failure": "Provider connection failed.",
            "timeout": "Market-data request exceeded 30 seconds.",
            "stale_data": "Stale market data: latest candle is too old.",
            "incomplete_data": "Required OHLCV fields are missing: Volume.",
        }
        for expected, message in cases.items():
            with self.subTest(expected=expected):
                self.assertEqual(classify_data_error(message)["status"], expected)


if __name__ == "__main__":
    unittest.main()
