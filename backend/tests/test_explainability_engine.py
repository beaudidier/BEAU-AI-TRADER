import unittest

from engines.explainability_engine import build_explanation


class ExplainabilityEngineTests(unittest.TestCase):
    def test_explanation_is_complete_and_uses_underlying_values(self):
        explanation = build_explanation(
            82,
            engines={
                "trend": {"score": 90, "explanation": "Price is above all major EMAs."},
                "volume": {"score": 42, "explanation": "Relative volume is below its baseline."},
            },
            support=95,
            resistance=112,
            plan={"current_price": 100, "stop_loss": 94, "target_1": 112, "risk_reward_target_1": 2},
        )
        self.assertEqual(explanation["verdict"], "BUY")
        self.assertIn("82/100", explanation["summary"])
        self.assertTrue(explanation["strengths"])
        self.assertTrue(explanation["weaknesses"])
        self.assertIn("$95.00", explanation["invalidation"])
        self.assertIn("8 more points", explanation["next_trigger"])


if __name__ == "__main__":
    unittest.main()
