import unittest

from scripts.production_smoke import _check, _expect_json


class ProductionSmokeTests(unittest.TestCase):
    def test_json_check_accepts_expected_shape(self):
        result = _check(
            "backend:health",
            lambda: (
                200,
                {"content-type": "application/json"},
                b'{"status":"running"}',
            ),
            _expect_json(
                200,
                lambda payload: payload.get("status") == "running",
                "Backend is running.",
            ),
            attempts=1,
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.status, 200)

    def test_json_check_fails_without_exposing_response_details(self):
        result = _check(
            "feedback:auth-guard",
            lambda: (
                500,
                {"content-type": "application/json"},
                b'{"detail":"internal"}',
            ),
            _expect_json(
                401,
                lambda payload: bool(payload.get("detail")),
                "Protected.",
            ),
            attempts=1,
        )
        self.assertFalse(result.ok)
        self.assertEqual(
            result.message,
            "Expected status 401, received 500.",
        )

    def test_workflow_runs_on_main_and_before_monday(self):
        workflow = (
            __import__("pathlib").Path(__file__).resolve().parents[2]
            / ".github"
            / "workflows"
            / "production-smoke.yml"
        ).read_text()
        self.assertIn('cron: "0 20 * * 0"', workflow)
        self.assertIn("branches:", workflow)
        self.assertIn("- main", workflow)
        self.assertNotIn("secrets.", workflow)


if __name__ == "__main__":
    unittest.main()
