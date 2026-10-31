"""Medical Record & Secure File Management Business Logic Service for Phase 5."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import (
    ResourceNotFoundError, ResourceConflictError, ForbiddenError, AppValidationError, CliniXAIException
)
from app.database.collections import (
    COLLECTION_MEDICAL_RECORDS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS
)
from app.models.medical_record import (
    MedicalRecordInDB, RecordType, RecordSource, RecordStatus, FileMetadata
)
from app.models.user import UserInDB, UserRole
from app.schemas.medical_records import (
    CreateMedicalRecordRequest, UpdateMedicalRecordRequest
)
from app.services.storage_service import storage_service
from app.utils.file_validation import (
    validate_file_content, generate_secure_storage_key
)
from app.utils.id_generator import generate_medical_record_id
from app.utils.datetime import utc_now


class MedicalRecordService:
    """Core medical record management and secure file handling service."""

    @staticmethod
    async def _find_by_record_id(db: AsyncIOMotorDatabase, record_id: str) -> Dict[str, Any]:
        doc = await db[COLLECTION_MEDICAL_RECORDS].find_one({"record_id": record_id})
        if not doc:
            raise ResourceNotFoundError("Medical Record", record_id)
        return doc

    @staticmethod
    async def _resolve_doctor(db: AsyncIOMotorDatabase, doctor_user: UserInDB) -> Optional[Dict[str, Any]]:
        doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": doctor_user.user_id})
        if not doctor and getattr(doctor_user, "email", None):
            doctor = await db[COLLECTION_DOCTORS].find_one({"email": doctor_user.email})
        if not doctor:
            doctor = await db[COLLECTION_DOCTORS].find_one({"doctor_id": doctor_user.user_id})
        return doctor

    @staticmethod
    async def create_clinical_record(
        db: AsyncIOMotorDatabase,
        metadata: CreateMedicalRecordRequest,
        current_user: UserInDB,
    ) -> MedicalRecordInDB:
        """Creates a pure clinical medical record without requiring an uploaded file."""
        target_patient_id: str
        target_doctor_id: Optional[str] = None
        source: RecordSource

        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient:
                raise ResourceNotFoundError("Patient profile for current user")
            target_patient_id = patient["patient_id"]
            source = RecordSource.PATIENT
            if metadata.patient_id and metadata.patient_id != target_patient_id:
                raise ForbiddenError("Patients cannot create medical records for another patient.")
            if metadata.record_type in (RecordType.DIAGNOSIS, RecordType.CONSULTATION):
                raise ForbiddenError("Patients cannot create authoritative clinical diagnosis records.")
        elif current_user.role == UserRole.DOCTOR:
            if not metadata.patient_id:
                raise AppValidationError("Doctor record creation requires specifying 'patient_id'.")
            target_patient_id = metadata.patient_id
            doctor = await MedicalRecordService._resolve_doctor(db, current_user)
            if not doctor:
                raise ForbiddenError("Authenticated user does not have an active Doctor profile.")
            target_doctor_id = doctor["doctor_id"]
            source = RecordSource.DOCTOR
        elif current_user.role == UserRole.HOSPITAL_STAFF:
            if not metadata.patient_id:
                raise AppValidationError("Staff record creation requires specifying 'patient_id'.")
            target_patient_id = metadata.patient_id
            source = RecordSource.HOSPITAL_STAFF
        else: # Admin
            if not metadata.patient_id:
                raise AppValidationError("Admin record creation requires specifying 'patient_id'.")
            target_patient_id = metadata.patient_id
            source = RecordSource.HOSPITAL

        # Verify patient exists
        patient_exists = await db[COLLECTION_PATIENTS].find_one({"patient_id": target_patient_id})
        if not patient_exists:
            raise ResourceNotFoundError("Patient", target_patient_id)

        if current_user.role == UserRole.DOCTOR:
            # Verify clinical relationship with target patient
            has_apt = await db[COLLECTION_APPOINTMENTS].find_one({
                "patient_id": target_patient_id,
                "doctor_id": target_doctor_id
            })
            has_consult = await db[COLLECTION_CONSULTATIONS].find_one({
                "patient_id": target_patient_id,
                "doctor_id": target_doctor_id
            })
            if not has_apt and not has_consult and not metadata.appointment_id and not metadata.consultation_id:
                raise ForbiddenError("You are not authorized to create medical records for this patient without an established clinical relationship.")

        # Relationship validations
        department_id: Optional[str] = metadata.department_id
        apt_doc = None
        if metadata.appointment_id:
            apt_doc = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": metadata.appointment_id})
            if not apt_doc:
                raise ResourceNotFoundError("Appointment", metadata.appointment_id)
            if apt_doc["patient_id"] != target_patient_id:
                raise AppValidationError("Specified appointment does not belong to the target patient.")
            if current_user.role == UserRole.DOCTOR and target_doctor_id and apt_doc["doctor_id"] != target_doctor_id:
                raise ForbiddenError("Specified appointment does not belong to this doctor.")
            department_id = apt_doc.get("department_id") or department_id
            if not target_doctor_id and apt_doc.get("doctor_id"):
                target_doctor_id = apt_doc["doctor_id"]

        consult_doc = None
        if metadata.consultation_id:
            consult_doc = await db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": metadata.consultation_id})
            if not consult_doc:
                raise ResourceNotFoundError("Consultation", metadata.consultation_id)
            if consult_doc["patient_id"] != target_patient_id:
                raise AppValidationError("Specified consultation does not belong to the target patient.")
            if current_user.role == UserRole.DOCTOR and target_doctor_id and consult_doc["doctor_id"] != target_doctor_id:
                raise ForbiddenError("Specified consultation does not belong to this doctor.")
            department_id = consult_doc.get("department_id") or department_id
            if not target_doctor_id and consult_doc.get("doctor_id"):
                target_doctor_id = consult_doc["doctor_id"]

            # Prevent duplicate records for the same consultation
            existing_cns = await db[COLLECTION_MEDICAL_RECORDS].find_one({
                "consultation_id": metadata.consultation_id,
                "is_deleted": {"$ne": True}
            })
            if existing_cns:
                raise ResourceConflictError("A medical record is already associated with this consultation.")

        # Cross-validate appointment and consultation relationship if both are provided
        if metadata.appointment_id and metadata.consultation_id and apt_doc and consult_doc:
            if consult_doc.get("appointment_id") and consult_doc["appointment_id"] != metadata.appointment_id:
                raise AppValidationError("Specified appointment does not match the consultation's appointment.")
            if apt_doc.get("doctor_id") and consult_doc.get("doctor_id") and apt_doc["doctor_id"] != consult_doc["doctor_id"]:
                raise AppValidationError("Specified appointment doctor does not match consultation doctor.")
            if apt_doc.get("patient_id") and consult_doc.get("patient_id") and apt_doc["patient_id"] != consult_doc["patient_id"]:
                raise AppValidationError("Specified appointment patient does not match consultation patient.")

        record_id = generate_medical_record_id()
        now = utc_now()

        record_doc = MedicalRecordInDB(
            record_id=record_id,
            patient_id=target_patient_id,
            appointment_id=metadata.appointment_id,
            consultation_id=metadata.consultation_id,
            doctor_id=target_doctor_id,
            department_id=department_id,
            record_type=metadata.record_type,
            title=metadata.title,
            description=metadata.description,
            clinical_date=metadata.clinical_date or now.strftime("%Y-%m-%d"),
            diagnosis=metadata.diagnosis,
            clinical_notes=metadata.clinical_notes,
            treatment_plan=metadata.treatment_plan,
            symptoms=metadata.symptoms,
            file=None,
            uploaded_by=current_user.user_id,
            source=source,
            status=RecordStatus.ACTIVE,
            ai_eligible=False,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )

        await db[COLLECTION_MEDICAL_RECORDS].insert_one(record_doc.to_mongo_dict())
        logger.info(f"Created clinical medical record {record_id} for Patient {target_patient_id} by {current_user.user_id}")

        # Audit Log & Notification
        try:
            from app.services.audit_service import log_audit_event
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType

            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value,
                action="create_medical_record",
                resource="medical_record",
                resource_id=record_id,
                metadata={"patient_id": target_patient_id, "title": metadata.title, "record_type": metadata.record_type.value},
            )

            patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": target_patient_id})
            if patient and patient.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=patient["user_id"],
                    notification_type=NotificationType.CLINICAL,
                    title="New Medical Record Added",
                    body=f"Medical record '{metadata.title}' has been added to your profile.",
                    reference_id=record_id,
                    reference_type="medical_record",
                )
        except Exception as exc_audit:
            logger.warning(f"Failed to dispatch audit/notification for medical record creation {record_id}: {exc_audit}")

        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        return record_doc

    @staticmethod
    async def upload_medical_record(
        db: AsyncIOMotorDatabase,
        original_filename: str,
        content_type: str,
        content_bytes: bytes,
        metadata: CreateMedicalRecordRequest,
        current_user: UserInDB,
    ) -> MedicalRecordInDB:
        """Securely validates file, determines ownership, stores file bytes, and creates medical record entry."""
        # 1. File content validation (size, MIME type, extension, magic bytes, SHA-256 checksum)
        validation = validate_file_content(original_filename, content_type, content_bytes)

        # 2. Determine target patient_id, doctor_id, and record source based on caller role
        target_patient_id: str
        target_doctor_id: Optional[str] = None
        source: RecordSource

        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient:
                raise ResourceNotFoundError("Patient profile for current user")
            target_patient_id = patient["patient_id"]
            source = RecordSource.PATIENT
            if metadata.patient_id and metadata.patient_id != target_patient_id:
                raise ForbiddenError("Patients cannot upload medical records for another patient.")
            if metadata.record_type in (RecordType.DIAGNOSIS, RecordType.CONSULTATION):
                raise ForbiddenError("Patients cannot create authoritative clinical diagnosis records.")
        elif current_user.role == UserRole.DOCTOR:
            if not metadata.patient_id:
                raise AppValidationError("Doctor upload requires specifying 'patient_id'.")
            target_patient_id = metadata.patient_id
            doctor = await MedicalRecordService._resolve_doctor(db, current_user)
            if not doctor:
                raise ForbiddenError("Authenticated user does not have an active Doctor profile.")
            target_doctor_id = doctor["doctor_id"]
            source = RecordSource.DOCTOR

            # Verify doctor has care relationship with target patient
            has_apt = await db[COLLECTION_APPOINTMENTS].find_one({
                "patient_id": target_patient_id,
                "doctor_id": target_doctor_id
            })
            has_consult = await db[COLLECTION_CONSULTATIONS].find_one({
                "patient_id": target_patient_id,
                "doctor_id": target_doctor_id
            })
            if not has_apt and not has_consult and not metadata.appointment_id and not metadata.consultation_id:
                raise ForbiddenError("You are not authorized to upload medical records for this patient without an established clinical relationship.")
        elif current_user.role == UserRole.HOSPITAL_STAFF:
            if not metadata.patient_id:
                raise AppValidationError("Staff upload requires specifying 'patient_id'.")
            target_patient_id = metadata.patient_id
            source = RecordSource.HOSPITAL_STAFF
        else: # Admin
            if not metadata.patient_id:
                raise AppValidationError("Admin upload requires specifying 'patient_id'.")
            target_patient_id = metadata.patient_id
            source = RecordSource.HOSPITAL

        # Verify patient exists
        patient_exists = await db[COLLECTION_PATIENTS].find_one({"patient_id": target_patient_id})
        if not patient_exists:
            raise ResourceNotFoundError("Patient", target_patient_id)

        # 3. Relationship validations (Appointment & Consultation)
        department_id: Optional[str] = metadata.department_id
        apt_doc = None
        if metadata.appointment_id:
            apt_doc = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": metadata.appointment_id})
            if not apt_doc:
                raise ResourceNotFoundError("Appointment", metadata.appointment_id)
            if apt_doc["patient_id"] != target_patient_id:
                raise AppValidationError("Specified appointment does not belong to the target patient.")
            if current_user.role == UserRole.DOCTOR and target_doctor_id and apt_doc["doctor_id"] != target_doctor_id:
                raise ForbiddenError("Specified appointment does not belong to this doctor.")
            department_id = apt_doc.get("department_id") or department_id
            if not target_doctor_id and apt_doc.get("doctor_id"):
                target_doctor_id = apt_doc["doctor_id"]

        consult_doc = None
        if metadata.consultation_id:
            consult_doc = await db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": metadata.consultation_id})
            if not consult_doc:
                raise ResourceNotFoundError("Consultation", metadata.consultation_id)
            if consult_doc["patient_id"] != target_patient_id:
                raise AppValidationError("Specified consultation does not belong to the target patient.")
            if current_user.role == UserRole.DOCTOR and target_doctor_id and consult_doc["doctor_id"] != target_doctor_id:
                raise ForbiddenError("Specified consultation does not belong to this doctor.")
            department_id = consult_doc.get("department_id") or department_id
            if not target_doctor_id and consult_doc.get("doctor_id"):
                target_doctor_id = consult_doc["doctor_id"]

            # Prevent duplicate records for the same consultation
            existing_cns = await db[COLLECTION_MEDICAL_RECORDS].find_one({
                "consultation_id": metadata.consultation_id,
                "is_deleted": {"$ne": True}
            })
            if existing_cns:
                raise ResourceConflictError("A medical record is already associated with this consultation.")

        # Cross-validate appointment and consultation relationship if both are provided
        if metadata.appointment_id and metadata.consultation_id and apt_doc and consult_doc:
            if consult_doc.get("appointment_id") and consult_doc["appointment_id"] != metadata.appointment_id:
                raise AppValidationError("Specified appointment does not match the consultation's appointment.")
            if apt_doc.get("doctor_id") and consult_doc.get("doctor_id") and apt_doc["doctor_id"] != consult_doc["doctor_id"]:
                raise AppValidationError("Specified appointment doctor does not match consultation doctor.")
            if apt_doc.get("patient_id") and consult_doc.get("patient_id") and apt_doc["patient_id"] != consult_doc["patient_id"]:
                raise AppValidationError("Specified appointment patient does not match consultation patient.")

        # 4. Generate un-guessable storage key and save file
        storage_key, ext = generate_secure_storage_key(original_filename)
        saved_key = await storage_service.save_file(content_bytes, storage_key, subfolder="medical-records")

        # 5. Determine AI eligibility
        ai_eligible = (metadata.record_type == RecordType.MEDICAL_IMAGE and validation.is_image)

        file_meta = FileMetadata(
            storage_key=saved_key,
            original_filename=validation.filename,
            content_type=validation.content_type,
            size_bytes=validation.size_bytes,
            checksum=validation.checksum,
            extension=validation.extension,
            storage_provider=settings.STORAGE_PROVIDER,
            uploaded_at=utc_now(),
        )

        record_id = generate_medical_record_id()
        now = utc_now()

        record_doc = MedicalRecordInDB(
            record_id=record_id,
            patient_id=target_patient_id,
            appointment_id=metadata.appointment_id,
            consultation_id=metadata.consultation_id,
            doctor_id=target_doctor_id,
            department_id=department_id,
            record_type=metadata.record_type,
            title=metadata.title,
            description=metadata.description,
            clinical_date=metadata.clinical_date or now.strftime("%Y-%m-%d"),
            diagnosis=metadata.diagnosis,
            clinical_notes=metadata.clinical_notes,
            treatment_plan=metadata.treatment_plan,
            symptoms=metadata.symptoms,
            file=file_meta,
            uploaded_by=current_user.user_id,
            source=source,
            status=RecordStatus.ACTIVE,
            ai_eligible=ai_eligible,
            is_deleted=False,
            created_at=now,
            updated_at=now,
        )

        # 6. Insert MongoDB document with error cleanup safeguard
        try:
            await db[COLLECTION_MEDICAL_RECORDS].insert_one(record_doc.to_mongo_dict())
            logger.info(f"Created medical record {record_id} for Patient {target_patient_id}. Storage key: {saved_key}")

            # Audit Log & Notification
            try:
                from app.services.audit_service import log_audit_event
                from app.services.notification_service import NotificationService
                from app.models.notification import NotificationType

                await log_audit_event(
                    db=db,
                    actor_id=current_user.user_id,
                    role=current_user.role.value,
                    action="upload_medical_record",
                    resource="medical_record",
                    resource_id=record_id,
                    metadata={"patient_id": target_patient_id, "title": metadata.title, "record_type": metadata.record_type.value},
                )

                patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": target_patient_id})
                if patient and patient.get("user_id"):
                    await NotificationService.dispatch(
                        db=db,
                        recipient_user_id=patient["user_id"],
                        notification_type=NotificationType.CLINICAL,
                        title="New Medical Record Uploaded",
                        body=f"Medical record '{metadata.title}' has been added to your profile.",
                        reference_id=record_id,
                        reference_type="medical_record",
                    )
            except Exception as exc_audit:
                logger.warning(f"Failed to dispatch audit/notification for medical record upload {record_id}: {exc_audit}")

            try:
                from app.database.mongodb import save_in_memory_snapshot
                await save_in_memory_snapshot(db)
            except Exception:
                pass

            return record_doc
        except Exception as exc:
            logger.error(f"Failed to insert medical record document {record_id}: {exc}. Cleaning up saved file...")
            await storage_service.delete_file(saved_key, subfolder="medical-records")
            if isinstance(exc, CliniXAIException):
                raise exc
            raise CliniXAIException(f"Failed to persist medical record: {exc}", status_code=500)

    @staticmethod
    async def get_medical_record_by_id(
        db: AsyncIOMotorDatabase, record_id: str, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Fetch medical record metadata with object-level authorization."""
        record = await MedicalRecordService._find_by_record_id(db, record_id)

        # Soft-deleted check (Admin can view deleted, others get 404)
        if record.get("is_deleted") and current_user.role != UserRole.HOSPITAL_ADMIN:
            raise ResourceNotFoundError("Medical Record", record_id)

        # Authorization check
        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient or patient["patient_id"] != record["patient_id"]:
                raise ForbiddenError("You are not authorized to view this medical record.")
        elif current_user.role == UserRole.DOCTOR:
            doctor = await MedicalRecordService._resolve_doctor(db, current_user)
            doc_id = doctor["doctor_id"] if doctor else None
            if not doc_id:
                raise ForbiddenError("You are not authorized to view medical records without an active doctor profile.")
            if record.get("doctor_id") != doc_id and record.get("uploaded_by") != current_user.user_id:
                # Check care relationship via appointment or consultation
                has_relationship = await db[COLLECTION_APPOINTMENTS].find_one({
                    "patient_id": record["patient_id"],
                    "doctor_id": doc_id
                })
                if not has_relationship:
                    has_consult = await db[COLLECTION_CONSULTATIONS].find_one({
                        "patient_id": record["patient_id"],
                        "doctor_id": doc_id
                    })
                    if not has_consult:
                        raise ForbiddenError("You are not authorized to view medical records for this patient.")

        return record

    @staticmethod
    async def get_record_file_bytes(
        db: AsyncIOMotorDatabase, record_id: str, current_user: UserInDB
    ) -> Tuple[bytes, str, str]:
        """Authorized file download/view helper returning (content_bytes, content_type, original_filename)."""
        record = await MedicalRecordService.get_medical_record_by_id(db, record_id, current_user)
        file_meta = record.get("file")
        if not file_meta:
            raise ResourceNotFoundError("Attached file for Medical Record", record_id)
        storage_key = file_meta["storage_key"]

        content_bytes = await storage_service.read_file(storage_key, subfolder="medical-records")
        return content_bytes, file_meta["content_type"], file_meta["original_filename"]

    @staticmethod
    async def list_medical_records(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        page: int = 1,
        page_size: int = 20,
        record_type: Optional[RecordType] = None,
        patient_id: Optional[str] = None,
        appointment_id: Optional[str] = None,
        consultation_id: Optional[str] = None,
        status: Optional[RecordStatus] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Role-aware medical record list retrieval."""
        query: Dict[str, Any] = {"is_deleted": {"$ne": True}}

        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient:
                return [], 0
            query["patient_id"] = patient["patient_id"]
        elif current_user.role == UserRole.DOCTOR:
            doctor = await MedicalRecordService._resolve_doctor(db, current_user)
            doc_id = doctor["doctor_id"] if doctor else None
            if not doc_id:
                raise ForbiddenError("You are not authorized to view medical records without an active doctor profile.")
            if patient_id:
                # Verify doctor has clinical relationship with this patient
                has_apt = await db[COLLECTION_APPOINTMENTS].find_one({
                    "patient_id": patient_id,
                    "doctor_id": doc_id
                })
                has_consult = await db[COLLECTION_CONSULTATIONS].find_one({
                    "patient_id": patient_id,
                    "doctor_id": doc_id
                })
                if not has_apt and not has_consult:
                    raise ForbiddenError("You are not authorized to view medical records for this patient.")
                query["patient_id"] = patient_id
            else:
                    query["$or"] = [
                        {"doctor_id": doc_id},
                        {"uploaded_by": current_user.user_id},
                    ]
        else: # Admin / Staff
            if patient_id:
                query["patient_id"] = patient_id

        if record_type:
            query["record_type"] = record_type.value
        if appointment_id:
            query["appointment_id"] = appointment_id
        if consultation_id:
            query["consultation_id"] = consultation_id
        if status:
            query["status"] = status.value

        if search:
            search_regex = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"title": search_regex},
                {"description": search_regex},
                {"diagnosis": search_regex},
                {"record_id": search_regex},
            ]

        skip = (page - 1) * page_size
        total = await db[COLLECTION_MEDICAL_RECORDS].count_documents(query)
        cursor = db[COLLECTION_MEDICAL_RECORDS].find(query).sort([("clinical_date", -1), ("created_at", -1)]).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return docs, total

    @staticmethod
    async def update_medical_record_metadata(
        db: AsyncIOMotorDatabase,
        record_id: str,
        request: UpdateMedicalRecordRequest,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Update allowed record metadata and clinical notes with strict role authorization."""
        record = await MedicalRecordService.get_medical_record_by_id(db, record_id, current_user)

        # Check privileged clinical fields
        is_clinical_update = (
            request.diagnosis is not None or
            request.clinical_notes is not None or
            request.treatment_plan is not None or
            request.symptoms is not None
        )

        if current_user.role == UserRole.PATIENT:
            if is_clinical_update:
                raise ForbiddenError("Patients are not authorized to modify clinical diagnosis, notes, or treatment plan.")
            if record["uploaded_by"] != current_user.user_id:
                raise ForbiddenError("You are not authorized to update this medical record.")
        elif current_user.role == UserRole.DOCTOR:
            doctor = await MedicalRecordService._resolve_doctor(db, current_user)
            doc_id = doctor["doctor_id"] if doctor else None
            # Doctor can update if they are the doctor on record, uploaded it, or have care relationship
            if doc_id and record.get("doctor_id") != doc_id and record.get("uploaded_by") != current_user.user_id:
                has_apt = await db[COLLECTION_APPOINTMENTS].find_one({"patient_id": record["patient_id"], "doctor_id": doc_id})
                has_consult = await db[COLLECTION_CONSULTATIONS].find_one({"patient_id": record["patient_id"], "doctor_id": doc_id})
                if not has_apt and not has_consult:
                    raise ForbiddenError("You are not authorized to update records for this patient.")

        updates: Dict[str, Any] = {}
        if request.title is not None:
            updates["title"] = request.title
        if request.description is not None:
            updates["description"] = request.description
        if request.clinical_date is not None:
            updates["clinical_date"] = request.clinical_date
        if request.diagnosis is not None:
            updates["diagnosis"] = request.diagnosis
        if request.clinical_notes is not None:
            updates["clinical_notes"] = request.clinical_notes
        if request.treatment_plan is not None:
            updates["treatment_plan"] = request.treatment_plan
        if request.symptoms is not None:
            updates["symptoms"] = request.symptoms

        if updates:
            updates["updated_at"] = utc_now()
            await db[COLLECTION_MEDICAL_RECORDS].update_one(
                {"record_id": record_id},
                {"$set": updates}
            )
            logger.info(f"Updated metadata for medical record {record_id}")

            try:
                from app.services.audit_service import log_audit_event
                await log_audit_event(
                    db=db,
                    actor_id=current_user.user_id,
                    role=current_user.role.value,
                    action="update_medical_record",
                    resource="medical_record",
                    resource_id=record_id,
                    metadata={"fields_updated": list(updates.keys())},
                )
            except Exception as exc:
                logger.warning(f"Audit log error: {exc}")

        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        return await MedicalRecordService._find_by_record_id(db, record_id)

    @staticmethod
    async def archive_medical_record(
        db: AsyncIOMotorDatabase, record_id: str, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Soft-archives a medical record."""
        record = await MedicalRecordService.get_medical_record_by_id(db, record_id, current_user)

        if current_user.role not in (UserRole.HOSPITAL_ADMIN, UserRole.DOCTOR) and record["uploaded_by"] != current_user.user_id:
            raise ForbiddenError("You are not authorized to archive this medical record.")

        now = utc_now()
        await db[COLLECTION_MEDICAL_RECORDS].update_one(
            {"record_id": record_id},
            {"$set": {"status": RecordStatus.ARCHIVED.value, "updated_at": now}}
        )
        logger.info(f"Archived medical record {record_id}")
        return await MedicalRecordService._find_by_record_id(db, record_id)

    @staticmethod
    async def soft_delete_medical_record(
        db: AsyncIOMotorDatabase, record_id: str, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Soft-deletes a medical record (marks is_deleted=True)."""
        record = await MedicalRecordService.get_medical_record_by_id(db, record_id, current_user)

        if current_user.role == UserRole.PATIENT and record["uploaded_by"] != current_user.user_id:
            raise ForbiddenError("You are not authorized to delete this medical record.")
        elif current_user.role == UserRole.DOCTOR:
            doctor = await MedicalRecordService._resolve_doctor(db, current_user)
            doc_id = doctor["doctor_id"] if doctor else None
            if doc_id and record.get("doctor_id") != doc_id and record.get("uploaded_by") != current_user.user_id:
                raise ForbiddenError("You are not authorized to delete this medical record.")

        now = utc_now()
        await db[COLLECTION_MEDICAL_RECORDS].update_one(
            {"record_id": record_id},
            {"$set": {
                "is_deleted": True,
                "deleted_at": now,
                "deleted_by": current_user.user_id,
                "updated_at": now,
            }}
        )
        logger.info(f"Soft-deleted medical record {record_id} by {current_user.user_id}")

        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value,
                action="delete_medical_record",
                resource="medical_record",
                resource_id=record_id,
                metadata={"patient_id": record["patient_id"]},
            )
        except Exception as exc:
            logger.warning(f"Audit log error: {exc}")

        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

        return await MedicalRecordService._find_by_record_id(db, record_id)
