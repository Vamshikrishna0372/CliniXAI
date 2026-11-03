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
        uploader_role: Optional[str] = None,
        uploader_name: Optional[str] = None,
    ) -> MedicalDocumentInDB:
        """Validates and stores medical document upload with authoritative metadata persistence."""
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

        # Resolve authoritative uploader role and name directly
        resolved_role = "unknown"
        resolved_name = "Unknown"

        if uploader_role:
            r_val = uploader_role.value if hasattr(uploader_role, "value") else str(uploader_role)
            r_str = str(r_val).strip().lower().replace("userrole.", "")
            if "patient" in r_str:
                resolved_role = "patient"
            elif "doctor" in r_str:
                resolved_role = "doctor"
            elif "admin" in r_str:
                resolved_role = "hospital_admin"
            elif "staff" in r_str:
                resolved_role = "staff"
            else:
                resolved_role = r_str

        if uploader_name:
            resolved_name = str(uploader_name).strip()

        if resolved_role == "unknown" or resolved_name == "Unknown":
            if uploaded_by and uploaded_by not in ("system", "None", ""):
                from app.database.collections import COLLECTION_USERS, COLLECTION_DOCTORS, COLLECTION_PATIENTS, COLLECTION_STAFF
                user_rec = await self.db[COLLECTION_USERS].find_one({"user_id": uploaded_by})
                if user_rec:
                    raw_r = user_rec.get("role")
                    if hasattr(raw_r, "value"):
                        raw_r = raw_r.value
                    r_str = str(raw_r or "").strip().lower().replace("userrole.", "")
                    if "patient" in r_str:
                        resolved_role = "patient"
                    elif "doctor" in r_str:
                        resolved_role = "doctor"
                    elif "admin" in r_str:
                        resolved_role = "hospital_admin"
                    elif "staff" in r_str:
                        resolved_role = "staff"
                    else:
                        resolved_role = r_str or "unknown"
                    resolved_name = user_rec.get("full_name") or user_rec.get("name") or resolved_name

                if resolved_role == "unknown" or resolved_name == "Unknown":
                    doc_rec = await self.db[COLLECTION_DOCTORS].find_one({"$or": [{"user_id": uploaded_by}, {"doctor_id": uploaded_by}]})
                    if doc_rec:
                        resolved_role = "doctor"
                        resolved_name = doc_rec.get("full_name") or doc_rec.get("name") or "Doctor"
                    else:
                        pat_rec = await self.db[COLLECTION_PATIENTS].find_one({"$or": [{"user_id": uploaded_by}, {"patient_id": uploaded_by}]})
                        if pat_rec:
                            resolved_role = "patient"
                            resolved_name = pat_rec.get("full_name") or f"{pat_rec.get('first_name', '')} {pat_rec.get('last_name', '')}".strip() or "Patient"
                        else:
                            staff_rec = await self.db[COLLECTION_STAFF].find_one({"$or": [{"user_id": uploaded_by}, {"staff_id": uploaded_by}]})
                            if staff_rec:
                                resolved_role = "staff"
                                resolved_name = staff_rec.get("full_name") or staff_rec.get("name") or "Staff"

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
        elif category == DocumentCategory.OTHER:
            low_title = (title or "").lower()
            low_fn = (val_result.filename or "").lower()
            if any(k in low_title or k in low_fn for k in ["mri", "brain"]):
                category = DocumentCategory.MRI
                modality = "Brain MRI"
            elif any(k in low_title or k in low_fn for k in ["xray", "x-ray", "chest", "cxr"]):
                category = DocumentCategory.XRAY
                modality = "Chest X-Ray"
            else:
                modality = "Other"
        else:
            modality = category.value if hasattr(category, "value") else str(category)

        document = MedicalDocumentInDB(
            document_id=doc_id,
            patient_id=patient_id,
            uploaded_by=uploaded_by,
            uploaded_by_user_id=uploaded_by,
            uploaded_by_role=resolved_role,
            uploader_role=resolved_role,
            uploader_name=resolved_name,
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

        current_role = d.get("uploaded_by_role") or d.get("uploader_role")
        current_name = d.get("uploader_name")

        needs_resolution = (
            not current_role
            or not current_name
            or str(current_role).lower() in ("unknown", "none", "")
            or "userrole." in str(current_role).lower()
        )

        if needs_resolution:
            from app.database.collections import COLLECTION_USERS, COLLECTION_DOCTORS, COLLECTION_PATIENTS, COLLECTION_STAFF
            u_role = "unknown"
            u_name = current_name or "Unknown"
            if uploaded_by and uploaded_by not in ("system", "None", ""):
                user_rec = await self.db[COLLECTION_USERS].find_one({"user_id": uploaded_by})
                if user_rec:
                    raw_r = user_rec.get("role")
                    if hasattr(raw_r, "value"):
                        raw_r = raw_r.value
                    r_str = str(raw_r or "").strip().lower().replace("userrole.", "")
                    if "patient" in r_str:
                        u_role = "patient"
                    elif "doctor" in r_str:
                        u_role = "doctor"
                    elif "admin" in r_str:
                        u_role = "hospital_admin"
                    elif "staff" in r_str:
                        u_role = "staff"
                    else:
                        u_role = r_str or "unknown"
                    u_name = user_rec.get("full_name") or user_rec.get("name") or u_name

                if u_role == "unknown" or u_name == "Unknown":
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
            d["uploaded_by_role"] = u_role
            d["uploader_name"] = u_name
        else:
            r_str = str(current_role).strip().lower().replace("userrole.", "")
            if "patient" in r_str:
                clean_r = "patient"
            elif "doctor" in r_str:
                clean_r = "doctor"
            elif "admin" in r_str:
                clean_r = "hospital_admin"
            elif "staff" in r_str:
                clean_r = "staff"
            else:
                clean_r = r_str
            d["uploader_role"] = clean_r
            d["uploaded_by_role"] = clean_r

        # Modality
        current_mod = str(d.get("modality") or "").strip()
        cat = str(d.get("category", "")).lower()
        title = str(d.get("title", "")).lower()
        fn = str(d.get("original_file_name", "")).lower()
        if not current_mod or current_mod.lower() == "other":
            if "mri" in cat or "mri" in title or "mri" in fn or "brain" in title or "brain" in cat:
                d["modality"] = "Brain MRI"
            elif "xray" in cat or "x-ray" in cat or "xray" in title or "x-ray" in title or "chest" in cat or "chest" in title:
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
        """Updates document title, category, modality, or clinical notes."""
        document = await self.get_document(document_id)
        update_data = req.model_dump(exclude_unset=True)
        if not update_data:
            return document

        # Synchronize category and modality
        if "category" in update_data and update_data["category"]:
            cat_val = str(update_data["category"].value if hasattr(update_data["category"], "value") else update_data["category"]).lower()
            if "mri" in cat_val:
                update_data["category"] = DocumentCategory.MRI.value
                if "modality" not in update_data or not update_data["modality"]:
                    update_data["modality"] = "Brain MRI"
            elif "xray" in cat_val or "x-ray" in cat_val:
                update_data["category"] = DocumentCategory.XRAY.value
                if "modality" not in update_data or not update_data["modality"]:
                    update_data["modality"] = "Chest X-Ray"
            elif "ct" in cat_val:
                update_data["category"] = DocumentCategory.CT.value
                if "modality" not in update_data or not update_data["modality"]:
                    update_data["modality"] = "CT Scan"
            elif "derm" in cat_val or "skin" in cat_val:
                update_data["category"] = DocumentCategory.DERMOSCOPY.value
                if "modality" not in update_data or not update_data["modality"]:
                    update_data["modality"] = "Skin Dermoscopy"
            elif "fundus" in cat_val or "retin" in cat_val:
                update_data["category"] = DocumentCategory.FUNDUS.value
                if "modality" not in update_data or not update_data["modality"]:
                    update_data["modality"] = "Retinal Fundus"
            elif "other" in cat_val:
                update_data["category"] = DocumentCategory.OTHER.value
                if "modality" not in update_data or not update_data["modality"]:
                    update_data["modality"] = "Other"

        if "modality" in update_data and update_data["modality"]:
            mod_val = str(update_data["modality"]).lower()
            if ("mri" in mod_val or "brain" in mod_val) and "category" not in update_data:
                update_data["category"] = DocumentCategory.MRI.value
            elif ("xray" in mod_val or "x-ray" in mod_val or "chest" in mod_val) and "category" not in update_data:
                update_data["category"] = DocumentCategory.XRAY.value

        update_data["updated_at"] = utc_now()
        await self.collection.update_one(
            {"document_id": document_id},
            {"$set": update_data}
        )
        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(self.db)
        except Exception:
            pass
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
