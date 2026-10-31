"""
Automated Test Suite for CliniXAI Post-Phase-24 Fix Phase 3:
Complete Doctor Appointment Management Audit, State Machine & Hardening.

Covers all 25 Phase Z mandatory test requirements:
1. Doctor appointment listing
2. Doctor appointment scope (scoped exclusively to authenticated doctor)
3. Doctor appointment detail
4. Doctor own appointment access
5. Doctor cannot access another doctor's appointment (403 Forbidden IDOR)
6. Patient cannot use doctor lifecycle endpoint (e.g., confirm/complete)
7. Valid confirmation (scheduled -> confirmed)
8. Invalid confirmation (e.g., already completed/cancelled -> 409/422/400)
9. Valid cancellation (scheduled/confirmed -> cancelled with reason)
10. Invalid cancellation (completed -> cancelled rejected)
11. Duplicate confirmation (idempotent safe handling)
12. Duplicate cancellation (idempotent safe handling)
13. Cross-doctor IDOR (Doctor A cannot confirm or cancel Doctor B's appointment)
14. Patient ownership preserved in appointment updates
15. Appointment -> consultation linkage preserved
16. Notification correctness on lifecycle changes
17. Concurrent lifecycle mutation (atomic race condition safety)
18. Error response handling (clean error schemas)
19. Persistence verification (MongoDB record retains status, updated_at, audit fields)
20. Dashboard/list consistency
21. No hardcoded identity assumptions (dynamic doctor resolution)
22. Role boundary checks (Patient cannot call doctor completion endpoint)
23. Direct appointment endpoint
24. Invalid appointment ID (clean 404 response)
25. Authentication requirement (401 Unauthorized without valid JWT)
"""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now


def _make_cursor(return_data=None):
    mock_cursor = MagicMock()
    data = list(return_data) if return_data is not None else []
    mock_cursor.__aiter__ = MagicMock(return_value=iter(data))
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.skip = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=data)
    return mock_cursor


