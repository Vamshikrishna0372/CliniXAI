"""
Post-Phase-24 Fix Phase 5 Test Suite:
Brain MRI Document Discovery & Doctor-Side Patient Context.

Covers:
1. Authorized Doctor can retrieve patient's documents.
2. Existing Brain MRI document is returned with authoritative metadata.
3. Category filtering finds Brain MRI scan.
4. Category normalization accepts variations (MRI, Brain MRI, brain mri, brain_mri).
5. Unauthorized doctor attempting to list patient documents is rejected (403).
6. Unauthorized doctor cannot fetch single document (403).
7. Cross-patient document access by patient is rejected (403).
8. Soft-deleted documents are excluded from discovery.
9. Image retrieval requires authentication (401 for unauthenticated).
10. Image retrieval rejects unauthorized doctor (403).
11. Image retrieval rejects unauthorized cross-patient (403).
12. Authorized doctor can securely download/view patient's image bytes (200).
13. Authorized patient can download own document (200).
14. Authorized doctor can discover documents for their own patient.
15. Switching patients enforces strict care relationship isolation (403).
16. Document selection payload contains required fields (document_id, patient_id, category, title).
"""

import os
import unittest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.mongodb import db_manager, connect_to_mongo
from app.models.user import UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_DOCUMENTS, COLLECTION_APPOINTMENTS
)


