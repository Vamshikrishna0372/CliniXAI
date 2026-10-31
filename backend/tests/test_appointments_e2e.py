"""
Complete End-to-End Test Suite for CliniXAI Appointment Booking, Lifecycle Management,
Doctor Availability Calculation, Queue Integration, Consultation Linkage & MongoDB Persistence.
"""

import pytest
from httpx import AsyncClient
from datetime import date, timedelta

from app.utils.datetime import utc_now


async def get_patient_token(async_client: AsyncClient) -> str:
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "patient.one@clinixai.com",
        "password": "Patient@123",
    })
    assert res.status_code == 200, f"Patient login failed: {res.text}"
    body = res.json()
    return body["data"]["access_token"] if "data" in body else body["access_token"]


async def get_doctor_token(async_client: AsyncClient) -> str:
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "doctor.arjun@clinixai.com",
        "password": "Doctor@123",
    })
    assert res.status_code == 200, f"Doctor login failed: {res.text}"
    body = res.json()
    return body["data"]["access_token"] if "data" in body else body["access_token"]


async def get_admin_token(async_client: AsyncClient) -> str:
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "admin@clinixai.com",
        "password": "admin123",
    })
    assert res.status_code == 200, f"Admin login failed: {res.text}"
    body = res.json()
    return body["data"]["access_token"] if "data" in body else body["access_token"]


def get_next_weekday(start_offset: int = 1) -> str:
    """Helper to return an upcoming weekday (Mon-Fri) date string."""
    d = date.today() + timedelta(days=start_offset)
    while d.weekday() >= 5:  # 5 is Saturday, 6 is Sunday
        d += timedelta(days=1)
    return d.isoformat()


async def find_available_date_and_slot(async_client: AsyncClient, headers: dict, start_offset: int = 1):
    """Finds an upcoming weekday date and available slot for DOC-RAO-001."""
    d = date.today() + timedelta(days=start_offset)
    for _ in range(30):
        while d.weekday() >= 5:
            d += timedelta(days=1)
        target_date = d.isoformat()
        res = await async_client.get(
            "/api/v1/doctors/DOC-RAO-001/availability",
            headers=headers,
            params={"date": target_date}
        )
        if res.status_code == 200:
            slots = res.json().get("data", {}).get("available_slots", [])
            if len(slots) > 0:
                return target_date, slots[0]["start_time"]
        d += timedelta(days=1)
    raise RuntimeError("No available slots found within 30 days")


@pytest.mark.asyncio
async def test_doctor_availability(async_client: AsyncClient):
    """Test retrieving dynamic available time slots for a doctor on a scheduled clinic day."""
    pat_token = await get_patient_token(async_client)
    headers = {"Authorization": f"Bearer {pat_token}"}

    target_date, first_slot = await find_available_date_and_slot(async_client, headers, start_offset=1)
    res = await async_client.get(
        "/api/v1/doctors/DOC-RAO-001/availability",
        headers=headers,
        params={"date": target_date}
    )
    assert res.status_code == 200, f"Availability query failed: {res.text}"
    data = res.json()
    body = data["data"] if "data" in data else data
    assert body["doctor_id"] == "DOC-RAO-001"
    assert body["date"] == target_date
    assert len(body["available_slots"]) > 0
    assert ":" in first_slot