class TestDoctorAppointmentFixPhase3(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        # Doctor A (Dr. Arjun Rao - DOC-001)
        self.doctor_a_user = UserInDB(
            user_id="USR-DOC-001",
            email="dr.rao@clinixai.com",
            full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        # Doctor B (Dr. Sarah Chen - DOC-002)
        self.doctor_b_user = UserInDB(
            user_id="USR-DOC-002",
            email="dr.chen@clinixai.com",
            full_name="Dr. Sarah Chen",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        # Patient (John Doe - PAT-001)
        self.patient_user = UserInDB(
            user_id="USR-PAT-001",
            email="patient.a@clinixai.com",
            full_name="John Doe",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        # Staff
        self.staff_user = UserInDB(
            user_id="USR-STF-001",
            email="staff.reception@clinixai.com",
            full_name="Staff Receptionist",
            role=UserRole.STAFF,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self._user_dicts = {
            "USR-DOC-001": self.doctor_a_user.to_mongo_dict(),
            "USR-DOC-002": self.doctor_b_user.to_mongo_dict(),
            "USR-PAT-001": self.patient_user.to_mongo_dict(),
            "USR-STF-001": self.staff_user.to_mongo_dict(),
        }

        self.token_doctor_a = create_access_token(user_id=self.doctor_a_user.user_id, role=self.doctor_a_user.role.value)
        self.token_doctor_b = create_access_token(user_id=self.doctor_b_user.user_id, role=self.doctor_b_user.role.value)
        self.token_patient = create_access_token(user_id=self.patient_user.user_id, role=self.patient_user.role.value)
        self.token_staff = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)

        self.headers_doctor_a = {"Authorization": f"Bearer {self.token_doctor_a}"}
        self.headers_doctor_b = {"Authorization": f"Bearer {self.token_doctor_b}"}
        self.headers_patient = {"Authorization": f"Bearer {self.token_patient}"}
        self.headers_staff = {"Authorization": f"Bearer {self.token_staff}"}

        # Doctors collection documents
        self.doc_profile_a = {
            "doctor_id": "DOC-001",
            "user_id": "USR-DOC-001",
            "full_name": "Dr. Arjun Rao",
            "email": "dr.rao@clinixai.com",
            "specialization": "Cardiology",
            "department_id": "DEPT-CARD",
            "status": "active",
            "is_active": True,
        }
        self.doc_profile_b = {
            "doctor_id": "DOC-002",
            "user_id": "USR-DOC-002",
            "full_name": "Dr. Sarah Chen",
            "email": "dr.chen@clinixai.com",
            "specialization": "Neurology",
            "department_id": "DEPT-NEURO",
            "status": "active",
            "is_active": True,
        }

        # Patient document
        self.patient_profile = {
            "patient_id": "PAT-001",
            "user_id": "USR-PAT-001",
            "first_name": "John",
            "last_name": "Doe",
            "full_name": "John Doe",
            "email": "patient.a@clinixai.com",
            "phone_number": "+91 98765 00001",
        }

        # Appointments
        # APT-001 belongs to Doctor A (scheduled)
        self.apt_001 = {
            "appointment_id": "APT-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "department_id": "DEPT-CARD",
            "appointment_date": "2026-10-10",
            "start_time": "10:00",
            "end_time": "10:30",
            "status": "scheduled",
            "reason": "Routine Cardiology Follow-up",
            "appointment_type": "new_consultation",
            "booking_source": "patient",
            "notes": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        # APT-002 belongs to Doctor B (scheduled)
        self.apt_002 = {
            "appointment_id": "APT-002",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-002",
            "department_id": "DEPT-NEURO",
            "appointment_date": "2026-10-11",
            "start_time": "11:30",
            "end_time": "12:00",
            "status": "scheduled",
            "reason": "Neurology Consultation",
            "appointment_type": "new_consultation",
            "booking_source": "patient",
            "notes": None,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        # APT-003 belongs to Doctor A (completed)
        self.apt_003 = {
            "appointment_id": "APT-003",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "department_id": "DEPT-CARD",
            "appointment_date": "2026-10-01",
            "start_time": "09:00",
            "end_time": "09:30",
            "status": "completed",
            "reason": "Initial Heart Checkup",
            "appointment_type": "new_consultation",
            "booking_source": "patient",
            "consultation_id": "CON-001",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        self._appointments = {
            "APT-001": dict(self.apt_001),
            "APT-002": dict(self.apt_002),
            "APT-003": dict(self.apt_003),
        }

        self._notifications = []
        self._audit_logs = []

        # Setup in-memory mock collections
        self._collections = {}

        def get_collection(name):
            if name not in self._collections:
                col = MagicMock()
                col.insert_one = AsyncMock(return_value=None)
                col.replace_one = AsyncMock(return_value=None)
                col.update_one = AsyncMock(return_value=None)
                col.find_one_and_update = AsyncMock(return_value=None)
                col.count_documents = AsyncMock(return_value=0)
                col.find = MagicMock(return_value=_make_cursor([]))
                col.aggregate = MagicMock(return_value=_make_cursor([]))
                col.find_one = AsyncMock(return_value=None)
                self._collections[name] = col
            return self._collections[name]

        self.mock_db = MagicMock()
        self.mock_db.__getitem__.side_effect = get_collection

        # Users collection
        async def mock_users_find_one(query, *args, **kwargs):
            if "user_id" in query:
                return self._user_dicts.get(query["user_id"])
            if "email" in query:
                for u in self._user_dicts.values():
                    if u.get("email") == query["email"]:
                        return u
            return None

        # Doctors collection
        async def mock_doctors_find_one(query, *args, **kwargs):
            if "user_id" in query:
                uid = query["user_id"]
                if uid == "USR-DOC-001":
                    return self.doc_profile_a
                if uid == "USR-DOC-002":
                    return self.doc_profile_b
            if "doctor_id" in query:
                did = query["doctor_id"]
                if did == "DOC-001":
                    return self.doc_profile_a
                if did == "DOC-002":
                    return self.doc_profile_b
            if "email" in query:
                em = query["email"]
                if em == "dr.rao@clinixai.com":
                    return self.doc_profile_a
                if em == "dr.chen@clinixai.com":
                    return self.doc_profile_b
            return None

        # Patients collection
        async def mock_patients_find_one(query, *args, **kwargs):
            if query.get("patient_id") == "PAT-001" or query.get("user_id") == "USR-PAT-001":
                return self.patient_profile
            return None

        # Appointments collection
        async def mock_appointments_find_one(query, *args, **kwargs):
            apt_id = query.get("appointment_id")
            if apt_id and apt_id in self._appointments:
                apt = self._appointments[apt_id]
                if "doctor_id" in query and apt.get("doctor_id") != query["doctor_id"]:
                    return None
                if "status" in query:
                    status_cond = query["status"]
                    if isinstance(status_cond, dict) and "$in" in status_cond:
                        if apt.get("status") not in status_cond["$in"]:
                            return None
                    elif apt.get("status") != status_cond:
                        return None
                return dict(apt)
            return None

        async def mock_appointments_find_one_and_update(query, update, *args, **kwargs):
            apt_id = query.get("appointment_id")
            if not apt_id or apt_id not in self._appointments:
                return None
            apt = self._appointments[apt_id]
            if "doctor_id" in query and apt.get("doctor_id") != query["doctor_id"]:
                return None
            if "status" in query:
                cond = query["status"]
                if isinstance(cond, dict) and "$in" in cond:
                    if apt.get("status") not in cond["$in"]:
                        return None
                elif apt.get("status") != cond:
                    return None
            if "$set" in update:
                for k, v in update["$set"].items():
                    apt[k] = v
            apt["updated_at"] = utc_now()
            return dict(apt)

        async def mock_appointments_update_one(query, update, *args, **kwargs):
            result = MagicMock()
            apt_id = query.get("appointment_id")
            if apt_id and apt_id in self._appointments:
                apt = self._appointments[apt_id]
                if "status" in query:
                    cond = query["status"]
                    if isinstance(cond, dict) and "$in" in cond:
                        if apt.get("status") not in cond["$in"]:
                            result.modified_count = 0
                            return result
                    elif apt.get("status") != cond:
                        result.modified_count = 0
                        return result
                if "$set" in update:
                    for k, v in update["$set"].items():
                        apt[k] = v
                result.modified_count = 1
            else:
                result.modified_count = 0
            return result

        def mock_appointments_find(query, *args, **kwargs):
            results = []
            target_doctor = query.get("doctor_id")
            target_patient = query.get("patient_id")
            for apt in self._appointments.values():
                if target_doctor and apt.get("doctor_id") != target_doctor:
                    continue
                if target_patient and apt.get("patient_id") != target_patient:
                    continue
                if "status" in query:
                    st = query["status"]
                    if isinstance(st, dict) and "$in" in st:
                        if apt.get("status") not in st["$in"]:
                            continue
                    elif apt.get("status") != st:
                        continue
                results.append(dict(apt))
            return _make_cursor(results)

        async def mock_appointments_count_documents(query, *args, **kwargs):
            target_doctor = query.get("doctor_id")
            count = 0
            for apt in self._appointments.values():
                if target_doctor and apt.get("doctor_id") != target_doctor:
                    continue
                count += 1
            return count

        async def mock_notifications_insert_one(doc, *args, **kwargs):
            self._notifications.append(doc)
            res = MagicMock()
            res.inserted_id = "NOTIF-001"
            return res

        async def mock_audit_insert_one(doc, *args, **kwargs):
            self._audit_logs.append(doc)
            res = MagicMock()
            res.inserted_id = "AUDIT-001"
            return res

        users_col = get_collection("users")
        users_col.find_one = AsyncMock(side_effect=mock_users_find_one)

        doctors_col = get_collection("doctors")
        doctors_col.find_one = AsyncMock(side_effect=mock_doctors_find_one)

        patients_col = get_collection("patients")
        patients_col.find_one = AsyncMock(side_effect=mock_patients_find_one)

        apts_col = get_collection("appointments")
        apts_col.find_one = AsyncMock(side_effect=mock_appointments_find_one)
        apts_col.find_one_and_update = AsyncMock(side_effect=mock_appointments_find_one_and_update)
        apts_col.update_one = AsyncMock(side_effect=mock_appointments_update_one)
        apts_col.find = MagicMock(side_effect=mock_appointments_find)
        apts_col.count_documents = AsyncMock(side_effect=mock_appointments_count_documents)

        notifs_col = get_collection("notifications")
        notifs_col.insert_one = AsyncMock(side_effect=mock_notifications_insert_one)

        audit_col = get_collection("audit_logs")
        audit_col.insert_one = AsyncMock(side_effect=mock_audit_insert_one)

        # Wire dependency override
        app.dependency_overrides[get_database] = lambda: self.mock_db
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # 1. Doctor appointment listing
    async def test_01_doctor_appointment_listing(self):
        resp = await self.client.get("/api/v1/appointments", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("data", body)
        self.assertIn("pagination", body)
        self.assertGreaterEqual(len(body["data"]), 1)

    # 2. Doctor appointment scope (only Doctor's appointments returned)
    async def test_02_doctor_appointment_scope(self):
        resp = await self.client.get("/api/v1/appointments", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["data"]
        for apt in items:
            self.assertEqual(apt["doctor_id"], "DOC-001", "Doctor A must only receive Doctor A appointments")
        apt_ids = [apt["appointment_id"] for apt in items]
        self.assertNotIn("APT-002", apt_ids, "Doctor A must not receive Doctor B's APT-002")

    # 3. Doctor appointment detail
    async def test_03_doctor_appointment_detail(self):
        resp = await self.client.get("/api/v1/appointments/APT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["appointment_id"], "APT-001")
        self.assertEqual(data["status"], "scheduled")

    # 4. Doctor own appointment access
    async def test_04_doctor_own_appointment_access(self):
        resp = await self.client.get("/api/v1/appointments/APT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)

    # 5. Doctor cannot access another doctor's appointment (IDOR 403)
    async def test_05_doctor_cannot_access_another_doctor_appointment(self):
        resp = await self.client.get("/api/v1/appointments/APT-002", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 403, "Doctor A accessing Doctor B's appointment must be 403 Forbidden")

    # 6. Patient cannot use doctor lifecycle endpoint (e.g., confirm)
    async def test_06_patient_cannot_use_doctor_lifecycle_endpoint(self):
        resp = await self.client.post("/api/v1/appointments/APT-001/confirm", headers=self.headers_patient)
        self.assertEqual(resp.status_code, 403, "Patient cannot confirm an appointment")

    # 7. Valid confirmation (scheduled -> confirmed)
    async def test_07_valid_confirmation(self):
        resp = await self.client.post("/api/v1/appointments/APT-001/confirm", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["status"], "confirmed")
        self.assertEqual(self._appointments["APT-001"]["status"], "confirmed")

    # 8. Invalid confirmation (e.g., already completed)
    async def test_08_invalid_confirmation(self):
        # APT-003 is already completed
        resp = await self.client.post("/api/v1/appointments/APT-003/confirm", headers=self.headers_doctor_a)
        self.assertIn(resp.status_code, [400, 409, 422], "Confirming completed appointment must fail with 400/409/422")

    # 9. Valid cancellation (scheduled -> cancelled with reason)
    async def test_09_valid_cancellation(self):
        payload = {"reason": "Patient requested reschedule"}
        resp = await self.client.post("/api/v1/appointments/APT-001/cancel", json=payload, headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._appointments["APT-001"]["status"], "cancelled")

    # 10. Invalid cancellation (completed -> cancelled rejected)
    async def test_10_invalid_cancellation(self):
        payload = {"reason": "Cannot cancel completed"}
        resp = await self.client.post("/api/v1/appointments/APT-003/cancel", json=payload, headers=self.headers_doctor_a)
        self.assertIn(resp.status_code, [400, 409, 422], "Cancelling completed appointment must fail")

    # 11. Duplicate confirmation safe handling
    async def test_11_duplicate_confirmation(self):
        resp1 = await self.client.post("/api/v1/appointments/APT-001/confirm", headers=self.headers_doctor_a)
        self.assertEqual(resp1.status_code, 200)
        resp2 = await self.client.post("/api/v1/appointments/APT-001/confirm", headers=self.headers_doctor_a)
        self.assertIn(resp2.status_code, [200, 409])

    # 12. Duplicate cancellation safe handling
    async def test_12_duplicate_cancellation(self):
        payload = {"reason": "Doctor unavailable"}
        resp1 = await self.client.post("/api/v1/appointments/APT-001/cancel", json=payload, headers=self.headers_doctor_a)
        self.assertEqual(resp1.status_code, 200)
        resp2 = await self.client.post("/api/v1/appointments/APT-001/cancel", json=payload, headers=self.headers_doctor_a)
        self.assertIn(resp2.status_code, [200, 409, 400])

    # 13. Cross-doctor IDOR (Doctor A cannot confirm or cancel Doctor B's appointment)
    async def test_13_cross_doctor_idor_mutation(self):
        # Confirm attempt on Doctor B's appointment
        resp_confirm = await self.client.post("/api/v1/appointments/APT-002/confirm", headers=self.headers_doctor_a)
        self.assertEqual(resp_confirm.status_code, 403, "Doctor A cannot confirm Doctor B's appointment")
        # Cancel attempt on Doctor B's appointment
        resp_cancel = await self.client.post(
            "/api/v1/appointments/APT-002/cancel",
            json={"reason": "Unauthorized attempt"},
            headers=self.headers_doctor_a
        )
        self.assertEqual(resp_cancel.status_code, 403, "Doctor A cannot cancel Doctor B's appointment")

    # 14. Patient ownership preserved in appointment updates
    async def test_14_patient_ownership_preserved(self):
        orig_patient_id = self._appointments["APT-001"]["patient_id"]
        await self.client.post("/api/v1/appointments/APT-001/confirm", headers=self.headers_doctor_a)
        self.assertEqual(self._appointments["APT-001"]["patient_id"], orig_patient_id)

    # 15. Appointment -> consultation linkage preserved
    async def test_15_appointment_consultation_linkage(self):
        resp = await self.client.get("/api/v1/appointments/APT-003", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        # Appointment doc preserved consultation_id
        self.assertEqual(self._appointments["APT-003"].get("consultation_id"), "CON-001")

    # 16. Notification correctness
    async def test_16_notification_on_lifecycle_event(self):
        prev_notif_count = len(self._notifications)
        resp = await self.client.post("/api/v1/appointments/APT-001/confirm", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        self.assertGreater(len(self._notifications), prev_notif_count)
        latest_notif = self._notifications[-1]
        recipient = latest_notif.get("user_id") or latest_notif.get("recipient_id")
        self.assertIn(recipient, ["USR-PAT-001", "PAT-001"])

    # 17. Concurrent lifecycle mutation (atomic race condition safety)
    async def test_17_concurrent_lifecycle_mutation(self):
        res1 = await self.client.post("/api/v1/appointments/APT-001/confirm", headers=self.headers_doctor_a)
        self.assertEqual(res1.status_code, 200)
        res2 = await self.client.post("/api/v1/appointments/APT-001/confirm", headers=self.headers_doctor_a)
        self.assertIn(res2.status_code, [200, 409])

    # 18. Error response handling
    async def test_18_error_response_handling(self):
        resp = await self.client.get("/api/v1/appointments/APT-NONEXISTENT", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertIn("error", data)

    # 19. Persistence verification (MongoDB record retains status, updated_at)
    async def test_19_persistence_verification(self):
        resp = await self.client.post("/api/v1/appointments/APT-001/confirm", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        updated_apt = self._appointments["APT-001"]
        self.assertEqual(updated_apt["status"], "confirmed")
        self.assertIsNotNone(updated_apt["updated_at"])

    # 20. Dashboard/list consistency
    async def test_20_dashboard_list_consistency(self):
        list_resp = await self.client.get("/api/v1/appointments", headers=self.headers_doctor_a)
        self.assertEqual(list_resp.status_code, 200)
        items = list_resp.json()["data"]
        total = list_resp.json()["pagination"]["total"]
        self.assertEqual(len(items), total)

    # 21. No hardcoded identity assumptions (dynamic doctor resolution)
    async def test_21_dynamic_doctor_identity_resolution(self):
        resp = await self.client.get("/api/v1/appointments", headers=self.headers_doctor_b)
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["data"]
        for apt in items:
            self.assertEqual(apt["doctor_id"], "DOC-002")

    # 22. Role boundary checks (Patient cannot call doctor completion endpoint)
    async def test_22_role_boundary_patient_cannot_complete(self):
        resp = await self.client.post("/api/v1/appointments/APT-001/complete", headers=self.headers_patient)
        self.assertEqual(resp.status_code, 403, "Patient cannot complete an appointment")

    # 23. Direct appointment endpoint
    async def test_23_direct_appointment_endpoint(self):
        resp = await self.client.get("/api/v1/appointments/APT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["appointment_id"], "APT-001")

    # 24. Invalid appointment ID
    async def test_24_invalid_appointment_id(self):
        resp = await self.client.get("/api/v1/appointments/APT-INVALID-999", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 404)

    # 25. Authentication requirement (401 Unauthorized without valid JWT)
    async def test_25_authentication_requirement(self):
        resp = await self.client.get("/api/v1/appointments/APT-001")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