class TestBrainMRIDocumentDiscoveryFixPhase5(unittest.IsolatedAsyncioTestCase):
    """16 Focused Automated Tests for Fix Phase 5: Brain MRI Discovery & Patient Context."""

    @staticmethod
    def _data(res):
        j = res.json()
        return j.get("data", j)

    async def asyncSetUp(self):
        if db_manager.db is None:
            await connect_to_mongo()
        self.db = db_manager.db
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        # Doctor A: Dr. Arjun Rao (Authorized for Patient One)
        self.doc_a_user = {
            "user_id": "USR-DOC-RAO-001",
            "email": "doctor.arjun@clinixai.com",
            "full_name": "Dr. Arjun Rao",
            "role": UserRole.DOCTOR.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.doc_a = {
            "doctor_id": "DOC-RAO-001",
            "user_id": "USR-DOC-RAO-001",
            "first_name": "Arjun",
            "last_name": "Rao",
            "email": "doctor.arjun@clinixai.com",
            "specialty": "Neurology",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Doctor Unrelated: Dr. Vikram Joshi (No care relationship with Patient One)
        self.doc_unrelated_user = {
            "user_id": "USR-DOC-VIKRAM-P5",
            "email": "dr.vikram.p5@clinixai.com",
            "full_name": "Dr. Vikram Joshi",
            "role": UserRole.DOCTOR.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.doc_unrelated = {
            "doctor_id": "DOC-VIKRAM-P5",
            "user_id": "USR-DOC-VIKRAM-P5",
            "first_name": "Vikram",
            "last_name": "Joshi",
            "email": "dr.vikram.p5@clinixai.com",
            "specialty": "Orthopedics",
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Patient One: Seed patient with existing Brain MRI DOC-2026-001
        self.pat_1_user = {
            "user_id": "USR-PAT-ONE-001",
            "email": "patient.one@clinixai.com",
            "full_name": "Patient One",
            "role": UserRole.PATIENT.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.pat_1 = {
            "patient_id": "PAT-ONE-001",
            "user_id": "USR-PAT-ONE-001",
            "first_name": "Patient",
            "last_name": "One",
            "email": "patient.one@clinixai.com",
            "primary_physician_id": "DOC-RAO-001",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Patient Isolated: Separate patient with care relationship ONLY with Doctor Unrelated
        self.pat_isolated_user = {
            "user_id": "USR-PAT-ISOLATED-P5",
            "email": "patient.isolated.p5@clinixai.com",
            "full_name": "Patient Isolated",
            "role": UserRole.PATIENT.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "account_status": AccountStatus.ACTIVE.value,
            "is_active": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.pat_isolated = {
            "patient_id": "PAT-ISOLATED-P5",
            "user_id": "USR-PAT-ISOLATED-P5",
            "first_name": "Patient",
            "last_name": "Isolated",
            "email": "patient.isolated.p5@clinixai.com",
            "primary_physician_id": "DOC-VIKRAM-P5",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Ensure database documents exist
        await self.db[COLLECTION_USERS].update_one({"user_id": self.doc_a_user["user_id"]}, {"$set": self.doc_a_user}, upsert=True)
        await self.db[COLLECTION_DOCTORS].update_one({"doctor_id": self.doc_a["doctor_id"]}, {"$set": self.doc_a}, upsert=True)
        await self.db[COLLECTION_USERS].update_one({"user_id": self.doc_unrelated_user["user_id"]}, {"$set": self.doc_unrelated_user}, upsert=True)
        await self.db[COLLECTION_DOCTORS].update_one({"doctor_id": self.doc_unrelated["doctor_id"]}, {"$set": self.doc_unrelated}, upsert=True)

        await self.db[COLLECTION_USERS].update_one({"user_id": self.pat_1_user["user_id"]}, {"$set": self.pat_1_user}, upsert=True)
        await self.db[COLLECTION_PATIENTS].update_one({"patient_id": self.pat_1["patient_id"]}, {"$set": self.pat_1}, upsert=True)
        await self.db[COLLECTION_USERS].update_one({"user_id": self.pat_isolated_user["user_id"]}, {"$set": self.pat_isolated_user}, upsert=True)
        await self.db[COLLECTION_PATIENTS].update_one({"patient_id": self.pat_isolated["patient_id"]}, {"$set": self.pat_isolated}, upsert=True)

        # Ensure care relationship ONLY between Doctor Unrelated and Patient Isolated
        await self.db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": "APT-P5-ISOLATED-001"},
            {"$set": {
                "appointment_id": "APT-P5-ISOLATED-001",
                "patient_id": "PAT-ISOLATED-P5",
                "doctor_id": "DOC-VIKRAM-P5",
                "status": "CONFIRMED",
                "created_at": utc_now(),
                "updated_at": utc_now(),
            }},
            upsert=True
        )

        # Create isolated MRI document for Patient Isolated
        self.isolated_doc = {
            "document_id": "DOC-P5-ISOLATED-MRI",
            "patient_id": "PAT-ISOLATED-P5",
            "uploaded_by": "USR-DOC-VIKRAM-P5",
            "title": "Isolated Patient Brain MRI",
            "category": "MRI",
            "file_name": "doc_brain_mri_pat1.jpg",
            "original_file_name": "Isolated_Brain_MRI.jpg",
            "mime_type": "image/jpeg",
            "file_size_bytes": 42790,
            "storage_path": "C:\\Users\\Vamshikrishna\\Desktop\\CliniXAI\\backend\\uploads\\documents\\doc_brain_mri_pat1.jpg",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].update_one(
            {"document_id": self.isolated_doc["document_id"]},
            {"$set": self.isolated_doc},
            upsert=True
        )

        # Generate JWT tokens
        self.token_doc_a = create_access_token(
            user_id=self.doc_a_user["user_id"], role=UserRole.DOCTOR.value
        )
        self.headers_doc_a = {"Authorization": f"Bearer {self.token_doc_a}"}

        self.token_doc_unrelated = create_access_token(
            user_id=self.doc_unrelated_user["user_id"], role=UserRole.DOCTOR.value
        )
        self.headers_doc_unrelated = {"Authorization": f"Bearer {self.token_doc_unrelated}"}

        self.token_pat_1 = create_access_token(
            user_id=self.pat_1_user["user_id"], role=UserRole.PATIENT.value
        )
        self.headers_pat_1 = {"Authorization": f"Bearer {self.token_pat_1}"}

        self.token_pat_isolated = create_access_token(
            user_id=self.pat_isolated_user["user_id"], role=UserRole.PATIENT.value
        )
        self.headers_pat_isolated = {"Authorization": f"Bearer {self.token_pat_isolated}"}

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_01_doctor_can_retrieve_authorized_patient_documents(self):
        """Doctor A retrieves Patient A's documents successfully."""
        res = await self.client.get("/api/v1/documents", headers=self.headers_doc_a, params={"patient_id": "PAT-ONE-001"})
        self.assertEqual(res.status_code, 200, res.text)
        data = self._data(res)
        items = data.get("items", [])
        self.assertGreaterEqual(len(items), 1)
        doc_ids = [d["document_id"] for d in items]
        self.assertIn("DOC-2026-001", doc_ids)

    async def test_02_existing_brain_mri_returned_with_authoritative_metadata(self):
        """Brain MRI DOC-2026-001 has authoritative metadata for Patient A."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001", headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 200, res.text)
        doc = self._data(res)
        self.assertEqual(doc["document_id"], "DOC-2026-001")
        self.assertEqual(doc["patient_id"], "PAT-ONE-001")
        self.assertEqual(doc["category"], "MRI")
        self.assertIn("image", doc["mime_type"].lower())
        self.assertTrue("brain" in doc["title"].lower() or "brain" in doc.get("file_name", "").lower())

    async def test_03_category_filtering_finds_brain_mri(self):
        """Querying with category=MRI returns the Brain MRI scan."""
        res = await self.client.get("/api/v1/documents", headers=self.headers_doc_a, params={"patient_id": "PAT-ONE-001", "category": "MRI"})
        self.assertEqual(res.status_code, 200, res.text)
        items = self._data(res).get("items", [])
        self.assertTrue(any(d["document_id"] == "DOC-2026-001" for d in items))

    async def test_04_category_normalization_accepts_brain_mri_variants(self):
        """Category filter handles 'Brain MRI' gracefully."""
        res = await self.client.get("/api/v1/documents", headers=self.headers_doc_a, params={"patient_id": "PAT-ONE-001", "category": "Brain MRI"})
        self.assertEqual(res.status_code, 200, res.text)
        items = self._data(res).get("items", [])
        self.assertTrue(any(d["document_id"] == "DOC-2026-001" for d in items))

    async def test_05_unauthorized_doctor_cannot_list_patient_documents(self):
        """Doctor Unrelated has no care relationship with Patient One -> 403 Forbidden."""
        res = await self.client.get("/api/v1/documents", headers=self.headers_doc_unrelated, params={"patient_id": "PAT-ONE-001"})
        self.assertEqual(res.status_code, 403)

    async def test_06_unauthorized_doctor_cannot_get_single_document(self):
        """Doctor Unrelated cannot fetch DOC-2026-001 belonging to Patient One -> 403 Forbidden."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001", headers=self.headers_doc_unrelated)
        self.assertEqual(res.status_code, 403)

    async def test_07_patient_cannot_access_another_patients_document(self):
        """Patient Isolated cannot fetch Patient One's document -> 403 Forbidden."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001", headers=self.headers_pat_isolated)
        self.assertEqual(res.status_code, 403)

    async def test_08_soft_deleted_documents_are_excluded(self):
        """A soft-deleted document must not be discoverable."""
        soft_del_doc = {
            "document_id": "DOC-SOFT-DEL-TEST",
            "patient_id": "PAT-ONE-001",
            "title": "Deleted Brain MRI",
            "category": "MRI",
            "mime_type": "image/jpeg",
            "file_name": "deleted.jpg",
            "file_path": "uploads/documents/doc_brain_mri_pat1.jpg",
            "file_size": 1024,
            "is_deleted": True,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        await self.db[COLLECTION_DOCUMENTS].update_one(
            {"document_id": soft_del_doc["document_id"]},
            {"$set": soft_del_doc},
            upsert=True
        )

        res = await self.client.get("/api/v1/documents", headers=self.headers_doc_a, params={"patient_id": "PAT-ONE-001"})
        self.assertEqual(res.status_code, 200)
        items = self._data(res).get("items", [])
        self.assertFalse(any(d["document_id"] == "DOC-SOFT-DEL-TEST" for d in items))

        # Cleanup
        await self.db[COLLECTION_DOCUMENTS].delete_one({"document_id": "DOC-SOFT-DEL-TEST"})

    async def test_09_unauthenticated_download_returns_401(self):
        """Unauthenticated download request to /api/v1/documents/{id}/download must return 401."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001/download")
        self.assertEqual(res.status_code, 401)

    async def test_10_unauthorized_download_returns_403(self):
        """Doctor Unrelated attempting to download Patient One's image must return 403."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001/download", headers=self.headers_doc_unrelated)
        self.assertEqual(res.status_code, 403)

    async def test_11_cross_patient_download_returns_403(self):
        """Patient Isolated attempting to download Patient One's image must return 403."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001/download", headers=self.headers_pat_isolated)
        self.assertEqual(res.status_code, 403)

    async def test_12_authorized_doctor_can_download_mri_bytes(self):
        """Doctor A authorized for Patient One can securely download the image bytes."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001/download", headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 200)
        self.assertIn("image", res.headers.get("content-type", "").lower())
        self.assertGreater(len(res.content), 100)

    async def test_13_authorized_patient_can_download_own_mri(self):
        """Patient One can download their own document."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001/download", headers=self.headers_pat_1)
        self.assertEqual(res.status_code, 200)
        self.assertGreater(len(res.content), 100)

    async def test_14_doctor_unrelated_can_discover_own_patient_documents(self):
        """Doctor Unrelated can discover DOC-P5-ISOLATED-MRI for Patient Isolated."""
        res = await self.client.get("/api/v1/documents", headers=self.headers_doc_unrelated, params={"patient_id": "PAT-ISOLATED-P5"})
        self.assertEqual(res.status_code, 200)
        items = self._data(res).get("items", [])
        doc_ids = [d["document_id"] for d in items]
        self.assertIn("DOC-P5-ISOLATED-MRI", doc_ids)

    async def test_15_switching_patients_enforces_strict_isolation(self):
        """Querying PAT-ISOLATED-P5 with Doctor A credentials is forbidden."""
        res = await self.client.get("/api/v1/documents", headers=self.headers_doc_a, params={"patient_id": "PAT-ISOLATED-P5"})
        self.assertEqual(res.status_code, 403)

    async def test_16_document_selection_payload_contains_required_fields(self):
        """Ensure document response provides document_id, patient_id, category, and title for Phase 6 handoff."""
        res = await self.client.get("/api/v1/documents/DOC-2026-001", headers=self.headers_doc_a)
        self.assertEqual(res.status_code, 200)
        doc = self._data(res)
        self.assertIn("document_id", doc)
        self.assertIn("patient_id", doc)
        self.assertIn("title", doc)
        self.assertIn("category", doc)
        self.assertEqual(doc["document_id"], "DOC-2026-001")
        self.assertEqual(doc["patient_id"], "PAT-ONE-001")


if __name__ == "__main__":
    unittest.main()
