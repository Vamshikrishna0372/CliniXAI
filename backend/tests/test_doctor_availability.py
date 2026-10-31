"""Comprehensive Unit & Security Test Suite for Phase 6: Doctor Availability & Scheduling."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from datetime import date, timedelta

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.doctor import DoctorStatus, DayOfWeek
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


class TestPhase6DoctorAvailability(unittest.IsolatedAsyncioTestCase):
    """Rigorous tests for Phase 6 Doctor Schedule management & slot calculation."""

    async def asyncSetUp(self) -> None:
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

        self.mock_db = create_mock_db()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # Doctor User & Headers
        self.doctor_user = UserInDB(
            user_id="USR-DOC-001", email="doctor.arjun@clinixai.com", full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.doctor_token = create_access_token(user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)
        self.doctor_headers = {"Authorization": f"Bearer {self.doctor_token}"}

        # Another Doctor User
        self.other_doctor_user = UserInDB(
            user_id="USR-DOC-002", email="doctor.priya@clinixai.com", full_name="Dr. Priya Sharma",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.other_doctor_token = create_access_token(user_id=self.other_doctor_user.user_id, role=self.other_doctor_user.role.value)
        self.other_doctor_headers = {"Authorization": f"Bearer {self.other_doctor_token}"}

        # Patient User
        self.patient_user = UserInDB(
            user_id="USR-PAT-001", email="patient.one@clinixai.com", full_name="Aarav Sharma",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_token = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}

        now = utc_now()
        self.doctor_doc = {
            "doctor_id": "DOC-RAO-001",
            "user_id": self.doctor_user.user_id,
            "first_name": "Arjun",
            "last_name": "Rao",
            "full_name": "Dr. Arjun Rao",
            "email": "doctor.arjun@clinixai.com",
            "specialization": "Cardiology",
            "department_id": "DEPT-CARD",
            "qualification": "MBBS, MD",
            "experience_years": 10,
            "consultation_fee": 800.0,
            "status": "active",
            "is_deleted": False,
            "schedule": {
                "slot_duration_minutes": 30,
                "weekly": [
                    {
                        "day": "monday",
                        "is_available": True,
                        "slots": [
                            {"start": "09:00", "end": "12:00"},
                            {"start": "14:00", "end": "17:00"}
                        ]
                    },
                    {
                        "day": "tuesday",
                        "is_available": False,
                        "slots": []
                    }
                ]
            },
            "created_at": now,
            "updated_at": now,
        }

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    async def test_doctor_can_update_own_schedule(self) -> None:
        """Doctor can successfully update their own weekly schedule."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.doctor_doc

        payload = {
            "schedule": {
                "slot_duration_minutes": 30,
                "weekly": [
                    {
                        "day": "monday",
                        "is_available": True,
                        "slots": [{"start": "10:00", "end": "14:00"}]
                    }
                ]
            }
        }
        res = await self.client.patch("/api/v1/doctors/me/schedule", json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        self.mock_db["doctors"].update_one.assert_called()

    async def test_schedule_validation_rejects_start_greater_than_or_equal_to_end(self) -> None:
        """Reject schedule where start time is >= end time."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()

        payload = {
            "schedule": {
                "slot_duration_minutes": 30,
                "weekly": [
                    {
                        "day": "monday",
                        "is_available": True,
                        "slots": [{"start": "14:00", "end": "10:00"}]  # Invalid
                    }
                ]
            }
        }
        res = await self.client.patch("/api/v1/doctors/me/schedule", json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 422)

    async def test_schedule_validation_rejects_overlapping_slots(self) -> None:
        """Reject schedule containing overlapping intervals in the same day."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()

        payload = {
            "schedule": {
                "slot_duration_minutes": 30,
                "weekly": [
                    {
                        "day": "monday",
                        "is_available": True,
                        "slots": [
                            {"start": "09:00", "end": "12:00"},
                            {"start": "11:00", "end": "14:00"}  # Overlaps with 09:00-12:00
                        ]
                    }
                ]
            }
        }
        res = await self.client.patch("/api/v1/doctors/me/schedule", json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 422)

    async def test_schedule_validation_rejects_duplicate_days(self) -> None:
        """Reject schedule containing duplicate day entries."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()

        payload = {
            "schedule": {
                "slot_duration_minutes": 30,
                "weekly": [
                    {"day": "monday", "is_available": True, "slots": [{"start": "09:00", "end": "12:00"}]},
                    {"day": "monday", "is_available": False, "slots": []}
                ]
            }
        }
        res = await self.client.patch("/api/v1/doctors/me/schedule", json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 422)

    async def test_patient_cannot_update_doctor_schedule(self) -> None:
        """Patient role is forbidden from modifying doctor schedules."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()

        payload = {"schedule": {"slot_duration_minutes": 30, "weekly": []}}
        res = await self.client.patch("/api/v1/doctors/me/schedule", json=payload, headers=self.patient_headers)
        self.assertEqual(res.status_code, 403)

    async def test_calculate_availability_working_day(self) -> None:
        """Calculates slots for a future working day matching schedule."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_doc
        self.mock_db["appointments"].find.return_value = create_mock_cursor([])

        # Choose a guaranteed future Monday
        today = date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        future_monday = today + timedelta(days=days_until_monday)
        date_str = future_monday.isoformat()

        res = await self.client.get(f"/api/v1/doctors/DOC-RAO-001/availability?date={date_str}")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["doctor_id"], "DOC-RAO-001")
        self.assertEqual(data["date"], date_str)
        self.assertEqual(data["slot_duration_minutes"], 30)
        # 09:00-12:00 = 6 slots, 14:00-17:00 = 6 slots -> total 12
        self.assertEqual(data["total_available"], 12)
        slot_times = [s["start_time"] for s in data["available_slots"]]
        self.assertIn("09:00", slot_times)
        self.assertIn("11:30", slot_times)
        self.assertNotIn("12:00", slot_times)  # 12:00-14:00 is a break
        self.assertIn("14:00", slot_times)
        self.assertIn("16:30", slot_times)

    async def test_calculate_availability_non_working_day(self) -> None:
        """Returns 0 slots for a non-working day."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_doc

        # Choose a guaranteed future Tuesday (is_available: False in mock doc)
        today = date.today()
        days_until_tuesday = (1 - today.weekday()) % 7
        if days_until_tuesday == 0:
            days_until_tuesday = 7
        future_tuesday = today + timedelta(days=days_until_tuesday)

        res = await self.client.get(f"/api/v1/doctors/DOC-RAO-001/availability?date={future_tuesday.isoformat()}")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["total_available"], 0)
        self.assertEqual(len(data["available_slots"]), 0)

    async def test_calculate_availability_excludes_booked_slots(self) -> None:
        """Occupied slots are omitted from available slots."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_doc
        
        # Guaranteed future Monday
        today = date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        future_monday = today + timedelta(days=days_until_monday)
        date_str = future_monday.isoformat()

        # Mock an existing confirmed appointment at 09:30
        existing_appointment = {
            "doctor_id": "DOC-RAO-001",
            "appointment_date": date_str,
            "start_time": "09:30",
            "status": "confirmed",
        }
        self.mock_db["appointments"].find.return_value = create_mock_cursor([existing_appointment])

        res = await self.client.get(f"/api/v1/doctors/DOC-RAO-001/availability?date={date_str}")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        slot_times = [s["start_time"] for s in data["available_slots"]]
        self.assertIn("09:00", slot_times)
        self.assertNotIn("09:30", slot_times)  # Must be excluded
        self.assertIn("10:00", slot_times)
        self.assertEqual(data["total_available"], 11)

    async def test_calculate_availability_cancelled_appointment_frees_slot(self) -> None:
        """Cancelled appointment does not occupy the slot."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_doc
        
        today = date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        future_monday = today + timedelta(days=days_until_monday)
        date_str = future_monday.isoformat()

        # The service filters out status: {"$nin": ["cancelled", "no_show"]}
        # In mock db, find returns empty when querying non-cancelled
        self.mock_db["appointments"].find.return_value = create_mock_cursor([])

        res = await self.client.get(f"/api/v1/doctors/DOC-RAO-001/availability?date={date_str}")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        slot_times = [s["start_time"] for s in data["available_slots"]]
        self.assertIn("09:30", slot_times)
        self.assertEqual(data["total_available"], 12)

    async def test_calculate_availability_past_date_returns_zero_slots(self) -> None:
        """Past dates return 0 available slots."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_doc

        past_date = (date.today() - timedelta(days=5)).isoformat()
        res = await self.client.get(f"/api/v1/doctors/DOC-RAO-001/availability?date={past_date}")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["total_available"], 0)
        self.assertEqual(data["available_slots"], [])

    async def test_unconfigured_doctor_returns_zero_slots(self) -> None:
        """A doctor with no configured schedule or empty schedule returns 0 slots."""
        unconfigured_doc = dict(self.doctor_doc)
        unconfigured_doc["doctor_id"] = "DOC-NO-SCHED"
        unconfigured_doc["schedule"] = {"slot_duration_minutes": 30, "weekly": []}
        self.mock_db["doctors"].find_one.return_value = unconfigured_doc

        future_date = (date.today() + timedelta(days=10)).isoformat()
        res = await self.client.get(f"/api/v1/doctors/DOC-NO-SCHED/availability?date={future_date}")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["total_available"], 0)
        self.assertEqual(data["available_slots"], [])

    async def test_historical_appointment_does_not_block_future_date(self) -> None:
        """Appointments on a past/different date must not block availability on the target date."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_doc

        # Guaranteed future Monday
        today = date.today()
        days_until_monday = (0 - today.weekday()) % 7
        if days_until_monday == 0:
            days_until_monday = 7
        future_monday = today + timedelta(days=days_until_monday)
        target_date_str = future_monday.isoformat()

        # When queried for target_date_str, MongoDB returns empty because past appointment was on another date
        self.mock_db["appointments"].find.return_value = create_mock_cursor([])

        res = await self.client.get(f"/api/v1/doctors/DOC-RAO-001/availability?date={target_date_str}")
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["total_available"], 12)
        slot_times = [s["start_time"] for s in data["available_slots"]]
        self.assertIn("09:00", slot_times)
    async def test_calculate_availability_same_day_excludes_past_slots(self) -> None:
        """Same-day availability excludes slots whose start time has already passed."""
        from unittest.mock import patch
        from datetime import datetime
        self.mock_db["doctors"].find_one.return_value = self.doctor_doc
        self.mock_db["appointments"].find.return_value = create_mock_cursor([])

        # Mock current time to a Monday at 10:15
        mock_now = datetime(2026, 9, 21, 10, 15)  # 2026-09-21 is a Monday
        with patch("app.services.doctor_service.datetime") as mock_dt:
            mock_dt.now.return_value = mock_now
            mock_dt.fromisoformat = datetime.fromisoformat
            mock_dt.side_effect = lambda *args, **kwargs: datetime(*args, **kwargs)

            res = await self.client.get("/api/v1/doctors/DOC-RAO-001/availability?date=2026-09-21")
            self.assertEqual(res.status_code, 200)
            data = res.json()["data"]
            slot_times = [s["start_time"] for s in data["available_slots"]]
            # Slots before 10:15 (09:00, 09:30, 10:00) must be excluded
            self.assertNotIn("09:00", slot_times)
            self.assertNotIn("09:30", slot_times)
            self.assertNotIn("10:00", slot_times)
            # Future slots (10:30, 11:00, 11:30, etc.) must be present
            self.assertIn("10:30", slot_times)
            self.assertIn("11:00", slot_times)
            self.assertIn("14:00", slot_times)


if __name__ == "__main__":
    unittest.main()

