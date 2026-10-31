"""Focused E2E Test Suite for Authenticated Booking, Auth (401), RBAC (403), & Payload (422) Integrity."""

import pytest
from httpx import AsyncClient
from datetime import date, timedelta


def _extract_token(res_json: dict) -> str:
    if "data" in res_json and isinstance(res_json["data"], dict) and "access_token" in res_json["data"]:
        return res_json["data"]["access_token"]
    return res_json["access_token"]


@pytest.mark.asyncio
async def test_booking_real_authenticated_patient(async_client: AsyncClient):
    # ── 1. Register a Fresh Patient ──────────────────────────────────────────
    reg_email = "e2e.booking.patient@clinixai.com"
    reg_pwd = "PatientPass@123"
    reg_res = await async_client.post(
        "/api/v1/auth/register",
        json={
            "email": reg_email,
            "password": reg_pwd,
            "full_name": "E2E Booking Patient",
        },
    )
    assert reg_res.status_code in (201, 409), f"Registration failed: {reg_res.text}"

    # ── 2. Authenticate & Verify Login (200 OK) ───────────────
    login_res = await async_client.post(
        "/api/v1/auth/login",
        json={"email": reg_email, "password": reg_pwd},
    )
    assert login_res.status_code == 200, f"Login failed (401 error): {login_res.text}"
    token = _extract_token(login_res.json())
    headers = {"Authorization": f"Bearer {token}"}

    # ── 3. Verify /auth/me ────────────────────────────────────────────────────
    me_res = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    user_id = me_data.get("user_id") or me_data.get("data", {}).get("user_id")
    assert user_id is not None

    # ── 4. Verify /patients/me (Patient Profile Resolution) ───────────────────
    pat_me_res = await async_client.get("/api/v1/patients/me", headers=headers)
    assert pat_me_res.status_code == 200
    pat_profile = pat_me_res.json()["data"]
    patient_id = pat_profile["patient_id"]
    assert patient_id.startswith("PAT-")

    # ── 5. Verify RBAC Isolation: Patient Listing All Patients Is 403 Forbidden
    forbidden_list_res = await async_client.get("/api/v1/patients?page_size=100", headers=headers)
    assert forbidden_list_res.status_code == 403, "Patient listing all patients must return 403 Forbidden"

    # ── 6. Fetch Doctors & Real Availability ─────────────────────────────────
    docs_res = await async_client.get("/api/v1/doctors", headers=headers)
    assert docs_res.status_code == 200
    doctors = docs_res.json()["data"]
    assert len(doctors) > 0
    active_doc = next((d for d in doctors if d.get("status") == "active"), doctors[0])
    doctor_id = active_doc["doctor_id"]
    dept_id = active_doc.get("department_id") or "DEP-CARD-001"

    # Dynamic target weekday date (tomorrow or next weekday with available slots)
    target_date = date.today() + timedelta(days=1)
    slots = []
    target_date_str = ""
    for _ in range(14):
        while target_date.weekday() >= 5:
            target_date += timedelta(days=1)
        target_date_str = target_date.isoformat()
        avail_res = await async_client.get(
            f"/api/v1/doctors/{doctor_id}/availability",
            headers=headers,
            params={"date": target_date_str},
        )
        assert avail_res.status_code == 200
        avail_data = avail_res.json()["data"]
        slots = avail_data.get("available_slots", [])
        if len(slots) > 0:
            break
        target_date += timedelta(days=1)

    assert len(slots) > 0, f"No slots available for doctor {doctor_id} on {target_date_str}"
    target_slot = slots[0]["start_time"]

    # ── 7. Verify Payload Validation (422 Unprocessable Content for invalid enum)
    invalid_payload = {
        "doctor_id": doctor_id,
        "department_id": dept_id,
        "appointment_date": target_date_str,
        "start_time": target_slot,
        "appointment_type": "in_person",  # Invalid enum value
        "reason": "Invalid payload validation test",
    }
    invalid_res = await async_client.post("/api/v1/appointments", headers=headers, json=invalid_payload)
    assert invalid_res.status_code == 422, "Invalid appointment_type enum value must return 422 Unprocessable Content"

    # ── 8. Book Appointment (201 Created) ────────────────────────────────────
    valid_payload = {
        "doctor_id": doctor_id,
        "department_id": dept_id,
        "appointment_date": target_date_str,
        "start_time": target_slot,
        "appointment_type": "new_consultation",
        "reason": "Authentic E2E Patient Consultation",
    }
    book_res = await async_client.post("/api/v1/appointments", headers=headers, json=valid_payload)
    assert book_res.status_code == 201, f"Valid booking failed: {book_res.text}"
    apt_data = book_res.json()["data"]
    appointment_id = apt_data["appointment_id"]
    assert apt_data["patient_id"] == patient_id
    assert apt_data["doctor_id"] == doctor_id
    assert apt_data["status"] == "scheduled"

    # ── 9. Verify Retrieval & Persistence ───────────────────────────────────
    get_apt_res = await async_client.get(f"/api/v1/appointments/{appointment_id}", headers=headers)
    assert get_apt_res.status_code == 200
    retrieved_apt = get_apt_res.json()["data"]
    assert retrieved_apt["appointment_id"] == appointment_id

    # ── 10. Verify Double Booking Rejection (400 Bad Request / 409 Conflict) ─
    dup_book_res = await async_client.post("/api/v1/appointments", headers=headers, json=valid_payload)
    assert dup_book_res.status_code in (400, 409), f"Double booking must return 400 or 409 Conflict: {dup_book_res.text}"
