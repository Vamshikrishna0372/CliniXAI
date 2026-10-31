"""Unit test suite for Email Verification flows."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from datetime import timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.utils.datetime import utc_now
from app.utils.tokens import generate_secure_token, hash_token


def create_async_mock_db():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=None)
            col.delete_one = AsyncMock(return_value=None)
            col.delete_many = AsyncMock(return_value=None)
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestEmailVerification(unittest.IsolatedAsyncioTestCase):
    """Test suite for email verification endpoints."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_async_mock_db()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.user = UserInDB(
            user_id="USR-2026-VER001",
            email="verify@clinixai.com",
            full_name="Verify User",
            password_hash="hashedpass",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            email_verified=False,
            account_status=AccountStatus.ACTIVE,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    async def test_request_email_verification(self) -> None:
        """Verifies email verification request generates token."""
        self.mock_db["users"].find_one.return_value = self.user.to_mongo_dict()

        payload = {"email": "verify@clinixai.com"}
        response = await self.client.post("/api/v1/auth/email-verification/request", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    async def test_confirm_email_verification_success(self) -> None:
        """Verifies valid email verification token marks email_verified = True."""
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)

        user_unverified = self.user.model_copy()
        user_unverified.email_verification_token_hash = token_hash
        user_unverified.email_verification_expires_at = utc_now() + timedelta(hours=1)

        self.mock_db["users"].find_one.return_value = user_unverified.to_mongo_dict()

        payload = {"token": raw_token}
        response = await self.client.post("/api/v1/auth/email-verification/confirm", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
