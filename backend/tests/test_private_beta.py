import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from pydantic import ValidationError

import monitoring
from saas.auth import CurrentUser, _require_private_beta_access
from saas.router import (
    BetaFeedbackCreate,
    ProfessionalSignalReviewCreate,
    build_private_beta_readiness,
    create_beta_feedback,
    list_beta_feedback,
)


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607250014_professional_trader_private_beta.sql"
)


class _MembershipQuery:
    def __init__(self, active):
        self.active = active

    def table(self, _name):
        return self

    def select(self, _columns):
        return self

    def eq(self, _field, _value):
        return self

    def maybe_single(self):
        return self

    def execute(self):
        return SimpleNamespace(data={"active": True} if self.active else None)


class PrivateBetaTests(unittest.TestCase):
    def test_feedback_schema_accepts_only_structured_categories(self):
        payload = BetaFeedbackCreate(
            page="Trade Workspace",
            ticker="NVDA",
            category="risk",
            severity="high",
            message="The total risk needs clearer visual hierarchy.",
        )
        self.assertEqual(payload.category, "risk")
        with self.assertRaises(ValidationError):
            BetaFeedbackCreate(
                page="Workspace",
                category="other",
                severity="high",
                message="This category is not supported.",
            )

    def test_professional_review_confidence_is_bounded(self):
        values = {
            "ticker": "NVDA",
            "would_take_setup": True,
            "entry_logical": True,
            "stop_structurally_correct": True,
            "targets_realistic": True,
            "relevant_context_missing": False,
            "market_regime_makes_sense": True,
            "setup_confidence": 8,
        }
        self.assertEqual(
            ProfessionalSignalReviewCreate(**values).setup_confidence,
            8,
        )
        with self.assertRaises(ValidationError):
            ProfessionalSignalReviewCreate(
                **{**values, "setup_confidence": 11}
            )

    def test_private_beta_membership_is_enforced_when_enabled(self):
        user = CurrentUser("user-1", "tester@example.com", "token")
        settings = SimpleNamespace(private_beta_enforced=True)
        with (
            patch("saas.auth.get_settings", return_value=settings),
            patch(
                "saas.auth._supabase_client",
                return_value=_MembershipQuery(False),
            ),
            self.assertRaises(HTTPException) as error,
        ):
            _require_private_beta_access(user)
        self.assertEqual(error.exception.status_code, 403)

        with (
            patch("saas.auth.get_settings", return_value=settings),
            patch(
                "saas.auth._supabase_client",
                return_value=_MembershipQuery(True),
            ),
        ):
            _require_private_beta_access(user)

    def test_migration_provisions_owner_and_secures_beta_records(self):
        sql = MIGRATION.read_text()
        self.assertIn("order by created_at", sql)
        self.assertIn("'OWNER'", sql)
        self.assertIn("beta_feedback enable row level security", sql)
        self.assertIn(
            "professional_signal_reviews enable row level security",
            sql,
        )
        self.assertIn("beta_monitoring_events", sql)
        self.assertIn("public.is_private_beta_admin()", sql)

    def test_monitoring_is_best_effort_and_sanitized(self):
        inserted = []

        class Query:
            def table(self, _name):
                return self

            def insert(self, values):
                inserted.append(values)
                return self

            def execute(self):
                return SimpleNamespace(data=inserted)

        settings = SimpleNamespace(
            supabase_url="https://project.invalid",
            supabase_service_role_key="secret-value",
        )
        with (
            patch("monitoring.get_settings", return_value=settings),
            patch("monitoring.create_client", return_value=Query()),
        ):
            self.assertTrue(
                monitoring.record_monitoring_event(
                    "backend_error",
                    "x" * 1500,
                    path="/trade-plan/NVDA",
                    status_code=500,
                )
            )
        self.assertEqual(len(inserted[0]["message"]), 1000)
        self.assertNotIn("secret-value", str(inserted[0]))

    def test_monitoring_redacts_common_credential_shapes(self):
        message = (
            "Bearer secret-token "
            "access_token=query-secret "
            "sb_secret_example123 "
            "eyJaaaaaaaaaa.bbbbbbbbbb.cccccccccc"
        )
        sanitized = monitoring.sanitize_monitoring_text(message)
        self.assertNotIn("secret-token", sanitized)
        self.assertNotIn("query-secret", sanitized)
        self.assertNotIn("sb_secret_example123", sanitized)
        self.assertNotIn("eyJaaaaaaaaaa", sanitized)
        self.assertEqual(sanitized.count("[REDACTED]"), 4)
        self.assertEqual(
            monitoring.sanitize_monitoring_path(
                "/invite/private-token-value"
            ),
            "/invite/[REDACTED]",
        )

    def test_scheduler_failure_monitor_is_wired(self):
        workflow = (
            ROOT / ".github" / "workflows" / "forward-validation.yml"
        ).read_text()
        self.assertIn("if: failure()", workflow)
        self.assertIn("python -m monitoring scheduler-failure", workflow)

    def test_private_beta_readiness_reports_partial_scan_and_scheduler_delay(self):
        result = build_private_beta_readiness(
            {
                "health": "failed",
                "next_scheduled_run": "2026-07-27T22:30:00+00:00",
                "last_run": {
                    "completed_at": "2026-07-25T22:45:00+00:00",
                    "last_complete_market_date": "2026-07-24",
                    "completion_percentage": 89.5,
                    "provider_health": "failed",
                    "genuine_failures": {
                        "ABC": {"status": "timeout"},
                        "XYZ": {"status": "provider_failure"},
                    },
                },
                "latest_replay": None,
            }
        )
        self.assertEqual(result["system_status"], "degraded")
        self.assertEqual(result["scheduler_health"], "delayed")
        self.assertTrue(result["partial_scan"])
        self.assertEqual(result["failed_symbol_count"], 2)
        self.assertEqual(result["latest_complete_market_date"], "2026-07-24")

    def test_owner_can_list_all_feedback_while_tester_is_scoped(self):
        class FeedbackQuery:
            def __init__(self):
                self.eq_calls = []

            def table(self, _name):
                return self

            def select(self, _columns):
                return self

            def order(self, _column, desc=False):
                return self

            def limit(self, _value):
                return self

            def eq(self, field, value):
                self.eq_calls.append((field, value))
                return self

            def execute(self):
                return SimpleNamespace(data=[{"id": "feedback-1"}])

        user = CurrentUser("user-1", "tester@example.com", "token")
        owner_query = FeedbackQuery()
        with (
            patch("saas.router._client", return_value=owner_query),
            patch(
                "saas.router._private_beta_membership",
                return_value={"role": "OWNER", "active": True},
            ),
        ):
            self.assertEqual(list_beta_feedback(user), [{"id": "feedback-1"}])
        self.assertEqual(owner_query.eq_calls, [])

        tester_query = FeedbackQuery()
        with (
            patch("saas.router._client", return_value=tester_query),
            patch(
                "saas.router._private_beta_membership",
                return_value={"role": "TESTER", "active": True},
            ),
        ):
            self.assertEqual(list_beta_feedback(user), [{"id": "feedback-1"}])
        self.assertEqual(tester_query.eq_calls, [("user_id", "user-1")])

    def test_feedback_is_stored_for_the_authenticated_tester(self):
        inserted = []

        class InsertQuery:
            def table(self, _name):
                return self

            def insert(self, values):
                inserted.append(values)
                return self

            def execute(self):
                return SimpleNamespace(data=[{"id": "feedback-1", **inserted[0]}])

        user = CurrentUser("tester-1", "tester@example.com", "token")
        payload = BetaFeedbackCreate(
            page="  Trade Workspace  ",
            ticker="nvda",
            category="data quality",
            severity="high",
            message="  The latest price timestamp needs review.  ",
        )
        with patch("saas.router._client", return_value=InsertQuery()):
            result = create_beta_feedback(payload, user)
        self.assertEqual(result["user_id"], "tester-1")
        self.assertEqual(result["page"], "Trade Workspace")
        self.assertEqual(result["ticker"], "NVDA")
        self.assertEqual(
            result["message"],
            "The latest price timestamp needs review.",
        )


if __name__ == "__main__":
    unittest.main()
