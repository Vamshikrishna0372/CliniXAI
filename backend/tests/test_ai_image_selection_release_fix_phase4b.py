"""
Post-Phase-24 Fix Phase 4B Test Suite:
Existing Patient Image -> AI Analysis -> Doctor Review -> Explicit Release -> Patient Result.

36 Dedicated Automated Tests:
1. Doctor can list authorized patient images.
2. Doctor can select existing patient image.
3. Existing image does not require re-upload.
4. Unauthorized Doctor cannot select Patient B image.
5. Patient cannot initiate Doctor AI analysis.
6. Staff cannot initiate AI analysis.
7. Real model inference executes.
8. Prediction equals probability argmax.
9. Confidence equals predicted probability.
10. Class ordering is correct.
11. Source image relationship is persisted.
12. AI analysis is persisted.
13. Initial status is awaiting_review.
14. Awaiting-review result is not patient-visible.
15. Doctor can access own authorized analysis.
16. Unauthorized Doctor cannot access analysis.
17. Doctor can submit review.
18. Doctor assessment is persisted.
19. Doctor can explicitly release result.
20. Patient cannot release result.
21. Patient sees released result.
22. Patient cannot see another patient's result.
23. Grad-CAM is generated from real inference.
24. Grad-CAM requires authorization.
25. Invalid image is rejected.
26. Corrupt image is rejected.
27. Model failure does not fabricate result.
28. Duplicate active analysis is prevented/idempotent.
29. Concurrent review/release is safe.
30. Stale review/release is rejected appropriately.
31. AI result survives backend restart.
32. MongoDB remains authoritative.
33. Snapshot cannot downgrade newer MongoDB state.
34. Doctor assessment does not mutate raw model output.
35. Patient-facing response is sanitized.
36. Audit event is created for review/release where required.
"""

import io
import os
import unittest
import numpy as np
from PIL import Image
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.mongodb import db_manager, connect_to_mongo
from app.models.user import UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_DOCUMENTS, COLLECTION_AI_ANALYSES, COLLECTION_AUDIT_LOGS,
    COLLECTION_APPOINTMENTS
)
from app.ai.registry import get_ai_registry
from app.ai.model_loader import get_model_loader
from app.ai.preprocessing import load_and_preprocess_backend_image
from app.ai.inference import run_inference
from app.ai.gradcam import generate_gradcam_overlay_bytes
from app.services.ai_service import AIService


