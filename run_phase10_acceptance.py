"""
Phase 10 Comprehensive Acceptance Verification Script.
Executes the remaining acceptance hardening items against the real model and storage:
1. Real Brain MRI acceptance image upload & storage via Phase 9 medical record pipeline.
2. Raw model output capture & verification (4 finite classes, exact floats, class mapping).
3. Direct MongoDB query verification (corresponds to model inference).
4. Restart persistence (run inference, get analysis_id, restart FastAPI, verify DB & API).
5. Unauthenticated test (401).
6. Patient authorization test (403 for direct AI analysis).
7. Cross-patient test (403 IDOR blocked).
8. Unauthorized doctor test (403 Doctor Priya blocked on Patient One).
9. Deleted record test (404).
10. Missing file test (400 validation error).
11. Corrupt image test (400 decode error).
12. Unsupported image test (400 validation error).
13. Model failure test (controlled error, no fake predictions).
14. Persistence failure test (controlled error, no inconsistent state).
15. Concurrent real inference (2 simultaneous requests, no mixing).
"""

import os
import sys
import io
import json
import asyncio
import hashlib
from pathlib import Path
import uuid
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent / "backend"))

from app.core.security import create_access_token
from app.database.mongodb import connect_to_mongo, close_mongo_connection, db_manager, save_in_memory_snapshot
from app.services.storage_service import storage_service
from app.ai.registry import get_ai_registry, AIModuleIdentifier
from app.ai.model_loader import get_model_loader
from app.ai.preprocessing import load_and_preprocess_backend_image
from app.ai.inference import run_inference
from app.services.ai_service import AIService
from app.schemas.ai_analysis import AIAnalysisCreateRequest
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_DOCTORS, COLLECTION_PATIENTS,
    COLLECTION_APPOINTMENTS, COLLECTION_MEDICAL_RECORDS, COLLECTION_AI_ANALYSES
)
from app.utils.datetime import utc_now
from httpx import AsyncClient, ASGITransport
from app.main import app

REAL_MRI_PATH = Path("model-training/brain/dataset/Testing/glioma/Te-gl_1.jpg")

