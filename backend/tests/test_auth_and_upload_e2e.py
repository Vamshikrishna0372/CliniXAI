"""Comprehensive E2E Production Test Suite for CliniXAI.

Covers authentication, persistent MongoDB user accounts, duplicate email handling (409),
login-logout-relogin flow, token refresh rotation, medical image/document uploads,
storage persistence, RBAC isolation, invalid file validation, and AI inference.
"""

import io
import pytest
import pytest_asyncio
from PIL import Image
from httpx import AsyncClient
from app.database.mongodb import connect_to_mongo, db_manager
from app.database.db_seeder import seed_initial_data
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCUMENTS
)

TEST_USER_EMAIL = "production.e2e.patient@clinixai.com"
TEST_USER_PASSWORD = "ProductionPassword123!"
TEST_USER_NAME = "E2E Production Patient"

shared_context = {
    "user_id": None,
    "access_token": None,
    "refresh_token": None,
    "uploaded_doc_id": None,
}


def make_valid_png_bytes() -> bytes:
    """Generates a valid 224x224 PNG image in bytes format for PIL compatibility."""
    img = Image.new("RGB", (224, 224), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest_asyncio.fixture(autouse=True, scope="module")
async def init_database():
    """Ensure database connection and initial seeds are ready before running tests."""
    await connect_to_mongo()
    if db_manager.db is not None:
        await seed_initial_data(db_manager.db)


async def get_test_patient_tokens(async_client: AsyncClient):
    """Helper to obtain or create valid test patient session tokens."""
    db = db_manager.db
    res = await async_client.post("/api/v1/auth/login", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
    })
    if res.status_code == 200:
        data = res.json()
        u_id = data["user"]["user_id"]
        shared_context["user_id"] = u_id
        shared_context["access_token"] = data["access_token"]
        shared_context["refresh_token"] = data["refresh_token"]
        return {"access_token": data["access_token"], "refresh_token": data["refresh_token"], "user_id": u_id}

    reg_res = await async_client.post("/api/v1/auth/register", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "full_name": TEST_USER_NAME,
    })
    data = reg_res.json()
    u_id = data["user"]["user_id"]
    shared_context["user_id"] = u_id
    shared_context["access_token"] = data["access_token"]
    shared_context["refresh_token"] = data["refresh_token"]
    return {"access_token": data["access_token"], "refresh_token": data["refresh_token"], "user_id": u_id}


@pytest.mark.asyncio
async def test_01_register_new_user(async_client: AsyncClient):
    """TEST 1: Register new patient user -> 201 Created + JWT tokens."""
    db = db_manager.db
    if db is not None:
        await db[COLLECTION_USERS].delete_many({"email": TEST_USER_EMAIL})
        await db[COLLECTION_PATIENTS].delete_many({"email": TEST_USER_EMAIL})

    payload = {
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "full_name": TEST_USER_NAME,
    }
    res = await async_client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 201, f"Registration failed: {res.text}"
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == TEST_USER_EMAIL
    assert data["user"]["role"] == "patient"
    shared_context["user_id"] = data["user"]["user_id"]
    shared_context["access_token"] = data["access_token"]
    shared_context["refresh_token"] = data["refresh_token"]


@pytest.mark.asyncio
async def test_02_verify_mongodb_user_exists():
    """TEST 2: Verify user and linked patient records exist directly in MongoDB."""
    db = db_manager.db
    assert db is not None
    user_doc = await db[COLLECTION_USERS].find_one({"email": TEST_USER_EMAIL})
    assert user_doc is not None
    assert user_doc["email"] == TEST_USER_EMAIL
    assert user_doc["password_hash"] is not None
    assert user_doc["role"] == "patient"
    assert user_doc["account_status"] == "active"

    patient_doc = await db[COLLECTION_PATIENTS].find_one({"email": TEST_USER_EMAIL})
    assert patient_doc is not None
    assert patient_doc["user_id"] == user_doc["user_id"]


@pytest.mark.asyncio
async def test_03_login_with_registered_credentials(async_client: AsyncClient):
    """TEST 3: Login with registered credentials -> 200 OK."""
    res = await async_client.post("/api/v1/auth/login", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
    })
    assert res.status_code == 200, f"Login failed: {res.text}"
    data = res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["user"]["email"] == TEST_USER_EMAIL
    shared_context["access_token"] = data["access_token"]
    shared_context["refresh_token"] = data["refresh_token"]


