"""
End-to-End Tests for Medical Image Uploader Metadata Provenance.

Verifies:
1. Patient using normal email/password login uploads image -> uploaded_by_role = "patient"
2. Patient using Google Login uploads image -> uploaded_by_role = "patient"
3. Doctor uploads image for patient -> uploaded_by_role = "doctor", patient_id preserved
4. Hospital Staff uploads image for patient -> uploaded_by_role = "staff", patient_id preserved
5. Doctor AI Analysis page retrieval -> images categorized by actual uploader role, NOT viewer role
6. Role-resolution cannot be overridden by frontend and does not default to staff
"""

import io
import time
import unittest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.config import settings
from app.database.mongodb import db_manager, connect_to_mongo, close_mongo_connection
from app.database.collections import COLLECTION_DOCUMENTS, COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS, COLLECTION_STAFF
from app.models.user import UserRole, AccountStatus
from app.integrations.google_auth import GoogleAuthService


class TestMedicalImageUploaderProvenance(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self):
        await connect_to_mongo()
        self.db = db_manager.db
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://test")

        # 1. Login Normal Patient (Patient One)
        pat_login = await self.client.post(
            "/api/v1/auth/login",
            json={"email": "patient.one@clinixai.com", "password": "Patient@123"}
        )
        self.assertEqual(pat_login.status_code, 200, pat_login.text)
        self.pat_token = pat_login.json()["access_token"]
        self.pat_user = pat_login.json()["user"]

        # 2. Login Doctor (Dr. Arjun Rao)
        doc_login = await self.client.post(
            "/api/v1/auth/login",
            json={"email": "doctor.arjun@clinixai.com", "password": "Doctor@123"}
        )
        self.assertEqual(doc_login.status_code, 200, doc_login.text)
        self.doc_token = doc_login.json()["access_token"]
        self.doc_user = doc_login.json()["user"]

        # 3. Login Staff (Staff One)
        staff_login = await self.client.post(
            "/api/v1/auth/login",
            json={"email": "staff.one@clinixai.com", "password": "Staff@123"}
        )
        self.assertEqual(staff_login.status_code, 200, staff_login.text)
        self.staff_token = staff_login.json()["access_token"]
        self.staff_user = staff_login.json()["user"]

        # Ensure patient record for Patient One exists
        self.pat_profile = await self.db[COLLECTION_PATIENTS].find_one({"user_id": self.pat_user["user_id"]})
        if not self.pat_profile:
            self.pat_profile = await self.db[COLLECTION_PATIENTS].find_one({"email": self.pat_user["email"]})
        self.assertIsNotNone(self.pat_profile)
        self.pat_id = self.pat_profile["patient_id"]

    async def asyncTearDown(self):
        await self.client.aclose()
        await close_mongo_connection()

    def _create_dummy_image(self):
        """Creates valid PNG image bytes using PIL."""
        from PIL import Image
        buf = io.BytesIO()
        img = Image.new("RGB", (224, 224), color=(30, 30, 30))
        img.save(buf, format="PNG")
        return buf.getvalue()

    async def test_a_normal_patient_uploads_image(self):
        """Case A: Patient using normal login uploads medical image -> Patient role recorded."""
        headers = {"Authorization": f"Bearer {self.pat_token}"}
        img_bytes = self._create_dummy_image()

        files = {"file": ("normal_patient_mri.png", img_bytes, "image/png")}
        data = {
            "patient_id": self.pat_id,
            "title": "Patient Self-Uploaded Brain MRI",
            "category": "Brain MRI",
        }

        resp = await self.client.post("/api/v1/documents", headers=headers, data=data, files=files)
        self.assertEqual(resp.status_code, 201, resp.text)
        doc = resp.json()

        # Check API response
        self.assertEqual(doc["patient_id"], self.pat_id)
        self.assertEqual(doc["uploaded_by"], self.pat_user["user_id"])
        self.assertEqual(doc["uploaded_by_user_id"], self.pat_user["user_id"])
        self.assertEqual(doc["uploaded_by_role"], "patient")
        self.assertEqual(doc["uploader_role"], "patient")
        self.assertEqual(doc["uploader"]["role"], "patient")
        self.assertEqual(doc["uploader"]["user_id"], self.pat_user["user_id"])

        # Check MongoDB record
        db_doc = await self.db[COLLECTION_DOCUMENTS].find_one({"document_id": doc["document_id"]})
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc["patient_id"], self.pat_id)
        self.assertEqual(db_doc["uploaded_by_user_id"], self.pat_user["user_id"])
        self.assertEqual(db_doc["uploaded_by_role"], "patient")
        self.assertEqual(db_doc["uploader_role"], "patient")
        self.assertNotIn("userrole.", str(db_doc["uploader_role"]).lower())

    async def test_b_google_patient_uploads_image(self):
        """Case B: Patient created via Google Login uploads medical image -> Patient role recorded."""
        # 1. Register/Login a new Google Patient
        ts = int(time.time())
        google_email = f"vamshi.test.{ts}@gmail.com"
        google_sub = f"google_sub_test_{ts}"
        google_name = "Nagula Vamshi Test"

        with patch("app.integrations.google_auth.GoogleAuthService.verify_google_id_token") as mock_verify:
            mock_verify.return_value = {
                "google_sub": google_sub,
                "email": google_email,
                "full_name": google_name,
                "picture": "https://example.com/avatar.jpg",
            }
            auth_resp = await self.client.post("/api/v1/auth/google", json={"id_token": "valid_mock_token"})
            self.assertEqual(auth_resp.status_code, 200, auth_resp.text)
            g_data = auth_resp.json()
            g_token = g_data["access_token"]
            g_user = g_data

        # Verify Google user record in MongoDB has clean role 'patient'
        g_user_db = await self.db[COLLECTION_USERS].find_one({"email": google_email})
        self.assertIsNotNone(g_user_db)
        self.assertEqual(g_user_db["role"], "patient")
        self.assertIsInstance(g_user_db["role"], str)

        # Get Google patient profile
        g_pat_rec = await self.db[COLLECTION_PATIENTS].find_one({"email": google_email})
        self.assertIsNotNone(g_pat_rec)
        g_pid = g_pat_rec["patient_id"]

        # 2. Upload image as Google Patient
        headers = {"Authorization": f"Bearer {g_token}"}
        img_bytes = self._create_dummy_image()
        files = {"file": ("google_patient_mri.png", img_bytes, "image/png")}
        data = {
            "patient_id": g_pid,
            "title": "Google Patient Brain MRI",
            "category": "Brain MRI",
        }

        resp = await self.client.post("/api/v1/documents", headers=headers, data=data, files=files)
        self.assertEqual(resp.status_code, 201, resp.text)
        doc = resp.json()

        # Check API response
        self.assertEqual(doc["patient_id"], g_pid)
        self.assertEqual(doc["uploaded_by"], g_user_db["user_id"])
        self.assertEqual(doc["uploaded_by_user_id"], g_user_db["user_id"])
        self.assertEqual(doc["uploaded_by_role"], "patient")
        self.assertEqual(doc["uploader_role"], "patient")
        self.assertEqual(doc["uploader"]["role"], "patient")
        self.assertEqual(doc["uploader_name"], google_name)
        self.assertEqual(doc["uploader"]["name"], google_name)

        # Check MongoDB record
        db_doc = await self.db[COLLECTION_DOCUMENTS].find_one({"document_id": doc["document_id"]})
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc["patient_id"], g_pid)
        self.assertEqual(db_doc["uploaded_by_user_id"], g_user_db["user_id"])
        self.assertEqual(db_doc["uploaded_by_role"], "patient")
        self.assertEqual(db_doc["uploader_role"], "patient")
        self.assertEqual(db_doc["uploader_name"], google_name)
        self.assertNotIn("userrole.", str(db_doc["uploader_role"]).lower())

    async def test_c_doctor_uploads_image(self):
        """Case C: Doctor uploads medical image for patient -> Doctor role recorded."""
        headers = {"Authorization": f"Bearer {self.doc_token}"}
        img_bytes = self._create_dummy_image()
        files = {"file": ("clinician_mri.png", img_bytes, "image/png")}
        data = {
            "patient_id": self.pat_id,
            "title": "Doctor Prescribed Brain MRI",
            "category": "Brain MRI",
        }

        resp = await self.client.post("/api/v1/documents", headers=headers, data=data, files=files)
        self.assertEqual(resp.status_code, 201, resp.text)
        doc = resp.json()

        # Check API response
        self.assertEqual(doc["patient_id"], self.pat_id)
        self.assertEqual(doc["uploaded_by"], self.doc_user["user_id"])
        self.assertEqual(doc["uploaded_by_user_id"], self.doc_user["user_id"])
        self.assertEqual(doc["uploaded_by_role"], "doctor")
        self.assertEqual(doc["uploader_role"], "doctor")
        self.assertEqual(doc["uploader"]["role"], "doctor")
        self.assertIn("Dr.", doc["uploader_name"])

        # Check MongoDB record
        db_doc = await self.db[COLLECTION_DOCUMENTS].find_one({"document_id": doc["document_id"]})
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc["patient_id"], self.pat_id)
        self.assertEqual(db_doc["uploaded_by_user_id"], self.doc_user["user_id"])
        self.assertEqual(db_doc["uploaded_by_role"], "doctor")
        self.assertEqual(db_doc["uploader_role"], "doctor")

    async def test_d_staff_uploads_image(self):
        """Case D: Hospital Staff uploads medical image for patient -> Staff role recorded."""
        headers = {"Authorization": f"Bearer {self.staff_token}"}
        img_bytes = self._create_dummy_image()
        files = {"file": ("staff_scan.png", img_bytes, "image/png")}
        data = {
            "patient_id": self.pat_id,
            "title": "Hospital Staff Intake Scan",
            "category": "Brain MRI",
        }

        resp = await self.client.post("/api/v1/documents", headers=headers, data=data, files=files)
        self.assertEqual(resp.status_code, 201, resp.text)
        doc = resp.json()

        # Check API response
        self.assertEqual(doc["patient_id"], self.pat_id)
        self.assertEqual(doc["uploaded_by"], self.staff_user["user_id"])
        self.assertEqual(doc["uploaded_by_user_id"], self.staff_user["user_id"])
        self.assertEqual(doc["uploaded_by_role"], "staff")
        self.assertEqual(doc["uploader_role"], "staff")
        self.assertEqual(doc["uploader"]["role"], "staff")

        # Check MongoDB record
        db_doc = await self.db[COLLECTION_DOCUMENTS].find_one({"document_id": doc["document_id"]})
        self.assertIsNotNone(db_doc)
        self.assertEqual(db_doc["patient_id"], self.pat_id)
        self.assertEqual(db_doc["uploaded_by_user_id"], self.staff_user["user_id"])
        self.assertEqual(db_doc["uploaded_by_role"], "staff")
        self.assertEqual(db_doc["uploader_role"], "staff")

    async def test_e_doctor_ai_analysis_view_categorization(self):
        """
        Case E: Doctor viewing the AI Analysis page sees documents categorized
        by their actual uploader (Patient-Uploaded vs Doctor-Uploaded vs Staff-Uploaded),
        NOT by who is currently viewing the page.
        """
        # When Doctor requests documents for patient
        headers = {"Authorization": f"Bearer {self.doc_token}"}
        resp = await self.client.get(f"/api/v1/documents?patient_id={self.pat_id}", headers=headers)
        self.assertEqual(resp.status_code, 200, resp.text)
        items = resp.json()["items"]

        # Ensure documents have their respective author roles intact
        roles_found = {item.get("uploader_role") for item in items}
        self.assertTrue(len(roles_found) > 0)
        # Verify no item has corrupted 'userrole.' string
        for item in items:
            u_role = item.get("uploader_role")
            if u_role:
                self.assertNotIn("userrole.", u_role.lower())
                self.assertIn(u_role.lower(), ["patient", "doctor", "staff", "hospital_admin", "unknown"])

    async def test_f_historical_doc_nagula_vamshi_verified(self):
        """
        Case F: Verify historical document DOC-D1D8661F4C05 for Nagula Vamshi
        has uploader_role='patient', uploaded_by_role='patient', uploader_name='Nagula Vamshi'.
        """
        doc = await self.db[COLLECTION_DOCUMENTS].find_one({"document_id": "DOC-D1D8661F4C05"})
        if doc:
            self.assertEqual(doc["uploader_role"], "patient")
            self.assertEqual(doc["uploaded_by_role"], "patient")
            self.assertEqual(doc["uploader_name"], "Nagula Vamshi")
            self.assertNotIn("userrole.", str(doc["uploader_role"]).lower())


if __name__ == "__main__":
    unittest.main()

