"""
Phase 18: Staff Workflow — Production-Grade End-to-End Implementation Tests.
Validates the complete operational workflow for Reception / Front Desk / Hospital Staff:
1. Staff authentication & self profile (/staff/me)
2. Staff RBAC server-side enforcement (Staff, Patient, Doctor, Admin, Unauthenticated)
3. Operational Staff Dashboard metrics from real database (today's appointments, queue, pending bills, revenue)
4. Patient Search (multi-field: name, ID, phone, email, full name token matching, sensitive field protection)
5. Patient Registration support & duplicate prevention
6. Appointment Management & Check-in workflow (token generation, state advance, duplicate prevention, date validation)
7. Queue & Consultation Coordination (calling patient into consultation room, notification emission)
8. Billing & Payment recording (financial invariants: total = paid + balance, idempotency, duplicate prevention, receipts)
9. Concurrency & Idempotency safety
10. Realtime notification emission & WebSocket security
"""

import asyncio
import uuid
from datetime import datetime
import pytest
from httpx import AsyncClient

from app.utils.datetime import utc_now
from app.database.collections import (
    COLLECTION_APPOINTMENTS, COLLECTION_NOTIFICATIONS, COLLECTION_BILLING,
    COLLECTION_PATIENTS, COLLECTION_AUDIT_LOGS, COLLECTION_PAYMENTS
)
from app.database.mongodb import db_manager


# ── Helper Authentication Fixtures ─────────────────────────────────────────────

async def get_token_for(async_client: AsyncClient, email: str, password: str) -> str:
    res = await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    data = res.json()
    return data["data"]["access_token"] if "data" in data else data["access_token"]


async def get_staff_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "staff.one@clinixai.com", "Staff@123")


async def get_doctor_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "doctor.arjun@clinixai.com", "Doctor@123")


async def get_patient_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "patient.one@clinixai.com", "Patient@123")


async def get_admin_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "admin@clinixai.com", "admin123")


# ── 1. Staff Authentication & Profile Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_staff_authentication_and_profile(async_client: AsyncClient):
    """Staff can authenticate and view their assigned hospital profile."""
    token = await get_staff_token(async_client)
    headers = {"Authorization": f"Bearer {token}"}

    res = await async_client.get("/api/v1/staff/me", headers=headers)
    assert res.status_code == 200, f"Failed /staff/me: {res.text}"
    data = res.json()["data"]
    assert data["email"] == "staff.one@clinixai.com"
    assert "staff_id" in data
    assert data["status"] == "active"


# ── 2. Staff RBAC Boundaries Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_staff_rbac_boundaries(async_client: AsyncClient):
    """Verify strict server-side RBAC isolation across roles."""
    staff_token = await get_staff_token(async_client)
    patient_token = await get_patient_token(async_client)
    doctor_token = await get_doctor_token(async_client)

    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    patient_headers = {"Authorization": f"Bearer {patient_token}"}
    doctor_headers = {"Authorization": f"Bearer {doctor_token}"}

    # A. Staff can access staff dashboard overview
    res_staff = await async_client.get("/api/v1/staff/dashboard-overview", headers=staff_headers)
    assert res_staff.status_code == 200, f"Staff should access dashboard: {res_staff.text}"

    # B. Patient CANNOT access staff dashboard overview (403)
    res_pat = await async_client.get("/api/v1/staff/dashboard-overview", headers=patient_headers)
    assert res_pat.status_code == 403, f"Patient should be forbidden: {res_pat.text}"

    # C. Patient CANNOT access staff self profile (403)
    res_pat_me = await async_client.get("/api/v1/staff/me", headers=patient_headers)
    assert res_pat_me.status_code == 403

    # D. Doctor CANNOT access staff dashboard overview (403)
    res_doc = await async_client.get("/api/v1/staff/dashboard-overview", headers=doctor_headers)
    assert res_doc.status_code == 403

    # E. Unauthenticated request rejected (401)
    async_client.cookies.clear()
    res_unauth = await async_client.get("/api/v1/staff/dashboard-overview")
    assert res_unauth.status_code == 401

    # F. Staff CANNOT perform doctor clinical actions (e.g. create prescription -> 403)
    res_rx = await async_client.post("/api/v1/prescriptions", headers=staff_headers, json={
        "consultation_id": "CNS-TEST",
        "appointment_id": "APT-TEST",
        "patient_id": "PAT-ONE-001",
        "doctor_id": "DOC-RAO-001",
        "diagnosis": "Clinical attempt",
        "medications": [{"name": "Med", "strength": "10mg", "dosage": "1", "frequency": "Daily", "duration": "5 days"}]
    })
    assert res_rx.status_code == 403, f"Staff must not create prescriptions: {res_rx.text}"


