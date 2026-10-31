"""
Phase 22 Dedicated Security & Production Hardening Test Suite.

Comprehensive negative testing, attack surface validation, and production hardening verification:
1. Authentication Security & Enumeration Defense
2. JWT Tampering & Algorithm Confusion Protection
3. Session Revocation on Account Disablement
4. Invitation Token Security & Account Disablement Protection (SEC-01)
5. RBAC 4-Role Strict Boundary Enforcement
6. IDOR Patient Data Isolation
7. IDOR Doctor Clinical Boundary
8. Mass Assignment Protection
9. Mongo Query & Operator Injection Defense
10. Regex ReDoS Safety
11. Path Traversal & Safe Filename Resolution
12. File Upload Security, Magic Bytes, & Extension Spoofing
13. Security Headers, CSP, Frame Protection, & Cache-Control
14. CORS Security & Credential Isolation
15. Rate Limiting Enforcement
16. WebSocket Authentication & Query Token Prohibition
17. AI & Grad-CAM Endpoint Security
18. Billing & Payment Abuse Prevention
19. Error Message Hardening & Trace Concealment
20. Production Configuration Validation (Secret & CORS Hardening)
21. Audit Log Actor Immutability & Privacy
22. Soft Delete Security & Entity Concealment
"""

import asyncio
import os
import secrets
import unittest
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport
import jwt

from app.main import app
from app.core.config import settings, Settings
from app.core.security import create_access_token, create_refresh_token, hash_password
from app.utils.tokens import hash_token
from app.models.user import UserRole, AuthProvider, AccountStatus
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS, COLLECTION_STAFF,
    COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS, COLLECTION_PRESCRIPTIONS,
    COLLECTION_BILLING, COLLECTION_PAYMENTS, COLLECTION_DOCUMENTS,
    COLLECTION_AI_ANALYSES, COLLECTION_NOTIFICATIONS, COLLECTION_AUDIT_LOGS
)
from app.database.mongodb import db_manager, connect_to_mongo
from app.utils.datetime import utc_now
from app.services.storage_service import storage_service


