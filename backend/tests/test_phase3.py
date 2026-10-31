"""Comprehensive Unit Test Suite for Phase 3: Patients, Departments, Doctors, Staff, Appointments, Check-In, & Queue."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.patient import PatientInDB, PatientStatus
from app.models.department import DepartmentInDB, DepartmentStatus
from app.models.doctor import DoctorInDB, DoctorStatus, DoctorSchedule, DaySchedule, TimeSlotBlock, DayOfWeek
from app.models.staff import StaffInDB, StaffStatus
from app.models.appointment import AppointmentInDB, AppointmentStatus, AppointmentType, BookingSource
from app.core.security import create_access_token
from app.utils.datetime import utc_now


def create_mock_db_phase3():
    """Returns a flexible mock database supporting async motor operations."""
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            update_result = MagicMock(matched_count=1, modified_count=1)
            col.update_one = AsyncMock(return_value=update_result)
            col.count_documents = AsyncMock(return_value=0)
            
            # Cursor mock setup for find().sort().skip().limit().to_list()
            mock_cursor = MagicMock()
            mock_cursor.sort.return_value = mock_cursor
            mock_cursor.skip.return_value = mock_cursor
            mock_cursor.limit.return_value = mock_cursor
            mock_cursor.to_list = AsyncMock(return_value=[])
            
            col.find = MagicMock(return_value=mock_cursor)
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase3Endpoints(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 3 APIs."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase3()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # User definitions for roles
        self.admin_user = UserInDB(
            user_id="USR-2026-ADMIN1", email="admin@clinixai.com", full_name="Admin User",
            role=UserRole.HOSPITAL_ADMIN, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.doctor_user = UserInDB(
            user_id="USR-2026-DOC001", email="doctor@clinixai.com", full_name="Dr. Smith",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.staff_user = UserInDB(
            user_id="USR-2026-STF001", email="staff@clinixai.com", full_name="Staff User",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_user = UserInDB(
            user_id="USR-2026-PAT001", email="patient@clinixai.com", full_name="John Doe",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )

        # Tokens
        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.doctor_token = create_access_token(user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)
        self.staff_token = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)
        self.patient_token = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)

        # Headers
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.doctor_headers = {"Authorization": f"Bearer {self.doctor_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}

        # Shared mock entity dicts
        self.dept_dict = {
            "department_id": "DEP-2026-CARD",
            "name": "Cardiology",
            "code": "CARD",
            "status": "active",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }

        default_weekly = [
            DaySchedule(day=day, is_available=True, slots=[TimeSlotBlock(start="09:00", end="13:00")])
            for day in DayOfWeek
        ]
        self.doctor_dict = {
            "doctor_id": "DOC-2026-00001",
            "user_id": self.doctor_user.user_id,
            "first_name": "John",
            "last_name": "Smith",
            "email": "doctor@clinixai.com",
            "department_id": "DEP-2026-CARD",
            "specialization": "Cardiologist",
            "schedule": DoctorSchedule(slot_duration_minutes=30, weekly=default_weekly).model_dump(),
            "status": "active",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }

        self.patient_dict = {
            "patient_id": "PAT-2026-00001",
            "user_id": self.patient_user.user_id,
            "first_name": "John",
            "last_name": "Doe",
            "email": "patient@clinixai.com",
            "status": "active",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }

        self.staff_dict = {
            "staff_id": "STF-2026-00001",
            "user_id": self.staff_user.user_id,
            "first_name": "Staff",
            "last_name": "Member",
            "email": "staff@clinixai.com",
            "status": "active",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # ── Patients ─────────────────────────────────────────────────────────────

    async def test_patient_self_profile(self) -> None:
        """Patient retrieves own self profile via GET /api/v1/patients/me."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        res = await self.client.get("/api/v1/patients/me", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["patient_id"], "PAT-2026-00001")

    async def test_staff_create_patient(self) -> None:
        """Staff registers a new patient profile."""
        self.mock_db["users"].find_one.return_value = self.staff_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = None

        payload = {
            "first_name": "Alice",
            "last_name": "Smith",
            "phone": "+1234567890",
            "allergies": ["Penicillin"],
        }
        res = await self.client.post("/api/v1/patients", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["first_name"], "Alice")

    async def test_patient_cannot_list_all_patients(self) -> None:
        """Patient role is forbidden from listing all hospital patients (403)."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        res = await self.client.get("/api/v1/patients", headers=self.patient_headers)
        self.assertEqual(res.status_code, 403)

    # ── Departments ──────────────────────────────────────────────────────────

    async def test_admin_create_department(self) -> None:
        """Admin creates a new hospital department."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()
        self.mock_db["departments"].find_one.return_value = None

        payload = {"name": "Neurology", "code": "NEURO", "description": "Brain and Nervous System"}
        res = await self.client.post("/api/v1/departments", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["code"], "NEURO")

    async def test_non_admin_cannot_create_department(self) -> None:
        """Doctor role cannot create a department (403)."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        payload = {"name": "Pediatrics", "code": "PED"}
        res = await self.client.post("/api/v1/departments", json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 403)

    # ── Doctors & Availability ───────────────────────────────────────────────

    async def test_admin_provision_doctor(self) -> None:
        """Admin provisions a new Doctor account and profile."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()
        # Department lookup succeeds
        def find_one_side_effect(query):
            if "department_id" in query:
                return self.dept_dict
            return None

        self.mock_db["departments"].find_one.side_effect = find_one_side_effect
        self.mock_db["users"].find_one.side_effect = lambda q: self.admin_user.to_mongo_dict() if q.get("user_id") == self.admin_user.user_id else None

        payload = {
            "email": "newdoctor@clinixai.com",
            "full_name": "Dr. Alice",
            "first_name": "Alice",
            "last_name": "Doctor",
            "department_id": "DEP-2026-CARD",
            "specialization": "Cardiology",
        }
        res = await self.client.post("/api/v1/doctors", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["email"], "newdoctor@clinixai.com")

    async def test_calculate_doctor_availability(self) -> None:
        """Computes doctor slot availability for a future date."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        self.mock_db["appointments"].find.return_value = mock_cursor

        res = await self.client.get("/api/v1/doctors/DOC-2026-00001/availability?date=2028-10-15")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["doctor_id"], "DOC-2026-00001")
        self.assertGreater(data["total_available"], 0)

    # ── Hospital Staff ───────────────────────────────────────────────────────

    async def test_admin_provision_staff(self) -> None:
        """Admin provisions a new Hospital Staff account."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()
        self.mock_db["users"].find_one.side_effect = lambda q: self.admin_user.to_mongo_dict() if q.get("user_id") == self.admin_user.user_id else None

        payload = {
            "email": "newstaff@clinixai.com",
            "full_name": "Bob Staff",
            "first_name": "Bob",
            "last_name": "Staff",
            "job_title": "Receptionist",
        }
        res = await self.client.post("/api/v1/staff", json=payload, headers=self.admin_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["email"], "newstaff@clinixai.com")

    # ── Appointments, Check-In, & Queue ──────────────────────────────────────

    async def test_patient_book_appointment_and_double_booking_prevention(self) -> None:
        """Verifies appointment booking and double booking protection (409 Conflict)."""
        # DB mocks for booking setup
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = self.patient_dict
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["departments"].find_one.return_value = self.dept_dict

        mock_cursor = MagicMock()
        mock_cursor.to_list = AsyncMock(return_value=[])
        self.mock_db["appointments"].find.return_value = mock_cursor
        
        # First booking attempt succeeds
        self.mock_db["appointments"].find_one.return_value = None

        payload = {
            "doctor_id": "DOC-2026-00001",
            "department_id": "DEP-2026-CARD",
            "appointment_date": "2028-10-15",
            "start_time": "09:00",
            "reason": "Routine Checkup",
        }
        res = await self.client.post("/api/v1/appointments", json=payload, headers=self.patient_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["status"], "scheduled")

        # Second booking attempt on same slot fails with 409 Conflict
        self.mock_db["appointments"].find_one.return_value = {"appointment_id": "APT-2028-EXISTING"}
        res_conflict = await self.client.post("/api/v1/appointments", json=payload, headers=self.patient_headers)
        self.assertEqual(res_conflict.status_code, 409)

    async def test_confirm_appointment_workflow(self) -> None:
        """Doctor confirms a scheduled appointment."""
        apt_dict = {
            "appointment_id": "APT-2026-TEST01",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-00001",
            "department_id": "DEP-2026-CARD",
            "appointment_date": "2028-10-15",
            "start_time": "09:00",
            "end_time": "09:30",
            "status": "scheduled",
            "appointment_type": "new_consultation",
            "booking_source": "patient",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["appointments"].find_one.return_value = apt_dict

        res = await self.client.post("/api/v1/appointments/APT-2026-TEST01/confirm", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)

    async def test_complete_appointment_workflow(self) -> None:
        """Doctor completes an active appointment."""
        apt_dict = {
            "appointment_id": "APT-2026-TEST02",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-00001",
            "department_id": "DEP-2026-CARD",
            "appointment_date": "2028-10-15",
            "start_time": "09:00",
            "end_time": "09:30",
            "status": "in_consultation",
            "appointment_type": "new_consultation",
            "booking_source": "patient",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["appointments"].find_one.return_value = apt_dict

        res = await self.client.post("/api/v1/appointments/APT-2026-TEST02/complete", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)

    async def test_status_transition_validation_and_rbac(self) -> None:
        """Patient cannot transition appointment to completed directly (403/422)."""
        apt_dict = {
            "appointment_id": "APT-2026-TEST03",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-00001",
            "department_id": "DEP-2026-CARD",
            "appointment_date": "2028-10-15",
            "start_time": "09:00",
            "end_time": "09:30",
            "status": "scheduled",
            "appointment_type": "new_consultation",
            "booking_source": "patient",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = self.patient_dict
        self.mock_db["appointments"].find_one.return_value = apt_dict

        payload = {"status": "completed"}
        res = await self.client.patch("/api/v1/appointments/APT-2026-TEST03/status", json=payload, headers=self.patient_headers)
        self.assertIn(res.status_code, (400, 403, 422))


if __name__ == "__main__":
    unittest.main()

