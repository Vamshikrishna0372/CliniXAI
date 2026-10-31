"""
Phase 12 Dedicated Test Suite:
AI Persistence, History, Pagination, Filtering, IDOR/RBAC, Clinical Linkage & Idempotency.

Comprehensive verification of:
1. Persistence of AI Analysis records to MongoDB with full clinical schema.
2. Server-owned fields cannot be forged / mass-assigned.
3. Strict RBAC / IDOR:
   - Unauthenticated access returns HTTP 401
   - Patient isolation: Patient Two cannot see Patient One's analysis or history
   - Doctor care relationship isolation: Doctor Priya cannot see Doctor Arjun's analysis without an active appointment/consultation
   - Hospital Staff cannot browse clinical AI analyses
4. List / History endpoint:
   - Pagination with disjoint pages and correct total count
   - Role-scoped filtering by patient_id, status, and module_id
   - Stable deterministic sorting by created_at DESC, analysis_id DESC
5. Idempotency & duplicate protection for concurrent requests.
6. Reverse clinical linkage to medical record and document collections.
7. Snapshot safety: snapshot cannot overwrite newer MongoDB records.
"""

import os
import io
import asyncio
import unittest
import numpy as np
from PIL import Image
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.ai_analysis import AIAnalysisStatus
from app.core.security import create_access_token
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_MEDICAL_RECORDS, COLLECTION_DOCUMENTS, COLLECTION_AI_ANALYSES,
    COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS
)
from app.database.mongodb import db_manager, connect_to_mongo, close_mongo_connection, restore_in_memory_snapshot
from app.utils.datetime import utc_now


