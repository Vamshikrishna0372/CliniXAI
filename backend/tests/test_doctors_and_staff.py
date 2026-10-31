"""Comprehensive Test Suite for Doctors & Hospital Staff Modules in CliniXAI."""

import unittest
from unittest.mock import MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.doctor import DoctorStatus
from app.models.staff import StaffStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now
from tests.test_phase13 import create_mock_cursor


from unittest.mock import AsyncMock, MagicMock

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


class TestDoctorsAndStaff(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://test")

        self.mock_db = create_mock_db()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # Define Roles & Users
        self.admin_user = UserInDB(
            user_id="USR-ADM-001", email="admin@clinixai.com", full_name="System Admin",
            role=UserRole.HOSPITAL_ADMIN, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.doctor_user = UserInDB(
            user_id="USR-DOC-001", email="doctor@clinixai.com", full_name="Dr. Gregory House",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.staff_user = UserInDB(
            user_id="USR-STF-001", email="staff@clinixai.com", full_name="Nurse Ratched",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_user = UserInDB(
            user_id="USR-PAT-001", email="patient@clinixai.com", full_name="John Doe",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )

        # Tokens & Headers
        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.doctor_token = create_access_token(user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)
        self.staff_token = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)
        self.patient_token = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.doctor_headers = {"Authorization": f"Bearer {self.doctor_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}

        # Mock DB records
        self.dept_dict = {
            "department_id": "DEP-01",
            "name": "General Medicine",
            "description": "General care",
            "status": "active"
        }

        now = utc_now()
        self.doctor_dict = {
            "doctor_id": "DOC-001",
            "user_id": self.doctor_user.user_id,
            "first_name": "Gregory",
            "last_name": "House",
            "email": "doctor@clinixai.com",
            "specialization": "General Medicine",
            "department_id": "DEP-01",
            "qualification": "MBBS, MD",
            "experience_years": 15,
            "consultation_fee": 500.0,
            "status": "active",
            "created_at": now,
            "updated_at": now,
            "schedule": {
                "slot_duration_minutes": 30,
                "weekly": [
                    {"day": "monday", "is_available": True, "slots": [{"start": "09:00", "end": "12:00"}]}
                ]
            }
        }

        self.staff_dict = {
            "staff_id": "STF-001",
            "user_id": self.staff_user.user_id,
            "first_name": "Nurse",
            "last_name": "Ratched",
            "email": "staff@clinixai.com",
            "job_title": "Senior Receptionist",
            "department_id": "DEP-01",
            "status": "active",
            "created_at": now,
            "updated_at": now
        }

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # ── Doctor Endpoint Tests ───────────────────────────────────────────

    async def test_list_doctors_success(self) -> None:
        """Any authenticated user can list doctors."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["doctors"].count_documents.return_value = 1
        self.mock_db["doctors"].find.return_value = create_mock_cursor([self.doctor_dict])

        res = await self.client.get("/api/v1/doctors", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["data"]), 1)
        self.assertEqual(res.json()["data"][0]["doctor_id"], "DOC-001")

    async def test_get_doctor_detail_success(self) -> None:
        """Fetch doctor detail by ID."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict

        res = await self.client.get("/api/v1/doctors/DOC-001", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["doctor_id"], "DOC-001")

    async def test_create_doctor_admin_only(self) -> None:
        """Admin can provision a new doctor account."""
        self.mock_db["users"].find_one.side_effect = lambda q: self.admin_user.to_mongo_dict() if q.get("user_id") == self.admin_user.user_id else None
        self.mock_db["departments"].find_one.return_value = self.dept_dict

        payload = {
            "email": "newdoc@clinixai.com",
            "full_name": "Dr. Allison Cameron",
            "first_name": "Allison",
            "last_name": "Cameron",
            "specialization": "Immunology",
            "department_id": "DEP-01",
            "qualification": "MBBS, MD",
            "experience_years": 8,
            "consultation_fee": 600.0
        }
        res = await self.client.post("/api/v1/doctors", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        self.assertIn("data", res.json())

    async def test_update_doctor_profile(self) -> None:
        """Admin updates doctor profile fields."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict

        payload = {
            "specialization": "Cardiology",
            "consultation_fee": 750.0,
            "status": "active"
        }
        res = await self.client.patch("/api/v1/doctors/DOC-001", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.mock_db["doctors"].update_one.assert_called()

    # ── Staff Endpoint Tests ────────────────────────────────────────────

    async def test_list_staff_admin_only(self) -> None:
        """Admin lists hospital staff."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()
        self.mock_db["staff"].count_documents.return_value = 1
        self.mock_db["staff"].find.return_value = create_mock_cursor([self.staff_dict])

        res = await self.client.get("/api/v1/staff", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["data"]), 1)

    async def test_list_staff_forbidden_for_patient(self) -> None:
        """Patient receives 403 trying to access staff directory."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()

        res = await self.client.get("/api/v1/staff", headers=self.patient_headers)
        self.assertEqual(res.status_code, 403)

    async def test_update_staff_status_deactivation_sync(self) -> None:
        """Deactivating staff syncs account_status in users collection."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()
        self.mock_db["staff"].find_one.return_value = self.staff_dict

        payload = {"status": "inactive"}
        res = await self.client.patch("/api/v1/staff/STF-001", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

        # Assert staff collection update
        self.mock_db["staff"].update_one.assert_called()
        # Assert users collection account_status set to suspended
        self.mock_db["users"].update_one.assert_called_with(
            {"user_id": self.staff_user.user_id},
            {"$set": {"account_status": AccountStatus.SUSPENDED.value, "updated_at": unittest.mock.ANY}}
        )


if __name__ == "__main__":
    unittest.main()
