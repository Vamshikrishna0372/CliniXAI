"""Standardized Pytest fixtures configuration for CliniXAI automated test suite.
Provides:
- MongoDB connection and verification
- ASGI test client (AsyncClient)
- Deterministic test user authentication headers (Admin, Doctor A/B, Staff, Patient A/B)
- Test database isolation safety
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from typing import AsyncGenerator, Dict, Any

from app.main import app
from app.database.mongodb import connect_to_mongo, db_manager
from app.database.db_seeder import seed_initial_data
from app.core.security import create_access_token
from tests.fixtures.factories import verify_test_database_safety, cleanup_test_records_by_prefix


@pytest_asyncio.fixture(scope="session", autouse=True)
async def init_test_environment():
    """Initializes MongoDB and seeds baseline schema/indexes for the test session."""
    if db_manager.db is None:
        await connect_to_mongo()
    if db_manager.db is not None:
        await verify_test_database_safety(db_manager.db)
        await seed_initial_data(db_manager.db)
    yield
    # Cleanup any lingering TEST- records created during the session
    if db_manager.db is not None:
        await cleanup_test_records_by_prefix(db_manager.db, "TEST-")


@pytest_asyncio.fixture
async def test_db():
    """Provides direct reference to the active test database."""
    if db_manager.db is None:
        await connect_to_mongo()
    return db_manager.db


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Provides an httpx.AsyncClient bound to the FastAPI ASGI application with MongoDB connection."""
    if db_manager.db is None:
        await connect_to_mongo()
        if db_manager.db is not None:
            await seed_initial_data(db_manager.db)
            
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


# Standardized Test Roles & Tokens

@pytest.fixture
def admin_headers() -> Dict[str, str]:
    token = create_access_token(user_id="USR-ADMIN-001", role="hospital_admin")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def doctor_a_headers() -> Dict[str, str]:
    token = create_access_token(user_id="USR-DOC-RAO-001", role="doctor")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def doctor_b_headers() -> Dict[str, str]:
    token = create_access_token(user_id="USR-DOC-SHARMA-002", role="doctor")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def staff_headers() -> Dict[str, str]:
    token = create_access_token(user_id="USR-STAFF-001", role="staff")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def patient_a_headers() -> Dict[str, str]:
    token = create_access_token(user_id="USR-PAT-001", role="patient")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


@pytest.fixture
def patient_b_headers() -> Dict[str, str]:
    token = create_access_token(user_id="USR-PAT-002", role="patient")
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
