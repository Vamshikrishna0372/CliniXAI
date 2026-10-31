"""
Comprehensive Hardened Test Suite for Phase 8: Medical Records
Production Verification, RBAC Matrix, IDOR Defense, and Object-Level Authorization
"""

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


def create_mock_db():
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


class TestMedicalRecordsPhase8(unittest.IsolatedAsyncioTestCase):
    """End-to-end unit & security verification for Phase 8 Medical Records."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # Patient A (Alice)
        self.patient_a_user = UserInDB(
            user_id="USR-2026-PAT-A", email="patient.a@clinixai.com", full_name="Alice Patient",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_a_dict = {
            "patient_id": "PAT-2026-A01",
            "user_id": self.patient_a_user.user_id,
            "first_name": "Alice",
            "last_name": "Patient",
            "email": self.patient_a_user.email,
            "status": "active",
        }

        # Patient B (Bob)
        self.patient_b_user = UserInDB(
            user_id="USR-2026-PAT-B", email="patient.b@clinixai.com", full_name="Bob Patient",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_b_dict = {
            "patient_id": "PAT-2026-B02",
            "user_id": self.patient_b_user.user_id,
            "first_name": "Bob",
            "last_name": "Patient",
            "email": self.patient_b_user.email,
            "status": "active",
        }

        # Doctor 1 (Dr. Arjun Rao - Treating Doctor for Patient A)
        self.doctor_1_user = UserInDB(
            user_id="USR-2026-DOC-1", email="doctor.one@clinixai.com", full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.doctor_1_dict = {
            "doctor_id": "DOC-2026-001",
            "user_id": self.doctor_1_user.user_id,
            "first_name": "Arjun",
            "last_name": "Rao",
            "email": self.doctor_1_user.email,
            "status": "active",
        }

        # Doctor 2 (Dr. Priya Sharma - Unrelated Doctor with NO relationship to Patient A)
        self.doctor_2_user = UserInDB(
            user_id="USR-2026-DOC-2", email="doctor.two@clinixai.com", full_name="Dr. Priya Sharma",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.doctor_2_dict = {
            "doctor_id": "DOC-2026-002",
            "user_id": self.doctor_2_user.user_id,
            "first_name": "Priya",
            "last_name": "Sharma",
            "email": self.doctor_2_user.email,
            "status": "active",
        }

        # Staff User
        self.staff_user = UserInDB(
            user_id="USR-2026-STF-1", email="staff@clinixai.com", full_name="Front Desk Staff",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )

        # Hospital Admin
        self.admin_user = UserInDB(
            user_id="USR-2026-ADM-1", email="admin@clinixai.com", full_name="Hospital Administrator",
            role=UserRole.HOSPITAL_ADMIN, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )

        # Disabled User
        self.disabled_user = UserInDB(
            user_id="USR-2026-DIS-1", email="disabled@clinixai.com", full_name="Disabled User",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.SUSPENDED
        )

        # Deleted User ID (token valid, but record deleted in DB)
        self.deleted_user_id = "USR-2026-DEL-1"

        # Access Tokens
        self.token_pat_a = create_access_token(user_id=self.patient_a_user.user_id, role=self.patient_a_user.role.value)
        self.token_pat_b = create_access_token(user_id=self.patient_b_user.user_id, role=self.patient_b_user.role.value)
        self.token_doc_1 = create_access_token(user_id=self.doctor_1_user.user_id, role=self.doctor_1_user.role.value)
        self.token_doc_2 = create_access_token(user_id=self.doctor_2_user.user_id, role=self.doctor_2_user.role.value)
        self.token_staff = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)
        self.token_admin = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.token_disabled = create_access_token(user_id=self.disabled_user.user_id, role=self.disabled_user.role.value)
        self.token_deleted = create_access_token(user_id=self.deleted_user_id, role="patient")

        self.headers_pat_a = {"Authorization": f"Bearer {self.token_pat_a}"}
        self.headers_pat_b = {"Authorization": f"Bearer {self.token_pat_b}"}
        self.headers_doc_1 = {"Authorization": f"Bearer {self.token_doc_1}"}
        self.headers_doc_2 = {"Authorization": f"Bearer {self.token_doc_2}"}
        self.headers_staff = {"Authorization": f"Bearer {self.token_staff}"}
        self.headers_admin = {"Authorization": f"Bearer {self.token_admin}"}
        self.headers_disabled = {"Authorization": f"Bearer {self.token_disabled}"}
        self.headers_deleted = {"Authorization": f"Bearer {self.token_deleted}"}

        # User lookup helper in mock DB
        users_map = {
            self.patient_a_user.user_id: self.patient_a_user.to_mongo_dict(),
            self.patient_b_user.user_id: self.patient_b_user.to_mongo_dict(),
            self.doctor_1_user.user_id: self.doctor_1_user.to_mongo_dict(),
            self.doctor_2_user.user_id: self.doctor_2_user.to_mongo_dict(),
            self.staff_user.user_id: self.staff_user.to_mongo_dict(),
            self.admin_user.user_id: self.admin_user.to_mongo_dict(),
            self.disabled_user.user_id: self.disabled_user.to_mongo_dict(),
        }
        self.mock_db["users"].find_one.side_effect = lambda q: users_map.get(q.get("user_id"))

        # Pre-seeded record belonging to Patient A (created by Doctor 1)
        self.record_a = {
            "record_id": "MR-2026-A00001",
            "patient_id": "PAT-2026-A01",
            "doctor_id": "DOC-2026-001",
            "appointment_id": "APT-2026-A01",
            "consultation_id": "CNS-2026-A01",
            "record_type": "clinical_document",
            "title": "Comprehensive Cardiac Assessment",
            "description": "Patient presented with mild tachycardia",
            "diagnosis": "Sinus Tachycardia (R00.0)",
            "clinical_notes": "ECG confirms sinus tachycardia at 108 bpm. Heart sounds normal.",
            "treatment_plan": "Oral hydration and follow-up in 2 weeks.",
            "clinical_date": "2026-09-20",
            "file": None,
            "uploaded_by": self.doctor_1_user.user_id,
            "source": "doctor",
            "status": "active",
            "is_deleted": False,
            "ai_eligible": False,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }

        # Pre-seeded record belonging to Patient B
        self.record_b = {
            "record_id": "MR-2026-B00002",
            "patient_id": "PAT-2026-B02",
            "doctor_id": "DOC-2026-002",
            "appointment_id": "APT-2026-B02",
            "record_type": "clinical_document",
            "title": "Neurology Initial Evaluation",
            "description": "Patient presented with migraine",
            "diagnosis": "Migraine without aura (G43.0)",
            "clinical_notes": "Neurological exam normal.",
            "treatment_plan": "Triptan PRN.",
            "clinical_date": "2026-09-20",
            "file": None,
            "uploaded_by": self.doctor_2_user.user_id,
            "source": "doctor",
            "status": "active",
            "is_deleted": False,
            "ai_eligible": False,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # =========================================================================
    # SECTION 3: SECURITY TEST MATRIX (A through I)
    # =========================================================================

    async def test_security_a_unauthenticated_request(self) -> None:
        """A. Unauthenticated request to medical records returns HTTP 401."""
        res = await self.client.get("/api/v1/medical-records")
        self.assertEqual(res.status_code, 401)

    async def test_security_b_patient_own_record(self) -> None:
        """B. Patient viewing own medical record returns HTTP 200."""
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_a

        res = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_pat_a)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["record_id"], self.record_a["record_id"])
        self.assertEqual(res.json()["data"]["patient_id"], "PAT-2026-A01")

    async def test_security_c_patient_another_patient_record(self) -> None:
        """C. Patient attempting to view another patient's record returns HTTP 403."""
        self.mock_db["patients"].find_one.return_value = self.patient_b_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_a

        res = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_pat_b)
        self.assertEqual(res.status_code, 403)
        self.assertIn("not authorized", res.json()["error"]["message"].lower())

    async def test_security_d_doctor_authorized_patient(self) -> None:
        """D. Doctor with active care relationship viewing patient record returns HTTP 200."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_a
        self.mock_db["appointments"].find_one.return_value = {
            "appointment_id": "APT-2026-A01", "patient_id": "PAT-2026-A01", "doctor_id": "DOC-2026-001"
        }

        res = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_doc_1)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["record_id"], self.record_a["record_id"])

    async def test_security_e_doctor_unauthorized_patient(self) -> None:
        """E. Doctor with NO care relationship attempting to view patient record returns HTTP 403."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_2_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_a
        self.mock_db["appointments"].find_one.return_value = None
        self.mock_db["consultations"].find_one.return_value = None

        res = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_doc_2)
        self.assertEqual(res.status_code, 403)
        self.assertIn("not authorized", res.json()["error"]["message"].lower())

    async def test_security_f_staff_view_record(self) -> None:
        """F. Hospital Staff viewing medical record returns HTTP 200."""
        self.mock_db["medical_records"].find_one.return_value = self.record_a

        res = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_staff)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["record_id"], self.record_a["record_id"])

    async def test_security_g_hospital_admin_view_record(self) -> None:
        """G. Hospital Admin viewing medical record returns HTTP 200."""
        self.mock_db["medical_records"].find_one.return_value = self.record_a

        res = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_admin)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["record_id"], self.record_a["record_id"])

    async def test_security_h_disabled_user(self) -> None:
        """H. Disabled / Suspended user access returns HTTP 403."""
        res = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_disabled)
        self.assertEqual(res.status_code, 403)
        self.assertIn("access denied", res.json()["error"]["message"].lower())

    async def test_security_i_deleted_user(self) -> None:
        """I. Deleted user access returns HTTP 401."""
        res = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_deleted)
        self.assertEqual(res.status_code, 401)
        self.assertIn("no longer exists", res.json()["error"]["message"].lower())

    # =========================================================================
    # SECTION 4: IDOR TESTING
    # =========================================================================

    async def test_idor_cross_patient_get_denied(self) -> None:
        """IDOR: Patient A attempting GET Patient B's record returns HTTP 403."""
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_b

        res = await self.client.get(f"/api/v1/medical-records/{self.record_b['record_id']}", headers=self.headers_pat_a)
        self.assertEqual(res.status_code, 403)

    async def test_idor_cross_patient_patch_denied(self) -> None:
        """IDOR: Patient A attempting PATCH Patient B's record returns HTTP 403."""
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_b

        res = await self.client.patch(
            f"/api/v1/medical-records/{self.record_b['record_id']}",
            json={"title": "Hacked Title"},
            headers=self.headers_pat_a
        )
        self.assertEqual(res.status_code, 403)

    async def test_idor_cross_patient_delete_denied(self) -> None:
        """IDOR: Patient A attempting DELETE Patient B's record returns HTTP 403."""
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_b

        res = await self.client.delete(f"/api/v1/medical-records/{self.record_b['record_id']}", headers=self.headers_pat_a)
        self.assertEqual(res.status_code, 403)

    async def test_idor_patient_id_substitution_on_create_denied(self) -> None:
        """IDOR: Patient A specifying Patient B's patient_id in creation returns HTTP 403."""
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict

        payload = {
            "title": "Malicious Substituted Record",
            "patient_id": "PAT-2026-B02",
        }
        res = await self.client.post("/api/v1/medical-records", json=payload, headers=self.headers_pat_a)
        self.assertEqual(res.status_code, 403)
        self.assertIn("cannot create medical records for another patient", res.json()["error"]["message"].lower())

    async def test_idor_patient_cannot_modify_clinical_fields(self) -> None:
        """IDOR: Patient attempting to overwrite privileged clinical fields returns HTTP 403."""
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_a

        res = await self.client.patch(
            f"/api/v1/medical-records/{self.record_a['record_id']}",
            json={"diagnosis": "Forged Self-Diagnosis"},
            headers=self.headers_pat_a
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("not authorized to modify clinical", res.json()["error"]["message"].lower())

    # =========================================================================
    # SECTION 5: MASS ASSIGNMENT DEFENSE
    # =========================================================================

    async def test_mass_assignment_protection_on_patch(self) -> None:
        """Mass Assignment: Injected protected fields in PATCH are completely ignored."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_a
        self.mock_db["appointments"].find_one.return_value = {
            "patient_id": "PAT-2026-A01", "doctor_id": "DOC-2026-001"
        }

        malicious_payload = {
            "title": "Legitimate Title Update",
            "patient_id": "PAT-TWO-002",
            "doctor_id": "DOC-SHARMA-002",
            "created_by": "OTHER_USER",
            "created_at": "2020-01-01",
            "updated_at": "2020-01-01",
            "status": "approved",
            "is_deleted": True,
        }

        res = await self.client.patch(
            f"/api/v1/medical-records/{self.record_a['record_id']}",
            json=malicious_payload,
            headers=self.headers_doc_1
        )
        self.assertEqual(res.status_code, 200)

        # Inspect MongoDB update call arguments directly
        update_call = self.mock_db["medical_records"].update_one.call_args
        set_payload = update_call[0][1]["$set"]
        self.assertIn("title", set_payload)
        self.assertEqual(set_payload["title"], "Legitimate Title Update")
        self.assertNotIn("patient_id", set_payload)
        self.assertNotIn("doctor_id", set_payload)
        self.assertNotIn("created_by", set_payload)
        self.assertNotIn("created_at", set_payload)
        self.assertNotIn("status", set_payload)
        self.assertNotIn("is_deleted", set_payload)

    async def test_mass_assignment_protection_on_create(self) -> None:
        """Mass Assignment: Injected server-controlled fields in POST are discarded/overridden."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["appointments"].find_one.return_value = {
            "appointment_id": "APT-2026-A01", "patient_id": "PAT-2026-A01", "doctor_id": "DOC-2026-001"
        }

        payload = {
            "title": "Cardiology Consultation Summary",
            "patient_id": "PAT-2026-A01",
            "appointment_id": "APT-2026-A01",
            # Injected fields
            "doctor_id": "DOC-HACKED-999",
            "created_by": "HACKER",
            "created_at": "2020-01-01T00:00:00Z",
            "status": "approved",
            "is_deleted": True,
        }

        res = await self.client.post("/api/v1/medical-records", json=payload, headers=self.headers_doc_1)
        self.assertEqual(res.status_code, 201)

        insert_call = self.mock_db["medical_records"].insert_one.call_args
        inserted_doc = insert_call[0][0]
        # Doctor ID must be server-resolved DOC-2026-001, NOT DOC-HACKED-999
        self.assertEqual(inserted_doc["doctor_id"], "DOC-2026-001")
        # is_deleted must be False
        self.assertFalse(inserted_doc["is_deleted"])
        # status must be active
        self.assertEqual(inserted_doc["status"], "active")

    # =========================================================================
    # SECTION 6: INPUT VALIDATION
    # =========================================================================

    async def test_validation_invalid_record_id_returns_404(self) -> None:
        """Validation: Non-existent record_id returns HTTP 404."""
        self.mock_db["medical_records"].find_one.return_value = None
        res = await self.client.get("/api/v1/medical-records/MR-NONEXISTENT", headers=self.headers_admin)
        self.assertEqual(res.status_code, 404)

    async def test_validation_invalid_patient_id_returns_404(self) -> None:
        """Validation: Creating record with non-existent patient_id returns HTTP 404."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = None

        res = await self.client.post(
            "/api/v1/medical-records",
            json={"title": "Test Title", "patient_id": "PAT-INVALID-999"},
            headers=self.headers_doc_1
        )
        self.assertEqual(res.status_code, 404)

    async def test_validation_invalid_appointment_id_returns_404(self) -> None:
        """Validation: Creating record with non-existent appointment_id returns HTTP 404."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["appointments"].find_one.return_value = None

        res = await self.client.post(
            "/api/v1/medical-records",
            json={"title": "Test Title", "patient_id": "PAT-2026-A01", "appointment_id": "APT-NONEXISTENT"},
            headers=self.headers_doc_1
        )
        self.assertEqual(res.status_code, 404)

    async def test_validation_invalid_consultation_id_returns_404(self) -> None:
        """Validation: Creating record with non-existent consultation_id returns HTTP 404."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["consultations"].find_one.return_value = None

        res = await self.client.post(
            "/api/v1/medical-records",
            json={"title": "Test Title", "patient_id": "PAT-2026-A01", "consultation_id": "CNS-NONEXISTENT"},
            headers=self.headers_doc_1
        )
        self.assertEqual(res.status_code, 404)

    async def test_validation_invalid_record_type_returns_422(self) -> None:
        """Validation: Invalid record_type returns HTTP 422."""
        res = await self.client.post(
            "/api/v1/medical-records",
            json={"title": "Test Title", "patient_id": "PAT-2026-A01", "record_type": "invalid_type_xyz"},
            headers=self.headers_admin
        )
        self.assertEqual(res.status_code, 422)

    async def test_validation_malformed_clinical_date_returns_422(self) -> None:
        """Validation: Malformed clinical_date returns HTTP 422."""
        res = await self.client.post(
            "/api/v1/medical-records",
            json={"title": "Test Title", "patient_id": "PAT-2026-A01", "clinical_date": "not-a-valid-date"},
            headers=self.headers_admin
        )
        self.assertEqual(res.status_code, 422)

    async def test_validation_empty_or_missing_title_returns_422(self) -> None:
        """Validation: Missing or whitespace-only title returns HTTP 422."""
        # Missing title
        res1 = await self.client.post(
            "/api/v1/medical-records",
            json={"patient_id": "PAT-2026-A01"},
            headers=self.headers_admin
        )
        self.assertEqual(res1.status_code, 422)

        # Whitespace-only title
        res2 = await self.client.post(
            "/api/v1/medical-records",
            json={"title": "   ", "patient_id": "PAT-2026-A01"},
            headers=self.headers_admin
        )
        self.assertEqual(res2.status_code, 422)

    async def test_validation_oversized_text_returns_422(self) -> None:
        """Validation: Oversized text fields return HTTP 422."""
        oversized_title = "A" * 205
        res = await self.client.post(
            "/api/v1/medical-records",
            json={"title": oversized_title, "patient_id": "PAT-2026-A01"},
            headers=self.headers_admin
        )
        self.assertEqual(res.status_code, 422)

    async def test_validation_invalid_status_query_returns_422(self) -> None:
        """Validation: Querying with invalid status returns HTTP 422."""
        res = await self.client.get("/api/v1/medical-records?status=invalid_status_abc", headers=self.headers_admin)
        self.assertEqual(res.status_code, 422)

    # =========================================================================
    # SECTION 7: APPOINTMENT RELATIONSHIP INTEGRITY
    # =========================================================================

    async def test_appointment_relationship_mismatched_patient_rejected(self) -> None:
        """Appointment Integrity: Appointment belongs to Patient B, attempting record for Patient A returns 400."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        # Appointment belongs to Patient B
        self.mock_db["appointments"].find_one.return_value = {
            "appointment_id": "APT-2026-B02", "patient_id": "PAT-2026-B02", "doctor_id": "DOC-2026-001"
        }

        payload = {
            "patient_id": "PAT-2026-A01",
            "appointment_id": "APT-2026-B02",
            "title": "Mismatched Patient Record",
        }
        res = await self.client.post("/api/v1/medical-records", json=payload, headers=self.headers_doc_1)
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not belong to the target patient", res.json()["error"]["message"].lower())

    async def test_appointment_relationship_mismatched_doctor_rejected(self) -> None:
        """Appointment Integrity: Appointment belongs to Doctor 2, Doctor 1 attempting record returns 403."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        # Appointment belongs to Doctor 2
        self.mock_db["appointments"].find_one.return_value = {
            "appointment_id": "APT-2026-A01", "patient_id": "PAT-2026-A01", "doctor_id": "DOC-2026-002"
        }

        payload = {
            "patient_id": "PAT-2026-A01",
            "appointment_id": "APT-2026-A01",
            "title": "Mismatched Doctor Record",
        }
        res = await self.client.post("/api/v1/medical-records", json=payload, headers=self.headers_doc_1)
        self.assertEqual(res.status_code, 403)
        self.assertIn("does not belong to this doctor", res.json()["error"]["message"].lower())

    # =========================================================================
    # SECTION 8: CONSULTATION RELATIONSHIP INTEGRITY
    # =========================================================================

    async def test_consultation_relationship_mismatched_patient_rejected(self) -> None:
        """Consultation Integrity: Consultation belongs to Patient B, attempting record for Patient A returns 400."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        # Consultation belongs to Patient B
        self.mock_db["consultations"].find_one.return_value = {
            "consultation_id": "CNS-2026-B02", "patient_id": "PAT-2026-B02", "doctor_id": "DOC-2026-001"
        }

        payload = {
            "patient_id": "PAT-2026-A01",
            "consultation_id": "CNS-2026-B02",
            "title": "Mismatched Patient Consultation",
        }
        res = await self.client.post("/api/v1/medical-records", json=payload, headers=self.headers_doc_1)
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not belong to the target patient", res.json()["error"]["message"].lower())

    async def test_consultation_relationship_mismatched_doctor_rejected(self) -> None:
        """Consultation Integrity: Consultation belongs to Doctor 2, Doctor 1 attempting record returns 403."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        # Consultation belongs to Doctor 2
        self.mock_db["consultations"].find_one.return_value = {
            "consultation_id": "CNS-2026-A01", "patient_id": "PAT-2026-A01", "doctor_id": "DOC-2026-002"
        }

        payload = {
            "patient_id": "PAT-2026-A01",
            "consultation_id": "CNS-2026-A01",
            "title": "Mismatched Doctor Consultation",
        }
        res = await self.client.post("/api/v1/medical-records", json=payload, headers=self.headers_doc_1)
        self.assertEqual(res.status_code, 403)
        self.assertIn("does not belong to this doctor", res.json()["error"]["message"].lower())

    async def test_consultation_relationship_mismatched_appointment_rejected(self) -> None:
        """Consultation Integrity: Provided appointment_id does not match consultation's appointment_id returns 400."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["appointments"].find_one.return_value = {
            "appointment_id": "APT-2026-A01", "patient_id": "PAT-2026-A01", "doctor_id": "DOC-2026-001"
        }
        # Consultation linked to a DIFFERENT appointment (APT-DIFFERENT)
        self.mock_db["consultations"].find_one.return_value = {
            "consultation_id": "CNS-2026-A01",
            "appointment_id": "APT-DIFFERENT",
            "patient_id": "PAT-2026-A01",
            "doctor_id": "DOC-2026-001"
        }

        payload = {
            "patient_id": "PAT-2026-A01",
            "appointment_id": "APT-2026-A01",
            "consultation_id": "CNS-2026-A01",
            "title": "Mismatched Appointment and Consultation",
        }
        res = await self.client.post("/api/v1/medical-records", json=payload, headers=self.headers_doc_1)
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not match the consultation", res.json()["error"]["message"].lower())

    # =========================================================================
    # SECTION 9: CONSULTATION -> RECORD CREATION & DUPLICATE PROTECTION
    # =========================================================================

    async def test_duplicate_consultation_record_prevented(self) -> None:
        """Duplicate Protection: Attempting to create duplicate medical record for consultation returns HTTP 409."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict
        self.mock_db["consultations"].find_one.return_value = {
            "consultation_id": "CNS-2026-A01",
            "patient_id": "PAT-2026-A01",
            "doctor_id": "DOC-2026-001"
        }
        # Already existing record with this consultation_id
        self.mock_db["medical_records"].find_one.return_value = {
            "record_id": "MR-EXISTING",
            "consultation_id": "CNS-2026-A01",
            "is_deleted": False
        }

        payload = {
            "patient_id": "PAT-2026-A01",
            "consultation_id": "CNS-2026-A01",
            "title": "Duplicate Record Attempt",
        }
        res = await self.client.post("/api/v1/medical-records", json=payload, headers=self.headers_doc_1)
        self.assertEqual(res.status_code, 409)
        self.assertIn("already associated", res.json()["error"]["message"].lower())

    async def test_consultation_completion_creates_medical_record_idempotently(self) -> None:
        """Consultation Workflow: Completing a consultation auto-creates medical record, retry does not duplicate."""
        from app.services.consultation_service import ConsultationService

        consult_data = {
            "consultation_id": "CNS-2026-COMPLETE-1",
            "appointment_id": "APT-2026-COMPLETE-1",
            "patient_id": "PAT-2026-A01",
            "doctor_id": "DOC-2026-001",
            "department_id": "DEP-CARDIO",
            "status": "in_progress",
            "clinical_assessment": {"summary": "Stable sinus tachycardia."},
            "diagnoses": [{"name": "Sinus Tachycardia", "code": "R00.0", "type": "primary"}],
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["consultations"].find_one.return_value = dict(consult_data)
        self.mock_db["medical_records"].find_one.return_value = None

        # First completion
        await ConsultationService.complete_consultation(self.mock_db, "CNS-2026-COMPLETE-1", self.doctor_1_user)

        # Verify insert_one was called on medical_records
        mr_inserts = self.mock_db["medical_records"].insert_one.call_args_list
        self.assertGreaterEqual(len(mr_inserts), 1)
        inserted_mr = mr_inserts[-1][0][0]
        self.assertEqual(inserted_mr["consultation_id"], "CNS-2026-COMPLETE-1")
        self.assertEqual(inserted_mr["patient_id"], "PAT-2026-A01")
        self.assertEqual(inserted_mr["doctor_id"], "DOC-2026-001")
        self.assertEqual(inserted_mr["diagnosis"], "Sinus Tachycardia")

        # Second completion attempt (retry)
        consult_data["status"] = "completed"
        self.mock_db["consultations"].find_one.return_value = dict(consult_data)
        self.mock_db["medical_records"].find_one.return_value = inserted_mr

        count_before = self.mock_db["medical_records"].insert_one.call_count
        await ConsultationService.complete_consultation(self.mock_db, "CNS-2026-COMPLETE-1", self.doctor_1_user)
        count_after = self.mock_db["medical_records"].insert_one.call_count

        # Zero new medical records inserted on retry
        self.assertEqual(count_before, count_after)

    # =========================================================================
    # SECTION 10: SOFT DELETE LIFECYCLE
    # =========================================================================

    async def test_soft_delete_lifecycle(self) -> None:
        """Soft Delete: Marking is_deleted=True hides record from patient/doctor (404), accessible by admin (200)."""
        self.mock_db["doctors"].find_one.return_value = self.doctor_1_dict
        self.mock_db["medical_records"].find_one.return_value = self.record_a
        self.mock_db["appointments"].find_one.return_value = {
            "patient_id": "PAT-2026-A01", "doctor_id": "DOC-2026-001"
        }

        # Doctor soft-deletes the record
        del_res = await self.client.delete(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_doc_1)
        self.assertEqual(del_res.status_code, 200)

        # Verify update_one set is_deleted=True
        update_call = self.mock_db["medical_records"].update_one.call_args
        set_dict = update_call[0][1]["$set"]
        self.assertTrue(set_dict["is_deleted"])
        self.assertIn("deleted_at", set_dict)
        self.assertEqual(set_dict["deleted_by"], self.doctor_1_user.user_id)

        # Now mock the record as deleted in DB
        deleted_record = dict(self.record_a)
        deleted_record["is_deleted"] = True
        self.mock_db["medical_records"].find_one.return_value = deleted_record
        self.mock_db["patients"].find_one.return_value = self.patient_a_dict

        # Patient gets 404
        get_pat = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_pat_a)
        self.assertEqual(get_pat.status_code, 404)

        # Doctor gets 404
        get_doc = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_doc_1)
        self.assertEqual(get_doc.status_code, 404)

        # Admin can still access (HTTP 200)
        get_adm = await self.client.get(f"/api/v1/medical-records/{self.record_a['record_id']}", headers=self.headers_admin)
        self.assertEqual(get_adm.status_code, 200)


if __name__ == "__main__":
    unittest.main()
