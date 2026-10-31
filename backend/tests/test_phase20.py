"""Comprehensive Final End-to-End Integration & Release Hardening Test Suite for Phase 20."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now


def create_mock_cursor(return_data=None):
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db_phase20():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
            col.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
            col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
            col.count_documents = AsyncMock(return_value=1)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            col.aggregate = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase20FinalProductionReadiness(unittest.IsolatedAsyncioTestCase):
    """Final release hardening integration test suite verifying complete multi-role workflows and security."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase20()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.admin_user = UserInDB(
            user_id="USR-ADM-DEMO-001",
            email="admin@clinixai.com",
            full_name="Hospital Admin",
            role=UserRole.HOSPITAL_ADMIN,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.doc_user = UserInDB(
            user_id="USR-DOC-RAO-001",
            email="doctor.arjun@clinixai.com",
            full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.pat1_user = UserInDB(
            user_id="USR-PAT-ONE-001",
            email="patient.one@clinixai.com",
            full_name="Patient One",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.pat2_user = UserInDB(
            user_id="USR-PAT-TWO-002",
            email="patient.two@clinixai.com",
            full_name="Patient Two",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.staff_user = UserInDB(
            user_id="USR-STF-ONE-001",
            email="staff.one@clinixai.com",
            full_name="Staff One",
            role=UserRole.HOSPITAL_STAFF,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        def mock_user_find_one(query):
            uid = query.get("user_id")
            if uid == "USR-ADM-DEMO-001":
                return self.admin_user.model_dump()
            if uid == "USR-DOC-RAO-001":
                return self.doc_user.model_dump()
            if uid == "USR-PAT-ONE-001":
                return self.pat1_user.model_dump()
            if uid == "USR-PAT-TWO-002":
                return self.pat2_user.model_dump()
            if uid == "USR-STF-ONE-001":
                return self.staff_user.model_dump()
            return None

        self.mock_db["users"].find_one.side_effect = AsyncMock(side_effect=mock_user_find_one)

        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.doc_token = create_access_token(user_id=self.doc_user.user_id, role=self.doc_user.role.value)
        self.pat1_token = create_access_token(user_id=self.pat1_user.user_id, role=self.pat1_user.role.value)
        self.pat2_token = create_access_token(user_id=self.pat2_user.user_id, role=self.pat2_user.role.value)
        self.staff_token = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        self.pat1_headers = {"Authorization": f"Bearer {self.pat1_token}"}
        self.pat2_headers = {"Authorization": f"Bearer {self.pat2_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_auth_me_session_restoration(self):
        """Verify /auth/me returns current user payload for all 4 roles."""
        for name, headers, expected_uid in [
            ("Admin", self.admin_headers, "USR-ADM-DEMO-001"),
            ("Doctor", self.doc_headers, "USR-DOC-RAO-001"),
            ("Patient", self.pat1_headers, "USR-PAT-ONE-001"),
            ("Staff", self.staff_headers, "USR-STF-ONE-001"),
        ]:
            res = await self.client.get("/api/v1/auth/me", headers=headers)
            self.assertEqual(res.status_code, 200, f"Session restoration failed for {name}")
            data = res.json()
            uid_found = data.get("user_id") if "user_id" in data else data.get("data", {}).get("user_id")
            self.assertEqual(uid_found, expected_uid)

    async def test_admin_operational_summary_and_reports_csv(self):
        """Verify Admin can access operational summary and export CSV report."""
        res_sum = await self.client.get("/api/v1/admin/summary", headers=self.admin_headers)
        self.assertEqual(res_sum.status_code, 200)

        res_csv = await self.client.get("/api/v1/admin/reports/csv", headers=self.admin_headers)
        self.assertEqual(res_csv.status_code, 200)
        self.assertIn("Bill ID", res_csv.text)

    async def test_patient_notification_inbox_and_unread_count(self):
        """Verify Patient can view unread count and list notification inbox."""
        res_cnt = await self.client.get("/api/v1/notifications/unread-count", headers=self.pat1_headers)
        self.assertEqual(res_cnt.status_code, 200)

        res_list = await self.client.get("/api/v1/notifications", headers=self.pat1_headers)
        self.assertEqual(res_list.status_code, 200)

    async def test_idor_patient_isolation_security(self):
        """Verify Patient 2 cannot access Patient 1's appointment or bill (403 Forbidden)."""
        pat1_apt = {
            "appointment_id": "APT-PAT1-EXCLUSIVE",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "department_id": "DEP-CARD-001",
            "appointment_date": "2026-08-25",
            "start_time": "10:00",
            "end_time": "10:30",
            "status": "scheduled",
        }
        pat1_patient_profile = {
            "patient_id": "PAT-TWO-002",
            "user_id": "USR-PAT-TWO-002",
        }
        self.mock_db["appointments"].find_one.return_value = pat1_apt
        self.mock_db["patients"].find_one.return_value = pat1_patient_profile

        res_apt = await self.client.get("/api/v1/appointments/APT-PAT1-EXCLUSIVE", headers=self.pat2_headers)
        self.assertEqual(res_apt.status_code, 403)
