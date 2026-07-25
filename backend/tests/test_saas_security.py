import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from saas import auth
from saas.auth import get_current_user
from saas.entitlements import require_limit
from saas.router import _one


class SaaSSecurityTests(unittest.TestCase):
    def test_missing_access_token_is_rejected(self):
        with self.assertRaises(HTTPException) as error:
            get_current_user(None)
        self.assertEqual(error.exception.status_code, 401)

    def test_entitlement_limit_is_enforced(self):
        with self.assertRaises(HTTPException) as error:
            require_limit(1, 1, "Watchlist")
        self.assertEqual(error.exception.status_code, 403)

    def test_invalid_or_expired_token_is_rejected(self):
        original_jwt, original_settings = auth.jwt, auth.get_settings

        class FakeJwt:
            class PyJWTError(Exception): pass
            class InvalidTokenError(PyJWTError): pass
            @staticmethod
            def decode(*_args, **_kwargs): raise FakeJwt.InvalidTokenError("expired")

        auth.jwt = FakeJwt
        auth.get_settings = lambda: SimpleNamespace(supabase_jwt_secret="test-secret")
        try:
            with self.assertRaises(HTTPException) as error:
                get_current_user("Bearer expired-token")
            self.assertEqual(error.exception.status_code, 401)
        finally:
            auth.jwt, auth.get_settings = original_jwt, original_settings

    def test_revoked_supabase_session_is_rejected_without_server_error(self):
        original_error = auth.AuthApiError
        original_settings = auth.get_settings
        original_client = auth._supabase_client

        class FakeAuthError(Exception):
            pass

        class FakeAuth:
            @staticmethod
            def get_user(_token):
                raise FakeAuthError("revoked")

        auth.AuthApiError = FakeAuthError
        auth.get_settings = lambda: SimpleNamespace(supabase_jwt_secret=None)
        auth._supabase_client = lambda: SimpleNamespace(auth=FakeAuth())
        try:
            with self.assertRaises(HTTPException) as error:
                get_current_user("Bearer revoked-token")
            self.assertEqual(error.exception.status_code, 401)
        finally:
            auth.AuthApiError = original_error
            auth.get_settings = original_settings
            auth._supabase_client = original_client

    def test_rls_policies_bind_records_to_auth_uid(self):
        migration = Path("supabase/migrations/202607240001_saas_foundation.sql").read_text()
        self.assertIn("enable row level security", migration)
        self.assertIn("user_id = auth.uid()", migration)
        self.assertIn("watchlist items via owner", migration)

    def test_empty_supabase_single_response_is_safe(self):
        self.assertEqual(_one(None), {})

    def test_supabase_insert_response_returns_one_record(self):
        response = SimpleNamespace(data=[{"id": "account-1"}])

        self.assertEqual(_one(response), {"id": "account-1"})


if __name__ == "__main__":
    unittest.main()
