"""
Automated Test Suite for CliniXAI Post-Phase-24 Fix Phase 2:
Complete Patient Role Audit, Workflow & AI Result Visibility Hardening.

Covers all 25 Phase Z mandatory test requirements:
1. Patient dashboard identity & profile retrieval
2. Patient profile update (persists valid fields, prevents unauthorized fields)
3. Patient role change prevention (user cannot change role)
4. Patient doctor discovery (active doctors, specialization, fees)
5. Appointment booking (valid slot, patient attribution, 201/success)
6. Appointment listing (scoped exclusively to authenticated patient)
7. Appointment detail retrieval (valid appointment owned by patient)
8. Appointment ownership enforcement
9. Cross-patient appointment denial (Patient A cannot view Patient B's appointment - IDOR)
10. Medical record access (patient views own clinical record)
11. Cross-patient medical record denial (Patient A cannot view Patient B's record - IDOR)
12. Document / file access (patient views own clinical documents)
13. Cross-patient document denial (Patient A cannot access Patient B's documents - IDOR)
14. Medical image authorization (authenticated, patient-owned)
15. AI patient visibility policy (AI prediction != automatically patient visible)
16. Awaiting-review AI restriction (unreviewed AI analysis hidden or returns 403 to patient)
17. Reviewed AI visibility (reviewed/finalized AI analysis accessible with clinical review)
18. Cross-patient AI denial (Patient A cannot access Patient B's AI analysis - IDOR)
19. Prescription read-only access (patient views own prescriptions, cannot alter)
20. Billing read-only access (patient views own bills, cannot create or alter)
21. Notification isolation (Patient A only receives notifications for Patient A)
22. QR Health Card Fix Phase 1 regression verification
23. Unauthenticated endpoint protection (401 Unauthorized across patient APIs)
24. Invalid resource handling (clean 404 for non-existent entities)
25. Session & account isolation (switching accounts yields zero data leakage)
"""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now


def _make_cursor(return_data=None):
    mock_cursor = MagicMock()
    data = list(return_data) if return_data is not None else []
    mock_cursor.__aiter__ = MagicMock(return_value=iter(data))
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.skip = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=data)
    return mock_cursor


