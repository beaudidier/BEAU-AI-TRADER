import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException, Response
from pydantic import ValidationError

from saas.invites import (
    BetaInviteCreate,
    create_beta_invite,
    _serialize_invite,
    hash_invite_token,
    _require_admin,
)
from saas.auth import CurrentUser


ROOT = Path(__file__).resolve().parents[2]
MIGRATION = (
    ROOT
    / "supabase"
    / "migrations"
    / "202607250015_invite_only_beta_registration.sql"
)
EDGE_FUNCTION = (
    ROOT
    / "supabase"
    / "functions"
    / "invite-register"
    / "index.ts"
)
INVITE_PAGE = (
    ROOT
    / "frontend"
    / "src"
    / "pages"
    / "auth"
    / "InviteRegistrationPage.tsx"
)
INVITE_SERVICE = (
    ROOT
    / "frontend"
    / "src"
    / "services"
    / "inviteRegistration.ts"
)


class InviteRegistrationTests(unittest.TestCase):
    def test_invite_token_hash_is_deterministic_and_one_way_storage_shape(self):
        token = "private-invite-token-value-with-enough-entropy"
        digest = hash_invite_token(token)
        self.assertEqual(digest, hash_invite_token(token))
        self.assertEqual(len(digest), 64)
        self.assertNotIn(token, digest)

    def test_invite_limits_are_bounded(self):
        invite = BetaInviteCreate(
            expires_in_days=7,
            max_uses=1,
            label="Professional trader beta",
        )
        self.assertEqual(invite.max_uses, 1)
        with self.assertRaises(ValidationError):
            BetaInviteCreate(expires_in_days=0)
        with self.assertRaises(ValidationError):
            BetaInviteCreate(max_uses=101)

    def test_owner_creation_returns_clear_token_once_but_stores_only_hash(self):
        inserted = []
        now = datetime.now(timezone.utc)

        class InsertQuery:
            def table(self, _name):
                return self

            def insert(self, values):
                inserted.append(values)
                return self

            def execute(self):
                values = inserted[0]
                return SimpleNamespace(
                    data=[
                        {
                            "id": "invite-1",
                            "status": "active",
                            "created_at": now.isoformat(),
                            "expires_at": values["expires_at"],
                            "max_uses": values["max_uses"],
                            "use_count": 0,
                            "label": values["label"],
                        }
                    ]
                )

        user = CurrentUser("owner-1", "owner@example.com", "token")
        with (
            patch(
                "saas.invites._require_admin",
                return_value=InsertQuery(),
            ),
            patch(
                "saas.invites.secrets.token_urlsafe",
                return_value="clear-private-token",
            ),
            patch(
                "saas.invites.get_settings",
                return_value=SimpleNamespace(
                    frontend_app_url="https://app.example"
                ),
            ),
        ):
            result = create_beta_invite(
                BetaInviteCreate(
                    expires_in_days=7,
                    max_uses=1,
                    label="Professional trader beta",
                ),
                Response(),
                user,
            )
        self.assertEqual(
            result["invite_url"],
            "https://app.example/invite/clear-private-token",
        )
        self.assertNotIn("clear-private-token", str(inserted[0]))
        self.assertEqual(
            inserted[0]["token_hash"],
            hash_invite_token("clear-private-token"),
        )

    def test_non_admin_cannot_manage_invites(self):
        class MembershipQuery:
            def table(self, _name):
                return self

            def select(self, _columns):
                return self

            def eq(self, _field, _value):
                return self

            def maybe_single(self):
                return self

            def execute(self):
                return SimpleNamespace(
                    data={"role": "TESTER", "active": True}
                )

        user = CurrentUser("tester-1", "tester@example.com", "token")
        with (
            patch(
                "saas.invites.get_user_client",
                return_value=MembershipQuery(),
            ),
            self.assertRaises(HTTPException) as error,
        ):
            _require_admin(user)
        self.assertEqual(error.exception.status_code, 403)

    def test_expired_invite_is_serialized_as_expired(self):
        now = datetime.now(timezone.utc)
        result = _serialize_invite(
            {
                "id": "invite-1",
                "status": "active",
                "created_at": (now - timedelta(days=2)).isoformat(),
                "expires_at": (now - timedelta(days=1)).isoformat(),
                "max_uses": 2,
                "use_count": 1,
                "label": None,
            }
        )
        self.assertEqual(result["status"], "expired")
        self.assertEqual(result["remaining_uses"], 1)

    def test_migration_serializes_consumption_and_restricts_rpc(self):
        sql = MIGRATION.read_text()
        self.assertIn("token_hash text not null unique", sql)
        self.assertIn("for update", sql.lower())
        self.assertIn("use_count = next_use_count", sql)
        self.assertIn("beta_invite_uses", sql)
        self.assertIn(
            "revoke all on function public.consume_beta_invite",
            sql,
        )
        self.assertIn(
            "grant execute on function public.consume_beta_invite"
            "(text, uuid) to service_role",
            sql,
        )

    def test_registration_service_uses_admin_invite_and_cleans_up(self):
        source = EDGE_FUNCTION.read_text()
        self.assertIn('/auth/v1/invite', source)
        self.assertIn('method: "PUT"', source)
        self.assertIn("JSON.stringify({ password })", source)
        self.assertIn("consume_beta_invite", source)
        self.assertIn('method: "DELETE"', source)
        self.assertNotIn('/auth/v1/resend', source)
        self.assertNotIn("console.log", source)

    def test_resend_is_scoped_to_consumed_invite_user_and_rate_limited(self):
        source = EDGE_FUNCTION.read_text()
        self.assertIn("beta_invite_uses", source)
        self.assertIn("/auth/v1/admin/users/${userId}", source)
        self.assertIn("invitedUser.email.toLowerCase() !== email", source)
        self.assertIn("/auth/v1/otp", source)
        self.assertIn("create_user: false", source)
        self.assertIn("cooldown_seconds: 60", source)
        self.assertIn("over_email_send_rate_limit", source)
        self.assertIn("over_request_rate_limit", source)

    def test_frontend_prevents_duplicates_and_explains_verification_cooldown(self):
        page = INVITE_PAGE.read_text()
        service = INVITE_SERVICE.read_text()
        self.assertIn("requestInFlight.current", page)
        self.assertIn("EMAIL_COOLDOWN_KEY", page)
        self.assertIn("Check your inbox and spam folder", page)
        self.assertIn("Resend verification", page)
        self.assertIn("registrationRequest", service)
        self.assertIn("resendRequest", service)
        self.assertIn("email_rate_limited", service)
        self.assertIn("Sign in or request another verification email", service)

    def test_public_registration_remains_disabled(self):
        config = (ROOT / "supabase" / "config.toml").read_text()
        app = (ROOT / "frontend" / "src" / "App.tsx").read_text()
        self.assertIn("[auth]", config)
        self.assertIn("enable_signup = false", config)
        self.assertIn("enable_confirmations = true", config)
        self.assertIn(
            'path="/register" element={<Navigate to="/login" replace />}',
            app,
        )
        self.assertIn('path="/invite/:token"', app)

    def test_invite_paths_are_redacted_from_frontend_monitoring(self):
        source = (
            ROOT
            / "frontend"
            / "src"
            / "components"
            / "FrontendMonitoring.tsx"
        ).read_text()
        self.assertIn("[REDACTED]", source)
        self.assertIn("safePath(window.location.pathname)", source)


if __name__ == "__main__":
    unittest.main()
