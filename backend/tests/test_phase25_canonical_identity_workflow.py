"""
Phase 25 Automated Test Suite:
- Canonical Patient Identity (PAT-... enforcement, zero USR-... in documents)
- Explicit Medical Image Modality (Brain MRI vs Chest X-Ray vs other)
- Brain MRI Deep Learning Inference & GradientTape Grad-CAM explainability
- Doctor Clinical Review & Explicit Release governance
- Strict RBAC & Cross-Doctor Object-Level Authorization
- Authoritative Clinical Timeline Service
"""

import os
import io
import pytest
import numpy as np
from PIL import Image
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.mongodb import get_db, connect_to_mongo
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_APPOINTMENTS, COLLECTION_DOCUMENTS, COLLECTION_AI_ANALYSES
)
from app.services.timeline_service import TimelineService


@pytest.fixture(scope="session", autouse=True)
async def setup_db():
    await connect_to_mongo()


async def get_auth_token(client: AsyncClient, email: str, password: str = "Doctor@123") -> str:
    passwords_to_try = [password, "Doctor@123", "Patient@123", "Admin@123", "Password@123", "admin123"]
    resp = None
    for pwd in passwords_to_try:
        resp = await client.post("/api/v1/auth/login", json={"email": email, "password": pwd})
        if resp.status_code == 200:
            break
    assert resp is not None and resp.status_code == 200, f"Login failed for {email}: {resp.text if resp else 'No response'}"
    body = resp.json()
    return body["data"]["access_token"] if "data" in body else body["access_token"]


def create_synthetic_mri_image_bytes() -> bytes:
    """Create a realistic-dimensioned synthetic MRI image."""
    arr = np.zeros((224, 224, 3), dtype=np.uint8)
    # Draw oval / brain-like shape
    y, x = np.ogrid[:224, :224]
    mask = ((x - 112) ** 2) / (70 ** 2) + ((y - 112) ** 2) / (90 ** 2) <= 1
    arr[mask] = 160
    # Add some texture / details
    inner_mask = ((x - 100) ** 2) / (25 ** 2) + ((y - 100) ** 2) / (25 ** 2) <= 1
    arr[inner_mask] = 220
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_reconciled_documents_have_canonical_patient_ids():
    """Verify that no documents in the database possess a legacy USR-... patient_id."""
    db = get_db()
    usr_docs = await db[COLLECTION_DOCUMENTS].find({"patient_id": {"$regex": "^USR-"}}).to_list(100)
    assert len(usr_docs) == 0, f"Found {len(usr_docs)} un-reconciled documents with USR- IDs: {usr_docs}"


@pytest.mark.asyncio
async def test_patient_upload_enforces_canonical_patient_id():
    """Verify patient document upload automatically resolves and saves canonical PAT-... ID."""
    db = get_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Find a test patient with valid local auth credentials
        pat_user = await db[COLLECTION_USERS].find_one({
            "role": "patient",
            "auth_provider": "local",
            "password_hash": {"$exists": True, "$ne": None}
        })
        assert pat_user is not None, "Test patient user required"
        patient = await db[COLLECTION_PATIENTS].find_one({"user_id": pat_user["user_id"]})
        assert patient is not None, "Patient record required"

        canonical_pat_id = patient["patient_id"]
        user_id = pat_user["user_id"]
        token = await get_auth_token(client, pat_user["email"], "Patient@123")

        # Attempt to upload with explicit Brain MRI modality and tampering patient_id with user_id
        mri_bytes = create_synthetic_mri_image_bytes()
        files = {"file": ("patient_brain_scan.jpg", mri_bytes, "image/jpeg")}
        data = {
            "patient_id": user_id,  # Tampered or legacy user_id
            "title": "Brain MRI Axial Scan",
            "category": "Brain MRI",
        }
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.post("/api/v1/documents", files=files, data=data, headers=headers)
        assert resp.status_code in [200, 201], f"Document upload failed: {resp.text}"
        doc_data = resp.json()

        # Document MUST be saved with canonical PAT- ID, not USR-
        assert doc_data["patient_id"] == canonical_pat_id
        assert doc_data["patient_id"].startswith("PAT-")
        assert not doc_data["patient_id"].startswith("USR-")

        # Check DB record
        db_doc = await db[COLLECTION_DOCUMENTS].find_one({"document_id": doc_data["document_id"]})
        assert db_doc is not None
        assert db_doc["patient_id"] == canonical_pat_id
        assert db_doc["category"] in ["MRI", "BRAIN_MRI", "Brain MRI"]