# ── 3. Operational Staff Dashboard Real Data ───────────────────────────────────

@pytest.mark.asyncio
async def test_staff_dashboard_metrics_real_data(async_client: AsyncClient):
    """Staff dashboard returns real calculated metrics and lists from MongoDB."""
    token = await get_staff_token(async_client)
    headers = {"Authorization": f"Bearer {token}"}

    res = await async_client.get("/api/v1/staff/dashboard-overview", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]

    # Verify metrics structure
    metrics = data["metrics"]
    assert "today_appointments" in metrics
    assert "waiting_patients" in metrics
    assert "checked_in_today" in metrics
    assert "completed_consultations" in metrics
    assert "pending_bills" in metrics
    assert "today_collected_amount" in metrics
    assert "total_registered_patients" in metrics

    # Verify list sections exist
    assert isinstance(data["upcoming_appointments"], list)
    assert isinstance(data["active_queue"], list)
    assert isinstance(data["operational_alerts"], list)
    assert isinstance(data["recent_activity"], list)

    # Values must be non-negative real numbers
    assert metrics["today_appointments"] >= 0
    assert metrics["waiting_patients"] >= 0
    assert metrics["today_collected_amount"] >= 0.0
    assert metrics["total_registered_patients"] >= 0


# ── 4. Patient Search Multi-field & Protection ─────────────────────────────────

@pytest.mark.asyncio
async def test_staff_patient_search_and_data_privacy(async_client: AsyncClient):
    """Staff can search patients by name, ID, phone, email without exposing passwords/secrets."""
    token = await get_staff_token(async_client)
    headers = {"Authorization": f"Bearer {token}"}

    # Search by known ID
    res = await async_client.get("/api/v1/patients", headers=headers, params={"search": "PAT-ONE-001"})
    assert res.status_code == 200
    patients = res.json()["data"]
    assert len(patients) >= 1
    found = patients[0]
    assert found["patient_id"] == "PAT-ONE-001"

    # Data privacy: ensure no password hashes or sensitive authentication keys in payload
    assert "password_hash" not in found
    assert "hashed_password" not in found
    assert "auth_token" not in found

    # Search by name
    res_name = await async_client.get("/api/v1/patients", headers=headers, params={"search": found["first_name"]})
    assert res_name.status_code == 200
    assert len(res_name.json()["data"]) >= 1

    # Search by full name combined
    full_query = f"{found['first_name']} {found['last_name']}"
    res_full = await async_client.get("/api/v1/patients", headers=headers, params={"search": full_query})
    assert res_full.status_code == 200
    assert len(res_full.json()["data"]) >= 1