@pytest.mark.asyncio
async def test_appointment_booking_and_lifecycle_pipeline(async_client: AsyncClient):
    """Test full E2E appointment lifecycle: Book -> List (Patient, Doctor, Admin) -> Confirm -> Check-In -> Start Consultation -> Complete."""
    pat_token = await get_patient_token(async_client)
    doc_token = await get_doctor_token(async_client)
    admin_token = await get_admin_token(async_client)

    pat_headers = {"Authorization": f"Bearer {pat_token}"}
    doc_headers = {"Authorization": f"Bearer {doc_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    target_date, chosen_slot = await find_available_date_and_slot(async_client, pat_headers, start_offset=1)

    # 2. Patient books an appointment
    book_payload = {
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "appointment_date": target_date,
        "start_time": chosen_slot,
        "reason": "Brain MRI consultation follow-up",
        "appointment_type": "new_consultation"
    }
    book_res = await async_client.post("/api/v1/appointments", headers=pat_headers, json=book_payload)
    assert book_res.status_code == 201, f"Appointment booking failed: {book_res.text}"
    book_data = book_res.json()["data"]
    appointment_id = book_data["appointment_id"]
    assert appointment_id.startswith("APT-")
    assert book_data["doctor_id"] == "DOC-RAO-001"
    assert book_data["appointment_date"] == target_date
    assert book_data["start_time"] == chosen_slot

    # 3. Double-Booking Prevention Check: Attempt booking SAME slot again
    dup_res = await async_client.post("/api/v1/appointments", headers=pat_headers, json=book_payload)
    assert dup_res.status_code in {400, 409, 422}, f"Double booking was not prevented: {dup_res.text}"

    # 4. Verify Appointment Listing for Patient
    pat_list_res = await async_client.get("/api/v1/appointments", headers=pat_headers, params={"page_size": 100})
    assert pat_list_res.status_code == 200
    pat_items = pat_list_res.json()["data"]
    assert any(a["appointment_id"] == appointment_id for a in pat_items)

    # 5. Verify Appointment Listing for Doctor
    doc_list_res = await async_client.get("/api/v1/appointments", headers=doc_headers, params={"page_size": 100})
    assert doc_list_res.status_code == 200
    doc_items = doc_list_res.json()["data"]
    assert any(a["appointment_id"] == appointment_id for a in doc_items)

    # 6. Verify Appointment Listing for Admin
    admin_list_res = await async_client.get("/api/v1/appointments", headers=admin_headers, params={"page_size": 100})
    assert admin_list_res.status_code == 200
    admin_items = admin_list_res.json()["data"]
    assert any(a["appointment_id"] == appointment_id for a in admin_items)

    # 7. Doctor Confirms Appointment
    conf_res = await async_client.post(f"/api/v1/appointments/{appointment_id}/confirm", headers=doc_headers)
    assert conf_res.status_code == 200, f"Confirmation failed: {conf_res.text}"
    conf_data = conf_res.json()["data"]
    assert conf_data["status"] == "confirmed"

    # Set appointment_date to today so clinical check-in validation rule passes
    from app.database.mongodb import db_manager
    today_str = utc_now().date().isoformat()
    await db_manager.db["appointments"].update_one(
        {"appointment_id": appointment_id},
        {"$set": {"appointment_date": today_str}}
    )

    # 8. Check-In & Queue Workflow: Test on newly booked & confirmed appointment
    ci_res = await async_client.post(f"/api/v1/appointments/{appointment_id}/check-in", headers=doc_headers, json={"method": "manual"})
    assert ci_res.status_code == 200, f"Check-in failed: {ci_res.text}"
    ci_data = ci_res.json()["data"]
    assert ci_data["status"] in {"checked_in", "in_queue"}
    assert "queue" in ci_data and ci_data["queue"]["token_number"].startswith("A")

    # Verify Queue position endpoint
    q_pos_res = await async_client.get(f"/api/v1/appointments/{appointment_id}/queue-position", headers=pat_headers)
    assert q_pos_res.status_code == 200
    q_data = q_pos_res.json()["data"]
    assert q_data["token_number"] == ci_data["queue"]["token_number"]

    # 9. Doctor Starts Consultation linked to appointment
    start_cs_res = await async_client.post("/api/v1/consultations/start", headers=doc_headers, json={"appointment_id": appointment_id})
    assert start_cs_res.status_code == 201, f"Start consultation failed: {start_cs_res.text}"
    cs_data = start_cs_res.json()["data"]
    consultation_id = cs_data["consultation_id"]
    assert cs_data["appointment_id"] == appointment_id
    assert cs_data["doctor_id"] == "DOC-RAO-001"

    # 10. Record Doctor Clinical Assessment
    assess_res = await async_client.patch(
        f"/api/v1/consultations/{consultation_id}/assessment",
        headers=doc_headers,
        json={"assessment": {"summary": "Patient evaluated cleanly. Cardiac symptoms stable.", "risk_level": "low"}}
    )
    assert assess_res.status_code == 200, f"Clinical assessment recording failed: {assess_res.text}"

    # 11. Record Diagnosis
    diag_res = await async_client.patch(
        f"/api/v1/consultations/{consultation_id}/diagnoses",
        headers=doc_headers,
        json={"diagnoses": [{"name": "Stable Angina Follow-up", "type": "primary"}]}
    )
    assert diag_res.status_code == 200, f"Diagnoses recording failed: {diag_res.text}"

    # 12. Complete Consultation
    comp_cs_res = await async_client.post(
        f"/api/v1/consultations/{consultation_id}/complete",
        headers=doc_headers,
        json={"final_diagnosis": "No acute abnormality", "recommendations": "Annual follow-up"}
    )
    assert comp_cs_res.status_code == 200, f"Complete consultation failed: {comp_cs_res.text}"

    # 13. Verify Appointment Status transitions to COMPLETED
    detail_res = await async_client.get(f"/api/v1/appointments/{appointment_id}", headers=doc_headers)
    assert detail_res.status_code == 200
    detail_data = detail_res.json()["data"]
    assert detail_data["status"] == "completed"


@pytest.mark.asyncio
async def test_appointment_reschedule_and_cancel(async_client: AsyncClient):
    """Test rescheduling and cancelling appointments."""
    pat_token = await get_patient_token(async_client)
    headers = {"Authorization": f"Bearer {pat_token}"}

    target_date_1, slot_1 = await find_available_date_and_slot(async_client, headers, start_offset=3)
    target_date_2, slot_2 = await find_available_date_and_slot(async_client, headers, start_offset=6)

    # Book
    book_res = await async_client.post("/api/v1/appointments", headers=headers, json={
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "appointment_date": target_date_1,
        "start_time": slot_1,
        "reason": "Test reschedule appointment",
        "appointment_type": "new_consultation"
    })
    assert book_res.status_code == 201
    appointment_id = book_res.json()["data"]["appointment_id"]

    # Reschedule
    resched_res = await async_client.post(f"/api/v1/appointments/{appointment_id}/reschedule", headers=headers, json={
        "appointment_date": target_date_2,
        "start_time": slot_2,
        "reason": "Schedule conflict"
    })
    assert resched_res.status_code == 200, f"Reschedule failed: {resched_res.text}"
    resched_data = resched_res.json()["data"]
    assert resched_data["appointment_date"] == target_date_2
    assert resched_data["start_time"] == slot_2

    # Cancel
    cancel_res = await async_client.post(f"/api/v1/appointments/{appointment_id}/cancel", headers=headers, json={
        "reason": "Patient requested cancellation"
    })
    assert cancel_res.status_code == 200, f"Cancellation failed: {cancel_res.text}"
    cancel_data = cancel_res.json()["data"]
    assert cancel_data["status"] == "cancelled"
