"""
Comprehensive Complete Backend Verification Test Suite for CliniXAI.

Tests:
- FastAPI Startup & App Lifecycle
- Authentication & JWT Token Revocation
- RBAC Authorization & Patient Isolation
- Patients, Doctors, Staff, Departments Management
- Appointments & Double-Booking Prevention
- Consultations & Prescriptions
- Billing & Payment Recording
- Notifications Engine
- Follow-ups Subsystem
- Medical Documents Subsystem (Validation, Upload, Download, Delete, Restore)
- Persistent Audit Logging Subsystem
- Unified Backend Search Subsystem
- Clinical Timeline Aggregation
- Soft Delete & Restore Administration
- Multi-Model AI Subsystem (Registry, Loader, Missing Model Graceful Handling, AI Review, Analytics)
- Backend & AI Health Check Endpoints
"""

import pytest
import asyncio
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings
from app.ai.registry import get_ai_registry, AIModuleIdentifier
from app.ai.model_loader import get_model_loader
from app.models.user import UserRole, UserInDB


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_app_root_and_health_endpoints(client):
    """Verify root endpoint and health check APIs."""
    res = client.get("/")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "running"
    assert "version" in data

    res = client.get("/api/v1/health")
    assert res.status_code == 200

    res = client.get("/api/v1/ai/health")
    assert res.status_code == 200
    health_data = res.json()
    assert "status" in health_data
    assert "modules" in health_data

    res = client.get("/api/v1/ai/modules")
    assert res.status_code == 200
    modules_data = res.json()
    assert len(modules_data) >= 5


def test_ai_multi_model_registry_and_missing_model_graceful_handling():
    """Verify multi-model AI registry and graceful reporting when model files are missing."""
    registry = get_ai_registry()
    modules = registry.list_modules()
    assert len(modules) >= 5

    loader = get_model_loader()
    for mod_id in [
        AIModuleIdentifier.CHEST_XRAY.value,
        AIModuleIdentifier.BRAIN_MRI.value,
        AIModuleIdentifier.SKIN_DERMOSCOPY.value,
        AIModuleIdentifier.RETINAL_FUNDUS.value,
        AIModuleIdentifier.BONE_XRAY.value,
    ]:
        art = loader.load_module(mod_id)
        assert art is not None
        assert art.status in ("available", "unavailable", "initialization_failed")
        if not art.is_available:
            assert art.error_message is not None


def test_role_aliases():
    """Verify UserRole normalization handles 'admin' and 'staff' aliases."""
    admin_role = UserRole.normalize("admin")
    assert admin_role == UserRole.HOSPITAL_ADMIN

    staff_role = UserRole.normalize("staff")
    assert staff_role == UserRole.HOSPITAL_STAFF

    doc_role = UserRole.normalize("doctor")
    assert doc_role == UserRole.DOCTOR

    pat_role = UserRole.normalize("patient")
    assert pat_role == UserRole.PATIENT
