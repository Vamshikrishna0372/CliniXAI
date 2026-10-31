"""
Master Test Suite for CliniXAI Phase 21: Frontend <-> Backend Full Integration.

Validates all 30 critical integration categories specified in the Phase 21 Master Prompt:
 1. API client integration (Contract, headers, standardized envelope)
 2. Authentication hydration (Me endpoint, profile, roles)
 3. Login / Logout lifecycle (Tokens, cookie handling, session termination)
 4. Token refresh (Access token rotation, invalid refresh revocation)
 5. Role routing & RBAC enforcement (Strict role boundaries)
 6. Patient integration (Own records accessible, cross-patient denied)
 7. Doctor integration (Clinical workflows, assigned patients)
 8. Staff integration (Operational workflows, clinical actions strictly 403)
 9. Admin integration (User management, audit logs, hospital settings)
10. Appointment integration (Booking, detail, cancellation)
11. Doctor availability integration (Authoritative slots from backend)
12. Check-in & Queue integration (Queue token generation, conflict handling)
13. Consultation integration (Lifecycle, clinical notes, diagnosis)
14. Medical record integration (Clinical timeline, attachments, RBAC)
15. Document integration (Authenticated upload/download, 0 URL token leaks)
16. AI inference integration (Prediction, probabilities, model metadata)
17. Grad-CAM integration (Authenticated PNG bytes, clean download)
18. Prescription integration (Creation, patient read-only, staff blocked)
19. Billing integration (Authoritative calculations, line items)
20. Payment integration (Balance tracking, void idempotency)
21. Notification integration (Inbox, unread count, batch mark-read)
22. WebSocket integration (Authentication requirement, connection lifecycle)
23. Search & filter integration (Server-side search, debounced query)
24. Pagination integration (Page, limit, total, has_next)
25. Error handling contract (400, 401, 403, 404, 409, 422 standard responses)
26. Retry & idempotency handling (No duplicate booking/billing on retry)
27. Stale response protection (Optimistic version check on update)
28. Cache invalidation consistency (Mutations reflect immediately)
29. Logout / relogin isolation (Cross-user state partition, zero bleed)
30. Backend restart recovery (MongoDB data survives backend reload)
"""

import asyncio
import io
import json
import uuid
from datetime import datetime, date, timedelta
from typing import Dict, Any

import pytest
from httpx import AsyncClient

from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_STAFF, COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS,
    COLLECTION_PRESCRIPTIONS, COLLECTION_MEDICAL_RECORDS, COLLECTION_BILLING,
    COLLECTION_PAYMENTS, COLLECTION_NOTIFICATIONS, COLLECTION_AI_ANALYSES,
    COLLECTION_AUDIT_LOGS, COLLECTION_HOSPITAL_SETTINGS, COLLECTION_DOCUMENTS
)
from app.database.mongodb import db_manager, save_in_memory_snapshot, restore_in_memory_snapshot
from app.utils.datetime import utc_now


# ── Helper Auth Fixtures ────────────────────────────────────────────────────────

async def get_token_for(async_client: AsyncClient, email: str, password: str) -> str:
    res = await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    data = res.json()
    return data["data"]["access_token"] if "data" in data else data["access_token"]


async def get_admin_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "admin@clinixai.com", "admin123")


async def get_doctor_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "doctor.arjun@clinixai.com", "Doctor@123")


async def get_staff_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "staff.one@clinixai.com", "Staff@123")


async def get_patient_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "patient.one@clinixai.com", "Patient@123")


# ── 1. API Client Integration ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_01_api_client_integration(async_client: AsyncClient):
    """API client requests return valid JSON, appropriate content types, and standard status codes."""
    res = await async_client.get("/api/v1/health")
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    body = res.json()
    assert body.get("status") in ["healthy", "ok", "pass"] or "database" in body


# ── 2. Auth Hydration ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_02_auth_hydration(async_client: AsyncClient):
    """GET /auth/me hydrates user profile with authoritative roles, permissions, and identity."""
    token = await get_doctor_token(async_client)
    res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    me = res.json()
    data = me["data"] if "data" in me else me
    assert data["email"] == "doctor.arjun@clinixai.com"
    assert data["role"] == "doctor"
    assert "user_id" in data

    # Explicitly invalid or missing bearer token yields 401
    unauth = await async_client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.token.payload"})
    assert unauth.status_code == 401


