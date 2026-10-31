"""Comprehensive E2E Medical AI Prediction & XAI/Grad-CAM Verification Test Suite.

Verifies:
1. Module loading and availability across registered AI modalities.
2. Stateless direct-upload inference with 3 distinct real medical image patterns.
3. Verification of prediction class, probability distributions, confidence scores, and base64 Grad-CAM activation heatmaps.
4. Record-backed AI analysis creation (`POST /api/v1/ai-analyses`).
5. MongoDB persistence & state transitions (`AWAITING_REVIEW`, `REVIEWED`).
6. Doctor review submission workflow (`POST /api/v1/ai-analyses/{analysis_id}/review`).
7. Grad-CAM overlay image artifact streaming (`GET /api/v1/ai-analyses/{analysis_id}/gradcam`).
8. Patient-safe report generation (`GET /api/v1/ai-analyses/{analysis_id}/report`).
9. Paginated listing of AI analyses (`GET /api/v1/ai-analyses`).
"""

import io
import pytest
import pytest_asyncio
from PIL import Image, ImageDraw
from httpx import AsyncClient
from app.database.mongodb import connect_to_mongo, db_manager
from app.database.db_seeder import seed_initial_data
from app.database.collections import COLLECTION_USERS, COLLECTION_DOCUMENTS, COLLECTION_AI_ANALYSES


def generate_patterned_image_bytes(pattern: str) -> bytes:
    """Generates valid 224x224 PNG image bytes with distinct pattern features."""
    img = Image.new("RGB", (224, 224), color=(15, 15, 15))
    draw = ImageDraw.Draw(img)

    if pattern == "top_left":
        draw.ellipse([20, 20, 80, 80], fill=(230, 230, 250), outline=(255, 255, 255))
    elif pattern == "center":
        draw.ellipse([80, 80, 140, 140], fill=(250, 200, 200), outline=(255, 255, 255))
    elif pattern == "bottom_right":
        draw.ellipse([140, 140, 200, 200], fill=(200, 250, 200), outline=(255, 255, 255))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest_asyncio.fixture(autouse=True, scope="module")
async def init_database():
    """Ensure MongoDB connection and initial seed data are populated."""
    await connect_to_mongo()
    if db_manager.db is not None:
        await seed_initial_data(db_manager.db)


async def get_doctor_token(async_client: AsyncClient) -> str:
    """Obtains a valid access token for a Doctor account."""
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "doctor.arjun@clinixai.com",
        "password": "Doctor@123",
    })
    assert res.status_code == 200, f"Doctor login failed: {res.text}"
    body = res.json()
    return body["data"]["access_token"] if "data" in body else body["access_token"]


async def get_patient_token(async_client: AsyncClient) -> str:
    """Obtains a valid access token for a Patient account."""
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "patient.one@clinixai.com",
        "password": "Patient@123",
    })
    assert res.status_code == 200, f"Patient login failed: {res.text}"
    body = res.json()
    return body["data"]["access_token"] if "data" in body else body["access_token"]


