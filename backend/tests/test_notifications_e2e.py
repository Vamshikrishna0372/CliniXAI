"""Comprehensive Production E2E Test Suite for CliniXAI Notifications, WebSocket, & Real-Time Synchronization."""

import pytest
from datetime import date, timedelta
from httpx import AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.core.security import create_access_token
from app.models.user import UserRole, AccountStatus


def _extract_token(response_json: dict) -> str:
    if "data" in response_json and "access_token" in response_json["data"]:
        return response_json["data"]["access_token"]
    if "access_token" in response_json:
        return response_json["access_token"]
    raise KeyError(f"access_token not found in response: {response_json}")


@pytest.mark.asyncio
async def test_notifications_websocket_and_persistence_e2e_pipeline(async_client: AsyncClient):
    """Verifies complete E2E notification lifecycle: auth, WS handshake, event dispatch, MongoDB persistence, read/unread status, and RBAC isolation."""
    # ── 1. Authenticate Patient & Doctor Roles ──────────────────────────────────────────
    pat_login_res = await async_client.post("/api/v1/auth/login", json={"email": "patient.one@clinixai.com", "password": "Patient@123"})
    assert pat_login_res.status_code == 200
    pat_token = _extract_token(pat_login_res.json())
    pat_headers = {"Authorization": f"Bearer {pat_token}"}

    pat_me = await async_client.get("/api/v1/auth/me", headers=pat_headers)
    assert pat_me.status_code == 200
    pat_data = pat_me.json().get("data", pat_me.json())
    pat_user_id = pat_data["user_id"]

    doc_login_res = await async_client.post("/api/v1/auth/login", json={"email": "doctor.arjun@clinixai.com", "password": "Doctor@123"})
    assert doc_login_res.status_code == 200
    doc_token = _extract_token(doc_login_res.json())
    doc_headers = {"Authorization": f"Bearer {doc_token}"}

    doc_me = await async_client.get("/api/v1/auth/me", headers=doc_headers)
    assert doc_me.status_code == 200
    doc_data = doc_me.json().get("data", doc_me.json())
    doc_user_id = doc_data["user_id"]

    # ── 2. Test WebSocket Handshake & Auth Protocols ──────────────────────────────────────
    sync_client = TestClient(app)

    # Query param token -> Rejected with 1008 (Phase 17 security requirement)
    with pytest.raises(WebSocketDisconnect) as exc_query:
        with sync_client.websocket_connect(f"/api/v1/notifications/ws?token={pat_token}") as ws:
            ws.receive_text()
    assert exc_query.value.code == 1008

    # Missing token / unauthenticated -> 1008
    with pytest.raises(WebSocketDisconnect) as exc_missing:
        with sync_client.websocket_connect("/api/v1/notifications/ws") as ws:
            ws.receive_text()
    assert exc_missing.value.code == 1008

    # Invalid token -> 1008
    with pytest.raises(WebSocketDisconnect) as exc_invalid:
        with sync_client.websocket_connect("/api/v1/notifications/ws", cookies={"access_token": "invalid_jwt"}) as ws:
            ws.receive_text()
    assert exc_invalid.value.code == 1008

    # Valid token via HttpOnly cookie -> Connects & responds to ping/pong
    with sync_client.websocket_connect("/api/v1/notifications/ws", cookies={"access_token": pat_token}) as pat_ws:
        pat_ws.send_text("ping")
        resp = pat_ws.receive_text()
        assert resp == "pong"

    # ── 3. Dispatch Business Events & Verify MongoDB Notification Creation ──────────────────
    # Action: Patient books appointment
    target_d = date.today()
    slots = []
    target_date = target_d.isoformat()
    for day_offset in range(14):
        candidate_d = target_d + timedelta(days=day_offset)
        avail_res = await async_client.get(
            "/api/v1/doctors/DOC-RAO-001/availability",
            headers=pat_headers,
            params={"date": candidate_d.isoformat()},
        )
        if avail_res.status_code == 200:
            avail_data = avail_res.json().get("data", {})
            found_slots = avail_data.get("available_slots", [])
            if found_slots:
                target_date = candidate_d.isoformat()
                slots = found_slots
                break
    assert len(slots) > 0, "No available slots found for DOC-RAO-001"
    slot_time = slots[0]["start_time"] if isinstance(slots[0], dict) else slots[0]

    book_res = await async_client.post(
        "/api/v1/appointments",
        headers=pat_headers,
        json={
            "doctor_id": "DOC-RAO-001",
            "department_id": "DEPT-CARD",
            "appointment_date": target_date,
            "start_time": slot_time,
            "appointment_type": "new_consultation",
            "reason": "E2E Notification Test Consultation",
        },
    )
    assert book_res.status_code in (200, 201), f"Booking failed: {book_res.text}"
    appt = book_res.json()["data"]
    appt_id = appt["appointment_id"]

    # Doctor checks inbox for appointment notification
    doc_inbox_res = await async_client.get("/api/v1/notifications", headers=doc_headers)
    assert doc_inbox_res.status_code == 200
    doc_notifs = doc_inbox_res.json()["data"]
    assert len(doc_notifs) > 0

    # ── 4. Verify Doctor Actions & Patient Notifications ─────────────────────────────────────
    # Doctor confirms appointment
    confirm_res = await async_client.post(f"/api/v1/appointments/{appt_id}/confirm", headers=doc_headers)
    assert confirm_res.status_code == 200

    # Ensure appointment_date matches today for clinical check-in validation rule
    from app.database.mongodb import db_manager
    await db_manager.db["appointments"].update_one(
        {"appointment_id": appt_id},
        {"$set": {"appointment_date": date.today().isoformat()}}
    )

    # Doctor checks in patient
    checkin_res = await async_client.post(f"/api/v1/appointments/{appt_id}/check-in", headers=doc_headers, json={"method": "manual"})
    assert checkin_res.status_code == 200

    # Doctor starts consultation
    start_con_res = await async_client.post("/api/v1/consultations/start", headers=doc_headers, json={"appointment_id": appt_id})
    assert start_con_res.status_code in (200, 201)
    consultation_id = start_con_res.json()["data"]["consultation_id"]

    # Record clinical assessment
    assess_res = await async_client.patch(
        f"/api/v1/consultations/{consultation_id}/assessment",
        headers=doc_headers,
        json={"assessment": {"summary": "E2E Notification Test Assessment Notes", "impression": "Stable", "risk_level": "low"}},
    )
    assert assess_res.status_code == 200

    # Record diagnoses
    diag_res = await async_client.patch(
        f"/api/v1/consultations/{consultation_id}/diagnoses",
        headers=doc_headers,
        json={"diagnoses": [{"name": "Tension Headache", "type": "primary", "code": "G44.2"}]},
    )
    assert diag_res.status_code == 200

    # Issue prescription
    rx_res = await async_client.post(
        f"/api/v1/prescriptions/consultation/{consultation_id}",
        headers=doc_headers,
        json={
            "medications": [{"name": "Paracetamol 500mg", "dosage": "1 tablet", "frequency": "Once daily", "duration": "3 days", "instructions": "After meals"}],
            "instructions": "Drink plenty of fluids.",
        },
    )
    assert rx_res.status_code in (200, 201)

    # Complete consultation (auto-generates bill + notifications)
    comp_res = await async_client.post(f"/api/v1/consultations/{consultation_id}/complete", headers=doc_headers)
    assert comp_res.status_code == 200

    # ── 5. Verify Patient Notification Inbox & Unread Count ─────────────────────────────────
    pat_inbox_res = await async_client.get("/api/v1/notifications", headers=pat_headers)
    assert pat_inbox_res.status_code == 200
    pat_notifs = pat_inbox_res.json()["data"]
    assert len(pat_notifs) > 0

    unread_res = await async_client.get("/api/v1/notifications/unread-count", headers=pat_headers)
    assert unread_res.status_code == 200
    unread_count = unread_res.json()["data"]["unread_count"]
    assert unread_count >= 1

    # ── 6. Test Mark Read, Mark All Read, and State Persistence ─────────────────────────────
    target_notif_id = pat_notifs[0]["notification_id"]

    # Mark single notification as read
    mark_read_res = await async_client.patch(f"/api/v1/notifications/{target_notif_id}/read", headers=pat_headers)
    assert mark_read_res.status_code == 200

    # Verify unread count decreased
    unread_after_one = await async_client.get("/api/v1/notifications/unread-count", headers=pat_headers)
    assert unread_after_one.json()["data"]["unread_count"] == unread_count - 1

    # Mark all notifications read
    mark_all_res = await async_client.patch("/api/v1/notifications/read-all", headers=pat_headers)
    assert mark_all_res.status_code == 200

    # Verify unread count is now 0
    unread_final = await async_client.get("/api/v1/notifications/unread-count", headers=pat_headers)
    assert unread_final.json()["data"]["unread_count"] == 0

    # ── 7. Verify RBAC Isolation & Cross-User Security ──────────────────────────────────────
    # Doctor attempts to mark patient's notification read -> 403 Forbidden
    forbidden_mark = await async_client.patch(f"/api/v1/notifications/{target_notif_id}/read", headers=doc_headers)
    assert forbidden_mark.status_code == 403

    # Doctor attempts to delete patient's notification -> 403 Forbidden
    forbidden_delete = await async_client.delete(f"/api/v1/notifications/{target_notif_id}", headers=doc_headers)
    assert forbidden_delete.status_code == 403

    # Patient deletes own notification -> 200 OK
    delete_res = await async_client.delete(f"/api/v1/notifications/{target_notif_id}", headers=pat_headers)
    assert delete_res.status_code == 200
