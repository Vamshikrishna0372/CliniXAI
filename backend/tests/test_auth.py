"""Unit test suite for Authentication, Registration, Login, Token Refresh, and Logout."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import hash_password, create_access_token, create_refresh_token
from app.utils.datetime import utc_now


def create_async_mock_db():
    """Helper creating a mock database whose collection methods return awaitable AsyncMocks."""
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


class TestAuthEndpoints(unittest.IsolatedAsyncioTestCase):
    """Test suite for authentication API endpoints."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")
        
        self.mock_db = create_async_mock_db()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # Sample User data
        self.sample_password = "SecurePassword123!"
        self.hashed_password = hash_password(self.sample_password)
        
        self.sample_user = UserInDB(
            user_id="USR-2026-TEST01",
            email="patient@clinixai.com",
            full_name="Test Patient",
            password_hash=self.hashed_password,
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            email_verified=True,
            account_status=AccountStatus.ACTIVE,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    async def test_public_patient_registration_success(self) -> None:
        """Verifies successful public patient registration."""
        self.mock_db["users"].find_one.return_value = None

        payload = {
            "email": "newpatient@clinixai.com",
            "password": "Password123!",
            "full_name": "New Patient",
        }
        response = await self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["user"]["role"], "patient")
        self.assertEqual(data["user"]["email"], "newpatient@clinixai.com")

    async def test_public_registration_overrides_privileged_role_attempt(self) -> None:
        """Verifies that attempts to send a privileged role (e.g. hospital_admin) during public registration are strictly overridden to patient."""
        self.mock_db["users"].find_one.return_value = None

        payload = {
            "email": "hacker@clinixai.com",
            "password": "Password123!",
            "full_name": "Hacker User",
            "role": "hospital_admin"  # Malicious extra payload field
        }
        response = await self.client.post("/api/v1/auth/register", json=payload)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        # Must strictly be assigned 'patient' role
        self.assertEqual(data["user"]["role"], "patient")

    async def test_login_success(self) -> None:
        """Verifies successful user login with correct email and password."""
        self.mock_db["users"].find_one.return_value = self.sample_user.to_mongo_dict()

        payload = {
            "email": "patient@clinixai.com",
            "password": self.sample_password,
        }
        response = await self.client.post("/api/v1/auth/login", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertEqual(data["user"]["email"], "patient@clinixai.com")

    async def test_login_invalid_password(self) -> None:
        """Verifies 401 Unauthorized returned for wrong password."""
        self.mock_db["users"].find_one.return_value = self.sample_user.to_mongo_dict()

        payload = {
            "email": "patient@clinixai.com",
            "password": "WrongPassword999!",
        }
        response = await self.client.post("/api/v1/auth/login", json=payload)
        self.assertEqual(response.status_code, 401)

    async def test_get_current_user_me(self) -> None:
        """Verifies GET /api/v1/auth/me returns profile for valid Bearer token."""
        token = create_access_token(user_id=self.sample_user.user_id, role=self.sample_user.role.value)
        headers = {"Authorization": f"Bearer {token}"}

        self.mock_db["users"].find_one.return_value = self.sample_user.to_mongo_dict()

        response = await self.client.get("/api/v1/auth/me", headers=headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["user_id"], self.sample_user.user_id)
        self.assertEqual(data["email"], self.sample_user.email)

    async def test_admin_invite_user_rbac_enforcement(self) -> None:
        """Verifies Hospital Admin can invite a doctor/staff user, whereas non-admin receives 403 Forbidden."""
        patient_token = create_access_token(user_id=self.sample_user.user_id, role="patient")
        patient_headers = {"Authorization": f"Bearer {patient_token}"}

        admin_user_id = "USR-2026-ADM001"
        admin_token = create_access_token(user_id=admin_user_id, role="hospital_admin")
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        invite_payload = {
            "email": "dr.smith@clinixai.com",
            "full_name": "Dr. Smith",
            "role": "doctor"
        }

        # Patient attempt MUST be rejected with HTTP 403
        self.mock_db["users"].find_one.return_value = self.sample_user.to_mongo_dict()
        res_forbidden = await self.client.post("/api/v1/auth/invite", json=invite_payload, headers=patient_headers)
        self.assertEqual(res_forbidden.status_code, 403)

        # Admin attempt MUST succeed with HTTP 201
        admin_user_doc = UserInDB(
            user_id=admin_user_id, email="admin@clinixai.com", full_name="Admin User",
            role=UserRole.HOSPITAL_ADMIN, auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE, created_at=utc_now(), updated_at=utc_now()
        ).to_mongo_dict()

        def mock_find(query):
            if query.get("user_id") == admin_user_id:
                return admin_user_doc
            return None

        self.mock_db["users"].find_one.side_effect = mock_find
        res_ok = await self.client.post("/api/v1/auth/invite", json=invite_payload, headers=admin_headers)
        self.assertEqual(res_ok.status_code, 201)
        data = res_ok.json()
        self.assertTrue(data["success"])
        self.assertIn("invitation_token", data["data"])

    async def test_invitation_verify_and_accept_workflow(self) -> None:
        """Verifies verifying invitation token and accepting it to activate provisioned account."""
        from app.utils.tokens import generate_secure_token, hash_token
        from datetime import timedelta

        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)

        # Stale document — INACTIVE, has invitation_token_hash
        base_doc = UserInDB(
            user_id="USR-2026-DOC999",
            email="invited.doctor@clinixai.com",
            full_name="Invited Doctor",
            password_hash=None,
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            email_verified=False,
            account_status=AccountStatus.INACTIVE,
            invitation_token_hash=token_hash,
            invitation_expires_at=utc_now() + timedelta(days=7),
            created_at=utc_now(),
            updated_at=utc_now(),
        ).to_mongo_dict()

        # Activated document — ACTIVE, no invitation_token_hash
        activated_doc = {**base_doc, "account_status": AccountStatus.ACTIVE, "email_verified": True, "invitation_token_hash": None}

        # Simulate stateful DB: first 2 find_one calls return stale doc; after update_one, return activated doc
        update_called = {"value": False}

        async def stateful_find_one(query):
            if update_called["value"]:
                return activated_doc
            return base_doc

        async def fake_update_one(filter_q, update_q):
            update_called["value"] = True

        self.mock_db["users"].find_one.side_effect = stateful_find_one
        self.mock_db["users"].update_one.side_effect = fake_update_one

        # Step 1: Verify invitation token
        verify_res = await self.client.post("/api/v1/auth/invitation/verify", json={"token": raw_token})
        self.assertEqual(verify_res.status_code, 200)
        verify_data = verify_res.json()
        self.assertTrue(verify_data["success"])
        self.assertEqual(verify_data["data"]["email"], "invited.doctor@clinixai.com")
        self.assertEqual(verify_data["data"]["role"], "doctor")

        # Step 2: Accept invitation — activates account, returns JWT session
        accept_res = await self.client.post(
            "/api/v1/auth/invitation/accept",
            json={"token": raw_token, "password": "NewDoctorPassword123!"}
        )
        self.assertEqual(accept_res.status_code, 200)
        accept_data = accept_res.json()
        self.assertIn("access_token", accept_data)
        self.assertIn("refresh_token", accept_data)
        self.assertEqual(accept_data["user"]["role"], "doctor")
        self.assertEqual(accept_data["user"]["account_status"], "active")
        self.assertTrue(accept_data["user"]["email_verified"])

    async def test_cors_preflight_and_allowed_origins(self) -> None:
        """Verifies OPTIONS preflight and CORS response headers for configured origins."""
        for origin in ["http://localhost:8080", "http://localhost:5173", "http://localhost:3000"]:
            res = await self.client.options(
                "/api/v1/auth/login",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "authorization, content-type",
                }
            )
            self.assertEqual(res.status_code, 200)
            self.assertEqual(res.headers.get("access-control-allow-origin"), origin)
            self.assertEqual(res.headers.get("access-control-allow-credentials"), "true")