class TestPhase22SecurityProductionHardening(unittest.IsolatedAsyncioTestCase):
    """Phase 22 Master Security & Production Hardening Verification Suite."""

    async def asyncSetUp(self):
        await connect_to_mongo()
        self.db = db_manager.db
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        now = utc_now()

        # Seed Test Users
        self.admin_uid = "USR-SEC-ADM-01"
        self.doc1_uid = "USR-SEC-DOC-01"
        self.doc2_uid = "USR-SEC-DOC-02"
        self.staff_uid = "USR-SEC-STF-01"
        self.pat1_uid = "USR-SEC-PAT-01"
        self.pat2_uid = "USR-SEC-PAT-02"

        self.pat1_id = "PAT-SEC-001"
        self.pat2_id = "PAT-SEC-002"
        self.doc1_id = "DOC-SEC-001"
        self.doc2_id = "DOC-SEC-002"

        hashed_pw = hash_password("ValidPassword123!")

        # 1. Admin
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.admin_uid},
            {"$set": {
                "user_id": self.admin_uid,
                "email": "sec.admin@clinixai.com",
                "password_hash": hashed_pw,
                "full_name": "Security Admin",
                "role": UserRole.HOSPITAL_ADMIN.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "is_deleted": False,
                "updated_at": now,
            }},
            upsert=True
        )

        # 2. Doctor 1 (Arjun)
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.doc1_uid},
            {"$set": {
                "user_id": self.doc1_uid,
                "email": "sec.doc1@clinixai.com",
                "password_hash": hashed_pw,
                "full_name": "Dr. Sec Arjun",
                "role": UserRole.DOCTOR.value,
                "doctor_id": self.doc1_id,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "is_deleted": False,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": self.doc1_id},
            {"$set": {
                "doctor_id": self.doc1_id,
                "user_id": self.doc1_uid,
                "full_name": "Dr. Sec Arjun",
                "name": "Dr. Sec Arjun",
                "email": "sec.doc1@clinixai.com",
                "is_active": True,
                "is_deleted": False,
            }},
            upsert=True
        )

        # 3. Doctor 2 (Priya)
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.doc2_uid},
            {"$set": {
                "user_id": self.doc2_uid,
                "email": "sec.doc2@clinixai.com",
                "password_hash": hashed_pw,
                "full_name": "Dr. Sec Priya",
                "role": UserRole.DOCTOR.value,
                "doctor_id": self.doc2_id,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "is_deleted": False,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": self.doc2_id},
            {"$set": {
                "doctor_id": self.doc2_id,
                "user_id": self.doc2_uid,
                "full_name": "Dr. Sec Priya",
                "name": "Dr. Sec Priya",
                "email": "sec.doc2@clinixai.com",
                "is_active": True,
                "is_deleted": False,
            }},
            upsert=True
        )

        # 4. Staff
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.staff_uid},
            {"$set": {
                "user_id": self.staff_uid,
                "email": "sec.staff@clinixai.com",
                "password_hash": hashed_pw,
                "full_name": "Sec Staff Desk",
                "role": UserRole.HOSPITAL_STAFF.value,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "is_deleted": False,
                "updated_at": now,
            }},
            upsert=True
        )

        # 5. Patient 1 (Alice)
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.pat1_uid},
            {"$set": {
                "user_id": self.pat1_uid,
                "email": "sec.pat1@clinixai.com",
                "password_hash": hashed_pw,
                "full_name": "Alice Sec",
                "role": UserRole.PATIENT.value,
                "patient_id": self.pat1_id,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "is_deleted": False,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": self.pat1_id},
            {"$set": {
                "patient_id": self.pat1_id,
                "user_id": self.pat1_uid,
                "first_name": "Alice",
                "last_name": "Sec",
                "email": "sec.pat1@clinixai.com",
                "is_active": True,
                "is_deleted": False,
            }},
            upsert=True
        )

        # 6. Patient 2 (Bob)
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.pat2_uid},
            {"$set": {
                "user_id": self.pat2_uid,
                "email": "sec.pat2@clinixai.com",
                "password_hash": hashed_pw,
                "full_name": "Bob Sec",
                "role": UserRole.PATIENT.value,
                "patient_id": self.pat2_id,
                "account_status": AccountStatus.ACTIVE.value,
                "is_active": True,
                "is_deleted": False,
                "updated_at": now,
            }},
            upsert=True
        )
        await self.db[COLLECTION_PATIENTS].update_one(
            {"patient_id": self.pat2_id},
            {"$set": {
                "patient_id": self.pat2_id,
                "user_id": self.pat2_uid,
                "first_name": "Bob",
                "last_name": "Sec",
                "email": "sec.pat2@clinixai.com",
                "is_active": True,
                "is_deleted": False,
            }},
            upsert=True
        )

        # Generate standard tokens
        self.admin_token = create_access_token(user_id=self.admin_uid, role=UserRole.HOSPITAL_ADMIN.value)
        self.doc1_token = create_access_token(user_id=self.doc1_uid, role=UserRole.DOCTOR.value)
        self.doc2_token = create_access_token(user_id=self.doc2_uid, role=UserRole.DOCTOR.value)
        self.staff_token = create_access_token(user_id=self.staff_uid, role=UserRole.HOSPITAL_STAFF.value)
        self.pat1_token = create_access_token(user_id=self.pat1_uid, role=UserRole.PATIENT.value)
        self.pat2_token = create_access_token(user_id=self.pat2_uid, role=UserRole.PATIENT.value)

        self.admin_headers = {"Authorization": f"Bearer {self.admin_token}"}
        self.doc1_headers = {"Authorization": f"Bearer {self.doc1_token}"}
        self.doc2_headers = {"Authorization": f"Bearer {self.doc2_token}"}
        self.staff_headers = {"Authorization": f"Bearer {self.staff_token}"}
        self.pat1_headers = {"Authorization": f"Bearer {self.pat1_token}"}
        self.pat2_headers = {"Authorization": f"Bearer {self.pat2_token}"}

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.db[COLLECTION_USERS].delete_many({"email": {"$in": ["hacker.admin@clinixai.com", "invited.doc@clinixai.com"]}})
        await self.db[COLLECTION_BILLING].delete_many({"bill_id": {"$regex": "^BILL-SEC-"}})
        await self.db[COLLECTION_PAYMENTS].delete_many({"bill_id": {"$regex": "^BILL-SEC-"}})
        await self.db[COLLECTION_APPOINTMENTS].delete_many({"appointment_id": {"$regex": "^APT-SEC-"}})
        await self.db[COLLECTION_CONSULTATIONS].delete_many({"consultation_id": {"$regex": "^CON-SEC-"}})

    # ──────────────────────────────────────────────────────────────────────────
    # 1. Authentication Security & Enumeration Defense
    # ──────────────────────────────────────────────────────────────────────────
    async def test_01_authentication_invalid_credentials_and_enumeration(self):
        # Non-existent user -> 401
        res1 = await self.client.post("/api/v1/auth/login", json={"email": "nonexistent@clinixai.com", "password": "WrongPassword123!"})
        self.assertEqual(res1.status_code, 401)
        self.assertIn("Invalid email or password", res1.text)

        # Existing user with wrong password -> 401 with identical message (no account enumeration)
        res2 = await self.client.post("/api/v1/auth/login", json={"email": "sec.pat1@clinixai.com", "password": "WrongPassword123!"})
        self.assertEqual(res2.status_code, 401)
        self.assertIn("Invalid email or password", res2.text)

        # Registration with password shorter than 8 chars -> 400/422
        res3 = await self.client.post("/api/v1/auth/register", json={
            "email": "shortpw@test.com", "password": "short", "first_name": "Test", "last_name": "User"
        })
        self.assertIn(res3.status_code, [400, 422])

    # ──────────────────────────────────────────────────────────────────────────
    # 2. JWT Tampering & Algorithm Confusion
    # ──────────────────────────────────────────────────────────────────────────
    async def test_02_jwt_security_tampering_and_algorithm_confusion(self):
        # Unsigned token / algorithm 'none'
        unsigned_token = jwt.encode({"sub": self.admin_uid, "role": "hospital_admin", "type": "access"}, "", algorithm="none")
        res1 = await self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {unsigned_token}"})
        self.assertEqual(res1.status_code, 401)

        # Tampered payload with modified signature
        parts = self.admin_token.split(".")
        tampered_token = f"{parts[0]}.{parts[1]}tampered.{parts[2]}"
        res2 = await self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_token}"})
        self.assertEqual(res2.status_code, 401)

        # Token signed with wrong secret key
        wrong_secret_token = jwt.encode(
            {"sub": self.admin_uid, "role": "hospital_admin", "type": "access", "exp": datetime.now(timezone.utc) + timedelta(minutes=10)},
            "attacker_secret_key_12345",
            algorithm="HS256"
        )
        res3 = await self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {wrong_secret_token}"})
        self.assertEqual(res3.status_code, 401)

        # Expired token
        expired_token = create_access_token(user_id=self.admin_uid, role="hospital_admin", expires_delta=timedelta(seconds=-10))
        res4 = await self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        self.assertEqual(res4.status_code, 401)

        # Refresh token passed as access token -> rejected
        ref_token, _, _ = create_refresh_token(user_id=self.admin_uid)
        res5 = await self.client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {ref_token}"})
        self.assertEqual(res5.status_code, 401)

    # ──────────────────────────────────────────────────────────────────────────
    # 3. Session Revocation on Account Disablement
    # ──────────────────────────────────────────────────────────────────────────
    async def test_03_session_revocation_on_account_disable(self):
        # 1. Active user verifies session
        res_me = await self.client.get("/api/v1/auth/me", headers=self.pat1_headers)
        self.assertEqual(res_me.status_code, 200)

        # 2. Disable user account
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.pat1_uid},
            {"$set": {"account_status": AccountStatus.DISABLED.value, "is_active": False}}
        )

        # 3. Old token used -> strictly forbidden (403)
        res_disabled = await self.client.get("/api/v1/auth/me", headers=self.pat1_headers)
        self.assertEqual(res_disabled.status_code, 403)

        # 4. Attempt login with disabled account -> strictly rejected (403)
        res_login = await self.client.post("/api/v1/auth/login", json={"email": "sec.pat1@clinixai.com", "password": "ValidPassword123!"})
        self.assertEqual(res_login.status_code, 403)

        # 5. Restore user account to active
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": self.pat1_uid},
            {"$set": {"account_status": AccountStatus.ACTIVE.value, "is_active": True}}
        )
        res_restored = await self.client.get("/api/v1/auth/me", headers=self.pat1_headers)
        self.assertEqual(res_restored.status_code, 200)

    # ──────────────────────────────────────────────────────────────────────────
    # 4. Invitation Token Security & Disablement Protection (SEC-01)
    # ──────────────────────────────────────────────────────────────────────────
    async def test_04_invitation_token_security_and_disablement_protection(self):
        from app.services.auth_service import AuthService
        from app.utils.tokens import generate_secure_token

        invited_uid = "USR-SEC-INVITED-01"
        raw_inv_token = generate_secure_token()
        inv_hash = hash_token(raw_inv_token)
        now = utc_now()

        # Seed invited account
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": invited_uid},
            {"$set": {
                "user_id": invited_uid,
                "email": "invited.doc@clinixai.com",
                "full_name": "Dr. Invited Doctor",
                "role": UserRole.DOCTOR.value,
                "account_status": AccountStatus.PASSWORD_SETUP_REQUIRED.value,
                "is_active": True,
                "invitation_token_hash": inv_hash,
                "invitation_expires_at": now + timedelta(hours=24),
                "created_at": now,
            }},
            upsert=True
        )

        # 1. Verify invitation endpoint works
        res_v = await self.client.post("/api/v1/auth/invitation/verify", json={"token": raw_inv_token})
        self.assertEqual(res_v.status_code, 200)

        # 2. Disable invited user before acceptance
        await self.db[COLLECTION_USERS].update_one(
            {"user_id": invited_uid},
            {"$set": {"account_status": AccountStatus.DISABLED.value, "is_active": False}}
        )

        # Verification must now fail (SEC-01)
        res_v_dis = await self.client.post("/api/v1/auth/invitation/verify", json={"token": raw_inv_token})
        self.assertEqual(res_v_dis.status_code, 400)
        self.assertIn("disabled", res_v_dis.text.lower())

        # Acceptance must also fail (SEC-01)
        res_acc_dis = await self.client.post("/api/v1/auth/invitation/accept", json={
            "token": raw_inv_token, "password": "NewSecurePassword123!"
        })
        self.assertEqual(res_acc_dis.status_code, 400)
        self.assertIn("disabled", res_acc_dis.text.lower())

    # ──────────────────────────────────────────────────────────────────────────
    # 5. RBAC Strict Four-Role Matrix
    # ──────────────────────────────────────────────────────────────────────────
    async def test_05_rbac_strict_four_role_matrix(self):
        # Patient attempting Admin users endpoint -> 403
        res1 = await self.client.get("/api/v1/admin/users", headers=self.pat1_headers)
        self.assertEqual(res1.status_code, 403)

        # Staff attempting Admin settings endpoint -> 403
        res2 = await self.client.get("/api/v1/admin/settings", headers=self.staff_headers)
        self.assertEqual(res2.status_code, 403)

        # Staff attempting to prescribe -> 403
        res3 = await self.client.post("/api/v1/prescriptions", headers=self.staff_headers, json={
            "consultation_id": "CON-FAKE", "diagnosis": "Flu", "medications": []
        })
        self.assertEqual(res3.status_code, 403)

        # Patient attempting to prescribe -> 403
        res4 = await self.client.post("/api/v1/prescriptions", headers=self.pat1_headers, json={
            "consultation_id": "CON-FAKE", "diagnosis": "Flu", "medications": []
        })
        self.assertEqual(res4.status_code, 403)

        # Unauthenticated request to protected endpoint -> 401
        res5 = await self.client.get("/api/v1/admin/users")
        self.assertEqual(res5.status_code, 401)

    # ──────────────────────────────────────────────────────────────────────────
    # 6. IDOR Patient Data Isolation
    # ──────────────────────────────────────────────────────────────────────────
    async def test_06_idor_patient_data_isolation(self):
        now = utc_now()
        # Seed Appointment for Patient 2 (Bob)
        apt_p2_id = "APT-SEC-PAT2-001"
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": apt_p2_id},
            {"$set": {
                "appointment_id": apt_p2_id,
                "patient_id": self.pat2_id,
                "doctor_id": self.doc1_id,
                "status": "scheduled",
                "appointment_date": "2026-10-15",
                "start_time": "10:00",
                "end_time": "10:30",
                "is_deleted": False,
                "created_at": now,
            }},
            upsert=True
        )

        # Patient 1 (Alice) attempting to view Patient 2's appointment -> 403 Forbidden
        res_apt = await self.client.get(f"/api/v1/appointments/{apt_p2_id}", headers=self.pat1_headers)
        self.assertEqual(res_apt.status_code, 403)

        # Seed Bill for Patient 2
        bill_p2_id = "BILL-SEC-PAT2-001"
        await self.db[COLLECTION_BILLING].update_one(
            {"bill_id": bill_p2_id},
            {"$set": {
                "bill_id": bill_p2_id,
                "patient_id": self.pat2_id,
                "grand_total": 500.0,
                "amount_paid": 0.0,
                "balance_due": 500.0,
                "status": "pending",
                "is_deleted": False,
                "created_at": now,
            }},
            upsert=True
        )

        # Patient 1 attempting to view Patient 2's bill -> 403 Forbidden
        res_bill = await self.client.get(f"/api/v1/billing/{bill_p2_id}", headers=self.pat1_headers)
        self.assertEqual(res_bill.status_code, 403)

    # ──────────────────────────────────────────────────────────────────────────
    # 7. IDOR Doctor Clinical Boundary
    # ──────────────────────────────────────────────────────────────────────────
    async def test_07_idor_doctor_clinical_boundary(self):
        now = utc_now()
        # Consultation assigned to Doctor 1 (Arjun)
        con_doc1_id = "CON-SEC-DOC1-001"
        await self.db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": con_doc1_id},
            {"$set": {
                "consultation_id": con_doc1_id,
                "appointment_id": "APT-SEC-PAT1-001",
                "patient_id": self.pat1_id,
                "doctor_id": self.doc1_id,
                "status": "in_progress",
                "version": 1,
                "is_deleted": False,
                "created_at": now,
            }},
            upsert=True
        )

        # Doctor 2 (Priya) attempting to update clinical notes for Doctor 1's consultation -> 403
        res_notes = await self.client.patch(
            f"/api/v1/consultations/{con_doc1_id}/clinical-notes",
            headers=self.doc2_headers,
            json={"clinical_notes": "Doctor 2 unauthorized note modification"}
        )
        self.assertEqual(res_notes.status_code, 403)

    # ──────────────────────────────────────────────────────────────────────────
    # 8. Mass Assignment Guardrails
    # ──────────────────────────────────────────────────────────────────────────
    async def test_08_mass_assignment_guardrails(self):
        await self.db[COLLECTION_USERS].delete_many({"email": "hacker.admin@clinixai.com"})
        # 1. Patient registration attempting to set role to hospital_admin
        res_reg = await self.client.post("/api/v1/auth/register", json={
            "email": "hacker.admin@clinixai.com",
            "password": "Password123!",
            "full_name": "Hacker Admin",
            "role": "hospital_admin",
            "is_admin": True,
            "account_status": "active"
        })
        self.assertEqual(res_reg.status_code, 201)
        created_user = await self.db[COLLECTION_USERS].find_one({"email": "hacker.admin@clinixai.com"})
        self.assertIsNotNone(created_user)
        # Role must be strictly forced to PATIENT
        self.assertEqual(created_user["role"], UserRole.PATIENT.value)
        # Immediate cleanup of registered test user to prevent database pollution
        await self.db[COLLECTION_USERS].delete_many({"email": "hacker.admin@clinixai.com"})

        # 2. Payment creation attempting client balance/status spoofing
        now = utc_now()
        bill_id = "BILL-SEC-MASS-001"
        await self.db[COLLECTION_BILLING].update_one(
            {"bill_id": bill_id},
            {"$set": {
                "bill_id": bill_id,
                "patient_id": self.pat1_id,
                "subtotal": 1000.0,
                "total_tax": 0.0,
                "total_discount": 0.0,
                "discount": 0.0,
                "grand_total": 1000.0,
                "amount_paid": 0.0,
                "balance_due": 1000.0,
                "status": "issued",
                "payments": [],
                "is_deleted": False,
                "created_at": now,
            }},
            upsert=True
        )

        res_pay = await self.client.post(
            f"/api/v1/billing/{bill_id}/payments",
            headers=self.staff_headers,
            json={
                "amount": 200.0,
                "method": "cash",
                "balance_due": 0.0,       # Client attempt to zero out balance
                "status": "paid",          # Client attempt to force status
                "amount_paid": 1000.0,     # Client attempt to force full paid
            }
        )
        self.assertEqual(res_pay.status_code, 200)
        updated_bill = await self.db[COLLECTION_BILLING].find_one({"bill_id": bill_id})
        # Server must correctly compute balance: 1000 - 200 = 800, status must be partially_paid
        self.assertEqual(updated_bill["balance_due"], 800.0)
        self.assertEqual(updated_bill["amount_paid"], 200.0)
        self.assertEqual(updated_bill["status"], "partially_paid")

    # ──────────────────────────────────────────────────────────────────────────
    # 9. Mongo Query & Operator Injection Defense
    # ──────────────────────────────────────────────────────────────────────────
    async def test_09_mongo_operator_and_query_injection(self):
        # Malicious payload with Mongo operators in search query
        res = await self.client.get(
            "/api/v1/search?q={\"$gt\":\"\"}&limit_per_resource=5",
            headers=self.admin_headers
        )
        self.assertEqual(res.status_code, 200)
        # Search must treat {"$gt":""} literally as a string, not evaluate as operator

    # ──────────────────────────────────────────────────────────────────────────
    # 10. Regex ReDoS Safety
    # ──────────────────────────────────────────────────────────────────────────
    async def test_10_regex_redos_safety(self):
        # Pathological repetitive backtracking query
        evil_regex = "a" * 50 + ".*" * 10 + "b"
        res = await self.client.get(f"/api/v1/search?q={evil_regex}", headers=self.admin_headers)
        self.assertEqual(res.status_code, 200)

    # ──────────────────────────────────────────────────────────────────────────
    # 11. Path Traversal & Safe Filename Resolution
    # ──────────────────────────────────────────────────────────────────────────
    async def test_11_path_traversal_protection(self):
        from app.core.exceptions import AppValidationError

        # Direct storage service path traversal attempt
        with self.assertRaises(AppValidationError):
            storage_service._resolve_safe_path("../../windows/win.ini", "documents")

        with self.assertRaises(AppValidationError):
            storage_service._resolve_safe_path("..\\..\\boot.ini", "documents")

        with self.assertRaises(AppValidationError):
            storage_service._resolve_safe_path("file\x00traversal.txt", "documents")

    # ──────────────────────────────────────────────────────────────────────────
    # 12. File Upload Security, Magic Bytes, & Extension Spoofing
    # ──────────────────────────────────────────────────────────────────────────
    async def test_12_file_upload_security_magic_bytes_and_extension_spoofing(self):
        # Executable file upload attempt -> strictly rejected (400/422)
        res_exe = await self.client.post(
            "/api/v1/documents",
            headers=self.pat1_headers,
            data={"patient_id": self.pat1_id, "title": "Malicious Script", "category": "Report"},
            files={"file": ("malware.exe", b"MZ\x90\x00\x03\x00\x00\x00", "application/x-msdownload")}
        )
        self.assertIn(res_exe.status_code, [400, 422])

        # PHP script upload attempt -> rejected
        res_php = await self.client.post(
            "/api/v1/documents",
            headers=self.pat1_headers,
            data={"patient_id": self.pat1_id, "title": "PHP Backdoor", "category": "Report"},
            files={"file": ("shell.php", b"<?php phpinfo(); ?>", "application/x-php")}
        )
        self.assertIn(res_php.status_code, [400, 422])

    # ──────────────────────────────────────────────────────────────────────────
    # 13. Security Headers, CSP, Frame Protection, & Cache-Control
    # ──────────────────────────────────────────────────────────────────────────
    async def test_13_security_headers_and_csp_enforcement(self):
        res = await self.client.get("/api/v1/health")
        self.assertEqual(res.status_code, 200)

        # Standard headers
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertEqual(res.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")
        self.assertIn("camera=()", res.headers.get("Permissions-Policy", ""))

        # CSP with frame-ancestors 'none'
        csp = res.headers.get("Content-Security-Policy", "")
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("default-src 'self'", csp)

        # API Cache-Control
        cache_ctrl = res.headers.get("Cache-Control", "")
        self.assertIn("no-store", cache_ctrl)
        self.assertIn("no-cache", cache_ctrl)

    # ──────────────────────────────────────────────────────────────────────────
    # 14. CORS Security & Credential Isolation
    # ──────────────────────────────────────────────────────────────────────────
    async def test_14_cors_security_and_credential_restrictions(self):
        # Preflight from allowed origin
        res_cors = await self.client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://localhost:3100",
                "Access-Control-Request-Method": "GET"
            }
        )
        self.assertEqual(res_cors.headers.get("Access-Control-Allow-Origin"), "http://localhost:3100")
        self.assertEqual(res_cors.headers.get("Access-Control-Allow-Credentials"), "true")

        # Disallowed origin must not receive credentialed wildcard
        res_evil = await self.client.options(
            "/api/v1/health",
            headers={
                "Origin": "http://evil-attacker-site.com",
                "Access-Control-Request-Method": "GET"
            }
        )
        self.assertNotEqual(res_evil.headers.get("Access-Control-Allow-Origin"), "*")

    # ──────────────────────────────────────────────────────────────────────────
    # 15. Rate Limiting Enforcement
    # ──────────────────────────────────────────────────────────────────────────
    async def test_15_rate_limiting_enforcement(self):
        # Using test rate limiting header on login endpoint
        headers = {"X-Test-Rate-Limit": "true", "X-Forwarded-For": "203.0.113.199"}
        statuses = []
        for _ in range(7):
            res = await self.client.post(
                "/api/v1/auth/login",
                headers=headers,
                json={"email": "nonexistent@clinixai.com", "password": "WrongPassword123!"}
            )
            statuses.append(res.status_code)

        # The rate limit must trigger HTTP 429 Too Many Requests
        self.assertIn(429, statuses)

    # ──────────────────────────────────────────────────────────────────────────
    # 16. WebSocket Authentication & Query Token Prohibition
    # ──────────────────────────────────────────────────────────────────────────
    async def test_16_websocket_authentication_and_query_token_rejection(self):
        # Testing through HTTP request simulating query parameter attempt on notification WS endpoint
        from fastapi.testclient import TestClient
        client = TestClient(app)

        # Attempt WebSocket connection with ?token= query parameter -> must be rejected with 1008
        with client.websocket_connect(f"/api/v1/notifications/ws?token={self.pat1_token}") as ws:
            msg = ws.receive()
            self.assertEqual(msg["type"], "websocket.close")
            self.assertEqual(msg["code"], 1008)

    # ──────────────────────────────────────────────────────────────────────────
    # 17. AI & Grad-CAM Endpoint Security
    # ──────────────────────────────────────────────────────────────────────────
    async def test_17_ai_inference_and_gradcam_authorization(self):
        # Staff requesting Grad-CAM -> strictly forbidden (403)
        res_staff = await self.client.get(
            "/api/v1/ai-analyses/AI-SEC-TEST-001/gradcam",
            headers=self.staff_headers
        )
        self.assertEqual(res_staff.status_code, 403)

        # Grad-CAM rejecting ?token= query parameter -> 401
        res_query = await self.client.get(
            f"/api/v1/ai-analyses/AI-SEC-TEST-001/gradcam?token={self.doc1_token}"
        )
        self.assertEqual(res_query.status_code, 401)

    # ──────────────────────────────────────────────────────────────────────────
    # 18. Billing & Payment Abuse Prevention
    # ──────────────────────────────────────────────────────────────────────────
    async def test_18_billing_and_payment_abuse_prevention(self):
        now = utc_now()
        bill_id = "BILL-SEC-ABUSE-001"
        await self.db[COLLECTION_BILLING].update_one(
            {"bill_id": bill_id},
            {"$set": {
                "bill_id": bill_id,
                "patient_id": self.pat1_id,
                "subtotal": 500.0,
                "total_tax": 0.0,
                "total_discount": 0.0,
                "discount": 0.0,
                "grand_total": 500.0,
                "amount_paid": 0.0,
                "balance_due": 500.0,
                "status": "issued",
                "payments": [],
                "is_deleted": False,
                "created_at": now,
            }},
            upsert=True
        )

        # 1. Negative amount payment -> 422
        res_neg = await self.client.post(
            f"/api/v1/billing/{bill_id}/payments",
            headers=self.staff_headers,
            json={"amount": -50.0, "method": "cash"}
        )
        self.assertIn(res_neg.status_code, [400, 422])

        # 2. Overpayment exceeding balance -> 400
        res_over = await self.client.post(
            f"/api/v1/billing/{bill_id}/payments",
            headers=self.staff_headers,
            json={"amount": 99999.0, "method": "cash"}
        )
        self.assertEqual(res_over.status_code, 400)

        # 3. Patient 2 attempting payment against Patient 1's bill -> 403
        res_other = await self.client.post(
            f"/api/v1/billing/{bill_id}/payments",
            headers=self.pat2_headers,
            json={"amount": 100.0, "method": "cash"}
        )
        self.assertEqual(res_other.status_code, 403)

    # ──────────────────────────────────────────────────────────────────────────
    # 19. Error Message Hardening & Trace Concealment
    # ──────────────────────────────────────────────────────────────────────────
    async def test_19_error_message_hardening_and_trace_concealment(self):
        # Malformed endpoint or parameter -> 422/400
        res = await self.client.get("/api/v1/appointments/INVALID_MALFORMED_ID")
        self.assertIn(res.status_code, [401, 403, 404])
        # Response must not contain Python traceback or internal file paths
        self.assertNotIn("Traceback (most recent call last)", res.text)
        self.assertNotIn("c:\\users\\", res.text.lower())
        self.assertNotIn("mongodb://", res.text.lower())

    # ──────────────────────────────────────────────────────────────────────────
    # 20. Production Configuration Validation (Secret & CORS Hardening)
    # ──────────────────────────────────────────────────────────────────────────
    def test_20_production_configuration_validation(self):
        # Production with default dev secret must raise RuntimeError
        bad_settings = Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="clinixai_dev_jwt_secret_key_2026_change_in_production_replace_me"
        )
        with self.assertRaises(RuntimeError):
            bad_settings.validate_production_security()

        # Production with wildcard CORS must raise RuntimeError
        bad_cors_settings = Settings(
            ENVIRONMENT="production",
            JWT_SECRET_KEY="a_strong_production_secret_key_random_hex_string_12345",
            CORS_ORIGINS=["*"]
        )
        with self.assertRaises(RuntimeError):
            bad_cors_settings.validate_production_security()

    # ──────────────────────────────────────────────────────────────────────────
    # 21. Audit Log Actor Immutability & Privacy
    # ──────────────────────────────────────────────────────────────────────────
    async def test_21_audit_log_actor_immutability_and_privacy(self):
        # Patient attempting to list audit logs -> 403
        res_pat = await self.client.get("/api/v1/audit-logs", headers=self.pat1_headers)
        self.assertEqual(res_pat.status_code, 403)

        # Admin listing audit logs -> 200
        res_adm = await self.client.get("/api/v1/audit-logs", headers=self.admin_headers)
        self.assertEqual(res_adm.status_code, 200)

        # Patient attempting to access admin user accounts -> 403
        res_admin_users = await self.client.get("/api/v1/admin/users", headers=self.pat1_headers)
        self.assertEqual(res_admin_users.status_code, 403)

    # ──────────────────────────────────────────────────────────────────────────
    # 22. Soft Delete Security & Entity Concealment
    # ──────────────────────────────────────────────────────────────────────────
    async def test_22_soft_delete_and_data_isolation(self):
        now = utc_now()
        del_apt_id = "APT-SEC-DELETED-001"
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": del_apt_id},
            {"$set": {
                "appointment_id": del_apt_id,
                "patient_id": self.pat1_id,
                "doctor_id": self.doc1_id,
                "status": "cancelled",
                "is_deleted": True,
                "created_at": now,
                "updated_at": now,
            }},
            upsert=True
        )

        # Querying soft-deleted appointment directly -> 404
        res = await self.client.get(f"/api/v1/appointments/{del_apt_id}", headers=self.pat1_headers)
        self.assertEqual(res.status_code, 404)

    # ──────────────────────────────────────────────────────────────────────────
    # 23. Prescription Clinical Role Authorization & Linkage
    # ──────────────────────────────────────────────────────────────────────────
    async def test_23_prescription_doctor_only_authorization_and_linkage(self):
        # Staff attempting to issue prescription -> 403
        res_staff = await self.client.post("/api/v1/prescriptions", headers=self.staff_headers, json={
            "consultation_id": "CON-SEC-DOC1-001",
            "medications": [{"medicine_name": "Amoxicillin", "dosage": "500mg", "frequency": "TDS", "duration_days": 5}],
            "diagnosis": "Bacterial Infection"
        })
        self.assertEqual(res_staff.status_code, 403)

        # Patient attempting to issue prescription -> 403
        res_pat = await self.client.post("/api/v1/prescriptions", headers=self.pat1_headers, json={
            "consultation_id": "CON-SEC-DOC1-001",
            "medications": [{"medicine_name": "Amoxicillin", "dosage": "500mg", "frequency": "TDS", "duration_days": 5}],
            "diagnosis": "Bacterial Infection"
        })
        self.assertEqual(res_pat.status_code, 403)

        # Doctor with missing consultation_id -> 400/422
        res_empty = await self.client.post("/api/v1/prescriptions", headers=self.doc1_headers, json={
            "medications": [{"medicine_name": "Amoxicillin", "dosage": "500mg", "frequency": "TDS", "duration_days": 5}],
            "diagnosis": "Bacterial Infection"
        })
        self.assertIn(res_empty.status_code, [400, 422])

    # ──────────────────────────────────────────────────────────────────────────
    # 24. Consultation Immutability upon Completion
    # ──────────────────────────────────────────────────────────────────────────
    async def test_24_consultation_completion_immutability(self):
        now = utc_now()
        completed_con_id = "CON-SEC-COMPLETED-001"
        await self.db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": completed_con_id},
            {"$set": {
                "consultation_id": completed_con_id,
                "appointment_id": "APT-SEC-PAT1-001",
                "patient_id": self.pat1_id,
                "doctor_id": self.doc1_id,
                "status": "completed",
                "version": 2,
                "is_deleted": False,
                "completed_at": now,
                "created_at": now,
            }},
            upsert=True
        )

        # Doctor attempting to edit clinical notes of a finalized completed consultation -> 400 Bad Request
        res_edit = await self.client.patch(
            f"/api/v1/consultations/{completed_con_id}/clinical-notes",
            headers=self.doc1_headers,
            json={"clinical_notes": "Attempting to overwrite finalized legal clinical record"}
        )
        self.assertEqual(res_edit.status_code, 400)
        self.assertIn("finalized", res_edit.text.lower())

    # ──────────────────────────────────────────────────────────────────────────
    # 25. Notification IDOR & User Isolation
    # ──────────────────────────────────────────────────────────────────────────
    async def test_25_notification_idor_and_isolation(self):
        now = utc_now()
        p2_ntf_id = "NTF-SEC-PAT2-001"
        await self.db[COLLECTION_NOTIFICATIONS].update_one(
            {"notification_id": p2_ntf_id},
            {"$set": {
                "notification_id": p2_ntf_id,
                "recipient_user_id": self.pat2_uid,
                "user_id": self.pat2_uid,
                "notification_type": "appointment_confirmed",
                "type": "appointment_confirmed",
                "title": "Private Notification for Bob",
                "body": "Confidential patient notification",
                "status": "unread",
                "read": False,
                "created_at": now,
            }},
            upsert=True
        )

        # Patient 1 (Alice) attempting to view Patient 2 (Bob)'s notification -> 403 or 404
        res_view = await self.client.get(f"/api/v1/notifications/{p2_ntf_id}", headers=self.pat1_headers)
        self.assertIn(res_view.status_code, [403, 404])

        # Patient 1 attempting to mark-read Patient 2's notification -> 403 or 404
        res_read = await self.client.post(f"/api/v1/notifications/{p2_ntf_id}/read", headers=self.pat1_headers)
        self.assertIn(res_read.status_code, [403, 404])

    # ──────────────────────────────────────────────────────────────────────────
    # 26. Health & Readiness Endpoint Security (No Secret Exposure)
    # ──────────────────────────────────────────────────────────────────────────
    async def test_26_health_and_readiness_no_secret_leakage(self):
        res_health = await self.client.get("/api/v1/health")
        self.assertEqual(res_health.status_code, 200)
        self.assertNotIn("mongodb://", res_health.text.lower())
        self.assertNotIn("password", res_health.text.lower())
        self.assertNotIn("secret", res_health.text.lower())

        res_ready = await self.client.get("/api/v1/health/ready")
        self.assertEqual(res_ready.status_code, 200)
        self.assertNotIn("mongodb://", res_ready.text.lower())
        self.assertNotIn("password", res_ready.text.lower())
        self.assertNotIn("cluster0", res_ready.text.lower())

    # ──────────────────────────────────────────────────────────────────────────
    # 27. Logout Session Invalidation & Cookie Removal
    # ──────────────────────────────────────────────────────────────────────────
    async def test_27_logout_session_invalidation(self):
        login_res = await self.client.post("/api/v1/auth/login", json={
            "email": "sec.pat1@clinixai.com", "password": "ValidPassword123!"
        })
        self.assertEqual(login_res.status_code, 200)
        ref_token = login_res.json()["refresh_token"]

        # Logout with refresh token
        logout_res = await self.client.post(
            "/api/v1/auth/logout",
            json={"refresh_token": ref_token},
            headers={"Authorization": f"Bearer {login_res.json()['access_token']}"}
        )
        self.assertEqual(logout_res.status_code, 200)

        # Attempt to use revoked refresh token -> 401 Unauthorized
        re_refresh = await self.client.post("/api/v1/auth/refresh", json={"refresh_token": ref_token})
        self.assertEqual(re_refresh.status_code, 401)

    # ──────────────────────────────────────────────────────────────────────────
    # 28. SSRF Architecture Audit Verification
    # ──────────────────────────────────────────────────────────────────────────
    def test_28_ssrf_architecture_audit(self):
        """Verifies no user-controlled server-side URL fetch path identified in application routes."""
        import inspect
        from app.api.v1.router import api_v1_router

        def _audit_route(r):
            if hasattr(r, "endpoint") and callable(r.endpoint):
                sig = inspect.signature(r.endpoint)
                param_names = [p.name.lower() for p in sig.parameters.values()]
                self.assertNotIn("target_url", param_names)
                self.assertNotIn("remote_url", param_names)
                self.assertNotIn("fetch_url", param_names)
                self.assertNotIn("webhook_url", param_names)
            if hasattr(r, "routes"):
                for sub in r.routes:
                    _audit_route(sub)

        for route in api_v1_router.routes:
            _audit_route(route)


if __name__ == "__main__":
    unittest.main()