# ── 5. Patient Registration Support ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_staff_patient_registration_workflow(async_client: AsyncClient):
    """Staff registers walk-in patient, validates duplicate email prevention and input schemas."""
    token = await get_staff_token(async_client)
    headers = {"Authorization": f"Bearer {token}"}

    unique_email = f"walkin.{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "first_name": "Rohan",
        "last_name": "Verma",
        "email": unique_email,
        "phone": "+91 98765 99999",
        "date_of_birth": "1994-06-15",
        "gender": "male",
        "blood_group": "B+",
        "allergies": ["Penicillin"],
        "address": {
            "street": "123 MG Road",
            "city": "Bengaluru",
            "state": "Karnataka",
            "postal_code": "560001",
            "country": "India"
        },
        "emergency_contact": {
            "name": "Sunita Verma",
            "relationship": "Mother",
            "phone": "+91 98765 88888"
        }
    }

    # A. Successful registration
    res = await async_client.post("/api/v1/patients", headers=headers, json=payload)
    assert res.status_code in (200, 201), f"Patient registration failed: {res.text}"
    created = res.json()["data"]
    assert created["first_name"] == "Rohan"
    assert created["last_name"] == "Verma"
    assert created["patient_id"].startswith("PAT-")

    # B. Duplicate email rejected with 409 Conflict
    res_dup = await async_client.post("/api/v1/patients", headers=headers, json=payload)
    assert res_dup.status_code == 409, f"Expected 409 on duplicate email, got: {res_dup.text}"

    # C. Missing required first_name rejected with 422
    bad_payload = {**payload, "first_name": "", "email": "unique.new@example.com"}
    res_bad = await async_client.post("/api/v1/patients", headers=headers, json=bad_payload)
    assert res_bad.status_code in (400, 422)


# ── 6. Appointment Check-In Workflow & Prevention of Duplicates ────────────────

@pytest.mark.asyncio
async def test_staff_appointment_check_in_and_duplicate_prevention(async_client: AsyncClient):
    """Staff checks in patient, assigns queue token, advances status, and rejects duplicate check-ins."""
    staff_token = await get_staff_token(async_client)
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    today_str = datetime.now().date().isoformat()
    apt_id = f"APT-TEST-{uuid.uuid4().hex[:6]}"

    # Directly create confirmed appointment for today in DB with all required fields
    db = db_manager.db
    await db[COLLECTION_APPOINTMENTS].insert_one({
        "appointment_id": apt_id,
        "patient_id": "PAT-ONE-001",
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "appointment_date": today_str,
        "start_time": "11:00",
        "end_time": "11:30",
        "reason": "Chest Pain Evaluation",
        "appointment_type": "new_consultation",
        "status": "confirmed",
        "booking_source": "hospital_staff",
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })

    # A. Check-in patient
    ci_res = await async_client.post(
        f"/api/v1/appointments/{apt_id}/check-in",
        headers=staff_headers,
        json={"method": "manual"}
    )
    assert ci_res.status_code == 200, f"Check-in failed: {ci_res.text}"
    ci_data = ci_res.json()["data"]
    assert ci_data["status"] == "in_queue"
    assert "queue" in ci_data
    assert ci_data["queue"]["token_number"].startswith("A-")
    assert ci_data["queue"]["position"] >= 1
    assert "check_in" in ci_data
    assert ci_data["check_in"]["method"] == "manual"

    # B. Duplicate check-in on already checked-in appointment must be rejected (409 Conflict)
    dup_res = await async_client.post(
        f"/api/v1/appointments/{apt_id}/check-in",
        headers=staff_headers,
        json={"method": "manual"}
    )
    assert dup_res.status_code == 409, f"Expected 409 conflict on duplicate check-in, got {dup_res.text}"


# ── 7. Queue Flow & Doctor Coordination ────────────────────────────────────────