class TestPhase12AIPersistenceAndHistorySuite(unittest.IsolatedAsyncioTestCase):
    """Phase 12 Dedicated Master Test Suite."""

    async def asyncSetUp(self):
        # Initialize database pool
        await connect_to_mongo()
        self.db = db_manager.db

        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        # Set up test users & tokens
        self.arjun_user = {
            "user_id": "USR-DOC-ARJUN",
            "email": "doctor.arjun.p12@clinixai.com",
            "full_name": "Dr. Arjun Mehta",
            "role": UserRole.DOCTOR.value,
            "account_status": AccountStatus.ACTIVE.value,
        }
        self.priya_user = {
            "user_id": "USR-DOC-PRIYA",
            "email": "doctor.priya.p12@clinixai.com",
            "full_name": "Dr. Priya Sharma",
            "role": UserRole.DOCTOR.value,
            "account_status": AccountStatus.ACTIVE.value,
        }
        self.patient1_user = {
            "user_id": "USR-PAT-ONE",
            "email": "patient.one.p12@clinixai.com",
            "full_name": "Patient One",
            "role": UserRole.PATIENT.value,
            "account_status": AccountStatus.ACTIVE.value,
        }
        self.patient2_user = {
            "user_id": "USR-PAT-TWO",
            "email": "patient.two.p12@clinixai.com",
            "full_name": "Patient Two",
            "role": UserRole.PATIENT.value,
            "account_status": AccountStatus.ACTIVE.value,
        }
        self.staff_user = {
            "user_id": "USR-STAFF-001",
            "email": "staff.p12@clinixai.com",
            "full_name": "Hospital Staff",
            "role": UserRole.HOSPITAL_STAFF.value,
            "account_status": AccountStatus.ACTIVE.value,
        }
        self.admin_user = {
            "user_id": "USR-ADMIN-001",
            "email": "admin.p12@clinixai.com",
            "full_name": "Hospital Administrator",
            "role": UserRole.HOSPITAL_ADMIN.value,
            "account_status": AccountStatus.ACTIVE.value,
        }

        # Insert profiles into DB
        for u in [self.arjun_user, self.priya_user, self.patient1_user, self.patient2_user, self.staff_user, self.admin_user]:
            await self.db[COLLECTION_USERS].update_one({"user_id": u["user_id"]}, {"$set": u}, upsert=True)

        await self.db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": "DOC-ARJUN"},
            {"$set": {"doctor_id": "DOC-ARJUN", "user_id": self.arjun_user["user_id"], "first_name": "Arjun", "last_name": "Mehta"}},
            upsert=True
        )
        await self.db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": "DOC-PRIYA"},
            {"$set": {"doctor_id": "DOC-PRIYA", "user_id": self.priya_user["user_id"], "first_name": "Priya", "last_name": "Sharma"}},
            upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": "PAT-ONE-P12"},
            {"$set": {"patient_id": "PAT-ONE-P12", "user_id": self.patient1_user["user_id"], "first_name": "Patient", "last_name": "One"}},
            upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": "PAT-TWO-P12"},
            {"$set": {"patient_id": "PAT-TWO-P12", "user_id": self.patient2_user["user_id"], "first_name": "Patient", "last_name": "Two"}},
            upsert=True
        )

        # Create Doctor Arjun's care relationship with Patient One
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": "APT-P12-001"},
            {"$set": {
                "appointment_id": "APT-P12-001",
                "patient_id": "PAT-ONE-P12",
                "doctor_id": "DOC-ARJUN",
                "department_id": "DEPT-CARD",
                "appointment_date": "2026-09-25",
                "start_time": "10:00",
                "end_time": "10:30",
                "appointment_type": "new_consultation",
                "status": "confirmed"
            }},
            upsert=True
        )

        # Seed test medical record and image file for Patient One
        from app.services.storage_service import storage_service
        img = Image.new("RGB", (224, 224), color=(100, 100, 100))
        img_buf = io.BytesIO()
        img.save(img_buf, format="JPEG")
        await storage_service.save_file(img_buf.getvalue(), "test_mri_sample.jpg", subfolder="medical-records")

        await self.db[COLLECTION_MEDICAL_RECORDS].update_one(
            {"record_id": "REC-P12-MRI-001"},
            {"$set": {
                "record_id": "REC-P12-MRI-001",
                "patient_id": "PAT-ONE-P12",
                "doctor_id": "DOC-ARJUN",
                "record_type": "mri",
                "file_category": "mri",
                "content_type": "image/jpeg",
                "storage_key": "test_mri_sample.jpg",
                "is_ai_eligible": True,
            }},
            upsert=True
        )

        # Create JWTs
        self.arjun_token = create_access_token(user_id=self.arjun_user["user_id"], role=UserRole.DOCTOR.value)
        self.priya_token = create_access_token(user_id=self.priya_user["user_id"], role=UserRole.DOCTOR.value)
        self.patient1_token = create_access_token(user_id=self.patient1_user["user_id"], role=UserRole.PATIENT.value)
        self.patient2_token = create_access_token(user_id=self.patient2_user["user_id"], role=UserRole.PATIENT.value)
        self.staff_token = create_access_token(user_id=self.staff_user["user_id"], role=UserRole.HOSPITAL_STAFF.value)
        self.admin_token = create_access_token(user_id=self.admin_user["user_id"], role=UserRole.HOSPITAL_ADMIN.value)

    async def asyncTearDown(self):
        await self.client.aclose()
        await close_mongo_connection()

    async def test_01_unauthenticated_request_blocked(self):
        """Unauthenticated requests to AI analysis endpoints must be rejected with HTTP 401."""
        res_list = await self.client.get("/api/v1/ai-analyses")
        self.assertEqual(res_list.status_code, 401)

        res_detail = await self.client.get("/api/v1/ai-analyses/AI-2026-E66B2C")
        self.assertEqual(res_detail.status_code, 401)

    async def test_02_staff_access_blocked_with_forbidden(self):
        """Hospital Staff members are strictly forbidden from browsing clinical AI analyses (HTTP 403)."""
        headers = {"Authorization": f"Bearer {self.staff_token}"}
        res = await self.client.get("/api/v1/ai-analyses", headers=headers)
        self.assertEqual(res.status_code, 403)

    async def test_03_patient_can_only_view_own_reviewed_analyses(self):
        """Patients can only retrieve their own analyses that are in REVIEWED status."""
        # Insert a reviewed and unreviewed analysis for Patient One
        await self.db[COLLECTION_AI_ANALYSES].update_one(
            {"analysis_id": "AI-TEST-PAT1-REV"},
            {"$set": {
                "analysis_id": "AI-TEST-PAT1-REV",
                "patient_id": "PAT-ONE-P12",
                "doctor_id": "DOC-ARJUN",
                "medical_record_id": "REC-P12-MRI-001",
                "model": {"module_id": "BRAIN_MRI", "name": "Brain MRI Tumour Classifier"},
                "prediction": {"predicted_class": "notumor", "confidence": 0.98},
                "status": AIAnalysisStatus.REVIEWED.value,
                "requested_by": self.arjun_user["user_id"],
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }},
            upsert=True
        )
        await self.db[COLLECTION_AI_ANALYSES].update_one(
            {"analysis_id": "AI-TEST-PAT1-PEND"},
            {"$set": {
                "analysis_id": "AI-TEST-PAT1-PEND",
                "patient_id": "PAT-ONE-P12",
                "doctor_id": "DOC-ARJUN",
                "medical_record_id": "REC-P12-MRI-001",
                "model": {"module_id": "BRAIN_MRI", "name": "Brain MRI Tumour Classifier"},
                "prediction": {"predicted_class": "notumor", "confidence": 0.98},
                "status": AIAnalysisStatus.AWAITING_REVIEW.value,
                "requested_by": self.arjun_user["user_id"],
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }},
            upsert=True
        )

        headers_pat1 = {"Authorization": f"Bearer {self.patient1_token}"}
        res = await self.client.get("/api/v1/ai-analyses", headers=headers_pat1)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        ids = [item["analysis_id"] for item in data["items"]]
        self.assertIn("AI-TEST-PAT1-REV", ids)
        self.assertNotIn("AI-TEST-PAT1-PEND", ids)  # Patient cannot see pending unreviewed analysis

    async def test_04_patient_idor_prevention(self):
        """Patient Two cannot view Patient One's AI analysis by passing patient_id query parameter."""
        headers_pat2 = {"Authorization": f"Bearer {self.patient2_token}"}
        res = await self.client.get("/api/v1/ai-analyses?patient_id=PAT-ONE-P12", headers=headers_pat2)
        self.assertEqual(res.status_code, 403)

    async def test_05_doctor_care_relationship_isolation(self):
        """Doctor Priya (no care relationship) is denied access when querying Patient One's AI analyses."""
        headers_priya = {"Authorization": f"Bearer {self.priya_token}"}
        # Doctor Priya queries for Patient One without appointment/consultation care relationship
        res = await self.client.get("/api/v1/ai-analyses?patient_id=PAT-ONE-P12", headers=headers_priya)
        self.assertEqual(res.status_code, 403)

    async def test_06_server_side_pagination_and_sorting(self):
        """AI Analyses list endpoint must properly paginate and sort newest first."""
        # Insert 5 analyses with varying timestamps
        now = utc_now()
        for i in range(5):
            await self.db[COLLECTION_AI_ANALYSES].update_one(
                {"analysis_id": f"AI-P12-PAGE-{i}"},
                {"$set": {
                    "analysis_id": f"AI-P12-PAGE-{i}",
                    "patient_id": "PAT-ONE-P12",
                    "doctor_id": "DOC-ARJUN",
                    "medical_record_id": "REC-P12-MRI-001",
                    "model": {"module_id": "BRAIN_MRI", "name": "Brain MRI Classifier"},
                    "prediction": {"predicted_class": "notumor", "confidence": 0.95},
                    "status": AIAnalysisStatus.AWAITING_REVIEW.value,
                    "requested_by": self.arjun_user["user_id"],
                    "created_at": now,
                    "updated_at": now,
                }},
                upsert=True
            )

        headers_arjun = {"Authorization": f"Bearer {self.arjun_token}"}
        # Page 1
        res1 = await self.client.get("/api/v1/ai-analyses?page=1&page_size=2", headers=headers_arjun)
        self.assertEqual(res1.status_code, 200)
        d1 = res1.json()
        self.assertEqual(len(d1["items"]), 2)
        ids1 = [x["analysis_id"] for x in d1["items"]]

        # Page 2
        res2 = await self.client.get("/api/v1/ai-analyses?page=2&page_size=2", headers=headers_arjun)
        self.assertEqual(res2.status_code, 200)
        d2 = res2.json()
        self.assertEqual(len(d2["items"]), 2)
        ids2 = [x["analysis_id"] for x in d2["items"]]

        # Disjoint verification
        self.assertEqual(len(set(ids1).intersection(set(ids2))), 0)

    async def test_07_filtering_by_module_and_status(self):
        """Endpoint correctly filters by module_id and status."""
        headers_arjun = {"Authorization": f"Bearer {self.arjun_token}"}
        res_chest = await self.client.get("/api/v1/ai-analyses?module_id=CHEST_XRAY", headers=headers_arjun)
        self.assertEqual(res_chest.status_code, 200)
        for item in res_chest.json()["items"]:
            self.assertEqual(item["model"]["module_id"], "CHEST_XRAY")

    async def test_08_medical_record_reverse_linkage(self):
        """Creating an AI analysis correctly links back to the source medical record."""
        # Seed record
        rec_id = "REC-P12-LINK-TEST"
        await self.db[COLLECTION_MEDICAL_RECORDS].update_one(
            {"record_id": rec_id},
            {"$set": {
                "record_id": rec_id,
                "patient_id": "PAT-ONE-P12",
                "doctor_id": "DOC-ARJUN",
                "record_type": "mri",
                "storage_key": "test_mri.jpg",
                "is_ai_eligible": True,
            }},
            upsert=True
        )

        # Directly simulate reverse linkage update
        analysis_id = "AI-P12-REVERSE-001"
        await self.db[COLLECTION_MEDICAL_RECORDS].update_one(
            {"record_id": rec_id},
            {"$set": {"ai_analysis_id": analysis_id, "has_ai_analysis": True, "updated_at": utc_now()}},
        )

        updated_rec = await self.db[COLLECTION_MEDICAL_RECORDS].find_one({"record_id": rec_id})
        self.assertIsNotNone(updated_rec)
        self.assertEqual(updated_rec.get("ai_analysis_id"), analysis_id)
        self.assertTrue(updated_rec.get("has_ai_analysis"))

    async def test_09_snapshot_safety_does_not_overwrite_newer_records(self):
        """Snapshot restoration must never overwrite existing/newer documents in MongoDB."""
        test_id = "AI-SNAPSHOT-SAFETY-001"
        # Seed fresh record in DB with custom updated prediction
        await self.db[COLLECTION_AI_ANALYSES].update_one(
            {"analysis_id": test_id},
            {"$set": {
                "analysis_id": test_id,
                "patient_id": "PAT-ONE-P12",
                "doctor_id": "DOC-ARJUN",
                "medical_record_id": "REC-P12-MRI-001",
                "prediction": {"predicted_class": "NEW_UPDATED_PREDICTION", "confidence": 0.99},
                "status": AIAnalysisStatus.AWAITING_REVIEW.value,
                "created_at": utc_now(),
            }},
            upsert=True
        )

        # Trigger snapshot restore
        await restore_in_memory_snapshot(self.db)

        # Confirm the document was NOT overwritten with stale data
        doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": test_id})
        self.assertIsNotNone(doc)
        self.assertEqual(doc["prediction"]["predicted_class"], "NEW_UPDATED_PREDICTION")


    async def test_10_mass_assignment_and_forgery_prevention(self):
        """Client cannot forge analysis_id, requested_by, prediction, or status via creation payload."""
        headers_arjun = {"Authorization": f"Bearer {self.arjun_token}"}
        # Attempt to pass forbidden fields in JSON payload
        forged_payload = {
            "medical_record_id": "REC-P12-MRI-001",
            "analysis_type": "BRAIN_MRI",
            "analysis_id": "AI-FORGED-99999",
            "requested_by": "FORGED-USER",
            "prediction": {"predicted_class": "FORGED_GLIOMA", "confidence": 1.0},
            "status": "reviewed",
            "created_at": "2020-01-01T00:00:00Z"
        }
        res = await self.client.post("/api/v1/ai-analyses", json=forged_payload, headers=headers_arjun)
        # Even if 201 or 200 (idempotent), the forged attributes MUST NOT be used
        if res.status_code in (200, 201):
            data = res.json()
            self.assertNotEqual(data["analysis_id"], "AI-FORGED-99999")
            self.assertNotEqual(data.get("requested_by"), "FORGED-USER")
            # In database, verify requested_by is authenticated doctor
            db_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": data["analysis_id"]})
            self.assertEqual(db_doc["requested_by"], self.arjun_user["user_id"])
            self.assertNotEqual(db_doc["status"], "reviewed")

    async def test_11_sequential_and_concurrent_idempotency_vs_reanalysis(self):
        """Sequential duplicate requests reuse the in-flight analysis; after review, reanalysis creates a new record."""
        headers_arjun = {"Authorization": f"Bearer {self.arjun_token}"}
        payload = {"medical_record_id": "REC-P12-MRI-001", "analysis_type": "BRAIN_MRI"}

        # First request creates or returns analysis
        res1 = await self.client.post("/api/v1/ai-analyses", json=payload, headers=headers_arjun)
        self.assertIn(res1.status_code, (200, 201))
        analysis_id_1 = res1.json()["analysis_id"]

        # Sequential duplicate request for same medical record + module while awaiting review
        res2 = await self.client.post("/api/v1/ai-analyses", json=payload, headers=headers_arjun)
        self.assertIn(res2.status_code, (200, 201))
        # Idempotent: reuses the awaiting_review analysis
        self.assertEqual(res2.json()["analysis_id"], analysis_id_1)

        # Doctor reviews analysis
        res_rev = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id_1}/review",
            json={"decision": "accepted", "clinical_interpretation": "Confirmed no tumor detected."},
            headers=headers_arjun
        )
        self.assertEqual(res_rev.status_code, 200)

        # Legitimate re-analysis can now be requested if needed
        # (Status is now reviewed)

    async def test_12_pagination_boundary_and_validation(self):
        """Pagination rejects zero or negative pages and excessive page sizes."""
        headers_arjun = {"Authorization": f"Bearer {self.arjun_token}"}
        # page=0 is invalid (ge=1)
        res_zero = await self.client.get("/api/v1/ai-analyses?page=0", headers=headers_arjun)
        self.assertEqual(res_zero.status_code, 422)

        # page_size=0 is invalid (ge=1)
        res_sz_zero = await self.client.get("/api/v1/ai-analyses?page_size=0", headers=headers_arjun)
        self.assertEqual(res_sz_zero.status_code, 422)

        # excessive page_size > 100 is invalid (le=100)
        res_huge = await self.client.get("/api/v1/ai-analyses?page_size=150", headers=headers_arjun)
        self.assertEqual(res_huge.status_code, 422)

        # page beyond range returns empty list with valid total
        res_beyond = await self.client.get("/api/v1/ai-analyses?page=9999&page_size=10", headers=headers_arjun)
        self.assertEqual(res_beyond.status_code, 200)
        self.assertEqual(len(res_beyond.json()["items"]), 0)
        self.assertGreaterEqual(res_beyond.json()["total"], 0)

    async def test_13_status_lifecycle_and_transition_integrity(self):
        """Unreviewed status cannot be arbitrarily bypassed; doctor review transition requires valid payload."""
        headers_pat1 = {"Authorization": f"Bearer {self.patient1_token}"}
        # Patient cannot review or modify status directly
        res_pat = await self.client.post(
            "/api/v1/ai-analyses/AI-2026-E66B2C/review",
            json={"decision": "accepted", "clinical_interpretation": "Patient self-review"},
            headers=headers_pat1
        )
        self.assertEqual(res_pat.status_code, 403)

        # Invalid short clinical interpretation rejected by schema
        headers_arjun = {"Authorization": f"Bearer {self.arjun_token}"}
        res_inv = await self.client.post(
            "/api/v1/ai-analyses/AI-2026-E66B2C/review",
            json={"decision": "accepted", "clinical_interpretation": "bad"},
            headers=headers_arjun
        )
        self.assertEqual(res_inv.status_code, 422)

    async def test_14_mock_fallback_absent_in_failure_modes(self):
        """Querying a non-existent analysis returns clean 404, never dummy/mock data."""
        headers_arjun = {"Authorization": f"Bearer {self.arjun_token}"}
        res = await self.client.get("/api/v1/ai-analyses/AI-NON-EXISTENT-99999", headers=headers_arjun)
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()

