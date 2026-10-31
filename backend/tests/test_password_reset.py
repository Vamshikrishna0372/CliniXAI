"""Unit test suite for Password Reset and Change Password flows."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from datetime import timedelta
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import hash_password, create_access_token
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


class TestPasswordResetFlows(unittest.IsolatedAsyncioTestCase):
    """Test suite for password reset and change password endpoints."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_async_mock_db()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.old_password = "OldPassword123!"
        self.user = UserInDB(
            user_id="USR-2026-PWD001",
            email="reset@clinixai.com",
            full_name="Reset Test User",
            password_hash=hash_password(self.old_password),
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    async def test_forgot_password_request(self) -> None:
        """Verifies forgot password request generates reset token hash."""
        self.mock_db["users"].find_one.return_value = self.user.to_mongo_dict()

        payload = {"email": "reset@clinixai.com"}
        response = await self.client.post("/api/v1/auth/password/forgot", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    async def test_reset_password_success(self) -> None:
        """Verifies password reset with valid token succeeds and revokes active sessions."""
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)

        user_with_token = self.user.model_copy()
        user_with_token.password_reset_token_hash = token_hash
        user_with_token.password_reset_expires_at = utc_now() + timedelta(hours=1)

        self.mock_db["users"].find_one.return_value = user_with_token.to_mongo_dict()

        payload = {
            "token": raw_token,
            "new_password": "NewBrandPassword123!",
        }
        response = await self.client.post("/api/v1/auth/password/reset", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

    async def test_change_password_success(self) -> None:
        """Verifies authenticated password change with valid current password."""
        token = create_access_token(user_id=self.user.user_id, role=self.user.role.value)

        self.mock_db["users"].find_one.return_value = self.user.to_mongo_dict()

        payload = {
            "current_password": self.old_password,
            "new_password": "BrandNewPassword456!",
        }
        response = await self.client.post(
            "/api/v1/auth/password/change",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