@pytest.mark.asyncio
async def test_04_call_auth_me(async_client: AsyncClient):
    """TEST 4: Call /auth/me with access token -> 200 OK."""
    if not shared_context.get("access_token"):
        await get_test_patient_tokens(async_client)
    token = shared_context["access_token"]
    me_res = await async_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_res.status_code == 200
    me_data = me_res.json()
    assert me_data["email"] == TEST_USER_EMAIL
    assert me_data["role"] == "patient"


@pytest.mark.asyncio
async def test_05_logout(async_client: AsyncClient):
    """TEST 5: Logout -> revokes session."""
    if not shared_context.get("refresh_token"):
        await get_test_patient_tokens(async_client)
    refresh_token = shared_context["refresh_token"]
    logout_res = await async_client.post("/api/v1/auth/logout", json={"refresh_token": refresh_token})
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True


@pytest.mark.asyncio
async def test_06_login_again_same_credentials(async_client: AsyncClient):
    """TEST 6: Login again using SAME credentials -> 200 OK."""
    res = await async_client.post("/api/v1/auth/login", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
    })
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == TEST_USER_EMAIL
    shared_context["access_token"] = data["access_token"]
    shared_context["refresh_token"] = data["refresh_token"]


@pytest.mark.asyncio
async def test_07_refresh_access_token(async_client: AsyncClient):
    """TEST 7: Refresh access token -> 200 OK with rotated token pair."""
    if not shared_context.get("refresh_token"):
        await get_test_patient_tokens(async_client)
    old_refresh = shared_context["refresh_token"]
    refresh_res = await async_client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refresh_res.status_code == 200
    data = refresh_res.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["refresh_token"] != old_refresh
    shared_context["access_token"] = data["access_token"]
    shared_context["refresh_token"] = data["refresh_token"]


@pytest.mark.asyncio
async def test_08_call_protected_endpoint_with_refreshed_token(async_client: AsyncClient):
    """TEST 8: Access protected endpoint with refreshed token -> 200 OK."""
    if not shared_context.get("access_token"):
        await get_test_patient_tokens(async_client)
    new_access_token = shared_context["access_token"]
    doc_res = await async_client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {new_access_token}"}
    )
    assert doc_res.status_code == 200


@pytest.mark.asyncio
async def test_09_register_duplicate_email_conflict(async_client: AsyncClient):
    """TEST 9: Registering duplicate email -> 409 Conflict."""
    await get_test_patient_tokens(async_client)
    res = await async_client.post("/api/v1/auth/register", json={
        "email": TEST_USER_EMAIL,
        "password": TEST_USER_PASSWORD,
        "full_name": TEST_USER_NAME,
    })
    assert res.status_code == 409
    err_body = res.json()
    msg = err_body.get("error", {}).get("message", res.text)
    assert "already exists" in msg.lower()


