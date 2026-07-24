import unittest

from decision_rules import recommendation_for_score


class DecisionRulesTests(unittest.TestCase):
    def test_confidence_boundaries_use_the_canonical_recommendations(self):
        cases = {
            0: "SKIP", 59: "SKIP", 60: "WATCH", 74: "WATCH",
            75: "BUY", 89: "BUY", 90: "STRONG BUY", 100: "STRONG BUY",
        }
        for score, expected in cases.items():
            with self.subTest(score=score):
                self.assertEqual(recommendation_for_score(score), expected)

    def test_invalid_scores_fail_closed_to_skip(self):
        self.assertEqual(recommendation_for_score(float("nan")), "SKIP")
        self.assertEqual(recommendation_for_score("not-a-score"), "SKIP")


if __name__ == "__main__":
    unittest.main()
