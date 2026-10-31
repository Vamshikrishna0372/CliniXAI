"""Medical Records & Secure File Management API Routes for CliniXAI Phase 5."""

import urllib.parse
from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user
from app.models.user import UserInDB, UserRole
from app.models.medical_record import RecordType, RecordStatus
from app.schemas.medical_records import (
    CreateMedicalRecordRequest, UpdateMedicalRecordRequest,
    MedicalRecordResponse, MedicalRecordSummaryResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.medical_record_service import MedicalRecordService
from app.core.exceptions import AppValidationError

router = APIRouter(prefix="/medical-records", tags=["Medical Records"])


@router.post(
    "",
    response_model=APIResponse[MedicalRecordResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create or Upload Medical Record (JSON or Multipart)",
)
async def create_or_upload_medical_record(
    request: Request,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Create a clinical medical record (JSON) or upload a document/image (multipart/form-data)."""
    content_type = request.headers.get("content-type", "")

    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        title = str(form.get("title", ""))
        description = form.get("description")
        clinical_notes = form.get("clinical_notes")
        diagnosis = form.get("diagnosis")
        treatment_plan = form.get("treatment_plan")
        raw_rec_type = form.get("record_type", RecordType.OTHER.value)
        try:
            record_type = RecordType(raw_rec_type)
        except ValueError:
            record_type = RecordType.OTHER
        clinical_date = form.get("clinical_date")
        patient_id = form.get("patient_id")
        appointment_id = form.get("appointment_id")
        consultation_id = form.get("consultation_id")

        metadata = CreateMedicalRecordRequest(
            title=title,
            description=str(description) if description else None,
            clinical_notes=str(clinical_notes) if clinical_notes else None,
            diagnosis=str(diagnosis) if diagnosis else None,
            treatment_plan=str(treatment_plan) if treatment_plan else None,
            record_type=record_type,
            clinical_date=str(clinical_date) if clinical_date else None,
            patient_id=str(patient_id) if patient_id else None,
            appointment_id=str(appointment_id) if appointment_id else None,
            consultation_id=str(consultation_id) if consultation_id else None,
        )

        if file and hasattr(file, "read") and getattr(file, "filename", None):
            content_bytes = await file.read()
            record = await MedicalRecordService.upload_medical_record(
                db,
                original_filename=file.filename,
                content_type=getattr(file, "content_type", None) or "application/octet-stream",
                content_bytes=content_bytes,
                metadata=metadata,
                current_user=current_user,
            )
            return APIResponse(message="Medical record uploaded successfully", data=record.model_dump())
        else:
            record = await MedicalRecordService.create_clinical_record(db, metadata, current_user)
            return APIResponse(message="Medical record created successfully", data=record.model_dump())
    else:
        # JSON body
        payload = await request.json()
        metadata = CreateMedicalRecordRequest(**payload)
        record = await MedicalRecordService.create_clinical_record(db, metadata, current_user)
        return APIResponse(message="Medical record created successfully", data=record.model_dump())


@router.get(
    "",
    response_model=PaginatedResponse[MedicalRecordSummaryResponse],
    summary="List Medical Records (Role-Aware)",
)
async def list_medical_records(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    record_type: Optional[RecordType] = Query(default=None),
    patient_id: Optional[str] = Query(default=None),
    appointment_id: Optional[str] = Query(default=None),
    consultation_id: Optional[str] = Query(default=None),
    status: Optional[RecordStatus] = Query(default=None),
    search: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Role-aware listing of medical records (Patients see own, Doctors see authorized patient records)."""
    docs, total = await MedicalRecordService.list_medical_records(
        db,
        current_user=current_user,
        page=page,
        page_size=page_size,
        record_type=record_type,
        patient_id=patient_id,
        appointment_id=appointment_id,
        consultation_id=consultation_id,
        status=status,
        search=search,
    )
    meta = PaginationMeta.create(page=page, page_size=page_size, total=total)

    results = [
        MedicalRecordSummaryResponse(
            record_id=d["record_id"],
            patient_id=d["patient_id"],
            appointment_id=d.get("appointment_id"),
            consultation_id=d.get("consultation_id"),
            doctor_id=d.get("doctor_id"),
            record_type=d["record_type"],
            title=d["title"],
            clinical_date=d.get("clinical_date"),
            diagnosis=d.get("diagnosis"),
            content_type=d.get("file", {}).get("content_type", "text/plain") if d.get("file") else "text/plain",
            size_bytes=d.get("file", {}).get("size_bytes", 0) if d.get("file") else 0,
            status=d["status"],
            ai_eligible=d.get("ai_eligible", False),
            created_at=d["created_at"],
        )
        for d in docs
    ]

    return PaginatedResponse(data=results, pagination=meta)


@router.get(
    "/{record_id}",
    response_model=APIResponse[MedicalRecordResponse],
    summary="Get Medical Record Metadata",
)
async def get_medical_record_detail(
    record_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Fetch medical record metadata with object-level authorization."""
    record = await MedicalRecordService.get_medical_record_by_id(db, record_id, current_user)
    return APIResponse(data=record)


@router.get(
    "/{record_id}/file",
    summary="Secure File Download / Stream",
    responses={
        200: {
            "content": {"application/pdf": {}, "image/jpeg": {}, "image/png": {}},
            "description": "Secure file stream content",
        }
    },
)
async def get_medical_record_file(
    record_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Securely streams medical file content bytes for authorized users only.

    Applies X-Content-Type-Options: nosniff security header and sanitized Content-Disposition.
    """
    content_bytes, content_type, filename = await MedicalRecordService.get_record_file_bytes(
        db, record_id, current_user
    )

    safe_filename = urllib.parse.quote(filename.replace("\r", "").replace("\n", ""))
    headers = {
        "Content-Disposition": f'inline; filename="{safe_filename}"',
        "X-Content-Type-Options": "nosniff",
    }

    return Response(content=content_bytes, media_type=content_type, headers=headers)


@router.patch(
    "/{record_id}",
    response_model=APIResponse[MedicalRecordResponse],
    summary="Update Record Metadata",
)
async def update_medical_record(
    record_id: str,
    request: UpdateMedicalRecordRequest,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Update title, description, or clinical date of a medical record."""
    updated = await MedicalRecordService.update_medical_record_metadata(
        db, record_id, request, current_user
    )
    return APIResponse(message="Record metadata updated", data=updated)


@router.patch(
    "/{record_id}/archive",
    response_model=APIResponse[MedicalRecordResponse],
    summary="Archive Medical Record",
)
async def archive_medical_record(
    record_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Soft-archives a medical record."""
    archived = await MedicalRecordService.archive_medical_record(db, record_id, current_user)
    return APIResponse(message="Record archived successfully", data=archived)


@router.delete(
    "/{record_id}",
    response_model=APIResponse[MedicalRecordResponse],
    summary="Soft Delete Medical Record",
)
async def delete_medical_record(
    record_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Soft-deletes a medical record (marks is_deleted=True)."""
    deleted = await MedicalRecordService.soft_delete_medical_record(db, record_id, current_user)
    return APIResponse(message="Record deleted successfully", data=deleted)