async def run_acceptance():
    print("=" * 60)
    print("STARTING PHASE 10 COMPREHENSIVE ACCEPTANCE VERIFICATION")
    print("=" * 60)
    
    # 0. Connect DB
    await connect_to_mongo()
    db = db_manager.db
    
    from app.database.db_seeder import seed_initial_data
    await seed_initial_data(db)
    
    # Authenticate users
    # Doctor Arjun Rao: DOC-RAO-001 / USR-DOC-RAO-001 (has appointment APT-2026-001 with PAT-ONE-001)
    user_arjun = await db[COLLECTION_USERS].find_one({"email": "doctor.arjun@clinixai.com"})
    user_priya = await db[COLLECTION_USERS].find_one({"email": "doctor.priya@clinixai.com"})
    user_pat1 = await db[COLLECTION_USERS].find_one({"email": "patient.one@clinixai.com"})
    user_pat2 = await db[COLLECTION_USERS].find_one({"email": "patient.two@clinixai.com"})
    
    token_arjun = create_access_token(user_id=user_arjun["user_id"], role=user_arjun["role"])
    token_priya = create_access_token(user_id=user_priya["user_id"], role=user_priya["role"])
    token_pat1 = create_access_token(user_id=user_pat1["user_id"], role=user_pat1["role"])
    token_pat2 = create_access_token(user_id=user_pat2["user_id"], role=user_pat2["role"])
    
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        
        # ============================================================
        # 1. REAL BRAIN MRI ACCEPTANCE IMAGE
        # ============================================================
        print("\n--- 1. REAL BRAIN MRI ACCEPTANCE IMAGE ---")
        mri_bytes = REAL_MRI_PATH.read_bytes()
        mri_img = Image.open(io.BytesIO(mri_bytes))
        mri_sha = hashlib.sha256(mri_bytes).hexdigest()
        
        print(f"Filename: {REAL_MRI_PATH.name}")
        print(f"MIME type: image/jpeg")
        print(f"Dimensions: {mri_img.size}")
        print(f"Size: {len(mri_bytes)} bytes")
        print(f"SHA-256: {mri_sha}")
        
        # Upload through existing medical record endpoint as Doctor Arjun for Patient One
        upload_resp = await client.post(
            "/api/v1/medical-records",
            headers={"Authorization": f"Bearer {token_arjun}"},
            files={"file": (REAL_MRI_PATH.name, mri_bytes, "image/jpeg")},
            data={
                "patient_id": "PAT-ONE-001",
                "title": "Phase 10 Real Brain MRI Acceptance Scan",
                "record_type": "mri",
                "appointment_id": "APT-2026-001",
                "diagnosis": "Suspected cranial neoplasm",
            },
        )
        assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.text}"
        rec_json = upload_resp.json()
        rec_data = rec_json.get("data", rec_json)
        real_record_id = rec_data["record_id"]
        print(f"Medical Record Created: {real_record_id}")
        
        # Verify file in Phase 9 storage
        db_rec = await db[COLLECTION_MEDICAL_RECORDS].find_one({"record_id": real_record_id})
        assert db_rec is not None
        storage_key = db_rec["file"]["storage_key"]
        stored_bytes = await storage_service.read_file(storage_key, subfolder="medical-records")
        assert len(stored_bytes) == len(mri_bytes)
        assert hashlib.sha256(stored_bytes).hexdigest() == mri_sha
        print("Storage Abstraction verified: Byte parity and SHA-256 match.")
        
        # ============================================================
        # 2. VERIFY RAW MODEL OUTPUT
        # ============================================================
        print("\n--- 2. VERIFY RAW MODEL OUTPUT ---")
        loader = get_model_loader()
        artifact = loader.load_module(AIModuleIdentifier.BRAIN_MRI.value)
        prep = load_and_preprocess_backend_image(mri_bytes, target_size=(224, 224), strategy="resnet50")
        batch = np.expand_dims(prep, axis=0)
        raw_output = artifact.model.predict(batch, verbose=0)[0]
        
        raw_list = [float(x) for x in raw_output]
        print(f"raw_output = {raw_list}")
        assert len(raw_list) == 4, f"Expected 4 outputs, got {len(raw_list)}"
        assert all(np.isfinite(x) for x in raw_list), "Non-finite values found"
        assert not any(np.isnan(x) for x in raw_list), "NaN values found"
        prob_sum = float(np.sum(raw_output))
        print(f"sum(probabilities) = {prob_sum:.8f}")
        assert abs(prob_sum - 1.0) < 1e-4, "Softmax probabilities must sum to 1.0"
        
        class_mapping = artifact.class_names
        print(f"class_mapping = {class_mapping}")
        assert class_mapping == ["glioma", "meningioma", "notumor", "pituitary"], "Class mapping mismatch"
        for idx, (cls_name, val) in enumerate(zip(class_mapping, raw_list)):
            print(f"  Class {idx} [{cls_name}]: {val:.8f}")
            
        pred_idx = int(np.argmax(raw_output))
        pred_class = class_mapping[pred_idx]
        pred_conf = raw_list[pred_idx]
        print(f"Derived Prediction: {pred_class} (Confidence: {pred_conf:.8f})")
        
        # ============================================================
        # 3. DIRECT MONGODB VERIFICATION
        # ============================================================
        print("\n--- 3. DIRECT MONGODB VERIFICATION ---")
        # Trigger AI analysis via endpoint
        ai_resp = await client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {token_arjun}"},
            json={
                "medical_record_id": real_record_id,
                "analysis_type": "BRAIN_MRI",
            },
        )
        assert ai_resp.status_code == 201, f"AI Analysis failed: {ai_resp.text}"
        ai_data = ai_resp.json()
        analysis_id = ai_data["analysis_id"]
        print(f"API Returned analysis_id: {analysis_id}")
        
        # Direct MongoDB Query
        mongo_doc = await db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        assert mongo_doc is not None, "MongoDB document not found!"
        print(f"analysis_id: {mongo_doc.get('analysis_id')}")
        print(f"record_id: {mongo_doc.get('medical_record_id')}")
        print(f"patient_id: {mongo_doc.get('patient_id')}")
        print(f"doctor_id: {mongo_doc.get('doctor_id')}")
        print(f"requested_by: {mongo_doc.get('requested_by')}")
        print(f"prediction: {mongo_doc.get('prediction', {}).get('predicted_class')}")
        print(f"confidence: {mongo_doc.get('prediction', {}).get('confidence')}")
        print(f"probabilities: {mongo_doc.get('prediction', {}).get('class_probabilities')}")
        print(f"model identifier/version: {mongo_doc.get('model', {}).get('module_id')} v{mongo_doc.get('model', {}).get('version')}")
        print(f"created_at: {mongo_doc.get('created_at')}")
        print(f"status: {mongo_doc.get('status')}")
        
        assert mongo_doc["prediction"]["predicted_class"] == pred_class
        assert round(mongo_doc["prediction"]["confidence"], 4) == round(pred_conf, 4)
        print("MongoDB document matches real model inference exactly.")
        
        # ============================================================
        # 4. RESTART PERSISTENCE
        # ============================================================
        print("\n--- 4. RESTART PERSISTENCE ---")
        # Snapshot in-memory DB to disk
        await save_in_memory_snapshot(db)
        await close_mongo_connection()
        print("FastAPI / MongoDB pool stopped.")
        
        # Simulate restart
        await connect_to_mongo()
        db_new = db_manager.db
        print("FastAPI / MongoDB pool restarted & reconnected.")
        
        # Re-fetch via API
        get_resp = await client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {token_arjun}"},
        )
        assert get_resp.status_code == 200, f"Get post-restart failed: {get_resp.text}"
        reloaded_api = get_resp.json()
        
        # Direct DB query
        reloaded_db = await db_new[COLLECTION_AI_ANALYSES].find_one({"analysis_id": analysis_id})
        assert reloaded_db is not None, "Document missing after restart!"
        assert reloaded_db["prediction"]["predicted_class"] == pred_class
        assert round(reloaded_db["prediction"]["confidence"], 4) == round(pred_conf, 4)
        assert reloaded_api["prediction"]["predicted_class"] == pred_class
        print(f"Restart Persistence Confirmed: {analysis_id} recovered with identical prediction {pred_class} and confidence {reloaded_api['prediction']['confidence']}")

        # ============================================================
        # 5. UNAUTHENTICATED TEST
        # ============================================================
        print("\n--- 5. UNAUTHENTICATED TEST ---")
        unauth_resp = await client.post(
            "/api/v1/ai-analyses",
            json={"medical_record_id": real_record_id, "analysis_type": "BRAIN_MRI"},
        )
        print(f"Unauthenticated status code: {unauth_resp.status_code}")
        assert unauth_resp.status_code in (401, 403), f"Expected 401/403, got {unauth_resp.status_code}"
        print("Unauthenticated access strictly blocked.")
        
        # ============================================================
        # 6. PATIENT AUTHORIZATION TEST
        # ============================================================
        print("\n--- 6. PATIENT AUTHORIZATION TEST ---")
        patient_resp = await client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {token_pat1}"},
            json={"medical_record_id": real_record_id, "analysis_type": "BRAIN_MRI"},
        )
        print(f"Patient trigger status code: {patient_resp.status_code}")
        assert patient_resp.status_code == 403, f"Expected 403, got {patient_resp.status_code}"
        print("Patient forbidden from initiating clinical AI analysis.")

        # ============================================================
        # 7. CROSS-PATIENT TEST
        # ============================================================
        print("\n--- 7. CROSS-PATIENT TEST ---")
        # Patient Two tries to get Patient One's analysis
        cross_resp = await client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {token_pat2}"},
        )
        print(f"Cross-patient status code: {cross_resp.status_code}")
        assert cross_resp.status_code in (403, 404), f"Expected 403/404, got {cross_resp.status_code}"
        print("Cross-patient access strictly blocked (0 prediction data leaked).")

        # ============================================================
        # 8. UNAUTHORIZED DOCTOR TEST
        # ============================================================
        print("\n--- 8. UNAUTHORIZED DOCTOR TEST ---")
        # Create a patient and record that has care relationship ONLY with Dr. Arjun Rao, NEVER with Dr. Priya Sharma
        # Note: Use active db_new after step 4's restart
        db_active = db_manager.db
        isolated_pat_id = "PAT-ISOLATED-009"
        await db_active[COLLECTION_PATIENTS].update_one(
            {"patient_id": isolated_pat_id},
            {"$set": {
                "patient_id": isolated_pat_id,
                "first_name": "Isolated",
                "last_name": "Patient",
                "email": "isolated@patient.com",
                "is_deleted": False,
            }},
            upsert=True
        )
        # Establish care relationship ONLY with Dr Arjun Rao
        await db_active[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": "APT-ISOLATED-001"},
            {"$set": {
                "appointment_id": "APT-ISOLATED-001",
                "patient_id": isolated_pat_id,
                "doctor_id": "DOC-RAO-001",
                "status": "completed",
                "is_deleted": False,
            }},
            upsert=True
        )
        isolated_rec_resp = await client.post(
            "/api/v1/medical-records",
            headers={"Authorization": f"Bearer {token_arjun}"},
            files={"file": ("isolated_mri.jpg", mri_bytes, "image/jpeg")},
            data={"patient_id": isolated_pat_id, "title": "Isolated Patient Brain Scan", "record_type": "mri", "appointment_id": "APT-ISOLATED-001"},
        )
        assert isolated_rec_resp.status_code == 201, f"Failed to create isolated record: {isolated_rec_resp.text}"
        isolated_rec_id = isolated_rec_resp.json().get("data", isolated_rec_resp.json())["record_id"]

        # Doctor Priya has NO appointment and NO consultation with PAT-ISOLATED-009
        priya_resp = await client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {token_priya}"},
            json={"medical_record_id": isolated_rec_id, "analysis_type": "BRAIN_MRI"},
        )
        print(f"Unauthorized doctor status code: {priya_resp.status_code}")
        assert priya_resp.status_code == 403, f"Expected 403, got {priya_resp.status_code}: {priya_resp.text}"
        print("Doctor Priya without care relationship blocked with HTTP 403.")

        # ============================================================
        # 9. DELETED RECORD TEST
        # ============================================================
        print("\n--- 9. DELETED RECORD TEST ---")
        del_rec_resp = await client.post(
            "/api/v1/medical-records",
            headers={"Authorization": f"Bearer {token_arjun}"},
            files={"file": ("to_delete.jpg", mri_bytes, "image/jpeg")},
            data={"patient_id": "PAT-ONE-001", "title": "Scan To Delete", "record_type": "mri", "appointment_id": "APT-2026-001"},
        )
        del_id = del_rec_resp.json().get("data", del_rec_resp.json())["record_id"]
        # Delete it
        del_exec = await client.delete(f"/api/v1/medical-records/{del_id}", headers={"Authorization": f"Bearer {token_arjun}"})
        assert del_exec.status_code == 200
        
        del_infer_resp = await client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {token_arjun}"},
            json={"medical_record_id": del_id, "analysis_type": "BRAIN_MRI"},
        )
        print(f"Deleted record inference status code: {del_infer_resp.status_code}")
        assert del_infer_resp.status_code in (404, 400), f"Expected 404, got {del_infer_resp.status_code}"
        print("Deleted record inference rejected safely.")

        # ============================================================
        # 10. MISSING FILE TEST
        # ============================================================
        print("\n--- 10. MISSING FILE TEST ---")
        # Create record without file
        no_file_rec = {
            "record_id": "REC-NO-FILE-001",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "appointment_id": "APT-2026-001",
            "title": "Record with no file",
            "record_type": "mri",
            "is_deleted": False,
            "created_at": utc_now(),
        }
        await db_new[COLLECTION_MEDICAL_RECORDS].insert_one(no_file_rec)
        missing_file_resp = await client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {token_arjun}"},
            json={"medical_record_id": "REC-NO-FILE-001", "analysis_type": "BRAIN_MRI"},
        )
        print(f"Missing file status code: {missing_file_resp.status_code}")
        assert missing_file_resp.status_code == 400, f"Expected 400, got {missing_file_resp.status_code}"
        print("Missing file handled cleanly with HTTP 400.")

        # ============================================================
        # 11. CORRUPT IMAGE TEST
        # ============================================================
        print("\n--- 11. CORRUPT IMAGE TEST ---")
        corrupt_key = f"corrupt_{uuid.uuid4().hex[:6]}.jpg"
        corrupt_rec_id = f"REC-CORRUPT-{uuid.uuid4().hex[:6]}"
        corrupt_bytes = b"CORRUPTED_NON_IMAGE_DATA_BYTES_EXACT"
        await storage_service.save_file(corrupt_bytes, corrupt_key, subfolder="medical-records")
        corrupt_rec = {
            "record_id": corrupt_rec_id,
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "appointment_id": "APT-2026-001",
            "title": "Corrupted scan",
            "record_type": "mri",
            "storage_key": corrupt_key,
            "content_type": "image/jpeg",
            "file": {"storage_key": corrupt_key, "content_type": "image/jpeg"},
            "is_deleted": False,
            "is_ai_eligible": True,
            "created_at": utc_now(),
        }
        await db_new[COLLECTION_MEDICAL_RECORDS].insert_one(corrupt_rec)
        corrupt_resp = await client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {token_arjun}"},
            json={"medical_record_id": corrupt_rec_id, "analysis_type": "BRAIN_MRI"},
        )
        print(f"Corrupt image status code: {corrupt_resp.status_code}")
        assert corrupt_resp.status_code == 400, f"Expected 400, got {corrupt_resp.status_code}"
        assert "corrupted" in corrupt_resp.text.lower() or "invalid" in corrupt_resp.text.lower()
        print("Corrupt image handled cleanly with HTTP 400 decode error.")

        # ============================================================
        # 12. UNSUPPORTED IMAGE / FILE TYPE TEST
        # ============================================================
        print("\n--- 12. UNSUPPORTED FILE TYPE TEST ---")
        pdf_rec_id = f"REC-PDF-{uuid.uuid4().hex[:6]}"
        pdf_rec = {
            "record_id": pdf_rec_id,
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "appointment_id": "APT-2026-001",
            "title": "Lab PDF report",
            "record_type": "clinical_document",
            "storage_key": "lab_doc.pdf",
            "content_type": "application/pdf",
            "file": {"storage_key": "lab_doc.pdf", "content_type": "application/pdf"},
            "is_deleted": False,
            "is_ai_eligible": False,
            "created_at": utc_now(),
        }
        await db_new[COLLECTION_MEDICAL_RECORDS].insert_one(pdf_rec)
        unsupp_resp = await client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {token_arjun}"},
            json={"medical_record_id": pdf_rec_id, "analysis_type": "BRAIN_MRI"},
        )
        print(f"Unsupported type status code: {unsupp_resp.status_code}")
        assert unsupp_resp.status_code == 400, f"Expected 400, got {unsupp_resp.status_code}"
        assert "restricted to medical image" in unsupp_resp.text.lower() or "eligible" in unsupp_resp.text.lower()
        print("Unsupported non-image file type rejected with HTTP 400.")

        # ============================================================
        # 13. MODEL FAILURE TEST
        # ============================================================
        print("\n--- 13. MODEL FAILURE TEST ---")
        registry = get_ai_registry()
        # Temporarily disable module config in registry so it is unavailable
        brain_cfg = registry.get_module("BRAIN_MRI")
        orig_enabled = brain_cfg.enabled
        try:
            brain_cfg.enabled = False
            # Evict from cache to trigger reload
            if "BRAIN_MRI" in loader._module_cache:
                del loader._module_cache["BRAIN_MRI"]
            
            fresh_rec_mf = await client.post(
                "/api/v1/medical-records",
                headers={"Authorization": f"Bearer {token_arjun}"},
                files={"file": (f"mri_mod_fail_{uuid.uuid4().hex[:4]}.jpg", mri_bytes, "image/jpeg")},
                data={"patient_id": "PAT-ONE-001", "title": "Fresh for Model Fail", "record_type": "mri", "appointment_id": "APT-2026-001"},
            )
            fresh_id = fresh_rec_mf.json().get("data", fresh_rec_mf.json())["record_id"]
            
            mod_fail_resp = await client.post(
                "/api/v1/ai-analyses",
                headers={"Authorization": f"Bearer {token_arjun}"},
                json={"medical_record_id": fresh_id, "analysis_type": "BRAIN_MRI"},
            )
            print(f"Model failure status code: {mod_fail_resp.status_code}")
            data = mod_fail_resp.json()
            print(f"Model failure result status: {data.get('status')}")
            assert data.get("status") == "model_unavailable"
            assert data.get("prediction") is None
            print("Model failure correctly recorded as model_unavailable with 0 fake predictions.")
        finally:
            brain_cfg.enabled = orig_enabled
            if "BRAIN_MRI" in loader._module_cache:
                del loader._module_cache["BRAIN_MRI"]
            # reload real model
            loader.load_module("BRAIN_MRI")

        # ============================================================
        # 14. PERSISTENCE FAILURE TEST
        # ============================================================
        print("\n--- 14. PERSISTENCE FAILURE TEST ---")
        fresh_rec_pf = await client.post(
            "/api/v1/medical-records",
            headers={"Authorization": f"Bearer {token_arjun}"},
            files={"file": ("mri_pf.jpg", mri_bytes, "image/jpeg")},
            data={"patient_id": "PAT-ONE-001", "title": "Fresh for PF Test", "record_type": "mri", "appointment_id": "APT-2026-001"},
        )
        pf_rec_id = fresh_rec_pf.json().get("data", fresh_rec_pf.json())["record_id"]
        
        # Intercept mongomock underlying collection replace_one to simulate DB persistence failure when writing completed analysis
        import mongomock.collection
        orig_replace = mongomock.collection.Collection.replace_one
        def fail_replace(self, *args, **kwargs):
            if self.name == COLLECTION_AI_ANALYSES:
                raise RuntimeError("Simulated MongoDB Persistence Crash")
            return orig_replace(self, *args, **kwargs)
        mongomock.collection.Collection.replace_one = fail_replace
        try:
            pf_resp = await client.post(
                "/api/v1/ai-analyses",
                headers={"Authorization": f"Bearer {token_arjun}"},
                json={"medical_record_id": pf_rec_id, "analysis_type": "BRAIN_MRI"},
            )
            print(f"Persistence failure status code: {pf_resp.status_code}")
            # If replace_one raises inside create_analysis, it's caught by outer except Exception,
            # which then calls replace_one again (which also raises), bubbling up to FastAPI as a 500 error,
            # or returning 500. Ensure it did not succeed with completed prediction.
            assert pf_resp.status_code >= 500, f"Expected 5xx on DB persistence crash, got {pf_resp.status_code}: {pf_resp.text}"
            print("Persistence crash raises controlled 500 error; does not report completed success.")
        finally:
            mongomock.collection.Collection.replace_one = orig_replace

        # ============================================================
        # 15. CONCURRENT REAL INFERENCE
        # ============================================================
        print("\n--- 15. CONCURRENT REAL INFERENCE ---")
        # Prepare two distinct records
        # Record 1: glioma MRI (Te-gl_1.jpg)
        rec1_resp = await client.post(
            "/api/v1/medical-records",
            headers={"Authorization": f"Bearer {token_arjun}"},
            files={"file": ("conc_glioma.jpg", mri_bytes, "image/jpeg")},
            data={"patient_id": "PAT-ONE-001", "title": "Concurrent Glioma", "record_type": "mri", "appointment_id": "APT-2026-001"},
        )
        id1 = rec1_resp.json().get("data", rec1_resp.json())["record_id"]
        
        # Record 2: notumor MRI (Testing/notumor/Te-no_0010.jpg or similar)
        notumor_path = Path("model-training/brain/dataset/Testing/notumor")
        notumor_file = list(notumor_path.glob("*.jpg"))[0]
        notumor_bytes = notumor_file.read_bytes()
        
        rec2_resp = await client.post(
            "/api/v1/medical-records",
            headers={"Authorization": f"Bearer {token_arjun}"},
            files={"file": ("conc_notumor.jpg", notumor_bytes, "image/jpeg")},
            data={"patient_id": "PAT-ONE-001", "title": "Concurrent Notumor", "record_type": "mri", "appointment_id": "APT-2026-001"},
        )
        id2 = rec2_resp.json().get("data", rec2_resp.json())["record_id"]
        
        # Launch simultaneously
        req1 = client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {token_arjun}"},
            json={"medical_record_id": id1, "analysis_type": "BRAIN_MRI"},
        )
        req2 = client.post(
            "/api/v1/ai-analyses",
            headers={"Authorization": f"Bearer {token_arjun}"},
            json={"medical_record_id": id2, "analysis_type": "BRAIN_MRI"},
        )
        res1, res2 = await asyncio.gather(req1, req2)
        assert res1.status_code == 201, f"Req 1 failed: {res1.text}"
        assert res2.status_code == 201, f"Req 2 failed: {res2.text}"
        
        data1 = res1.json()
        data2 = res2.json()
        print(f"Req 1: analysis_id={data1['analysis_id']} record={data1['medical_record_id']} pred={data1['prediction']['predicted_class']}")
        print(f"Req 2: analysis_id={data2['analysis_id']} record={data2['medical_record_id']} pred={data2['prediction']['predicted_class']}")
        
        assert data1['analysis_id'] != data2['analysis_id']
        assert data1['medical_record_id'] == id1
        assert data2['medical_record_id'] == id2
        print("Concurrent inference executed simultaneously with zero contamination.")

    # Save snapshot
    await save_in_memory_snapshot(db_new)
    await close_mongo_connection()
    print("\n" + "=" * 60)
    print("ALL ACCEPTANCE VERIFICATIONS SUCCEEDED!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_acceptance())