@pytest.mark.asyncio
async def test_queue_listing_and_calling_patient(async_client: AsyncClient):
    """Staff views live queue and coordinates consultation call with real notification dispatch."""
    staff_token = await get_staff_token(async_client)
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    today_str = datetime.now().date().isoformat()
    apt_id = f"APT-CALL-{uuid.uuid4().hex[:6]}"

    db = db_manager.db
    await db[COLLECTION_APPOINTMENTS].insert_one({
        "appointment_id": apt_id,
        "patient_id": "PAT-ONE-001",
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "appointment_date": today_str,
        "start_time": "12:00",
        "end_time": "12:30",
        "appointment_type": "new_consultation",
        "booking_source": "hospital_staff",
        "status": "in_queue",
        "queue": {"token_number": "A-999", "position": 1, "joined_at": utc_now()},
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })

    # A. Queue contains appointment
    q_res = await async_client.get(
        "/api/v1/appointments/queue",
        headers=staff_headers,
        params={"target_date_str": today_str}
    )
    assert q_res.status_code == 200
    q_items = q_res.json()["data"]
    assert any(item["appointment_id"] == apt_id for item in q_items)

    # B. Staff calls patient into consultation room
    call_res = await async_client.post(
        f"/api/v1/appointments/{apt_id}/call",
        headers=staff_headers,
    )
    assert call_res.status_code == 200, f"Call patient failed: {call_res.text}"
    called_apt = call_res.json()["data"]
    assert called_apt["status"] == "in_consultation"
    assert "called_at" in called_apt.get("queue", {})

    # C. Also verify the /call-patient alias route returns 400 when appointment is already in_consultation
    alias_res = await async_client.post(
        f"/api/v1/appointments/{apt_id}/call-patient",
        headers=staff_headers,
    )
    assert alias_res.status_code == 400, f"Repeated call must return 400, got: {alias_res.text}"

    # D. Verify alias route works on a fresh in_queue appointment (200)
    apt_id_2 = f"APT-CALL2-{uuid.uuid4().hex[:6]}"
    await db[COLLECTION_APPOINTMENTS].insert_one({
        "appointment_id": apt_id_2,
        "patient_id": "PAT-ONE-001",
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "appointment_date": today_str,
        "start_time": "12:30",
        "end_time": "13:00",
        "appointment_type": "new_consultation",
        "booking_source": "hospital_staff",
        "status": "in_queue",
        "queue": {"token_number": "A-998", "position": 2, "joined_at": utc_now()},
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })
    alias_res2 = await async_client.post(
        f"/api/v1/appointments/{apt_id_2}/call-patient",
        headers=staff_headers,
    )
    assert alias_res2.status_code == 200, f"Alias /call-patient failed: {alias_res2.text}"
    assert alias_res2.json()["data"]["status"] == "in_consultation"


# ── 8. Billing & Payment Invariants ────────────────────────────────────────────