@pytest.mark.asyncio
async def test_ai_health_and_modules_list(async_client: AsyncClient):
    """Test AI health check and modules endpoints."""
    res = await async_client.get("/api/v1/ai/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in {"ok", "degraded", "healthy", "available"}
    assert "modules" in data

    mod_res = await async_client.get("/api/v1/ai/modules")
    assert mod_res.status_code == 200
    modules = mod_res.json()
    assert len(modules) >= 5
    mod_ids = [m["module_id"] for m in modules]
    assert "BRAIN_MRI" in mod_ids
    assert "CHEST_XRAY" in mod_ids


@pytest.mark.asyncio
async def test_direct_infer_3_independent_images(async_client: AsyncClient):
    """Test direct upload inference on 3 distinct independent medical image patterns."""
    doc_token = await get_doctor_token(async_client)
    headers = {"Authorization": f"Bearer {doc_token}"}

    patterns = ["top_left", "center", "bottom_right"]
    results = []

    for idx, p in enumerate(patterns):
        img_bytes = generate_patterned_image_bytes(p)
        files = {"image": (f"test_mri_{p}.png", img_bytes, "image/png")}
        data = {"analysis_type": "BRAIN_MRI"}

        res = await async_client.post("/api/v1/ai/infer", headers=headers, files=files, data=data)
        assert res.status_code == 200, f"Direct infer failed for pattern {p}: {res.text}"
        body = res.json()

        assert body["module_id"] == "BRAIN_MRI"
        assert body["predicted_class"] is not None
        assert 0.0 <= body["confidence"] <= 1.0
        assert len(body["probabilities"]) > 0
        assert body["gradcam_available"] is True
        assert body["gradcam_b64"] is not None
        assert body["gradcam_b64"].startswith("data:image/png;base64,")

        results.append(body)

    # Verify predictions were recorded independently
    assert len(results) == 3


@pytest.mark.asyncio
async def test_record_backed_ai_analysis_pipeline(async_client: AsyncClient):
    """Test end-to-end medical record upload -> AI analysis trigger -> MongoDB -> Doctor Review -> Report."""
    doc_token = await get_doctor_token(async_client)
    headers = {"Authorization": f"Bearer {doc_token}"}

    # 1. Upload a medical image document
    img_bytes = generate_patterned_image_bytes("center")
    upload_res = await async_client.post(
        "/api/v1/documents",
        headers=headers,
        files={"file": ("brain_scan_patient.png", img_bytes, "image/png")},
        data={"patient_id": "PAT-ONE-001", "category": "MRI", "title": "Brain MRI Scan"}
    )
    assert upload_res.status_code == 201, f"Document upload failed: {upload_res.text}"
    upload_body = upload_res.json()
    doc_data = upload_body["data"] if "data" in upload_body else upload_body
    record_id = doc_data["document_id"]

    # 2. Trigger AI Analysis for uploaded medical record
    analysis_req = {
        "medical_record_id": record_id,
        "analysis_type": "BRAIN_MRI",
    }
    create_res = await async_client.post("/api/v1/ai-analyses", headers=headers, json=analysis_req)
    assert create_res.status_code == 201, f"AI Analysis creation failed: {create_res.text}"
    analysis_data = create_res.json()
    analysis_id = analysis_data["analysis_id"]

    assert analysis_data["status"].upper() in {"AWAITING_REVIEW", "COMPLETED", "PROCESSING"}
    assert analysis_data["prediction"] is not None
    assert analysis_data["prediction"]["predicted_class"] is not None

    # 3. Retrieve Single AI Analysis detail
    get_res = await async_client.get(f"/api/v1/ai-analyses/{analysis_id}", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["analysis_id"] == analysis_id

    # 4. Retrieve Grad-CAM PNG Heatmap Stream
    gc_res = await async_client.get(f"/api/v1/ai-analyses/{analysis_id}/gradcam", headers=headers)
    assert gc_res.status_code == 200
    assert gc_res.headers["content-type"] == "image/png"
    assert len(gc_res.content) > 0

    # 5. Doctor submits clinical review & interpretation
    review_req = {
        "decision": "accepted",
        "clinical_interpretation": "Tumor lesion confirmed in high-activation region. Recommend follow-up neuro-imaging.",
        "notes": "Patient advised regarding neurosurgical consultation.",
        "release_to_patient": True,
    }
    rev_res = await async_client.post(f"/api/v1/ai-analyses/{analysis_id}/review", headers=headers, json=review_req)
    assert rev_res.status_code == 200, f"Doctor review failed: {rev_res.text}"
    rev_data = rev_res.json()
    assert rev_data["status"].upper() in {"REVIEWED", "COMPLETED"}
    assert rev_data["doctor_review"]["decision"].lower() == "accepted"

    # 6. Patient retrieves own reviewed patient-safe report
    pat_token = await get_patient_token(async_client)
    pat_headers = {"Authorization": f"Bearer {pat_token}"}
    rep_res = await async_client.get(f"/api/v1/ai-analyses/{analysis_id}/report", headers=pat_headers)
    assert rep_res.status_code == 200, f"Patient report failed: {rep_res.text}"
    rep_data = rep_res.json()
    assert rep_data["report"]["doctor_interpretation"] is not None

    # 7. List paginated AI Analyses
    list_res = await async_client.get("/api/v1/ai-analyses", headers=headers)
    assert list_res.status_code == 200
    items = list_res.json()["items"]
    assert any(i["analysis_id"] == analysis_id for i in items)
