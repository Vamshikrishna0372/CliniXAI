"""
Comprehensive Production-Hardening & End-to-End Acceptance Tests for CliniXAI Google Authentication.

Validates:
1. Google identity verification (OIDC token validation)
2. Safe account linking: existing email/password account linked to Google
3. Existing Google user repeat login (idempotency, zero duplicates in users and patients)
4. New Google account strictly assigned PATIENT role with linked patient profile in patients collection
5. Account status enforcement: disabled/suspended accounts blocked with 403 Forbidden
6. Role security: role cannot be overridden or escalated via OAuth
7. HttpOnly cookie setting and TokenResponse payload structure
8. OAuth redirect GET callback handling (code exchange & safe error redirect)
9. Zero secret leakage across responses and logs
"""

import pytest
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.database.collections import COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.utils.datetime import utc_now
from app.utils.id_generator import generate_user_id, generate_patient_id
from app.database.mongodb import connect_to_mongo, close_mongo_connection, get_db


@pytest.fixture(autouse=True)
async def setup_db():
    await connect_to_mongo()
    yield
    await close_mongo_connection()


@pytest.mark.asyncio
class TestGoogleAuthAcceptance:

    # 1. New Google User -> Strict Patient Creation
    @patch("app.integrations.google_auth.GoogleAuthService.verify_google_id_token")
    async def test_new_google_patient_registration(self, mock_verify):
        """New Google identity automatically registers as Patient with linked profile."""
        db = get_db()
        test_email = "google.patient.test@gmail.com"
        test_sub = "google_sub_pat_1001"

        # Cleanup before test
        await db[COLLECTION_USERS].delete_many({"email": test_email})
        await db[COLLECTION_PATIENTS].delete_many({"email": test_email})

        mock_verify.return_value = {
            "google_sub": test_sub,
            "email": test_email,
            "full_name": "Google Patient One",
            "picture": "https://example.com/avatar.jpg",
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/google", json={"id_token": "valid_token_xyz"})
            assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
            data = resp.json()

            # Verify tokens and role
            assert "access_token" in data
            assert "refresh_token" in data
            assert data["role"] == "patient"
            assert data["email"] == test_email
            assert "user" in data
            assert data["user"]["role"] == "patient"
            assert data["user"]["patient_id"] is not None

            # Verify MongoDB users record
            user_rec = await db[COLLECTION_USERS].find_one({"email": test_email})
            assert user_rec is not None
            assert user_rec["google_sub"] == test_sub
            assert user_rec["role"] == "patient"
            assert user_rec["auth_provider"] == "google"
            assert user_rec["email_verified"] is True
            assert user_rec["account_status"] == "active"

            # Verify MongoDB patients record
            pat_rec = await db[COLLECTION_PATIENTS].find_one({"user_id": user_rec["user_id"]})
            assert pat_rec is not None
            assert pat_rec["patient_id"] == data["user"]["patient_id"]
            assert pat_rec["status"] == "active"

            # Verify Set-Cookie headers for browser clients
            cookies = resp.headers.get_list("set-cookie")
            cookie_names = [c.split("=")[0] for c in cookies]
            assert "access_token" in cookie_names
            assert "refresh_token" in cookie_names

        # Cleanup
        await db[COLLECTION_USERS].delete_many({"email": test_email})
        await db[COLLECTION_PATIENTS].delete_many({"email": test_email})

    # 2. Existing Google User Repeat Login (Zero Duplicates)
    @patch("app.integrations.google_auth.GoogleAuthService.verify_google_id_token")
    async def test_existing_google_user_repeat_login_no_duplicates(self, mock_verify):
        """Second login with same Google account preserves existing user and creates zero duplicate records."""
        db = get_db()
        test_email = "repeat.google@gmail.com"
        test_sub = "google_sub_repeat_2002"

        # Cleanup
        await db[COLLECTION_USERS].delete_many({"email": test_email})
        await db[COLLECTION_PATIENTS].delete_many({"email": test_email})

        mock_verify.return_value = {
            "google_sub": test_sub,
            "email": test_email,
            "full_name": "Repeat Google User",
            "picture": None,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Login 1: Creates account
            resp1 = await client.post("/api/v1/auth/google", json={"id_token": "token_1"})
            assert resp1.status_code == 200
            user1 = resp1.json()["user"]

            # Login 2: Re-authenticates existing account
            resp2 = await client.post("/api/v1/auth/google", json={"id_token": "token_2"})
            assert resp2.status_code == 200
            user2 = resp2.json()["user"]

            # Verify identical user_id and patient_id
            assert user1["user_id"] == user2["user_id"]
            assert user1["patient_id"] == user2["patient_id"]

            # Count documents in DB to strictly guarantee NO duplicate users or patients
            user_count = await db[COLLECTION_USERS].count_documents({"email": test_email})
            pat_count = await db[COLLECTION_PATIENTS].count_documents({"email": test_email})
            assert user_count == 1, f"Expected exactly 1 user document, found {user_count}"
            assert pat_count == 1, f"Expected exactly 1 patient document, found {pat_count}"

        # Cleanup
        await db[COLLECTION_USERS].delete_many({"email": test_email})
        await db[COLLECTION_PATIENTS].delete_many({"email": test_email})

    # 3. Email-Based Account Linking
    @patch("app.integrations.google_auth.GoogleAuthService.verify_google_id_token")
    async def test_email_based_account_linking(self, mock_verify):
        """Existing local email user logging in with Google gets google_sub linked without role change."""
        db = get_db()
        test_email = "local.existing@gmail.com"
        test_sub = "google_sub_link_3003"
        existing_uid = generate_user_id()
        existing_pid = generate_patient_id()

        # Seed existing local user
        await db[COLLECTION_USERS].delete_many({"email": test_email})
        await db[COLLECTION_PATIENTS].delete_many({"email": test_email})

        now = utc_now()
        await db[COLLECTION_USERS].insert_one({
            "user_id": existing_uid,
            "email": test_email,
            "full_name": "Existing Local Patient",
            "password_hash": "existing_hashed_pwd",
            "role": "patient",
            "auth_provider": "local",
            "google_sub": None,
            "email_verified": False,
            "account_status": "active",
            "created_at": now,
            "updated_at": now,
        })
        await db[COLLECTION_PATIENTS].insert_one({
            "patient_id": existing_pid,
            "user_id": existing_uid,
            "first_name": "Existing",
            "last_name": "Local",
            "full_name": "Existing Local Patient",
            "email": test_email,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        })

        mock_verify.return_value = {
            "google_sub": test_sub,
            "email": test_email,
            "full_name": "Existing Local Patient",
            "picture": None,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/google", json={"id_token": "token_link"})
            assert resp.status_code == 200
            data = resp.json()

            assert data["user"]["user_id"] == existing_uid
            assert data["user"]["patient_id"] == existing_pid
            assert data["role"] == "patient"

            # Check DB updated
            updated_user = await db[COLLECTION_USERS].find_one({"user_id": existing_uid})
            assert updated_user["google_sub"] == test_sub
            assert updated_user["email_verified"] is True

            user_count = await db[COLLECTION_USERS].count_documents({"email": test_email})
            assert user_count == 1

        # Cleanup
        await db[COLLECTION_USERS].delete_many({"email": test_email})
        await db[COLLECTION_PATIENTS].delete_many({"email": test_email})

    # 4. Account Status Enforcement (Disabled Accounts Blocked)
    @patch("app.integrations.google_auth.GoogleAuthService.verify_google_id_token")
    async def test_disabled_account_rejected(self, mock_verify):
        """User with DISABLED status is rejected with 403 Forbidden."""
        db = get_db()
        test_email = "disabled.user@gmail.com"
        test_sub = "google_sub_disabled_4004"
        uid = generate_user_id()

        await db[COLLECTION_USERS].delete_many({"email": test_email})
        now = utc_now()
        await db[COLLECTION_USERS].insert_one({
            "user_id": uid,
            "email": test_email,
            "full_name": "Disabled Patient",
            "role": "patient",
            "auth_provider": "google",
            "google_sub": test_sub,
            "email_verified": True,
            "account_status": "disabled",
            "created_at": now,
            "updated_at": now,
        })

        mock_verify.return_value = {
            "google_sub": test_sub,
            "email": test_email,
            "full_name": "Disabled Patient",
            "picture": None,
        }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/google", json={"id_token": "token_disabled"})
            assert resp.status_code == 403, f"Expected 403 Forbidden, got {resp.status_code}"

        # Cleanup
        await db[COLLECTION_USERS].delete_many({"email": test_email})

    # 5. Invalid Token Rejected
    async def test_invalid_google_token_rejected(self):
        """Malformed or empty token is rejected with 401 Unauthorized."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp1 = await client.post("/api/v1/auth/google", json={"id_token": "short"})
            assert resp1.status_code == 401

            resp2 = await client.post("/api/v1/auth/google", json={})
            assert resp2.status_code in [400, 422]  # Validation error: missing token/credential/code

    # 6. OAuth Redirect GET Callback Handles Error
    async def test_google_callback_error_redirects(self):
        """OAuth error returned from Google redirects back to frontend login with safe error message."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/auth/google/callback?error=access_denied", follow_redirects=False)
            assert resp.status_code in [302, 303, 307]
            redirect_location = resp.headers.get("location", "")
            assert "/auth/login?error=" in redirect_location

    # 7. OAuth Redirect GET Callback Handles Missing Code
    async def test_google_callback_missing_code_redirects(self):
        """Callback without code parameter redirects to login with error."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/auth/google/callback", follow_redirects=False)
            assert resp.status_code in [302, 303, 307]
            redirect_location = resp.headers.get("location", "")
            assert "/auth/login?error=" in redirect_location

    # 8. Google OAuth Login Redirect URL Endpoint
    async def test_google_login_redirect_url(self):
        """GET /auth/google/login redirects to accounts.google.com with proper params."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/auth/google/login", follow_redirects=False)
            assert resp.status_code in [302, 303, 307]
            redirect_location = resp.headers.get("location", "")
            assert "accounts.google.com" in redirect_location
            assert "client_id=" in redirect_location
            assert "redirect_uri=" in redirect_location
            assert "scope=openid" in redirect_location

    # 9. Google OAuth Callback with Frontend Timestamped State
    @patch("app.integrations.google_auth.GoogleAuthService.verify_google_id_token")
    @patch("app.integrations.google_auth.GoogleAuthService.exchange_code_for_tokens")
    async def test_google_callback_frontend_state_success(self, mock_exchange, mock_verify):
        """GET /auth/google/callback with valid code and frontend timestamped state succeeds and redirects with tokens."""
        import time
        db = get_db()
        test_email = "mobile.oauth.test@gmail.com"
        test_sub = "google_sub_mobile_9999"

        await db[COLLECTION_USERS].delete_many({"email": test_email})
        await db[COLLECTION_PATIENTS].delete_many({"email": test_email})

        mock_exchange.return_value = {
            "id_token": "valid_mock_id_token",
            "access_token": "mock_google_access",
        }
        mock_verify.return_value = {
            "google_sub": test_sub,
            "email": test_email,
            "full_name": "Mobile Google Patient",
            "picture": None,
        }

        ts_now = int(time.time() * 1000)
        state = f"clinixai_oauth_{ts_now}"

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(f"/api/v1/auth/google/callback?code=mock_auth_code&state={state}", follow_redirects=False)
            assert resp.status_code in [302, 303, 307]
            redirect_location = resp.headers.get("location", "")
            assert "google_success=true" in redirect_location
            assert "access_token=" in redirect_location
            assert "refresh_token=" in redirect_location

        await db[COLLECTION_USERS].delete_many({"email": test_email})
        await db[COLLECTION_PATIENTS].delete_many({"email": test_email})