@pytest.mark.asyncio
async def test_staff_billing_and_payment_invariants(async_client: AsyncClient):
    """Staff creates bill, issues, records payment; verifies financial invariants, idempotency, and receipts."""
    staff_token = await get_staff_token(async_client)
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # A. Staff creates a manual bill via API
    create_res = await async_client.post(
        "/api/v1/billing",
        headers=staff_headers,
        json={
            "patient_id": "PAT-ONE-001",
            "line_items": [
                {"item_code": "CONS-GEN", "description": "Consultation Fee", "quantity": 1, "unit_price": 1000.0}
            ],
            "notes": "Reception desk initial billing",
        }
    )
    assert create_res.status_code == 201, f"Create bill failed: {create_res.text}"
    bill_data = create_res.json()["data"]
    bill_id = bill_data["bill_id"]
    assert bill_data["grand_total"] == 1000.0
    assert bill_data["balance_due"] == 1000.0

    # B. Staff issues the bill
    issue_res = await async_client.post(f"/api/v1/billing/{bill_id}/issue", headers=staff_headers)
    assert issue_res.status_code == 200, f"Issue bill failed: {issue_res.text}"

    # C. Staff views bill details
    b_res = await async_client.get(f"/api/v1/billing/{bill_id}", headers=staff_headers)
    assert b_res.status_code == 200, f"Cannot view bill: {b_res.text}"
    issued_bill = b_res.json()["data"]
    assert issued_bill["grand_total"] == 1000.0
    assert issued_bill["balance_due"] == 1000.0
    assert issued_bill["paid_amount"] == 0.0

    # D. Staff records partial payment of ₹600 via UPI
    idempotency_key = f"IDEMP-{uuid.uuid4().hex}"
    pay_payload = {
        "amount": 600.0,
        "method": "upi",
        "reference_number": "UPI-REF-12345",
        "idempotency_key": idempotency_key,
        "notes": "Front desk counter collection"
    }

    pay_res = await async_client.post(
        f"/api/v1/billing/{bill_id}/payments",
        headers=staff_headers,
        json=pay_payload
    )
    assert pay_res.status_code == 200, f"Payment recording failed: {pay_res.text}"
    updated_bill = pay_res.json()["data"]

    # Invariant: grand_total == paid_amount + balance_due
    assert updated_bill["paid_amount"] == 600.0
    assert updated_bill["balance_due"] == 400.0
    assert updated_bill["grand_total"] == updated_bill["paid_amount"] + updated_bill["balance_due"]
    assert updated_bill["status"] == "partially_paid"

    # E. Duplicate payment with same idempotency key must not double-charge
    dup_pay = await async_client.post(
        f"/api/v1/billing/{bill_id}/payments",
        headers=staff_headers,
        json=pay_payload
    )
    assert dup_pay.status_code == 200
    dup_data = dup_pay.json()["data"]
    # Still paid 600, not 1200!
    assert dup_data["paid_amount"] == 600.0
    assert dup_data["balance_due"] == 400.0

    # F. Overpayment prevention (attempting to pay ₹500 when balance is ₹400 -> rejected)
    over_pay = await async_client.post(
        f"/api/v1/billing/{bill_id}/payments",
        headers=staff_headers,
        json={
            "amount": 500.0,
            "method": "cash",
            "idempotency_key": f"IDEMP-OVER-{uuid.uuid4().hex}"
        }
    )
    assert over_pay.status_code == 400, f"Overpayment should be rejected: {over_pay.text}"

    # G. Settle remainder ₹400
    settle_res = await async_client.post(
        f"/api/v1/billing/{bill_id}/payments",
        headers=staff_headers,
        json={
            "amount": 400.0,
            "method": "cash",
            "idempotency_key": f"IDEMP-FINAL-{uuid.uuid4().hex}"
        }
    )
    assert settle_res.status_code == 200
    settled_bill = settle_res.json()["data"]
    assert settled_bill["paid_amount"] == 1000.0
    assert settled_bill["balance_due"] == 0.0
    assert settled_bill["status"] == "paid"

    # H. Receipt access
    rcpt_res = await async_client.get(f"/api/v1/billing/{bill_id}/receipt", headers=staff_headers)
    assert rcpt_res.status_code == 200, f"Receipt access failed: {rcpt_res.text}"
    receipt = rcpt_res.json()["data"]
    assert receipt["bill_id"] == bill_id
    assert receipt["grand_total"] == 1000.0
    assert receipt["balance_due"] == 0.0
    assert receipt["amount_paid"] == 400.0
    assert receipt["receipt_id"].startswith("RCT-")


# ── 9. Concurrency & Idempotency Safety ────────────────────────────────────────

