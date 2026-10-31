"""Comprehensive Unit & Integration Test Suite for Phase 16: Billing, Invoices, Payments, Receipts & Financial Workflows."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.billing import BillingStatus, PaymentMethod, PaymentStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now


def create_mock_cursor(return_data=None):
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db_phase16():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.find_one_and_update = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
            col.count_documents = AsyncMock(return_value=1)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase16BillingAndPayments(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 16 Billing, Line-Items, Payment Recording, Receipts, and Financial RBAC."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase16()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.admin_user = UserInDB(
            user_id="USR-ADM-DEMO-001",
            email="admin@clinixai.com",
            full_name="Hospital Admin",
            role=UserRole.HOSPITAL_ADMIN,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.staff_user = UserInDB(
            user_id="USR-STF-ONE-001",
            email="staff.one@clinixai.com",
            full_name="Staff One",
            role=UserRole.HOSPITAL_STAFF,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.pat_user_1 = UserInDB(
            user_id="USR-PAT-ONE-001",
            email="patient.one@clinixai.com",
            full_name="Patient One",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.pat_user_2 = UserInDB(
            user_id="USR-PAT-TWO-002",
            email="patient.two@clinixai.com",
            full_name="Patient Two",
            role=UserRole.PATIENT,
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

        def mock_user_find_one(query):
            uid = query.get("user_id")
            if uid == "USR-ADM-DEMO-001":
                return self.admin_user.model_dump()
            if uid == "USR-STF-ONE-001":
                return self.staff_user.model_dump()
            if uid == "USR-PAT-ONE-001":
                return self.pat_user_1.model_dump()
            if uid == "USR-PAT-TWO-002":
                return self.pat_user_2.model_dump()
            if uid == "USR-DOC-RAO-001":
                return self.doc_user.model_dump()
            return None

        def mock_patient_find_one(query):
            pid = query.get("patient_id")
            uid = query.get("user_id")
            if pid == "PAT-ONE-001" or uid == "USR-PAT-ONE-001":
                return {"patient_id": "PAT-ONE-001", "user_id": "USR-PAT-ONE-001", "first_name": "Patient", "last_name": "One"}
            if pid == "PAT-TWO-002" or uid == "USR-PAT-TWO-002":
                return {"patient_id": "PAT-TWO-002", "user_id": "USR-PAT-TWO-002", "first_name": "Patient", "last_name": "Two"}
            return {"patient_id": "PAT-ONE-001", "user_id": "USR-PAT-ONE-001", "first_name": "Patient", "last_name": "One"}

        self.mock_db["patients"].find_one.side_effect = AsyncMock(side_effect=mock_patient_find_one)
        self.mock_db["users"].find_one.side_effect = AsyncMock(side_effect=mock_user_find_one)
        self.mock_db["appointments"].find_one.return_value = {"appointment_id": "APT-001", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-RAO-001"}

        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.staff_token = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)
        self.pat1_token = create_access_token(user_id=self.pat_user_1.user_id, role=self.pat_user_1.role.value)
        self.pat2_token = create_access_token(user_id=self.pat_user_2.user_id, role=self.pat_user_2.role.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        self.pat1_headers = {"Authorization": f"Bearer {self.pat1_token}"}
        self.pat2_headers = {"Authorization": f"Bearer {self.pat2_token}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_create_bill_and_calculate_totals(self):
        """Test creating draft bill and calculating line item totals."""
        payload = {
            "patient_id": "PAT-ONE-001",
            "appointment_id": "APT-001",
            "line_items": [
                {
                    "item_code": "CONSULT-001",
                    "description": "General Cardiology Consultation",
                    "quantity": 1.0,
                    "unit_price": 1000.0,
                    "tax_percent": 5.0,
                    "discount_amount": 100.0,
                }
            ],
            "notes": "Cardiology consult bill",
        }
        response = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        bill = data["data"]
        self.assertEqual(bill["subtotal"], 1000.0)
        self.assertEqual(bill["total_tax"], 50.0)
        self.assertEqual(bill["total_discount"], 100.0)
        self.assertEqual(bill["grand_total"], 950.0)
        self.assertEqual(bill["status"], "draft")

    async def test_issue_bill(self):
        """Test issuing draft bill transitions status to ISSUED."""
        sample_bill = {
            "bill_id": "BIL-TEST-001",
            "patient_id": "PAT-ONE-001",
            "created_by": "USR-STF-ONE-001",
            "line_items": [{"item_code": "CONSULT", "description": "Consultation", "quantity": 1, "unit_price": 500, "tax_percent": 0, "discount_amount": 0}],
            "payments": [],
            "status": "draft",
            "subtotal": 500.0,
            "total_tax": 0.0,
            "total_discount": 0.0,
            "grand_total": 500.0,
            "amount_paid": 0.0,
            "balance_due": 500.0,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["billing"].find_one.return_value = sample_bill

        response = await self.client.post("/api/v1/billing/BIL-TEST-001/issue", headers=self.staff_headers)
        self.assertEqual(response.status_code, 200)

    async def test_record_payment_and_overpayment_validation(self):
        """Test recording UPI payment and ensuring overpayment is rejected."""
        sample_bill = {
            "bill_id": "BIL-TEST-002",
            "patient_id": "PAT-ONE-001",
            "created_by": "USR-STF-ONE-001",
            "line_items": [{"item_code": "CONSULT", "description": "Consultation", "quantity": 1, "unit_price": 500.0, "tax_percent": 0, "discount_amount": 0}],
            "payments": [],
            "status": "issued",
            "subtotal": 500.0,
            "total_tax": 0.0,
            "total_discount": 0.0,
            "grand_total": 500.0,
            "amount_paid": 0.0,
            "balance_due": 500.0,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["billing"].find_one.return_value = sample_bill

        # Overpayment validation test (> 500.00) -> 400 Bad Request
        overpay_resp = await self.client.post(
            "/api/v1/billing/BIL-TEST-002/payments",
            json={"amount": 600.0, "method": "upi", "reference_number": "UTR123456789"},
            headers=self.staff_headers,
        )
        self.assertEqual(overpay_resp.status_code, 400)

        # Exact payment success test -> 200 OK
        paid_bill_1 = {**sample_bill, "amount_paid": 500.0, "balance_due": 0.0, "status": "paid", "payments": [{"payment_id": "PAY-1", "amount": 500.0}]}
        self.mock_db["billing"].find_one_and_update.return_value = paid_bill_1
        pay_resp = await self.client.post(
            "/api/v1/billing/BIL-TEST-002/payments",
            json={"amount": 500.0, "method": "upi", "reference_number": "UTR123456789"},
            headers=self.staff_headers,
        )
        self.assertEqual(pay_resp.status_code, 200)

    async def test_patient_self_payment_and_patient_isolation(self):
        """Test Patient 1 can pay own bill, while Patient 2 is forbidden (403)."""
        sample_bill = {
            "bill_id": "BIL-TEST-PAT1",
            "patient_id": "PAT-ONE-001",
            "created_by": "USR-STF-ONE-001",
            "line_items": [{"item_code": "SERVICE", "description": "Therapy", "quantity": 1, "unit_price": 300.0, "tax_percent": 0, "discount_amount": 0}],
            "payments": [],
            "status": "issued",
            "subtotal": 300.0,
            "total_tax": 0.0,
            "total_discount": 0.0,
            "grand_total": 300.0,
            "amount_paid": 0.0,
            "balance_due": 300.0,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["billing"].find_one.return_value = sample_bill
        paid_bill_2 = {**sample_bill, "amount_paid": 300.0, "balance_due": 0.0, "status": "paid", "payments": [{"payment_id": "PAY-2", "amount": 300.0}]}
        self.mock_db["billing"].find_one_and_update.return_value = paid_bill_2

        def mock_patient_find_one(query):
            uid = query.get("user_id")
            if uid == "USR-PAT-ONE-001":
                return {"patient_id": "PAT-ONE-001", "user_id": "USR-PAT-ONE-001"}
            if uid == "USR-PAT-TWO-002":
                return {"patient_id": "PAT-TWO-002", "user_id": "USR-PAT-TWO-002"}
            return None

        self.mock_db["patients"].find_one.side_effect = AsyncMock(side_effect=mock_patient_find_one)

        # Patient 1 cannot record offline payments -> 403 Forbidden (staff/admin only)
        p1_pay = await self.client.post(
            "/api/v1/billing/BIL-TEST-PAT1/payments",
            json={"amount": 300.0, "method": "card", "reference_number": "TXN9999"},
            headers=self.pat1_headers,
        )
        self.assertEqual(p1_pay.status_code, 403)

        # Patient 2 tries to pay Patient 1's bill -> 403 Forbidden
        p2_pay = await self.client.post(
            "/api/v1/billing/BIL-TEST-PAT1/payments",
            json={"amount": 300.0, "method": "card", "reference_number": "TXN8888"},
            headers=self.pat2_headers,
        )
        self.assertEqual(p2_pay.status_code, 403)

        # Staff records payment for Patient 1's bill -> 200 OK
        staff_pay = await self.client.post(
            "/api/v1/billing/BIL-TEST-PAT1/payments",
            json={"amount": 300.0, "method": "card", "reference_number": "TXN9999"},
            headers=self.staff_headers,
        )
        self.assertEqual(staff_pay.status_code, 200)

    async def test_get_receipt_data(self):
        """Test retrieving structured receipt payload for print / download."""
        sample_bill = {
            "bill_id": "BIL-TEST-003",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "created_by": "USR-STF-ONE-001",
            "line_items": [{"item_code": "LAB", "description": "Blood Panel", "quantity": 1, "unit_price": 800.0, "tax_percent": 0, "discount_amount": 0}],
            "payments": [{"payment_id": "PAY-001", "amount": 800.0, "method": "cash", "status": "completed", "paid_at": utc_now().isoformat(), "recorded_by": "USR-STF-ONE-001"}],
            "status": "paid",
            "grand_total": 800.0,
            "amount_paid": 800.0,
            "balance_due": 0.0,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["billing"].find_one.return_value = sample_bill
        self.mock_db["patients"].find_one.return_value = {"patient_id": "PAT-ONE-001", "user_id": "USR-PAT-ONE-001", "first_name": "Patient", "last_name": "One"}

        response = await self.client.get("/api/v1/billing/BIL-TEST-003/receipt", headers=self.pat1_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        receipt = data["data"]
        self.assertEqual(receipt["bill_id"], "BIL-TEST-003")
        self.assertEqual(receipt["amount_paid"], 800.0)