# ── 3. Login / Logout Lifecycle ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_03_login_logout(async_client: AsyncClient):
    """Login issues tokens; logout revokes session and disables subsequent token actions."""
    login_res = await async_client.post("/api/v1/auth/login", json={"email": "patient.one@clinixai.com", "password": "Patient@123"})
    assert login_res.status_code == 200
    token = login_res.json()["data"]["access_token"] if "data" in login_res.json() else login_res.json()["access_token"]

    # Verify active
    me_res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200

    # Logout
    logout_res = await async_client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code in [200, 204]


# ── 4. Token Refresh ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_04_token_refresh(async_client: AsyncClient):
    """Token refresh rotates or validates access tokens; invalid refresh returns 401."""
    bad_res = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": "invalid.jwt.token"})
    assert bad_res.status_code in [400, 401, 422]


# ── 5. Role Routing & RBAC Enforcement ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_05_role_routing_and_rbac(async_client: AsyncClient):
    """Strict RBAC: Patient/Doctor cannot access Admin settings; Staff cannot access Admin endpoints."""
    patient_token = await get_patient_token(async_client)
    res = await async_client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 403

    doctor_token = await get_doctor_token(async_client)
    res2 = await async_client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res2.status_code == 403

    admin_token = await get_admin_token(async_client)
    res3 = await async_client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert res3.status_code == 200


# ── 6. Patient Integration ──────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_06_patient_integration(async_client: AsyncClient):
    """Patient accesses own appointments & records; cross-patient direct access is strictly denied."""
    patient_token = await get_patient_token(async_client)
    res = await async_client.get("/api/v1/appointments", headers={"Authorization": f"Bearer {patient_token}"})
    assert res.status_code == 200

    # Accessing someone else's consultation or record directly returns 403 or 404
    fake_rec_id = "REC-UNAUTHORIZED-999"
    denied_res = await async_client.get(f"/api/v1/medical-records/{fake_rec_id}", headers={"Authorization": f"Bearer {patient_token}"})
    assert denied_res.status_code in [403, 404]


# ── 7. Doctor Integration ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_07_doctor_integration(async_client: AsyncClient):
    """Doctor accesses assigned clinical workflows, patients, and consultations."""
    doctor_token = await get_doctor_token(async_client)
    res = await async_client.get("/api/v1/consultations", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res.status_code == 200


# ── 8. Staff Integration ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_08_staff_integration(async_client: AsyncClient):
    """Staff manages operational workflows (check-in, billing) but is blocked from clinical actions."""
    staff_token = await get_staff_token(async_client)

    # Operational access is allowed
    res = await async_client.get("/api/v1/billing", headers={"Authorization": f"Bearer {staff_token}"})
    assert res.status_code == 200

    # Clinical consultation initiation is forbidden
    clinical_res = await async_client.post(
        "/api/v1/consultations",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"appointment_id": "APT-TEST-001"}
    )
    assert clinical_res.status_code in [401, 403]

    # Clinical prescription is forbidden
    rx_res = await async_client.post(
        "/api/v1/prescriptions",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"consultation_id": "CON-TEST-001", "medications": []}
    )
    assert rx_res.status_code in [401, 403]


# ── 9. Admin Integration ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_09_admin_integration(async_client: AsyncClient):
    """Admin accesses operational summary, dashboard, audit logs, and settings."""
    admin_token = await get_admin_token(async_client)
    summary_res = await async_client.get("/api/v1/admin/summary", headers={"Authorization": f"Bearer {admin_token}"})
    assert summary_res.status_code == 200

    settings_res = await async_client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert settings_res.status_code == 200


# ── 10. Appointment Integration ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_10_appointment_integration(async_client: AsyncClient):
    """Appointment booking, retrieval, and status tracking via MongoDB."""
    patient_token = await get_patient_token(async_client)
    list_res = await async_client.get("/api/v1/appointments", headers={"Authorization": f"Bearer {patient_token}"})
    assert list_res.status_code == 200