@pytest.mark.asyncio
async def test_concurrency_and_idempotency_safety(async_client: AsyncClient):
    """Concurrent check-in attempts from multiple staff members are safely serialized."""
    staff_token = await get_staff_token(async_client)
    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    today_str = datetime.now().date().isoformat()
    apt_id = f"APT-CONC-{uuid.uuid4().hex[:6]}"

    db = db_manager.db
    await db[COLLECTION_APPOINTMENTS].insert_one({
        "appointment_id": apt_id,
        "patient_id": "PAT-ONE-001",
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "appointment_date": today_str,
        "start_time": "14:00",
        "end_time": "14:30",
        "appointment_type": "new_consultation",
        "booking_source": "hospital_staff",
        "status": "confirmed",
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })

    # Fire 2 simultaneous check-in requests
    req1 = async_client.post(f"/api/v1/appointments/{apt_id}/check-in", headers=staff_headers, json={"method": "manual"})
    req2 = async_client.post(f"/api/v1/appointments/{apt_id}/check-in", headers=staff_headers, json={"method": "manual"})

    res1, res2 = await asyncio.gather(req1, req2)
    statuses = [res1.status_code, res2.status_code]

    # Exactly one must succeed (200), and the competing request must be rejected (409 Conflict)
    assert statuses.count(200) == 1, f"Expected exactly one 200, got: {statuses}"
    assert statuses.count(409) == 1, f"Expected exactly one 409 Conflict, got: {statuses}"

    # Verify MongoDB appointment document consistency
    final_doc = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": apt_id})
    assert final_doc["status"] == "in_queue"
    assert "token_number" in final_doc.get("queue", {})
    assert final_doc.get("check_in", {}).get("method") == "manual"


# ── 10. Staff Appointment Management & Filtering ──────────────────────────────

@pytest.mark.asyncio
async def test_staff_appointment_management_and_filters(async_client: AsyncClient):
    """Staff can list, search, and filter appointments by doctor, date, and status."""
    staff_token = await get_staff_token(async_client)
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    # List appointments as staff
    res = await async_client.get("/api/v1/appointments", headers=staff_headers, params={"page": 1, "page_size": 20})
    assert res.status_code == 200, f"Staff list appointments failed: {res.text}"
    data = res.json()
    assert "data" in data
    assert "pagination" in data
    assert isinstance(data["data"], list)

    # Filter by doctor
    res_doc = await async_client.get(
        "/api/v1/appointments",
        headers=staff_headers,
        params={"doctor_id": "DOC-RAO-001"}
    )
    assert res_doc.status_code == 200
    for apt in res_doc.json()["data"]:
        assert apt["doctor_id"] == "DOC-RAO-001"

    # Filter by date
    today_str = datetime.now().date().isoformat()
    res_date = await async_client.get(
        "/api/v1/appointments",
        headers=staff_headers,
        params={"date_from": today_str, "date_to": today_str}
    )
    assert res_date.status_code == 200


# ── 11. Staff Patient Update Support ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_staff_patient_update_workflow(async_client: AsyncClient):
    """Staff updates operational contact details for a patient."""
    staff_token = await get_staff_token(async_client)
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    update_payload = {
        "phone": "+91 91234 56789",
        "emergency_contact": {
            "name": "Updated Emergency Contact",
            "relationship": "Spouse",
            "phone": "+91 98888 77777"
        }
    }

    res = await async_client.patch(
        "/api/v1/patients/PAT-ONE-001",
        headers=staff_headers,
        json=update_payload
    )
    assert res.status_code == 200, f"Patient update failed: {res.text}"
    updated = res.json()["data"]
    assert updated["phone"] == "+91 91234 56789"
    assert updated["emergency_contact"]["name"] == "Updated Emergency Contact"


# ── 12. Staff Operational Search ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_staff_operational_search(async_client: AsyncClient):
    """Staff global operational search for patients and resources."""
    staff_token = await get_staff_token(async_client)
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    res = await async_client.get("/api/v1/search", headers=staff_headers, params={"q": "PAT-ONE-001"})
    assert res.status_code == 200
    results = res.json()
    assert "patients" in results or "results" in results or "total_matches" in results

    # Ensure search results do not expose password hashes
    raw_text = res.text
    assert "password_hash" not in raw_text
    assert "hashed_password" not in raw_text


# ── 13. Staff Action Audit Trail & Notifications ──────────────────────────────