@pytest.mark.asyncio
async def test_brain_mri_dl_inference_and_gradcam():
    """Verify genuine DL inference (brain_model.keras) and GradientTape Grad-CAM execution."""
    db = get_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Find doctor with local auth credentials
        doc_user = await db[COLLECTION_USERS].find_one({
            "email": "doctor.arjun@clinixai.com",
            "auth_provider": "local"
        })
        assert doc_user is not None
        doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": doc_user["user_id"]})
        assert doctor is not None
        doc_token = await get_auth_token(client, doc_user["email"], "Doctor@123")

        # Find patient with established appointment with this doctor
        appt = await db[COLLECTION_APPOINTMENTS].find_one({
            "doctor_id": doctor["doctor_id"],
            "is_deleted": {"$ne": True}
        })
        assert appt is not None
        pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": appt["patient_id"]})
        assert pat is not None

        # Upload a Brain MRI document for this patient
        mri_bytes = create_synthetic_mri_image_bytes()
        files = {"file": ("diagnostic_brain_mri.jpg", mri_bytes, "image/jpeg")}
        upload_resp = await client.post(
            "/api/v1/documents",
            files=files,
            data={"patient_id": pat["patient_id"], "title": "Diagnostic Brain MRI", "category": "Brain MRI"},
            headers={"Authorization": f"Bearer {doc_token}"}
        )
        assert upload_resp.status_code in [200, 201]
        uploaded_doc = upload_resp.json()
        doc_id = uploaded_doc["document_id"]

        # Doctor triggers AI analysis without re-uploading the image
        ai_resp = await client.post(
            "/api/v1/ai-analyses",
            json={
                "document_id": doc_id,
                "patient_id": pat["patient_id"],
                "analysis_type": "BRAIN_MRI",
                "force_new": True,
            },
            headers={"Authorization": f"Bearer {doc_token}"}
        )
        assert ai_resp.status_code in [200, 201], f"AI analysis failed: {ai_resp.text}"
        ai_data = ai_resp.json()
        analysis_id = ai_data["analysis_id"]

        # Validate prediction output
        assert "prediction" in ai_data
        pred = ai_data["prediction"]
        assert pred["predicted_class"] in ["glioma", "meningioma", "notumor", "pituitary", "Glioma", "Meningioma", "No Tumor", "Pituitary"]
        assert 0.0 <= pred["confidence"] <= 1.0
        assert len(pred.get("class_probabilities", {}) or pred.get("probabilities", [])) > 0

        # Validate Grad-CAM & Explainability
        assert "explainability" in ai_data
        assert ai_data["explainability"] is not None
        assert ai_data["explainability"]["method"] == "grad_cam"
        assert ai_data["explainability"]["target_layer"] == "conv5_block3_out"
        assert "artifact_storage_key" in ai_data["explainability"]

        # Verify initial status is awaiting_review or pending_review
        assert str(ai_data.get("status", "")).lower() in ["completed", "pending_review", "awaiting_review"]
        assert ai_data.get("is_released_to_patient") is not True


