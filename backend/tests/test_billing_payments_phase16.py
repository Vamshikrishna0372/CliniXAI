"""Dedicated Comprehensive Test Suite for CliniXAI Phase 16: Billing & Payments.

Covers Sections A through M (all 92 items):
A. Authentication (1-5)
B. RBAC (6-15)
C. Relationships (16-23)
D. Money & Calculations (24-36)
E. Offline Payments (37-46)
F. Duplicate / Idempotency (47-50)
G. Concurrency (51-54)
H. Security, IDOR, Mass Assignment, XSS (55-66)
I. Persistence & Snapshot Safety (67-72)
J. Audit Logging (73-79)
K. Financial Integrity (80-85)
L. AI / Clinical Boundary Immutability (86-88)
M. History, Pagination & Filtering (89-92)
"""

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.billing import BillingStatus, PaymentMethod, PaymentStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now
from app.database.collections import (
    COLLECTION_BILLING, COLLECTION_PAYMENTS, COLLECTION_PATIENTS,
    COLLECTION_DOCTORS, COLLECTION_CONSULTATIONS, COLLECTION_APPOINTMENTS,
    COLLECTION_AI_ANALYSES, COLLECTION_PRESCRIPTIONS, COLLECTION_AUDIT_LOGS
)


class TestBillingPaymentsPhase16(unittest.IsolatedAsyncioTestCase):
    """Phase 16 Master Test Suite."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        # In-memory collections dictionary
        self.collections = {
            COLLECTION_BILLING: {},
            COLLECTION_PAYMENTS: {},
            COLLECTION_PATIENTS: {},
            COLLECTION_DOCTORS: {},
            COLLECTION_CONSULTATIONS: {},
            COLLECTION_APPOINTMENTS: {},
            COLLECTION_AI_ANALYSES: {},
            COLLECTION_PRESCRIPTIONS: {},
            COLLECTION_AUDIT_LOGS: {},
            "users": {},
        }

        # Mock DB implementation backed by self.collections
        self.mock_db = MagicMock()

        def get_col(name):
            col = MagicMock()
            col_store = self.collections.get(name, {})

            async def find_one(query, *args, **kwargs):
                for doc in reversed(list(col_store.values())):
                    matches = True
                    for k, v in query.items():
                        if k == "is_deleted" and isinstance(v, dict) and "$ne" in v:
                            if doc.get("is_deleted") == v["$ne"]:
                                matches = False; break
                        elif k == "status" and isinstance(v, dict) and "$ne" in v:
                            if doc.get("status") == v["$ne"]:
                                matches = False; break
                        elif k == "status" and isinstance(v, dict) and "$in" in v:
                            if doc.get("status") not in v["$in"]:
                                matches = False; break
                        elif k == "$or":
                            or_matches = any(doc.get(sub_k) == sub_v for cond in v for sub_k, sub_v in cond.items())
                            if not or_matches: matches = False; break
                        elif doc.get(k) != v:
                            matches = False
                            break
                    if matches:
                        return dict(doc)
                return None

            async def insert_one(doc, *args, **kwargs):
                d = dict(doc)
                key = d.get("audit_id") or d.get("bill_id") or d.get("payment_id") or d.get("patient_id") or d.get("consultation_id") or d.get("appointment_id") or d.get("prescription_id") or d.get("user_id") or str(len(col_store))
                col_store[key] = d
                res = MagicMock()
                res.inserted_id = "test-id"
                return res

            async def update_one(query, update, *args, **kwargs):
                target = None
                for doc in col_store.values():
                    if all(doc.get(k) == v for k, v in query.items() if not k.startswith("$")):
                        target = doc
                        break
                if target:
                    if "$set" in update:
                        target.update(update["$set"])
                    if "$push" in update:
                        for field, val in update["$push"].items():
                            target.setdefault(field, []).append(val)
                    return MagicMock(modified_count=1)
                return MagicMock(modified_count=0)

            async def find_one_and_update(query, update, *args, **kwargs):
                target = None
                for doc in col_store.values():
                    matches = True
                    for k, v in query.items():
                        if k == "is_deleted" and isinstance(v, dict) and "$ne" in v:
                            if doc.get("is_deleted") == v["$ne"]: matches = False; break
                        elif k == "status" and isinstance(v, dict) and "$in" in v:
                            if doc.get("status") not in v["$in"]: matches = False; break
                        elif k == "status" and isinstance(v, dict) and "$ne" in v:
                            if doc.get("status") == v["$ne"]: matches = False; break
                        elif k == "balance_due" and isinstance(v, dict) and "$gte" in v:
                            if doc.get("balance_due", 0.0) < v["$gte"]: matches = False; break
                        elif doc.get(k) != v:
                            matches = False; break
                    if matches:
                        target = doc
                        break
                if not target:
                    return None

                doc_before = dict(target)

                if "$set" in update:
                    target.update(update["$set"])
                if "$inc" in update:
                    for field, inc_val in update["$inc"].items():
                        target[field] = round(target.get(field, 0.0) + inc_val, 2)
                if "$push" in update:
                    for field, val in update["$push"].items():
                        target.setdefault(field, []).append(val)
                if "$pull" in update:
                    for field, cond in update["$pull"].items():
                        if field in target and isinstance(target[field], list):
                            if isinstance(cond, dict):
                                target[field] = [
                                    item for item in target[field]
                                    if not all(item.get(ck) == cv for ck, cv in cond.items())
                                ]

                from pymongo import ReturnDocument
                ret_doc = kwargs.get("return_document")
                if ret_doc == ReturnDocument.BEFORE:
                    return doc_before
                return dict(target)

            async def count_documents(query, *args, **kwargs):
                count = 0
                for doc in col_store.values():
                    matches = True
                    for k, v in query.items():
                        if k == "is_deleted" and isinstance(v, dict) and "$ne" in v:
                            if doc.get("is_deleted") == v["$ne"]: matches = False; break
                        elif k == "status" and isinstance(v, dict) and "$ne" in v:
                            if doc.get("status") == v["$ne"]: matches = False; break
                        elif doc.get(k) != v:
                            matches = False; break
                    if matches: count += 1
                return count

            def find(query, *args, **kwargs):
                matched = []
                for doc in col_store.values():
                    matches = True
                    for k, v in query.items():
                        if k == "is_deleted" and isinstance(v, dict) and "$ne" in v:
                            if doc.get("is_deleted") == v["$ne"]: matches = False; break
                        elif k == "status" and isinstance(v, dict) and "$ne" in v:
                            if doc.get("status") == v["$ne"]: matches = False; break
                        elif doc.get(k) != v:
                            matches = False; break
                    if matches: matched.append(dict(doc))
                
                class MockCursor:
                    def __init__(self, data):
                        self._data = list(data)
                        self._skip = 0
                        self._limit = len(data)

                    def sort(self, *args, **kwargs):
                        return self

                    def skip(self, n):
                        self._skip = n
                        return self

                    def limit(self, n):
                        self._limit = n
                        return self

                    async def to_list(self, length=None):
                        sliced = self._data[self._skip : self._skip + self._limit]
                        if length is not None:
                            sliced = sliced[:length]
                        return sliced

                return MockCursor(matched)

            col.find_one = AsyncMock(side_effect=find_one)
            col.insert_one = AsyncMock(side_effect=insert_one)
            col.update_one = AsyncMock(side_effect=update_one)
            col.find_one_and_update = AsyncMock(side_effect=find_one_and_update)
            col.count_documents = AsyncMock(side_effect=count_documents)
            col.find = MagicMock(side_effect=find)
            return col

        self.mock_db.__getitem__.side_effect = get_col
        app.dependency_overrides[get_database] = lambda: self.mock_db

        # Users
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

        for u in (self.admin_user, self.staff_user, self.pat_user_1, self.pat_user_2, self.doc_user):
            self.collections["users"][u.user_id] = u.to_mongo_dict()

        # Patients
        self.pat_1_record = {"patient_id": "PAT-ONE-001", "user_id": self.pat_user_1.user_id, "first_name": "Patient", "last_name": "One"}
        self.pat_2_record = {"patient_id": "PAT-TWO-002", "user_id": self.pat_user_2.user_id, "first_name": "Patient", "last_name": "Two"}
        self.collections[COLLECTION_PATIENTS]["PAT-ONE-001"] = self.pat_1_record
        self.collections[COLLECTION_PATIENTS]["PAT-TWO-002"] = self.pat_2_record

        # Doctor
        self.doc_record = {
            "doctor_id": "DOC-RAO-001",
            "user_id": self.doc_user.user_id,
            "first_name": "Arjun",
            "last_name": "Rao",
            "full_name": "Dr. Arjun Rao",
            "email": "doctor.arjun@clinixai.com",
            "consultation_fee": 750.0,
            "status": "active",
            "is_deleted": False,
        }
        self.collections[COLLECTION_DOCTORS]["DOC-RAO-001"] = self.doc_record

        # Encounters
        self.consult_record = {
            "consultation_id": "CON-2026-1001",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "appointment_id": "APT-2026-1001",
            "status": "completed",
            "clinical_notes": "Patient fully evaluated."
        }
        self.collections[COLLECTION_CONSULTATIONS]["CON-2026-1001"] = self.consult_record

        self.apt_record = {
            "appointment_id": "APT-2026-1001",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "department_id": "DEPT-CARD",
            "appointment_date": "2026-09-28",
            "start_time": "10:00",
            "end_time": "10:30",
            "reason": "Cardiac checkup",
            "appointment_type": "new_consultation",
            "booking_source": "patient",
            "status": "completed",
            "is_deleted": False,
        }
        self.collections[COLLECTION_APPOINTMENTS]["APT-2026-1001"] = self.apt_record

        # Tokens & Headers
        self.admin_headers = {"Authorization": f"Bearer {create_access_token(self.admin_user.user_id, self.admin_user.role.value)}"}
        self.staff_headers = {"Authorization": f"Bearer {create_access_token(self.staff_user.user_id, self.staff_user.role.value)}"}
        self.pat1_headers = {"Authorization": f"Bearer {create_access_token(self.pat_user_1.user_id, self.pat_user_1.role.value)}"}
        self.pat2_headers = {"Authorization": f"Bearer {create_access_token(self.pat_user_2.user_id, self.pat_user_2.role.value)}"}
        self.doc_headers = {"Authorization": f"Bearer {create_access_token(self.doc_user.user_id, self.doc_user.role.value)}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION A: AUTHENTICATION (Items 1-5)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_01_unauthenticated_bill_list(self):
        res = await self.client.get("/api/v1/billing")
        self.assertEqual(res.status_code, 401)

    async def test_02_unauthenticated_bill_detail(self):
        res = await self.client.get("/api/v1/billing/BILL-2026-000001")
        self.assertEqual(res.status_code, 401)

    async def test_03_unauthenticated_bill_create(self):
        res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Fee", "unit_price": 500}]})
        self.assertEqual(res.status_code, 401)

    async def test_04_unauthenticated_payment(self):
        res = await self.client.post("/api/v1/billing/BILL-2026-000001/payments", json={"amount": 500, "method": "cash"})
        self.assertEqual(res.status_code, 401)

    async def test_05_unauthenticated_cancellation_or_void(self):
        res1 = await self.client.post("/api/v1/billing/BILL-2026-000001/cancel")
        self.assertEqual(res1.status_code, 401)
        res2 = await self.client.post("/api/v1/billing/BILL-2026-000001/payments/PAY-001/void", json={"reason": "Error"})
        self.assertEqual(res2.status_code, 401)

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION B: RBAC (Items 6-15)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_06_staff_bill_creation(self):
        payload = {"patient_id": "PAT-ONE-001", "line_items": [{"description": "General Checkup", "unit_price": 600, "quantity": 1}]}
        res = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]
        self.assertTrue(data["bill_id"].startswith("BILL-"))
        self.assertEqual(data["grand_total"], 600.0)
        self.assertEqual(data["created_by"], self.staff_user.user_id)

    async def test_07_staff_payment_recording(self):
        # Create bill
        b_res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "X-Ray", "unit_price": 400}]}, headers=self.staff_headers)
        bill_id = b_res.json()["data"]["bill_id"]
        # Staff records cash payment
        p_res = await self.client.post(f"/api/v1/billing/{bill_id}/payments", json={"amount": 400, "method": "cash"}, headers=self.staff_headers)
        self.assertEqual(p_res.status_code, 200)
        self.assertEqual(p_res.json()["data"]["status"], "paid")
        self.assertEqual(p_res.json()["data"]["amount_paid"], 400.0)

    async def test_08_staff_history(self):
        await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Test", "unit_price": 100}]}, headers=self.staff_headers)
        res = await self.client.get("/api/v1/billing", headers=self.staff_headers)
        self.assertEqual(res.status_code, 200)
        self.assertGreaterEqual(len(res.json()["data"]), 1)

    async def test_09_patient_own_access(self):
        b_res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Test", "unit_price": 200}]}, headers=self.staff_headers)
        bill_id = b_res.json()["data"]["bill_id"]
        res = await self.client.get(f"/api/v1/billing/{bill_id}", headers=self.pat1_headers)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["data"]["bill_id"], bill_id)

    async def test_10_patient_other_access_denied(self):
        b_res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Test", "unit_price": 200}]}, headers=self.staff_headers)
        bill_id = b_res.json()["data"]["bill_id"]
        res = await self.client.get(f"/api/v1/billing/{bill_id}", headers=self.pat2_headers)
        self.assertEqual(res.status_code, 403)

    async def test_11_patient_create_denied(self):
        res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Test", "unit_price": 200}]}, headers=self.pat1_headers)
        self.assertEqual(res.status_code, 403)

    async def test_12_patient_payment_denied(self):
        b_res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Test", "unit_price": 200}]}, headers=self.staff_headers)
        bill_id = b_res.json()["data"]["bill_id"]
        # Patient cannot record payment in offline hospital billing
        res = await self.client.post(f"/api/v1/billing/{bill_id}/payments", json={"amount": 200, "method": "cash"}, headers=self.pat1_headers)
        self.assertEqual(res.status_code, 403)

    async def test_13_doctor_billing_restrictions(self):
        # Doctor cannot create arbitrary manual bills
        res1 = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Test", "unit_price": 200}]}, headers=self.doc_headers)
        self.assertEqual(res1.status_code, 403)
        # Doctor cannot record payment
        b_res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Test", "unit_price": 200}]}, headers=self.staff_headers)
        bill_id = b_res.json()["data"]["bill_id"]
        res2 = await self.client.post(f"/api/v1/billing/{bill_id}/payments", json={"amount": 200, "method": "cash"}, headers=self.doc_headers)
        self.assertEqual(res2.status_code, 403)

    async def test_14_admin_policy(self):
        b_res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Admin bill", "unit_price": 1000}]}, headers=self.admin_headers)
        self.assertEqual(b_res.status_code, 201)
        bill_id = b_res.json()["data"]["bill_id"]
        p_res = await self.client.post(f"/api/v1/billing/{bill_id}/payments", json={"amount": 500, "method": "card", "reference_number": "AUTH-123"}, headers=self.admin_headers)
        self.assertEqual(p_res.status_code, 200)

    async def test_15_cross_role_manipulation(self):
        # Patient tries to cancel bill
        b_res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Fee", "unit_price": 300}]}, headers=self.staff_headers)
        bill_id = b_res.json()["data"]["bill_id"]
        c_res = await self.client.post(f"/api/v1/billing/{bill_id}/cancel", headers=self.pat1_headers)
        self.assertEqual(c_res.status_code, 403)

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION C: RELATIONSHIPS (Items 16-23)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_16_consultation_linkage(self):
        res = await self.client.post(
            "/api/v1/billing",
            json={"consultation_id": "CON-2026-1001", "line_items": [{"description": "Consultation", "unit_price": 750}]},
            headers=self.staff_headers
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]
        self.assertEqual(data["consultation_id"], "CON-2026-1001")
        self.assertEqual(data["patient_id"], "PAT-ONE-001")

    async def test_17_appointment_linkage(self):
        res = await self.client.post(
            "/api/v1/billing",
            json={"patient_id": "PAT-ONE-001", "appointment_id": "APT-2026-1001", "line_items": [{"description": "Service", "unit_price": 250}]},
            headers=self.staff_headers
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["appointment_id"], "APT-2026-1001")

    async def test_18_patient_linkage(self):
        res = await self.client.post(
            "/api/v1/billing",
            json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Visit", "unit_price": 300}]},
            headers=self.staff_headers
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["patient_id"], "PAT-ONE-001")

    async def test_19_invalid_consultation(self):
        res = await self.client.post(
            "/api/v1/billing",
            json={"consultation_id": "CON-DOES-NOT-EXIST", "line_items": [{"description": "Test", "unit_price": 500}]},
            headers=self.staff_headers
        )
        self.assertEqual(res.status_code, 404)

    async def test_20_cancelled_consultation(self):
        self.collections[COLLECTION_CONSULTATIONS]["CON-CANCELLED"] = {
            "consultation_id": "CON-CANCELLED",
            "patient_id": "PAT-ONE-001",
            "status": "cancelled",
        }
        res = await self.client.post(
            "/api/v1/billing",
            json={"consultation_id": "CON-CANCELLED", "line_items": [{"description": "Test", "unit_price": 500}]},
            headers=self.staff_headers
        )
        self.assertEqual(res.status_code, 400)

    async def test_21_mismatched_patient(self):
        res = await self.client.post(
            "/api/v1/billing",
            json={"consultation_id": "CON-2026-1001", "patient_id": "PAT-TWO-002", "line_items": [{"description": "Test", "unit_price": 500}]},
            headers=self.staff_headers
        )
        self.assertEqual(res.status_code, 400)

    async def test_22_mismatched_appointment(self):
        res = await self.client.post(
            "/api/v1/billing",
            json={"patient_id": "PAT-TWO-002", "appointment_id": "APT-2026-1001", "line_items": [{"description": "Test", "unit_price": 500}]},
            headers=self.staff_headers
        )
        self.assertEqual(res.status_code, 400)

    async def test_23_prescription_does_not_automatically_create_medication_charge(self):
        # A prescription exists but bill line items are strictly staff authorable
        res = await self.client.post(
            "/api/v1/billing",
            json={"patient_id": "PAT-ONE-001", "prescription_id": "RX-2026-001", "line_items": [{"description": "Clinical Consult", "unit_price": 500}]},
            headers=self.staff_headers
        )
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]
        self.assertEqual(len(data["line_items"]), 1)
        self.assertEqual(data["grand_total"], 500.0)

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION D: MONEY & CALCULATIONS (Items 24-36)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_24_to_29_financial_calculations(self):
        # Line item: qty 2 * 300 = 600, discount 50 -> subtotal 600, discount 50, grand_total 550
        payload = {
            "patient_id": "PAT-ONE-001",
            "line_items": [{"description": "Service A", "quantity": 2, "unit_price": 300.0}],
            "discount": 50.0,
        }
        res = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 201)
        b = res.json()["data"]
        self.assertEqual(b["subtotal"], 600.0)
        self.assertEqual(b["total_discount"], 50.0)
        self.assertEqual(b["grand_total"], 550.0)
        self.assertEqual(b["balance_due"], 550.0)
        self.assertEqual(b["amount_paid"], 0.0)

        # Record partial payment
        p_res = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 200.0, "method": "cash"}, headers=self.staff_headers)
        p_data = p_res.json()["data"]
        self.assertEqual(p_data["amount_paid"], 200.0)
        self.assertEqual(p_data["balance_due"], 350.0)
        self.assertEqual(p_data["status"], "partially_paid")

    async def test_30_inr_consistency(self):
        res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Test", "unit_price": 100}]}, headers=self.staff_headers)
        self.assertEqual(res.json()["data"]["currency"], "INR")

    async def test_31_decimal_precision(self):
        payload = {
            "patient_id": "PAT-ONE-001",
            "line_items": [{"description": "Item", "quantity": 3, "unit_price": 33.33}],
        }
        res = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()["data"]["grand_total"], 99.99)

    async def test_32_negative_amount_rejection(self):
        payload = {"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": -50.0}]}
        res = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 422)

    async def test_33_zero_amount_rejection(self):
        b_res = await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 100.0}]}, headers=self.staff_headers)
        bill_id = b_res.json()["data"]["bill_id"]
        p_res = await self.client.post(f"/api/v1/billing/{bill_id}/payments", json={"amount": 0.0, "method": "cash"}, headers=self.staff_headers)
        self.assertEqual(p_res.status_code, 422)

    async def test_34_invalid_quantity(self):
        payload = {"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "quantity": 0, "unit_price": 50.0}]}
        res = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 422)

    async def test_35_invalid_discount(self):
        payload = {"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 100.0}], "discount": -10.0}
        res = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 422)

    async def test_36_discount_greater_than_subtotal(self):
        payload = {"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 100.0}], "discount": 150.0}
        res = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 400)

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION E: OFFLINE PAYMENTS (Items 37-46)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_37_to_39_payment_methods(self):
        # CASH
        b1 = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 100}]}, headers=self.staff_headers)).json()["data"]
        p1 = await self.client.post(f"/api/v1/billing/{b1['bill_id']}/payments", json={"amount": 100, "method": "cash"}, headers=self.staff_headers)
        self.assertEqual(p1.status_code, 200)

        # UPI
        b2 = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 200}]}, headers=self.staff_headers)).json()["data"]
        p2 = await self.client.post(f"/api/v1/billing/{b2['bill_id']}/payments", json={"amount": 200, "method": "upi", "reference_number": "UPI-UTR-999"}, headers=self.staff_headers)
        self.assertEqual(p2.status_code, 200)

        # CARD
        b3 = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 300}]}, headers=self.staff_headers)).json()["data"]
        p3 = await self.client.post(f"/api/v1/billing/{b3['bill_id']}/payments", json={"amount": 300, "method": "card", "reference_number": "CARD-AUTH-888"}, headers=self.staff_headers)
        self.assertEqual(p3.status_code, 200)

    async def test_40_and_41_partial_and_full_payment(self):
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Consultation", "unit_price": 1000}]}, headers=self.staff_headers)).json()["data"]
        # Partial
        p1 = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 400, "method": "cash"}, headers=self.staff_headers)
        self.assertEqual(p1.json()["data"]["status"], "partially_paid")
        self.assertEqual(p1.json()["data"]["balance_due"], 600.0)
        # Full
        p2 = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 600, "method": "upi"}, headers=self.staff_headers)
        self.assertEqual(p2.json()["data"]["status"], "paid")
        self.assertEqual(p2.json()["data"]["balance_due"], 0.0)

    async def test_42_overpayment_rejection(self):
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Consultation", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        res = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 550, "method": "cash"}, headers=self.staff_headers)
        self.assertEqual(res.status_code, 400)

    async def test_43_invalid_payment_method(self):
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Consultation", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        res1 = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 100, "method": "bitcoin"}, headers=self.staff_headers)
        self.assertEqual(res1.status_code, 422)
        res2 = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 100, "method": "razorpay"}, headers=self.staff_headers)
        self.assertEqual(res2.status_code, 422)

    async def test_44_payment_reference_validation(self):
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 200}]}, headers=self.staff_headers)).json()["data"]
        # Overly long reference (>100 chars)
        res = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 100, "method": "upi", "reference_number": "A" * 150}, headers=self.staff_headers)
        self.assertEqual(res.status_code, 422)

    async def test_45_payment_immutability(self):
        # No PUT endpoint exists to rewrite recorded payment fields
        res = await self.client.put("/api/v1/billing/BILL-1/payments/PAY-1", json={"amount": 1000}, headers=self.staff_headers)
        self.assertIn(res.status_code, (404, 405))

    async def test_46_payment_voiding(self):
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        p_res = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 500, "method": "cash"}, headers=self.staff_headers)
        payment_id = p_res.json()["data"]["payments"][0]["payment_id"]
        # Void payment
        v_res = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments/{payment_id}/void", json={"reason": "Cash entered in error"}, headers=self.staff_headers)
        self.assertEqual(v_res.status_code, 200)
        v_data = v_res.json()["data"]
        self.assertEqual(v_data["balance_due"], 500.0)
        self.assertEqual(v_data["amount_paid"], 0.0)
        self.assertNotEqual(v_data["status"], "paid")

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION F: DUPLICATE / IDEMPOTENCY (Items 47-50)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_47_and_48_duplicate_bill_and_idempotency(self):
        # Consultation duplicate bill protection
        b1 = (await self.client.post("/api/v1/billing", json={"consultation_id": "CON-2026-1001", "line_items": [{"description": "Item", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        b2 = (await self.client.post("/api/v1/billing", json={"consultation_id": "CON-2026-1001", "line_items": [{"description": "Item", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        self.assertEqual(b1["bill_id"], b2["bill_id"])

        # Idempotency key
        b3 = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 500}], "idempotency_key": "IDEM-KEY-001"}, headers=self.staff_headers)).json()["data"]
        b4 = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 500}], "idempotency_key": "IDEM-KEY-001"}, headers=self.staff_headers)).json()["data"]
        self.assertEqual(b3["bill_id"], b4["bill_id"])

    async def test_49_and_50_duplicate_payment_and_retry_safe(self):
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 1000}]}, headers=self.staff_headers)).json()["data"]
        ref = "UTR-IDEM-999"
        # First payment
        p1 = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 500, "method": "upi", "reference_number": ref}, headers=self.staff_headers)
        self.assertEqual(p1.status_code, 200)
        # Duplicate retry with same reference
        p2 = await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 500, "method": "upi", "reference_number": ref}, headers=self.staff_headers)
        self.assertEqual(p2.status_code, 200)
        self.assertEqual(len(p2.json()["data"]["payments"]), 1)
        self.assertEqual(p2.json()["data"]["amount_paid"], 500.0)

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION G: CONCURRENCY (Items 51-54)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_51_simultaneous_bill_creation(self):
        req1 = self.client.post("/api/v1/billing", json={"consultation_id": "CON-2026-1001", "line_items": [{"description": "Fee", "unit_price": 750}]}, headers=self.staff_headers)
        req2 = self.client.post("/api/v1/billing", json={"consultation_id": "CON-2026-1001", "line_items": [{"description": "Fee", "unit_price": 750}]}, headers=self.staff_headers)
        r1, r2 = await asyncio.gather(req1, req2)
        self.assertIn(r1.status_code, (200, 201))
        self.assertIn(r2.status_code, (200, 201))
        self.assertEqual(r1.json()["data"]["bill_id"], r2.json()["data"]["bill_id"])

    async def test_52_simultaneous_payments(self):
        # Balance = 1000. Payment A = 600, Payment B = 400 -> Paid = 1000, Balance = 0, Status = PAID
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Procedure", "unit_price": 1000}]}, headers=self.staff_headers)).json()["data"]
        req1 = self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 600, "method": "cash"}, headers=self.staff_headers)
        req2 = self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 400, "method": "upi", "reference_number": "UPI-PARALLEL-1"}, headers=self.staff_headers)
        r1, r2 = await asyncio.gather(req1, req2)
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        final_bill = (await self.client.get(f"/api/v1/billing/{b['bill_id']}", headers=self.staff_headers)).json()["data"]
        self.assertEqual(final_bill["amount_paid"], 1000.0)
        self.assertEqual(final_bill["balance_due"], 0.0)
        self.assertEqual(final_bill["status"], "paid")

    async def test_53_overpayment_race(self):
        # Balance = 1000. Request A = 700, Request B = 700 -> exactly one succeeds, one rejected (cannot overpay)
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Surgery", "unit_price": 1000}]}, headers=self.staff_headers)).json()["data"]
        req1 = self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 700, "method": "cash"}, headers=self.staff_headers)
        req2 = self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 700, "method": "card", "reference_number": "CARD-RACE"}, headers=self.staff_headers)
        r1, r2 = await asyncio.gather(req1, req2)
        statuses = [r1.status_code, r2.status_code]
        self.assertIn(200, statuses)
        self.assertIn(400, statuses)
        final_bill = (await self.client.get(f"/api/v1/billing/{b['bill_id']}", headers=self.staff_headers)).json()["data"]
        self.assertEqual(final_bill["amount_paid"], 700.0)
        self.assertEqual(final_bill["balance_due"], 300.0)

    async def test_54_simultaneous_cancellation(self):
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        req1 = self.client.post(f"/api/v1/billing/{b['bill_id']}/cancel", json={"reason": "Cancel 1"}, headers=self.staff_headers)
        req2 = self.client.post(f"/api/v1/billing/{b['bill_id']}/cancel", json={"reason": "Cancel 2"}, headers=self.staff_headers)
        r1, r2 = await asyncio.gather(req1, req2)
        statuses = [r1.status_code, r2.status_code]
        self.assertIn(200, statuses)

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION H: SECURITY, IDOR, MASS ASSIGNMENT, XSS (Items 55-66)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_55_idor(self):
        # Patient 1 cannot access Patient 2's bill
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-TWO-002", "line_items": [{"description": "Item", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        res = await self.client.get(f"/api/v1/billing/{b['bill_id']}", headers=self.pat1_headers)
        self.assertEqual(res.status_code, 403)

    async def test_56_to_64_mass_assignment_protection(self):
        # Malicious payload with injected server-controlled fields
        malicious = {
            "bill_id": "BILL-FAKE-12345",
            "patient_id": "PAT-ONE-001",
            "created_by": "ATTACKER",
            "total_amount": 1.0,
            "paid_amount": 999999.0,
            "balance_amount": 0.0,
            "status": "paid",
            "created_at": "2000-01-01T00:00:00Z",
            "line_items": [{"description": "Real service", "unit_price": 500.0}],
        }
        res = await self.client.post("/api/v1/billing", json=malicious, headers=self.staff_headers)
        self.assertEqual(res.status_code, 201)
        data = res.json()["data"]
        self.assertNotEqual(data["bill_id"], "BILL-FAKE-12345")
        self.assertNotEqual(data["created_by"], "ATTACKER")
        self.assertNotEqual(data["status"], "paid")
        self.assertEqual(data["grand_total"], 500.0)
        self.assertEqual(data["amount_paid"], 0.0)
        self.assertEqual(data["balance_due"], 500.0)

    async def test_65_xss_protection(self):
        payload = {
            "patient_id": "PAT-ONE-001",
            "line_items": [{"description": "<script>alert('xss')</script>Blood Test", "unit_price": 200.0}],
            "notes": "<img src=x onerror=alert(1)>",
        }
        res = await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)
        self.assertEqual(res.status_code, 201)
        # Content is stored as plain string and will not execute
        self.assertIn("Blood Test", res.json()["data"]["line_items"][0]["description"])

    async def test_66_mongo_query_injection(self):
        res = await self.client.get('/api/v1/billing?patient_id={"$ne":null}', headers=self.staff_headers)
        self.assertEqual(res.status_code, 200)

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION I: PERSISTENCE & SNAPSHOT SAFETY (Items 67-72)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_67_to_72_persistence_and_stale_snapshot_safety(self):
        # 1. Create bill
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        bill_id = b["bill_id"]

        # 2. Record payment -> status PAID
        await self.client.post(f"/api/v1/billing/{bill_id}/payments", json={"amount": 500, "method": "cash"}, headers=self.staff_headers)

        # 3. Verify in MongoDB
        doc = self.collections[COLLECTION_BILLING][bill_id]
        self.assertEqual(doc["status"], "paid")
        self.assertEqual(doc["amount_paid"], 500.0)

        # 4. Verify in Payments collection
        payment_doc = next(iter(self.collections[COLLECTION_PAYMENTS].values()), None)
        self.assertIsNotNone(payment_doc)
        self.assertEqual(payment_doc["bill_id"], bill_id)

        # 5. Stale snapshot test:
        # Simulate an older disk snapshot with status: "issued"
        from app.database.mongodb import restore_in_memory_snapshot
        stale_bill_snapshot = [dict(doc, status="issued", amount_paid=0.0, balance_due=500.0)]
        with patch("json.load", return_value=stale_bill_snapshot), patch("pathlib.Path.exists", return_value=True):
            # In restore_in_memory_snapshot, atomic $setOnInsert is used, so live document remains PAID
            await restore_in_memory_snapshot(self.mock_db)
            live_doc = self.collections[COLLECTION_BILLING][bill_id]
            self.assertEqual(live_doc["status"], "paid")
            self.assertEqual(live_doc["amount_paid"], 500.0)

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION J: AUDIT LOGGING (Items 73-79)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_73_to_79_audit_logs(self):
        # Bill created audit
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Fee", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        bill_id = b["bill_id"]

        # Payment recorded audit
        p = (await self.client.post(f"/api/v1/billing/{bill_id}/payments", json={"amount": 500, "method": "card", "reference_number": "AUTH-777"}, headers=self.staff_headers)).json()["data"]

        # Check audit logs in collection
        audit_events = list(self.collections[COLLECTION_AUDIT_LOGS].values())
        actions = [ev.get("action") for ev in audit_events]
        self.assertIn("billing.created", actions)
        self.assertIn("payment.recorded", actions)

        # Verify actor identity & no secret leakage
        pmt_audit = next(ev for ev in audit_events if ev.get("action") == "payment.recorded")
        self.assertEqual(pmt_audit["actor_id"], self.staff_user.user_id)
        # Check no sensitive keys
        metadata_str = str(pmt_audit.get("metadata", {}))
        self.assertNotIn("cvv", metadata_str.lower())
        self.assertNotIn("pin", metadata_str.lower())

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION K: FINANCIAL INTEGRITY (Items 80-85)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_80_to_85_financial_reconciliation(self):
        # Multi-item bill with partial payments
        payload = {
            "patient_id": "PAT-ONE-001",
            "line_items": [
                {"description": "Consultation", "quantity": 1, "unit_price": 500.0},
                {"description": "Lab Test", "quantity": 2, "unit_price": 250.0},
            ],
            "discount": 100.0,
        }
        b = (await self.client.post("/api/v1/billing", json=payload, headers=self.staff_headers)).json()["data"]
        # Subtotal: 500 + 500 = 1000. Total: 1000 - 100 = 900.
        self.assertEqual(b["subtotal"], 1000.0)
        self.assertEqual(b["grand_total"], 900.0)

        # Payment 1 = 300
        p1 = (await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 300.0, "method": "cash"}, headers=self.staff_headers)).json()["data"]
        self.assertEqual(p1["amount_paid"], 300.0)
        self.assertEqual(p1["balance_due"], 600.0)
        self.assertEqual(p1["status"], "partially_paid")

        # Payment 2 = 600
        p2 = (await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 600.0, "method": "upi"}, headers=self.staff_headers)).json()["data"]
        self.assertEqual(p2["amount_paid"], 900.0)
        self.assertEqual(p2["balance_due"], 0.0)
        self.assertEqual(p2["status"], "paid")

        # Reconcile sum of payments
        sum_payments = sum(p["amount"] for p in p2["payments"] if p["status"] in ("completed", "recorded"))
        self.assertEqual(sum_payments, p2["amount_paid"])
        self.assertEqual(p2["grand_total"] - p2["amount_paid"], p2["balance_due"])

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION L: AI & CLINICAL BOUNDARIES (Items 86-88)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_86_to_88_clinical_immutability(self):
        # AI analysis record
        ai_doc = {"analysis_id": "AI-2026-001", "predicted_class": "Pneumonia", "confidence": 0.94}
        self.collections[COLLECTION_AI_ANALYSES]["AI-2026-001"] = ai_doc

        # Prescription record
        rx_doc = {"prescription_id": "RX-2026-001", "medications": [{"name": "Amoxicillin"}]}
        self.collections[COLLECTION_PRESCRIPTIONS]["RX-2026-001"] = rx_doc

        # Create bill and record payment
        b = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item", "unit_price": 500}]}, headers=self.staff_headers)).json()["data"]
        await self.client.post(f"/api/v1/billing/{b['bill_id']}/payments", json={"amount": 500, "method": "cash"}, headers=self.staff_headers)

        # Verify AI document is 100% unchanged
        self.assertEqual(self.collections[COLLECTION_AI_ANALYSES]["AI-2026-001"]["predicted_class"], "Pneumonia")
        self.assertEqual(self.collections[COLLECTION_AI_ANALYSES]["AI-2026-001"]["confidence"], 0.94)

        # Verify prescription is 100% unchanged
        self.assertEqual(self.collections[COLLECTION_PRESCRIPTIONS]["RX-2026-001"]["medications"][0]["name"], "Amoxicillin")

        # Verify consultation notes are 100% unchanged
        self.assertEqual(self.collections[COLLECTION_CONSULTATIONS]["CON-2026-1001"]["clinical_notes"], "Patient fully evaluated.")

    # ════════════════════════════════════════════════════════════════════════════
    # SECTION M: API HISTORY, PAGINATION & FILTERING (Items 89-92)
    # ════════════════════════════════════════════════════════════════════════════

    async def test_89_to_92_api_history_and_filtering(self):
        # Create 3 bills with different statuses
        b1 = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item 1", "unit_price": 100}]}, headers=self.staff_headers)).json()["data"]
        b2 = (await self.client.post("/api/v1/billing", json={"patient_id": "PAT-ONE-001", "line_items": [{"description": "Item 2", "unit_price": 200}]}, headers=self.staff_headers)).json()["data"]
        # Pay b2
        await self.client.post(f"/api/v1/billing/{b2['bill_id']}/payments", json={"amount": 200, "method": "cash"}, headers=self.staff_headers)

        # Pagination: page_size=1
        p_res = await self.client.get("/api/v1/billing?page=1&page_size=1", headers=self.staff_headers)
        self.assertEqual(p_res.status_code, 200)
        self.assertEqual(len(p_res.json()["data"]), 1)
        self.assertIn("pagination", p_res.json())

        # Filtering by status: paid
        f_res = await self.client.get("/api/v1/billing?status=paid", headers=self.staff_headers)
        self.assertEqual(f_res.status_code, 200)
        self.assertTrue(all(b["status"] == "paid" for b in f_res.json()["data"]))

        # Patient authorization-aware filtering: Patient 2 sees 0 of Patient 1's bills
        p2_res = await self.client.get("/api/v1/billing", headers=self.pat2_headers)
        self.assertEqual(p2_res.status_code, 200)
        self.assertEqual(len(p2_res.json()["data"]), 0)


if __name__ == "__main__":
    unittest.main()
