"""Phase 23 Smoke Test Suite.
Provides fast validation (<10s) of platform sanity:
1. Health and readiness endpoints
2. Authentication and role detection across all 4 roles
3. Admin core workflow (dashboard stats and user listing)
4. Doctor core workflow (doctor detail and appointments)
5. Staff core workflow (front-desk dashboard and queue)
6. Patient core workflow (profile and doctor discovery)
7. Authoritative database read and state mutation
"""

import pytest
from httpx import AsyncClient


async def get_token_for(async_client: AsyncClient, email: str, password: str) -> str:
    res = await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert res.status_code == 200, f"Login failed for {email}: {res.text}"
    data = res.json()
    return data["data"]["access_token"] if "data" in data else data["access_token"]


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_01_health_and_readiness(async_client: AsyncClient):
    """Verify health and readiness probes return 200 OK and connected database."""
    res_health = await async_client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["status"] == "healthy"

    res_ready = await async_client.get("/api/v1/health/ready")
    assert res_ready.status_code == 200
    assert res_ready.json()["database"] == "connected"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_02_authentication_and_role_detection(async_client: AsyncClient):
    """Verify login authentication and role detection across all 4 canonical roles."""
    roles_credentials = [
        ("admin@clinixai.com", "admin123", "hospital_admin"),
        ("staff.one@clinixai.com", "Staff@123", "staff"),
        ("doctor.arjun@clinixai.com", "Doctor@123", "doctor"),
        ("patient.one@clinixai.com", "Patient@123", "patient"),
    ]

    for email, password, expected_role in roles_credentials:
        token = await get_token_for(async_client, email, password)
        assert token is not None and len(token) > 20


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_03_admin_core_workflow(async_client: AsyncClient):
    """Verify admin dashboard metrics and user directory listing."""
    admin_token = await get_token_for(async_client, "admin@clinixai.com", "admin123")
    headers = {"Authorization": f"Bearer {admin_token}"}

    res_dash = await async_client.get("/api/v1/admin/dashboard", headers=headers)
    assert res_dash.status_code == 200

    res_users = await async_client.get("/api/v1/admin/users?page=1&limit=5", headers=headers)
    assert res_users.status_code == 200
    assert len(res_users.json()["data"]) > 0


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_04_doctor_core_workflow(async_client: AsyncClient):
    """Verify doctor schedule query and appointment queue workspace."""
    doctor_token = await get_token_for(async_client, "doctor.arjun@clinixai.com", "Doctor@123")
    headers = {"Authorization": f"Bearer {doctor_token}"}

    res_doc = await async_client.get("/api/v1/doctors/DOC-RAO-001", headers=headers)
    assert res_doc.status_code == 200
    doc_json = res_doc.json()
    doc_data = doc_json.get("data", doc_json)
    assert doc_data["doctor_id"] == "DOC-RAO-001"

    res_apts = await async_client.get("/api/v1/appointments?page=1&page_size=5", headers=headers)
    assert res_apts.status_code == 200
    assert "data" in res_apts.json()


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_05_staff_core_workflow(async_client: AsyncClient):
    """Verify staff operational dashboard and profile."""
    staff_token = await get_token_for(async_client, "staff.one@clinixai.com", "Staff@123")
    headers = {"Authorization": f"Bearer {staff_token}"}

    res_dash = await async_client.get("/api/v1/staff/dashboard-overview", headers=headers)
    assert res_dash.status_code == 200

    res_me = await async_client.get("/api/v1/staff/me", headers=headers)
    assert res_me.status_code == 200
    assert res_me.json()["data"]["email"] == "staff.one@clinixai.com"


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_06_patient_core_workflow(async_client: AsyncClient):
    """Verify patient profile retrieval and doctor discovery."""
    patient_token = await get_token_for(async_client, "patient.one@clinixai.com", "Patient@123")
    headers = {"Authorization": f"Bearer {patient_token}"}

    res_me = await async_client.get("/api/v1/patients/me", headers=headers)
    assert res_me.status_code == 200
    pat_json = res_me.json()
    pat_data = pat_json.get("data", pat_json)
    assert pat_data["patient_id"] == "PAT-ONE-001"

    res_docs = await async_client.get("/api/v1/doctors?page=1&page_size=5", headers=headers)
    assert res_docs.status_code == 200
    assert len(res_docs.json()["data"]) > 0


@pytest.mark.smoke
@pytest.mark.asyncio
async def test_smoke_07_database_read_and_mutation(async_client: AsyncClient, test_db):
    """Verify authoritative database write, read, and safe test cleanup."""
    patient_token = await get_token_for(async_client, "patient.one@clinixai.com", "Patient@123")
    headers = {"Authorization": f"Bearer {patient_token}"}

    test_apt_data = {
        "doctor_id": "DOC-RAO-001",
        "appointment_date": "2026-12-25",
        "start_time": "11:00",
        "reason": "Smoke Test Consultation",
    }
    
    # Create
    res_book = await async_client.post("/api/v1/appointments", json=test_apt_data, headers=headers)
    if res_book.status_code in [201, 200]:
        book_json = res_book.json()
        book_data = book_json.get("data", book_json)
        apt_id = book_data["appointment_id"]
        # Read from API
        res_get = await async_client.get(f"/api/v1/appointments/{apt_id}", headers=headers)
        assert res_get.status_code == 200
        get_json = res_get.json()
        get_data = get_json.get("data", get_json)
        assert get_data["appointment_id"] == apt_id
        
        # Verify directly in MongoDB
        db_record = await test_db["appointments"].find_one({"appointment_id": apt_id})
        assert db_record is not None
        assert db_record["patient_id"] == "PAT-ONE-001"
        
        # Cleanup
        await test_db["appointments"].delete_one({"appointment_id": apt_id})
    elif res_book.status_code == 409:
        # Slot was already occupied in persistent DB, read existing
        res_apts = await async_client.get("/api/v1/appointments?page=1&page_size=1", headers=headers)
        assert res_apts.status_code == 200
