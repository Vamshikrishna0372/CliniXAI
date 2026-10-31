"""Consultation business logic service for Phase 4."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import (
    ResourceNotFoundError, ResourceConflictError, ForbiddenError, AppValidationError
)
from app.database.collections import (
    COLLECTION_CONSULTATIONS, COLLECTION_APPOINTMENTS, COLLECTION_PATIENTS,
    COLLECTION_DOCTORS, COLLECTION_PRESCRIPTIONS, COLLECTION_AI_ANALYSES,
    COLLECTION_MEDICAL_RECORDS
)
from app.models.consultation import (
    ConsultationInDB, ConsultationStatus, ChiefComplaint, Symptom, Vitals,
    ClinicalAssessment, Diagnosis, RiskLevel
)
from app.models.appointment import AppointmentStatus
from app.models.user import UserInDB, UserRole
from app.schemas.consultations import (
    PatientClinicalContextResponse, PastConsultationSummary
)
from app.utils.id_generator import generate_consultation_id
from app.utils.datetime import utc_now
from app.database.mongodb import save_in_memory_snapshot


class ConsultationService:
    """Core Doctor clinical workspace business logic service."""

    @staticmethod
    async def _find_by_consultation_id(db: AsyncIOMotorDatabase, consultation_id: str) -> Dict[str, Any]:
        doc = await db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": consultation_id})
        if not doc:
            doc = await db[COLLECTION_CONSULTATIONS].find_one({"appointment_id": consultation_id})
        if not doc:
            raise ResourceNotFoundError("Consultation", consultation_id)
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
    async def _check_doctor_authorization(
        db: AsyncIOMotorDatabase, doctor_user: UserInDB, consult_dict: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enforces care relationship authorization for Doctor role."""
        if doctor_user.role in (UserRole.HOSPITAL_ADMIN,):
            return {}
        if doctor_user.role != UserRole.DOCTOR:
            raise ForbiddenError("Only doctors can perform clinical actions on a consultation.")

        doctor = await ConsultationService._resolve_doctor(db, doctor_user)
        if not doctor:
            raise ForbiddenError("Authenticated user does not have an active Doctor profile.")

        doc_id = doctor["doctor_id"]
        # Direct assigned doctor
        if consult_dict.get("doctor_id") == doc_id:
            return doctor

        # Or has valid active care relationship (appointment or consultation with patient)
        patient_id = consult_dict.get("patient_id")
        has_apt = await db[COLLECTION_APPOINTMENTS].find_one({
            "patient_id": patient_id,
            "doctor_id": doc_id,
        })
        if has_apt:
            return doctor

        has_con = await db[COLLECTION_CONSULTATIONS].find_one({
            "patient_id": patient_id,
            "doctor_id": doc_id,
        })
        if has_con:
            return doctor

        raise ForbiddenError("You are not authorized to access or modify this consultation.")

    @staticmethod
    async def start_consultation(
        db: AsyncIOMotorDatabase, appointment_id: str, doctor_user: UserInDB
    ) -> ConsultationInDB:
        """Starts a consultation session linked to an appointment.

        Enforces:
        - Doctor owns appointment (or Admin/Staff operational authorization).
        - Appointment is not cancelled, no_show, or completed.
        - Idempotent: If consultation already exists for this appointment_id, returns existing.
        - Concurrency safe against duplicate simultaneous starts.
        - Updates appointment status -> 'in_consultation'.
        - Immediately syncs in-memory snapshot to disk.
        """
        apt = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": appointment_id})
        if not apt:
            raise ResourceNotFoundError("Appointment", appointment_id)

        if doctor_user.role == UserRole.PATIENT:
            raise ForbiddenError("Patients cannot start clinical consultations.")

        # Doctor ownership check for DOCTOR role (Admin and Staff operate with hospital-wide operational privileges)
        doctor = None
        if doctor_user.role == UserRole.DOCTOR:
            doctor = await ConsultationService._resolve_doctor(db, doctor_user)
            if not doctor:
                raise ForbiddenError("Authenticated user does not have an active Doctor profile.")

            if doctor["doctor_id"] != apt["doctor_id"]:
                raise ForbiddenError("You are not authorized to start a consultation for another doctor's appointment.")

        if apt.get("status") in (AppointmentStatus.CANCELLED.value, AppointmentStatus.NO_SHOW.value, AppointmentStatus.COMPLETED.value):
            raise AppValidationError(f"Cannot start consultation. Appointment is in status '{apt['status']}'.")

        # Idempotency check: return existing consultation if already started
        existing = await db[COLLECTION_CONSULTATIONS].find_one({"appointment_id": appointment_id})
        if existing:
            return ConsultationInDB(**existing)

        consultation_id = generate_consultation_id()
        now = utc_now()

        consultation_doc = ConsultationInDB(
            consultation_id=consultation_id,
            appointment_id=appointment_id,
            patient_id=apt["patient_id"],
            doctor_id=apt["doctor_id"],
            department_id=apt["department_id"],
            status=ConsultationStatus.IN_PROGRESS,
            created_by=doctor_user.user_id,
            version=1,
            started_at=now,
            created_at=now,
            updated_at=now,
        )

        try:
            await db[COLLECTION_CONSULTATIONS].insert_one(consultation_doc.to_mongo_dict())
        except Exception:
            # Handle duplicate key / concurrent race condition
            existing = await db[COLLECTION_CONSULTATIONS].find_one({"appointment_id": appointment_id})
            if existing:
                return ConsultationInDB(**existing)
            raise

        # Update appointment status to in_consultation
        await db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": appointment_id},
            {
                "$set": {
                    "status": AppointmentStatus.IN_CONSULTATION.value,
                    "queue.called_at": now,
                    "updated_at": now,
                }
            }
        )

        logger.info(f"Started consultation {consultation_id} for appointment {appointment_id} by user {doctor_user.user_id}")

        # Audit Log & Notification
        try:
            from app.services.audit_service import log_audit_event
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType

            await log_audit_event(
                db=db,
                actor_id=doctor_user.user_id,
                role=doctor_user.role.value,
                action="consultation.started",
                resource="consultation",
                resource_id=consultation_id,
                metadata={"appointment_id": appointment_id, "patient_id": apt["patient_id"]},
            )

            patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": apt["patient_id"]})
            if patient and patient.get("user_id"):
                doc_name = f"Dr. {doctor.get('first_name', '')} {doctor.get('last_name', '')}".strip() if doctor else "Your doctor"
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=patient["user_id"],
                    notification_type=NotificationType.CONSULTATION_STARTED,
                    title="Consultation Started",
                    body=f"{doc_name} has started your consultation.",
                    reference_id=consultation_id,
                    reference_type="consultation",
                    dedupe_key=f"consultation_started:{consultation_id}:{patient['user_id']}",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch audit/notification for consultation start {consultation_id}: {exc}")

        await save_in_memory_snapshot(db)
        return consultation_doc

    @staticmethod
    async def get_consultation_by_id(db: AsyncIOMotorDatabase, consultation_id: str) -> Dict[str, Any]:
        return await ConsultationService._find_by_consultation_id(db, consultation_id)

    @staticmethod
    async def get_patient_clinical_context(
        db: AsyncIOMotorDatabase, patient_id: str, doctor_user: UserInDB
    ) -> PatientClinicalContextResponse:
        """Retrieves clinical context (patient profile, allergies, past completed consultations, active prescriptions) for Doctor workspace."""
        patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": patient_id})
        if not patient:
            raise ResourceNotFoundError("Patient", patient_id)

        if doctor_user.role == UserRole.DOCTOR:
            from app.services.appointment_service import AppointmentService
            doctor = await AppointmentService.get_doctor_for_user(db, doctor_user)
            doc_id = doctor.get("doctor_id") if doctor else None
            if not doc_id:
                raise ForbiddenError("You are not authorized to access this patient's clinical workspace without an established care relationship.")
            has_apt = await db[COLLECTION_APPOINTMENTS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
            has_consult = await db[COLLECTION_CONSULTATIONS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
            if not has_apt and not has_consult:
                raise ForbiddenError("You are not authorized to access this patient's clinical workspace without an established care relationship.")

        # Fetch past completed consultations for this patient
        past_consults_cursor = db[COLLECTION_CONSULTATIONS].find({
            "patient_id": patient_id,
            "status": ConsultationStatus.COMPLETED.value
        }).sort("completed_at", -1).limit(10)
        past_docs = await past_consults_cursor.to_list(length=10)

        past_summaries = []
        for c in past_docs:
            diagnoses = [Diagnosis(**d) for d in c.get("diagnoses", [])]
            assessment_summary = c.get("clinical_assessment", {}).get("summary") if c.get("clinical_assessment") else None
            past_summaries.append(
                PastConsultationSummary(
                    consultation_id=c["consultation_id"],
                    appointment_id=c["appointment_id"],
                    date=c.get("completed_at", c["created_at"]).strftime("%Y-%m-%d") if isinstance(c.get("completed_at"), datetime) else str(c.get("completed_at", "")),
                    diagnoses=diagnoses,
                    assessment_summary=assessment_summary,
                )
            )

        # Fetch recent prescriptions
        prescriptions_cursor = db[COLLECTION_PRESCRIPTIONS].find({"patient_id": patient_id}).sort("created_at", -1).limit(5)
        rx_docs = await prescriptions_cursor.to_list(length=5)
        for rx in rx_docs:
            rx.pop("_id", None)

        # Safely extract names whether full_name or first/last name
        first_name = patient.get("first_name")
        last_name = patient.get("last_name")
        if not first_name and not last_name:
            full_name = patient.get("full_name") or ""
            parts = full_name.split(" ", 1)
            first_name = parts[0] if parts and parts[0] else "Patient"
            last_name = parts[1] if len(parts) > 1 else ""
        elif not first_name:
            first_name = "Patient"
        elif not last_name:
            last_name = ""

        return PatientClinicalContextResponse(
            patient_id=patient["patient_id"],
            first_name=first_name,
            last_name=last_name,
            full_name=patient.get("full_name") or f"{first_name} {last_name}".strip(),
            date_of_birth=str(patient.get("date_of_birth")) if patient.get("date_of_birth") else None,
            gender=patient.get("gender"),
            blood_group=patient.get("blood_group"),
            allergies=patient.get("allergies", []),
            past_consultations=past_summaries,
            recent_prescriptions=rx_docs,
        )

    @staticmethod
    async def update_consultation_data(
        db: AsyncIOMotorDatabase,
        consultation_id: str,
        update_field: str,
        data_value: Any,
        doctor_user: UserInDB,
        expected_version: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generic validator and updater for active consultation sections (chief_complaint, symptoms, vitals, clinical_notes, assessment, diagnoses, instructions)."""
        consult_dict = await ConsultationService._find_by_consultation_id(db, consultation_id)

        if consult_dict["status"] == ConsultationStatus.COMPLETED.value:
            raise AppValidationError("Completed consultation is finalized and cannot be modified.")
        if consult_dict["status"] == ConsultationStatus.CANCELLED.value:
            raise AppValidationError("Cancelled consultation cannot be modified.")

        await ConsultationService._check_doctor_authorization(db, doctor_user, consult_dict)

        now = utc_now()
        filter_query: Dict[str, Any] = {"consultation_id": consultation_id}
        if expected_version is not None:
            filter_query["version"] = expected_version

        result = await db[COLLECTION_CONSULTATIONS].update_one(
            filter_query,
            {"$set": {update_field: data_value, "updated_at": now}, "$inc": {"version": 1}}
        )
        if expected_version is not None and result.matched_count == 0:
            raise ResourceConflictError("Consultation has been modified by another concurrent request. Please refresh and retry.")

        # Audit logging for consultation update
        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=doctor_user.user_id,
                role=doctor_user.role.value,
                action="consultation.updated",
                resource="consultation",
                resource_id=consultation_id,
                metadata={"field": update_field, "patient_id": consult_dict["patient_id"]},
            )
        except Exception as exc:
            logger.warning(f"Failed to log audit for consultation update {consultation_id}: {exc}")

        await save_in_memory_snapshot(db)
        return await ConsultationService._find_by_consultation_id(db, consultation_id)

    @staticmethod
    async def update_care_plan(
        db: AsyncIOMotorDatabase,
        consultation_id: str,
        care_plan: str,
        follow_up_required: bool,
        follow_up_date: Optional[str],
        doctor_user: UserInDB,
    ) -> Dict[str, Any]:
        """Updates care plan and follow up instructions."""
        consult_dict = await ConsultationService._find_by_consultation_id(db, consultation_id)
        if consult_dict["status"] == ConsultationStatus.COMPLETED.value:
            raise AppValidationError("Completed consultation is finalized and cannot be modified.")
        if consult_dict["status"] == ConsultationStatus.CANCELLED.value:
            raise AppValidationError("Cancelled consultation cannot be modified.")

        await ConsultationService._check_doctor_authorization(db, doctor_user, consult_dict)

        now = utc_now()
        await db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": consultation_id},
            {
                "$set": {
                    "care_plan": care_plan,
                    "follow_up_required": follow_up_required,
                    "follow_up_date": follow_up_date,
                    "updated_at": now,
                },
                "$inc": {"version": 1},
            }
        )
        await save_in_memory_snapshot(db)
        return await ConsultationService._find_by_consultation_id(db, consultation_id)

    @staticmethod
    async def link_ai_analysis(
        db: AsyncIOMotorDatabase,
        consultation_id: str,
        ai_analysis_id: str,
        doctor_user: UserInDB,
    ) -> Dict[str, Any]:
        """Links an existing authorized AI analysis to this clinical encounter. Guarantees cross-patient isolation and AI immutability."""
        consult_dict = await ConsultationService._find_by_consultation_id(db, consultation_id)
        if consult_dict["status"] == ConsultationStatus.COMPLETED.value:
            raise AppValidationError("Completed consultation is finalized and cannot be modified.")
        if consult_dict["status"] == ConsultationStatus.CANCELLED.value:
            raise AppValidationError("Cancelled consultation cannot be modified.")

        await ConsultationService._check_doctor_authorization(db, doctor_user, consult_dict)

        ai_doc = await db[COLLECTION_AI_ANALYSES].find_one({"analysis_id": ai_analysis_id})
        if not ai_doc:
            raise ResourceNotFoundError("AI Analysis", ai_analysis_id)

        # Strict cross-patient boundary enforcement
        if ai_doc.get("patient_id") != consult_dict.get("patient_id"):
            raise AppValidationError("Cannot link AI analysis belonging to another patient.")

        now = utc_now()
        await db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": consultation_id},
            {
                "$addToSet": {
                    "linked_ai_analysis_ids": ai_analysis_id,
                    "ai_analysis_references": ai_analysis_id,
                },
                "$set": {"updated_at": now},
                "$inc": {"version": 1},
            }
        )

        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=doctor_user.user_id,
                role=doctor_user.role.value,
                action="consultation.ai_analysis_linked",
                resource="consultation",
                resource_id=consultation_id,
                metadata={"ai_analysis_id": ai_analysis_id, "patient_id": consult_dict["patient_id"]},
            )
        except Exception as exc:
            logger.warning(f"Failed to log audit for ai link {consultation_id}: {exc}")

        await save_in_memory_snapshot(db)
        return await ConsultationService._find_by_consultation_id(db, consultation_id)

    @staticmethod
    async def link_medical_record(
        db: AsyncIOMotorDatabase,
        consultation_id: str,
        record_id: str,
        doctor_user: UserInDB,
    ) -> Dict[str, Any]:
        """Links an existing authorized Medical Record to this clinical encounter. Guarantees cross-patient isolation."""
        consult_dict = await ConsultationService._find_by_consultation_id(db, consultation_id)
        if consult_dict["status"] == ConsultationStatus.COMPLETED.value:
            raise AppValidationError("Completed consultation is finalized and cannot be modified.")
        if consult_dict["status"] == ConsultationStatus.CANCELLED.value:
            raise AppValidationError("Cancelled consultation cannot be modified.")

        await ConsultationService._check_doctor_authorization(db, doctor_user, consult_dict)

        mr_doc = await db[COLLECTION_MEDICAL_RECORDS].find_one({"record_id": record_id})
        if not mr_doc:
            raise ResourceNotFoundError("Medical Record", record_id)

        # Strict cross-patient boundary enforcement
        if mr_doc.get("patient_id") != consult_dict.get("patient_id"):
            raise AppValidationError("Cannot link medical record belonging to another patient.")

        now = utc_now()
        await db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": consultation_id},
            {
                "$addToSet": {
                    "linked_medical_record_ids": record_id,
                    "medical_record_references": record_id,
                },
                "$set": {"updated_at": now},
                "$inc": {"version": 1},
            }
        )

        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=doctor_user.user_id,
                role=doctor_user.role.value,
                action="consultation.medical_record_linked",
                resource="consultation",
                resource_id=consultation_id,
                metadata={"record_id": record_id, "patient_id": consult_dict["patient_id"]},
            )
        except Exception as exc:
            logger.warning(f"Failed to log audit for mr link {consultation_id}: {exc}")

        await save_in_memory_snapshot(db)
        return await ConsultationService._find_by_consultation_id(db, consultation_id)

    @staticmethod
    async def complete_consultation(
        db: AsyncIOMotorDatabase, consultation_id: str, doctor_user: UserInDB
    ) -> Dict[str, Any]:
        """Finalizes and completes a consultation session.

        Validates minimum required clinical fields:
        - Clinical Assessment must be recorded with non-empty summary.
        - At least one primary diagnosis must be recorded.
        """
        consult_dict = await ConsultationService._find_by_consultation_id(db, consultation_id)

        if consult_dict["status"] == ConsultationStatus.COMPLETED.value:
            return consult_dict

        if consult_dict["status"] == ConsultationStatus.CANCELLED.value:
            raise AppValidationError("Cancelled consultation cannot be completed.")

        await ConsultationService._check_doctor_authorization(db, doctor_user, consult_dict)

        # Validate minimum clinical documentation
        if not consult_dict.get("clinical_assessment") or not consult_dict.get("clinical_assessment", {}).get("summary"):
            raise AppValidationError("Cannot complete consultation: Doctor Clinical Assessment is required.")

        diagnoses = consult_dict.get("diagnoses", [])
        if not diagnoses:
            raise AppValidationError("Cannot complete consultation: At least one diagnosis is required.")

        now = utc_now()

        # Update consultation
        await db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": consultation_id},
            {
                "$set": {
                    "status": ConsultationStatus.COMPLETED.value,
                    "completed_at": now,
                    "completed_by": doctor_user.user_id,
                    "updated_at": now,
                },
                "$inc": {"version": 1},
            }
        )

        # Update appointment -> completed
        await db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": consult_dict["appointment_id"]},
            {
                "$set": {
                    "status": AppointmentStatus.COMPLETED.value,
                    "queue.completed_at": now,
                    "updated_at": now,
                }
            }
        )

        # Idempotently create/update linked Medical Record document in MongoDB
        try:
            from app.database.collections import COLLECTION_MEDICAL_RECORDS
            from app.utils.id_generator import generate_medical_record_id

            primary_diag = diagnoses[0].get("name", "Clinical Consultation") if isinstance(diagnoses[0], dict) else getattr(diagnoses[0], "name", "Clinical Consultation")
            
            existing_mr = await db[COLLECTION_MEDICAL_RECORDS].find_one({"consultation_id": consultation_id})
            if not existing_mr:
                rec_id = generate_medical_record_id()
                mr_doc = {
                    "record_id": rec_id,
                    "patient_id": consult_dict["patient_id"],
                    "doctor_id": consult_dict["doctor_id"],
                    "department_id": consult_dict["department_id"],
                    "appointment_id": consult_dict["appointment_id"],
                    "consultation_id": consultation_id,
                    "record_type": "clinical_document",
                    "title": f"Consultation Summary — {primary_diag}",
                    "description": f"Diagnosis: {primary_diag}. Completed on {now.strftime('%Y-%m-%d')}.",
                    "clinical_date": now.strftime("%Y-%m-%d"),
                    "diagnosis": primary_diag,
                    "clinical_notes": consult_dict.get("clinical_assessment", {}).get("summary") if isinstance(consult_dict.get("clinical_assessment"), dict) else None,
                    "uploaded_by": doctor_user.user_id,
                    "source": "doctor",
                    "status": "active",
                    "is_deleted": False,
                    "created_at": now,
                    "updated_at": now,
                }
                await db[COLLECTION_MEDICAL_RECORDS].insert_one(mr_doc)
                logger.info(f"Created Medical Record {rec_id} for consultation {consultation_id}")
        except Exception as mr_exc:
            logger.warning(f"Medical record auto-creation notice for {consultation_id}: {mr_exc}")

        # Idempotently create linked Bill document in MongoDB
        try:
            from app.services.billing_service import BillingService
            await BillingService.create_bill_from_consultation(db, consultation_id, doctor_user)
            logger.info(f"Auto-generated Billing Record for consultation {consultation_id}")
        except Exception as bill_exc:
            logger.warning(f"Billing auto-creation notice for {consultation_id}: {bill_exc}")

        logger.info(f"Completed consultation {consultation_id} for appointment {consult_dict['appointment_id']}")

        # Audit Log & Notification
        try:
            from app.services.audit_service import log_audit_event
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType

            await log_audit_event(
                db=db,
                actor_id=doctor_user.user_id,
                role=doctor_user.role.value,
                action="consultation.completed",
                resource="consultation",
                resource_id=consultation_id,
                metadata={"appointment_id": consult_dict["appointment_id"], "patient_id": consult_dict["patient_id"]},
            )

            patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": consult_dict["patient_id"]})
            if patient and patient.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=patient["user_id"],
                    notification_type=NotificationType.CONSULTATION_COMPLETED,
                    title="Consultation Completed",
                    body=f"Your consultation {consultation_id} is completed. Diagnosis and treatment details are available.",
                    reference_id=consultation_id,
                    reference_type="consultation",
                    dedupe_key=f"consultation_completed:{consultation_id}:{patient['user_id']}",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch audit/notification for consultation completion {consultation_id}: {exc}")

        await save_in_memory_snapshot(db)
        return await ConsultationService._find_by_consultation_id(db, consultation_id)

    @staticmethod
    async def cancel_consultation(
        db: AsyncIOMotorDatabase, consultation_id: str, reason: Optional[str], doctor_user: UserInDB
    ) -> Dict[str, Any]:
        """Cancels an active consultation."""
        consult_dict = await ConsultationService._find_by_consultation_id(db, consultation_id)

        if consult_dict["status"] == ConsultationStatus.COMPLETED.value:
            raise AppValidationError("Completed consultation cannot be cancelled.")

        await ConsultationService._check_doctor_authorization(db, doctor_user, consult_dict)

        now = utc_now()
        await db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": consultation_id},
            {
                "$set": {
                    "status": ConsultationStatus.CANCELLED.value,
                    "cancelled_at": now,
                    "cancel_reason": reason,
                    "updated_at": now,
                },
                "$inc": {"version": 1},
            }
        )
        logger.info(f"Cancelled consultation {consultation_id}")
        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=doctor_user.user_id,
                role=doctor_user.role.value,
                action="consultation.cancelled",
                resource="consultation",
                resource_id=consultation_id,
                metadata={"reason": reason, "patient_id": consult_dict["patient_id"]},
            )
        except Exception as exc:
            logger.warning(f"Failed to log audit for consultation cancel {consultation_id}: {exc}")

        await save_in_memory_snapshot(db)
        return await ConsultationService._find_by_consultation_id(db, consultation_id)

    @staticmethod
    async def list_consultations(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        page: int = 1,
        page_size: int = 20,
        status: Optional[ConsultationStatus] = None,
        patient_id: Optional[str] = None,
        doctor_id: Optional[str] = None,
        department_id: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Role-aware consultation listing."""
        query: Dict[str, Any] = {}

        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient:
                return [], 0
            query["patient_id"] = patient["patient_id"]
            query["status"] = ConsultationStatus.COMPLETED.value
        elif current_user.role == UserRole.DOCTOR:
            from app.services.appointment_service import AppointmentService
            doctor = await AppointmentService.get_doctor_for_user(db, current_user)
            if not doctor:
                return [], 0
            doc_id = doctor["doctor_id"]
            if patient_id:
                has_apt = await db[COLLECTION_APPOINTMENTS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
                has_consult = await db[COLLECTION_CONSULTATIONS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
                if not has_apt and not has_consult:
                    raise ForbiddenError("You are not authorized to view consultations for this patient.")
                query["patient_id"] = patient_id
            else:
                query["doctor_id"] = doc_id
        else: # Admin / Staff
            if patient_id:
                query["patient_id"] = patient_id
            if doctor_id:
                query["doctor_id"] = doctor_id

        if department_id:
            query["department_id"] = department_id
        if status:
            query["status"] = status.value

        skip = (page - 1) * page_size
        total = await db[COLLECTION_CONSULTATIONS].count_documents(query)
        cursor = db[COLLECTION_CONSULTATIONS].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return docs, total
