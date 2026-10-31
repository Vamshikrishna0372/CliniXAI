"""Medical Document service for managing secure upload, metadata, retrieval, and deletion."""

import os
import uuid
from typing import Optional, List, Tuple, Any
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import COLLECTION_DOCUMENTS
from app.models.document import MedicalDocumentInDB, DocumentCategory
from app.schemas.documents import DocumentMetadataUpdateRequest
from app.services.storage_service import storage_service
from app.utils.file_validation import (
    validate_file_content,
    generate_secure_storage_key,
)
from app.core.exceptions import NotFoundError, ForbiddenError, AppValidationError
from app.utils.datetime import utc_now


class DocumentService:
    """Service handling medical document lifecycle."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[COLLECTION_DOCUMENTS]
        self.storage = storage_service

    async def upload_document(
        self,
        patient_id: str,
        uploaded_by: str,
        title: str,
        category: DocumentCategory,
        original_filename: str,
        content_type: str,
        content_bytes: bytes,
        notes: Optional[str] = None,
        consultation_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        medical_record_id: Optional[str] = None,
        ai_analysis_id: Optional[str] = None,
    ) -> MedicalDocumentInDB:
        """Validates and stores medical document upload with metadata persistence."""
        # Defensive check: ensure canonical patient_id is always stored
        if str(patient_id).startswith("USR-"):
            from app.database.collections import COLLECTION_PATIENTS
            pat_rec = await self.db[COLLECTION_PATIENTS].find_one({"user_id": patient_id})
            if pat_rec and pat_rec.get("patient_id"):
                patient_id = pat_rec["patient_id"]

        val_result = validate_file_content(original_filename, content_type, content_bytes)
        storage_filename, ext = generate_secure_storage_key(original_filename)

        storage_path = await self.storage.save_file(
            content_bytes, storage_filename, subfolder="documents"
        )

        doc_id = f"DOC-{uuid.uuid4().hex[:12].upper()}"

        # Resolve uploader role and name directly
        uploader_role = "unknown"
        uploader_name = "Unknown"
        if uploaded_by and uploaded_by != "system" and uploaded_by != "None":
            from app.database.collections import COLLECTION_USERS, COLLECTION_DOCTORS, COLLECTION_PATIENTS, COLLECTION_STAFF
            user_rec = await self.db[COLLECTION_USERS].find_one({"user_id": uploaded_by})
            if user_rec:
                uploader_role = str(user_rec.get("role", "unknown")).lower()
                uploader_name = user_rec.get("full_name") or user_rec.get("name")
            if not uploader_name or uploader_role == "unknown":
                doc_rec = await self.db[COLLECTION_DOCTORS].find_one({"$or": [{"user_id": uploaded_by}, {"doctor_id": uploaded_by}]})
                if doc_rec:
                    uploader_role = "doctor"
                    uploader_name = doc_rec.get("full_name") or doc_rec.get("name") or "Doctor"
                else:
                    pat_rec = await self.db[COLLECTION_PATIENTS].find_one({"$or": [{"user_id": uploaded_by}, {"patient_id": uploaded_by}]})
                    if pat_rec:
                        uploader_role = "patient"
                        uploader_name = pat_rec.get("full_name") or f"{pat_rec.get('first_name', '')} {pat_rec.get('last_name', '')}".strip() or "Patient"
                    else:
                        staff_rec = await self.db[COLLECTION_STAFF].find_one({"$or": [{"user_id": uploaded_by}, {"staff_id": uploaded_by}]})
                        if staff_rec:
                            uploader_role = "staff"
                            uploader_name = staff_rec.get("full_name") or staff_rec.get("name") or "Staff"

        modality = "Other"
        if category == DocumentCategory.MRI:
            modality = "Brain MRI"
        elif category == DocumentCategory.XRAY:
            modality = "Chest X-Ray"
        elif category == DocumentCategory.CT:
            modality = "CT Scan"
        elif category == DocumentCategory.DERMOSCOPY:
            modality = "Skin Dermoscopy"
        elif category == DocumentCategory.FUNDUS:
            modality = "Retinal Fundus"
        else:
            modality = category.value if hasattr(category, "value") else str(category)

        document = MedicalDocumentInDB(
            document_id=doc_id,
            patient_id=patient_id,
            uploaded_by=uploaded_by,
            uploaded_by_user_id=uploaded_by,
            uploader_role=uploader_role,
            uploader_name=uploader_name,
            title=title,
            category=category,
            modality=modality,
            file_name=storage_filename,
            original_file_name=val_result.filename,
            mime_type=val_result.content_type,
            file_size_bytes=val_result.size_bytes,
            storage_path=storage_path,
            notes=notes,
            consultation_id=consultation_id,
            appointment_id=appointment_id,
            medical_record_id=medical_record_id,
            ai_analysis_id=ai_analysis_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        try:
            await self.collection.insert_one(document.to_mongo_dict())
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(self.db)
        except Exception as exc:
            await self.storage.delete_file(storage_filename, subfolder="documents")
            raise exc

        # Audit Log & Notification
        try:
            from app.services.audit_service import log_audit_event
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType
            from app.database.collections import COLLECTION_PATIENTS

            await log_audit_event(
                db=self.db,
                actor_id=uploaded_by,
                role="user",
                action="upload_document",
                resource="document",
                resource_id=doc_id,
                metadata={"patient_id": patient_id, "consultation_id": consultation_id, "title": title},
            )

            patient = await self.db[COLLECTION_PATIENTS].find_one({"patient_id": patient_id})
            if patient and patient.get("user_id"):
                await NotificationService.dispatch(
                    db=self.db,
                    recipient_user_id=patient["user_id"],
                    notification_type=NotificationType.CLINICAL,
                    title="Medical Document Uploaded",
                    body=f"Document '{title}' has been uploaded and linked to your records.",
                    reference_id=doc_id,
                    reference_type="document",
                )
        except Exception as exc:
            pass

        return document

    async def enrich_document_provenance(self, doc_dict: dict) -> dict:
        """Ensures document has complete uploader provenance, modality, and AI analysis status."""
        d = dict(doc_dict)
        uploaded_by = d.get("uploaded_by") or d.get("uploaded_by_user_id")
        d["uploaded_by"] = uploaded_by or "unknown"
        d["uploaded_by_user_id"] = uploaded_by

        if not d.get("uploader_role") or not d.get("uploader_name") or d.get("uploader_role") == "unknown":
            from app.database.collections import COLLECTION_USERS, COLLECTION_DOCTORS, COLLECTION_PATIENTS, COLLECTION_STAFF
            u_role = "unknown"
            u_name = "Unknown"
            if uploaded_by and uploaded_by != "system" and uploaded_by != "None":
                user_rec = await self.db[COLLECTION_USERS].find_one({"user_id": uploaded_by})
                if user_rec:
                    u_role = str(user_rec.get("role", "unknown")).lower()
                    u_name = user_rec.get("full_name") or user_rec.get("name")
                if not u_name or u_role == "unknown":
                    doc_rec = await self.db[COLLECTION_DOCTORS].find_one({"$or": [{"user_id": uploaded_by}, {"doctor_id": uploaded_by}]})
                    if doc_rec:
                        u_role = "doctor"
                        u_name = doc_rec.get("full_name") or doc_rec.get("name") or "Doctor"
                    else:
                        pat_rec = await self.db[COLLECTION_PATIENTS].find_one({"$or": [{"user_id": uploaded_by}, {"patient_id": uploaded_by}]})
                        if pat_rec:
                            u_role = "patient"
                            u_name = pat_rec.get("full_name") or f"{pat_rec.get('first_name', '')} {pat_rec.get('last_name', '')}".strip() or "Patient"
                        else:
                            staff_rec = await self.db[COLLECTION_STAFF].find_one({"$or": [{"user_id": uploaded_by}, {"staff_id": uploaded_by}]})
                            if staff_rec:
                                u_role = "staff"
                                u_name = staff_rec.get("full_name") or staff_rec.get("name") or "Staff"
            d["uploader_role"] = u_role
            d["uploader_name"] = u_name

        # Modality
        if not d.get("modality"):
            cat = str(d.get("category", "")).lower()
            title = str(d.get("title", "")).lower()
            fn = str(d.get("original_file_name", "")).lower()
            if "mri" in cat or "mri" in title or "mri" in fn or "brain" in title:
                d["modality"] = "Brain MRI"
            elif "xray" in cat or "x-ray" in cat or "xray" in title or "x-ray" in title:
                d["modality"] = "Chest X-Ray"
            elif "ct" in cat or "ct" in title:
                d["modality"] = "CT Scan"
            elif "derm" in cat or "skin" in cat:
                d["modality"] = "Skin Dermoscopy"
            elif "fundus" in cat or "retin" in cat:
                d["modality"] = "Retinal Fundus"
            else:
                d["modality"] = d.get("category") or "Other"

        # AI Analysis status
        from app.database.collections import COLLECTION_AI_ANALYSES
        ai_id = d.get("ai_analysis_id")
        if not ai_id:
            an_rec = await self.db[COLLECTION_AI_ANALYSES].find_one({"document_id": d.get("document_id"), "is_deleted": {"$ne": True}})
            if an_rec:
                d["ai_analysis_id"] = an_rec.get("analysis_id")
                d["ai_analysis_status"] = an_rec.get("status")
        elif not d.get("ai_analysis_status"):
            an_rec = await self.db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": ai_id})
            if an_rec:
                d["ai_analysis_status"] = an_rec.get("status")

        return d

    async def get_document(self, document_id: str) -> MedicalDocumentInDB:
        """Retrieves document metadata by ID."""
        doc = await self.collection.find_one({"document_id": document_id, "is_deleted": {"$ne": True}})
        if not doc:
            raise NotFoundError(f"Medical document '{document_id}' not found.")
        enriched = await self.enrich_document_provenance(doc)
        return MedicalDocumentInDB(**enriched)

    async def read_document_bytes(self, document_id: str) -> Tuple[bytes, MedicalDocumentInDB]:
        """Reads document raw content bytes from storage for streaming."""
        document = await self.get_document(document_id)
        keys_to_try = [document.file_name]
        storage_key = getattr(document, "storage_key", None)
        if storage_key and storage_key not in keys_to_try:
            keys_to_try.append(storage_key)

        for key in keys_to_try:
            for subfolder in ["documents", "medical-records", "ai-analyses"]:
                try:
                    content_bytes = await self.storage.read_file(key, subfolder=subfolder)
                    return content_bytes, document
                except Exception:
                    continue

        raise NotFoundError(f"File for document '{document_id}' not found in storage.")

    async def list_documents(
        self,
        patient_id: Optional[Any] = None,
        category: Optional[DocumentCategory] = None,
        uploaded_by: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[MedicalDocumentInDB], int]:
        """Lists medical documents with optional patient, category, or uploader filtering."""
        query = {"is_deleted": {"$ne": True}}
        if patient_id:
            if isinstance(patient_id, (list, tuple, set)):
                query["patient_id"] = {"$in": list(patient_id)}
            else:
                query["patient_id"] = patient_id
        if category:
            if category == DocumentCategory.MRI:
                query["category"] = {"$in": [DocumentCategory.MRI.value, "mri", "MRI", "Brain MRI", "brain mri", "brain_mri"]}
            elif category == DocumentCategory.XRAY:
                query["category"] = {"$in": [DocumentCategory.XRAY.value, "xray", "X-Ray", "Chest X-Ray", "x-ray", "chest_xray"]}
            else:
                query["category"] = category.value
        if uploaded_by:
            query["uploaded_by"] = uploaded_by

        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        items = []
        for doc in docs:
            enriched = await self.enrich_document_provenance(doc)
            items.append(MedicalDocumentInDB(**enriched))
        return items, total

    async def update_metadata(self, document_id: str, req: DocumentMetadataUpdateRequest) -> MedicalDocumentInDB:
        """Updates document title, category, or clinical notes."""
        document = await self.get_document(document_id)
        update_data = req.model_dump(exclude_unset=True)
        if not update_data:
            return document

        update_data["updated_at"] = utc_now()
        await self.collection.update_one(
            {"document_id": document_id},
            {"$set": update_data}
        )
        return await self.get_document(document_id)

    async def soft_delete_document(self, document_id: str, deleted_by: str) -> bool:
        """Soft deletes medical document record."""
        document = await self.get_document(document_id)
        await self.collection.update_one(
            {"document_id": document_id},
            {"$set": {"is_deleted": True, "deleted_at": utc_now(), "deleted_by": deleted_by}}
        )
        return True

    async def restore_document(self, document_id: str) -> MedicalDocumentInDB:
        """Restores soft-deleted document record."""
        res = await self.collection.update_one(
            {"document_id": document_id},
            {"$set": {"is_deleted": False, "deleted_at": None, "deleted_by": None}}
        )
        if res.matched_count == 0:
            raise NotFoundError(f"Deleted document '{document_id}' not found.")
        doc = await self.collection.find_one({"document_id": document_id})
        return MedicalDocumentInDB(**doc)
