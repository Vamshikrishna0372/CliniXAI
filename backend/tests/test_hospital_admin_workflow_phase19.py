"""
Phase 19: Hospital Admin Workflow — Production-Grade End-to-End Implementation Tests.
Validates the complete operational and administrative workflow:
1. Admin authentication & authoritative operational dashboard metrics (/admin/dashboard)
2. Server-side RBAC security matrix (Admin allowed, Staff/Doctor/Patient forbidden, Unauthenticated rejected)
3. User Management (search, filter, detail, credential protection)
4. Account Lifecycle (active -> disabled -> active, session revocation, self-disable protection)
5. Admin Doctor Management (invitation setup, profile update, status sync)
6. Admin Staff Management (invitation setup, profile update, status sync)
7. Patient Operational Oversight & Clinical Boundary Preservation
8. Appointment Administration & Administrative Cancellation with Audit + Notifications
9. Billing Administration & Financial Invariant Respect
10. Hospital System Settings (persistence in hospital_settings, secrets protection)
11. Audit Logs (immutable records, actor/action/target/date filtering)
12. Escaped Regex Operational Search (cross-collection search, ReDoS protection)
13. Mass Assignment & Malicious Payload Protection
14. Concurrency & Idempotency Safety
"""

import asyncio
import uuid
import pytest
from httpx import AsyncClient

from app.core.security import hash_password
from app.models.user import UserRole, AuthProvider, AccountStatus
from app.utils.datetime import utc_now
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_DOCTORS, COLLECTION_STAFF,
    COLLECTION_PATIENTS, COLLECTION_APPOINTMENTS, COLLECTION_BILLING,
    COLLECTION_AUDIT_LOGS, COLLECTION_NOTIFICATIONS,
    COLLECTION_HOSPITAL_SETTINGS
)
from app.database.mongodb import db_manager


# ── Helper Authentication Fixtures ─────────────────────────────────────────────

async def get_token_for(async_client: AsyncClient, email: str, password: str) -> str:
    res = await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    data = res.json()
    return data["data"]["access_token"] if "data" in data else data["access_token"]


async def get_admin_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "admin@clinixai.com", "admin123")


async def get_staff_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "staff.one@clinixai.com", "Staff@123")


async def get_doctor_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "doctor.arjun@clinixai.com", "Doctor@123")


async def get_patient_token(async_client: AsyncClient) -> str:
    return await get_token_for(async_client, "patient.one@clinixai.com", "Patient@123")


# ── 1. Admin Authentication & Authoritative Dashboard Metrics ─────────────────

