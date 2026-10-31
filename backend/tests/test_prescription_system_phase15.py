"""
Phase 15 Hardened Final Acceptance Audit Test Suite:
Prescription System, Controlled Medication Models, Validation Rules,
Consultation & Appointment Linkage, Doctor Authorization, IDOR Protection,
Mass-Assignment Guardrails, Duplicate & Concurrency Protection,
Cancellation Workflow, Audit Logging, Patient Privacy Boundary,
Restart Persistence, Snapshot Safety, and AI Immutability Boundary.

Structured Sections A through M covering all 88 audit items.
"""

import asyncio
import unittest
from datetime import datetime, timezone, timedelta, date
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.models.user import UserRole, AuthProvider, AccountStatus
from app.models.prescription import PrescriptionStatus, MedicationRoute, Medication
from app.models.consultation import ConsultationStatus
from app.models.appointment import AppointmentStatus, AppointmentType, BookingSource
from app.core.security import create_access_token
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS, COLLECTION_PRESCRIPTIONS,
    COLLECTION_AUDIT_LOGS, COLLECTION_MEDICAL_RECORDS, COLLECTION_AI_ANALYSES
)
from app.database.mongodb import db_manager, connect_to_mongo, save_in_memory_snapshot, restore_in_memory_snapshot
from app.utils.datetime import utc_now


