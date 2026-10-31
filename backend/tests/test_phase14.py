"""Comprehensive Unit & Integration Test Suite for Phase 14: Reports, Analytics, Dashboards & Data Visualization."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token


def create_mock_cursor(return_data=None):
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db_phase14():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
            col.count_documents = AsyncMock(return_value=5)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            col.aggregate = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase14AnalyticsAndReports(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 14 Admin Analytics, Reports, Financial Metrics, and RBAC."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase14()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.admin_user = UserInDB(
            user_id="USR-ADM-DEMO-001",
            email="admin@clinixai.com",
            full_name="Hospital Administrator",
            role=UserRole.HOSPITAL_ADMIN,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.doc_user = UserInDB(
            user_id="USR-DOC-RAO-001",
            email="doctor.arjun@clinixai.com",
            full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.pat_user = UserInDB(
            user_id="USR-PAT-ONE-001",
            email="patient.one@clinixai.com",
            full_name="Patient One",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        def mock_user_find_one(query):
            uid = query.get("user_id")
            if uid == "USR-ADM-DEMO-001":
                return self.admin_user.model_dump()
            if uid == "USR-DOC-RAO-001":
                return self.doc_user.model_dump()
            if uid == "USR-PAT-ONE-001":
                return self.pat_user.model_dump()
            return None

        self.mock_db["users"].find_one.side_effect = AsyncMock(side_effect=mock_user_find_one)

        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.doc_token = create_access_token(user_id=self.doc_user.user_id, role=self.doc_user.role.value)
        self.pat_token = create_access_token(user_id=self.pat_user.user_id, role=self.pat_user.role.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        self.pat_headers = {"Authorization": f"Bearer {self.pat_token}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_admin_operational_summary(self):
        """Test retrieving hospital operational summary as Admin."""
        response = await self.client.get("/api/v1/admin/summary", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        summary = data["data"]
        self.assertIn("total_patients", summary)
        self.assertIn("active_doctors", summary)
        self.assertIn("today_appointments", summary)

    async def test_admin_financial_summary(self):
        """Test retrieving hospital financial summary with date parameters."""
        sample_bill = {
            "bill_id": "BIL-001",
            "grand_total": 1500.0,
            "amount_paid": 1500.0,
            "balance_due": 0.0,
            "status": "paid",
            "payments": [{"method": "upi", "amount": 1500.0, "status": "completed"}],
            "created_at": "2026-08-10T10:00:00Z",
        }
        self.mock_db["billing"].find.return_value = create_mock_cursor([sample_bill])

        response = await self.client.get(
            "/api/v1/admin/financial-summary?start_date=2026-08-01&end_date=2026-08-31",
            headers=self.admin_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        fin = data["data"]
        self.assertEqual(fin["total_billed"], 1500.0)
        self.assertEqual(fin["total_collected"], 1500.0)
        self.assertIn("payment_methods", fin)

    async def test_revenue_by_department(self):
        """Test retrieving department-level revenue breakdown."""
        sample_dept = [{"department_id": "DEP-CARD", "name": "Cardiology"}]
        self.mock_db["departments"].find.return_value = create_mock_cursor(sample_dept)

        sample_agg = [{"_id": "DEP-CARD", "total_billed": 5000.0, "total_collected": 4500.0, "bill_count": 3}]
        self.mock_db["billing"].aggregate.return_value = create_mock_cursor(sample_agg)

        response = await self.client.get("/api/v1/admin/revenue-by-department", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIsInstance(data["data"], list)

    async def test_appointment_analytics(self):
        """Test retrieving appointment status and department breakdown."""
        self.mock_db["appointments"].count_documents.return_value = 20
        response = await self.client.get("/api/v1/admin/appointment-analytics", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"]["total_appointments"], 20)

    async def test_export_billing_csv(self):
        """Test generating and downloading sanitized CSV report."""
        sample_bill = {
            "bill_id": "BIL-TEST-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "grand_total": 1200.0,
            "amount_paid": 1200.0,
            "balance_due": 0.0,
            "status": "paid",
            "created_at": "2026-08-12T14:30:00Z",
        }
        self.mock_db["billing"].find.return_value = create_mock_cursor([sample_bill])

        response = await self.client.get("/api/v1/admin/reports/csv", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("Bill ID,Patient ID,Doctor ID", response.text)
        self.assertIn("BIL-TEST-001", response.text)

    async def test_rbac_isolation_non_admin_forbidden(self):
        """Verify Doctor and Patient cannot access Admin analytics endpoints."""
        doc_resp = await self.client.get("/api/v1/admin/summary", headers=self.doc_headers)
        self.assertEqual(doc_resp.status_code, 403)

        pat_resp = await self.client.get("/api/v1/admin/financial-summary", headers=self.pat_headers)
        self.assertEqual(pat_resp.status_code, 403)