@pytest.mark.asyncio
async def test_staff_audit_trail_and_notifications(async_client: AsyncClient):
    """Verifies that operational staff actions generate persistent audit logs and notifications."""
    staff_token = await get_staff_token(async_client)
    staff_headers = {"Authorization": f"Bearer {staff_token}"}

    today_str = datetime.now().date().isoformat()
    apt_id = f"APT-AUDIT-{uuid.uuid4().hex[:6]}"

    db = db_manager.db
    await db[COLLECTION_APPOINTMENTS].insert_one({
        "appointment_id": apt_id,
        "patient_id": "PAT-ONE-001",
        "doctor_id": "DOC-RAO-001",
        "department_id": "DEPT-CARD",
        "appointment_date": today_str,
        "start_time": "15:00",
        "end_time": "15:30",
        "appointment_type": "new_consultation",
        "booking_source": "hospital_staff",
        "status": "confirmed",
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })

    # Staff checks in patient
    res_ci = await async_client.post(
        f"/api/v1/appointments/{apt_id}/check-in",
        headers=staff_headers,
        json={"method": "manual"}
    )
    assert res_ci.status_code == 200

    # Verify notification created for patient
    notif = await db[COLLECTION_NOTIFICATIONS].find_one({
        "reference_id": apt_id,
        "type": "checkin_success"
    })
    assert notif is not None
    assert notif["recipient_user_id"] == "USR-PAT-ONE-001"
    assert "Token" in notif["body"]

    # Verify audit log recorded for appointment check-in
    audit = await db[COLLECTION_AUDIT_LOGS].find_one({
        "resource_id": apt_id,
        "action": {"$regex": "check.*in", "$options": "i"}
    })
    assert audit is not None, f"Audit log must be recorded in MongoDB for check-in on {apt_id}"
    assert audit["resource_id"] == apt_id
    assert audit["action"] == "appointment_check_in"


# ── 14. Comprehensive Staff Security & IDOR Matrix ────────────────────────────

@pytest.mark.asyncio
async def test_staff_security_and_idor_matrix(async_client: AsyncClient):
    """Comprehensive verification of RBAC, IDOR protection, and authentication boundaries."""
    staff_token = await get_staff_token(async_client)
    patient_token = await get_patient_token(async_client)
    doctor_token = await get_doctor_token(async_client)
    admin_token = await get_admin_token(async_client)

    staff_headers = {"Authorization": f"Bearer {staff_token}"}
    patient_headers = {"Authorization": f"Bearer {patient_token}"}
    doctor_headers = {"Authorization": f"Bearer {doctor_token}"}
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Unauthenticated request to /staff/dashboard-overview -> 401
    async_client.cookies.clear()
    res_unauth = await async_client.get("/api/v1/staff/dashboard-overview")
    assert res_unauth.status_code == 401

    # 2. Patient attempting to access /staff/dashboard-overview -> 403
    res_pat_dash = await async_client.get("/api/v1/staff/dashboard-overview", headers=patient_headers)
    assert res_pat_dash.status_code == 403

    # 3. Doctor attempting to access /staff/dashboard-overview -> 403
    res_doc_dash = await async_client.get("/api/v1/staff/dashboard-overview", headers=doctor_headers)
    assert res_doc_dash.status_code == 403

    # 4. Admin CAN access staff dashboard overview -> 200
    res_adm_dash = await async_client.get("/api/v1/staff/dashboard-overview", headers=admin_headers)
    assert res_adm_dash.status_code == 200

    # 5. Staff attempting to access admin-only settings -> 403
    res_staff_admin = await async_client.get("/api/v1/admin/summary", headers=staff_headers)
    assert res_staff_admin.status_code == 403

    # 6. Non-existent appointment check-in returns 404
    res_not_found = await async_client.post(
        "/api/v1/appointments/APT-NONEXISTENT-999999/check-in",
        headers=staff_headers,
        json={"method": "manual"}
    )
    assert res_not_found.status_code == 404

    # 7. Non-existent bill payment returns 404
    res_bill_404 = await async_client.post(
        "/api/v1/billing/BILL-NONEXISTENT-999999/payments",
        headers=staff_headers,
        json={"amount": 100.0, "method": "cash"}
    )
    assert res_bill_404.status_code == 404

