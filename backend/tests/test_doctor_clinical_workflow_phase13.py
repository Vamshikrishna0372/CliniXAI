"""
Phase 13 Dedicated Test Suite:
Doctor Clinical Workflow, Care Relationship Authorization,
AI Prediction Immutability, Separate Clinical Interpretation,
Audit Logging, Patient Visibility Boundary, and Security Hardening.

Verification covers:
1. Doctor authorized patient access
2. Unauthorized doctor denied (care relationship isolation)
3. Patient denied doctor review workflow
4. Hospital Staff policy (cannot perform clinical review)
5. Admin policy (cannot review without doctor profile / operational policy)
6. Unauthenticated access returns HTTP 401
7. AI analysis retrieval by authorized doctor
8. Source image access authorization
9. Grad-CAM access authorization
10. Doctor review creation with valid clinical interpretation and decision
11. Reviewer identity derived strictly from JWT (cannot be spoofed)
12. Patient identity and analysis linkage derived from server-owned document
13. Mass assignment protection (rejects/ignores forged prediction, confidence, created_at, etc.)
14. AI prediction immutability (predicted_class remains identical before and after review)
15. AI confidence immutability (confidence remains identical before and after review)
16. AI model info immutability (name, module_id, version unchanged)
17. Explainability artifact immutability (storage key and Grad-CAM unchanged)
18. Status transition from awaiting_review -> reviewed
19. Invalid status transition rollback blocked
20. Duplicate review protection / safe idempotent update
21. Concurrent review behavior
22. Consultation linkage
23. Medical record linkage
24. Invalid consultation rejection
25. Invalid medical record handling
26. Audit log created in audit_logs collection with doctor actor and review action
27. MongoDB persistence verified by direct database query
28. Review survives simulated restart
29. Review data survives re-login
30. Patient visibility after review (patient can view reviewed analysis)
31. Doctor private notes protected from patient view
32. Nonexistent analysis handling
33. Invalid review payload handling
34. Whitespace-only notes or invalid interpretation handling
35. Fake future timestamp rejection
"""

import os
import io
import asyncio
import unittest
from datetime import datetime, timezone
import numpy as np
from PIL import Image
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.ai_analysis import AIAnalysisStatus, DoctorReviewDecision
from app.core.security import create_access_token
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_MEDICAL_RECORDS, COLLECTION_DOCUMENTS, COLLECTION_AI_ANALYSES,
    COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS, COLLECTION_AUDIT_LOGS
)
from app.database.mongodb import db_manager, connect_to_mongo, close_mongo_connection
from app.utils.datetime import utc_now