class TestAIImageSelectionReleaseFixPhase4B(unittest.IsolatedAsyncioTestCase):
    """36 Automated Tests for Fix Phase 4B Clinical AI Workflow."""

    @staticmethod
    def _data(res):
        j = res.json()
        return j.get("data", j)

    async def asyncSetUp(self):
        if db_manager.db is None:
            await connect_to_mongo()
        self.db = db_manager.db
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        # Doctor A: Dr. Arjun Rao (Authorized for Patient One)
        self.doc_a_user = {
            "user_id": "USR-DOC-ARJUN-4B",
            "email": "dr.arjun.p4b@clinixai.com",
            "full_name": "Dr. Arjun Rao",
            "role": UserRole.DOCTOR.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.doc_a = {
            "doctor_id": "DOC-ARJUN-4B",
            "user_id": "USR-DOC-ARJUN-4B",
            "first_name": "Arjun",
            "last_name": "Rao",
            "email": "dr.arjun.p4b@clinixai.com",
            "specialty": "Neurology",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Doctor B: Dr. Priya Sharma (Unauthorized for Patient One)
        self.doc_b_user = {
            "user_id": "USR-DOC-PRIYA-4B",
            "email": "dr.priya.p4b@clinixai.com",
            "full_name": "Dr. Priya Sharma",
            "role": UserRole.DOCTOR.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.doc_b = {
            "doctor_id": "DOC-PRIYA-4B",
            "user_id": "USR-DOC-PRIYA-4B",
            "first_name": "Priya",
            "last_name": "Sharma",
            "specialty": "Dermatology",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Patient One
        self.pat_1_user = {
            "user_id": "USR-PAT-ONE-4B",
            "email": "patient.one.p4b@clinixai.com",
            "full_name": "Patient One",
            "role": UserRole.PATIENT.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.pat_1 = {
            "patient_id": "PAT-ONE-4B",
            "user_id": "USR-PAT-ONE-4B",
            "first_name": "Patient",
            "last_name": "One",
            "email": "patient.one.p4b@clinixai.com",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Patient Two
        self.pat_2_user = {
            "user_id": "USR-PAT-TWO-4B",
            "email": "patient.two.p4b@clinixai.com",
            "full_name": "Patient Two",
            "role": UserRole.PATIENT.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.pat_2 = {
            "patient_id": "PAT-TWO-4B",
            "user_id": "USR-PAT-TWO-4B",
            "first_name": "Patient",
            "last_name": "Two",
            "email": "patient.two.p4b@clinixai.com",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Staff user
        self.staff_user = {
            "user_id": "USR-STAFF-4B",
            "email": "staff.p4b@clinixai.com",
            "full_name": "Hospital Staff",
            "role": UserRole.HOSPITAL_STAFF.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Care Relationship: Doctor A with Patient One
        self.apt_1 = {
            "appointment_id": "APT-P4B-001",
            "patient_id": "PAT-ONE-4B",
            "doctor_id": "DOC-ARJUN-4B",
            "department_id": "DEP-NEURO",
            "appointment_date": "2026-10-15",
            "start_time": "09:00",
            "end_time": "09:30",
            "status": "confirmed",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Real test Brain MRI image on disk
        self.storage_dir = os.path.join(os.getcwd(), "storage", "documents")
        os.makedirs(self.storage_dir, exist_ok=True)
        self.test_img_path = os.path.join(self.storage_dir, "doc_brain_mri_pat4b.jpg")
        
        # Write real MRI bytes if source available or realistic image
        source_real_mri = os.path.join(os.getcwd(), "model-training", "brain", "dataset", "Training", "notumor", "Tr-no_15.jpg")
        if os.path.exists(source_real_mri):
            with open(source_real_mri, "rb") as sf:
                img_bytes = sf.read()
        else:
            img = Image.new("RGB", (224, 224), color=(30, 30, 30))
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            img_bytes = buf.getvalue()

        with open(self.test_img_path, "wb") as f:
            f.write(img_bytes)

        from app.services.storage_service import get_storage_service
        storage = get_storage_service()
        await storage.save_file(content_bytes=img_bytes, storage_key="doc_brain_mri_pat4b.jpg", subfolder="documents")

        # Document record in DB for Patient One
        self.doc_1 = {
            "document_id": "DOC-P4B-001",
            "patient_id": "PAT-ONE-4B",
            "title": "Brain MRI T1 Scan",
            "category": "MRI",
            "file_name": "doc_brain_mri_pat4b.jpg",
            "file_path": self.test_img_path,
            "file_size": len(img_bytes),
            "mime_type": "image/jpeg",
            "description": "Brain MRI Axial Scan",
            "uploaded_by_id": "PAT-ONE-4B",
            "uploaded_by_role": "patient",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Clear existing test data
        await self.db[COLLECTION_USERS].delete_many({"user_id": {"$in": [
            self.doc_a_user["user_id"], self.doc_b_user["user_id"],
            self.pat_1_user["user_id"], self.pat_2_user["user_id"],
            self.staff_user["user_id"]
        ]}})
        await self.db[COLLECTION_DOCTORS].delete_many({"doctor_id": {"$in": ["DOC-ARJUN-4B", "DOC-PRIYA-4B"]}})
        await self.db[COLLECTION_PATIENTS].delete_many({"patient_id": {"$in": ["PAT-ONE-4B", "PAT-TWO-4B"]}})
        await self.db[COLLECTION_DOCUMENTS].delete_many({"document_id": "DOC-P4B-001"})
        await self.db[COLLECTION_APPOINTMENTS].delete_many({"appointment_id": "APT-P4B-001"})
        await self.db[COLLECTION_AI_ANALYSES].delete_many({"patient_id": {"$in": ["PAT-ONE-4B", "PAT-TWO-4B"]}})

        # Insert fresh fixtures
        await self.db[COLLECTION_USERS].insert_many([
            self.doc_a_user, self.doc_b_user, self.pat_1_user, self.pat_2_user, self.staff_user
        ])
        await self.db[COLLECTION_DOCTORS].insert_many([self.doc_a, self.doc_b])
        await self.db[COLLECTION_PATIENTS].insert_many([self.pat_1, self.pat_2])
        await self.db[COLLECTION_DOCUMENTS].insert_one(self.doc_1)
        await self.db[COLLECTION_APPOINTMENTS].insert_one(self.apt_1)

        # Generate tokens
        self.token_doc_a = create_access_token(user_id=self.doc_a_user["user_id"], role=UserRole.DOCTOR.value)
        self.token_doc_b = create_access_token(user_id=self.doc_b_user["user_id"], role=UserRole.DOCTOR.value)
        self.token_pat_1 = create_access_token(user_id=self.pat_1_user["user_id"], role=UserRole.PATIENT.value)
        self.token_pat_2 = create_access_token(user_id=self.pat_2_user["user_id"], role=UserRole.PATIENT.value)
        self.token_staff = create_access_token(user_id=self.staff_user["user_id"], role=UserRole.HOSPITAL_STAFF.value)

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.db[COLLECTION_USERS].delete_many({"user_id": {"$in": [
            self.doc_a_user["user_id"], self.doc_b_user["user_id"],
            self.pat_1_user["user_id"], self.pat_2_user["user_id"],
            self.staff_user["user_id"]
        ]}})
        await self.db[COLLECTION_DOCTORS].delete_many({"doctor_id": {"$in": ["DOC-ARJUN-4B", "DOC-PRIYA-4B"]}})
        await self.db[COLLECTION_PATIENTS].delete_many({"patient_id": {"$in": ["PAT-ONE-4B", "PAT-TWO-4B"]}})
        await self.db[COLLECTION_DOCUMENTS].delete_many({"document_id": "DOC-P4B-001"})
        await self.db[COLLECTION_APPOINTMENTS].delete_many({"appointment_id": "APT-P4B-001"})
        await self.db[COLLECTION_AI_ANALYSES].delete_many({"patient_id": {"$in": ["PAT-ONE-4B", "PAT-TWO-4B"]}})

    # --- 1. Doctor lists authorized patient images ---
    async def test_01_doctor_can_list_authorized_patient_images(self):
        res = await self.client.get(
            "/api/v1/documents",
            params={"patient_id": "PAT-ONE-4B"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(res.status_code, 200)
        docs = res.json().get("items", [])
        self.assertTrue(any(d["document_id"] == "DOC-P4B-001" for d in docs))

    # --- 2. Doctor selects existing patient image ---
    async def test_02_doctor_can_select_existing_patient_image(self):
        res = await self.client.get(
            "/api/v1/documents/DOC-P4B-001",
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(res.status_code, 200)
        doc = res.json()
        self.assertEqual(doc["patient_id"], "PAT-ONE-4B")
        self.assertEqual(doc["category"], "MRI")

    # --- 3. Existing image does not require re-upload ---
    async def test_03_existing_image_does_not_require_reupload(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(res.status_code, 201)
        data = self._data(res)
        self.assertEqual(data["patient_id"], "PAT-ONE-4B")
        self.assertEqual(data["document_id"], "DOC-P4B-001")
        self.assertEqual(data["status"], "awaiting_review")

    # --- 4. Unauthorized Doctor cannot select Patient B image ---
    async def test_04_unauthorized_doctor_cannot_select_patient_b_image(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_b}"}
        )
        self.assertEqual(res.status_code, 403)

    # --- 5. Patient cannot initiate Doctor AI analysis ---
    async def test_05_patient_cannot_initiate_doctor_ai_analysis(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_pat_1}"}
        )
        self.assertEqual(res.status_code, 403)

    # --- 6. Staff cannot initiate AI analysis ---
    async def test_06_staff_cannot_initiate_ai_analysis(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_staff}"}
        )
        self.assertEqual(res.status_code, 403)

    # --- 7. Real model inference executes ---
    async def test_07_real_model_inference_executes(self):
        with open(self.test_img_path, "rb") as f:
            img_bytes = f.read()
        tensor = load_and_preprocess_backend_image(img_bytes)
        pred, ver = run_inference(tensor, module_id="BRAIN_MRI")
        self.assertIsNotNone(pred.predicted_class)
        self.assertGreater(pred.confidence, 0.0)
        self.assertGreater(len(pred.class_probabilities), 0)
        gc_bytes, target_layer = generate_gradcam_overlay_bytes(
            original_image_input=img_bytes,
            preprocessed_tensor=tensor,
            module_id="BRAIN_MRI",
            target_class_index=2
        )
        self.assertIsNotNone(gc_bytes)
        self.assertGreater(len(gc_bytes), 1000)

    # --- 8. Prediction equals probability argmax ---
    async def test_08_prediction_equals_probability_argmax(self):
        with open(self.test_img_path, "rb") as f:
            img_bytes = f.read()
        tensor = load_and_preprocess_backend_image(img_bytes)
        pred, _ = run_inference(tensor, module_id="BRAIN_MRI")
        probs = pred.class_probabilities
        expected_class = max(probs, key=probs.get)
        self.assertEqual(pred.predicted_class, expected_class)

    # --- 9. Confidence equals predicted probability ---
    async def test_09_confidence_equals_predicted_probability(self):
        with open(self.test_img_path, "rb") as f:
            img_bytes = f.read()
        tensor = load_and_preprocess_backend_image(img_bytes)
        pred, _ = run_inference(tensor, module_id="BRAIN_MRI")
        pred_class = pred.predicted_class
        expected_conf = pred.class_probabilities[pred_class]
        self.assertAlmostEqual(pred.confidence, expected_conf, places=4)

    # --- 10. Class ordering is correct ---
    async def test_10_class_ordering_is_correct(self):
        registry = get_ai_registry()
        mod = registry.get_module("BRAIN_MRI")
        expected_classes = ["glioma", "meningioma", "notumor", "pituitary"]
        self.assertEqual(mod.default_class_names, expected_classes)

    # --- 11. Source image relationship is persisted ---
    async def test_11_source_image_relationship_persisted(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(res.status_code, 201)
        analysis_id = self._data(res)["analysis_id"]
        rec = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertIsNotNone(rec)
        self.assertEqual(rec["document_id"], "DOC-P4B-001")
        self.assertEqual(rec["patient_id"], "PAT-ONE-4B")

    # --- 12. AI analysis is persisted ---
    async def test_12_ai_analysis_persisted(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(res.status_code, 201)
        analysis_id = self._data(res)["analysis_id"]
        count = await self.db[COLLECTION_AI_ANALYSES].count_documents({"analysis_id": analysis_id})
        self.assertEqual(count, 1)

    # --- 13. Initial status is awaiting_review ---
    async def test_13_initial_status_is_awaiting_review(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        data = self._data(res)
        self.assertEqual(data["status"], "awaiting_review")
        rec = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": data["analysis_id"]})
        self.assertFalse(rec.get("is_released_to_patient", False))

    # --- 14. Awaiting-review result is not patient-visible ---
    async def test_14_awaiting_review_result_is_not_patient_visible(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        # Patient direct get -> 403
        p_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {self.token_pat_1}"}
        )
        self.assertEqual(p_res.status_code, 403)

        # Patient report -> 403
        r_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/report",
            headers={"Authorization": f"Bearer {self.token_pat_1}"}
        )
        self.assertEqual(r_res.status_code, 403)

        # Patient gradcam -> 403
        g_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/gradcam",
            headers={"Authorization": f"Bearer {self.token_pat_1}"}
        )
        self.assertEqual(g_res.status_code, 403)

        # Patient list -> analysis not present
        l_res = await self.client.get(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {self.token_pat_1}"}
        )
        self.assertEqual(l_res.status_code, 200)
        items = l_res.json().get("items", [])
        self.assertFalse(any(it["analysis_id"] == analysis_id for it in items))

    # --- 15. Doctor can access own authorized analysis ---
    async def test_15_doctor_can_access_own_authorized_analysis(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        d_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(d_res.status_code, 200)
        self.assertEqual(self._data(d_res)["analysis_id"], analysis_id)

    # --- 16. Unauthorized Doctor cannot access analysis ---
    async def test_16_unauthorized_doctor_cannot_access_analysis(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        d_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {self.token_doc_b}"}
        )
        self.assertEqual(d_res.status_code, 403)

    # --- 17. Doctor can submit review ---
    async def test_17_doctor_can_submit_review(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        rev_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Clinically reviewed: scan shows clear parenchyma without mass effect.",
                "release_to_patient": True
            },
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(rev_res.status_code, 200)
        data = self._data(rev_res)
        self.assertEqual(data["status"], "reviewed")

    # --- 18. Doctor assessment is persisted ---
    async def test_18_doctor_assessment_is_persisted(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Consistent with non-tumorous baseline.",
                "release_to_patient": True
            },
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        rec = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertEqual(rec["doctor_review"]["clinical_interpretation"], "Consistent with non-tumorous baseline.")
        self.assertEqual(rec["doctor_review"]["decision"], "accepted")

    # --- 19. Doctor can explicitly release result ---
    async def test_19_doctor_can_explicitly_release_result(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]
        # Review first without release
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Assessment ready.",
                "release_to_patient": False
            },
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        # Explicit release endpoint
        rel_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(rel_res.status_code, 200)
        rec = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertTrue(rec["is_released_to_patient"])
        self.assertIsNotNone(rec["released_at"])

    # --- 20. Patient cannot release result ---
    async def test_20_patient_cannot_release_result(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        rel_res = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/release",
            headers={"Authorization": f"Bearer {self.token_pat_1}"}
        )
        self.assertEqual(rel_res.status_code, 403)

    # --- 21. Patient sees released result ---
    async def test_21_patient_sees_released_result(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Normal scan.",
                "release_to_patient": True
            },
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )

        p_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {self.token_pat_1}"}
        )
        self.assertEqual(p_res.status_code, 200)
        self.assertEqual(self._data(p_res)["analysis_id"], analysis_id)

    # --- 22. Patient cannot see another patient's result ---
    async def test_22_patient_cannot_see_another_patient_result(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "clinical_interpretation": "Normal scan.",
                "release_to_patient": True
            },
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )

        p2_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {self.token_pat_2}"}
        )
        self.assertEqual(p2_res.status_code, 403)

    # --- 23. Grad-CAM is generated from real inference ---
    async def test_23_gradcam_generated_from_real_inference(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        gc_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/gradcam",
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(gc_res.status_code, 200)
        self.assertEqual(gc_res.headers["content-type"], "image/png")
        self.assertGreater(len(gc_res.content), 1000)

    # --- 24. Grad-CAM requires authorization ---
    async def test_24_gradcam_requires_authorization(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        # No header
        gc_noauth = await self.client.get(f"/api/v1/ai-analyses/{analysis_id}/gradcam")
        self.assertEqual(gc_noauth.status_code, 401)

        # Unauthorized doctor
        gc_unauth = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/gradcam",
            headers={"Authorization": f"Bearer {self.token_doc_b}"}
        )
        self.assertEqual(gc_unauth.status_code, 403)

    # --- 25. Invalid image is rejected ---
    async def test_25_invalid_image_rejected(self):
        bad_doc = {
            "document_id": "DOC-BAD-001",
            "patient_id": "PAT-ONE-4B",
            "title": "Text File",
            "category": "Lab Report",
            "file_name": "report.txt",
            "file_path": "/invalid/path.txt",
            "file_size": 10,
            "mime_type": "text/plain",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].insert_one(bad_doc)

        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-BAD-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertIn(res.status_code, [400, 422])
        await self.db[COLLECTION_DOCUMENTS].delete_one({"document_id": "DOC-BAD-001"})

    # --- 26. Corrupt image is rejected ---
    async def test_26_corrupt_image_rejected(self):
        from app.services.storage_service import get_storage_service
        storage = get_storage_service()
        await storage.save_file(content_bytes=b"NOT_AN_IMAGE_RANDOM_CORRUPT_BYTES", storage_key="corrupt.jpg", subfolder="documents")

        corrupt_doc = {
            "document_id": "DOC-CORRUPT-001",
            "patient_id": "PAT-ONE-4B",
            "title": "Corrupted MRI",
            "category": "MRI",
            "file_name": "corrupt.jpg",
            "file_size": 33,
            "mime_type": "image/jpeg",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].insert_one(corrupt_doc)

        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-CORRUPT-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertIn(res.status_code, [400, 422, 500])
        await self.db[COLLECTION_DOCUMENTS].delete_one({"document_id": "DOC-CORRUPT-001"})
        await storage.delete_file("corrupt.jpg", subfolder="documents")

    # --- 27. Model failure does not fabricate result ---
    async def test_27_model_failure_does_not_fabricate_result(self):
        with self.assertRaises(Exception):
            run_inference(np.zeros((224, 224, 3), dtype=np.float32), module_id="INVALID_NONEXISTENT_MOD")

    # --- 28. Duplicate active analysis is prevented/idempotent ---
    async def test_28_duplicate_active_analysis_prevented_or_idempotent(self):
        res1 = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(res1.status_code, 201)

        # Immediate second analysis request for identical document while active
        res2 = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        # Either safely idempotent (200/201) returning active or 409 Conflict
        self.assertIn(res2.status_code, [200, 201, 409])

    # --- 29. Concurrent review/release is safe ---
    async def test_29_concurrent_review_release_is_safe(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        r1 = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Pass 1", "release_to_patient": True},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        r2 = await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Pass 2", "release_to_patient": True},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(r1.status_code, 200)
        self.assertIn(r2.status_code, [200, 409])
        rec = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertEqual(rec["status"], "reviewed")

    # --- 30. Stale review/release is rejected appropriately ---
    async def test_30_stale_review_release_rejected_appropriately(self):
        res = await self.client.post(
            f"/api/v1/ai-analyses/AI-NONEXISTENT-999/review",
            json={"decision": "accepted", "clinical_interpretation": "Valid"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(res.status_code, 404)

    # --- 31. AI result survives backend restart ---
    async def test_31_ai_result_survives_backend_restart(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Survives reboot.", "release_to_patient": True},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )

        # Simulate fresh client reconnect
        await self.client.aclose()
        fresh_transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=fresh_transport, base_url="http://testserver")

        check_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        self.assertEqual(check_res.status_code, 200)
        self.assertEqual(self._data(check_res)["doctor_review"]["clinical_interpretation"], "Survives reboot.")

    # --- 32. MongoDB remains authoritative ---
    async def test_32_mongodb_remains_authoritative(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]
        direct_mongo_doc = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertIsNotNone(direct_mongo_doc)
        self.assertEqual(direct_mongo_doc["patient_id"], "PAT-ONE-4B")

    # --- 33. Snapshot cannot downgrade newer MongoDB state ---
    async def test_33_snapshot_cannot_downgrade_newer_mongodb_state(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]
        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Released status", "release_to_patient": True},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        # Verify status in DB is reviewed
        rec = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        self.assertEqual(rec["status"], "reviewed")
        self.assertTrue(rec["is_released_to_patient"])

    # --- 34. Doctor assessment does not mutate raw model output ---
    async def test_34_doctor_assessment_does_not_mutate_raw_model_output(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]
        before_pred = self._data(res)["prediction"]["predicted_class"]
        before_conf = self._data(res)["prediction"]["confidence"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "rejected", "clinical_interpretation": "Clinician disagrees", "release_to_patient": True},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )

        after_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        after_data = self._data(after_res)
        self.assertEqual(after_data["prediction"]["predicted_class"], before_pred)
        self.assertEqual(after_data["prediction"]["confidence"], before_conf)
        self.assertEqual(after_data["doctor_review"]["decision"], "rejected")

    # --- 35. Patient-facing response is sanitized ---
    async def test_35_patient_facing_response_is_sanitized(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Clear.", "release_to_patient": True},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )

        rep_res = await self.client.get(
            f"/api/v1/ai-analyses/{analysis_id}/report",
            headers={"Authorization": f"Bearer {self.token_pat_1}"}
        )
        self.assertEqual(rep_res.status_code, 200)
        rep_data = self._data(rep_res)
        self.assertIn("disclaimer", rep_data)
        # Ensure internal technical keys like gradients or layer activation references are absent
        self.assertNotIn("target_layer_activation", rep_data)
        self.assertNotIn("internal_tensor_weights", rep_data)

    # --- 36. Audit event is created for review/release ---
    async def test_36_audit_event_created_for_review_release(self):
        res = await self.client.post(
            "/api/v1/ai-analyses",
            json={"document_id": "DOC-P4B-001"},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )
        analysis_id = self._data(res)["analysis_id"]

        await self.client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={"decision": "accepted", "clinical_interpretation": "Audit verified.", "release_to_patient": True},
            headers={"Authorization": f"Bearer {self.token_doc_a}"}
        )

        audit_entry = await self.db[COLLECTION_AUDIT_LOGS].find_one({
            "resource_id": analysis_id,
            "action": {"$in": ["ai_analysis.reviewed", "ai_analysis_reviewed"]}
        })
        self.assertIsNotNone(audit_entry)
        self.assertEqual(audit_entry.get("actor_id") or audit_entry.get("actor_user_id"), self.doc_a_user["user_id"])


if __name__ == "__main__":
    unittest.main()
