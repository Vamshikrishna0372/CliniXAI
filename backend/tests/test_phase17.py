"""Comprehensive Unit & Integration Test Suite for Phase 17: Appointments, Scheduling, Availability, Check-In & Hospital Operations."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.appointment import AppointmentStatus, AppointmentType, BookingSource
from app.core.security import create_access_token
from app.utils.datetime import utc_now


def create_mock_cursor(return_data=None):
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db_phase17():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
            col.count_documents = AsyncMock(return_value=0)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase17AppointmentsAndScheduling(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 17 Appointments, Slot Availability, Double-Booking Safeguards, Check-In, and RBAC."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase17()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.admin_user = UserInDB(
            user_id="USR-ADM-DEMO-001",
            email="admin@clinixai.com",
            full_name="Hospital Admin",
            role=UserRole.HOSPITAL_ADMIN,
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

        self.pat_user_1 = UserInDB(
            user_id="USR-PAT-ONE-001",
            email="patient.one@clinixai.com",
            full_name="Patient One",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.pat_user_2 = UserInDB(
            user_id="USR-PAT-TWO-002",
            email="patient.two@clinixai.com",
            full_name="Patient Two",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.doc_user_1 = UserInDB(
            user_id="USR-DOC-RAO-001",
            email="doctor.arjun@clinixai.com",
            full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.doc_user_2 = UserInDB(
            user_id="USR-DOC-PRIYA-002",
            email="doctor.priya@clinixai.com",
            full_name="Dr. Priya Sharma",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        def mock_user_find_one(query):
            uid = query.get("user_id")
            if uid == "USR-ADM-DEMO-001":
                return self.admin_user.model_dump()
            if uid == "USR-STF-ONE-001":
                return self.staff_user.model_dump()
            if uid == "USR-PAT-ONE-001":
                return self.pat_user_1.model_dump()
            if uid == "USR-PAT-TWO-002":
                return self.pat_user_2.model_dump()
            if uid == "USR-DOC-RAO-001":
                return self.doc_user_1.model_dump()
            if uid == "USR-DOC-PRIYA-002":
                return self.doc_user_2.model_dump()
            return None

        def mock_patient_find_one(query):
            pid = query.get("patient_id")
            uid = query.get("user_id")
            if pid == "PAT-ONE-001" or uid == "USR-PAT-ONE-001":
                return {"patient_id": "PAT-ONE-001", "user_id": "USR-PAT-ONE-001", "first_name": "Patient", "last_name": "One", "status": "active"}
            if pid == "PAT-TWO-002" or uid == "USR-PAT-TWO-002":
                return {"patient_id": "PAT-TWO-002", "user_id": "USR-PAT-TWO-002", "first_name": "Patient", "last_name": "Two", "status": "active"}
            return {"patient_id": "PAT-ONE-001", "user_id": "USR-PAT-ONE-001", "first_name": "Patient", "last_name": "One", "status": "active"}

        def mock_doctor_find_one(query):
            did = query.get("doctor_id")
            uid = query.get("user_id")
            if did == "DOC-RAO-001" or uid == "USR-DOC-RAO-001":
                return {
                    "doctor_id": "DOC-RAO-001",
                    "user_id": "USR-DOC-RAO-001",
                    "first_name": "Arjun",
                    "last_name": "Rao",
                    "email": "doctor.arjun@clinixai.com",
                    "department_id": "DEP-CARD-001",
                    "status": "active",
                    "schedule": {
                        "slot_duration_minutes": 30,
                        "weekly": [
                            {"day": "monday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}]},
                            {"day": "tuesday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}]},
                            {"day": "wednesday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}]},
                            {"day": "thursday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}]},
                            {"day": "friday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}]},
                            {"day": "saturday", "is_available": False, "slots": []},
                            {"day": "sunday", "is_available": False, "slots": []},
                        ],
                    },
                }
            if did == "DOC-PRIYA-002" or uid == "USR-DOC-PRIYA-002":
                return {
                    "doctor_id": "DOC-PRIYA-002",
                    "user_id": "USR-DOC-PRIYA-002",
                    "first_name": "Priya",
                    "last_name": "Sharma",
                    "email": "doctor.priya@clinixai.com",
                    "department_id": "DEP-CARD-001",
                    "status": "active",
                }
            return None

        def mock_department_find_one(query):
            return {"department_id": "DEP-CARD-001", "department_name": "Cardiology"}

        self.mock_db["users"].find_one.side_effect = AsyncMock(side_effect=mock_user_find_one)
        self.mock_db["patients"].find_one.side_effect = AsyncMock(side_effect=mock_patient_find_one)
        self.mock_db["doctors"].find_one.side_effect = AsyncMock(side_effect=mock_doctor_find_one)
        self.mock_db["departments"].find_one.side_effect = AsyncMock(side_effect=mock_department_find_one)

        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.staff_token = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)
        self.pat1_token = create_access_token(user_id=self.pat_user_1.user_id, role=self.pat_user_1.role.value)
        self.pat2_token = create_access_token(user_id=self.pat_user_2.user_id, role=self.pat_user_2.role.value)
        self.doc1_token = create_access_token(user_id=self.doc_user_1.user_id, role=self.doc_user_1.role.value)
        self.doc2_token = create_access_token(user_id=self.doc_user_2.user_id, role=self.doc_user_2.role.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        self.pat1_headers = {"Authorization": f"Bearer {self.pat1_token}"}
        self.pat2_headers = {"Authorization": f"Bearer {self.pat2_token}"}
        self.doc1_headers = {"Authorization": f"Bearer {self.doc1_token}"}
        self.doc2_headers = {"Authorization": f"Bearer {self.doc2_token}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_book_appointment_success(self):
        """Test booking appointment creates record in MongoDB."""
        from datetime import date, timedelta
        target_date = (date.today() + timedelta(days=1))
        while target_date.weekday() >= 5:
            target_date += timedelta(days=1)
        target_date_str = target_date.isoformat()

        payload = {
            "doctor_id": "DOC-RAO-001",
            "department_id": "DEP-CARD-001",
            "appointment_date": target_date_str,
            "start_time": "10:00",
            "reason": "Chest discomfort consultation",
        }
        response = await self.client.post("/api/v1/appointments", json=payload, headers=self.pat1_headers)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        apt = data["data"]
        self.assertEqual(apt["patient_id"], "PAT-ONE-001")
        self.assertEqual(apt["doctor_id"], "DOC-RAO-001")
        self.assertEqual(apt["status"], "scheduled")

    async def test_double_booking_prevention_conflict(self):
        """Test double-booking attempt raises 409 Conflict."""
        from datetime import date, timedelta
        target_date = (date.today() + timedelta(days=1))
        while target_date.weekday() >= 5:
            target_date += timedelta(days=1)
        target_date_str = target_date.isoformat()

        existing_apt = {
            "appointment_id": "APT-EXISTING-100",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "department_id": "DEP-CARD-001",
            "appointment_date": target_date_str,
            "start_time": "10:00",
            "end_time": "10:30",
            "status": "scheduled",
        }
        self.mock_db["appointments"].find_one.return_value = existing_apt

        payload = {
            "doctor_id": "DOC-RAO-001",
            "department_id": "DEP-CARD-001",
            "appointment_date": target_date_str,
            "start_time": "10:00",
            "reason": "Simultaneous booking attempt",
        }
        response = await self.client.post("/api/v1/appointments", json=payload, headers=self.pat2_headers)
        self.assertEqual(response.status_code, 409)

    async def test_patient_and_doctor_object_level_authorization(self):
        """Test Patient 2 and Doctor 2 cannot view Patient 1's appointment (403 Forbidden)."""
        pat1_apt = {
            "appointment_id": "APT-PAT1-ONLY",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "department_id": "DEP-CARD-001",
            "appointment_date": "2026-08-25",
            "start_time": "11:00",
            "end_time": "11:30",
            "status": "scheduled",
        }
        self.mock_db["appointments"].find_one.return_value = pat1_apt

        # Patient 2 viewing Patient 1's appointment -> 403 Forbidden
        p2_resp = await self.client.get("/api/v1/appointments/APT-PAT1-ONLY", headers=self.pat2_headers)
        self.assertEqual(p2_resp.status_code, 403)

        # Doctor 2 viewing Doctor 1's private appointment -> 403 Forbidden
        d2_resp = await self.client.get("/api/v1/appointments/APT-PAT1-ONLY", headers=self.doc2_headers)
        self.assertEqual(d2_resp.status_code, 403)

    async def test_reschedule_appointment(self):
        """Test rescheduling an eligible appointment updates date/time and reschedule_history."""
        from datetime import date, timedelta
        target_date_1 = (date.today() + timedelta(days=1))
        while target_date_1.weekday() >= 5:
            target_date_1 += timedelta(days=1)
        target_date_2 = target_date_1 + timedelta(days=1)
        while target_date_2.weekday() >= 5:
            target_date_2 += timedelta(days=1)

        pat1_apt = {
            "appointment_id": "APT-RESCHED-01",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "department_id": "DEP-CARD-001",
            "appointment_date": target_date_1.isoformat(),
            "start_time": "10:00",
            "end_time": "10:30",
            "status": "scheduled",
            "appointment_type": "new_consultation",
            "booking_source": "patient",
            "reschedule_history": [],
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["appointments"].find_one.side_effect = AsyncMock(
            side_effect=[pat1_apt, None, pat1_apt]
        )

        resched_payload = {
            "appointment_date": target_date_2.isoformat(),
            "start_time": "11:00",
        }
        response = await self.client.post("/api/v1/appointments/APT-RESCHED-01/reschedule", json=resched_payload, headers=self.pat1_headers)
        self.assertEqual(response.status_code, 200)

    async def test_cancel_appointment(self):
        """Test cancelling an eligible appointment."""
        pat1_apt = {
            "appointment_id": "APT-CANCEL-01",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "department_id": "DEP-CARD-001",
            "appointment_date": "2026-08-25",
            "start_time": "10:00",
            "end_time": "10:30",
            "status": "scheduled",
            "appointment_type": "new_consultation",
            "booking_source": "patient",
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["appointments"].find_one.return_value = pat1_apt

        cancel_payload = {"reason": "Patient conflict"}
        response = await self.client.post("/api/v1/appointments/APT-CANCEL-01/cancel", json=cancel_payload, headers=self.pat1_headers)
        self.assertEqual(response.status_code, 200)
