"""Comprehensive Unit & Integration Test Suite for Phase 5: Doctor Discovery."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.doctor import DoctorStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now


def create_mock_cursor(return_data=None):
    """Helper creating a mock cursor with chainable sort, skip, limit methods."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=None)
            col.delete_one = AsyncMock(return_value=None)
            col.count_documents = AsyncMock(return_value=0)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase5DoctorDiscovery(unittest.IsolatedAsyncioTestCase):
    """Rigorous tests for Phase 5 Doctor Discovery endpoints and business logic."""

    async def asyncSetUp(self) -> None:
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

        self.mock_db = create_mock_db()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # Authenticated Patient
        self.patient_user = UserInDB(
            user_id="USR-PAT-001", email="patient.one@clinixai.com", full_name="Aarav Sharma",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_token = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}

        now = utc_now()
        self.active_doctor = {
            "doctor_id": "DOC-RAO-001",
            "user_id": "USR-DOC-001",
            "first_name": "Kavita",
            "last_name": "Rao",
            "full_name": "Dr. Kavita Rao",
            "email": "doctor.rao@clinixai.com",
            "specialization": "Cardiology",
            "department_id": "DEP-01",
            "qualification": "MBBS, MD (Cardiology)",
            "experience_years": 14,
            "consultation_fee": 800.0,
            "status": "active",
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }

        self.deleted_doctor = {
            "doctor_id": "DOC-DEL-999",
            "user_id": "USR-DOC-999",
            "first_name": "Terminated",
            "last_name": "Doc",
            "full_name": "Dr. Terminated Doc",
            "email": "deleted@clinixai.com",
            "specialization": "General Medicine",
            "department_id": "DEP-01",
            "qualification": "MBBS",
            "experience_years": 3,
            "consultation_fee": 400.0,
            "status": "inactive",
            "is_deleted": True,
            "created_at": now,
            "updated_at": now,
        }

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    async def test_doctor_discovery_lists_active_doctors_with_pagination(self) -> None:
        """Verify patient can list doctors with pagination metadata."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["doctors"].count_documents.return_value = 1
        self.mock_db["doctors"].find.return_value = create_mock_cursor([self.active_doctor])

        res = await self.client.get("/api/v1/doctors?page=1&page_size=10", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertTrue(body["success"])
        self.assertEqual(len(body["data"]), 1)
        self.assertEqual(body["data"][0]["doctor_id"], "DOC-RAO-001")
        self.assertEqual(body["data"][0]["specialization"], "Cardiology")
        self.assertEqual(body["pagination"]["page"], 1)
        self.assertEqual(body["pagination"]["total"], 1)

    async def test_doctor_discovery_excludes_deleted_and_defaults_active(self) -> None:
        """Verify list_doctors query enforces is_deleted != True and status == active."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["doctors"].count_documents.return_value = 1
        self.mock_db["doctors"].find.return_value = create_mock_cursor([self.active_doctor])

        res = await self.client.get("/api/v1/doctors", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)

        # Inspect the query passed to count_documents / find
        call_args = self.mock_db["doctors"].count_documents.call_args[0][0]
        self.assertEqual(call_args.get("is_deleted"), {"$ne": True})
        self.assertEqual(call_args.get("status"), DoctorStatus.ACTIVE.value)

    async def test_doctor_discovery_search_escaping(self) -> None:
        """Verify regex special characters in search do not crash or cause ReDoS injection."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["doctors"].count_documents.return_value = 0
        self.mock_db["doctors"].find.return_value = create_mock_cursor([])

        # Search term with regex metacharacters
        dangerous_search = "Dr.*[A-Z]+(?=test)"
        res = await self.client.get(f"/api/v1/doctors?search={dangerous_search}", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)

        call_args = self.mock_db["doctors"].count_documents.call_args[0][0]
        # Should be escaped properly in $or regexes
        self.assertIn("$or", call_args)
        escaped_val = call_args["$or"][0]["doctor_id"]["$regex"]
        self.assertIn(r"\*", escaped_val)
        self.assertIn(r"\[", escaped_val)

    async def test_get_doctor_detail_success(self) -> None:
        """Direct doctor profile lookup by doctor_id."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.active_doctor

        res = await self.client.get("/api/v1/doctors/DOC-RAO-001", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["doctor_id"], "DOC-RAO-001")
        self.assertEqual(data["first_name"], "Kavita")
        self.assertEqual(data["consultation_fee"], 800.0)

    async def test_get_doctor_detail_deleted_returns_404(self) -> None:
        """Deleted doctor returns 404 Not Found."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        # Mock find_one returning None because is_deleted == True was filtered out
        self.mock_db["doctors"].find_one.return_value = None

        res = await self.client.get("/api/v1/doctors/DOC-DEL-999", headers=self.patient_headers)
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["error"]["code"], "RESOURCE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
