"""Unified search backend service for CliniXAI collections."""

import re
from typing import List, Optional, Dict, Any
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS, COLLECTION_STAFF,
    COLLECTION_DEPARTMENTS, COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS,
    COLLECTION_MEDICAL_RECORDS, COLLECTION_PRESCRIPTIONS, COLLECTION_BILLING,
    COLLECTION_AI_ANALYSES, COLLECTION_NOTIFICATIONS, COLLECTION_DOCUMENTS
)
from app.schemas.search import SearchResultItem, SearchResponse
from app.models.user import UserInDB, UserRole


class SearchService:
    """Service executing multi-collection regex and text searches with RBAC scoping."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db

    async def search(
        self,
        query_str: str,
        user: UserInDB,
        resource_types: Optional[List[str]] = None,
        limit_per_resource: int = 10,
    ) -> SearchResponse:
        """Performs unified search across authorized resources for the current user."""
        clean_query = query_str.strip()
        if not clean_query:
            return SearchResponse(query=query_str, total_matches=0, results=[])

        regex_pattern = re.compile(re.escape(clean_query), re.IGNORECASE)
        results: List[SearchResultItem] = []

        is_admin = user.role in (UserRole.HOSPITAL_ADMIN, UserRole.ADMIN)
        is_doctor = user.role == UserRole.DOCTOR
        is_staff = user.role in (UserRole.HOSPITAL_STAFF, UserRole.STAFF)
        is_patient = user.role == UserRole.PATIENT

        # 1. Patients
        if not resource_types or "patient" in resource_types or "patients" in resource_types:
            p_filter: Dict[str, Any] = {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"first_name": regex_pattern},
                    {"last_name": regex_pattern},
                    {"email": regex_pattern},
                    {"phone": regex_pattern},
                    {"patient_id": regex_pattern},
                ]
            }
            if is_patient:
                p_filter["user_id"] = user.user_id

            cursor = self.db[COLLECTION_PATIENTS].find(p_filter).limit(limit_per_resource)
            async for doc in cursor:
                results.append(
                    SearchResultItem(
                        resource_type="patient",
                        resource_id=doc["patient_id"],
                        title=f"{doc.get('first_name', '')} {doc.get('last_name', '')}".strip(),
                        subtitle=doc.get("email") or doc.get("phone"),
                        status=doc.get("status"),
                        created_at=doc.get("created_at"),
                        details={"gender": doc.get("gender"), "blood_group": doc.get("blood_group")},
                    )
                )

        # 2. Doctors
        if not resource_types or "doctor" in resource_types or "doctors" in resource_types:
            d_filter: Dict[str, Any] = {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"first_name": regex_pattern},
                    {"last_name": regex_pattern},
                    {"email": regex_pattern},
                    {"specialization": regex_pattern},
                    {"doctor_id": regex_pattern},
                ]
            }
            cursor = self.db[COLLECTION_DOCTORS].find(d_filter).limit(limit_per_resource)
            async for doc in cursor:
                results.append(
                    SearchResultItem(
                        resource_type="doctor",
                        resource_id=doc["doctor_id"],
                        title=f"Dr. {doc.get('first_name', '')} {doc.get('last_name', '')}".strip(),
                        subtitle=doc.get("specialization") or doc.get("email"),
                        status=doc.get("status"),
                        created_at=doc.get("created_at"),
                        details={"department_id": doc.get("department_id")},
                    )
                )

        # 3. Staff
        if (is_admin or is_staff) and (not resource_types or "staff" in resource_types):
            st_filter: Dict[str, Any] = {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"first_name": regex_pattern},
                    {"last_name": regex_pattern},
                    {"email": regex_pattern},
                    {"job_title": regex_pattern},
                    {"staff_id": regex_pattern},
                ]
            }
            cursor = self.db[COLLECTION_STAFF].find(st_filter).limit(limit_per_resource)
            async for doc in cursor:
                results.append(
                    SearchResultItem(
                        resource_type="staff",
                        resource_id=doc["staff_id"],
                        title=f"{doc.get('first_name', '')} {doc.get('last_name', '')}".strip(),
                        subtitle=doc.get("job_title") or doc.get("email"),
                        status=doc.get("status"),
                        created_at=doc.get("created_at"),
                        details={"department_id": doc.get("department_id")},
                    )
                )

        # 4. Departments
        if not resource_types or "department" in resource_types or "departments" in resource_types:
            dept_filter: Dict[str, Any] = {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"name": regex_pattern},
                    {"code": regex_pattern},
                    {"description": regex_pattern},
                ]
            }
            cursor = self.db[COLLECTION_DEPARTMENTS].find(dept_filter).limit(limit_per_resource)
            async for doc in cursor:
                results.append(
                    SearchResultItem(
                        resource_type="department",
                        resource_id=doc["department_id"],
                        title=doc.get("name", ""),
                        subtitle=f"Code: {doc.get('code')}",
                        status=doc.get("status"),
                        created_at=doc.get("created_at"),
                        details={"location": doc.get("location")},
                    )
                )

        # 5. Appointments
        if not resource_types or "appointment" in resource_types or "appointments" in resource_types:
            apt_filter: Dict[str, Any] = {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"appointment_id": regex_pattern},
                    {"reason": regex_pattern},
                    {"appointment_date": regex_pattern},
                ]
            }
            cursor = self.db[COLLECTION_APPOINTMENTS].find(apt_filter).limit(limit_per_resource)
            async for doc in cursor:
                results.append(
                    SearchResultItem(
                        resource_type="appointment",
                        resource_id=doc["appointment_id"],
                        title=f"Appointment {doc.get('appointment_id')}",
                        subtitle=f"Date: {doc.get('appointment_date')} {doc.get('start_time')}",
                        status=doc.get("status"),
                        created_at=doc.get("created_at"),
                        details={"doctor_id": doc.get("doctor_id"), "patient_id": doc.get("patient_id")},
                    )
                )

        # 6. Consultations
        if not resource_types or "consultation" in resource_types or "consultations" in resource_types:
            c_filter: Dict[str, Any] = {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"consultation_id": regex_pattern},
                    {"chief_complaint.complaint": regex_pattern},
                    {"clinical_notes": regex_pattern},
                ]
            }
            cursor = self.db[COLLECTION_CONSULTATIONS].find(c_filter).limit(limit_per_resource)
            async for doc in cursor:
                results.append(
                    SearchResultItem(
                        resource_type="consultation",
                        resource_id=doc["consultation_id"],
                        title=f"Consultation {doc.get('consultation_id')}",
                        subtitle=doc.get("chief_complaint", {}).get("complaint") if isinstance(doc.get("chief_complaint"), dict) else "Consultation Record",
                        status=doc.get("status"),
                        created_at=doc.get("created_at"),
                        details={"patient_id": doc.get("patient_id"), "doctor_id": doc.get("doctor_id")},
                    )
                )

        # 7. Medical Documents
        if not resource_types or "document" in resource_types or "documents" in resource_types:
            doc_filter: Dict[str, Any] = {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"title": regex_pattern},
                    {"original_file_name": regex_pattern},
                    {"notes": regex_pattern},
                    {"category": regex_pattern},
                ]
            }
            cursor = self.db[COLLECTION_DOCUMENTS].find(doc_filter).limit(limit_per_resource)
            async for doc in cursor:
                results.append(
                    SearchResultItem(
                        resource_type="document",
                        resource_id=doc["document_id"],
                        title=doc.get("title", doc.get("original_file_name")),
                        subtitle=f"Category: {doc.get('category')}",
                        status="active",
                        created_at=doc.get("created_at"),
                        details={"mime_type": doc.get("mime_type"), "file_size_bytes": doc.get("file_size_bytes")},
                    )
                )

        # 8. User Accounts (Admin Only)
        if is_admin and (not resource_types or "user" in resource_types or "users" in resource_types):
            u_filter: Dict[str, Any] = {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"email": regex_pattern},
                    {"full_name": regex_pattern},
                    {"user_id": regex_pattern},
                ]
            }
            cursor = self.db[COLLECTION_USERS].find(u_filter).limit(limit_per_resource)
            async for doc in cursor:
                results.append(
                    SearchResultItem(
                        resource_type="user",
                        resource_id=doc["user_id"],
                        title=doc.get("full_name") or doc.get("email"),
                        subtitle=f"Role: {doc.get('role')} • {doc.get('email')}",
                        status=doc.get("account_status"),
                        created_at=doc.get("created_at"),
                        details={"role": doc.get("role"), "email_verified": doc.get("email_verified")},
                    )
                )

        return SearchResponse(
            query=query_str,
            total_matches=len(results),
            results=results,
        )