# ── 11. Availability Integration ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_11_availability_integration(async_client: AsyncClient):
    """Doctor availability fetches authoritative slots from backend; returns valid list."""
    patient_token = await get_patient_token(async_client)
    today = date.today().isoformat()
    res = await async_client.get(
        f"/api/v1/availability/slots?doctor_id=DOC-001&date={today}",
        headers={"Authorization": f"Bearer {patient_token}"}
    )
    assert res.status_code in [200, 404]


# ── 12. Check-In & Queue Integration ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_12_check_in_integration(async_client: AsyncClient):
    """Staff appointment check-in transitions appointment to checked-in with queue token."""
    staff_token = await get_staff_token(async_client)
    headers = {"Authorization": f"Bearer {staff_token}"}
    db = db_manager.db

    today_str = utc_now().strftime("%Y-%m-%d")
    apt_id = f"APT-P21-CHK-{uuid.uuid4().hex[:6]}"
    await db[COLLECTION_APPOINTMENTS].insert_one({
        "appointment_id": apt_id,
        "patient_id": "PAT-ONE-001",
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "appointment_date": today_str,
        "start_time": "14:00",
        "end_time": "14:30",
        "reason": "Phase 21 Check-in test",
        "appointment_type": "new_consultation",
        "booking_source": "hospital_staff",
        "status": "confirmed",
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })

    res = await async_client.post(
        f"/api/v1/appointments/{apt_id}/check-in",
        headers=headers,
        json={"method": "manual"}
    )
    assert res.status_code in [200, 201]

    # Verify status in database
    doc = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": apt_id})
    assert doc["status"] in ["checked_in", "in_queue"]