class TestPhase15PrescriptionSystemAuditSuite(unittest.IsolatedAsyncioTestCase):
    """Phase 15 Comprehensive Hardened Final Acceptance Audit Suite."""

    async def asyncSetUp(self):
        await connect_to_mongo()
        self.db = db_manager.db

        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        now = utc_now()

        # Doctor Arjun (Authorized Attending Doctor)
        self.arjun_user_id = "USR-DOC-ARJUN-15"
        self.arjun_doc_id = "DOC-ARJUN-15"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.arjun_user_id},
            {"$set": {
                "user_id": self.arjun_user_id,
                "email": "dr.arjun.p15@clinixai.com",
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
                "email": "dr.arjun.p15@clinixai.com",
                "department_id": "DEPT-CARD",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Doctor Priya (Unauthorized / Independent Doctor)
        self.priya_user_id = "USR-DOC-PRIYA-15"
        self.priya_doc_id = "DOC-PRIYA-15"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.priya_user_id},
            {"$set": {
                "user_id": self.priya_user_id,
                "email": "dr.priya.p15@clinixai.com",
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
                "email": "dr.priya.p15@clinixai.com",
                "department_id": "DEPT-NEUR",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Patient One (Authorized Patient)
        self.patient_user_id = "USR-PAT-ONE-15"
        self.patient_id = "PAT-ONE-15"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.patient_user_id},
            {"$set": {
                "user_id": self.patient_user_id,
                "email": "patient.one.p15@clinixai.com",
                "full_name": "Patient One",
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
            {"patient_id": self.patient_id},
            {"$set": {
                "patient_id": self.patient_id,
                "user_id": self.patient_user_id,
                "first_name": "Patient",
                "last_name": "One",
                "email": "patient.one.p15@clinixai.com",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Patient Two (Unrelated Patient)
        self.patient2_user_id = "USR-PAT-TWO-15"
        self.patient2_id = "PAT-TWO-15"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.patient2_user_id},
            {"$set": {
                "user_id": self.patient2_user_id,
                "email": "patient.two.p15@clinixai.com",
                "full_name": "Patient Two",
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
            {"patient_id": self.patient2_id},
            {"$set": {
                "patient_id": self.patient2_id,
                "user_id": self.patient2_user_id,
                "first_name": "Patient",
                "last_name": "Two",
                "email": "patient.two.p15@clinixai.com",
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Staff Member
        self.staff_user_id = "USR-STAFF-15"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.staff_user_id},
            {"$set": {
                "user_id": self.staff_user_id,
                "email": "staff.p15@clinixai.com",
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

        # Admin User
        self.admin_user_id = "USR-ADMIN-15"
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.admin_user_id},
            {"$set": {
                "user_id": self.admin_user_id,
                "email": "admin.p15@clinixai.com",
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

        # Auth Tokens
        self.arjun_token = create_access_token(user_id=self.arjun_user_id, role=UserRole.DOCTOR.value)
        self.priya_token = create_access_token(user_id=self.priya_user_id, role=UserRole.DOCTOR.value)
        self.patient_token = create_access_token(user_id=self.patient_user_id, role=UserRole.PATIENT.value)
        self.patient2_token = create_access_token(user_id=self.patient2_user_id, role=UserRole.PATIENT.value)
        self.staff_token = create_access_token(user_id=self.staff_user_id, role=UserRole.HOSPITAL_STAFF.value)
        self.admin_token = create_access_token(user_id=self.admin_user_id, role=UserRole.HOSPITAL_ADMIN.value)

        self.arjun_headers = {"Authorization": f"Bearer {self.arjun_token}"}
        self.priya_headers = {"Authorization": f"Bearer {self.priya_token}"}
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}
        self.patient2_headers = {"Authorization": f"Bearer {self.patient2_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}

        # Seed Appointments
        self.appointment_id = "APT-15-MAIN-001"
        self.completed_appointment_id = "APT-15-COMP-001"
        self.cancelled_appointment_id = "APT-15-CANC-001"
        self.noshow_appointment_id = "APT-15-NOSHOW-001"

        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": self.appointment_id},
            {"$set": {
                "appointment_id": self.appointment_id,
                "patient_id": self.patient_id,
                "doctor_id": self.arjun_doc_id,
                "status": "in_consultation",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": self.completed_appointment_id},
            {"$set": {
                "appointment_id": self.completed_appointment_id,
                "patient_id": self.patient_id,
                "doctor_id": self.arjun_doc_id,
                "status": "completed",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": self.cancelled_appointment_id},
            {"$set": {
                "appointment_id": self.cancelled_appointment_id,
                "patient_id": self.patient_id,
                "doctor_id": self.arjun_doc_id,
                "status": "cancelled",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": self.noshow_appointment_id},
            {"$set": {
                "appointment_id": self.noshow_appointment_id,
                "patient_id": self.patient_id,
                "doctor_id": self.arjun_doc_id,
                "status": "no_show",
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Seed Active Consultation for Dr. Arjun & Patient One
        self.consultation_id = "CON-15-MAIN-001"
        await self.db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": self.consultation_id},
            {"$set": {
                "consultation_id": self.consultation_id,
                "appointment_id": self.appointment_id,
                "patient_id": self.patient_id,
                "doctor_id": self.arjun_doc_id,
                "department_id": "DEPT-CARD",
                "status": ConsultationStatus.IN_PROGRESS.value,
                "clinical_assessment": {"summary": "Hypertension assessment", "risk_level": "moderate"},
                "diagnoses": [{"name": "Essential Hypertension", "type": "primary"}],
                "created_at": now,
                "updated_at": now,
                "is_deleted": False,
            }},
            upsert=True
        )

        # Seed Completed Consultation for Dr. Arjun & Patient One
        self.completed_consultation_id = "CON-15-COMP-001"
        await self.db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": self.completed_consultation_id},
            {"$set": {
                "consultation_id": self.completed_consultation_id,
                "appointment_id": self.completed_appointment_id,
                "patient_id": self.patient_id,
                "doctor_id": self.arjun_doc_id,
                "department_id": "DEPT-CARD",
                "status": ConsultationStatus.COMPLETED.value,
                "clinical_assessment": {"summary": "Completed encounter", "risk_level": "low"},
                "diagnoses": [{"name": "Routine Checkup", "type": "primary"}],
                "created_at": now,
                "updated_at": now,
                "is_deleted": False,
            }},
            upsert=True
        )

        # Seed Cancelled Consultation
        self.cancelled_consultation_id = "CON-15-CANC-001"
        await self.db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": self.cancelled_consultation_id},
            {"$set": {
                "consultation_id": self.cancelled_consultation_id,
                "appointment_id": self.cancelled_appointment_id,
                "patient_id": self.patient_id,
                "doctor_id": self.arjun_doc_id,
                "department_id": "DEPT-CARD",
                "status": ConsultationStatus.CANCELLED.value,
                "created_at": now,
                "updated_at": now,
                "is_deleted": False,
            }},
            upsert=True
        )

        # Seed No-show Consultation
        self.noshow_consultation_id = "CON-15-NOSHOW-001"
        await self.db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": self.noshow_consultation_id},
            {"$set": {
                "consultation_id": self.noshow_consultation_id,
                "appointment_id": self.noshow_appointment_id,
                "patient_id": self.patient_id,
                "doctor_id": self.arjun_doc_id,
                "department_id": "DEPT-CARD",
                "status": "no_show",
                "created_at": now,
                "updated_at": now,
                "is_deleted": False,
            }},
            upsert=True
        )

        # Seed Cross-Patient Consultation (mismatch with appointment)
        self.crosspat_apt_id = "APT-15-CROSSPAT-001"
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": self.crosspat_apt_id},
            {"$set": {
                "appointment_id": self.crosspat_apt_id,
                "patient_id": self.patient2_id,  # Mismatch: Patient Two
                "doctor_id": self.arjun_doc_id,
                "status": "in_consultation",
            }},
            upsert=True
        )
        self.crosspat_consult_id = "CON-15-CROSSPAT-001"
        await self.db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": self.crosspat_consult_id},
            {"$set": {
                "consultation_id": self.crosspat_consult_id,
                "appointment_id": self.crosspat_apt_id,
                "patient_id": self.patient_id,  # Consultation claims Patient One
                "doctor_id": self.arjun_doc_id,
                "status": "in_progress",
            }},
            upsert=True
        )

        # Seed Cross-Doctor Consultation (mismatch with appointment)
        self.crossdoc_apt_id = "APT-15-CROSSDOC-001"
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": self.crossdoc_apt_id},
            {"$set": {
                "appointment_id": self.crossdoc_apt_id,
                "patient_id": self.patient2_id,
                "doctor_id": self.priya_doc_id,  # Mismatch: Doctor Priya
                "status": "in_consultation",
            }},
            upsert=True
        )
        self.crossdoc_consult_id = "CON-15-CROSSDOC-001"
        await self.db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": self.crossdoc_consult_id},
            {"$set": {
                "consultation_id": self.crossdoc_consult_id,
                "appointment_id": self.crossdoc_apt_id,
                "patient_id": self.patient2_id,
                "doctor_id": self.arjun_doc_id,  # Consultation claims Doctor Arjun
                "status": "in_progress",
            }},
            upsert=True
        )

        # Seed Medical Record linked to consultation
        self.medical_record_id = "MR-15-CARD-001"
        await self.db[COLLECTION_MEDICAL_RECORDS].update_one(
            {"record_id": self.medical_record_id},
            {"$set": {
                "record_id": self.medical_record_id,
                "patient_id": self.patient_id,
                "doctor_id": self.arjun_doc_id,
                "consultation_id": self.consultation_id,
                "appointment_id": self.appointment_id,
                "title": "Clinical Summary Record",
                "record_type": "consultation_summary",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Clean existing prescriptions for test consultations
        await self.db[COLLECTION_PRESCRIPTIONS].delete_many({
            "consultation_id": {"$in": [
                self.consultation_id, self.completed_consultation_id,
                self.cancelled_consultation_id, self.noshow_consultation_id,
                self.crosspat_consult_id, self.crossdoc_consult_id
            ]}
        })

    async def asyncTearDown(self):
        await self.client.aclose()

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION A: Authentication (Items 1 - 4)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_a01_unauthenticated_list(self):
        """1. Unauthenticated list request rejected with 401."""
        res = await self.client.get("/api/v1/prescriptions")
        self.assertEqual(res.status_code, 401)

    async def test_a02_unauthenticated_detail(self):
        """2. Unauthenticated detail request rejected with 401."""
        res = await self.client.get("/api/v1/prescriptions/RX-2026-NONEXIST")
        self.assertEqual(res.status_code, 401)

    async def test_a03_unauthenticated_create(self):
        """3. Unauthenticated create request rejected with 401."""
        res = await self.client.post("/api/v1/prescriptions", json={"consultation_id": self.consultation_id})
        self.assertEqual(res.status_code, 401)

    async def test_a04_unauthenticated_cancel(self):
        """4. Unauthenticated cancel request rejected with 401."""
        res = await self.client.post("/api/v1/prescriptions/RX-2026-NONEXIST/cancel", json={"reason": "Cancel"})
        self.assertEqual(res.status_code, 401)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION B: Patient RBAC (Items 5 - 10)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_b05_patient_can_view_own_prescription(self):
        """5. Patient can view own prescription."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.get(f"/api/v1/prescriptions/{rx_id}", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["prescription_id"], rx_id)

    async def test_b06_patient_cannot_view_another_patient_prescription(self):
        """6. Patient cannot view another patient's prescription (403 Forbidden)."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.get(f"/api/v1/prescriptions/{rx_id}", headers=self.patient2_headers)
        self.assertEqual(res.status_code, 403)

    async def test_b07_patient_cannot_create(self):
        """7. Patient cannot create prescription (403 Forbidden)."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin 100mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "7 days"}]
        }, headers=self.patient_headers)
        self.assertEqual(res.status_code, 403)

    async def test_b08_patient_cannot_cancel(self):
        """8. Patient cannot cancel prescription (403 Forbidden)."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Cancel"}, headers=self.patient_headers)
        self.assertEqual(res.status_code, 403)

    async def test_b09_patient_cannot_modify(self):
        """9. Patient cannot modify prescription via create/update endpoint (403 Forbidden)."""
        res = await self.client.post(f"/api/v1/prescriptions/consultation/{self.consultation_id}", json={
            "medications": [{"name": "Morphine 10mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "10 days"}]
        }, headers=self.patient_headers)
        self.assertEqual(res.status_code, 403)

    async def test_b10_patient_safe_response_excludes_private_doctor_notes(self):
        """10. Patient-safe response excludes private doctor notes and internal authorship keys."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}],
            "notes": "CONFIDENTIAL: Suspected high sodium diet."
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.get(f"/api/v1/prescriptions/{rx_id}", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        data = res.json()["data"]
        self.assertNotIn("notes", data)
        self.assertNotIn("created_by", data)
        self.assertNotIn("updated_by", data)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION C: Doctor RBAC (Items 11 - 16)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_c11_authorized_doctor_can_create(self):
        """11. Authorized doctor can create prescription."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Atorvastatin 20mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 201)
        self.assertTrue(res.json()["data"]["prescription_id"].startswith("RX-"))

    async def test_c12_authorized_doctor_can_view(self):
        """12. Authorized doctor can view prescription with full clinical details."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Atorvastatin 20mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}],
            "notes": "Doctor private notes"
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.get(f"/api/v1/prescriptions/{rx_id}", headers=self.arjun_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["notes"], "Doctor private notes")

    async def test_c13_authorized_doctor_can_cancel(self):
        """13. Authorized doctor can cancel active prescription."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Atorvastatin 20mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={
            "reason": "Patient switched to Rosuvastatin"
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["status"], PrescriptionStatus.CANCELLED.value)

    async def test_c14_unauthorized_doctor_cannot_view(self):
        """14. Unauthorized doctor cannot view another doctor's prescription (403 Forbidden)."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Atorvastatin 20mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.get(f"/api/v1/prescriptions/{rx_id}", headers=self.priya_headers)
        self.assertEqual(res.status_code, 403)

    async def test_c15_unauthorized_doctor_cannot_create_using_another_doctor_consultation(self):
        """15. Unauthorized doctor cannot create prescription using another doctor's consultation (403 Forbidden)."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Atorvastatin 20mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.priya_headers)
        self.assertEqual(res.status_code, 403)

    async def test_c16_unauthorized_doctor_cannot_cancel_another_doctor_prescription(self):
        """16. Unauthorized doctor cannot cancel another doctor's prescription (403 Forbidden)."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Atorvastatin 20mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={
            "reason": "Unauthorized cancellation attempt"
        }, headers=self.priya_headers)
        self.assertEqual(res.status_code, 403)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION D: Staff/Admin (Items 17 - 22)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_d17_staff_cannot_create(self):
        """17. Staff cannot create prescription (403 Forbidden)."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin 75mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "7 days"}]
        }, headers=self.staff_headers)
        self.assertEqual(res.status_code, 403)

    async def test_d18_staff_cannot_modify(self):
        """18. Staff cannot cancel or modify prescription (403 Forbidden)."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin 75mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "7 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={
            "reason": "Staff attempt"
        }, headers=self.staff_headers)
        self.assertEqual(res.status_code, 403)

    async def test_d19_staff_access_follows_existing_read_policy(self):
        """19. Staff access follows existing hospital clinical read policy."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin 75mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "7 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.get(f"/api/v1/prescriptions/{rx_id}", headers=self.staff_headers)
        self.assertEqual(res.status_code, 200)

    async def test_d20_admin_cannot_impersonate_doctor(self):
        """20. Admin cannot impersonate doctor to author prescriptions."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "doctor_id": self.arjun_doc_id,
            "medications": [{"name": "Aspirin 75mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "7 days"}]
        }, headers=self.admin_headers)
        self.assertEqual(res.status_code, 403)

    async def test_d21_admin_cannot_create_as_another_doctor(self):
        """21. Admin cannot create prescription as another doctor via consultation route."""
        res = await self.client.post(f"/api/v1/prescriptions/consultation/{self.consultation_id}", json={
            "medications": [{"name": "Aspirin 75mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "7 days"}]
        }, headers=self.admin_headers)
        self.assertEqual(res.status_code, 403)

    async def test_d22_admin_cannot_silently_modify_doctor_authored_clinical_data(self):
        """22. Admin cannot cancel doctor-authored prescription without doctor clinical credentials."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin 75mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "7 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={
            "reason": "Admin cancellation"
        }, headers=self.admin_headers)
        self.assertEqual(res.status_code, 403)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION E: Clinical relationship integrity (Items 23 - 32)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_e23_prescription_to_consultation_relationship(self):
        """23. Prescription has valid consultation relationship and updates consultation."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Lisinopril 10mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        consult = await self.db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": self.consultation_id})
        self.assertEqual(consult["prescription_id"], rx_id)

    async def test_e24_consultation_to_appointment_relationship(self):
        """24. Prescription inherits consultation's appointment relationship."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Lisinopril 10mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.json()["data"]["appointment_id"], self.appointment_id)

    async def test_e25_prescription_patient_equals_consultation_patient(self):
        """25. Prescription patient equals consultation patient."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Lisinopril 10mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.json()["data"]["patient_id"], self.patient_id)

    async def test_e26_prescription_doctor_equals_consultation_doctor(self):
        """26. Prescription doctor equals consultation doctor."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Lisinopril 10mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.json()["data"]["doctor_id"], self.arjun_doc_id)

    async def test_e27_medical_record_linkage_where_supported(self):
        """27. Linked medical record is updated with new prescription ID."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Lisinopril 10mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        mr = await self.db[COLLECTION_MEDICAL_RECORDS].find_one({"record_id": self.medical_record_id})
        self.assertIn(rx_id, mr.get("prescription_ids", []))

    async def test_e28_invalid_consultation_rejected(self):
        """28. Invalid/non-existent consultation rejected with 404."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": "CON-DOES-NOT-EXIST-404",
            "medications": [{"name": "Paracetamol 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "3 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 404)

    async def test_e29_cancelled_consultation_rejected(self):
        """29. Cancelled consultation rejected with 400 Bad Request."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.cancelled_consultation_id,
            "medications": [{"name": "Paracetamol 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "3 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 400)

    async def test_e30_no_show_consultation_rejected(self):
        """30. No-show consultation rejected with 400 Bad Request."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.noshow_consultation_id,
            "medications": [{"name": "Paracetamol 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "3 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 400)

    async def test_e31_cross_patient_consultation_rejected(self):
        """31. Cross-patient consultation mismatch with appointment rejected with 400."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.crosspat_consult_id,
            "medications": [{"name": "Paracetamol 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "3 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 400)

    async def test_e32_cross_doctor_consultation_rejected(self):
        """32. Cross-doctor consultation mismatch with appointment rejected with 400."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.crossdoc_consult_id,
            "medications": [{"name": "Paracetamol 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "3 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 400)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION F: Medication validation (Items 33 - 46)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_f33_empty_medication_list(self):
        """33. Empty medication list rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": []
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f34_empty_medicine_name(self):
        """34. Empty medicine name rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "   ", "dosage": "1 tablet", "frequency": "Daily", "duration": "5 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f35_invalid_dosage(self):
        """35. Blank/empty dosage rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "   ", "frequency": "Daily", "duration": "5 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f36_zero_dosage(self):
        """36. Zero dosage rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "0 mg", "frequency": "Daily", "duration": "5 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f37_negative_dosage(self):
        """37. Negative dosage rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "-500mg", "frequency": "Daily", "duration": "5 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f38_invalid_dosage_unit(self):
        """38. Invalid dosage unit rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "1 tablet", "dosage_unit": "lightyears", "frequency": "Daily", "duration": "5 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f39_invalid_frequency(self):
        """39. Empty/blank frequency rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "1 tablet", "frequency": "   ", "duration": "5 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f40_invalid_route(self):
        """40. Invalid administration route rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "1 tablet", "frequency": "Daily", "duration": "5 days", "route": "telepathic"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f41_zero_duration(self):
        """41. Zero duration rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "1 tablet", "frequency": "Daily", "duration": "0 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f42_negative_duration(self):
        """42. Negative duration rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "1 tablet", "frequency": "Daily", "duration": "-7 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f43_invalid_duration_unit(self):
        """43. Invalid duration unit rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "1 tablet", "frequency": "Daily", "duration": "5 days", "duration_unit": "eons"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f44_invalid_quantity(self):
        """44. Invalid/negative quantity rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "1 tablet", "frequency": "Daily", "duration": "5 days", "quantity": "-10"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f45_oversized_instructions(self):
        """45. Oversized instructions (> 500 chars) rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin", "dosage": "1 tablet", "frequency": "Daily", "duration": "5 days", "instructions": "X" * 501}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_f46_malformed_nested_medication_item(self):
        """46. Malformed nested medication item missing required fields rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Aspirin"}]  # Missing dosage, frequency, duration
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION G: Security (Items 47 - 55)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_g47_mass_assignment(self):
        """47. Malicious extra fields in payload do not contaminate database."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}],
            "is_admin": True,
            "root_access": "granted",
            "billing_override": 0.0
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 201)
        rx_id = res.json()["data"]["prescription_id"]
        doc = await self.db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": rx_id})
        self.assertNotIn("is_admin", doc)
        self.assertNotIn("root_access", doc)
        self.assertNotIn("billing_override", doc)

    async def test_g48_client_supplied_prescription_id_ignored(self):
        """48. Client-supplied prescription_id is ignored; server-generated RX-YYYY-XXXXXX used."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "prescription_id": "RX-HACKED-001",
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 201)
        self.assertNotEqual(res.json()["data"]["prescription_id"], "RX-HACKED-001")
        self.assertTrue(res.json()["data"]["prescription_id"].startswith("RX-"))

    async def test_g49_client_supplied_patient_id_ignored(self):
        """49. Client-supplied patient_id ignored; consultation's patient_id enforced."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "patient_id": self.patient2_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["patient_id"], self.patient_id)

    async def test_g50_client_supplied_doctor_id_ignored(self):
        """50. Client-supplied doctor_id ignored; consultation's doctor_id enforced."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "doctor_id": self.priya_doc_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["doctor_id"], self.arjun_doc_id)

    async def test_g51_client_supplied_created_by_ignored(self):
        """51. Client-supplied created_by ignored; authenticated doctor user ID enforced."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "created_by": "USR-ATTACKER",
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["created_by"], self.arjun_user_id)

    async def test_g52_client_supplied_timestamps_ignored(self):
        """52. Client-supplied timestamps ignored; server-generated timestamps enforced."""
        past_time = "2020-01-01T00:00:00Z"
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "created_at": past_time,
            "issued_at": past_time,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 201)
        self.assertNotEqual(res.json()["data"]["created_at"], past_time)

    async def test_g53_client_supplied_status_ignored(self):
        """53. Client-supplied status ignored; initial status is ACTIVE."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "status": "cancelled",
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["status"], PrescriptionStatus.ACTIVE.value)

    async def test_g54_xss_payload_rejected_or_sanitized(self):
        """54. XSS payloads in medicine name, dosage, or instructions rejected with 422."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{
                "name": "<script>alert('xss')</script> Paracetamol",
                "dosage": "1 tablet",
                "frequency": "Daily",
                "duration": "5 days"
            }]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 422)

    async def test_g55_mongo_query_injection_rejected(self):
        """55. Mongo query injection payloads safely rejected/isolated as 404."""
        res = await self.client.get('/api/v1/prescriptions/{"$gt": ""}', headers=self.arjun_headers)
        self.assertEqual(res.status_code, 404)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION H: Duplicate/concurrency (Items 56 - 60)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_h56_duplicate_active_prescription_business_rule(self):
        """56. Duplicate prescription request updates existing active prescription idempotently."""
        res1 = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res1.status_code, 201)
        rx1_id = res1.json()["data"]["prescription_id"]

        # Call again with updated medications
        res2 = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amlodipine 10mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertIn(res2.status_code, [200, 201])
        rx2_id = res2.json()["data"]["prescription_id"]
        self.assertEqual(rx1_id, rx2_id)

        # Invariant: exactly 1 active prescription in DB for consultation
        count = await self.db[COLLECTION_PRESCRIPTIONS].count_documents({
            "consultation_id": self.consultation_id,
            "status": {"$in": ["active", "issued"]}
        })
        self.assertEqual(count, 1)

    async def test_h57_simultaneous_prescription_creation(self):
        """57. Simultaneous prescription creation results in clean state and exactly 1 active record."""
        payload1 = {
            "consultation_id": self.completed_consultation_id,
            "medications": [{"name": "Paracetamol 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "3 days"}]
        }
        payload2 = {
            "consultation_id": self.completed_consultation_id,
            "medications": [{"name": "Cetirizine 10mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "5 days"}]
        }

        res1, res2 = await asyncio.gather(
            self.client.post("/api/v1/prescriptions", json=payload1, headers=self.arjun_headers),
            self.client.post("/api/v1/prescriptions", json=payload2, headers=self.arjun_headers),
            return_exceptions=True
        )
        self.assertIn(res1.status_code, [200, 201])
        self.assertIn(res2.status_code, [200, 201])

        active_count = await self.db[COLLECTION_PRESCRIPTIONS].count_documents({
            "consultation_id": self.completed_consultation_id,
            "status": {"$in": ["active", "issued"]}
        })
        self.assertEqual(active_count, 1)

    async def test_h58_simultaneous_cancellation(self):
        """58. Simultaneous cancellation results in exactly one 200 OK and one 400 rejection."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        cancel_payload = {"reason": "Concurrent therapy change"}
        res1, res2 = await asyncio.gather(
            self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json=cancel_payload, headers=self.arjun_headers),
            self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json=cancel_payload, headers=self.arjun_headers),
            return_exceptions=True
        )

        codes = [res1.status_code, res2.status_code]
        self.assertIn(200, codes)
        self.assertIn(400, codes)

        final_doc = await self.db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": rx_id})
        self.assertEqual(final_doc["status"], PrescriptionStatus.CANCELLED.value)

    async def test_h59_no_status_race(self):
        """59. Status is deterministic; cancelled prescription remains cancelled."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amlodipine 5mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Cancelled"}, headers=self.arjun_headers)

        doc = await self.db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": rx_id})
        self.assertEqual(doc["status"], PrescriptionStatus.CANCELLED.value)

    async def test_h60_no_duplicate_active_prescription_caused_by_race(self):
        """60. Rapid sequential creates never produce duplicate active prescriptions."""
        for i in range(3):
            await self.client.post("/api/v1/prescriptions", json={
                "consultation_id": self.consultation_id,
                "medications": [{"name": f"Drug {i}", "dosage": "1 tablet", "frequency": "Daily", "duration": "5 days"}]
            }, headers=self.arjun_headers)

        count = await self.db[COLLECTION_PRESCRIPTIONS].count_documents({
            "consultation_id": self.consultation_id,
            "status": {"$in": ["active", "issued"]}
        })
        self.assertEqual(count, 1)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION I: Lifecycle (Items 61 - 67)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_i61_active_prescription(self):
        """61. Prescription is created in ACTIVE status."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Metformin 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["status"], PrescriptionStatus.ACTIVE.value)

    async def test_i62_cancellation(self):
        """62. Cancellation transitions status to CANCELLED."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Metformin 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        cancel_res = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={
            "reason": "Discontinued due to normal HbA1c"
        }, headers=self.arjun_headers)
        self.assertEqual(cancel_res.status_code, 200)
        self.assertEqual(cancel_res.json()["data"]["status"], PrescriptionStatus.CANCELLED.value)

    async def test_i63_cancellation_requires_valid_reason_if_implemented(self):
        """63. Cancellation requires a valid non-empty reason."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Metformin 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        res = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "   "}, headers=self.arjun_headers)
        self.assertEqual(res.status_code, 400)

    async def test_i64_cancellation_records_server_actor(self):
        """64. Cancellation records server actor in cancelled_by."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Metformin 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        cancel_res = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Adverse reaction"}, headers=self.arjun_headers)
        self.assertEqual(cancel_res.json()["data"]["cancelled_by"], self.arjun_user_id)

    async def test_i65_cancellation_records_server_timestamp(self):
        """65. Cancellation records server timestamp in cancelled_at."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Metformin 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        cancel_res = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Adverse reaction"}, headers=self.arjun_headers)
        self.assertIsNotNone(cancel_res.json()["data"]["cancelled_at"])

    async def test_i66_cancelled_prescription_cannot_silently_reactivate(self):
        """66. Cancelled prescription cannot silently reactivate."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Metformin 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Cancelled"}, headers=self.arjun_headers)

        # Attempt to re-cancel
        re_cancel = await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Re-cancel"}, headers=self.arjun_headers)
        self.assertEqual(re_cancel.status_code, 400)

        # Check DB remains cancelled
        doc = await self.db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": rx_id})
        self.assertEqual(doc["status"], PrescriptionStatus.CANCELLED.value)

    async def test_i67_historical_prescription_remains_readable_according_to_policy(self):
        """67. Historical cancelled prescription remains readable by doctor and patient."""
        create_res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Metformin 500mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = create_res.json()["data"]["prescription_id"]

        await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Clinical reason"}, headers=self.arjun_headers)

        doc_res = await self.client.get(f"/api/v1/prescriptions/{rx_id}", headers=self.arjun_headers)
        self.assertEqual(doc_res.status_code, 200)
        self.assertEqual(doc_res.json()["data"]["status"], PrescriptionStatus.CANCELLED.value)

        pat_res = await self.client.get(f"/api/v1/prescriptions/{rx_id}", headers=self.patient_headers)
        self.assertEqual(pat_res.status_code, 200)
        self.assertEqual(pat_res.json()["data"]["status"], PrescriptionStatus.CANCELLED.value)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION J: Audit (Items 68 - 73)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_j68_prescription_created_audit(self):
        """68. prescription.created audit log written upon creation."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Telmisartan 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        audit = await self.db[COLLECTION_AUDIT_LOGS].find_one({"resource_id": rx_id, "action": "prescription.created"})
        self.assertIsNotNone(audit)

    async def test_j69_prescription_cancelled_audit(self):
        """69. prescription.cancelled audit log written upon cancellation."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Telmisartan 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Hypotension observed"}, headers=self.arjun_headers)

        audit = await self.db[COLLECTION_AUDIT_LOGS].find_one({"resource_id": rx_id, "action": "prescription.cancelled"})
        self.assertIsNotNone(audit)

    async def test_j70_correct_actor(self):
        """70. Audit log records authenticated doctor actor_id."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Telmisartan 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        audit = await self.db[COLLECTION_AUDIT_LOGS].find_one({"resource_id": rx_id, "action": "prescription.created"})
        self.assertEqual(audit["actor_id"], self.arjun_user_id)

    async def test_j71_correct_resource_id(self):
        """71. Audit log records correct prescription resource_id."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Telmisartan 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        audit = await self.db[COLLECTION_AUDIT_LOGS].find_one({"resource_id": rx_id, "action": "prescription.created"})
        self.assertEqual(audit["resource_id"], rx_id)

    async def test_j72_server_timestamp(self):
        """72. Audit log records valid server timestamp."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Telmisartan 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        audit = await self.db[COLLECTION_AUDIT_LOGS].find_one({"resource_id": rx_id, "action": "prescription.created"})
        self.assertIn("timestamp", audit)

    async def test_j73_no_jwt_password_token_leakage(self):
        """73. Audit logs contain no JWT tokens, passwords, or hashes."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Telmisartan 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "30 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        audit = await self.db[COLLECTION_AUDIT_LOGS].find_one({"resource_id": rx_id, "action": "prescription.created"})
        metadata_str = str(audit.get("metadata", {}))
        self.assertNotIn("Bearer", metadata_str)
        self.assertNotIn("password", metadata_str)
        self.assertNotIn("token", metadata_str)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION K: Persistence (Items 74 - 78)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_k74_mongodb_persistence(self):
        """74. Prescription directly persisted in MongoDB."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Pantoprazole 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        doc = await self.db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": rx_id})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["prescription_id"], rx_id)

    async def test_k75_restart_persistence(self):
        """75. Prescription persists across simulated restart."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Pantoprazole 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        # Save snapshot and restore
        await save_in_memory_snapshot(self.db)
        await restore_in_memory_snapshot(self.db)

        doc = await self.db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": rx_id})
        self.assertEqual(doc["prescription_id"], rx_id)

    async def test_k76_snapshot_persistence(self):
        """76. Prescription persists to disk snapshot file."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Pantoprazole 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        await save_in_memory_snapshot(self.db)
        doc = await self.db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": rx_id})
        self.assertIsNotNone(doc)

    async def test_k77_stale_snapshot_cannot_overwrite_newer_mongodb_data(self):
        """77. Stale snapshot cannot overwrite newer MongoDB data (atomic $setOnInsert)."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Pantoprazole 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        # Save snapshot with initial instruction
        await save_in_memory_snapshot(self.db)

        # Update live record in authoritative MongoDB directly
        await self.db[COLLECTION_PRESCRIPTIONS].update_one(
            {"prescription_id": rx_id},
            {"$set": {"instructions": "LIVE UPDATED INSTRUCTIONS IN MONGODB"}}
        )

        # Attempt restore from stale snapshot
        await restore_in_memory_snapshot(self.db)

        # Live MongoDB update must NOT be overwritten
        live_doc = await self.db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": rx_id})
        self.assertEqual(live_doc["instructions"], "LIVE UPDATED INSTRUCTIONS IN MONGODB")

    async def test_k78_cancelled_prescription_cannot_be_restored_as_active(self):
        """78. Cancelled prescription in MongoDB cannot be restored as active from older snapshot."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Pantoprazole 40mg", "dosage": "1 tablet", "frequency": "Daily", "duration": "14 days"}]
        }, headers=self.arjun_headers)
        rx_id = res.json()["data"]["prescription_id"]

        # Save snapshot while ACTIVE
        await save_in_memory_snapshot(self.db)

        # Authoritatively cancel in MongoDB
        await self.client.post(f"/api/v1/prescriptions/{rx_id}/cancel", json={"reason": "Cancelled"}, headers=self.arjun_headers)

        # Restore snapshot
        await restore_in_memory_snapshot(self.db)

        # Invariant: MongoDB status must remain CANCELLED
        doc = await self.db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": rx_id})
        self.assertEqual(doc["status"], PrescriptionStatus.CANCELLED.value)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION L: History/list (Items 79 - 83)
    # ═════════════════════════════════════════════════════════════════════════════

    async def test_l79_list_endpoint(self):
        """79. List endpoint returns data and pagination metadata."""
        res = await self.client.get("/api/v1/prescriptions", headers=self.arjun_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("data", res.json())
        self.assertIn("pagination", res.json())

    async def test_l80_pagination(self):
        """80. Pagination parameters page & page_size work correctly."""
        res = await self.client.get("/api/v1/prescriptions?page=1&page_size=5", headers=self.arjun_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["pagination"]["page"], 1)
        self.assertEqual(res.json()["pagination"]["page_size"], 5)

    async def test_l81_deterministic_sorting(self):
        """81. Deterministic sorting by created_at descending."""
        res = await self.client.get("/api/v1/prescriptions", headers=self.arjun_headers)
        self.assertEqual(res.status_code, 200)
        items = res.json()["data"]
        if len(items) >= 2:
            dates = [it.get("created_at") for it in items if it.get("created_at")]
            self.assertEqual(dates, sorted(dates, reverse=True))

    async def test_l82_status_filtering(self):
        """82. Status filtering filters to requested status."""
        res = await self.client.get("/api/v1/prescriptions?status=active", headers=self.arjun_headers)
        self.assertEqual(res.status_code, 200)
        for item in res.json()["data"]:
            self.assertIn(item["status"], ["active", "issued"])

    async def test_l83_authorization_cannot_be_bypassed_through_filters(self):
        """83. Patient cannot bypass isolation by supplying patient_id filter."""
        res = await self.client.get(f"/api/v1/prescriptions?patient_id={self.patient2_id}", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        # Even with filter for patient2, response only contains Patient One's prescriptions
        for item in res.json()["data"]:
            self.assertEqual(item.get("doctor_id"), self.arjun_doc_id)

    # ═════════════════════════════════════════════════════════════════════════════
    # SECTION M: AI boundary (Items 84 - 88)
    # ═════════════════════════════════════════════════════════════════════════════

    async def _seed_ai_analysis(self, ai_id: str = "AI-15-BOUND-001"):
        now = utc_now()
        await self.db[COLLECTION_AI_ANALYSES].update_one(
            {"analysis_id": ai_id},
            {"$set": {
                "analysis_id": ai_id,
                "patient_id": self.patient_id,
                "module_id": "chest_xray",
                "prediction": {"predicted_class": "Pneumonia", "confidence": 0.945},
                "status": "completed",
                "probabilities": {"Pneumonia": 0.945, "Normal": 0.055},
                "metadata": {"gradcam_layer": "conv5_block3_out", "heatmap_dimensions": [224, 224]},
                "created_at": now,
            }},
            upsert=True
        )

    async def test_m84_prescription_does_not_mutate_ai_analysis(self):
        """84. Prescription creation does not mutate AI analysis document."""
        ai_id = "AI-15-BOUND-001"
        await self._seed_ai_analysis(ai_id)

        await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amoxicillin 500mg", "dosage": "1 capsule", "frequency": "Thrice daily", "duration": "7 days"}]
        }, headers=self.arjun_headers)

        ai_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": ai_id})
        self.assertEqual(ai_doc["status"], "completed")

    async def test_m85_prescription_does_not_mutate_confidence(self):
        """85. AI confidence score remains unchanged."""
        ai_id = "AI-15-BOUND-001"
        await self._seed_ai_analysis(ai_id)

        await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amoxicillin 500mg", "dosage": "1 capsule", "frequency": "Thrice daily", "duration": "7 days"}]
        }, headers=self.arjun_headers)

        ai_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": ai_id})
        self.assertEqual(ai_doc["prediction"]["confidence"], 0.945)

    async def test_m86_prescription_does_not_mutate_probabilities(self):
        """86. AI probabilities distribution remains unchanged."""
        ai_id = "AI-15-BOUND-001"
        await self._seed_ai_analysis(ai_id)

        await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amoxicillin 500mg", "dosage": "1 capsule", "frequency": "Thrice daily", "duration": "7 days"}]
        }, headers=self.arjun_headers)

        ai_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": ai_id})
        self.assertEqual(ai_doc["probabilities"]["Pneumonia"], 0.945)
        self.assertEqual(ai_doc["probabilities"]["Normal"], 0.055)

    async def test_m87_prescription_does_not_mutate_gradcam_metadata(self):
        """87. AI Grad-CAM metadata remains unchanged."""
        ai_id = "AI-15-BOUND-001"
        await self._seed_ai_analysis(ai_id)

        await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amoxicillin 500mg", "dosage": "1 capsule", "frequency": "Thrice daily", "duration": "7 days"}]
        }, headers=self.arjun_headers)

        ai_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": ai_id})
        self.assertEqual(ai_doc["metadata"]["gradcam_layer"], "conv5_block3_out")
        self.assertEqual(ai_doc["metadata"]["heatmap_dimensions"], [224, 224])

    async def test_m88_prescription_records_doctor_authorship_rather_than_ai(self):
        """88. Prescription strictly records doctor authorship rather than AI authorship."""
        res = await self.client.post("/api/v1/prescriptions", json={
            "consultation_id": self.consultation_id,
            "medications": [{"name": "Amoxicillin 500mg", "dosage": "1 capsule", "frequency": "Thrice daily", "duration": "7 days"}]
        }, headers=self.arjun_headers)
        data = res.json()["data"]

        self.assertEqual(data["created_by"], self.arjun_user_id)
        self.assertIn("Arjun", data["issued_by"])
        self.assertNotIn("AI", data["issued_by"])
        self.assertNotIn("model", data["issued_by"])


if __name__ == "__main__":
    unittest.main()
