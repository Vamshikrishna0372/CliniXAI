import asyncio
import os
import sys
import json
import time
import requests

BASE_URL = "http://localhost:8000"

def run_phase13_acceptance():
    print("=" * 60)
    print("PHASE 13: CANONICAL AI WORKFLOW & PERSISTENCE VERIFICATION")
    print("=" * 60)

    # 1. Doctor Login
    print("\n--- Step 1: Doctor Login ---")
    login_resp = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": "doctor.arjun@clinixai.com",
        "password": "Doctor@123"
    })
    assert login_resp.status_code == 200, f"Doctor login failed: {login_resp.text}"
    doctor_token = login_resp.json()["access_token"]
    doctor_headers = {"Authorization": f"Bearer {doctor_token}"}
    print("Doctor Arjun authenticated successfully.")

    # 2. Genuine MRI Image Pipeline Inference (Section 5)
    print("\n--- Step 2: Genuine AI Inference Pipeline ---")
    mri_path = os.path.join("uploads", "medical-records", "6521E09310C95B7DE0FAE0381957D9D0.jpg")
    assert os.path.exists(mri_path), f"MRI fixture not found at {mri_path}"
    with open(mri_path, "rb") as f:
        img_bytes = f.read()

    files = {"image": ("brain_mri.jpg", img_bytes, "image/jpeg")}
    data = {"analysis_type": "BRAIN_MRI"}
    infer_resp = requests.post(f"{BASE_URL}/api/v1/ai/infer", files=files, data=data, headers=doctor_headers)
    assert infer_resp.status_code == 200, f"Infer failed: {infer_resp.text}"
    infer_data = infer_resp.json()
    analysis_id = infer_data.get("analysis_id")
    print(f"Dynamically generated canonical Analysis ID: {analysis_id}")
    assert analysis_id and analysis_id.startswith("AI-"), f"Invalid analysis_id: {analysis_id}"
    
    print(f"Prediction: {infer_data['predicted_class']}")
    print(f"Confidence: {infer_data['confidence']}")
    print(f"Probabilities: {infer_data['probabilities']}")
    print(f"Model: {infer_data['display_name']} ({infer_data['architecture']} v{infer_data['model_version']})")
    print(f"Grad-CAM available: {infer_data['gradcam_available']}")

    assert infer_data["predicted_class"] == "notumor", f"Expected notumor, got {infer_data['predicted_class']}"
    assert abs(infer_data["confidence"] - 0.3893) < 0.01, f"Expected ~0.3893, got {infer_data['confidence']}"
    assert infer_data["gradcam_available"] is True, "Expected gradcam_available to be True"

    # 3. Direct MongoDB Verification Pre-Restart (Section 6)
    print("\n--- Step 3: MongoDB Direct Query (Pre-Restart) ---")
    import motor.motor_asyncio
    from app.database.mongodb import db_manager, connect_to_mongo, close_mongo_connection
    from app.database.collections import COLLECTION_AI_ANALYSES, COLLECTION_AUDIT_LOGS

    async def get_db_doc(aid):
        await connect_to_mongo()
        doc = await db_manager.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": aid})
        await close_mongo_connection()
        return doc

    doc_pre = asyncio.run(get_db_doc(analysis_id))
    assert doc_pre is not None, f"Analysis {analysis_id} not found in MongoDB pre-restart!"
    print("Pre-Restart Captured MongoDB Document:")
    print(f"  analysis_id: {doc_pre.get('analysis_id')}")
    print(f"  patient_id: {doc_pre.get('patient_id')}")
    print(f"  medical_record_id: {doc_pre.get('medical_record_id')}")
    print(f"  status: {doc_pre.get('status')}")
    print(f"  prediction: {doc_pre.get('prediction')}")
    print(f"  model: {doc_pre.get('model')}")
    print(f"  explainability: {doc_pre.get('explainability')}")
    print(f"  created_at: {doc_pre.get('created_at')}")
    print(f"  updated_at: {doc_pre.get('updated_at')}")

    # 4. Restart Backend Server (Section 6)
    print("\n--- Step 4: Restart Backend Server ---")
    import subprocess
    # Find process on port 8000
    pids = []
    out = subprocess.check_output('netstat -ano | findstr "8000"', shell=True).decode()
    for line in out.strip().splitlines():
        parts = line.split()
        if len(parts) >= 5 and "LISTENING" in line and parts[1].endswith(":8000"):
            pids.append(parts[4])
    for pid in set(pids):
        print(f"Stopping backend PID {pid}...")
        subprocess.call(f"taskkill /F /PID {pid}", shell=True)

    time.sleep(2)
    print("Starting fresh backend instance...")
    proc = subprocess.Popen("uvicorn app.main:app --host 0.0.0.0 --port 8000", shell=True, cwd=".")
    
    # Wait for health
    time.sleep(3)
    healthy = False
    for _ in range(20):
        try:
            r = requests.get(f"{BASE_URL}/api/v1/health")
            if r.status_code == 200:
                healthy = True
                break
        except Exception:
            time.sleep(1)
    assert healthy, "Backend failed to restart!"
    print("Fresh backend instance is healthy.")

    # 5. Direct MongoDB Verification Post-Restart (Section 6)
    print("\n--- Step 5: Direct MongoDB Comparison (Post-Restart) ---")
    doc_post = asyncio.run(get_db_doc(analysis_id))
    assert doc_post is not None, f"Analysis {analysis_id} not found in MongoDB post-restart!"
    
    print("Comparing pre-restart vs post-restart fields:")
    assert doc_post["analysis_id"] == doc_pre["analysis_id"], "analysis_id changed"
    assert doc_post["prediction"]["predicted_class"] == doc_pre["prediction"]["predicted_class"], "predicted_class changed"
    assert abs(doc_post["prediction"]["confidence"] - doc_pre["prediction"]["confidence"]) < 1e-4, "confidence changed"
    assert doc_post["model"]["name"] == doc_pre["model"]["name"], "model.name changed"
    assert doc_post["model"]["architecture"] == doc_pre["model"]["architecture"], "model.architecture changed"
    assert doc_post["explainability"]["artifact_storage_key"] == doc_pre["explainability"]["artifact_storage_key"], "explainability key changed"
    assert doc_post["medical_record_id"] == doc_pre["medical_record_id"], "medical_record_id changed"
    assert doc_post["status"] == doc_pre["status"], "status changed"
    print("All inference, model, explainability, and linkage fields are IDENTICAL across backend restart!")

    # 6. Re-query via API after restart
    print("\n--- Step 6: API Verification Post-Restart ---")
    api_get = requests.get(f"{BASE_URL}/api/v1/ai-analyses/{analysis_id}", headers=doctor_headers)
    assert api_get.status_code == 200, f"API get failed: {api_get.status_code} {api_get.text}"
    api_json = api_get.json()
    assert api_json["analysis_id"] == analysis_id
    assert api_json["prediction"]["predicted_class"] == "notumor"
    assert abs(api_json["prediction"]["confidence"] - 0.3893) < 0.01
    print("API endpoint successfully returned identical persistent analysis.")

    # 7. Doctor Review #1 (Section 7)
    print("\n--- Step 7: Doctor Review #1 ---")
    rev1_payload = {
        "decision": "accepted",
        "clinical_interpretation": "Confirmed no focal intracranial mass or tumor detected on MRI study.",
        "notes": "Doctor Arjun internal review notes."
    }
    rev1_resp = requests.post(f"{BASE_URL}/api/v1/ai-analyses/{analysis_id}/review", json=rev1_payload, headers=doctor_headers)
    assert rev1_resp.status_code == 200, f"Review #1 failed: {rev1_resp.text}"
    rev1_data = rev1_resp.json()
    assert rev1_data["status"] == "reviewed", f"Expected reviewed status, got {rev1_data['status']}"
    assert rev1_data["doctor_review"]["reviewed_by"] == "USR-DOC-RAO-001"
    assert rev1_data["doctor_review"]["decision"] == "accepted"
    assert rev1_data["doctor_review"]["reviewed_at"] is not None
    print(f"Review #1 submitted successfully: status={rev1_data['status']}, reviewed_by={rev1_data['doctor_review']['reviewed_by']}")

    # 8. Review Revision (Review #2) & Immutability (Section 8)
    print("\n--- Step 8: Review Revision (Review #2) & Immutability ---")
    rev2_payload = {
        "decision": "accepted_as_supporting_information",
        "clinical_interpretation": "Confirmed baseline normal brain MRI imaging with non-pathological findings.",
        "notes": "Doctor Arjun updated internal review notes."
    }
    rev2_resp = requests.post(f"{BASE_URL}/api/v1/ai-analyses/{analysis_id}/review", json=rev2_payload, headers=doctor_headers)
    assert rev2_resp.status_code == 200, f"Review #2 failed: {rev2_resp.text}"
    rev2_data = rev2_resp.json()
    assert rev2_data["status"] == "reviewed"
    assert rev2_data["doctor_review"]["decision"] == "accepted_as_supporting_information"
    assert rev2_data["doctor_review"]["clinical_interpretation"] == rev2_payload["clinical_interpretation"]
    # Verify AI inference immutability
    assert rev2_data["prediction"]["predicted_class"] == "notumor"
    assert abs(rev2_data["prediction"]["confidence"] - 0.3893) < 0.01
    assert rev2_data["model"]["architecture"] == "ResNet50"
    assert rev2_data["explainability"]["artifact_storage_key"] == doc_pre["explainability"]["artifact_storage_key"]
    print("Review #2 updated review successfully while AI prediction, model, and artifacts remained strictly immutable.")

    # 9. Patient Security Boundary (Section 9)
    print("\n--- Step 9: Patient Security Boundary ---")
    # Patient One login
    pat_login = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
        "email": "patient.one@clinixai.com",
        "password": "Patient@123"
    })
    assert pat_login.status_code == 200, f"Patient login failed: {pat_login.text}"
    pat_token = pat_login.json()["access_token"]
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    rep_resp = requests.get(f"{BASE_URL}/api/v1/ai-analyses/{analysis_id}/report", headers=pat_headers)
    assert rep_resp.status_code == 200, f"Patient report failed: {rep_resp.text}"
    rep_data = rep_resp.json()
    print("Patient Report Response:")
    print(json.dumps(rep_data, indent=2))
    assert rep_data["status"] == "reviewed"
    assert "report" in rep_data
    report = rep_data["report"]
    assert "report_date" in report
    assert "doctor_name" in report
    assert "result_summary" in report
    assert "model_confidence" in report
    assert "doctor_interpretation" in report
    assert "disclaimer" in report

    # Verify absence of sensitive leakages
    raw_text = rep_resp.text
    assert "Doctor Arjun internal review notes" not in raw_text, "Private doctor notes exposed to patient!"
    assert "Doctor Arjun updated internal review notes" not in raw_text, "Private doctor notes exposed to patient!"
    assert "eyJ" not in raw_text, "JWT exposed in patient report!"
    assert "storage_path" not in raw_text, "Internal storage path exposed!"
    print("Patient security boundary verified: patient receives clinical report without internal notes or secrets.")

    print("\n" + "=" * 60)
    print("PHASE 13 SERVER WORKFLOW & PERSISTENCE FULLY VERIFIED!")
    print("=" * 60)

if __name__ == "__main__":
    run_phase13_acceptance()