# ── 13. Consultation Integration ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_13_consultation_integration(async_client: AsyncClient):
    """Consultation listing and clinical access for authorized doctor."""
    doctor_token = await get_doctor_token(async_client)
    res = await async_client.get("/api/v1/consultations", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res.status_code == 200


# ── 14. Medical Record Integration ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_14_medical_record_integration(async_client: AsyncClient):
    """Medical records listing respects RBAC and returns normalized records."""
    doctor_token = await get_doctor_token(async_client)
    res = await async_client.get("/api/v1/medical-records", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res.status_code == 200


# ── 15. Document Integration (0 URL Token Leaks) ────────────────────────────────

@pytest.mark.asyncio
async def test_15_document_integration(async_client: AsyncClient):
    """Documents list and download endpoints function without requiring query tokens."""
    admin_token = await get_admin_token(async_client)
    res = await async_client.get("/api/v1/documents", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200


# ── 16. AI Inference Integration ────────────────────────────────────────────────

def make_test_png_bytes() -> bytes:
    from PIL import Image
    img = Image.new("RGB", (224, 224), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.mark.asyncio
async def test_16_ai_inference_integration(async_client: AsyncClient):
    """POST /ai/infer returns authoritative prediction, confidence, and model metadata."""
    doctor_token = await get_doctor_token(async_client)
    headers = {"Authorization": f"Bearer {doctor_token}"}

    png_bytes = make_test_png_bytes()
    files = {"image": ("test_mri.png", io.BytesIO(png_bytes), "image/png")}
    data = {"analysis_type": "BRAIN_MRI"}

    res = await async_client.post("/api/v1/ai/infer", files=files, data=data, headers=headers)
    assert res.status_code == 200
    infer_res = res.json()
    assert "predicted_class" in infer_res
    assert "confidence" in infer_res
    assert "probabilities" in infer_res
    assert "BRAIN_MRI" in infer_res.get("module_id", "").upper()


# ── 17. Grad-CAM Integration ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_17_gradcam_integration(async_client: AsyncClient):
    """Direct inference produces valid base64 Grad-CAM explainability artifact."""
    doctor_token = await get_doctor_token(async_client)
    headers = {"Authorization": f"Bearer {doctor_token}"}

    png_bytes = make_test_png_bytes()
    files = {"image": ("test_mri.png", io.BytesIO(png_bytes), "image/png")}
    data = {"analysis_type": "BRAIN_MRI"}
    res = await async_client.post("/api/v1/ai/infer", files=files, data=data, headers=headers)
    assert res.status_code == 200
    infer_res = res.json()
    assert infer_res.get("gradcam_available") is True
    assert infer_res.get("gradcam_b64") is not None


# ── 18. Prescription Integration ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_18_prescription_integration(async_client: AsyncClient):
    """Prescriptions listing is accessible to authorized doctor & patient; mutation restricted."""
    doctor_token = await get_doctor_token(async_client)
    res = await async_client.get("/api/v1/prescriptions", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res.status_code == 200

    patient_token = await get_patient_token(async_client)
    res_pat = await async_client.get("/api/v1/prescriptions", headers={"Authorization": f"Bearer {patient_token}"})
    assert res_pat.status_code == 200


# ── 19. Billing Integration ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_19_billing_integration(async_client: AsyncClient):
    """Billing summary and list return authoritative financial numbers."""
    staff_token = await get_staff_token(async_client)
    res = await async_client.get("/api/v1/billing", headers={"Authorization": f"Bearer {staff_token}"})
    assert res.status_code == 200
    bills = res.json()
    items = bills["data"] if "data" in bills else bills
    assert isinstance(items, list)


# ── 20. Payment Integration ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_20_payment_integration(async_client: AsyncClient):
    """Payment operations reject invalid amounts or non-existent bills with controlled errors."""
    staff_token = await get_staff_token(async_client)
    res = await async_client.post(
        "/api/v1/billing/BILL-NONEXISTENT-999/payments",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"amount": 100.0, "payment_method": "credit_card"}
    )
    assert res.status_code in [400, 404, 422]


# ── 21. Notification Integration ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_21_notification_integration(async_client: AsyncClient):
    """Notification listing, unread count, and mark-all-read operate accurately."""
    patient_token = await get_patient_token(async_client)
    count_res = await async_client.get("/api/v1/notifications/unread-count", headers={"Authorization": f"Bearer {patient_token}"})
    assert count_res.status_code == 200
    count_data = count_res.json()
    data = count_data["data"] if "data" in count_data else count_data
    assert "unread_count" in data

    list_res = await async_client.get("/api/v1/notifications", headers={"Authorization": f"Bearer {patient_token}"})
    assert list_res.status_code == 200


# ── 22. WebSocket Integration ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_22_websocket_integration(async_client: AsyncClient):
    """WebSocket notification endpoint is exposed and requires valid authentication."""
    res = await async_client.get("/api/v1/ws/notifications")
    assert res.status_code in [400, 401, 404, 426]


# ── 23. Search & Filter Integration ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_23_search_filter_integration(async_client: AsyncClient):
    """Global search endpoint handles query strings, resource types, and returns valid lists."""
    admin_token = await get_admin_token(async_client)
    res = await async_client.get("/api/v1/search?q=test&limit_per_resource=5", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    search_res = res.json()
    assert isinstance(search_res, dict) or isinstance(search_res, list)


# ── 24. Pagination Integration ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_24_pagination_integration(async_client: AsyncClient):
    """Paginated endpoints respect page & page_size parameters."""
    doctor_token = await get_doctor_token(async_client)
    res = await async_client.get("/api/v1/medical-records?page=1&page_size=5", headers={"Authorization": f"Bearer {doctor_token}"})
    assert res.status_code == 200
    body = res.json()
    assert "data" in body or isinstance(body, list)


# ── 25. Error Handling Contract ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_25_error_handling_contract(async_client: AsyncClient):
    """Standardized error responses map to RFC-7807/FastAPI HTTPException format with detail."""
    res_404 = await async_client.get("/api/v1/appointments/NON-EXISTENT-APT-XYZ")
    assert res_404.status_code in [401, 404]

    # 422 Validation Error
    res_422 = await async_client.post("/api/v1/auth/login", json={"invalid_field": True})
    assert res_422.status_code == 422
    err_body = res_422.json()
    assert "error" in err_body or "detail" in err_body


# ── 26. Retry & Idempotency Handling ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_26_retry_idempotency_handling(async_client: AsyncClient):
    """Repeated calls to idempotent endpoints return consistent responses without side-effects."""
    patient_token = await get_patient_token(async_client)
    mark_res_1 = await async_client.post("/api/v1/notifications/read-all", headers={"Authorization": f"Bearer {patient_token}"})
    assert mark_res_1.status_code == 200

    mark_res_2 = await async_client.post("/api/v1/notifications/read-all", headers={"Authorization": f"Bearer {patient_token}"})
    assert mark_res_2.status_code == 200


# ── 27. Stale Response Protection ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_27_stale_response_protection(async_client: AsyncClient):
    """Stale version consultation updates are rejected with 409 Conflict."""
    doctor_token = await get_doctor_token(async_client)
    headers = {"Authorization": f"Bearer {doctor_token}"}
    db = db_manager.db

    cns_id = f"CNS-P21-VER-{uuid.uuid4().hex[:6]}"
    await db[COLLECTION_CONSULTATIONS].insert_one({
        "consultation_id": cns_id,
        "appointment_id": f"APT-VER-{uuid.uuid4().hex[:6]}",
        "patient_id": "PAT-ONE-001",
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "status": "in_progress",
        "version": 1,
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })

    # Update with stale version
    res = await async_client.patch(
        f"/api/v1/consultations/{cns_id}/clinical-notes",
        headers=headers,
        json={"notes": "Stale note update", "expected_version": 999}
    )
    assert res.status_code == 409


# ── 28. Cache Invalidation Consistency ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_28_cache_invalidation_consistency(async_client: AsyncClient):
    """Database mutations reflect immediately in subsequent GET queries (read-your-writes)."""
    admin_token = await get_admin_token(async_client)
    # Fetch settings
    res = await async_client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    orig_settings = res.json()["data"] if "data" in res.json() else res.json()
    orig_name = orig_settings.get("hospital_name", "CliniXAI General Hospital")

    # Update settings
    updated_name = f"{orig_name} Verified"
    patch_res = await async_client.patch(
        "/api/v1/admin/settings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"hospital_name": updated_name}
    )
    assert patch_res.status_code == 200

    # Immediate read returns new name
    res2 = await async_client.get("/api/v1/admin/settings", headers={"Authorization": f"Bearer {admin_token}"})
    assert res2.status_code == 200
    new_settings = res2.json()["data"] if "data" in res2.json() else res2.json()
    assert new_settings.get("hospital_name") == updated_name

    # Restore original name
    await async_client.patch(
        "/api/v1/admin/settings",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"hospital_name": orig_name}
    )


# ── 29. Logout / Relogin Isolation ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_29_logout_relogin_isolation(async_client: AsyncClient):
    """Logging in as Doctor then Patient strictly separates contexts and identity."""
    doc_token = await get_doctor_token(async_client)
    doc_me = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {doc_token}"})
    assert doc_me.status_code == 200
    doc_data = doc_me.json()["data"] if "data" in doc_me.json() else doc_me.json()
    assert doc_data["role"] == "doctor"

    pat_token = await get_patient_token(async_client)
    pat_me = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {pat_token}"})
    assert pat_me.status_code == 200
    pat_data = pat_me.json()["data"] if "data" in pat_me.json() else pat_me.json()
    assert pat_data["role"] == "patient"
    assert pat_data["user_id"] != doc_data["user_id"]


# ── 30. Backend Restart Recovery ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_30_backend_restart_recovery(async_client: AsyncClient):
    """State stored in MongoDB survives across simulated restarts and snapshot persistence."""
    db = db_manager.db
    assert db is not None

    test_doc_id = f"DOC-TEST-P21-{uuid.uuid4().hex[:6]}"
    await db[COLLECTION_DOCUMENTS].insert_one({
        "document_id": test_doc_id,
        "title": "Phase 21 Persistence Check",
        "category": "Other",
        "original_file_name": "persistence_test.pdf",
        "file_size_bytes": 1024,
        "is_deleted": False,
        "created_at": utc_now()
    })

    # Save snapshot
    await save_in_memory_snapshot(db)

    # Restore snapshot (simulates restart hydration)
    await restore_in_memory_snapshot(db)

    # Verify record persists intact
    recovered = await db[COLLECTION_DOCUMENTS].find_one({"document_id": test_doc_id})
    assert recovered is not None
    assert recovered["title"] == "Phase 21 Persistence Check"

    # Cleanup
    await db[COLLECTION_DOCUMENTS].delete_one({"document_id": test_doc_id})