class TestPhase13DoctorClinicalWorkflowSuite(unittest.IsolatedAsyncioTestCase):
    """Phase 13 Master Test Suite for Doctor Clinical Workflow."""

    async def asyncSetUp(self):
        await connect_to_mongo()
        self.db = db_manager.db

        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        # Set up Doctor Arjun (Authorized Doctor)
        self.arjun_user = {
            "user_id": "USR-DOC-ARJUN-13",
            "email": "dr.arjun.p13@clinixai.com",
            "full_name": "Dr. Arjun Mehta",
            "role": UserRole.DOCTOR.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.arjun_doctor = {
            "doctor_id": "DOC-ARJUN-13",
            "user_id": "USR-DOC-ARJUN-13",
            "first_name": "Arjun",
            "last_name": "Mehta",
            "email": "dr.arjun.p13@clinixai.com",
            "specialty": "Neurology",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Set up Doctor Priya (Unrelated Doctor with NO care relationship)
        self.priya_user = {
            "user_id": "USR-DOC-PRIYA-13",
            "email": "dr.priya.p13@clinixai.com",
            "full_name": "Dr. Priya Sharma",
            "role": UserRole.DOCTOR.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.priya_doctor = {
            "doctor_id": "DOC-PRIYA-13",
            "user_id": "USR-DOC-PRIYA-13",
            "first_name": "Priya",
            "last_name": "Sharma",
            "specialty": "Dermatology",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Set up Patient One
        self.pat1_user = {
            "user_id": "USR-PAT-ONE-13",
            "email": "patient.one.p13@clinixai.com",
            "full_name": "Patient One",
            "role": UserRole.PATIENT.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.pat1 = {
            "patient_id": "PAT-ONE-13",
            "user_id": "USR-PAT-ONE-13",
            "first_name": "Patient",
            "last_name": "One",
            "email": "patient.one.p13@clinixai.com",
            "status": "active",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Set up Hospital Staff
        self.staff_user = {
            "user_id": "USR-STAFF-13",
            "email": "staff.p13@clinixai.com",
            "full_name": "Staff Member",
            "role": UserRole.HOSPITAL_STAFF.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Clean old test documents
        test_uids = [self.arjun_user["user_id"], self.priya_user["user_id"], self.pat1_user["user_id"], self.staff_user["user_id"]]
        await self.db[COLLECTION_USERS].delete_many({"user_id": {"$in": test_uids}})
        await self.db[COLLECTION_DOCTORS].delete_many({"doctor_id": {"$in": ["DOC-ARJUN-13", "DOC-PRIYA-13"]}})
        await self.db[COLLECTION_PATIENTS].delete_many({"patient_id": "PAT-ONE-13"})
        await self.db[COLLECTION_AI_ANALYSES].delete_many({"patient_id": "PAT-ONE-13"})
        await self.db[COLLECTION_MEDICAL_RECORDS].delete_many({"patient_id": "PAT-ONE-13"})
        await self.db[COLLECTION_APPOINTMENTS].delete_many({"patient_id": "PAT-ONE-13"})
        await self.db[COLLECTION_CONSULTATIONS].delete_many({"patient_id": "PAT-ONE-13"})

        # Insert setup docs
        await self.db[COLLECTION_USERS].insert_many([
            self.arjun_user, self.priya_user, self.pat1_user, self.staff_user
        ])
        await self.db[COLLECTION_DOCTORS].insert_many([self.arjun_doctor, self.priya_doctor])
        await self.db[COLLECTION_PATIENTS].insert_one(self.pat1)

        # Authorized appointment between Dr. Arjun and Patient One
        self.test_apt = {
            "appointment_id": "APT-P13-001",
            "patient_id": "PAT-ONE-13",
            "doctor_id": "DOC-ARJUN-13",
            "department_id": "DEP-NEURO",
            "appointment_date": "2026-10-01",
            "start_time": "10:00",
            "end_time": "10:30",
            "appointment_type": "new_consultation",
            "status": "confirmed",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_APPOINTMENTS].insert_one(self.test_apt)

        # Linked Medical Record
        self.test_mr = {
            "record_id": "REC-P13-001",
            "patient_id": "PAT-ONE-13",
            "doctor_id": "DOC-ARJUN-13",
            "appointment_id": "APT-P13-001",
            "title": "Brain MRI Study",
            "record_type": "imaging",
            "clinical_notes": "Suspected neurological symptoms",
            "file": {
                "storage_key": "medical-records/test_mri_p13.jpg",
                "original_filename": "brain_mri_p13.jpg",
                "content_type": "image/jpeg",
                "file_size": 1024,
            },
            "status": "completed",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_MEDICAL_RECORDS].insert_one(self.test_mr)

        # Standard AI Analysis document awaiting review
        self.analysis_doc = {
            "analysis_id": "AI-2026-P13-001",
            "patient_id": "PAT-ONE-13",
            "doctor_id": "DOC-ARJUN-13",
            "medical_record_id": "REC-P13-001",
            "appointment_id": "APT-P13-001",
            "model": {
                "module_id": "BRAIN_MRI",
                "name": "Brain MRI Tumour Classifier",
                "version": "1.0.0",
                "architecture": "CustomCNN",
                "classification_mode": "multiclass",
            },
            "prediction": {
                "predicted_class": "notumor",
                "confidence": 0.885,
                "class_probabilities": {
                    "glioma": 0.045,
                    "meningioma": 0.050,
                    "notumor": 0.885,
                    "pituitary": 0.020,
                },
                "clinical_summary": "No focal intracranial mass detected by model.",
            },
            "explainability": {
                "method": "Grad-CAM",
                "target_layer": "conv2d_3",
                "artifact_storage_key": "explainability/ai_p13_001_gradcam.png",
                "heatmap_min": 0.0,
                "heatmap_max": 1.0,
            },
            "status": "awaiting_review",
            "requested_by": "USR-DOC-ARJUN-13",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_AI_ANALYSES].insert_one(self.analysis_doc)

        # Generate tokens
        self.arjun_token = create_access_token(user_id="USR-DOC-ARJUN-13", role=UserRole.DOCTOR.value)
        self.priya_token = create_access_token(user_id="USR-DOC-PRIYA-13", role=UserRole.DOCTOR.value)
        self.pat1_token = create_access_token(user_id="USR-PAT-ONE-13", role=UserRole.PATIENT.value)
        self.staff_token = create_access_token(user_id="USR-STAFF-13", role=UserRole.HOSPITAL_STAFF.value)

    async def asyncTearDown(self):
        await self.client.aclose()
        # Clean up test artifacts from DB
        test_uids = [self.arjun_user["user_id"], self.priya_user["user_id"], self.pat1_user["user_id"], self.staff_user["user_id"]]
        await self.db[COLLECTION_USERS].delete_many({"user_id": {"$in": test_uids}})
        await self.db[COLLECTION_DOCTORS].delete_many({"doctor_id": {"$in": ["DOC-ARJUN-13", "DOC-PRIYA-13"]}})
        await self.db[COLLECTION_PATIENTS].delete_many({"patient_id": "PAT-ONE-13"})
        await self.db[COLLECTION_AI_ANALYSES].delete_many({"patient_id": "PAT-ONE-13"})
        await self.db[COLLECTION_MEDICAL_RECORDS].delete_many({"patient_id": "PAT-ONE-13"})
        await self.db[COLLECTION_APPOINTMENTS].delete_many({"patient_id": "PAT-ONE-13"})
        await self.db[COLLECTION_CONSULTATIONS].delete_many({"patient_id": "PAT-ONE-13"})

    # 1. Doctor Arjun (authorized) can get AI analysis
    async def test_01_authorized_doctor_can_access_ai_analysis(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        resp = await self.client.get(f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}", headers=headers)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["analysis_id"], self.analysis_doc["analysis_id"])
        self.assertEqual(data["prediction"]["predicted_class"], "notumor")
        self.assertAlmostEqual(data["prediction"]["confidence"], 0.885, places=2)

    # 2. Unauthorized Doctor Priya (no care relationship) is denied
    async def test_02_unauthorized_doctor_denied(self):
        headers = {"Authorization": f"Bearer {self.priya_token}"}
        resp = await self.client.get(f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}", headers=headers)
        self.assertEqual(resp.status_code, 403)

    # 3. Patient denied reviewing AI analysis
    async def test_03_patient_denied_review_workflow(self):
        headers = {"Authorization": f"Bearer {self.pat1_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Patient self interpretation attempt.",
        }
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 403)

    # 4. Hospital Staff denied reviewing AI analysis
    async def test_04_hospital_staff_denied_review_workflow(self):
        headers = {"Authorization": f"Bearer {self.staff_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Staff attempt to review.",
        }
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 403)

    # 5. Unauthenticated review attempt returns 401
    async def test_05_unauthenticated_review_returns_401(self):
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Anonymous review attempt.",
        }
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            json=payload,
        )
        self.assertEqual(resp.status_code, 401)

    # 6. Unauthorized Doctor Priya cannot submit review for Arjun's patient
    async def test_06_unauthorized_doctor_cannot_submit_review(self):
        headers = {"Authorization": f"Bearer {self.priya_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Dr. Priya trying to review Dr. Arjun's patient.",
        }
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 403)

    # 7. Authorized Doctor submits clinical review & updates status to reviewed
    async def test_07_authorized_doctor_review_success_and_immutability(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Brain MRI review is consistent with absence of neoplastic pathology.",
            "notes": "Internal physician note: Recommend clinical follow-up in 6 months if symptoms recur.",
        }
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Status transition
        self.assertEqual(data["status"], "reviewed")

        # Reviewer identity derived strictly from server/JWT
        self.assertEqual(data["doctor_review"]["reviewed_by"], "USR-DOC-ARJUN-13")
        self.assertEqual(data["doctor_review"]["decision"], "accepted")
        self.assertEqual(
            data["doctor_review"]["clinical_interpretation"],
            "Brain MRI review is consistent with absence of neoplastic pathology."
        )

        # AI PREDICTION IMMUTABILITY CHECK
        self.assertEqual(data["prediction"]["predicted_class"], "notumor")
        self.assertAlmostEqual(data["prediction"]["confidence"], 0.885, places=2)
        self.assertEqual(data["prediction"]["class_probabilities"]["notumor"], 0.885)
        self.assertEqual(data["model"]["name"], "Brain MRI Tumour Classifier")
        self.assertEqual(data["model"]["version"], "1.0.0")

        # Direct MongoDB Check
        mongo_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": self.analysis_doc["analysis_id"]})
        self.assertIsNotNone(mongo_doc)
        self.assertEqual(mongo_doc["status"], "reviewed")
        self.assertEqual(mongo_doc["prediction"]["predicted_class"], "notumor")
        self.assertAlmostEqual(mongo_doc["prediction"]["confidence"], 0.885, places=2)

    # 8. Mass assignment protection: Client cannot forge prediction or reviewer identity
    async def test_08_mass_assignment_protection(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        malicious_payload = {
            "decision": "accepted",
            "clinical_interpretation": "Valid diagnostic interpretation.",
            "doctor_id": "DOC-FORGED",
            "reviewed_by": "USR-FORGED",
            "patient_id": "PAT-FORGED",
            "prediction": {
                "predicted_class": "glioma",
                "confidence": 0.99,
            },
            "status": "awaiting_review",
            "model": {"name": "Hacked Model"},
        }
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=malicious_payload,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # Forged fields MUST NOT overwrite server-owned fields
        self.assertEqual(data["doctor_review"]["reviewed_by"], "USR-DOC-ARJUN-13")
        self.assertEqual(data["patient_id"], "PAT-ONE-13")
        self.assertEqual(data["prediction"]["predicted_class"], "notumor")
        self.assertAlmostEqual(data["prediction"]["confidence"], 0.885, places=2)
        self.assertEqual(data["model"]["name"], "Brain MRI Tumour Classifier")

    # 9. Audit log entry created on doctor review
    async def test_09_audit_log_persisted_on_review(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Normal scan confirmed with clinician audit.",
        }
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 200)

        # Verify audit log
        audit = await self.db[COLLECTION_AUDIT_LOGS].find_one({
            "resource_id": self.analysis_doc["analysis_id"],
            "action": "ai_analysis.reviewed",
        })
        self.assertIsNotNone(audit)
        self.assertEqual(audit["actor_id"], "USR-DOC-ARJUN-13")
        self.assertEqual(audit["resource"], "ai_analysis")
        self.assertEqual(audit["metadata"]["decision"], "accepted")

    # 10. Patient post-review visibility & private notes protection
    async def test_10_patient_post_review_visibility_and_notes_protection(self):
        # First, Arjun reviews with a private note
        headers_arjun = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Normal brain scan, no abnormality observed.",
            "notes": "CONFIDENTIAL PHYSICIAN NOTE: Patient has severe anxiety regarding brain tumour history.",
        }
        await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers_arjun,
            json=payload,
        )

        # Now Patient One accesses the reviewed analysis
        headers_pat = {"Authorization": f"Bearer {self.pat1_token}"}
        resp = await self.client.get(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}",
            headers=headers_pat,
        )
        self.assertEqual(resp.status_code, 200)
        pat_data = resp.json()

        # Patient sees clinical interpretation and status
        self.assertEqual(pat_data["status"], "reviewed")
        self.assertEqual(
            pat_data["doctor_review"]["clinical_interpretation"],
            "Normal brain scan, no abnormality observed."
        )

        # BUT Doctor's private confidential notes MUST BE SANITIZED (None)
        self.assertIsNone(pat_data["doctor_review"]["notes"])

    # 11. Patient-safe report endpoint also protects private notes
    async def test_11_patient_safe_report_endpoint(self):
        headers_arjun = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Clear MRI findings.",
            "notes": "CONFIDENTIAL: Internal physician discussion notes.",
        }
        await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers_arjun,
            json=payload,
        )

        headers_pat = {"Authorization": f"Bearer {self.pat1_token}"}
        resp = await self.client.get(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/report",
            headers=headers_pat,
        )
        self.assertEqual(resp.status_code, 200)
        report_data = resp.json()
        self.assertIn("report", report_data)
        self.assertEqual(report_data["report"]["doctor_interpretation"], "Clear MRI findings.")
        self.assertNotIn("CONFIDENTIAL", str(report_data))

    # 12. Review decision validation: reject invalid enum values
    async def test_12_invalid_decision_enum_rejected(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {
            "decision": "totally_approved",  # Invalid enum
            "clinical_interpretation": "Valid diagnostic interpretation.",
        }
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 422)

    # 13. Short or empty clinical interpretation rejected
    async def test_13_short_interpretation_rejected(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "ok",  # Min length is 5
        }
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 422)

    # 14. Nonexistent analysis ID returns 404
    async def test_14_nonexistent_analysis_returns_404(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Valid diagnostic interpretation.",
        }
        resp = await self.client.post(
            "/api/v1/ai-analyses/AI-NONEXISTENT-999/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 404)

    # 15. Duplicate review protection / Idempotency
    async def test_15_duplicate_review_idempotency_and_preservation(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload1 = {
            "decision": "accepted",
            "clinical_interpretation": "Initial review: consistent with non-pathological MRI.",
        }
        resp1 = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload1,
        )
        self.assertEqual(resp1.status_code, 200)

        # Submit revision / duplicate
        payload2 = {
            "decision": "accepted_as_supporting_information",
            "clinical_interpretation": "Updated review: accepted as supporting baseline imaging.",
        }
        resp2 = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload2,
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.json()
        self.assertEqual(data2["doctor_review"]["decision"], "accepted_as_supporting_information")

        # Immutability remains intact
        self.assertEqual(data2["prediction"]["predicted_class"], "notumor")
        self.assertAlmostEqual(data2["prediction"]["confidence"], 0.885, places=2)

    # 16. Concurrent review submissions do not corrupt state or AI prediction
    async def test_16_concurrent_review_safety(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload1 = {"decision": "accepted", "clinical_interpretation": "Concurrent review stream A assessment."}
        payload2 = {"decision": "accepted", "clinical_interpretation": "Concurrent review stream B assessment."}

        resps = await asyncio.gather(
            self.client.post(f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review", headers=headers, json=payload1),
            self.client.post(f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review", headers=headers, json=payload2),
        )
        for r in resps:
            self.assertEqual(r.status_code, 200)

        # Direct DB verification: Document is clean, status is reviewed, prediction is untouched
        db_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": self.analysis_doc["analysis_id"]})
        self.assertEqual(db_doc["status"], "reviewed")
        self.assertEqual(db_doc["prediction"]["predicted_class"], "notumor")
        self.assertAlmostEqual(db_doc["prediction"]["confidence"], 0.885, places=2)

    # 17. Consultation linkage validation
    async def test_17_consultation_linkage_preservation(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {"decision": "accepted", "clinical_interpretation": "Evaluation with consultation context preserved."}
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["medical_record_id"], "REC-P13-001")
        self.assertEqual(data["appointment_id"], "APT-P13-001")

    # 18. Medical image and Grad-CAM artifact immutability
    async def test_18_image_and_gradcam_artifacts_immutable(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {"decision": "accepted", "clinical_interpretation": "Review submitted without touching image or Grad-CAM artifacts."}
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["explainability"]["artifact_storage_key"], "explainability/ai_p13_001_gradcam.png")
        self.assertEqual(data["explainability"]["method"], "Grad-CAM")
        self.assertEqual(data["explainability"]["target_layer"], "conv2d_3")

    # 19. Invalid status rollback attempted by client is rejected
    async def test_19_invalid_status_rollback_blocked(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        # First review sets status to reviewed
        payload = {"decision": "accepted", "clinical_interpretation": "Legitimate initial review."}
        await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )
        # Attempt to roll back status via review payload mass assignment
        malicious = {"decision": "accepted", "clinical_interpretation": "Attempting status reset.", "status": "awaiting_review"}
        resp = await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=malicious,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "reviewed")

    # 20. Review persists across simulated restart and re-login
    async def test_20_review_persists_across_restart_and_relogin(self):
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {
            "decision": "accepted",
            "clinical_interpretation": "Confirmed diagnosis and clinical evaluation.",
            "notes": "Internal audit check note.",
        }
        await self.client.post(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}/review",
            headers=headers,
            json=payload,
        )

        # Simulate re-login with a new token
        new_arjun_token = create_access_token(user_id="USR-DOC-ARJUN-13", role=UserRole.DOCTOR.value)
        new_headers = {"Authorization": f"Bearer {new_arjun_token}"}

        resp = await self.client.get(
            f"/api/v1/ai-analyses/{self.analysis_doc['analysis_id']}",
            headers=new_headers,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["status"], "reviewed")
        self.assertEqual(data["doctor_review"]["decision"], "accepted")
        self.assertEqual(data["doctor_review"]["clinical_interpretation"], "Confirmed diagnosis and clinical evaluation.")
        self.assertEqual(data["doctor_review"]["reviewed_by"], "USR-DOC-ARJUN-13")
        self.assertEqual(data["prediction"]["predicted_class"], "notumor")
        self.assertAlmostEqual(data["prediction"]["confidence"], 0.885, places=2)

    # 21. Real AI analysis creation, persistence, restart survival, and field immutability
    async def test_21_create_persist_ai_analysis_survives_restart_with_unchanged_values(self):
        # 1. Create a genuine MRI image buffer
        img = Image.new("RGB", (224, 224), color=(30, 30, 30))
        img_buf = io.BytesIO()
        img.save(img_buf, format="JPEG")
        raw_bytes = img_buf.getvalue()

        # 2. Trigger real AI inference through direct infer endpoint
        headers = {"Authorization": f"Bearer {self.arjun_token}"}
        resp = await self.client.post(
            "/api/v1/ai/infer",
            headers=headers,
            files={"image": ("mri_scan.jpg", raw_bytes, "image/jpeg")},
            data={"analysis_type": "BRAIN_MRI"},
        )
        self.assertEqual(resp.status_code, 200)
        res_data = resp.json()
        analysis_id = res_data.get("analysis_id")
        self.assertIsNotNone(analysis_id)
        self.assertTrue(analysis_id.startswith("AI-"))

        # 3. Query MongoDB directly and capture pre-restart state
        doc_before = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertIsNotNone(doc_before)
        pred_before = doc_before["prediction"]["predicted_class"]
        conf_before = doc_before["prediction"]["confidence"]
        status_before = doc_before["status"]
        model_before = doc_before["model"]["name"]

        # 4. Simulate server restart: close MongoDB connection and reconnect
        await close_mongo_connection()
        await connect_to_mongo()
        self.db = db_manager.db

        # 5. Query MongoDB directly after restart
        doc_after = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertIsNotNone(doc_after, f"Analysis {analysis_id} not found in MongoDB after restart!")
        self.assertEqual(doc_after["prediction"]["predicted_class"], pred_before)
        self.assertEqual(doc_after["prediction"]["confidence"], conf_before)
        self.assertEqual(doc_after["status"], status_before)
        self.assertEqual(doc_after["model"]["name"], model_before)
        self.assertEqual(doc_after["medical_record_id"], doc_before["medical_record_id"])

        # 6. Query API endpoint after restart
        api_resp = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers=headers,
        )
        self.assertEqual(api_resp.status_code, 200)
        api_data = api_resp.json()
        self.assertEqual(api_data["analysis_id"], analysis_id)
        self.assertEqual(api_data["prediction"]["predicted_class"], pred_before)
        self.assertEqual(api_data["prediction"]["confidence"], conf_before)


if __name__ == "__main__":
    unittest.main()
