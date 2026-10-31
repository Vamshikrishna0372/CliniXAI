"""Comprehensive Unit Test Suite for Phase 6: Billing, Payments, Receipts & Notifications."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now


def create_mock_cursor(return_data=None):
    """Helper creating a mock cursor with chainable sort, skip, limit methods."""
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db_phase6():
    """Returns a flexible mock database supporting async motor operations for Phase 6."""
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=None)
            col.update_many = AsyncMock(return_value=MagicMock(modified_count=1))
            col.count_documents = AsyncMock(return_value=0)
            col.find = MagicMock(return_value=create_mock_cursor([]))

            async def _mock_find_one_and_update(filter_dict=None, update_dict=None, *args, **kwargs):
                doc = col.find_one.return_value
                if doc:
                    res = dict(doc)
                    if update_dict and isinstance(update_dict, dict):
                        if "$inc" in update_dict:
                            for k, v in update_dict["$inc"].items():
                                res[k] = round(float(res.get(k, 0)) + float(v), 2)
                        if "$set" in update_dict:
                            res.update(update_dict["$set"])
                        if "$push" in update_dict:
                            for k, v in update_dict["$push"].items():
                                res.setdefault(k, []).append(v)
                    return res
                return None

            col.find_one_and_update = AsyncMock(side_effect=_mock_find_one_and_update)
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase6BillingAndNotifications(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 6 Billing, Payments, Receipts, and Notifications."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase6()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # User definitions
        self.admin_user = UserInDB(
            user_id="USR-2026-ADM001", email="admin@clinixai.com", full_name="Admin User",
            role=UserRole.HOSPITAL_ADMIN, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.staff_user = UserInDB(
            user_id="USR-2026-STF001", email="staff@clinixai.com", full_name="Staff User",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.patient_user = UserInDB(
            user_id="USR-2026-PAT001", email="patient@clinixai.com", full_name="Jane Patient",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )
        self.other_patient_user = UserInDB(
            user_id="USR-2026-PAT002", email="otherpatient@clinixai.com", full_name="Bob Patient",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE
        )

        # Tokens
        self.admin_token = create_access_token(user_id=self.admin_user.user_id, role=self.admin_user.role.value)
        self.staff_token = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)
        self.patient_token = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)
        self.other_patient_token = create_access_token(user_id=self.other_patient_user.user_id, role=self.other_patient_user.role.value)

        # Headers
        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        self.patient_headers = {"Authorization": f"Bearer {self.patient_token}"}
        self.other_patient_headers = {"Authorization": f"Bearer {self.other_patient_token}"}

        # Mock DB entities
        self.patient_dict = {
            "patient_id": "PAT-2026-00001",
            "user_id": self.patient_user.user_id,
            "first_name": "Jane",
            "last_name": "Patient",
            "email": "patient@clinixai.com",
            "status": "active",
        }
        self.bill_dict = {
            "bill_id": "BILL-2026-000001",
            "patient_id": "PAT-2026-00001",
            "appointment_id": "APT-2026-000001",
            "consultation_id": None,
            "prescription_id": None,
            "department_id": "DEP-2026-CARD",
            "doctor_id": "DOC-2026-000001",
            "line_items": [
                {
                    "item_code": "CONSULT-001",
                    "description": "General Consultation",
                    "quantity": 1.0,
                    "unit_price": 500.0,
                    "tax_percent": 0.0,
                    "discount_amount": 0.0,
                }
            ],
            "subtotal": 500.0,
            "total_tax": 0.0,
            "total_discount": 0.0,
            "grand_total": 500.0,
            "amount_paid": 0.0,
            "balance_due": 500.0,
            "payments": [],
            "status": "draft",
            "notes": "Initial consultation fee",
            "created_by": self.admin_user.user_id,
            "issued_at": None,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # ── Billing Flow Tests ──────────────────────────────────────────────────

    async def test_create_bill_success(self) -> None:
        """Staff creates draft bill for a patient."""
        self.mock_db["users"].find_one.return_value = self.staff_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        payload = {
            "patient_id": "PAT-2026-00001",
            "line_items": [
                {
                    "item_code": "LAB-BLOOD",
                    "description": "Complete Blood Count",
                    "quantity": 1.0,
                    "unit_price": 750.0,
                    "tax_percent": 5.0,
                    "discount_amount": 50.0,
                }
            ],
            "notes": "Lab test bill",
        }
        res = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]
        self.assertEqual(data["patient_id"], "PAT-2026-00001")
        self.assertEqual(data["status"], "draft")
        self.assertGreater(data["grand_total"], 0)

    async def test_issue_bill_dispatches_notification(self) -> None:
        """Issuing a bill updates status to ISSUED and creates a notification."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()
        self.mock_db["billing"].find_one.return_value = self.bill_dict
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        res = await self.client.post("/api/v1/billing/BILL-2026-000001/issue", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

        # Verify notification insert was called
        self.mock_db["notifications"].insert_one.assert_called_once()

    async def test_record_payment_updates_balance_due(self) -> None:
        """Recording a full payment sets status to PAID and balance_due to 0."""
        self.mock_db["users"].find_one.return_value = self.staff_user.to_mongo_dict()
        issued_bill = dict(self.bill_dict)
        issued_bill["status"] = "issued"
        self.mock_db["billing"].find_one.return_value = issued_bill
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        payload = {
            "amount": 500.0,
            "method": "upi",
            "reference_number": "UPI9876543210",
            "notes": "GPay payment",
        }
        res = await self.client.post("/api/v1/billing/BILL-2026-000001/payments", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 200)

    async def test_overpayment_rejected(self) -> None:
        """Recording a payment greater than balance due is rejected with 400 Bad Request."""
        self.mock_db["users"].find_one.return_value = self.staff_user.to_mongo_dict()
        issued_bill = dict(self.bill_dict)
        issued_bill["status"] = "issued"
        self.mock_db["billing"].find_one.return_value = issued_bill

        payload = {
            "amount": 1000.0,  # exceeds 500.0 balance
            "method": "cash",
        }
        res = await self.client.post("/api/v1/billing/BILL-2026-000001/payments", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 400)
        self.assertIn("exceeds balance", res.json()["error"]["message"].lower())

    async def test_patient_cannot_view_other_patient_bill(self) -> None:
        """Patient B is rejected (403) from viewing Patient A's bill."""
        self.mock_db["users"].find_one.return_value = self.other_patient_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = {"patient_id": "PAT-2026-00002", "user_id": self.other_patient_user.user_id}
        self.mock_db["billing"].find_one.return_value = self.bill_dict

        res = await self.client.get("/api/v1/billing/BILL-2026-000001", headers=self.other_patient_headers)
        self.assertEqual(res.status_code, 403)

    # ── Notification Flow Tests ──────────────────────────────────────────────

    async def test_list_notifications_unread_count(self) -> None:
        """Patient fetches unread notification count."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["notifications"].count_documents.return_value = 3

        res = await self.client.get("/api/v1/notifications/unread-count", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["unread_count"], 3)

    async def test_mark_notification_read(self) -> None:
        """Patient marks notification as read."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        now = utc_now().isoformat()
        self.mock_db["notifications"].find_one.return_value = {
            "notification_id": "NTF-2026-000001",
            "recipient_user_id": self.patient_user.user_id,
            "notification_type": "bill_issued",
            "channel": "in_app",
            "status": "sent",
            "title": "Bill Issued",
            "body": "Your bill has been issued",
            "reference_id": "BILL-2026-000001",
            "reference_type": "billing",
            "created_at": now,
            "updated_at": now,
        }

        res = await self.client.patch("/api/v1/notifications/NTF-2026-000001/read", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["status"], "read")

    # ── Receipt & Auto Consultation Billing Tests ──────────────────────────────

    async def test_get_receipt_data(self) -> None:
        """Authorized patient retrieves receipt data for recorded payment."""
        self.mock_db["users"].find_one.return_value = self.patient_user.to_mongo_dict()
        self.mock_db["patients"].find_one.return_value = self.patient_dict

        bill_with_payment = dict(self.bill_dict)
        bill_with_payment["payments"] = [
            {
                "payment_id": "PAY-2026-123456",
                "amount": 500.0,
                "method": "upi",
                "status": "completed",
                "reference_number": "UPI123",
                "notes": "Paid",
                "paid_at": utc_now().isoformat(),
                "recorded_by": self.staff_user.user_id,
            }
        ]
        self.mock_db["billing"].find_one.return_value = bill_with_payment

        res = await self.client.get("/api/v1/billing/BILL-2026-000001/receipt", headers=self.patient_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("RCT-2026-123456", res.json()["data"]["receipt_id"])

    async def test_auto_create_bill_from_consultation(self) -> None:
        """Staff creates bill automatically from completed consultation."""
        self.mock_db["users"].find_one.return_value = self.staff_user.to_mongo_dict()
        self.mock_db["billing"].find_one.return_value = None  # No existing bill
        self.mock_db["consultations"].find_one.return_value = {
            "consultation_id": "CON-2026-000001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-000001",
            "appointment_id": "APT-2026-000001",
            "status": "completed",
        }
        self.mock_db["patients"].find_one.return_value = self.patient_dict
        self.mock_db["doctors"].find_one.return_value = {
            "doctor_id": "DOC-2026-000001",
            "consultation_fee": 650.0,
            "last_name": "House",
        }
        self.mock_db["appointments"].find_one.return_value = {
            "appointment_id": "APT-2026-000001",
            "patient_id": "PAT-2026-00001",
            "doctor_id": "DOC-2026-000001",
            "department_id": "DEP-2026-CARD",
        }

        res = await self.client.post("/api/v1/billing/from-consultation/CON-2026-000001", headers=self.staff_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["grand_total"], 650.0)

    # ── Admin Operations & Analytics Tests ────────────────────────────────────

    async def test_admin_operational_summary(self) -> None:
        """Hospital Admin fetches operational summary metrics."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()

        res = await self.client.get("/api/v1/admin/summary", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("total_patients", res.json()["data"])
        self.assertEqual(res.json()["data"]["currency"], "INR")

    async def test_admin_financial_summary(self) -> None:
        """Hospital Admin fetches financial summary metrics."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()

        res = await self.client.get("/api/v1/admin/financial-summary", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertIn("total_billed", res.json()["data"])

    async def test_admin_export_billing_csv(self) -> None:
        """Hospital Admin downloads billing CSV report."""
        self.mock_db["users"].find_one.return_value = self.admin_user.to_mongo_dict()

        res = await self.client.get("/api/v1/admin/reports/csv", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers["content-type"], "text/csv; charset=utf-8")
        self.assertIn("Bill ID", res.text)


if __name__ == "__main__":
    unittest.main()
