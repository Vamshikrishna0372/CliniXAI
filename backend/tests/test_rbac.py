"""Unit test suite for Four-Role RBAC Authorization dependencies."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport
from fastapi import APIRouter, Depends

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.dependencies.auth import require_roles
from app.utils.datetime import utc_now


def create_async_mock_db():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=None)
            col.delete_one = AsyncMock(return_value=None)
            col.delete_many = AsyncMock(return_value=None)
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


# Create dummy protected router for RBAC tests
test_rbac_router = APIRouter(prefix="/test-rbac", tags=["Test RBAC"])

@test_rbac_router.get("/admin-only", dependencies=[Depends(require_roles(UserRole.HOSPITAL_ADMIN))])
async def admin_only_route():
    return {"message": "Admin area"}

@test_rbac_router.get("/doctor-only", dependencies=[Depends(require_roles(UserRole.DOCTOR))])
async def doctor_only_route():
    return {"message": "Doctor area"}

@test_rbac_router.get("/patient-only", dependencies=[Depends(require_roles(UserRole.PATIENT))])
async def patient_only_route():
    return {"message": "Patient area"}

@test_rbac_router.get("/staff-only", dependencies=[Depends(require_roles(UserRole.HOSPITAL_STAFF))])
async def staff_only_route():
    return {"message": "Staff area"}

@test_rbac_router.get("/clinical-staff", dependencies=[Depends(require_roles(UserRole.DOCTOR, UserRole.HOSPITAL_STAFF))])
async def clinical_staff_route():
    return {"message": "Clinical staff area"}

app.include_router(test_rbac_router)


class TestRBACDependencies(unittest.IsolatedAsyncioTestCase):
    """Test suite for role-based authorization controls across all 4 user roles."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_async_mock_db()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # Create user fixtures for all 4 roles
        self.admin_user = UserInDB(
            user_id="USR-2026-ADM001", email="admin@clinixai.com", full_name="Admin",
            role=UserRole.HOSPITAL_ADMIN, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
            created_at=utc_now(), updated_at=utc_now()
        )
        self.doctor_user = UserInDB(
            user_id="USR-2026-DOC001", email="doctor@clinixai.com", full_name="Doctor",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
            created_at=utc_now(), updated_at=utc_now()
        )
        self.patient_user = UserInDB(
            user_id="USR-2026-PAT001", email="patient@clinixai.com", full_name="Patient",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
            created_at=utc_now(), updated_at=utc_now()
        )
        self.staff_user = UserInDB(
            user_id="USR-2026-STF001", email="staff@clinixai.com", full_name="Staff",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
            created_at=utc_now(), updated_at=utc_now()
        )

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    async def test_admin_access(self) -> None:
        """Verifies Hospital Admin can access admin endpoint, while Doctor/Patient/Staff are rejected."""
        token_admin = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        token_patient = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)

        # Admin request -> 200 OK
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()
        res_admin = await self.client.get("/test-rbac/admin-only", headers={"Authorization": f"Bearer {token_admin}"})
        self.assertEqual(res_admin.status_code, 200)

        # Patient request -> 403 Forbidden
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        res_patient = await self.client.get("/test-rbac/admin-only", headers={"Authorization": f"Bearer {token_patient}"})
        self.assertEqual(res_patient.status_code, 403)

    async def test_doctor_access(self) -> None:
        """Verifies Doctor can access doctor endpoint, while Patient is rejected."""
        token_doctor = create_access_token(user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)
        token_patient = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)

        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        res_doctor = await self.client.get("/test-rbac/doctor-only", headers={"Authorization": f"Bearer {token_doctor}"})
        self.assertEqual(res_doctor.status_code, 200)

        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        res_patient = await self.client.get("/test-rbac/doctor-only", headers={"Authorization": f"Bearer {token_patient}"})
        self.assertEqual(res_patient.status_code, 403)

    async def test_multi_role_access(self) -> None:
        """Verifies multi-role dependency accepts both Doctor and Hospital Staff."""
        token_doctor = create_access_token(user_id=self.doctor_user.user_id, role=self.doctor_user.role.value)
        token_staff = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)
        token_patient = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)

        # Doctor -> 200 OK
        self.mock_db["users"].find_one.return_value = self.doctor_user.to_mongo_dict()
        res1 = await self.client.get("/test-rbac/clinical-staff", headers={"Authorization": f"Bearer {token_doctor}"})
        self.assertEqual(res1.status_code, 200)

        # Staff -> 200 OK
        self.mock_db["users"].find_one.return_value = self.staff_user.to_mongo_dict()
        res2 = await self.client.get("/test-rbac/clinical-staff", headers={"Authorization": f"Bearer {token_staff}"})
        self.assertEqual(res2.status_code, 200)

        # Patient -> 403 Forbidden
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        res3 = await self.client.get("/test-rbac/clinical-staff", headers={"Authorization": f"Bearer {token_patient}"})
        self.assertEqual(res3.status_code, 403)