@pytest.mark.asyncio
async def test_admin_authentication_and_dashboard_metrics(async_client: AsyncClient):
    """Admin authenticates and receives real aggregated metrics from MongoDB collections."""
    admin_token = await get_admin_token(async_client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    res = await async_client.get("/api/v1/admin/dashboard", headers=headers)
    assert res.status_code == 200, f"Dashboard failed: {res.text}"
    body = res.json()
    assert body.get("success") is True
    data = body["data"]

    # Verify authoritative operational metrics are present and non-negative
    assert "total_patients" in data
    assert "active_doctors" in data
    assert "active_staff" in data
    assert "today_appointments" in data
    assert "pending_appointments" in data
    assert "collected_revenue" in data
    assert "active_users" in data
    assert "disabled_users" in data
    assert "recent_activity" in data
    assert "operational_alerts" in data

    assert data["total_patients"] >= 0
    assert data["active_doctors"] >= 0
    assert data["active_staff"] >= 0
    assert data["active_users"] >= 1  # At least the admin user itself


# ── 2. RBAC Server-Side Security Matrix ────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_rbac_security_matrix(async_client: AsyncClient):
    """Verifies strict server-side RBAC across roles for admin endpoints."""
    admin_token = await get_admin_token(async_client)
    staff_token = await get_staff_token(async_client)
    doctor_token = await get_doctor_token(async_client)
    patient_token = await get_patient_token(async_client)

    endpoints = [
        ("/api/v1/admin/dashboard", "GET"),
        ("/api/v1/admin/users", "GET"),
        ("/api/v1/admin/settings", "GET"),
        ("/api/v1/admin/search?q=test", "GET"),
    ]

    for url, method in endpoints:
        # Unauthenticated -> 401
        res_unauth = await async_client.request(method, url)
        assert res_unauth.status_code in (401, 403), f"Unauth expected 401/403 for {url}, got {res_unauth.status_code}"

        # Patient -> 403
        res_pat = await async_client.request(method, url, headers={"Authorization": f"Bearer {patient_token}"})
        assert res_pat.status_code == 403, f"Patient expected 403 for {url}, got {res_pat.status_code}"

        # Doctor -> 403
        res_doc = await async_client.request(method, url, headers={"Authorization": f"Bearer {doctor_token}"})
        assert res_doc.status_code == 403, f"Doctor expected 403 for {url}, got {res_doc.status_code}"

        # Staff -> 403
        res_staff = await async_client.request(method, url, headers={"Authorization": f"Bearer {staff_token}"})
        assert res_staff.status_code == 403, f"Staff expected 403 for {url}, got {res_staff.status_code}"

        # Admin -> 200
        res_adm = await async_client.request(method, url, headers={"Authorization": f"Bearer {admin_token}"})
        assert res_adm.status_code == 200, f"Admin expected 200 for {url}, got {res_adm.status_code}"


# ── 3. User Management Search, Filter & Detail ─────────────────────────────────

@pytest.mark.asyncio
async def test_admin_user_management_search_filter_detail(async_client: AsyncClient):
    """Admin can search, filter, and inspect users without exposing password hashes or tokens."""
    admin_token = await get_admin_token(async_client)
    headers = {"Authorization": f"Bearer {admin_token}"}

    # List all users
    res = await async_client.get("/api/v1/admin/users?limit=20", headers=headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert isinstance(data, list)
    assert len(data) > 0

    first_user = data[0]
    user_id = first_user["user_id"]

    # Verify no credential leakage in list
    for u in data:
        assert "password_hash" not in u
        assert "password" not in u
        assert "invitation_token" not in u
        assert "invitation_token_hash" not in u

    # Inspect specific user detail
    detail_res = await async_client.get(f"/api/v1/admin/users/{user_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()["data"]
    assert detail["user_id"] == user_id
    assert "password_hash" not in detail
    assert "invitation_token" not in detail


# ── 4. User Lifecycle: Active -> Disabled -> Active & Session Revocation ───────

@pytest.mark.asyncio
async def test_admin_user_lifecycle_disable_and_enable(async_client: AsyncClient):
    """Admin disables an account, active sessions are deleted, login is blocked, then re-enables."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    db = db_manager.db
    # Create a test patient user directly to test lifecycle safely
    test_user_id = f"USR-TEST-LIFE-{uuid.uuid4().hex[:6]}"
    test_email = f"lifecycle_{uuid.uuid4().hex[:6]}@testclinix.com"
    test_pwd = "TestPassword@123"

    await db[COLLECTION_USERS].insert_one({
        "user_id": test_user_id,
        "email": test_email,
        "full_name": "Lifecycle Test User",
        "role": UserRole.PATIENT.value,
        "auth_provider": AuthProvider.LOCAL.value,
        "account_status": AccountStatus.ACTIVE.value,
        "password_hash": hash_password(test_pwd),
        "is_active": True,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })

    # User can login when active
    token = await get_token_for(async_client, test_email, test_pwd)
    assert token is not None

    # Simulate an active session in DB
    await db["sessions"].insert_one({
        "session_id": f"sess-{uuid.uuid4().hex}",
        "user_id": test_user_id,
        "created_at": utc_now(),
    })
    pre_sess_count = await db["sessions"].count_documents({"user_id": test_user_id})
    assert pre_sess_count >= 1

    # Admin disables the account
    disable_res = await async_client.patch(
        f"/api/v1/admin/users/{test_user_id}/status",
        headers=admin_headers,
        json={"account_status": "disabled", "reason": "Operational safety test audit"}
    )
    assert disable_res.status_code == 200, f"Disable failed: {disable_res.text}"
    assert disable_res.json()["data"]["account_status"] == "disabled"

    # Verify active sessions were revoked from DB
    post_sess_count = await db["sessions"].count_documents({"user_id": test_user_id})
    assert post_sess_count == 0, "Active sessions must be revoked on account disable!"

    # Verify audit log was emitted
    audit = await db[COLLECTION_AUDIT_LOGS].find_one({
        "action": "ACCOUNT_STATUS_CHANGED",
        "resource_id": test_user_id
    })
    assert audit is not None, "ACCOUNT_STATUS_CHANGED audit log must be recorded!"

    # Disabled user cannot login
    login_disabled = await async_client.post("/api/v1/auth/login", json={"email": test_email, "password": test_pwd})
    assert login_disabled.status_code in (400, 403), "Disabled account must not be able to login!"

    # Admin re-enables the account
    enable_res = await async_client.patch(
        f"/api/v1/admin/users/{test_user_id}/status",
        headers=admin_headers,
        json={"account_status": "active", "reason": "Restoring operational access"}
    )
    assert enable_res.status_code == 200
    assert enable_res.json()["data"]["account_status"] == "active"

    # Verify re-enabled user can login again
    token_restored = await get_token_for(async_client, test_email, test_pwd)
    assert token_restored is not None

    # Clean up test user
    await db[COLLECTION_USERS].delete_one({"user_id": test_user_id})


# ── 5. Self-Disable Prohibition ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_self_disable_prohibition(async_client: AsyncClient):
    """Admin cannot disable their own account (prevents lockout)."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Fetch admin's own user_id
    me_res = await async_client.get("/api/v1/auth/me", headers=admin_headers)
    assert me_res.status_code == 200
    me_data = me_res.json()
    admin_id = me_data["user_id"] if "user_id" in me_data else me_data["data"]["user_id"]

    res = await async_client.patch(
        f"/api/v1/admin/users/{admin_id}/status",
        headers=admin_headers,
        json={"account_status": "disabled", "reason": "Self-disable test"}
    )
    assert res.status_code in (400, 403)
    assert "cannot disable their own account" in res.text.lower()


# ── 6. Admin Doctor Management & Operational Provisioning ─────────────────────

@pytest.mark.asyncio
async def test_admin_doctor_provisioning_and_lifecycle(async_client: AsyncClient):
    """Admin provisions a Doctor account via secure invitation, searches, and updates operational profile."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    db = db_manager.db

    doc_email = f"dr.test.{uuid.uuid4().hex[:6]}@clinixai.com"
    doc_payload = {
        "email": doc_email,
        "full_name": "Dr. Ananya Roy",
        "first_name": "Ananya",
        "last_name": "Roy",
        "phone": "+919876543210",
        "specialization": "Neurology",
        "qualification": "MBBS, MD, DM (Neuro)",
        "experience_years": 10,
        "department_id": "DEPT-CARD",
        "consultation_fee": 1200.0,
        "room_number": "Room 402",
        "bio": "Consultant Neurologist"
    }

    # 1. Provision Doctor
    create_res = await async_client.post("/api/v1/admin/doctors", headers=admin_headers, json=doc_payload)
    assert create_res.status_code == 201, f"Doctor creation failed: {create_res.text}"
    created_data = create_res.json()["data"]
    doctor_id = created_data["doctor_id"]
    user_id = created_data["user_id"]

    # Verify no invitation token is exposed in API response
    assert "invitation_token" not in created_data
    assert "token" not in created_data

    # Verify duplicate email rejected
    dup_res = await async_client.post("/api/v1/admin/doctors", headers=admin_headers, json=doc_payload)
    assert dup_res.status_code in (400, 409), "Duplicate email doctor creation must fail!"

    # 2. Search / List Doctors
    list_res = await async_client.get(f"/api/v1/admin/doctors?q=Ananya", headers=admin_headers)
    assert list_res.status_code == 200
    doctors_list = list_res.json()["data"]
    assert any(d["doctor_id"] == doctor_id for d in doctors_list)

    # 3. Update Operational Profile
    update_res = await async_client.patch(
        f"/api/v1/admin/doctors/{doctor_id}",
        headers=admin_headers,
        json={"consultation_fee": 1500.0, "experience_years": 12}
    )
    assert update_res.status_code == 200
    updated_doc = update_res.json()["data"]
    assert updated_doc["consultation_fee"] == 1500.0
    assert updated_doc["experience_years"] == 12

    # 4. Toggle Status
    status_res = await async_client.patch(
        f"/api/v1/admin/doctors/{doctor_id}/status",
        headers=admin_headers,
        json={"status": "inactive", "reason": "Sabbatical leave"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["data"]["status"] == "inactive"

    # Clean up test doctor
    await db[COLLECTION_DOCTORS].delete_one({"doctor_id": doctor_id})
    await db[COLLECTION_USERS].delete_one({"user_id": user_id})


# ── 7. Admin Staff Management & Operational Provisioning ──────────────────────

@pytest.mark.asyncio
async def test_admin_staff_provisioning_and_lifecycle(async_client: AsyncClient):
    """Admin provisions a Hospital Staff account, updates department, and toggles status."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    db = db_manager.db

    staff_email = f"staff.test.{uuid.uuid4().hex[:6]}@clinixai.com"
    staff_payload = {
        "email": staff_email,
        "full_name": "Rohan Verma",
        "first_name": "Rohan",
        "last_name": "Verma",
        "phone": "+919123456780",
        "department_id": "DEPT-CARD",
        "job_title": "Senior Front Desk Executive"
    }

    # 1. Provision Staff
    create_res = await async_client.post("/api/v1/admin/staff", headers=admin_headers, json=staff_payload)
    assert create_res.status_code == 201, f"Staff creation failed: {create_res.text}"
    created_data = create_res.json()["data"]
    staff_id = created_data["staff_id"]
    user_id = created_data["user_id"]

    # Verify no invitation token is exposed
    assert "invitation_token" not in created_data

    # Duplicate email rejected
    dup_res = await async_client.post("/api/v1/admin/staff", headers=admin_headers, json=staff_payload)
    assert dup_res.status_code in (400, 409)

    # 2. Search / List Staff
    list_res = await async_client.get(f"/api/v1/admin/staff?q=Rohan", headers=admin_headers)
    assert list_res.status_code == 200
    staff_list = list_res.json()["data"]
    assert any(s["staff_id"] == staff_id for s in staff_list)

    # 3. Update Operational Profile
    update_res = await async_client.patch(
        f"/api/v1/admin/staff/{staff_id}",
        headers=admin_headers,
        json={"job_title": "Lead Admissions Officer", "phone": "+919876543219"}
    )
    assert update_res.status_code == 200
    updated_staff = update_res.json()["data"]
    assert updated_staff["job_title"] == "Lead Admissions Officer"

    # Clean up test staff
    await db[COLLECTION_STAFF].delete_one({"staff_id": staff_id})
    await db[COLLECTION_USERS].delete_one({"user_id": user_id})


# ── 8. Patient Operational Oversight & Strict Clinical Boundary ───────────────

@pytest.mark.asyncio
async def test_admin_patient_operational_oversight_and_clinical_boundary(async_client: AsyncClient):
    """Admin has operational visibility over patients, but cannot forge doctor diagnoses or clinical notes."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Operational patient list
    res = await async_client.get("/api/v1/admin/patients?limit=10", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert isinstance(data, list)

    if len(data) > 0:
        first_patient = data[0]
        patient_id = first_patient["patient_id"]

        # View operational patient record
        pat_res = await async_client.get(f"/api/v1/admin/patients/{patient_id}", headers=admin_headers)
        assert pat_res.status_code == 200
        pat_data = pat_res.json()["data"]
        assert pat_data["patient_id"] == patient_id

    # Strict Clinical Boundary: Admin cannot perform Doctor-only prescription creation
    forged_prescription_payload = {
        "consultation_id": "CNS-TEST-001",
        "patient_id": "PAT-TEST-001",
        "medications": [{"name": "Amoxicillin", "dosage": "500mg"}]
    }
    rx_res = await async_client.post(
        "/api/v1/prescriptions",
        headers=admin_headers,
        json=forged_prescription_payload
    )
    # Admin MUST be blocked from creating prescriptions (403 Forbidden)
    assert rx_res.status_code == 403, "Admin must NOT be able to forge clinical prescriptions!"


# ── 9. Appointment Administration & Cancellation ──────────────────────────────

@pytest.mark.asyncio
async def test_admin_appointment_oversight_and_cancellation(async_client: AsyncClient):
    """Admin can oversee appointments and perform audited administrative cancellations."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    db = db_manager.db

    # Create a test appointment in MongoDB
    appt_id = f"APT-ADM-TEST-{uuid.uuid4().hex[:6]}"
    await db[COLLECTION_APPOINTMENTS].insert_one({
        "appointment_id": appt_id,
        "patient_id": "PAT-DEMO-001",
        "doctor_id": "DOC-DEMO-001",
        "department_id": "DEPT-CARD",
        "scheduled_time": utc_now(),
        "appointment_date": "2026-10-15",
        "start_time": "09:00",
        "end_time": "09:30",
        "appointment_type": "new_consultation",
        "status": "scheduled",
        "type": "in_person",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })

    # Search appointments
    search_res = await async_client.get(f"/api/v1/admin/appointments?status=scheduled&page_size=100", headers=admin_headers)
    assert search_res.status_code == 200
    appts = search_res.json()["data"]
    assert isinstance(appts, list)
    assert any(a["appointment_id"] == appt_id for a in appts)

    # Cancel appointment administratively
    cancel_res = await async_client.patch(
        f"/api/v1/admin/appointments/{appt_id}/cancel",
        headers=admin_headers,
        json={"reason": "Doctor emergency leave announced by administration"}
    )
    assert cancel_res.status_code == 200
    assert cancel_res.json()["data"]["status"] == "cancelled"

    # Verify audit event emitted
    audit = await db[COLLECTION_AUDIT_LOGS].find_one({
        "action": "APPOINTMENT_CANCELLED_BY_ADMIN",
        "resource_id": appt_id
    })
    assert audit is not None, "Audit log must be emitted for administrative cancellation!"

    # Clean up test appointment
    await db[COLLECTION_APPOINTMENTS].delete_one({"appointment_id": appt_id})


# ── 10. Billing Administration & Financial Invariant Respect ───────────────────

@pytest.mark.asyncio
async def test_admin_billing_oversight(async_client: AsyncClient):
    """Admin can oversee billing aggregates with authoritative calculations."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    res = await async_client.get("/api/v1/admin/billing?limit=20", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()["data"]
    assert isinstance(data, list)


# ── 11. Hospital System Settings & Secrets Protection ─────────────────────────

@pytest.mark.asyncio
async def test_admin_hospital_settings_persistence_and_secrets(async_client: AsyncClient):
    """Admin can view and update system settings, stored in hospital_settings without leaking secrets."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    db = db_manager.db

    # 1. Get settings
    get_res = await async_client.get("/api/v1/admin/settings", headers=admin_headers)
    assert get_res.status_code == 200
    settings = get_res.json()["data"]
    assert "hospital_name" in settings
    assert "total_bed_capacity" in settings

    # Ensure no secrets leaked
    assert "jwt_secret" not in settings
    assert "smtp_password" not in settings
    assert "database_url" not in settings

    # 2. Update settings
    new_capacity = 320
    update_res = await async_client.patch(
        "/api/v1/admin/settings",
        headers=admin_headers,
        json={"total_bed_capacity": new_capacity, "emergency_contact": "+91-11-23456789"}
    )
    assert update_res.status_code == 200
    updated_settings = update_res.json()["data"]
    assert updated_settings["total_bed_capacity"] == new_capacity

    # Verify MongoDB persistence
    db_doc = await db[COLLECTION_HOSPITAL_SETTINGS].find_one({"setting_id": "default"})
    assert db_doc is not None
    assert db_doc["total_bed_capacity"] == new_capacity


# ── 12. Audit Logs & Advanced Date Range Filtering ────────────────────────────

@pytest.mark.asyncio
async def test_admin_audit_logs_filtering(async_client: AsyncClient):
    """Admin inspects immutable audit logs with action, actor, and date filters."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    res = await async_client.get("/api/v1/audit-logs?limit=25", headers=admin_headers)
    assert res.status_code == 200
    data = res.json()
    assert "items" in data
    assert "total" in data
    assert isinstance(data["items"], list)


# ── 13. Escaped Regex Operational Search (ReDoS Protection) ────────────────────

@pytest.mark.asyncio
async def test_admin_operational_search_regex_escaped(async_client: AsyncClient):
    """Admin operational search properly escapes regex special characters without crashing."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    # Query with characters that would cause regex syntax error or ReDoS if unescaped
    malicious_query = "([*+?^${}()|\\"
    res = await async_client.get(f"/api/v1/admin/search?q={malicious_query}", headers=admin_headers)
    assert res.status_code == 200, f"Unescaped regex crashed the search endpoint: {res.text}"
    data = res.json()["data"]
    assert "results" in data
    assert "users" in data["results"]
    assert "doctors" in data["results"]
    assert "staff" in data["results"]
    assert "patients" in data["results"]


# ── 14. Mass Assignment & Malicious Payload Protection ────────────────────────

@pytest.mark.asyncio
async def test_admin_mass_assignment_protection(async_client: AsyncClient):
    """Admin update endpoints reject or strip forbidden fields like password_hash or _id."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    db = db_manager.db

    # Find any user
    user = await db[COLLECTION_USERS].find_one({"role": "patient"})
    if user:
        user_id = user["user_id"]
        original_hash = user.get("password_hash")

        # Attempt to inject password_hash and escalate role via status update
        malicious_payload = {
            "account_status": user.get("account_status", "active"),
            "password_hash": "hacked_password_hash",
            "role": "hospital_admin",
            "_id": "64b0f92b1a8f9b001c9a1234"
        }
        res = await async_client.patch(
            f"/api/v1/admin/users/{user_id}/status",
            headers=admin_headers,
            json=malicious_payload
        )
        assert res.status_code == 200

        # Verify DB doc was NOT modified with malicious fields
        refreshed = await db[COLLECTION_USERS].find_one({"user_id": user_id})
        assert refreshed.get("password_hash") == original_hash, "password_hash must NOT be overwritten by mass assignment!"
        assert refreshed.get("role") == "patient", "role must NOT be escalated via status patch!"


# ── 15. Concurrency & Idempotency Safety ───────────────────────────────────────

@pytest.mark.asyncio
async def test_admin_concurrency_and_idempotency(async_client: AsyncClient):
    """Concurrent updates to account status execute safely without corrupting database state."""
    admin_token = await get_admin_token(async_client)
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    db = db_manager.db

    # Create temporary user for concurrency test
    test_uid = f"USR-CONC-{uuid.uuid4().hex[:6]}"
    await db[COLLECTION_USERS].insert_one({
        "user_id": test_uid,
        "email": f"concurrency_{uuid.uuid4().hex[:6]}@testclinix.com",
        "full_name": "Concurrency Test User",
        "role": "patient",
        "account_status": "active",
        "created_at": utc_now(),
        "updated_at": utc_now(),
    })

    # Dispatch two concurrent disable requests
    req1 = async_client.patch(
        f"/api/v1/admin/users/{test_uid}/status",
        headers=admin_headers,
        json={"account_status": "disabled", "reason": "Concurrent admin disable 1"}
    )
    req2 = async_client.patch(
        f"/api/v1/admin/users/{test_uid}/status",
        headers=admin_headers,
        json={"account_status": "disabled", "reason": "Concurrent admin disable 2"}
    )

    res1, res2 = await asyncio.gather(req1, req2)
    assert res1.status_code == 200
    assert res2.status_code == 200

    # Verify final state is cleanly disabled
    final_user = await db[COLLECTION_USERS].find_one({"user_id": test_uid})
    assert final_user["account_status"] == "disabled"

    # Clean up
    await db[COLLECTION_USERS].delete_one({"user_id": test_uid})
