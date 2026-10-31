"""Comprehensive Unit & Integration Test Suite for Phase 19: Analytics, Reports & Hospital Operations Production Hardening."""

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


def create_mock_db_phase19():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.count_documents = AsyncMock(return_value=10)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            col.aggregate = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase19AnalyticsAndReports(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 19 Analytics, Department Revenue, Payment Breakdown, CSV Export, and RBAC."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase19()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.admin_user = UserInDB(
            user_id="USR-ADM-DEMO-001",
            email="admin@clinixai.com",
            full_name="Hospital Admin",
            role=UserRole.HOSPITAL_ADMIN,
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
            if uid == "USR-PAT-ONE-001":
                return self.pat_user.model_dump()
            return None

        self.mock_db["users"].find_one.side_effect = AsyncMock(side_effect=mock_user_find_one)

        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.pat_token = create_access_token(user_id=self.pat_user.user_id, role=self.pat_user.role.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.pat_headers = {"Authorization": f"Bearer {self.pat_token}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_get_operational_summary_admin(self):
        """Test Admin retrieves operational summary metrics."""
        response = await self.client.get("/api/v1/admin/summary", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        self.assertIn("total_patients", data["data"])
        self.assertIn("active_doctors", data["data"])

    async def test_get_financial_summary_admin(self):
        """Test Admin retrieves financial summary aggregates."""
        sample_bills = [
            {
                "bill_id": "BIL-001",
                "grand_total": 1500.0,
                "amount_paid": 1500.0,
                "balance_due": 0.0,
                "status": "paid",
                "payments": [{"status": "completed", "method": "upi", "amount": 1500.0}],
            }
        ]
        self.mock_db["billing"].find.return_value = create_mock_cursor(sample_bills)

        response = await self.client.get("/api/v1/admin/financial-summary", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("total_billed", data["data"])
        self.assertEqual(data["data"]["total_billed"], 1500.0)

    async def test_get_revenue_by_department_admin(self):
        """Test Admin retrieves revenue grouped by department."""
        dept_docs = [{"department_id": "DEP-CARD-001", "name": "Cardiology"}]
        agg_results = [{"_id": "DEP-CARD-001", "total_billed": 2500.0, "total_collected": 2500.0, "bill_count": 2}]

        self.mock_db["departments"].find.return_value = create_mock_cursor(dept_docs)
        self.mock_db["billing"].aggregate.return_value = create_mock_cursor(agg_results)

        response = await self.client.get("/api/v1/admin/revenue-by-department", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(len(data["data"]), 1)
        self.assertEqual(data["data"][0]["department_name"], "Cardiology")

    async def test_get_payment_method_mix_admin(self):
        """Test Admin retrieves payment method breakdown."""
        bills_with_payments = [
            {"payments": [{"status": "completed", "method": "cash", "amount": 500.0}]},
            {"payments": [{"status": "completed", "method": "card", "amount": 1000.0}]},
        ]
        self.mock_db["billing"].find.return_value = create_mock_cursor(bills_with_payments)

        response = await self.client.get("/api/v1/admin/payment-method-mix", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("payment_methods", data["data"])
        self.assertEqual(data["data"]["payment_methods"]["cash"]["amount"], 500.0)

    async def test_get_appointment_analytics_admin(self):
        """Test Admin retrieves appointment status and department breakdown."""
        status_agg = [{"_id": "completed", "count": 8}, {"_id": "scheduled", "count": 4}]
        dept_agg = [{"_id": "DEP-CARD-001", "count": 12}]

        self.mock_db["appointments"].aggregate.side_effect = [
            create_mock_cursor(status_agg),
            create_mock_cursor(dept_agg),
        ]

        response = await self.client.get("/api/v1/admin/appointment-analytics", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"]["by_status"]["completed"], 8)

    async def test_export_billing_csv_admin(self):
        """Test Admin downloads sanitized CSV report of billing data."""
        sample_bills = [
            {
                "bill_id": "BIL-CSV-01",
                "patient_id": "PAT-001",
                "doctor_id": "DOC-001",
                "grand_total": 500.0,
                "amount_paid": 500.0,
                "balance_due": 0.0,
                "status": "paid",
                "created_at": "2026-08-13T10:00:00",
            }
        ]
        self.mock_db["billing"].find.return_value = create_mock_cursor(sample_bills)

        response = await self.client.get("/api/v1/admin/reports/csv", headers=self.admin_headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("Bill ID", response.text)
        self.assertIn("BIL-CSV-01", response.text)

    async def test_non_admin_access_forbidden(self):
        """Verify Patient calling Admin operational summary endpoint receives 403 Forbidden."""
        response = await self.client.get("/api/v1/admin/summary", headers=self.pat_headers)
        self.assertEqual(response.status_code, 403)