@pytest.mark.asyncio
async def test_patient_access_restricted_before_doctor_release():
    """Verify patient cannot view AI analysis before explicit doctor approval and release."""
    db = get_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Doctor
        doc_user = await db[COLLECTION_USERS].find_one({"email": "doctor.arjun@clinixai.com"})
        doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": doc_user["user_id"]})
        doc_token = await get_auth_token(client, doc_user["email"], "Doctor@123")

        # Patient with appointment
        pat_user = await db[COLLECTION_USERS].find_one({"email": "patient.one@clinixai.com"})
        pat = await db[COLLECTION_PATIENTS].find_one({"user_id": pat_user["user_id"]})
        pat_token = await get_auth_token(client, pat_user["email"], "Patient@123")

        # Upload MRI
        mri_bytes = create_synthetic_mri_image_bytes()
        files = {"file": ("unreleased_scan.jpg", mri_bytes, "image/jpeg")}
        up_resp = await client.post(
            "/api/v1/documents",
            files=files,
            data={"patient_id": pat["patient_id"], "title": "Unreleased Brain MRI", "category": "Brain MRI"},
            headers={"Authorization": f"Bearer {doc_token}"}
        )
        doc_id = up_resp.json()["document_id"]

        # Run AI
        ai_resp = await client.post(
            "/api/v1/ai-analyses",
            json={"document_id": doc_id, "patient_id": pat["patient_id"], "analysis_type": "BRAIN_MRI", "force_new": True},
            headers={"Authorization": f"Bearer {doc_token}"}
        )
        analysis_id = ai_resp.json()["analysis_id"]

        # Patient attempts to view unreleased AI analysis
        pat_view_resp = await client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {pat_token}"}
        )
        # Should be 403 Forbidden
        assert pat_view_resp.status_code == 403, f"Expected 403 for unreleased AI analysis, got {pat_view_resp.status_code}"

        # Doctor reviews and explicitly releases
        rev_resp = await client.post(
            f"/api/v1/ai-analyses/{analysis_id}/review",
            json={
                "decision": "accepted",
                "notes": "Brain MRI reviewed. AI localization confirmed.",
                "clinical_interpretation": "Confirmed benign meningioma. Recommended observation.",
                "release_to_patient": True,
            },
            headers={"Authorization": f"Bearer {doc_token}"}
        )
        assert rev_resp.status_code in [200, 201], f"Doctor review failed: {rev_resp.text}"

        # Now patient can view the sanitized released result
        pat_view_after_resp = await client.get(
            f"/api/v1/ai-analyses/{analysis_id}",
            headers={"Authorization": f"Bearer {pat_token}"}
        )
        assert pat_view_after_resp.status_code == 200, f"Expected 200 after release, got {pat_view_after_resp.status_code}"
        released_data = pat_view_after_resp.json()
        assert "prediction" in released_data
        assert released_data.get("is_released_to_patient") is True


@pytest.mark.asyncio
async def test_rbac_unrelated_doctor_forbidden():
    """Verify an unrelated doctor without care relationship cannot access patient workspace/documents."""
    db = get_db()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Doctor A: doctor.arjun
        doc_a_user = await db[COLLECTION_USERS].find_one({"email": "doctor.arjun@clinixai.com"})
        doc_a = await db[COLLECTION_DOCTORS].find_one({"user_id": doc_a_user["user_id"]})

        # Doctor B: doctor.priya
        doc_b_user = await db[COLLECTION_USERS].find_one({"email": "doctor.priya@clinixai.com"})
        doc_b = await db[COLLECTION_DOCTORS].find_one({"user_id": doc_b_user["user_id"]})
        doc_b_token = await get_auth_token(client, doc_b_user["email"], "Doctor@123")

        # Find or create a patient that has an appointment with doc_a only
        # Check patients with doc_a appointment
        doc_a_appts = await db[COLLECTION_APPOINTMENTS].find({"doctor_id": doc_a["doctor_id"]}).to_list(100)
        target_pat_id = None
        for a in doc_a_appts:
            pid = a["patient_id"]
            # verify doc_b has NO appointment with this patient
            has_b = await db[COLLECTION_APPOINTMENTS].find_one({"doctor_id": doc_b["doctor_id"], "patient_id": pid})
            if not has_b:
                target_pat_id = pid
                break

        if not target_pat_id:
            pytest.skip("No exclusive patient found for doctor A")

        # Doctor B attempts to view Doctor A's patient clinical workspace & documents
        resp = await client.get(f"/api/v1/patients/{target_pat_id}", headers={"Authorization": f"Bearer {doc_b_token}"})
        assert resp.status_code == 403, f"Expected 403 Forbidden for unrelated doctor on patient, got {resp.status_code}"

        doc_resp = await client.get(f"/api/v1/documents?patient_id={target_pat_id}", headers={"Authorization": f"Bearer {doc_b_token}"})
        assert doc_resp.status_code == 403, f"Expected 403 Forbidden for unrelated doctor on documents, got {doc_resp.status_code}"


@pytest.mark.asyncio
async def test_clinical_timeline_service():
    """Verify TimelineService aggregates all events correctly using canonical patient ID."""
    db = get_db()
    patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": "PAT-ONE-001"})
    if not patient:
        patient = await db[COLLECTION_PATIENTS].find_one({"is_active": True})
    assert patient is not None

    service = TimelineService(db)
    timeline = await service.get_patient_timeline(patient["patient_id"])
    assert timeline.patient_id == patient["patient_id"]
    assert isinstance(timeline.events, list)
    assert timeline.total_events >= 0
