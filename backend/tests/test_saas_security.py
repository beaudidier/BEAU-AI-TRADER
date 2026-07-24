import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi import HTTPException

from saas import auth
from saas.auth import get_current_user
from saas.entitlements import require_limit


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

    def test_rls_policies_bind_records_to_auth_uid(self):
        migration = Path("supabase/migrations/202607240001_saas_foundation.sql").read_text()
        self.assertIn("enable row level security", migration)
        self.assertIn("user_id = auth.uid()", migration)
        self.assertIn("watchlist items via owner", migration)


if __name__ == "__main__":
    unittest.main()
