from __future__ import annotations

import unittest

from forward_validation.setup_clarity import (
    distance_to_entry_percent,
    sector_concentration,
    setup_clarity,
    setup_status_from_outcome,
)


def signal(ticker: str = "TEST", sector: str = "Technology"):
    return {
        "ticker": ticker,
        "sector": sector,
        "signal_price": 110.0,
        "proposed_pullback_entry": 100.0,
        "stop_loss": 95.0,
        "expiry_date": "2026-07-30",
        "data_timestamp": "2026-07-25T00:00:00",
    }


class SetupStatusTests(unittest.TestCase):
    def test_waiting_setup_is_not_actionable_at_market(self):
        result = setup_clarity(signal(), {"status": "waiting_for_entry"})
        self.assertEqual(result["status"], "waiting_for_entry")
        self.assertEqual(result["instruction"], "Do not buy at market")
        self.assertFalse(result["actionable_at_market"])
        self.assertEqual(result["expiry_date"], "2026-07-30")

    def test_triggered_entry_keeps_original_plan(self):
        original = signal()
        result = setup_clarity(
            original,
            {"status": "entered", "current_price": 102.0},
        )
        self.assertEqual(result["status"], "entry_triggered")
        self.assertEqual(result["planned_entry"], original["proposed_pullback_entry"])
        self.assertIn("$95.0000", result["invalidation"])

    def test_expired_setup_is_not_actionable(self):
        result = setup_clarity(signal(), {"status": "expired"})
        self.assertEqual(result["status"], "expired")
        self.assertEqual(result["instruction"], "Expired—do not enter")
        self.assertFalse(result["actionable_at_market"])

    def test_invalidated_setup_is_not_actionable(self):
        result = setup_clarity(
            signal(),
            {
                "status": "invalidated",
                "invalidation_reason": "The immutable market data is invalid.",
            },
        )
        self.assertEqual(result["status"], "invalidated")
        self.assertEqual(result["invalidation"], "The immutable market data is invalid.")
        self.assertFalse(result["actionable_at_market"])

    def test_completed_execution_has_completed_setup_status(self):
        self.assertEqual(setup_status_from_outcome("TP2_hit"), "completed")
        self.assertEqual(setup_status_from_outcome("stopped"), "completed")

    def test_distance_to_entry_is_signed_and_zero_safe(self):
        self.assertEqual(distance_to_entry_percent(105, 100), 5.0)
        self.assertEqual(distance_to_entry_percent(95, 100), -5.0)
        self.assertIsNone(distance_to_entry_percent(100, 0))


class SectorConcentrationTests(unittest.TestCase):
    def test_single_sector_warning_triggers_only_above_thirty_percent(self):
        at_threshold = [
            signal(str(index), "Technology" if index < 3 else f"Sector {index}")
            for index in range(10)
        ]
        over_threshold = [
            signal(str(index), "Technology" if index < 4 else f"Sector {index}")
            for index in range(10)
        ]
        self.assertFalse(
            sector_concentration(at_threshold)["dominant_sector_warning"]
        )
        self.assertTrue(
            sector_concentration(over_threshold)["dominant_sector_warning"]
        )

    def test_two_related_sector_warning_triggers_only_above_fifty_percent(self):
        at_threshold = [
            signal("U1", "Utilities"),
            signal("U2", "Utilities"),
            signal("R1", "Real Estate"),
            signal("R2", "Real Estate"),
            signal("T1", "Technology"),
            signal("T2", "Technology"),
            signal("H1", "Health Care"),
            signal("H2", "Health Care"),
        ]
        over_threshold = at_threshold[:5]
        self.assertFalse(
            sector_concentration(at_threshold)["related_sector_warning"]
        )
        self.assertTrue(
            sector_concentration(over_threshold)["related_sector_warning"]
        )


if __name__ == "__main__":
    unittest.main()
