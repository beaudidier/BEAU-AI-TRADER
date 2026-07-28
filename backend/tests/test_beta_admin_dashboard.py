import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException

from saas.admin import (
    AccountUpdate,
    FeedbackUpdate,
    RetryRequest,
    require_admin,
    retry_failed_job,
    update_beta_account,
    update_feedback,
)
from saas.auth import CurrentUser


class Query:
    def __init__(self, rows=None):
        self.rows = list(rows or [])
        self.inserted = []
        self.updated = []
        self.filters = []

    def table(self, _name): return self
    def select(self, _columns): return self
    def maybe_single(self): return self
    def eq(self, key, value): self.filters.append((key, value)); return self
    def insert(self, values): self.inserted.append(values); return self
    def update(self, values): self.updated.append(values); return self
    def execute(self):
        value = self.rows.pop(0) if self.rows else {}
        return SimpleNamespace(data=value)


class BetaAdminTests(unittest.TestCase):
    def setUp(self):
        self.owner = CurrentUser("owner-1", "owner@example.com", "token")
        self.tester = CurrentUser("tester-1", "tester@example.com", "token")

    def test_non_admin_is_blocked(self):
        client = Query([{"role": "TESTER", "active": True}])
        with patch("saas.admin.get_user_client", return_value=client):
            with self.assertRaises(HTTPException) as raised:
                require_admin(self.tester)
        self.assertEqual(raised.exception.status_code, 403)

    def test_active_admin_has_access(self):
        client = Query([{"role": "ADMIN", "active": True}])
        with patch("saas.admin.get_user_client", return_value=client):
            self.assertIs(require_admin(self.owner), client)

    def test_feedback_status_update_is_audited(self):
        client = Query([
            {"id": "feedback-1", "status": "resolved"},
            {"id": "audit-1"},
        ])
        with (
            patch("saas.admin.get_user_client", return_value=client),
            patch("saas.admin.require_admin", return_value=client),
        ):
            result = update_feedback(
                "feedback-1",
                FeedbackUpdate(status="resolved", owner_notes="Verified"),
                self.owner,
            )
        self.assertEqual(result["status"], "resolved")
        self.assertTrue(any(row.get("action") == "feedback.status_updated" for row in client.inserted))

    def test_user_isolation_prevents_disabling_owner(self):
        client = Query()
        with patch("saas.admin.require_admin", return_value=client):
            with self.assertRaises(HTTPException) as raised:
                update_beta_account(self.owner.id, AccountUpdate(active=False), self.owner)
        self.assertEqual(raised.exception.status_code, 409)

    def test_only_non_destructive_failed_jobs_are_retryable(self):
        client = Query([
            {"id": "event-1", "event_type": "failed_auth"},
        ])
        with patch("saas.admin.require_admin", return_value=client):
            with self.assertRaises(HTTPException) as raised:
                retry_failed_job(RetryRequest(event_id="event-1"), self.owner)
        self.assertEqual(raised.exception.status_code, 422)

    def test_mobile_layout_and_filters_are_present(self):
        source = (
            __import__("pathlib").Path(__file__).parents[2]
            / "frontend/src/pages/AdminDashboardPage.tsx"
        ).read_text()
        self.assertIn("overflow-x-auto", source)
        self.assertIn("sm:p-8", source)
        self.assertIn("feedback_status", (
            __import__("pathlib").Path(__file__).parents[2]
            / "frontend/src/services/adminApi.ts"
        ).read_text())


if __name__ == "__main__":
    unittest.main()
