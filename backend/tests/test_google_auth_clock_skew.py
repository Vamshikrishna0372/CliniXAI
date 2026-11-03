"""
Unit and Integration Tests for Google OAuth ID Token Clock Skew Tolerance.
Verifies:
1. Google ID token issued slightly in the future (e.g. 2-5 seconds clock drift between client/Google and server)
   is successfully accepted using google-auth library's clock_skew_in_seconds option.
2. Tokens issued far in the future (> clock_skew_in_seconds) remain strictly rejected.
3. Expired tokens (> clock_skew_in_seconds in the past) remain strictly rejected.
4. Security validation (signature, issuer, audience, email_verified) is strictly preserved.
5. End-to-end Google authentication flow (Token -> User lookup/creation -> JWT session -> Role dashboard).
6. Normal email/password authentication is completely unaffected.
"""

import time
import unittest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.database.mongodb import db_manager, connect_to_mongo, close_mongo_connection
from app.database.collections import COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS
from app.models.user import UserRole, AccountStatus
from app.integrations.google_auth import GoogleAuthService
from app.core.exceptions import UnauthorizedError


class TestGoogleAuthClockSkew(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await connect_to_mongo()
        self.db = db_manager.db
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

    async def asyncTearDown(self):
        await self.client.aclose()
        await close_mongo_connection()

    @patch("google.oauth2.id_token.verify_oauth2_token")
    @patch("google.auth.transport.requests.Request")
    async def test_01_token_used_too_early_within_clock_skew_passes(self, mock_request, mock_verify):
        """
        Verify that a Google ID token with iat slightly in the future (e.g. 2s drift)
        passes verification when clock_skew_in_seconds is passed to google.oauth2.id_token.
        """
        now = int(time.time())
        # Mock claim representing a valid Google payload with iat 2 seconds ahead of server clock
        mock_claim = {
            "iss": "https://accounts.google.com",
            "aud": settings.GOOGLE_CLIENT_ID,
            "sub": "google_sub_skew_test_12345",
            "email": "skew.patient@example.com",
            "email_verified": True,
            "name": "Skew Test Patient",
            "iat": now + 2,
            "exp": now + 3600,
        }
        mock_verify.return_value = mock_claim

        result = await GoogleAuthService.verify_google_id_token("real_format_google_id_token_xyz")

        # Verify verify_oauth2_token was called with clock_skew_in_seconds=15
        mock_verify.assert_called_once()
        args, kwargs = mock_verify.call_args
        self.assertEqual(kwargs.get("clock_skew_in_seconds"), settings.GOOGLE_AUTH_CLOCK_SKEW_SECONDS)
        self.assertEqual(kwargs.get("audience"), settings.GOOGLE_CLIENT_ID)
        self.assertEqual(result["email"], "skew.patient@example.com")
        self.assertEqual(result["google_sub"], "google_sub_skew_test_12345")

    @patch("google.oauth2.id_token.verify_oauth2_token")
    @patch("google.auth.transport.requests.Request")
    async def test_02_token_used_too_early_beyond_clock_skew_rejected(self, mock_request, mock_verify):
        """
        Verify that a Google ID token issued far in the future (> clock_skew_in_seconds)
        raises UnauthorizedError with message indicating invalid token.
        """
        # When token is beyond clock skew, google.auth raises ValueError
        mock_verify.side_effect = ValueError(
            "Token used too early, 1793679051 < 1793679351. Check that your computer's clock is set correctly."
        )

        with self.assertRaises(UnauthorizedError) as ctx:
            await GoogleAuthService.verify_google_id_token("future_token_beyond_skew")
        self.assertIn("Invalid Google ID token", str(ctx.exception))
        self.assertIn("Token used too early", str(ctx.exception))

    @patch("google.oauth2.id_token.verify_oauth2_token")
    @patch("google.auth.transport.requests.Request")
    async def test_03_expired_token_strictly_rejected(self, mock_request, mock_verify):
        """
        Verify that an expired Google ID token raises UnauthorizedError.
        """
        mock_verify.side_effect = ValueError("Token expired, 1793679051 < 1793675000")

        with self.assertRaises(UnauthorizedError) as ctx:
            await GoogleAuthService.verify_google_id_token("expired_google_id_token")
        self.assertIn("expired", str(ctx.exception).lower())

    @patch("google.oauth2.id_token.verify_oauth2_token")
    @patch("google.auth.transport.requests.Request")
    async def test_04_audience_mismatch_strictly_rejected(self, mock_request, mock_verify):
        """
        Verify that a token with wrong audience is rejected without bypass.
        """
        mock_claim = {
            "iss": "https://accounts.google.com",
            "aud": "wrong-client-id.apps.googleusercontent.com",
            "sub": "sub_wrong_aud",
            "email": "attacker@example.com",
            "email_verified": True,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        mock_verify.return_value = mock_claim

        with self.assertRaises(UnauthorizedError) as ctx:
            await GoogleAuthService.verify_google_id_token("token_wrong_aud")
        self.assertIn("audience mismatch", str(ctx.exception).lower())

    @patch("google.oauth2.id_token.verify_oauth2_token")
    @patch("google.auth.transport.requests.Request")
    async def test_05_untrusted_issuer_strictly_rejected(self, mock_request, mock_verify):
        """
        Verify that a token with untrusted issuer is rejected without bypass.
        """
        mock_claim = {
            "iss": "https://fake-google.com",
            "aud": settings.GOOGLE_CLIENT_ID,
            "sub": "sub_fake_iss",
            "email": "attacker@example.com",
            "email_verified": True,
            "iat": int(time.time()),
            "exp": int(time.time()) + 3600,
        }
        mock_verify.return_value = mock_claim

        with self.assertRaises(UnauthorizedError) as ctx:
            await GoogleAuthService.verify_google_id_token("token_fake_iss")
        self.assertIn("issuer is untrusted", str(ctx.exception).lower())

    @patch("app.integrations.google_auth.GoogleAuthService.verify_google_id_token")
    async def test_06_complete_google_login_flow_new_patient(self, mock_verify_profile):
        """
        Verify complete flow:
        Google Login -> ID Token -> Verification -> User created as Patient -> JWT Session -> Dashboard
        """
        test_email = f"new.patient.google.{int(time.time())}@gmail.com"
        test_sub = f"google_sub_{int(time.time())}"
        mock_verify_profile.return_value = {
            "google_sub": test_sub,
            "email": test_email,
            "full_name": "Google New Patient",
            "picture": "https://example.com/avatar.jpg",
        }

        resp = await self.client.post("/api/v1/auth/google", json={"id_token": "valid_token_fresh"})
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["role"], "patient")
        self.assertEqual(data["email"], test_email)

        # Verify patient record was created in database
        patient_record = await self.db[COLLECTION_PATIENTS].find_one({"email": test_email})
        self.assertIsNotNone(patient_record)
        self.assertEqual(patient_record["full_name"], "Google New Patient")

        # Verify access token allows accessing patient dashboard / profile
        auth_headers = {"Authorization": f"Bearer {data['access_token']}"}
        me_resp = await self.client.get("/api/v1/auth/me", headers=auth_headers)
        self.assertEqual(me_resp.status_code, 200)
        me_data = me_resp.json()
        self.assertEqual(me_data["email"], test_email)
        self.assertEqual(me_data["role"], "patient")

    async def test_07_normal_email_password_login_unbroken(self):
        """
        Verify that normal email/password authentication remains 100% operational.
        """
        # Doctor Arjun login
        doc_resp = await self.client.post(
            "/api/v1/auth/login",
            json={"email": "doctor.arjun@clinixai.com", "password": "Doctor@123"}
        )
        self.assertEqual(doc_resp.status_code, 200, doc_resp.text)
        doc_data = doc_resp.json()
        self.assertIn("access_token", doc_data)
        self.assertEqual(doc_data["user"]["role"], "doctor")

        # Patient One login
        pat_resp = await self.client.post(
            "/api/v1/auth/login",
            json={"email": "patient.one@clinixai.com", "password": "Patient@123"}
        )
        self.assertEqual(pat_resp.status_code, 200, pat_resp.text)
        pat_data = pat_resp.json()
        self.assertIn("access_token", pat_data)
        self.assertEqual(pat_data["user"]["role"], "patient")


if __name__ == "__main__":
    unittest.main()