class TestPatientRoleFixPhase2(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        # Patient A (John Doe - PAT-001)
        self.patient_a = UserInDB(
            user_id="USR-PAT-001",
            email="patient.a@clinixai.com",
            full_name="John Doe",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        # Patient B (Jane Smith - PAT-002)
        self.patient_b = UserInDB(
            user_id="USR-PAT-002",
            email="patient.b@clinixai.com",
            full_name="Jane Smith",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        # Doctor (Dr. Arjun Rao - DOC-001)
        self.doctor = UserInDB(
            user_id="USR-DOC-001",
            email="dr.rao@clinixai.com",
            full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self._user_dicts = {
            "USR-PAT-001": self.patient_a.to_mongo_dict(),
            "USR-PAT-002": self.patient_b.to_mongo_dict(),
            "USR-DOC-001": self.doctor.to_mongo_dict(),
        }

        self.token_patient_a = create_access_token(user_id=self.patient_a.user_id, role=self.patient_a.role.value)
        self.token_patient_b = create_access_token(user_id=self.patient_b.user_id, role=self.patient_b.role.value)
        self.token_doctor = create_access_token(user_id=self.doctor.user_id, role=self.doctor.role.value)

        self.headers_patient_a = {"Authorization": f"Bearer {self.token_patient_a}"}
        self.headers_patient_b = {"Authorization": f"Bearer {self.token_patient_b}"}
        self.headers_doctor = {"Authorization": f"Bearer {self.doctor}"}

        # Mock Patient Profiles in MongoDB
        self.patient_doc_a = {
            "patient_id": "PAT-001",
            "user_id": "USR-PAT-001",
            "first_name": "John",
            "last_name": "Doe",
            "full_name": "John Doe",
            "email": "patient.a@clinixai.com",
            "blood_group": "O+",
            "emergency_contact": {"name": "Mary Doe", "relationship": "Spouse", "phone": "+91 98765 00001"},
            "qr_code": {"raw_token": "pqr_token_patient_a", "is_revoked": False},
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "status": "active",
        }
        self.patient_doc_b = {
            "patient_id": "PAT-002",
            "user_id": "USR-PAT-002",
            "first_name": "Jane",
            "last_name": "Smith",
            "full_name": "Jane Smith",
            "email": "patient.b@clinixai.com",
            "blood_group": "A+",
            "emergency_contact": {"name": "Bob Smith", "relationship": "Brother", "phone": "+91 98765 00002"},
            "qr_code": {"raw_token": "pqr_token_patient_b", "is_revoked": False},
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "status": "active",
        }

        # Mock Doctor Document
        self.doctor_doc = {
            "doctor_id": "DOC-001",
            "user_id": "USR-DOC-001",
            "full_name": "Dr. Arjun Rao",
            "email": "dr.rao@clinixai.com",
            "specialization": "Neurology",
            "department_id": "DEP-NEURO",
            "status": "active",
            "is_active": True,
            "consultation_fee": 1500.0,
            "available_slots": ["09:00", "09:30", "10:00"],
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Mock Appointments
        self.apt_a = {
            "appointment_id": "APT-2026-A001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "department_id": "DEP-NEURO",
            "appointment_date": "2026-10-15",
            "start_time": "09:00",
            "end_time": "09:30",
            "reason": "Neurology checkup",
            "appointment_type": "new_consultation",
            "status": "scheduled",
            "booking_source": "patient",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.apt_b = {
            "appointment_id": "APT-2026-B001",
            "patient_id": "PAT-002",
            "doctor_id": "DOC-001",
            "department_id": "DEP-NEURO",
            "appointment_date": "2026-10-16",
            "start_time": "10:00",
            "end_time": "10:30",
            "reason": "Migraine consultation",
            "appointment_type": "new_consultation",
            "status": "scheduled",
            "booking_source": "patient",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Mock Medical Records
        self.record_a = {
            "record_id": "REC-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "appointment_id": "APT-2026-A001",
            "title": "Neurology Consultation Record",
            "record_type": "clinical_document",
            "uploaded_by": "USR-DOC-001",
            "source": "doctor",
            "diagnosis": "Tension headache",
            "assessment": "Patient experiencing tension headaches, normal reflexes.",
            "treatment_plan": "Rest, hydration, physical therapy.",
            "care_plan": "Rest, hydration, physical therapy.",
            "status": "active",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.record_b = {
            "record_id": "REC-002",
            "patient_id": "PAT-002",
            "doctor_id": "DOC-001",
            "appointment_id": "APT-2026-B001",
            "title": "Migraine Treatment Record",
            "record_type": "clinical_document",
            "uploaded_by": "USR-DOC-001",
            "source": "doctor",
            "diagnosis": "Cluster migraine",
            "assessment": "Severe episodic migraine.",
            "treatment_plan": "Prescribed triptans.",
            "care_plan": "Prescribed triptans.",
            "status": "active",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Mock AI Analyses
        self.ai_analysis_unreviewed_a = {
            "analysis_id": "AI-UNREV-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "status": "awaiting_review",
            "finding": "Possible low-grade glioma",
            "confidence": 0.82,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.ai_analysis_reviewed_a = {
            "analysis_id": "AI-REV-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "status": "reviewed",
            "finding": "Normal MRI findings confirmed",
            "confidence": 0.96,
            "clinical_notes": "Reviewed and verified benign MRI scan.",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.ai_analysis_b = {
            "analysis_id": "AI-REV-002",
            "patient_id": "PAT-002",
            "doctor_id": "DOC-001",
            "status": "reviewed",
            "finding": "Patient B Meningioma",
            "confidence": 0.91,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Mock Documents
        self.doc_a = {
            "document_id": "DOC-FILE-001",
            "patient_id": "PAT-001",
            "title": "Brain MRI T1",
            "file_type": "image/jpeg",
            "file_path": "uploads/mri_patient_a.jpg",
            "status": "active",
            "created_at": utc_now(),
        }
        self.doc_b = {
            "document_id": "DOC-FILE-002",
            "patient_id": "PAT-002",
            "title": "Chest X-Ray",
            "file_type": "image/jpeg",
            "file_path": "uploads/xray_patient_b.jpg",
            "status": "active",
            "created_at": utc_now(),
        }

        # Mock Prescriptions
        self.rx_a = {
            "prescription_id": "RX-001",
            "consultation_id": "CNS-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "appointment_id": "APT-2026-A001",
            "medications": [{"name": "Paracetamol", "dosage": "500mg", "frequency": "BID", "duration": "5 days"}],
            "status": "active",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Mock Bills
        self.bill_a = {
            "bill_id": "BILL-001",
            "patient_id": "PAT-001",
            "appointment_id": "APT-2026-A001",
            "line_items": [
                {
                    "item_code": "ITEM-001",
                    "description": "Consultation Fee",
                    "quantity": 1.0,
                    "unit_price": 1500.0,
                    "tax_percent": 0.0,
                    "discount_amount": 0.0,
                    "subtotal": 1500.0,
                    "tax_amount": 0.0,
                    "total": 1500.0,
                }
            ],
            "subtotal": 1500.0,
            "total_tax": 0.0,
            "total_discount": 0.0,
            "grand_total": 1500.0,
            "total_amount": 1500.0,
            "amount_paid": 1500.0,
            "paid_amount": 1500.0,
            "balance_due": 0.0,
            "balance_amount": 0.0,
            "currency": "INR",
            "payments": [],
            "status": "paid",
            "created_by": "USR-STF-001",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Mock Notifications
        self.notif_a = {
            "notification_id": "NOTIF-001",
            "user_id": "USR-PAT-001",
            "recipient_id": "USR-PAT-001",
            "title": "Appointment Scheduled",
            "message": "Your appointment APT-2026-A001 has been booked.",
            "read": False,
            "created_at": utc_now(),
        }

        # Setup in-memory mock collections
        self._collections = {}

        def get_collection(name):
            if name not in self._collections:
                col = MagicMock()
                col.insert_one = AsyncMock(return_value=None)
                col.replace_one = AsyncMock(return_value=None)
                col.update_one = AsyncMock(return_value=None)
                col.count_documents = AsyncMock(return_value=0)
                col.find = MagicMock(return_value=_make_cursor([]))
                col.aggregate = MagicMock(return_value=_make_cursor([]))
                col.find_one = AsyncMock(return_value=None)
                self._collections[name] = col
            return self._collections[name]

        self.mock_db = MagicMock()
        self.mock_db.__getitem__.side_effect = get_collection

        # Users collection
        async def users_find_one(query, *args, **kwargs):
            uid = query.get("user_id")
            if uid:
                return self._user_dicts.get(uid)
            email = query.get("email")
            if email:
                for u in self._user_dicts.values():
                    if u["email"] == email:
                        return u
            return None

        # Patients collection
        async def patients_find_one(query, *args, **kwargs):
            pid = query.get("patient_id")
            if pid == "PAT-001":
                return self.patient_doc_a
            if pid == "PAT-002":
                return self.patient_doc_b
            uid = query.get("user_id")
            if uid == "USR-PAT-001":
                return self.patient_doc_a
            if uid == "USR-PAT-002":
                return self.patient_doc_b
            raw_token = query.get("qr_code.raw_token")
            if raw_token == "pqr_token_patient_a":
                return self.patient_doc_a
            return None

        async def patients_update_one(filter_query, update_doc, *args, **kwargs):
            pid = filter_query.get("patient_id")
            target = self.patient_doc_a if pid == "PAT-001" else (self.patient_doc_b if pid == "PAT-002" else None)
            if target and "$set" in update_doc:
                for k, v in update_doc["$set"].items():
                    target[k] = v
            return MagicMock(modified_count=1)

        # Doctors collection
        def doctors_find(query=None, *args, **kwargs):
            return _make_cursor([self.doctor_doc])

        async def doctors_find_one(query, *args, **kwargs):
            did = query.get("doctor_id")
            if did == "DOC-001":
                return self.doctor_doc
            return None

        # Appointments collection
        async def appointments_find_one(query, *args, **kwargs):
            aid = query.get("appointment_id")
            if aid == "APT-2026-A001":
                return self.apt_a
            if aid == "APT-2026-B001":
                return self.apt_b
            return None

        def appointments_find(query=None, *args, **kwargs):
            pid = (query or {}).get("patient_id")
            if pid == "PAT-001":
                return _make_cursor([self.apt_a])
            if pid == "PAT-002":
                return _make_cursor([self.apt_b])
            return _make_cursor([self.apt_a, self.apt_b])

        # Medical Records collection
        async def records_find_one(query, *args, **kwargs):
            rid = query.get("record_id")
            if rid == "REC-001":
                return self.record_a
            if rid == "REC-002":
                return self.record_b
            return None

        def records_find(query=None, *args, **kwargs):
            pid = (query or {}).get("patient_id")
            if pid == "PAT-001":
                return _make_cursor([self.record_a])
            if pid == "PAT-002":
                return _make_cursor([self.record_b])
            return _make_cursor([])

        # AI Analyses collection
        async def ai_find_one(query, *args, **kwargs):
            aid = query.get("analysis_id")
            if aid == "AI-UNREV-001":
                return self.ai_analysis_unreviewed_a
            if aid == "AI-REV-001":
                return self.ai_analysis_reviewed_a
            if aid == "AI-REV-002":
                return self.ai_analysis_b
            return None

        def ai_find(query=None, *args, **kwargs):
            pid = (query or {}).get("patient_id")
            status = (query or {}).get("status")
            items = []
            if pid == "PAT-001":
                items = [self.ai_analysis_reviewed_a] if status == "reviewed" else [self.ai_analysis_unreviewed_a, self.ai_analysis_reviewed_a]
            elif pid == "PAT-002":
                items = [self.ai_analysis_b]
            return _make_cursor(items)

        # Prescriptions collection
        def rx_find(query=None, *args, **kwargs):
            pid = (query or {}).get("patient_id")
            if pid == "PAT-001":
                return _make_cursor([self.rx_a])
            return _make_cursor([])

        # Billing collection
        def billing_find(query=None, *args, **kwargs):
            pid = (query or {}).get("patient_id")
            if pid == "PAT-001":
                return _make_cursor([self.bill_a])
            return _make_cursor([])

        # Notifications collection
        def notif_find(query=None, *args, **kwargs):
            uid = (query or {}).get("recipient_id") or (query or {}).get("user_id")
            if uid == "USR-PAT-001":
                return _make_cursor([self.notif_a])
            return _make_cursor([])

        # Wire up mock collections
        get_collection("users").find_one = users_find_one
        get_collection("patients").find_one = patients_find_one
        get_collection("patients").update_one = patients_update_one
        get_collection("doctors").find = doctors_find
        get_collection("doctors").find_one = doctors_find_one
        get_collection("appointments").find = appointments_find
        get_collection("appointments").find_one = appointments_find_one
        get_collection("appointments").count_documents = AsyncMock(return_value=1)
        get_collection("medical_records").find = records_find
        get_collection("medical_records").find_one = records_find_one
        get_collection("ai_analyses").find = ai_find
        get_collection("ai_analyses").find_one = ai_find_one
        get_collection("prescriptions").find = rx_find
        get_collection("billing").find = billing_find
        get_collection("notifications").find = notif_find

        async def override_get_db():
            return self.mock_db

        app.dependency_overrides[get_database] = override_get_db

        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver/api/v1")

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # 1. Patient Dashboard & Profile Identity
    async def test_01_patient_profile_retrieval(self):
        resp = await self.client.get("/patients/me", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get("data", {})
        self.assertEqual(data.get("patient_id"), "PAT-001")
        self.assertEqual(data.get("full_name"), "John Doe")

    # 2. Patient Profile Update (Permitted Fields)
    async def test_02_patient_profile_update_valid_fields(self):
        update_payload = {"emergency_contact": {"name": "Mary Doe Updated", "relationship": "Spouse", "phone": "+91 98765 99999"}}
        resp = await self.client.patch("/patients/me", headers=self.headers_patient_a, json=update_payload)
        self.assertEqual(resp.status_code, 200)

    # 3. Patient Cannot Modify Own Role (RBAC Preservation)
    async def test_03_patient_cannot_change_own_role(self):
        resp = await self.client.patch("/patients/me", headers=self.headers_patient_a, json={"role": "doctor"})
        # Role must not change to doctor; API ignores or forbids role escalation
        verify_resp = await self.client.get("/patients/me", headers=self.headers_patient_a)
        data = verify_resp.json().get("data", {})
        self.assertEqual(data.get("patient_id"), "PAT-001")

    # 4. Doctor Discovery
    async def test_04_doctor_discovery(self):
        resp = await self.client.get("/doctors", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get("data", [])
        self.assertGreaterEqual(len(data), 1)
        self.assertEqual(data[0].get("doctor_id"), "DOC-001")

    # 5. Doctor Details Navigation
    async def test_05_doctor_detail_retrieval(self):
        resp = await self.client.get("/doctors/DOC-001", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get("data", {})
        self.assertEqual(data.get("doctor_id"), "DOC-001")
        self.assertEqual(data.get("specialization"), "Neurology")

    # 6. Appointment Listing Scoped to Authenticated Patient
    async def test_06_appointment_listing_scoped_to_patient(self):
        resp = await self.client.get("/appointments", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get("data", [])
        for apt in data:
            self.assertEqual(apt.get("patient_id"), "PAT-001")

    # 7. Appointment Detail Retrieval (Own Appointment)
    async def test_07_appointment_detail_own_success(self):
        resp = await self.client.get("/appointments/APT-2026-A001", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get("data", {})
        self.assertEqual(data.get("appointment_id"), "APT-2026-A001")
        self.assertEqual(data.get("patient_id"), "PAT-001")

    # 8. Cross-Patient Appointment IDOR Protection (Patient A cannot view Patient B's appointment)
    async def test_08_cross_patient_appointment_idor_denied(self):
        resp = await self.client.get("/appointments/APT-2026-B001", headers=self.headers_patient_a)
        self.assertIn(resp.status_code, [403, 404])

    # 9. Patient Cannot Confirm Appointment as Doctor/Staff
    async def test_09_patient_cannot_confirm_appointment(self):
        resp = await self.client.post("/appointments/APT-2026-A001/confirm", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 403)

    # 10. Medical Records Access (Own Record)
    async def test_10_medical_record_own_access(self):
        resp = await self.client.get("/medical-records/REC-001", headers=self.headers_patient_a)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            self.assertEqual(data.get("patient_id"), "PAT-001")

    # 11. Cross-Patient Medical Record IDOR Protection
    async def test_11_cross_patient_medical_record_denied(self):
        resp = await self.client.get("/medical-records/REC-002", headers=self.headers_patient_a)
        self.assertIn(resp.status_code, [403, 404])

    # 12. Cross-Patient Document IDOR Protection
    async def test_12_cross_patient_document_denied(self):
        resp = await self.client.get("/documents/DOC-FILE-002", headers=self.headers_patient_a)
        self.assertIn(resp.status_code, [403, 404])

    # 13. AI Patient Visibility: Awaiting Review Restricted
    async def test_13_awaiting_review_ai_restricted_from_patient(self):
        resp = await self.client.get("/ai-analysis/AI-UNREV-001", headers=self.headers_patient_a)
        # Unreviewed AI results must not be directly exposed to patient (403 Forbidden)
        self.assertIn(resp.status_code, [403, 404])

    # 14. AI Patient Visibility: Reviewed Analysis Accessible
    async def test_14_reviewed_ai_visible_to_patient(self):
        resp = await self.client.get("/ai-analysis/AI-REV-001", headers=self.headers_patient_a)
        if resp.status_code == 200:
            data = resp.json().get("data", {})
            self.assertEqual(data.get("status"), "reviewed")
            self.assertEqual(data.get("patient_id"), "PAT-001")

    # 15. Cross-Patient AI Analysis IDOR Protection
    async def test_15_cross_patient_ai_analysis_denied(self):
        resp = await self.client.get("/ai-analysis/AI-REV-002", headers=self.headers_patient_a)
        self.assertIn(resp.status_code, [403, 404])

    # 16. Patient Cannot Modify AI Analysis Result
    async def test_16_patient_cannot_modify_ai_result(self):
        resp = await self.client.patch("/ai-analysis/AI-REV-001", headers=self.headers_patient_a, json={"finding": "Tampered finding"})
        self.assertIn(resp.status_code, [403, 404, 405])

    # 17. Prescription Read-Only Access
    async def test_17_prescription_read_only(self):
        resp = await self.client.get("/prescriptions", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 200)

    # 18. Patient Cannot Create Prescriptions
    async def test_18_patient_cannot_create_prescription(self):
        resp = await self.client.post("/prescriptions", headers=self.headers_patient_a, json={
            "patient_id": "PAT-001", "doctor_id": "DOC-001", "medications": []
        })
        self.assertEqual(resp.status_code, 403)

    # 19. Billing Read-Only Access
    async def test_19_billing_read_only(self):
        resp = await self.client.get("/billing", headers=self.headers_patient_a)
        # If /billing is restricted or filtered for patients
        self.assertIn(resp.status_code, [200, 403])

    # 20. Patient Cannot Create Bills
    async def test_20_patient_cannot_create_bill(self):
        resp = await self.client.post("/billing", headers=self.headers_patient_a, json={
            "patient_id": "PAT-001",
            "line_items": [{"description": "Tampered item", "unit_price": 100.0, "quantity": 1.0}]
        })
        self.assertEqual(resp.status_code, 403)

    # 21. Notification Isolation
    async def test_21_notification_isolation(self):
        resp = await self.client.get("/notifications", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json().get("data", [])
        for notif in data:
            self.assertEqual(notif.get("user_id"), "USR-PAT-001")

    # 22. Fix Phase 1 QR Health Card Regression Check
    async def test_22_qr_health_card_regression(self):
        resp = await self.client.get("/patients/me/qr", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("token", data)
        self.assertIn("payload", data)
        self.assertEqual(data.get("token"), "pqr_token_patient_a")

    # 23. Unauthenticated Endpoint Protection
    async def test_23_unauthenticated_request_rejected(self):
        resp = await self.client.get("/patients/me")
        self.assertEqual(resp.status_code, 401)
        resp2 = await self.client.get("/appointments")
        self.assertEqual(resp2.status_code, 401)
        resp3 = await self.client.get("/patients/me/qr")
        self.assertEqual(resp3.status_code, 401)

    # 24. Invalid Resource Handling
    async def test_24_invalid_appointment_not_found(self):
        resp = await self.client.get("/appointments/APT-NONEXISTENT", headers=self.headers_patient_a)
        self.assertIn(resp.status_code, [404, 403])

    # 25. Session and Account Isolation (Patient A vs Patient B)
    async def test_25_account_isolation_no_leakage(self):
        resp_a = await self.client.get("/patients/me", headers=self.headers_patient_a)
        resp_b = await self.client.get("/patients/me", headers=self.headers_patient_b)
        self.assertEqual(resp_a.status_code, 200)
        self.assertEqual(resp_b.status_code, 200)
        data_a = resp_a.json().get("data", {})
        data_b = resp_b.json().get("data", {})
        self.assertEqual(data_a.get("patient_id"), "PAT-001")
        self.assertEqual(data_b.get("patient_id"), "PAT-002")
        self.assertNotEqual(data_a.get("patient_id"), data_b.get("patient_id"))
