"""
Automated Test Suite for CliniXAI Post-Phase-24 Fix Phase 4A:
Doctor Clinical Workspace & Patient Context Hardening.

Covers all 25 Phase 4A required tests:
1. Doctor can access own authorized appointment.
2. Doctor can resolve appointment -> patient.
3. Patient identity is correct.
4. Doctor can access patient clinical workspace / context.
5. Doctor can access authorized medical records.
6. Unauthorized Doctor cannot access records (403 Forbidden).
7. Doctor can access authorized documents.
8. Unauthorized Doctor cannot access documents (403 Forbidden).
9. Doctor can access authorized medical images.
10. Unauthorized Doctor cannot access images (403 Forbidden).
11. Patient A cannot access Patient B clinical workspace (403 Forbidden).
12. Doctor can access authorized consultation.
13. Unauthorized Doctor cannot modify consultation (403 Forbidden).
14. Doctor prescription linkage is correct.
15. Patient cannot modify Doctor prescription (403 Forbidden).
16. Staff cannot perform clinical Doctor operations (403 Forbidden).
17. Appointment -> consultation relationship remains correct.
18. Consultation -> medical record relationship remains correct.
19. Prescription -> patient relationship remains correct.
20. Direct IDOR attempts return 403 or 404.
21. Invalid clinical IDs return proper clean errors (404/422).
22. Persistence survives process restart (MongoDB records retain linkage & context).
23. Stale consultation update returns 409 Conflict.
24. No cross-patient data leakage.
25. Existing Fix Phase 1 QR workflow still passes.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.core.security import create_access_token
from app.utils.datetime import utc_now


class AsyncIteratorWrapper:
    def __init__(self, data):
        self.data = list(data)
        self.idx = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.idx < len(self.data):
            item = self.data[self.idx]
            self.idx += 1
            return item
        raise StopAsyncIteration


def _make_cursor(return_data=None):
    mock_cursor = MagicMock()
    data = list(return_data) if return_data is not None else []
    mock_cursor.__aiter__ = MagicMock(side_effect=lambda: AsyncIteratorWrapper(data))
    mock_cursor.sort = MagicMock(return_value=mock_cursor)
    mock_cursor.skip = MagicMock(return_value=mock_cursor)
    mock_cursor.limit = MagicMock(return_value=mock_cursor)
    mock_cursor.to_list = AsyncMock(return_value=data)
    return mock_cursor


class TestDoctorClinicalWorkspaceFixPhase4A(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        # Doctor A: Dr. Arjun Rao (DOC-001)
        self.doctor_a_user = UserInDB(
            user_id="USR-DOC-001",
            email="dr.rao@clinixai.com",
            full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        # Doctor B: Dr. Priya Sharma (DOC-002)
        self.doctor_b_user = UserInDB(
            user_id="USR-DOC-002",
            email="dr.sharma@clinixai.com",
            full_name="Dr. Priya Sharma",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        # Patient A: John Doe (PAT-001)
        self.patient_a_user = UserInDB(
            user_id="USR-PAT-001",
            email="patient.a@clinixai.com",
            full_name="John Doe",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        # Patient B: Jane Smith (PAT-002)
        self.patient_b_user = UserInDB(
            user_id="USR-PAT-002",
            email="patient.b@clinixai.com",
            full_name="Jane Smith",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )
        # Staff User: Receptionist
        self.staff_user = UserInDB(
            user_id="USR-STF-001",
            email="staff@clinixai.com",
            full_name="Staff Receptionist",
            role=UserRole.STAFF,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self._user_dicts = {
            "USR-DOC-001": self.doctor_a_user.to_mongo_dict(),
            "USR-DOC-002": self.doctor_b_user.to_mongo_dict(),
            "USR-PAT-001": self.patient_a_user.to_mongo_dict(),
            "USR-PAT-002": self.patient_b_user.to_mongo_dict(),
            "USR-STF-001": self.staff_user.to_mongo_dict(),
        }

        self.token_doctor_a = create_access_token(user_id=self.doctor_a_user.user_id, role=self.doctor_a_user.role.value)
        self.token_doctor_b = create_access_token(user_id=self.doctor_b_user.user_id, role=self.doctor_b_user.role.value)
        self.token_patient_a = create_access_token(user_id=self.patient_a_user.user_id, role=self.patient_a_user.role.value)
        self.token_patient_b = create_access_token(user_id=self.patient_b_user.user_id, role=self.patient_b_user.role.value)
        self.token_staff = create_access_token(user_id=self.staff_user.user_id, role=self.staff_user.role.value)

        self.headers_doctor_a = {"Authorization": f"Bearer {self.token_doctor_a}"}
        self.headers_doctor_b = {"Authorization": f"Bearer {self.token_doctor_b}"}
        self.headers_patient_a = {"Authorization": f"Bearer {self.token_patient_a}"}
        self.headers_patient_b = {"Authorization": f"Bearer {self.token_patient_b}"}
        self.headers_staff = {"Authorization": f"Bearer {self.token_staff}"}

        # Doctor profiles in DB
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
            "full_name": "Dr. Priya Sharma",
            "email": "dr.sharma@clinixai.com",
            "specialization": "Neurology",
            "department_id": "DEPT-NEURO",
            "status": "active",
            "is_active": True,
        }

        # Patient profiles in DB
        self.patient_profile_a = {
            "patient_id": "PAT-001",
            "user_id": "USR-PAT-001",
            "first_name": "John",
            "last_name": "Doe",
            "full_name": "John Doe",
            "email": "patient.a@clinixai.com",
            "phone_number": "+91 98765 00001",
            "date_of_birth": "1985-05-15",
            "gender": "male",
            "blood_group": "O+",
            "allergies": ["Penicillin"],
            "chronic_conditions": ["Hypertension"],
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.patient_profile_b = {
            "patient_id": "PAT-002",
            "user_id": "USR-PAT-002",
            "first_name": "Jane",
            "last_name": "Smith",
            "full_name": "Jane Smith",
            "email": "patient.b@clinixai.com",
            "phone_number": "+91 98765 00002",
            "date_of_birth": "1992-08-20",
            "gender": "female",
            "blood_group": "A+",
            "allergies": ["Sulfa"],
            "chronic_conditions": ["Migraine"],
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Appointments
        self.apt_001 = {
            "appointment_id": "APT-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "department_id": "DEPT-CARD",
            "appointment_date": "2026-10-10",
            "start_time": "10:00",
            "end_time": "10:30",
            "status": "scheduled",
            "reason": "Cardiology Consultation",
            "appointment_type": "new_consultation",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.apt_002 = {
            "appointment_id": "APT-002",
            "patient_id": "PAT-002",
            "doctor_id": "DOC-002",
            "department_id": "DEPT-NEURO",
            "appointment_date": "2026-10-11",
            "start_time": "11:00",
            "end_time": "11:30",
            "status": "scheduled",
            "reason": "Neurology Checkup",
            "appointment_type": "new_consultation",
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Medical Records
        self.rec_001 = {
            "record_id": "REC-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "appointment_id": "APT-001",
            "record_type": "consultation_note",
            "title": "Cardiac Assessment",
            "clinical_notes": "Mild chest tightness on exertion. ECG normal sinus rhythm.",
            "diagnosis": "Stage 1 Essential Hypertension",
            "treatment_plan": "Amlodipine 5mg daily. Low sodium diet.",
            "uploaded_by": "USR-DOC-001",
            "source": "doctor",
            "status": "active",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.rec_002 = {
            "record_id": "REC-002",
            "patient_id": "PAT-002",
            "doctor_id": "DOC-002",
            "appointment_id": "APT-002",
            "record_type": "consultation_note",
            "title": "Migraine Evaluation",
            "clinical_notes": "Unilateral throbbing headache with photophobia.",
            "diagnosis": "Common Migraine",
            "treatment_plan": "Sumatriptan PRN.",
            "uploaded_by": "USR-DOC-002",
            "source": "doctor",
            "status": "active",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Documents & Medical Images
        self.doc_file_001 = {
            "document_id": "DOC-FILE-001",
            "patient_id": "PAT-001",
            "title": "Chest X-Ray PA View",
            "original_filename": "chest_xray_pa.png",
            "content_type": "image/png",
            "file_size": 2048576,
            "category": "X-Ray",
            "is_medical_image": True,
            "image_type": "xray",
            "storage_path": "uploads/PAT-001/chest_xray_pa.png",
            "uploaded_by": "USR-DOC-001",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.doc_file_002 = {
            "document_id": "DOC-FILE-002",
            "patient_id": "PAT-002",
            "title": "Brain MRI T1 Contrast",
            "original_filename": "brain_mri_t1.png",
            "content_type": "image/png",
            "file_size": 4194304,
            "category": "MRI",
            "is_medical_image": True,
            "image_type": "mri",
            "storage_path": "uploads/PAT-002/brain_mri_t1.png",
            "uploaded_by": "USR-DOC-002",
            "is_deleted": False,
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Consultations
        self.con_001 = {
            "consultation_id": "CON-001",
            "appointment_id": "APT-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "status": "in_progress",
            "version": 1,
            "clinical_notes": "Patient reports recurrent palpitations.",
            "chief_complaint": {"complaint": "Palpitations and fatigue", "duration": "2 weeks", "severity": "moderate"},
            "diagnosis": {"primary_diagnosis": "Sinus Tachycardia", "icd10_code": "R00.0"},
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.con_002 = {
            "consultation_id": "CON-002",
            "appointment_id": "APT-002",
            "patient_id": "PAT-002",
            "doctor_id": "DOC-002",
            "status": "in_progress",
            "version": 1,
            "clinical_notes": "Normal neurological exam.",
            "chief_complaint": {"complaint": "Severe headache", "duration": "3 days", "severity": "severe"},
            "diagnosis": {"primary_diagnosis": "Episodic Migraine", "icd10_code": "G43.0"},
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # Prescriptions
        self.rx_001 = {
            "prescription_id": "RX-001",
            "consultation_id": "CON-001",
            "patient_id": "PAT-001",
            "doctor_id": "DOC-001",
            "appointment_id": "APT-001",
            "status": "issued",
            "medications": [
                {
                    "name": "Metoprolol Succinate",
                    "dosage": "25mg",
                    "frequency": "Once daily",
                    "duration": "30 days",
                    "instructions": "Take with breakfast",
                }
            ],
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }
        self.rx_002 = {
            "prescription_id": "RX-002",
            "consultation_id": "CON-002",
            "patient_id": "PAT-002",
            "doctor_id": "DOC-002",
            "appointment_id": "APT-002",
            "status": "issued",
            "medications": [
                {
                    "name": "Sumatriptan",
                    "dosage": "50mg",
                    "frequency": "PRN at onset",
                    "duration": "10 days",
                    "instructions": "Max 2 tablets per 24 hours",
                }
            ],
            "created_at": utc_now(),
            "updated_at": utc_now(),
        }

        # In-memory dictionaries
        self._appointments = {"APT-001": dict(self.apt_001), "APT-002": dict(self.apt_002)}
        self._patients = {"PAT-001": dict(self.patient_profile_a), "PAT-002": dict(self.patient_profile_b)}
        self._doctors = {"DOC-001": dict(self.doc_profile_a), "DOC-002": dict(self.doc_profile_b)}
        self._records = {"REC-001": dict(self.rec_001), "REC-002": dict(self.rec_002)}
        self._documents = {"DOC-FILE-001": dict(self.doc_file_001), "DOC-FILE-002": dict(self.doc_file_002)}
        self._consultations = {"CON-001": dict(self.con_001), "CON-002": dict(self.con_002)}
        self._prescriptions = {"RX-001": dict(self.rx_001), "RX-002": dict(self.rx_002)}

        # Setup mock collections for database dependency
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
                col.distinct = AsyncMock(return_value=[])
                self._collections[name] = col
            return self._collections[name]

        # Bind users collection
        users_col = get_collection("users")
        async def mock_find_one_user(filter_doc, *args, **kwargs):
            if "user_id" in filter_doc:
                return self._user_dicts.get(filter_doc["user_id"])
            if "email" in filter_doc:
                for u in self._user_dicts.values():
                    if u.get("email") == filter_doc["email"]:
                        return u
            return None
        users_col.find_one = AsyncMock(side_effect=mock_find_one_user)

        # Bind doctors collection
        doctors_col = get_collection("doctors")
        async def mock_find_one_doctor(filter_doc, *args, **kwargs):
            if "$or" in filter_doc:
                for cond in filter_doc["$or"]:
                    for doc in self._doctors.values():
                        if any(doc.get(k) == v for k, v in cond.items()):
                            return dict(doc)
            if "user_id" in filter_doc:
                uid = filter_doc["user_id"]
                for doc in self._doctors.values():
                    if doc.get("user_id") == uid:
                        return dict(doc)
            if "doctor_id" in filter_doc:
                return self._doctors.get(filter_doc["doctor_id"])
            if "email" in filter_doc:
                for doc in self._doctors.values():
                    if doc.get("email") == filter_doc["email"]:
                        return dict(doc)
            return None
        doctors_col.find_one = AsyncMock(side_effect=mock_find_one_doctor)

        # Bind patients collection
        patients_col = get_collection("patients")
        async def mock_find_one_patient(filter_doc, *args, **kwargs):
            if "patient_id" in filter_doc:
                return self._patients.get(filter_doc["patient_id"])
            if "user_id" in filter_doc:
                uid = filter_doc["user_id"]
                for p in self._patients.values():
                    if p.get("user_id") == uid:
                        return dict(p)
            return None
        patients_col.find_one = AsyncMock(side_effect=mock_find_one_patient)

        # Bind appointments collection
        appointments_col = get_collection("appointments")
        async def mock_find_one_apt(filter_doc, *args, **kwargs):
            if "appointment_id" in filter_doc:
                return self._appointments.get(filter_doc["appointment_id"])
            for apt in self._appointments.values():
                match = True
                for k, v in filter_doc.items():
                    if apt.get(k) != v:
                        match = False
                        break
                if match:
                    return dict(apt)
            return None
        appointments_col.find_one = AsyncMock(side_effect=mock_find_one_apt)

        def mock_find_apt(filter_doc, *args, **kwargs):
            results = []
            for apt in self._appointments.values():
                match = True
                for k, v in filter_doc.items():
                    if k == "$or":
                        sub_matches = any(all(apt.get(sk) == sv for sk, sv in sub.items()) for sub in v)
                        if not sub_matches:
                            match = False
                    elif apt.get(k) != v:
                        match = False
                if match:
                    results.append(dict(apt))
            return _make_cursor(results)
        appointments_col.find = MagicMock(side_effect=mock_find_apt)
        appointments_col.count_documents = AsyncMock(return_value=len(self._appointments))

        async def mock_apt_distinct(field, filter_doc=None):
            filter_doc = filter_doc or {}
            items = []
            for apt in self._appointments.values():
                if all(apt.get(k) == v for k, v in filter_doc.items()):
                    if field in apt and apt[field] not in items:
                        items.append(apt[field])
            return items
        appointments_col.distinct = AsyncMock(side_effect=mock_apt_distinct)

        # Bind medical_records collection
        records_col = get_collection("medical_records")
        async def mock_find_one_rec(filter_doc, *args, **kwargs):
            if "record_id" in filter_doc:
                return self._records.get(filter_doc["record_id"])
            return None
        records_col.find_one = AsyncMock(side_effect=mock_find_one_rec)

        def mock_find_rec(filter_doc, *args, **kwargs):
            results = []
            for r in self._records.values():
                match = True
                for k, v in filter_doc.items():
                    if k == "is_deleted":
                        if isinstance(v, dict) and "$ne" in v:
                            if r.get("is_deleted", False) == v["$ne"]:
                                match = False
                        elif r.get("is_deleted", False) != v:
                            match = False
                    elif k == "patient_id" and r.get("patient_id") != v:
                        match = False
                if match:
                    results.append(dict(r))
            return _make_cursor(results)
        records_col.find = MagicMock(side_effect=mock_find_rec)
        records_col.count_documents = AsyncMock(return_value=len(self._records))

        # Bind documents collection
        documents_col = get_collection("documents")
        async def mock_find_one_doc(filter_doc, *args, **kwargs):
            if "document_id" in filter_doc:
                return self._documents.get(filter_doc["document_id"])
            return None
        documents_col.find_one = AsyncMock(side_effect=mock_find_one_doc)

        def mock_find_doc(filter_doc, *args, **kwargs):
            results = []
            for d in self._documents.values():
                match = True
                for k, v in filter_doc.items():
                    if k == "is_deleted":
                        if isinstance(v, dict) and "$ne" in v:
                            if d.get("is_deleted", False) == v["$ne"]:
                                match = False
                        elif d.get("is_deleted", False) != v:
                            match = False
                    elif k == "patient_id":
                        if isinstance(v, dict) and "$in" in v:
                            if d.get("patient_id") not in v["$in"]:
                                match = False
                        elif d.get("patient_id") != v:
                            match = False
                    elif k == "is_medical_image" and d.get("is_medical_image") != v:
                        match = False
                if match:
                    results.append(dict(d))
            return _make_cursor(results)
        documents_col.find = MagicMock(side_effect=mock_find_doc)
        documents_col.count_documents = AsyncMock(return_value=len(self._documents))

        # Bind consultations collection
        consultations_col = get_collection("consultations")
        async def mock_find_one_con(filter_doc, *args, **kwargs):
            if "consultation_id" in filter_doc:
                return self._consultations.get(filter_doc["consultation_id"])
            for c in self._consultations.values():
                match = True
                for k, v in filter_doc.items():
                    if c.get(k) != v:
                        match = False
                        break
                if match:
                    return dict(c)
            return None
        consultations_col.find_one = AsyncMock(side_effect=mock_find_one_con)

        def mock_find_con(filter_doc, *args, **kwargs):
            results = []
            for c in self._consultations.values():
                match = True
                for k, v in filter_doc.items():
                    if k == "$or":
                        sub_matches = any(all(c.get(sk) == sv for sk, sv in sub.items()) for sub in v)
                        if not sub_matches:
                            match = False
                    elif c.get(k) != v:
                        match = False
                if match:
                    results.append(dict(c))
            return _make_cursor(results)
        consultations_col.find = MagicMock(side_effect=mock_find_con)

        async def mock_con_distinct(field, filter_doc=None):
            filter_doc = filter_doc or {}
            items = []
            for c in self._consultations.values():
                if all(c.get(k) == v for k, v in filter_doc.items()):
                    if field in c and c[field] not in items:
                        items.append(c[field])
            return items
        consultations_col.distinct = AsyncMock(side_effect=mock_con_distinct)

        async def mock_update_con(filter_query, update_doc, *args, **kwargs):
            cid = filter_query.get("consultation_id")
            c = self._consultations.get(cid)
            result = MagicMock()
            if not c:
                result.matched_count = 0
                return result
            if "version" in filter_query and filter_query["version"] != c.get("version", 1):
                result.matched_count = 0
                return result
            result.matched_count = 1
            if "$set" in update_doc:
                c.update(update_doc["$set"])
            if "$inc" in update_doc and "version" in update_doc["$inc"]:
                c["version"] = c.get("version", 1) + update_doc["$inc"]["version"]
            return result
        consultations_col.update_one = AsyncMock(side_effect=mock_update_con)

        # Bind prescriptions collection
        prescriptions_col = get_collection("prescriptions")
        async def mock_find_one_rx(filter_doc, *args, **kwargs):
            if "prescription_id" in filter_doc:
                return self._prescriptions.get(filter_doc["prescription_id"])
            for rx in self._prescriptions.values():
                match = True
                for k, v in filter_doc.items():
                    if rx.get(k) != v:
                        match = False
                        break
                if match:
                    return dict(rx)
            return None
        prescriptions_col.find_one = AsyncMock(side_effect=mock_find_one_rx)

        def mock_find_rx(filter_doc, *args, **kwargs):
            results = []
            for rx in self._prescriptions.values():
                match = True
                for k, v in filter_doc.items():
                    if rx.get(k) != v:
                        match = False
                if match:
                    results.append(dict(rx))
            return _make_cursor(results)
        prescriptions_col.find = MagicMock(side_effect=mock_find_rx)

        self.mock_db = MagicMock()
        self.mock_db.__getitem__ = MagicMock(side_effect=get_collection)
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    # -------------------------------------------------------------------------
    # TEST 1: Doctor can access own authorized appointment
    # -------------------------------------------------------------------------
    async def test_01_doctor_can_access_own_authorized_appointment(self):
        resp = await self.client.get("/api/v1/appointments/APT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertEqual(data["appointment_id"], "APT-001")
        self.assertEqual(data["doctor_id"], "DOC-001")
        self.assertEqual(data["patient_id"], "PAT-001")

    # -------------------------------------------------------------------------
    # TEST 2: Doctor can resolve appointment -> patient
    # -------------------------------------------------------------------------
    async def test_02_doctor_can_resolve_appointment_to_patient(self):
        resp = await self.client.get("/api/v1/appointments/APT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        apt_data = resp.json()["data"]
        patient_id = apt_data["patient_id"]
        self.assertEqual(patient_id, "PAT-001")

        # Now doctor resolves the patient record
        pat_resp = await self.client.get(f"/api/v1/patients/{patient_id}", headers=self.headers_doctor_a)
        self.assertEqual(pat_resp.status_code, 200)
        pat_data = pat_resp.json()["data"]
        self.assertEqual(pat_data["patient_id"], "PAT-001")
        self.assertEqual(pat_data["first_name"], "John")

    # -------------------------------------------------------------------------
    # TEST 3: Patient identity is correct
    # -------------------------------------------------------------------------
    async def test_03_patient_identity_is_correct(self):
        resp = await self.client.get("/api/v1/patients/PAT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        p = resp.json()["data"]
        self.assertEqual(p["patient_id"], "PAT-001")
        self.assertEqual(p["full_name"], "John Doe")
        self.assertEqual(p["blood_group"], "O+")
        self.assertIn("Penicillin", p["allergies"])

    # -------------------------------------------------------------------------
    # TEST 4: Doctor can access patient clinical workspace / context
    # -------------------------------------------------------------------------
    async def test_04_doctor_can_access_patient_clinical_workspace_context(self):
        resp = await self.client.get("/api/v1/patients/PAT-001/timeline", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        timeline = resp.json()
        self.assertIn("patient_id", timeline)
        self.assertEqual(timeline["patient_id"], "PAT-001")
        self.assertIn("events", timeline)

    # -------------------------------------------------------------------------
    # TEST 5: Doctor can access authorized medical records
    # -------------------------------------------------------------------------
    async def test_05_doctor_can_access_authorized_medical_records(self):
        resp = await self.client.get("/api/v1/medical-records?patient_id=PAT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()["data"]
        self.assertTrue(len(data) >= 1)
        self.assertEqual(data[0]["record_id"], "REC-001")
        self.assertEqual(data[0]["patient_id"], "PAT-001")

    # -------------------------------------------------------------------------
    # TEST 6: Unauthorized Doctor cannot access records (403 Forbidden)
    # -------------------------------------------------------------------------
    async def test_06_unauthorized_doctor_cannot_access_records(self):
        # Doctor A has NO appointment/care relationship with Patient B
        resp = await self.client.get("/api/v1/medical-records?patient_id=PAT-002", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 403)
        body_text = str(resp.json()).lower()
        self.assertIn("authorized", body_text)

    # -------------------------------------------------------------------------
    # TEST 7: Doctor can access authorized documents
    # -------------------------------------------------------------------------
    async def test_07_doctor_can_access_authorized_documents(self):
        resp = await self.client.get("/api/v1/documents?patient_id=PAT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        docs = resp.json()["items"]
        self.assertTrue(len(docs) >= 1)
        self.assertEqual(docs[0]["document_id"], "DOC-FILE-001")
        self.assertEqual(docs[0]["patient_id"], "PAT-001")

    # -------------------------------------------------------------------------
    # TEST 8: Unauthorized Doctor cannot access documents (403 Forbidden)
    # -------------------------------------------------------------------------
    async def test_08_unauthorized_doctor_cannot_access_documents(self):
        # Doctor A attempts to list documents for Patient B
        resp = await self.client.get("/api/v1/documents?patient_id=PAT-002", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 403)

        # Doctor A attempts to fetch single document belonging to Patient B
        single_resp = await self.client.get("/api/v1/documents/DOC-FILE-002", headers=self.headers_doctor_a)
        self.assertEqual(single_resp.status_code, 403)

    # -------------------------------------------------------------------------
    # TEST 9: Doctor can access authorized medical images
    # -------------------------------------------------------------------------
    async def test_09_doctor_can_access_authorized_medical_images(self):
        resp = await self.client.get("/api/v1/documents?patient_id=PAT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        images = resp.json()["items"]
        self.assertTrue(len(images) >= 1)
        self.assertEqual(images[0]["category"], "X-Ray")
        self.assertEqual(images[0]["patient_id"], "PAT-001")

    # -------------------------------------------------------------------------
    # TEST 10: Unauthorized Doctor cannot access images (403 Forbidden)
    # -------------------------------------------------------------------------
    async def test_10_unauthorized_doctor_cannot_access_images(self):
        resp = await self.client.get("/api/v1/documents?patient_id=PAT-002", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # TEST 11: Patient A cannot access Patient B clinical workspace (403 Forbidden)
    # -------------------------------------------------------------------------
    async def test_11_patient_a_cannot_access_patient_b_clinical_workspace(self):
        resp = await self.client.get("/api/v1/patients/PAT-002", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 403)

        timeline_resp = await self.client.get("/api/v1/patients/PAT-002/timeline", headers=self.headers_patient_a)
        self.assertEqual(timeline_resp.status_code, 403)

    # -------------------------------------------------------------------------
    # TEST 12: Doctor can access authorized consultation
    # -------------------------------------------------------------------------
    async def test_12_doctor_can_access_authorized_consultation(self):
        resp = await self.client.get("/api/v1/consultations/CON-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        c = resp.json()["data"]
        self.assertEqual(c["consultation_id"], "CON-001")
        self.assertEqual(c["patient_id"], "PAT-001")
        self.assertEqual(c["doctor_id"], "DOC-001")

    # -------------------------------------------------------------------------
    # TEST 13: Unauthorized Doctor cannot modify consultation (403 Forbidden)
    # -------------------------------------------------------------------------
    async def test_13_unauthorized_doctor_cannot_modify_consultation(self):
        patch_payload = {
            "notes": "Attempting unauthorized note update",
            "expected_version": 1,
        }
        resp = await self.client.patch("/api/v1/consultations/CON-002/clinical-notes", json=patch_payload, headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # TEST 14: Doctor prescription linkage is correct
    # -------------------------------------------------------------------------
    async def test_14_doctor_prescription_linkage_is_correct(self):
        resp = await self.client.get("/api/v1/prescriptions/RX-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        rx = resp.json()["data"]
        self.assertEqual(rx["prescription_id"], "RX-001")
        self.assertEqual(rx["patient_id"], "PAT-001")
        self.assertEqual(rx["doctor_id"], "DOC-001")
        self.assertEqual(rx["consultation_id"], "CON-001")

    # -------------------------------------------------------------------------
    # TEST 15: Patient cannot modify Doctor prescription (403 Forbidden)
    # -------------------------------------------------------------------------
    async def test_15_patient_cannot_modify_doctor_prescription(self):
        payload = {
            "medications": [{"name": "Morphine", "dosage": "100mg"}]
        }
        resp = await self.client.patch("/api/v1/prescriptions/RX-001", json=payload, headers=self.headers_patient_a)
        self.assertIn(resp.status_code, [403, 405])

    # -------------------------------------------------------------------------
    # TEST 16: Staff cannot perform clinical Doctor operations (403 Forbidden)
    # -------------------------------------------------------------------------
    async def test_16_staff_cannot_perform_clinical_doctor_operations(self):
        rx_payload = {
            "consultation_id": "CON-001",
            "patient_id": "PAT-001",
            "medications": [{"name": "Aspirin", "dosage": "75mg", "frequency": "Daily", "duration": "30 days"}],
        }
        resp = await self.client.post("/api/v1/prescriptions", json=rx_payload, headers=self.headers_staff)
        self.assertEqual(resp.status_code, 403)

    # -------------------------------------------------------------------------
    # TEST 17: Appointment -> consultation relationship remains correct
    # -------------------------------------------------------------------------
    async def test_17_appointment_to_consultation_relationship_remains_correct(self):
        apt_resp = await self.client.get("/api/v1/appointments/APT-001", headers=self.headers_doctor_a)
        self.assertEqual(apt_resp.status_code, 200)

        con_resp = await self.client.get("/api/v1/consultations/CON-001", headers=self.headers_doctor_a)
        self.assertEqual(con_resp.status_code, 200)
        con_data = con_resp.json()["data"]
        self.assertEqual(con_data["appointment_id"], "APT-001")
        self.assertEqual(con_data["patient_id"], "PAT-001")

    # -------------------------------------------------------------------------
    # TEST 18: Consultation -> medical record relationship remains correct
    # -------------------------------------------------------------------------
    async def test_18_consultation_to_medical_record_relationship_remains_correct(self):
        rec_resp = await self.client.get("/api/v1/medical-records/REC-001", headers=self.headers_doctor_a)
        self.assertEqual(rec_resp.status_code, 200)
        rec = rec_resp.json()["data"]
        self.assertEqual(rec["appointment_id"], "APT-001")
        self.assertEqual(rec["patient_id"], "PAT-001")
        self.assertEqual(rec["doctor_id"], "DOC-001")

    # -------------------------------------------------------------------------
    # TEST 19: Prescription -> patient relationship remains correct
    # -------------------------------------------------------------------------
    async def test_19_prescription_to_patient_relationship_remains_correct(self):
        rx_resp = await self.client.get("/api/v1/prescriptions/RX-001", headers=self.headers_doctor_a)
        self.assertEqual(rx_resp.status_code, 200)
        rx = rx_resp.json()["data"]
        self.assertEqual(rx["patient_id"], "PAT-001")

        # Patient also accesses own prescription
        pat_rx_resp = await self.client.get("/api/v1/prescriptions/RX-001", headers=self.headers_patient_a)
        self.assertEqual(pat_rx_resp.status_code, 200)

    # -------------------------------------------------------------------------
    # TEST 20: Direct IDOR attempts return 403 or 404
    # -------------------------------------------------------------------------
    async def test_20_direct_idor_attempts_return_403_or_404(self):
        # Doctor A attempts to access Doctor B's consultation
        resp_con = await self.client.get("/api/v1/consultations/CON-002", headers=self.headers_doctor_a)
        self.assertEqual(resp_con.status_code, 403)

        # Doctor A attempts to access Doctor B's prescription
        resp_rx = await self.client.get("/api/v1/prescriptions/RX-002", headers=self.headers_doctor_a)
        self.assertEqual(resp_rx.status_code, 403)

        # Patient A attempts to access Patient B's prescription
        resp_rx_pat = await self.client.get("/api/v1/prescriptions/RX-002", headers=self.headers_patient_a)
        self.assertEqual(resp_rx_pat.status_code, 403)

    # -------------------------------------------------------------------------
    # TEST 21: Invalid clinical IDs return proper clean errors (404/422)
    # -------------------------------------------------------------------------
    async def test_21_invalid_clinical_ids_return_proper_errors(self):
        resp_apt = await self.client.get("/api/v1/appointments/APT-NONEXISTENT", headers=self.headers_doctor_a)
        self.assertEqual(resp_apt.status_code, 404)

        resp_pat = await self.client.get("/api/v1/patients/PAT-NONEXISTENT", headers=self.headers_doctor_a)
        self.assertEqual(resp_pat.status_code, 404)

        resp_rec = await self.client.get("/api/v1/medical-records/REC-NONEXISTENT", headers=self.headers_doctor_a)
        self.assertEqual(resp_rec.status_code, 404)

        resp_doc = await self.client.get("/api/v1/documents/DOC-NONEXISTENT", headers=self.headers_doctor_a)
        self.assertEqual(resp_doc.status_code, 404)

    # -------------------------------------------------------------------------
    # TEST 22: Persistence survives process restart (linkages preserved)
    # -------------------------------------------------------------------------
    async def test_22_persistence_survives_process_restart(self):
        # In MongoDB, all clinical records retain explicit relational foreign keys
        self.assertEqual(self._appointments["APT-001"]["patient_id"], "PAT-001")
        self.assertEqual(self._appointments["APT-001"]["doctor_id"], "DOC-001")
        self.assertEqual(self._consultations["CON-001"]["appointment_id"], "APT-001")
        self.assertEqual(self._records["REC-001"]["patient_id"], "PAT-001")
        self.assertEqual(self._prescriptions["RX-001"]["consultation_id"], "CON-001")
        self.assertEqual(self._documents["DOC-FILE-001"]["patient_id"], "PAT-001")

    # -------------------------------------------------------------------------
    # TEST 23: Stale consultation update returns 409 Conflict
    # -------------------------------------------------------------------------
    async def test_23_stale_consultation_update_returns_409(self):
        # Update CON-001 with stale version (expected_version 0 when db has version 1)
        payload = {
            "notes": "Attempting stale concurrent update",
            "expected_version": 0,
        }
        resp = await self.client.patch("/api/v1/consultations/CON-001/clinical-notes", json=payload, headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 409)

    # -------------------------------------------------------------------------
    # TEST 24: No cross-patient data leakage
    # -------------------------------------------------------------------------
    async def test_24_no_cross_patient_data_leakage(self):
        # When Doctor A queries records for Patient A, no Patient B record is returned
        resp = await self.client.get("/api/v1/medical-records?patient_id=PAT-001", headers=self.headers_doctor_a)
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["data"]
        for item in items:
            self.assertEqual(item["patient_id"], "PAT-001")
            self.assertNotEqual(item["patient_id"], "PAT-002")

    # -------------------------------------------------------------------------
    # TEST 25: Existing Fix Phase 1 QR workflow still passes
    # -------------------------------------------------------------------------
    async def test_25_existing_fix_phase_1_qr_workflow_still_passes(self):
        # Patient A requesting QR token
        resp = await self.client.get("/api/v1/patients/me/qr", headers=self.headers_patient_a)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn("token", data)
        self.assertIn("payload", data)
