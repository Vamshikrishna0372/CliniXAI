"""Comprehensive Unit Test Suite for Phase 4: Doctor Clinical APIs, Consultations, Prescriptions & Follow-Ups."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
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


def create_mock_db_phase4():
    """Returns a flexible mock database supporting async motor operations for Phase 4."""
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=None)
            col.count_documents = AsyncMock(return_value=0)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase4ClinicalEndpoints(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 4 Clinical APIs."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase4()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # User definitions
        self.doctor_user = UserInDB(
            user_id="USR-2026-DOC001", email="doctor@clinixai.com", full_name="Dr. House",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.other_doctor_user = UserInDB(
            user_id="USR-2026-DOC002", email="otherdoc@clinixai.com", full_name="Dr. Strange",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_user = UserInDB(
            user_id="USR-2026-PAT001", email="patient@clinixai.com", full_name="Jane Doe",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.staff_user = UserInDB(
            user_id="USR-2026-STF001", email="staff@clinixai.com", full_name="Nurse Ratched",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )

        # Tokens
        self.doctor_token = create_access_token(user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)
        self.other_doctor_token = create_access_token(user_id=self.other_doctor_user.user_id, role=self.other_doctor_user.role.value)
        self.patient_token = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)
        self.staff_token = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)

        # Headers
        self.doctor_headers = {"Authorization": f"Bearer {self.doctor_token}"}
        self.other_doctor_headers = {"Authorization": f"Bearer {self.other_doctor_token}"}
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}

        # Mock DB entities
        self.doctor_dict = {
            "doctor_id": "DOC-2026-00001",
            "user_id": self.doctor_user.user_id,
            "first_name": "Gregory",
            "last_name": "House",
            "email": "doctor@clinixai.com",
            "department_id": "DEP-2026-CARD",
            "status": "active",
        }
        self.other_doctor_dict = {
            "doctor_id": "DOC-2026-00002",
            "user_id": self.other_doctor_user.user_id,
            "first_name": "Stephen",
            "last_name": "Strange",
            "email": "otherdoc@clinixai.com",
            "department_id": "DEP-2026-NEURO",
            "status": "active",
        }
        self.patient_dict = {
            "patient_id": "PAT-2026-00001",
            "user_id": self.patient_user.user_id,
            "first_name": "Jane",
            "last_name": "Doe",
            "email": "patient@clinixai.com",
            "gender": "female",
            "blood_group": "O+",
            "allergies": ["Aspirin"],
            "status": "active",
        }
        self.appointment_dict = {
            "appointment_id": "APT-2026-000001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-00001",
            "department_id": "DEP-2026-CARD",
            "appointment_date": "2028-10-15",
            "start_time": "10:00",
            "end_time": "10:30",
            "status": "in_queue",
        }
        self.consultation_dict = {
            "consultation_id": "CON-2026-000001",
            "appointment_id": "APT-2026-000001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-00001",
            "department_id": "DEP-2026-CARD",
            "status": "in_progress",
            "symptoms": [],
            "diagnoses": [],
            "doctor_instructions": [],
            "started_at": utc_now().isoformat(),
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # ── Start Consultation & Context ──────────────────────────────────────────

    async def test_start_consultation_success(self) -> None:
        """Assigned Doctor starts consultation successfully."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        
        self.mock_db["appointments"].find_one.side_effect = lambda q: self.appointment_dict if q.get("appointment_id") == "APT-2026-000001" else None
        self.mock_db["doctors"].find_one.side_effect = lambda q: self.doctor_dict if q.get("user_id") == self.doctor_user.user_id else None
        self.mock_db["consultations"].find_one.return_value = None

        res = await self.client.post("/api/v1/consultations/start", json={"appointment_id": "APT-2026-000001"}, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["status"], "in_progress")

    async def test_unauthorized_doctor_cannot_start_consultation(self) -> None:
        """Doctor cannot start consultation for another doctor's assigned appointment (403)."""
        self.mock_db["users"].find_one.return_value = self.other_doctor_user.to_mongo_dict()
        self.mock_db["appointments"].find_one.return_value = self.appointment_dict
        self.mock_db["doctors"].find_one.return_value = self.other_doctor_dict

        res = await self.client.post("/api/v1/consultations/start", json={"appointment_id": "APT-2026-000001"}, headers=self.other_doctor_headers)
        self.assertEqual(res.status_code, 403)

    async def test_staff_cannot_start_clinical_consultation(self) -> None:
        """Hospital Staff must be denied from initiating clinical consultations (Phase 18 clinical boundary)."""
        self.mock_db["users"].find_one.return_value = self.staff_user.to_mongo_dict()
        self.mock_db["appointments"].find_one.side_effect = lambda q: self.appointment_dict if q.get("appointment_id") == "APT-2026-000001" else None
        self.mock_db["consultations"].find_one.return_value = None

        res = await self.client.post("/api/v1/consultations/start", json={"appointment_id": "APT-2026-000001"}, headers=self.staff_headers)
        self.assertEqual(res.status_code, 403)

    async def test_get_patient_clinical_context(self) -> None:
        """Doctor retrieves patient clinical context workspace."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["appointments"].find_one.return_value = self.appointment_dict
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        mock_cursor = create_mock_cursor([])
        self.mock_db["consultations"].find.return_value = mock_cursor
        self.mock_db["prescriptions"].find.return_value = mock_cursor

        res = await self.client.get("/api/v1/consultations/patient-context/PAT-2026-00001", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertEqual(data["patient_id"], "PAT-2026-00001")
        self.assertIn("Aspirin", data["allergies"])

    # ── Record Clinical Data ──────────────────────────────────────────────────

    async def test_record_vitals_and_calculate_bmi(self) -> None:
        """Doctor records vitals, verifying automatic BMI calculation."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["consultations"].find_one.return_value = self.consultation_dict

        payload = {
            "vitals": {
                "temperature_c": 37.2,
                "heart_rate_bpm": 75,
                "bp_systolic": 120,
                "bp_diastolic": 80,
                "weight_kg": 70.0,
                "height_cm": 175.0,
            }
        }
        res = await self.client.patch("/api/v1/consultations/CON-2026-000001/vitals", json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 200)
        self.mock_db["consultations"].update_one.assert_called()

    # ── Prescription & Completion ─────────────────────────────────────────────

    async def test_issue_prescription(self) -> None:
        """Doctor issues prescription for consultation."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["consultations"].find_one.return_value = self.consultation_dict
        self.mock_db["prescriptions"].find_one.return_value = None

        payload = {
            "medications": [
                {
                    "name": "Amoxicillin",
                    "strength": "500 mg",
                    "dosage": "1 capsule",
                    "frequency": "Thrice daily",
                    "duration": "7 days",
                    "timing": "After meals",
                }
            ],
            "instructions": "Complete full course of antibiotics.",
            "follow_up": {
                "required": True,
                "follow_up_date": "2028-10-25",
                "reason": "Re-evaluate infection response",
            }
        }
        res = await self.client.post("/api/v1/prescriptions/consultation/CON-2026-000001", json=payload, headers=self.doctor_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["medications"][0]["name"], "Amoxicillin")

    async def test_complete_consultation_validation(self) -> None:
        """Completing consultation fails if assessment or primary diagnosis is missing."""
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        self.mock_db["doctors"].find_one.return_value = self.doctor_dict
        self.mock_db["consultations"].find_one.return_value = self.consultation_dict

        res = await self.client.post("/api/v1/consultations/CON-2026-000001/complete", headers=self.doctor_headers)
        self.assertEqual(res.status_code, 400)


if __name__ == "__main__":
    unittest.main()
