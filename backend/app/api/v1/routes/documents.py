"""Medical Document API endpoints for safe file upload, metadata, streaming, and soft delete."""

import urllib.parse
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, Query, File, UploadFile, Form, status, Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user
from app.models.user import UserInDB, UserRole
from app.models.document import DocumentCategory
from app.schemas.documents import DocumentResponse, DocumentListResponse, DocumentMetadataUpdateRequest
from app.services.document_service import DocumentService
from app.services.audit_service import log_audit_event
from app.core.exceptions import ForbiddenError, AppValidationError

router = APIRouter(prefix="/documents", tags=["Medical Documents"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Medical Document",
    description="Upload a medical document (MRI, CT, X-Ray, Dermoscopy, Fundus, Lab Report, Prescription, PDF) with validation.",
)
async def upload_document(
    patient_id: str = Form(...),
    title: str = Form(...),
    category: str = Form("Other"),
    file: UploadFile = File(...),
    notes: Optional[str] = Form(None),
    consultation_id: Optional[str] = Form(None),
    appointment_id: Optional[str] = Form(None),
    medical_record_id: Optional[str] = Form(None),
    ai_analysis_id: Optional[str] = Form(None),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> DocumentResponse:
    """Handles medical document upload enforcing canonical patient identity and category mapping."""
    cat_map = {
        "mri": DocumentCategory.MRI,
        "brain mri": DocumentCategory.MRI,
        "brain-mri": DocumentCategory.MRI,
        "brainmri": DocumentCategory.MRI,
        "xray": DocumentCategory.XRAY,
        "x-ray": DocumentCategory.XRAY,
        "chest xray": DocumentCategory.XRAY,
        "chest x-ray": DocumentCategory.XRAY,
        "chestxray": DocumentCategory.XRAY,
        "cxr": DocumentCategory.XRAY,
        "ct": DocumentCategory.CT,
        "ct scan": DocumentCategory.CT,
        "ct_scan": DocumentCategory.CT,
        "dermoscopy": DocumentCategory.DERMOSCOPY,
        "skin": DocumentCategory.DERMOSCOPY,
        "fundus": DocumentCategory.FUNDUS,
        "retinal fundus": DocumentCategory.FUNDUS,
        "lab report": DocumentCategory.LAB_REPORT,
        "lab_report": DocumentCategory.LAB_REPORT,
        "prescription": DocumentCategory.PRESCRIPTION,
        "medical pdf": DocumentCategory.MEDICAL_PDF,
        "medical_pdf": DocumentCategory.MEDICAL_PDF,
        "other": DocumentCategory.OTHER,
    }
    category_enum = cat_map.get(str(category).strip().lower(), DocumentCategory.OTHER)

    canonical_patient_id = patient_id
    if current_user.role == UserRole.PATIENT:
        from app.database.collections import COLLECTION_PATIENTS
        patient_rec = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
        if not patient_rec and getattr(current_user, "email", None):
            patient_rec = await db[COLLECTION_PATIENTS].find_one({"email": current_user.email})
        if not patient_rec:
            raise ForbiddenError("No registered patient profile found for this user account.")
        canonical_pid = patient_rec["patient_id"]
        valid_pids = {current_user.user_id, canonical_pid}
        if patient_id not in valid_pids:
            raise ForbiddenError("Patients can only upload documents for their own profile.")
        canonical_patient_id = canonical_pid
    elif current_user.role == UserRole.DOCTOR:
        from app.database.collections import COLLECTION_DOCTORS, COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS, COLLECTION_PATIENTS
        doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
        doc_id = doctor["doctor_id"] if doctor else None
        
        # Resolve canonical patient id if USR- was passed
        pat_rec = await db[COLLECTION_PATIENTS].find_one({"$or": [{"patient_id": patient_id}, {"user_id": patient_id}]})
        if pat_rec and pat_rec.get("patient_id"):
            canonical_patient_id = pat_rec["patient_id"]
            
        check_pids = [canonical_patient_id]
        if pat_rec:
            if pat_rec.get("patient_id"): check_pids.append(pat_rec["patient_id"])
            if pat_rec.get("user_id"): check_pids.append(pat_rec["user_id"])
        clean_pids = list(set(check_pids))
        apt_q = {"patient_id": clean_pids[0], "doctor_id": doc_id} if len(clean_pids) == 1 else {"patient_id": {"$in": clean_pids}, "doctor_id": doc_id}
        has_apt = await db[COLLECTION_APPOINTMENTS].find_one(apt_q)
        has_consult = await db[COLLECTION_CONSULTATIONS].find_one(apt_q)
        if not has_apt and not has_consult and not consultation_id:
            raise ForbiddenError("You are not authorized to upload documents for this patient without an established clinical relationship.")
    else:
        # Staff / Admin upload
        from app.database.collections import COLLECTION_PATIENTS
        pat_rec = await db[COLLECTION_PATIENTS].find_one({"$or": [{"patient_id": patient_id}, {"user_id": patient_id}]})
        if pat_rec and pat_rec.get("patient_id"):
            canonical_patient_id = pat_rec["patient_id"]

    content_bytes = await file.read()
    service = DocumentService(db)
    document = await service.upload_document(
        patient_id=canonical_patient_id,
        uploaded_by=current_user.user_id,
        title=title,
        category=category_enum,
        original_filename=file.filename or "document",
        content_type=file.content_type or "application/octet-stream",
        content_bytes=content_bytes,
        notes=notes,
        consultation_id=consultation_id,
        appointment_id=appointment_id,
        medical_record_id=medical_record_id,
        ai_analysis_id=ai_analysis_id,
    )

    await log_audit_event(
        db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="DOCUMENT_UPLOAD",
        resource="documents",
        resource_id=document.document_id,
    )

    return DocumentResponse(**document.model_dump())


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Medical Documents",
)
async def list_documents(
    patient_id: Optional[str] = None,
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> DocumentListResponse:
    """Lists documents enforcing patient isolation."""
    category_enum = None
    if category:
        cat_map = {
            "xray": DocumentCategory.XRAY,
            "x-ray": DocumentCategory.XRAY,
            "chest xray": DocumentCategory.XRAY,
            "chest x-ray": DocumentCategory.XRAY,
            "chestxray": DocumentCategory.XRAY,
            "cxr": DocumentCategory.XRAY,
            "mri": DocumentCategory.MRI,
            "brain mri": DocumentCategory.MRI,
            "brain-mri": DocumentCategory.MRI,
            "brainmri": DocumentCategory.MRI,
            "ct": DocumentCategory.CT,
            "dermoscopy": DocumentCategory.DERMOSCOPY,
            "fundus": DocumentCategory.FUNDUS,
            "lab report": DocumentCategory.LAB_REPORT,
            "lab_report": DocumentCategory.LAB_REPORT,
            "prescription": DocumentCategory.PRESCRIPTION,
            "medical pdf": DocumentCategory.MEDICAL_PDF,
            "medical_pdf": DocumentCategory.MEDICAL_PDF,
            "other": DocumentCategory.OTHER,
        }
        category_enum = cat_map.get(category.lower().strip())
        if not category_enum:
            try:
                category_enum = DocumentCategory(category)
            except ValueError:
                category_enum = None

    query_patient_ids: Any = patient_id
    if current_user.role == UserRole.PATIENT:
        from app.database.collections import COLLECTION_PATIENTS
        patient_rec = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
        ids = [current_user.user_id]
        if patient_rec and patient_rec.get("patient_id"):
            ids.append(patient_rec["patient_id"])
        query_patient_ids = ids
    elif current_user.role == UserRole.DOCTOR:
        from app.services.appointment_service import AppointmentService
        from app.database.collections import COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS, COLLECTION_PATIENTS
        doctor = await AppointmentService.get_doctor_for_user(db, current_user)
        doc_id = doctor.get("doctor_id") if doctor else None
        if not doc_id:
            raise ForbiddenError("You are not authorized to view documents without an established doctor profile.")
        if patient_id:
            pat_rec = await db[COLLECTION_PATIENTS].find_one({"$or": [{"patient_id": patient_id}, {"user_id": patient_id}]})
            check_pids = [patient_id]
            if pat_rec:
                if pat_rec.get("patient_id"): check_pids.append(pat_rec["patient_id"])
                if pat_rec.get("user_id"): check_pids.append(pat_rec["user_id"])
            clean_pids = list(set(check_pids))
            apt_q = {"patient_id": clean_pids[0], "doctor_id": doc_id} if len(clean_pids) == 1 else {"patient_id": {"$in": clean_pids}, "doctor_id": doc_id}
            has_apt = await db[COLLECTION_APPOINTMENTS].find_one(apt_q)
            has_consult = await db[COLLECTION_CONSULTATIONS].find_one(apt_q)
            if not has_apt and not has_consult:
                raise ForbiddenError("You are not authorized to view documents for this patient.")
            query_patient_ids = clean_pids[0] if len(clean_pids) == 1 else {"$in": clean_pids}
        else:
            apt_pids = await db[COLLECTION_APPOINTMENTS].distinct("patient_id", {"doctor_id": doc_id})
            cns_pids = await db[COLLECTION_CONSULTATIONS].distinct("patient_id", {"doctor_id": doc_id})
            authorized_pids = list(set(apt_pids + cns_pids))
            query_patient_ids = {"$in": authorized_pids} if authorized_pids else "NONE"

    service = DocumentService(db)
    items, total = await service.list_documents(
        patient_id=query_patient_ids,
        category=category_enum,
        skip=skip,
        limit=limit,
    )

    resp_items = [DocumentResponse(**item.model_dump()) for item in items]
    return DocumentListResponse(total=total, items=resp_items)


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Medical Document Metadata",
)
async def get_document(
    document_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> DocumentResponse:
    """Retrieves document metadata."""
    service = DocumentService(db)
    document = await service.get_document(document_id)

    if current_user.role == UserRole.PATIENT:
        from app.database.collections import COLLECTION_PATIENTS
        patient_rec = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
        valid_ids = {current_user.user_id}
        if patient_rec:
            valid_ids.add(patient_rec.get("patient_id"))
        if document.patient_id not in valid_ids and document.uploaded_by != current_user.user_id:
            raise ForbiddenError("You are not authorized to view this medical document.")
    elif current_user.role == UserRole.DOCTOR:
        from app.services.appointment_service import AppointmentService
        from app.database.collections import COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS
        doctor = await AppointmentService.get_doctor_for_user(db, current_user)
        doc_id = doctor.get("doctor_id") if doctor else None
        if not doc_id:
            raise ForbiddenError("You are not authorized to access documents without an active doctor profile.")
        if document.uploaded_by != current_user.user_id:
            from app.database.collections import COLLECTION_PATIENTS
            pat_rec = await db[COLLECTION_PATIENTS].find_one({"$or": [{"patient_id": document.patient_id}, {"user_id": document.patient_id}]})
            check_pids = [document.patient_id]
            if pat_rec:
                if pat_rec.get("patient_id"): check_pids.append(pat_rec["patient_id"])
                if pat_rec.get("user_id"): check_pids.append(pat_rec["user_id"])
            clean_pids = list(set(check_pids))
            apt_q = {"patient_id": clean_pids[0], "doctor_id": doc_id} if len(clean_pids) == 1 else {"patient_id": {"$in": clean_pids}, "doctor_id": doc_id}
            has_apt = await db[COLLECTION_APPOINTMENTS].find_one(apt_q)
            has_consult = await db[COLLECTION_CONSULTATIONS].find_one(apt_q)
            if not has_apt and not has_consult:
                raise ForbiddenError("You are not authorized to access documents for this patient.")

    return DocumentResponse(**document.model_dump())


@router.get(
    "/{document_id}/download",
    status_code=status.HTTP_200_OK,
    summary="Download/Stream Medical Document File",
)
async def download_document(
    document_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
):
    """Streams document file content."""
    service = DocumentService(db)
    content_bytes, document = await service.read_document_bytes(document_id)

    if current_user.role == UserRole.PATIENT:
        from app.database.collections import COLLECTION_PATIENTS
        patient_rec = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
        valid_ids = {current_user.user_id}
        if patient_rec:
            valid_ids.add(patient_rec.get("patient_id"))
        if document.patient_id not in valid_ids and document.uploaded_by != current_user.user_id:
            raise ForbiddenError("You are not authorized to download this medical document.")
    elif current_user.role == UserRole.DOCTOR:
        from app.services.appointment_service import AppointmentService
        from app.database.collections import COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS, COLLECTION_PATIENTS
        doctor = await AppointmentService.get_doctor_for_user(db, current_user)
        doc_id = doctor.get("doctor_id") if doctor else None
        if not doc_id:
            raise ForbiddenError("You are not authorized to download documents without an active doctor profile.")
        if document.uploaded_by != current_user.user_id:
            pat_rec = await db[COLLECTION_PATIENTS].find_one({"$or": [{"patient_id": document.patient_id}, {"user_id": document.patient_id}]})
            check_pids = [document.patient_id]
            if pat_rec:
                if pat_rec.get("patient_id"): check_pids.append(pat_rec["patient_id"])
                if pat_rec.get("user_id"): check_pids.append(pat_rec["user_id"])
            clean_pids = list(set(check_pids))
            apt_q = {"patient_id": clean_pids[0], "doctor_id": doc_id} if len(clean_pids) == 1 else {"patient_id": {"$in": clean_pids}, "doctor_id": doc_id}
            has_apt = await db[COLLECTION_APPOINTMENTS].find_one(apt_q)
            has_consult = await db[COLLECTION_CONSULTATIONS].find_one(apt_q)
            if not has_apt and not has_consult:
                raise ForbiddenError("You are not authorized to download documents for this patient.")

    await log_audit_event(
        db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="DOCUMENT_DOWNLOAD",
        resource="documents",
        resource_id=document_id,
    )

    safe_filename = urllib.parse.quote(document.original_file_name.replace("\r", "").replace("\n", ""))
    return Response(
        content=content_bytes,
        media_type=document.mime_type,
        headers={
            "Content-Disposition": f'inline; filename="{safe_filename}"',
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Document Metadata",
)
async def update_document_metadata(
    document_id: str,
    req: DocumentMetadataUpdateRequest,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> DocumentResponse:
    """Updates document metadata."""
    service = DocumentService(db)
    updated = await service.update_metadata(document_id, req)
    return DocumentResponse(**updated.model_dump())


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Soft Delete Document",
)
async def delete_document(
    document_id: str,
    db: AsyncIOMotorDatabase = Depends(get_database),
    current_user: UserInDB = Depends(get_current_user),
) -> dict:
    """Soft deletes document record."""
    service = DocumentService(db)
    await service.soft_delete_document(document_id, deleted_by=current_user.user_id)

    await log_audit_event(
        db,
        actor_id=current_user.user_id,
        role=current_user.role.value,
        action="DOCUMENT_DELETE",
        resource="documents",
        resource_id=document_id,
    )

    return {"message": f"Document '{document_id}' soft-deleted successfully."}
