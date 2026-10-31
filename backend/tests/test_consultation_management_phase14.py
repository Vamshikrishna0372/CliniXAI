"""
Phase 14 Dedicated Test Suite:
Consultation Management, Lifecycle State Machine, Appointment Boundary,
Doctor Clinical Workspace, Note Ownership, Completion Validation,
Medical Record & AI Analysis Linkage, Optimistic Concurrency,
Audit Logging, Patient Visibility Boundary, and Snapshot Safety.
"""

import asyncio
import unittest
from datetime import datetime, timezone, timedelta, date
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.user import UserRole, AuthProvider, AccountStatus
from app.models.consultation import ConsultationStatus, SymptomSeverity, RiskLevel, DiagnosisType
from app.models.appointment import AppointmentStatus, AppointmentType, BookingSource
from app.core.security import create_access_token
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS, COLLECTION_AUDIT_LOGS,
    COLLECTION_MEDICAL_RECORDS, COLLECTION_AI_ANALYSES
)
from app.database.mongodb import db_manager, connect_to_mongo, save_in_memory_snapshot, restore_in_memory_snapshot
from app.utils.datetime import utc_now


class TestPhase14ConsultationManagementSuite(unittest.IsolatedAsyncioTestCase):
    """Phase 14 Comprehensive Test Suite for Consultation Management."""

    async def asyncSetUp(self):
        await connect_to_mongo()
        self.db = db_manager.db

        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        now = utc_now()

        # Doctor Arjun (Authorized Doctor)
        self.arjun_user_id = "USR-DOC-ARJUN-14"
        self.arjun_doc_id = "DOC-ARJUN-14"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.arjun_user_id},
            {"$set": {
                "user_id": self.arjun_user_id,
                "email": "dr.arjun.p14@clinixai.com",
                "full_name": "Dr. Arjun Rao",
                "role": UserRole.DOCTOR.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": self.arjun_doc_id},
            {"$set": {
                "doctor_id": self.arjun_doc_id,
                "user_id": self.arjun_user_id,
                "first_name": "Arjun",
                "last_name": "Rao",
                "email": "dr.arjun.p14@clinixai.com",
                "department_id": "DEPT-CARD",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Doctor Priya (Unauthorized / Independent Doctor)
        self.priya_user_id = "USR-DOC-PRIYA-14"
        self.priya_doc_id = "DOC-PRIYA-14"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.priya_user_id},
            {"$set": {
                "user_id": self.priya_user_id,
                "email": "dr.priya.p14@clinixai.com",
                "full_name": "Dr. Priya Sharma",
                "role": UserRole.DOCTOR.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": self.priya_doc_id},
            {"$set": {
                "doctor_id": self.priya_doc_id,
                "user_id": self.priya_user_id,
                "first_name": "Priya",
                "last_name": "Sharma",
                "email": "dr.priya.p14@clinixai.com",
                "department_id": "DEPT-NEUR",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Patient One
        self.pat1_user_id = "USR-PAT-ONE-14"
        self.pat1_id = "PAT-ONE-14"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.pat1_user_id},
            {"$set": {
                "user_id": self.pat1_user_id,
                "email": "patient1.p14@clinixai.com",
                "full_name": "Ramesh Patel",
                "role": UserRole.PATIENT.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": self.pat1_id},
            {"$set": {
                "patient_id": self.pat1_id,
                "user_id": self.pat1_user_id,
                "first_name": "Ramesh",
                "last_name": "Patel",
                "email": "patient1.p14@clinixai.com",
                "gender": "male",
                "date_of_birth": "1980-05-15",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Patient Two (Independent Patient)
        self.pat2_user_id = "USR-PAT-TWO-14"
        self.pat2_id = "PAT-TWO-14"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.pat2_user_id},
            {"$set": {
                "user_id": self.pat2_user_id,
                "email": "patient2.p14@clinixai.com",
                "full_name": "Sunita Verma",
                "role": UserRole.PATIENT.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": self.pat2_id},
            {"$set": {
                "patient_id": self.pat2_id,
                "user_id": self.pat2_user_id,
                "first_name": "Sunita",
                "last_name": "Verma",
                "email": "patient2.p14@clinixai.com",
                "gender": "female",
                "date_of_birth": "1985-08-20",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Hospital Staff
        self.staff_user_id = "USR-STAFF-14"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.staff_user_id},
            {"$set": {
                "user_id": self.staff_user_id,
                "email": "staff.p14@clinixai.com",
                "full_name": "Hospital Staff",
                "role": UserRole.HOSPITAL_STAFF.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Hospital Admin
        self.admin_user_id = "USR-ADMIN-14"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.admin_user_id},
            {"$set": {
                "user_id": self.admin_user_id,
                "email": "admin.p14@clinixai.com",
                "full_name": "Hospital Admin",
                "role": UserRole.HOSPITAL_ADMIN.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Generate JWT Auth Tokens
        self.arjun_token = create_access_token(user_id=self.arjun_user_id, role=UserRole.DOCTOR.value)
        self.arjun_headers = {"Authorization": f"Bearer {self.arjun_token}"}

        self.priya_token = create_access_token(user_id=self.priya_user_id, role=UserRole.DOCTOR.value)
        self.priya_headers = {"Authorization": f"Bearer {self.priya_token}"}

        self.pat1_token = create_access_token(user_id=self.pat1_user_id, role=UserRole.PATIENT.value)
        self.pat1_headers = {"Authorization": f"Bearer {self.pat1_token}"}

        self.pat2_token = create_access_token(user_id=self.pat2_user_id, role=UserRole.PATIENT.value)
        self.pat2_headers = {"Authorization": f"Bearer {self.pat2_token}"}

        self.staff_token = create_access_token(user_id=self.staff_user_id, role=UserRole.HOSPITAL_STAFF.value)
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}

        self.admin_token = create_access_token(user_id=self.admin_user_id, role=UserRole.HOSPITAL_ADMIN.value)
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

    async def asyncTearDown(self):
        await self.client.aclose()

    async def _create_test_appointment(
        self,
        appointment_id: str,
        patient_id: str,
        doctor_id: str,
        status: str = AppointmentStatus.CHECKED_IN.value
    ):
        """Helper to create test appointment in MongoDB."""
        await self.db[COLLECTION_CONSULTATIONS].delete_many({"appointment_id": appointment_id})
        now = utc_now()
        apt_doc = {
            "appointment_id": appointment_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
            "department_id": "DEPT-CARD",
            "appointment_date": date.today().isoformat(),
            "start_time": "10:00",
            "end_time": "10:30",
            "reason": "Test Clinical Consultation",
            "appointment_type": AppointmentType.NEW_CONSULTATION.value,
            "status": status,
            "booking_source": BookingSource.PATIENT.value,
            "created_at": now,
            "updated_at": now,
        }
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": appointment_id},
            {"$set": apt_doc},
            upsert=True
        )
        return apt_doc

    # =========================================================================
    # 1. Unauthenticated & Unauthorized Role Access
    # =========================================================================
    async def test_01_unauthenticated_access_returns_401(self):
        """Unauthenticated request must return 401."""
        res = await self.client.get("/api/v1/consultations")
        self.assertEqual(res.status_code, 401)

        res = await self.client.post("/api/v1/consultations/start/APT-FAKE-01")
        self.assertEqual(res.status_code, 401)

    async def test_02_patient_cannot_start_or_complete_consultation(self):
        """Patient role must be strictly forbidden from starting or completing consultation."""
        apt_id = "APT-P14-001"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        # Patient attempts to start consultation -> 403
        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.pat1_headers,
            json={"chief_complaint": "Self started"}
        )
        self.assertEqual(res.status_code, 403)

    async def test_03_staff_cannot_create_or_modify_clinical_notes(self):
        """Staff role cannot start consultation or modify doctor clinical notes."""
        apt_id = "APT-P14-002"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.staff_headers,
            json={"chief_complaint": "Staff started"}
        )
        self.assertEqual(res.status_code, 403)

    # =========================================================================
    # 2. Care Relationship Authorization & Cross-Doctor Isolation
    # =========================================================================
    async def test_04_unauthorized_doctor_denied_start_consultation(self):
        """Doctor Priya cannot start a consultation for Doctor Arjun's appointment."""
        apt_id = "APT-P14-003"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.priya_headers,
            json={"chief_complaint": "Unauthorized doctor start"}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("authorized", res.text.lower())

    async def test_05_authorized_doctor_starts_consultation_successfully(self):
        """Doctor Arjun starts consultation for his scheduled appointment."""
        apt_id = "APT-P14-004"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={
                "chief_complaint": "Occasional palpitations",
                "duration": "2 weeks"
            }
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]
        self.assertEqual(data["status"], ConsultationStatus.IN_PROGRESS.value)
        self.assertEqual(data["patient_id"], self.pat1_id)
        self.assertEqual(data["doctor_id"], self.arjun_doc_id)
        self.assertEqual(data["created_by"], self.arjun_user_id)
        self.assertIsNotNone(data["started_at"])

        # Check appointment status transitioned to in_consultation
        apt = await self.db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": apt_id})
        self.assertEqual(apt["status"], "in_consultation")

    # =========================================================================
    # 3. Duplicate Consultation Prevention & Concurrency Double-Start
    # =========================================================================
    async def test_06_duplicate_consultation_start_returns_existing(self):
        """Starting an already active consultation returns the existing active consultation without duplicating."""
        apt_id = "APT-P14-005"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res1 = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Initial complaint"}
        )
        self.assertEqual(res1.status_code, 201)
        cns_id_1 = res1.json()["data"]["consultation_id"]

        # Second attempt to start same appointment
        res2 = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Second attempt"}
        )
        self.assertIn(res2.status_code, [200, 201])
        cns_id_2 = res2.json()["data"]["consultation_id"]
        self.assertEqual(cns_id_1, cns_id_2)

        # Verify only 1 consultation exists in DB for this appointment
        count = await self.db[COLLECTION_CONSULTATIONS].count_documents({"appointment_id": apt_id})
        self.assertEqual(count, 1)

    async def test_07_concurrent_consultation_creation_protection(self):
        """Two concurrent start requests for the same appointment result in only 1 active consultation."""
        apt_id = "APT-P14-006"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res1, res2 = await asyncio.gather(
            self.client.post(f"/api/v1/consultations/start/{apt_id}", headers=self.arjun_headers, json={"chief_complaint": "Req 1"}),
            self.client.post(f"/api/v1/consultations/start/{apt_id}", headers=self.arjun_headers, json={"chief_complaint": "Req 2"}),
        )
        self.assertIn(res1.status_code, [200, 201])
        self.assertIn(res2.status_code, [200, 201])

        id1 = res1.json()["data"]["consultation_id"]
        id2 = res2.json()["data"]["consultation_id"]
        self.assertEqual(id1, id2)

        count = await self.db[COLLECTION_CONSULTATIONS].count_documents({"appointment_id": apt_id})
        self.assertEqual(count, 1)

    # =========================================================================
    # 4. Appointment Lifecycle Boundary (Cancelled & No-Show Blocked)
    # =========================================================================
    async def test_08_cannot_start_consultation_for_cancelled_appointment(self):
        """Starting consultation for a cancelled appointment is cleanly rejected (400)."""
        apt_id = "APT-P14-007"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id, status=AppointmentStatus.CANCELLED.value)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Cancelled appointment test"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("cancelled", res.text.lower())

    async def test_09_cannot_start_consultation_for_no_show_appointment(self):
        """Starting consultation for a no_show appointment is cleanly rejected (400)."""
        apt_id = "APT-P14-008"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id, status=AppointmentStatus.NO_SHOW.value)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "No-show test"}
        )
        self.assertEqual(res.status_code, 400)

    # =========================================================================
    # 5. Mass Assignment & Identity Spoofing Protection
    # =========================================================================
    async def test_10_mass_assignment_protection_on_creation(self):
        """Client-provided consultation_id, doctor_id, patient_id, and completed_at are ignored/server-derived."""
        apt_id = "APT-P14-009"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        malicious_payload = {
            "chief_complaint": "Spoof test",
            "consultation_id": "CONS-HACK-666",
            "doctor_id": "DOC-PRIYA-14",
            "patient_id": "PAT-TWO-14",
            "status": "completed",
            "completed_by": "USR-HACKER",
            "completed_at": "2099-01-01T00:00:00Z"
        }
        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json=malicious_payload
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]

        # Authoritative server values must be preserved
        self.assertNotEqual(data["consultation_id"], "CONS-HACK-666")
        self.assertEqual(data["doctor_id"], self.arjun_doc_id)
        self.assertEqual(data["patient_id"], self.pat1_id)
        self.assertEqual(data["status"], ConsultationStatus.IN_PROGRESS.value)
        self.assertIsNone(data.get("completed_at"))

    # =========================================================================
    # 6. Clinical Notes, Vitals, Symptoms, and Assessment Updates
    # =========================================================================
    async def test_11_clinical_notes_update_and_optimistic_concurrency(self):
        """Authorized doctor updates clinical notes, vitals, symptoms; version increments."""
        apt_id = "APT-P14-010"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Chest tightness", "duration": "3 days"}
        )
        cns = res.json()["data"]
        cns_id = cns["consultation_id"]
        initial_version = cns.get("version", 1)

        # Update clinical notes
        notes_res = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.arjun_headers,
            json={"clinical_notes": "Patient presents with mild chest discomfort on exertion. ECG sinus rhythm."}
        )
        self.assertEqual(notes_res.status_code, 200)
        cns_updated = notes_res.json()["data"]
        self.assertEqual(cns_updated["clinical_notes"], "Patient presents with mild chest discomfort on exertion. ECG sinus rhythm.")
        self.assertGreater(cns_updated["version"], initial_version)

        # Update symptoms
        sym_res = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/symptoms",
            headers=self.arjun_headers,
            json={"symptoms": [{"name": "Chest tightness", "severity": SymptomSeverity.MODERATE.value, "duration": "3 days"}]}
        )
        self.assertEqual(sym_res.status_code, 200)

        # Update assessment
        ass_res = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/assessment",
            headers=self.arjun_headers,
            json={
                "summary": "Stable angina symptoms, low risk of acute coronary syndrome.",
                "risk_level": RiskLevel.LOW.value
            }
        )
        self.assertEqual(ass_res.status_code, 200)

        # Update diagnoses
        diag_res = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/diagnoses",
            headers=self.arjun_headers,
            json={"diagnoses": [{"name": "Atypical Chest Pain", "type": DiagnosisType.PRIMARY.value, "code": "R07.9"}]}
        )
        self.assertEqual(diag_res.status_code, 200)

        # Update care plan
        care_res = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/care-plan",
            headers=self.arjun_headers,
            json={
                "care_plan": "Rest, avoid strenuous exercise for 1 week, daily walking 20 mins.",
                "follow_up_required": True,
                "follow_up_date": (date.today() + timedelta(days=7)).isoformat()
            }
        )
        self.assertEqual(care_res.status_code, 200)
        self.assertEqual(care_res.json()["data"]["care_plan"], "Rest, avoid strenuous exercise for 1 week, daily walking 20 mins.")
        self.assertTrue(care_res.json()["data"]["follow_up_required"])

    async def test_12_unauthorized_doctor_cannot_update_notes(self):
        """Doctor Priya cannot update Doctor Arjun's consultation notes."""
        apt_id = "APT-P14-011"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Notes test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Doctor Priya attempts update -> 403
        priya_res = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.priya_headers,
            json={"clinical_notes": "Malicious modification by Priya"}
        )
        self.assertEqual(priya_res.status_code, 403)

    # =========================================================================
    # 7. AI Analysis & Medical Record Linkage (Strict Cross-Patient Protection)
    # =========================================================================
    async def test_13_link_ai_analysis_same_patient_succeeds(self):
        """Authorized doctor links a valid AI analysis belonging to the same patient; AI data is immutable."""
        apt_id = "APT-P14-012"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Brain MRI consultation"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Create AI Analysis for Patient One
        now = utc_now()
        ai_id = "AI-P14-001"
        await self.db[COLLECTION_AI_ANALYSES].update_one(
            {"analysis_id": ai_id},
            {"$set": {
                "analysis_id": ai_id,
                "patient_id": self.pat1_id,
                "doctor_id": self.arjun_doc_id,
                "module_id": "BRAIN_MRI",
                "prediction": {"predicted_class": "notumor", "confidence": 0.95},
                "status": "completed",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        link_res = await self.client.post(
            f"/api/v1/consultations/{cns_id}/link-ai-analysis",
            headers=self.arjun_headers,
            json={"analysis_id": ai_id}
        )
        self.assertEqual(link_res.status_code, 200)
        self.assertIn(ai_id, link_res.json()["data"]["linked_ai_analysis_ids"])

        # Verify AI record immutability (prediction and confidence unchanged)
        ai_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": ai_id})
        self.assertEqual(ai_doc["prediction"]["predicted_class"], "notumor")
        self.assertEqual(ai_doc["prediction"]["confidence"], 0.95)

    async def test_14_cross_patient_ai_analysis_linkage_strictly_denied(self):
        """Attempting to link an AI analysis belonging to Patient Two into Patient One's consultation is rejected."""
        apt_id = "APT-P14-013"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "AI security test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Create AI Analysis for Patient TWO (different patient)
        now = utc_now()
        ai_pat2_id = "AI-P14-PAT2"
        await self.db[COLLECTION_AI_ANALYSES].update_one(
            {"analysis_id": ai_pat2_id},
            {"$set": {
                "analysis_id": ai_pat2_id,
                "patient_id": self.pat2_id,
                "module_id": "BRAIN_MRI",
                "prediction": {"predicted_class": "glioma", "confidence": 0.88},
                "status": "completed",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Attempt linking -> 403 or 422
        link_res = await self.client.post(
            f"/api/v1/consultations/{cns_id}/link-ai-analysis",
            headers=self.arjun_headers,
            json={"analysis_id": ai_pat2_id}
        )
        self.assertIn(link_res.status_code, [400, 403, 422])
        self.assertIn("patient", link_res.text.lower())

    async def test_15_cross_patient_medical_record_linkage_strictly_denied(self):
        """Attempting to link a medical record belonging to Patient Two into Patient One's consultation is rejected."""
        apt_id = "APT-P14-014"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Record security test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Medical Record for Patient TWO
        now = utc_now()
        mr_pat2_id = "MR-P14-PAT2"
        await self.db[COLLECTION_MEDICAL_RECORDS].update_one(
            {"record_id": mr_pat2_id},
            {"$set": {
                "record_id": mr_pat2_id,
                "patient_id": self.pat2_id,
                "title": "Lipid Profile Pat2",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        link_res = await self.client.post(
            f"/api/v1/consultations/{cns_id}/link-medical-record",
            headers=self.arjun_headers,
            json={"record_id": mr_pat2_id}
        )
        self.assertIn(link_res.status_code, [400, 403, 422])

    # =========================================================================
    # 8. Completion Lifecycle & Post-Completion Locking
    # =========================================================================
    async def test_16_completion_requires_assessment_and_diagnosis(self):
        """Consultation completion requires clinical assessment and at least one diagnosis."""
        apt_id = "APT-P14-015"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Completion test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Direct complete without assessment -> 400
        comp_res = await self.client.post(
            f"/api/v1/consultations/{cns_id}/complete",
            headers=self.arjun_headers
        )
        self.assertEqual(comp_res.status_code, 400)
        self.assertIn("assessment", comp_res.text.lower())

    async def test_17_successful_completion_lifecycle(self):
        """Consultation is completed successfully: status=COMPLETED, completed_by & completed_at recorded."""
        apt_id = "APT-P14-016"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Full cycle test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Add assessment & diagnosis
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/assessment",
            headers=self.arjun_headers,
            json={"summary": "Confirmed benign murmur.", "risk_level": RiskLevel.LOW.value}
        )
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/diagnoses",
            headers=self.arjun_headers,
            json={"diagnoses": [{"name": "Benign Murmur", "type": DiagnosisType.PRIMARY.value}]}
        )

        # Complete consultation
        comp_res = await self.client.post(
            f"/api/v1/consultations/{cns_id}/complete",
            headers=self.arjun_headers
        )
        self.assertEqual(comp_res.status_code, 200)
        cns = comp_res.json()["data"]
        self.assertEqual(cns["status"], ConsultationStatus.COMPLETED.value)
        self.assertEqual(cns["completed_by"], self.arjun_user_id)
        self.assertIsNotNone(cns["completed_at"])

        # Appointment status must be completed
        apt = await self.db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": apt_id})
        self.assertEqual(apt["status"], AppointmentStatus.COMPLETED.value)

    async def test_18_completed_consultation_is_clinically_locked(self):
        """After completion, updates to notes, symptoms, or diagnoses are strictly rejected (400)."""
        apt_id = "APT-P14-017"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Lock test"}
        )
        cns_id = res.json()["data"]["consultation_id"]
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/assessment",
            headers=self.arjun_headers,
            json={"summary": "Lock check summary.", "risk_level": RiskLevel.LOW.value}
        )
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/diagnoses",
            headers=self.arjun_headers,
            json={"diagnoses": [{"name": "Lock Check", "type": DiagnosisType.PRIMARY.value}]}
        )
        await self.client.post(f"/api/v1/consultations/{cns_id}/complete", headers=self.arjun_headers)

        # Attempt to update notes after completion -> 400
        patch_res = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.arjun_headers,
            json={"clinical_notes": "Post-completion alteration attempt"}
        )
        self.assertEqual(patch_res.status_code, 400)
        self.assertTrue(
            "finalized" in patch_res.text.lower() or
            "cannot be modified" in patch_res.text.lower() or
            "in_progress" in patch_res.text.lower()
        )

    async def test_19_duplicate_completion_is_cleanly_rejected(self):
        """Completing an already completed consultation is rejected (400)."""
        apt_id = "APT-P14-018"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Duplicate complete test"}
        )
        cns_id = res.json()["data"]["consultation_id"]
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/assessment",
            headers=self.arjun_headers,
            json={"summary": "Summary", "risk_level": RiskLevel.LOW.value}
        )
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/diagnoses",
            headers=self.arjun_headers,
            json={"diagnoses": [{"name": "Diag", "type": DiagnosisType.PRIMARY.value}]}
        )
        await self.client.post(f"/api/v1/consultations/{cns_id}/complete", headers=self.arjun_headers)

        # Second completion attempt -> idempotent 200 or 400 rejection
        res2 = await self.client.post(f"/api/v1/consultations/{cns_id}/complete", headers=self.arjun_headers)
        self.assertIn(res2.status_code, [200, 400])
        if res2.status_code == 200:
            self.assertEqual(res2.json()["data"]["status"], ConsultationStatus.COMPLETED.value)

    # =========================================================================
    # 9. Patient Privacy Boundary & IDOR Protection
    # =========================================================================
    async def test_20_patient_cannot_view_in_progress_consultation(self):
        """Patient cannot view an in-progress consultation (only completed)."""
        apt_id = "APT-P14-019"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "In progress privacy"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Patient requests details of in-progress consultation -> 403
        pat_res = await self.client.get(f"/api/v1/consultations/{cns_id}", headers=self.pat1_headers)
        self.assertEqual(pat_res.status_code, 403)

    async def test_21_patient_sees_completed_consultation_without_private_doctor_notes(self):
        """Patient can view completed consultation, but private doctor clinical_notes are hidden."""
        apt_id = "APT-P14-020"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Private notes test"}
        )
        cns_id = res.json()["data"]["consultation_id"]
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.arjun_headers,
            json={"clinical_notes": "CONFIDENTIAL DOCTOR OBSERVATION: Differential diagnosis rule out myocarditis."}
        )
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/assessment",
            headers=self.arjun_headers,
            json={"summary": "Patient is in good condition.", "risk_level": RiskLevel.LOW.value}
        )
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/diagnoses",
            headers=self.arjun_headers,
            json={"diagnoses": [{"name": "Routine Checkup", "type": DiagnosisType.PRIMARY.value}]}
        )
        await self.client.post(f"/api/v1/consultations/{cns_id}/complete", headers=self.arjun_headers)

        # Patient views the completed consultation
        pat_res = await self.client.get(f"/api/v1/consultations/{cns_id}", headers=self.pat1_headers)
        self.assertEqual(pat_res.status_code, 200)
        pat_data = pat_res.json()["data"]

        # Doctor's private clinical_notes MUST NOT be exposed in patient response
        self.assertNotIn("clinical_notes", pat_data)

    async def test_22_cross_patient_idor_strictly_denied(self):
        """Patient Two cannot view Patient One's completed consultation (IDOR denied)."""
        apt_id = "APT-P14-021"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "IDOR check"}
        )
        cns_id = res.json()["data"]["consultation_id"]
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/assessment",
            headers=self.arjun_headers,
            json={"summary": "Summary", "risk_level": RiskLevel.LOW.value}
        )
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/diagnoses",
            headers=self.arjun_headers,
            json={"diagnoses": [{"name": "Diag", "type": DiagnosisType.PRIMARY.value}]}
        )
        await self.client.post(f"/api/v1/consultations/{cns_id}/complete", headers=self.arjun_headers)

        # Patient TWO attempts to read Patient ONE's consultation -> 403
        idor_res = await self.client.get(f"/api/v1/consultations/{cns_id}", headers=self.pat2_headers)
        self.assertEqual(idor_res.status_code, 403)

    # =========================================================================
    # 10. Audit Logging Verification
    # =========================================================================
    async def test_23_audit_logging_verified_in_mongodb(self):
        """Starting and completing consultation generates audit logs in audit_logs collection."""
        apt_id = "APT-P14-022"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Audit trail test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Check audit log for start
        audit_start = await self.db[COLLECTION_AUDIT_LOGS].find_one({
            "action": "consultation.started",
            "resource_id": cns_id
        })
        self.assertIsNotNone(audit_start)
        self.assertEqual(audit_start["actor_id"], self.arjun_user_id)
        self.assertEqual(audit_start.get("resource"), "consultation")

        # Complete consultation
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/assessment",
            headers=self.arjun_headers,
            json={"summary": "Summary", "risk_level": RiskLevel.LOW.value}
        )
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/diagnoses",
            headers=self.arjun_headers,
            json={"diagnoses": [{"name": "Diag", "type": DiagnosisType.PRIMARY.value}]}
        )
        await self.client.post(f"/api/v1/consultations/{cns_id}/complete", headers=self.arjun_headers)

        # Check audit log for completion
        audit_comp = await self.db[COLLECTION_AUDIT_LOGS].find_one({
            "action": "consultation.completed",
            "resource_id": cns_id
        })
        self.assertIsNotNone(audit_comp)
        self.assertEqual(audit_comp["actor_id"], self.arjun_user_id)

    # =========================================================================
    # 11. Persistence Across Simulated Restart & Snapshot Safety
    # =========================================================================
    async def test_24_restart_persistence_and_snapshot_safety(self):
        """Consultation data survives snapshot sync and simulated restart with 100% field integrity."""
        apt_id = "APT-P14-023"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Persistence test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.arjun_headers,
            json={"clinical_notes": "Persistence verified notes."}
        )
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/assessment",
            headers=self.arjun_headers,
            json={"summary": "Patient robust.", "risk_level": RiskLevel.LOW.value}
        )
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/diagnoses",
            headers=self.arjun_headers,
            json={"diagnoses": [{"name": "Healthy", "type": DiagnosisType.PRIMARY.value}]}
        )
        await self.client.post(f"/api/v1/consultations/{cns_id}/complete", headers=self.arjun_headers)

        # 1. Capture MongoDB document before restart
        doc_before = await self.db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": cns_id})
        self.assertIsNotNone(doc_before)
        self.assertEqual(doc_before["status"], ConsultationStatus.COMPLETED.value)
        self.assertEqual(doc_before["clinical_notes"], "Persistence verified notes.")

        # 2. Trigger snapshot write to disk
        await save_in_memory_snapshot(self.db)

        # 3. Simulate restart by restoring snapshot
        await restore_in_memory_snapshot(self.db)

        # 4. Query document after simulated restart
        doc_after = await self.db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": cns_id})
        self.assertIsNotNone(doc_after)
        self.assertEqual(doc_after["status"], ConsultationStatus.COMPLETED.value)
        self.assertEqual(doc_after["clinical_notes"], doc_before["clinical_notes"])
        self.assertEqual(doc_after["completed_by"], doc_before["completed_by"])
        self.assertEqual(doc_after["started_at"], doc_before["started_at"])
        self.assertEqual(doc_after["completed_at"], doc_before["completed_at"])

    # =========================================================================
    # 12. Nonexistent Consultation & Validation Error Handling
    # =========================================================================
    async def test_25_nonexistent_consultation_returns_404(self):
        """Querying a nonexistent consultation ID returns 404."""
        res = await self.client.get("/api/v1/consultations/CNS-NONEXISTENT-999", headers=self.arjun_headers)
        self.assertEqual(res.status_code, 404)

    async def test_26_invalid_payload_returns_422(self):
        """Sending malformed payload types returns 422 Unprocessable Entity."""
        res = await self.client.patch(
            "/api/v1/consultations/CNS-2026-001/vitals",
            headers=self.arjun_headers,
            json={"bp_systolic": "not-a-number"}
        )
        self.assertEqual(res.status_code, 422)

    # =========================================================================
    # 13. Additional Hardened Security & Concurrency Verification
    # =========================================================================
    async def test_27_link_medical_record_same_patient_succeeds(self):
        """Authorized doctor links a valid medical record belonging to the same patient."""
        apt_id = "APT-P14-027"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "MR linkage test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        now = utc_now()
        mr_id = "MR-P14-PAT1-VALID"
        await self.db[COLLECTION_MEDICAL_RECORDS].update_one(
            {"record_id": mr_id},
            {"$set": {
                "record_id": mr_id,
                "patient_id": self.pat1_id,
                "doctor_id": self.arjun_doc_id,
                "title": "Lipid Profile Pat1",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        link_res = await self.client.post(
            f"/api/v1/consultations/{cns_id}/link-medical-record",
            headers=self.arjun_headers,
            json={"record_id": mr_id}
        )
        self.assertEqual(link_res.status_code, 200)
        self.assertIn(mr_id, link_res.json()["data"]["linked_medical_record_ids"])

    async def test_28_optimistic_concurrency_conflict_on_stale_version(self):
        """Updating notes with a stale expected_version triggers HTTP 409 Conflict."""
        apt_id = "APT-P14-028"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Concurrency test"}
        )
        cns_id = res.json()["data"]["consultation_id"]
        v1 = res.json()["data"].get("version", 1)

        # First update succeeds
        res_up1 = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.arjun_headers,
            json={"clinical_notes": "Update one", "expected_version": v1}
        )
        self.assertEqual(res_up1.status_code, 200)

        # Stale update with old expected_version v1 fails with 409
        res_stale = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.arjun_headers,
            json={"clinical_notes": "Stale overwrite attempt", "expected_version": v1}
        )
        self.assertEqual(res_stale.status_code, 409)

    async def test_29_cancelled_consultation_cannot_be_completed(self):
        """A cancelled consultation cannot transition to completed."""
        apt_id = "APT-P14-029"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Cancel test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Cancel consultation
        res_cancel = await self.client.post(
            f"/api/v1/consultations/{cns_id}/cancel",
            headers=self.arjun_headers,
            json={"reason": "Patient requested cancellation"}
        )
        self.assertEqual(res_cancel.status_code, 200)

        # Attempt to complete cancelled consultation -> 400
        res_comp = await self.client.post(
            f"/api/v1/consultations/{cns_id}/complete",
            headers=self.arjun_headers
        )
        self.assertEqual(res_comp.status_code, 400)
        self.assertIn("cancelled", res_comp.text.lower())

    async def test_30_cancelled_consultation_cannot_be_modified(self):
        """Notes or symptoms cannot be patched on a cancelled consultation."""
        apt_id = "APT-P14-030"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Cancel mod test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        await self.client.post(
            f"/api/v1/consultations/{cns_id}/cancel",
            headers=self.arjun_headers,
            json={"reason": "Cancelled"}
        )

        # Attempt to patch notes
        res_patch = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.arjun_headers,
            json={"clinical_notes": "Trying to modify after cancellation"}
        )
        self.assertEqual(res_patch.status_code, 400)

    async def test_31_patient_cannot_edit_doctor_clinical_notes(self):
        """Patient attempting to patch clinical notes receives 403 Forbidden."""
        apt_id = "APT-P14-031"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Patient edit test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        res_pat_edit = await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.pat1_headers,
            json={"clinical_notes": "Patient attempting to alter notes"}
        )
        self.assertEqual(res_pat_edit.status_code, 403)

    async def test_32_patient_cannot_change_consultation_status(self):
        """Patient cannot complete, cancel, or modify consultation status."""
        apt_id = "APT-P14-032"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Status test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Patient complete -> 403
        res_comp = await self.client.post(f"/api/v1/consultations/{cns_id}/complete", headers=self.pat1_headers)
        self.assertEqual(res_comp.status_code, 403)

        # Patient cancel -> 403
        res_cancel = await self.client.post(
            f"/api/v1/consultations/{cns_id}/cancel",
            headers=self.pat1_headers,
            json={"reason": "Patient cancel"}
        )
        self.assertEqual(res_cancel.status_code, 403)

    async def test_33_admin_audit_access_preserves_doctor_authorship(self):
        """Admin read access to consultation preserves authenticated doctor as author/creator."""
        apt_id = "APT-P14-033"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Admin view test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Admin reads consultation
        admin_res = await self.client.get(f"/api/v1/consultations/{cns_id}", headers=self.admin_headers)
        self.assertEqual(admin_res.status_code, 200)
        data = admin_res.json()["data"]
        self.assertEqual(data["doctor_id"], self.arjun_doc_id)
        self.assertEqual(data["created_by"], self.arjun_user_id)

    async def test_34_list_consultations_role_filtering_and_security(self):
        """Role-aware list endpoint correctly filters consultations per user role."""
        apt_id = "APT-P14-034"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "List filter test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # Doctor listing: Arjun sees this consultation
        doc_list = await self.client.get("/api/v1/consultations", headers=self.arjun_headers)
        self.assertEqual(doc_list.status_code, 200)
        items = doc_list.json()["data"]
        doc_cns_ids = [c["consultation_id"] for c in items]
        self.assertIn(cns_id, doc_cns_ids)

        # Patient listing: in-progress consultation should NOT be visible to patient
        pat_list = await self.client.get("/api/v1/consultations", headers=self.pat1_headers)
        self.assertEqual(pat_list.status_code, 200)
        pat_items = pat_list.json()["data"]
        pat_cns_ids = [c["consultation_id"] for c in pat_items]
        self.assertNotIn(cns_id, pat_cns_ids)

    async def test_35_snapshot_never_overwrites_newer_mongodb_data(self):
        """A stale disk snapshot cannot overwrite newer consultation clinical notes or status in MongoDB."""
        apt_id = "APT-P14-035"
        await self._create_test_appointment(apt_id, self.pat1_id, self.arjun_doc_id)

        res = await self.client.post(
            f"/api/v1/consultations/start/{apt_id}",
            headers=self.arjun_headers,
            json={"chief_complaint": "Snapshot safety test"}
        )
        cns_id = res.json()["data"]["consultation_id"]

        # 1. Take snapshot of initial state
        await save_in_memory_snapshot(self.db)

        # 2. Doctor updates clinical notes to a newer value in live MongoDB
        newer_notes = "UPDATED NEWER CLINICAL NOTES IN MONGODB"
        await self.client.patch(
            f"/api/v1/consultations/{cns_id}/clinical-notes",
            headers=self.arjun_headers,
            json={"clinical_notes": newer_notes}
        )

        # 3. Simulate snapshot restoration (e.g. from an older snapshot)
        await restore_in_memory_snapshot(self.db)

        # 4. Live MongoDB document MUST retain the newer notes
        doc = await self.db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": cns_id})
        self.assertEqual(doc["clinical_notes"], newer_notes)


if __name__ == "__main__":
    unittest.main()