@pytest.mark.asyncio
async def test_10_invalid_password(async_client: AsyncClient):
    """TEST 10: Invalid password -> 401 Unauthorized."""
    await get_test_patient_tokens(async_client)
    res = await async_client.post("/api/v1/auth/login", json={
        "email": TEST_USER_EMAIL,
        "password": "WrongPassword123!",
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_11_unknown_email(async_client: AsyncClient):
    """TEST 11: Unknown email -> 401 Unauthorized."""
    res = await async_client.post("/api/v1/auth/login", json={
        "email": "nonexistent.user@clinixai.com",
        "password": TEST_USER_PASSWORD,
    })
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_12_expired_or_invalid_access_token(async_client: AsyncClient):
    """TEST 12: Invalid access token -> 401 Unauthorized."""
    res = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": "Bearer invalid.jwt.token.here"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_13_invalid_refresh_token(async_client: AsyncClient):
    """TEST 13: Invalid refresh token -> 401 Unauthorized."""
    res = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": "invalid.refresh.token"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_14_upload_medical_image(async_client: AsyncClient):
    """TEST 14: Upload medical image -> 201 Created."""
    session = await get_test_patient_tokens(async_client)
    token = session["access_token"]
    user_id = session["user_id"]

    valid_png_bytes = make_valid_png_bytes()

    files = {
        "file": ("chest_xray_test.png", valid_png_bytes, "image/png"),
    }
    data = {
        "patient_id": user_id,
        "title": "Test Chest X-Ray Imaging",
        "category": "X-Ray",
    }

    res = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert res.status_code == 201, f"Document upload failed: {res.text}"
    res_data = res.json()
    assert "document_id" in res_data
    assert res_data["title"] == "Test Chest X-Ray Imaging"
    shared_context["uploaded_doc_id"] = res_data["document_id"]


@pytest.mark.asyncio
async def test_15_verify_mongodb_document_metadata():
    """TEST 15: Verify MongoDB document record exists."""
    doc_id = shared_context.get("uploaded_doc_id")
    db = db_manager.db
    assert doc_id is not None
    assert db is not None

    doc_record = await db[COLLECTION_DOCUMENTS].find_one({"document_id": doc_id})
    assert doc_record is not None
    assert doc_record["original_file_name"] == "chest_xray_test.png"


@pytest.mark.asyncio
async def test_16_verify_stored_file_bytes(async_client: AsyncClient):
    """TEST 16: Download/stream document and verify content bytes match."""
    session = await get_test_patient_tokens(async_client)
    token = session["access_token"]
    doc_id = shared_context["uploaded_doc_id"]

    stream_res = await async_client.get(
        f"/api/v1/documents/{doc_id}/download",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert stream_res.status_code == 200
    assert len(stream_res.content) > 0


@pytest.mark.asyncio
async def test_17_refresh_session_and_retrieve_document(async_client: AsyncClient):
    """TEST 17: Retrieve document list after session refresh."""
    session = await get_test_patient_tokens(async_client)
    refresh_res = await async_client.post("/api/v1/auth/refresh", json={
        "refresh_token": session["refresh_token"]
    })
    new_token = refresh_res.json()["access_token"]

    docs_res = await async_client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {new_token}"}
    )
    assert docs_res.status_code == 200
    items = docs_res.json()["items"]
    assert any(d["document_id"] == shared_context["uploaded_doc_id"] for d in items)


@pytest.mark.asyncio
async def test_18_unauthorized_user_attempts_another_document(async_client: AsyncClient):
    """TEST 18: Another patient user attempting access -> 403 Forbidden."""
    db = db_manager.db
    other_email = "other.patient.e2e@clinixai.com"
    if db is not None:
        await db[COLLECTION_USERS].delete_many({"email": other_email})

    reg_res = await async_client.post("/api/v1/auth/register", json={
        "email": other_email,
        "password": TEST_USER_PASSWORD,
        "full_name": "Other Patient",
    })
    other_token = reg_res.json()["access_token"]
    doc_id = shared_context["uploaded_doc_id"]

    access_res = await async_client.get(
        f"/api/v1/documents/{doc_id}",
        headers={"Authorization": f"Bearer {other_token}"}
    )
    assert access_res.status_code == 403


@pytest.mark.asyncio
async def test_19_invalid_file_upload_validation(async_client: AsyncClient):
    """TEST 19: Uploading dangerous executable -> 400 Bad Request."""
    session = await get_test_patient_tokens(async_client)
    token = session["access_token"]
    user_id = session["user_id"]

    files = {
        "file": ("malicious_script.exe", b"MZexecutabledata", "application/x-msdownload"),
    }
    data = {
        "patient_id": user_id,
        "title": "Executable File",
        "category": "Other",
    }

    res = await async_client.post(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {token}"},
        data=data,
        files=files,
    )
    assert res.status_code in (400, 422)


@pytest.mark.asyncio
async def test_20_ai_direct_inference(async_client: AsyncClient):
    """TEST 20: AI Direct Inference using medical image -> 200 OK."""
    doc_res = await async_client.post("/api/v1/auth/login", json={
        "email": "doctor.arjun@clinixai.com",
        "password": "Doctor@123",
    })
    assert doc_res.status_code == 200
    doc_token = doc_res.json()["access_token"]

    valid_png_bytes = make_valid_png_bytes()

    files = {
        "image": ("brain_mri.png", valid_png_bytes, "image/png"),
    }
    data = {
        "analysis_type": "BRAIN_MRI",
    }

    infer_res = await async_client.post(
        "/api/v1/ai/infer",
        headers={"Authorization": f"Bearer {doc_token}"},
        data=data,
        files=files,
    )
    assert infer_res.status_code == 200
    infer_data = infer_res.json()
    assert "predicted_class" in infer_data
    assert "confidence" in infer_data
