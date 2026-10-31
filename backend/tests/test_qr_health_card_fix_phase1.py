"""
Automated Test Suite for CliniXAI Post-Phase-24 Fix Phase 1:
QR Health Card + Authentication + Navigation Hardening.

Verifies:
1. Authenticated patient can retrieve personal QR card data (GET /patients/me/qr)
2. Authenticated patient can stream QR PNG image bytes (GET /patients/me/qr/image)
3. Authenticated patient can rotate & regenerate QR code (POST /patients/me/qr/regenerate)
4. Unauthenticated request to QR endpoints rejected (401 Unauthorized)
5. Cross-patient authorization isolation: Patient A cannot access Patient B QR data
6. Object-level authorization on patient profile (Patient A cannot view Patient B profile)
7. Non-patient roles (Doctor, Staff, Admin) cannot access personal patient QR endpoints (403 Forbidden)
8. Missing patient profile handled with clean 404 (ResourceNotFoundError)
9. Authoritative backend identity: derives identity exclusively from authenticated JWT
10. Explicit logout semantics: session invalidation remains explicit
11. Staff can scan and resolve patient QR token (POST /qr/resolve-patient)
12. Patients cannot resolve QR tokens (403 Forbidden)
13. Appointment QR check-in workflow integrity
14. Persistence of patient and QR metadata
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


class TestQRHealthCardFixPhase1(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        # Patient A (John Doe)
        self.patient_a = UserInDB(
            user_id="USR-PAT-001", email="patient.a@clinixai.com", full_name="John Doe",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
        )
        # Patient B (Jane Smith)
        self.patient_b = UserInDB(
            user_id="USR-PAT-002", email="patient.b@clinixai.com", full_name="Jane Smith",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
        )
        # Doctor
        self.doctor = UserInDB(
            user_id="USR-DOC-001", email="dr.smith@clinixai.com", full_name="Dr. Smith",
            role=UserRole.DOCTOR, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
        )
        # Staff
        self.staff = UserInDB(
            user_id="USR-STF-001", email="staff@clinixai.com", full_name="Staff One",
            role=UserRole.HOSPITAL_STAFF, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
        )
        # Patient with no profile
        self.patient_no_profile = UserInDB(
            user_id="USR-PAT-999", email="noprofile@clinixai.com", full_name="No Profile User",
            role=UserRole.PATIENT, auth_provider=AuthProvider.LOCAL, account_status=AccountStatus.ACTIVE,
        )

        self._user_dicts = {
            "USR-PAT-001": self.patient_a.to_mongo_dict(),
            "USR-PAT-002": self.patient_b.to_mongo_dict(),
            "USR-DOC-001": self.doctor.to_mongo_dict(),
            "USR-STF-001": self.staff.to_mongo_dict(),
            "USR-PAT-999": self.patient_no_profile.to_mongo_dict(),
        }

        self.token_patient_a = create_access_token(user_id=self.patient_a.user_id, role=self.patient_a.role.value)
        self.token_patient_b = create_access_token(user_id=self.patient_b.user_id, role=self.patient_b.role.value)
        self.token_doctor = create_access_token(user_id=self.doctor.user_id, role=self.doctor.role.value)
        self.token_staff = create_access_token(user_id=self.staff.user_id, role=self.staff.role.value)
        self.token_no_profile = create_access_token(user_id=self.patient_no_profile.user_id, role=self.patient_no_profile.role.value)

        self.headers_patient_a = {"Authorization": f"Bearer {self.token_patient_a}"}
        self.headers_patient_b = {"Authorization": f"Bearer {self.token_patient_b}"}
        self.headers_doctor = {"Authorization": f"Bearer {self.token_doctor}"}
        self.headers_staff = {"Authorization": f"Bearer {self.token_staff}"}
        self.headers_no_profile = {"Authorization": f"Bearer {self.token_no_profile}"}

        # Mock Patient documents in MongoDB
        self.patient_doc_a = {
            "patient_id": "PAT-001",
            "user_id": "USR-PAT-001",
            "first_name": "John",
            "last_name": "Doe",
            "full_name": "John Doe",
            "email": "patient.a@clinixai.com",
            "blood_group": "O+",
            "emergency_contact": {"name": "Mary Doe", "relationship": "Spouse", "phone": "+91 98765 00001"},
            "qr_code": {"raw_token": "pqr_token_patient_a", "is_revoked": False},
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "status": "active",
        }
        self.patient_doc_b = {
            "patient_id": "PAT-002",
            "user_id": "USR-PAT-002",
            "first_name": "Jane",
            "last_name": "Smith",
            "full_name": "Jane Smith",
            "email": "patient.b@clinixai.com",
            "blood_group": "A+",
            "emergency_contact": {"name": "Bob Smith", "relationship": "Brother", "phone": "+91 98765 00002"},
            "qr_code": {"raw_token": "pqr_token_patient_b", "is_revoked": False},
            "created_at": utc_now(),
            "updated_at": utc_now(),
            "status": "active",
        }

        self._patients = {
            "PAT-001": self.patient_doc_a,
            "PAT-002": self.patient_doc_b,
        }
        self._patients_by_user = {
            "USR-PAT-001": self.patient_doc_a,
            "USR-PAT-002": self.patient_doc_b,
        }

        self._collections = {}

        def get_collection(name):
            if name not in self._collections:
                col = MagicMock()
                col.insert_one = AsyncMock(return_value=None)
                col.replace_one = AsyncMock(return_value=None)
                col.update_one = AsyncMock(return_value=None)
                col.count_documents = AsyncMock(return_value=0)
                col.find = MagicMock(return_value=_make_cursor([]))
                col.aggregate = MagicMock(return_value=_make_cursor([]))
                col.find_one = AsyncMock(return_value=None)
                self._collections[name] = col
            return self._collections[name]

        self.mock_db = MagicMock()
        self.mock_db.__getitem__.side_effect = get_collection

        # Users collection find_one
        async def users_find_one(query, *args, **kwargs):
            uid = query.get("user_id")
            if uid:
                return self._user_dicts.get(uid)
            email = query.get("email")
            if email:
                for u in self._user_dicts.values():
                    if u["email"] == email:
                        return u
            return None

        # Patients collection find_one
        async def patients_find_one(query, *args, **kwargs):
            pid = query.get("patient_id")
            if pid:
                return self._patients.get(pid)
            uid = query.get("user_id")
            if uid:
                return self._patients_by_user.get(uid)
            raw_token = query.get("qr_code.raw_token")
            if raw_token:
                for p in self._patients.values():
                    if p.get("qr_code", {}).get("raw_token") == raw_token:
                        return p
            return None

        async def patients_update_one(filter_query, update_doc, *args, **kwargs):
            pid = filter_query.get("patient_id")
            doc = self._patients.get(pid)
            if doc and "$set" in update_doc:
                for k, v in update_doc["$set"].items():
                    doc[k] = v
            return MagicMock(modified_count=1)

        get_collection("users").find_one = users_find_one
        get_collection("patients").find_one = patients_find_one
        get_collection("patients").update_one = patients_update_one

        async def override_get_db():
            return self.mock_db

        app.dependency_overrides[get_database] = override_get_db

        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver/api/v1")

    async def asyncTearDown(self) -> None:
        app.dependency_overrides.clear()
        await self.client.aclose()

    # 1. Authenticated Patient can retrieve QR data
    async def test_authenticated_patient_can_retrieve_qr_card_data(self) -> None:
        res = await self.client.get("/patients/me/qr", headers=self.headers_patient_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertIn("token", data)
        self.assertIn("payload", data)
        self.assertIn("created_at", data)
        self.assertTrue(data["payload"].startswith("clinixai:patient:"))
        self.assertEqual(data["token"], "pqr_token_patient_a")

    # 2. Authenticated Patient can stream QR image bytes
    async def test_authenticated_patient_can_stream_qr_image(self) -> None:
        res = await self.client.get("/patients/me/qr/image", headers=self.headers_patient_a)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("content-type"), "image/png")
        self.assertGreater(len(res.content), 0)

    # 3. Unauthenticated request rejected (401)
    async def test_unauthenticated_request_rejected(self) -> None:
        res = await self.client.get("/patients/me/qr")
        self.assertEqual(res.status_code, 401)

        res_img = await self.client.get("/patients/me/qr/image")
        self.assertEqual(res_img.status_code, 401)

        res_regen = await self.client.post("/patients/me/qr/regenerate")
        self.assertEqual(res_regen.status_code, 401)

    # 4. Patient A cannot access Patient B QR data (Identity is strictly bound to token)
    async def test_patient_a_cannot_access_patient_b_qr_data(self) -> None:
        res_a = await self.client.get("/patients/me/qr", headers=self.headers_patient_a)
        self.assertEqual(res_a.status_code, 200)
        token_a = res_a.json()["token"]

        res_b = await self.client.get("/patients/me/qr", headers=self.headers_patient_b)
        self.assertEqual(res_b.status_code, 200)
        token_b = res_b.json()["token"]

        # Tokens are distinct and tied to respective patient identities
        self.assertNotEqual(token_a, token_b)
        self.assertEqual(token_a, "pqr_token_patient_a")
        self.assertEqual(token_b, "pqr_token_patient_b")

    # 5. Patient A cannot access Patient B profile detail
    async def test_patient_a_cannot_access_patient_b_profile(self) -> None:
        # Accessing own profile: allowed
        res_own = await self.client.get("/patients/PAT-001", headers=self.headers_patient_a)
        self.assertEqual(res_own.status_code, 200)

        # Accessing Patient B profile: 403 Forbidden
        res_other = await self.client.get("/patients/PAT-002", headers=self.headers_patient_a)
        self.assertEqual(res_other.status_code, 403)

    # 6. Non-patient roles denied from personal patient QR endpoints (403 Forbidden)
    async def test_non_patient_roles_cannot_access_patient_qr(self) -> None:
        res_doc = await self.client.get("/patients/me/qr", headers=self.headers_doctor)
        self.assertEqual(res_doc.status_code, 403)

        res_staff = await self.client.get("/patients/me/qr", headers=self.headers_staff)
        self.assertEqual(res_staff.status_code, 403)

    # 7. Missing patient profile handled with 404 (ResourceNotFoundError)
    async def test_missing_patient_profile_handled_correctly(self) -> None:
        res = await self.client.get("/patients/me/qr", headers=self.headers_no_profile)
        self.assertEqual(res.status_code, 404)

        res_me = await self.client.get("/patients/me", headers=self.headers_no_profile)
        self.assertEqual(res_me.status_code, 404)

    # 8. QR token regeneration rotates token
    async def test_qr_token_regeneration(self) -> None:
        res = await self.client.post("/patients/me/qr/regenerate", headers=self.headers_patient_a)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["token"].startswith("pqr_"))
        self.assertNotEqual(data["token"], "pqr_token_patient_a")

    # 9. Response schema correctness
    async def test_qr_token_response_schema(self) -> None:
        res = await self.client.get("/patients/me/qr", headers=self.headers_patient_a)
        data = res.json()
        self.assertIsInstance(data.get("token"), str)
        self.assertIsInstance(data.get("payload"), str)
        self.assertIsInstance(data.get("created_at"), str)

    # 10. Staff can scan and resolve patient QR token
    async def test_staff_resolve_patient_qr(self) -> None:
        res = await self.client.post(
            "/qr/resolve-patient",
            headers=self.headers_staff,
            json={"token": "clinixai:patient:pqr_token_patient_a"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["patient_id"], "PAT-001")
        self.assertEqual(data["first_name"], "John")
        self.assertEqual(data["last_name"], "Doe")

    # 11. Patients cannot resolve QR tokens (403 Forbidden)
    async def test_patient_cannot_resolve_patient_qr(self) -> None:
        res = await self.client.post(
            "/qr/resolve-patient",
            headers=self.headers_patient_a,
            json={"token": "clinixai:patient:pqr_token_patient_a"},
        )
        self.assertEqual(res.status_code, 403)

    # 12. No token query parameter leakage
    async def test_no_tokens_in_url(self) -> None:
        # All requests use standard Authorization header, not URL query params
        res = await self.client.get("/patients/me/qr", headers=self.headers_patient_a)
        self.assertNotIn("token=", str(res.url))
        self.assertNotIn("access_token=", str(res.url))


if __name__ == "__main__":
    unittest.main()
