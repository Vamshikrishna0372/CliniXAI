"""Prescription and Medication business logic service for Phase 15."""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import (
    ResourceNotFoundError, ResourceConflictError, ForbiddenError, AppValidationError
)
from app.database.collections import (
    COLLECTION_PRESCRIPTIONS, COLLECTION_CONSULTATIONS, COLLECTION_PATIENTS,
    COLLECTION_DOCTORS, COLLECTION_MEDICAL_RECORDS, COLLECTION_APPOINTMENTS
)
from app.models.prescription import (
    PrescriptionInDB, PrescriptionStatus, FollowUpStatus, FollowUp, Medication
)
from app.models.consultation import ConsultationStatus
from app.models.user import UserInDB, UserRole
from app.schemas.prescriptions import CreatePrescriptionRequest, UpdatePrescriptionRequest
from app.utils.id_generator import generate_prescription_id
from app.utils.datetime import utc_now


class PrescriptionService:
    """Core prescription management and follow-up tracking service."""

    @staticmethod
    async def _find_by_prescription_id(db: AsyncIOMotorDatabase, prescription_id: str) -> Dict[str, Any]:
        doc = await db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": prescription_id})
        if not doc:
            raise ResourceNotFoundError("Prescription", prescription_id)
        return doc

    @staticmethod
    async def create_or_update_prescription(
        db: AsyncIOMotorDatabase,
        consultation_id: str,
        request: CreatePrescriptionRequest,
        doctor_user: UserInDB,
    ) -> PrescriptionInDB:
        """Doctor issues or updates a prescription for an active/completed consultation."""
        consult = await db[COLLECTION_CONSULTATIONS].find_one({"consultation_id": consultation_id})
        if not consult:
            raise ResourceNotFoundError("Consultation", consultation_id)

        # Doctor ownership check: Doctor must be the assigned doctor for this clinical encounter
        doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": doctor_user.user_id})
        if not doctor or doctor["doctor_id"] != consult["doctor_id"]:
            raise ForbiddenError("You are not authorized to create a prescription for another doctor's consultation.")

        if consult.get("status") in ["cancelled", "no_show", ConsultationStatus.CANCELLED.value]:
            raise AppValidationError(f"Cannot issue prescription for a {consult.get('status')} consultation.")

        apt_id = consult.get("appointment_id")
        if apt_id:
            apt = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": apt_id})
            if apt:
                if apt.get("status") in ["cancelled", "no_show"]:
                    raise AppValidationError(f"Cannot issue prescription for a {apt.get('status')} appointment.")
                if apt.get("patient_id") and apt.get("patient_id") != consult.get("patient_id"):
                    raise AppValidationError("Cross-patient mismatch: consultation patient differs from appointment patient.")
                if apt.get("doctor_id") and apt.get("doctor_id") != consult.get("doctor_id"):
                    raise AppValidationError("Cross-doctor mismatch: consultation doctor differs from appointment doctor.")

        # Medications list must be non-empty
        meds = request.medications or request.items or []
        if len(meds) == 0:
            raise AppValidationError("At least one medication is required to issue a prescription.")

        # Validate follow-up date if provided
        if request.follow_up and request.follow_up.required and request.follow_up.follow_up_date:
            try:
                fu_date = date.fromisoformat(request.follow_up.follow_up_date)
                if fu_date < utc_now().date():
                    raise AppValidationError("Follow-up date cannot be in the past.")
            except ValueError:
                raise AppValidationError(f"Invalid follow-up date format '{request.follow_up.follow_up_date}'. Expected YYYY-MM-DD.")

        # Check existing active prescription for this consultation (duplicate / concurrency rule)
        existing_active = await db[COLLECTION_PRESCRIPTIONS].find_one({
            "consultation_id": consultation_id,
            "status": {"$in": [PrescriptionStatus.ACTIVE.value, PrescriptionStatus.ISSUED.value, "active", "issued"]},
            "is_deleted": {"$ne": True}
        })
        now = utc_now()
        today_str = now.date().isoformat()
        meds_dict = [m.model_dump() for m in meds]
        follow_up_dict = request.follow_up.model_dump() if request.follow_up else None

        # Check for linked medical record
        linked_mr = await db[COLLECTION_MEDICAL_RECORDS].find_one({
            "consultation_id": consultation_id,
            "is_deleted": {"$ne": True}
        })
        medical_record_id = linked_mr.get("record_id") if linked_mr else None

        if existing_active:
            # Update existing active prescription idempotently
            await db[COLLECTION_PRESCRIPTIONS].update_one(
                {"prescription_id": existing_active["prescription_id"]},
                {
                    "$set": {
                        "medications": meds_dict,
                        "instructions": request.instructions,
                        "notes": request.notes,
                        "follow_up": follow_up_dict,
                        "updated_at": now,
                        "updated_by": doctor_user.user_id,
                    }
                }
            )
            updated_dict = await db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": existing_active["prescription_id"]})
            logger.info(f"Updated prescription {existing_active['prescription_id']} for consultation {consultation_id}")

            try:
                from app.database.mongodb import save_in_memory_snapshot
                await save_in_memory_snapshot(db)
            except Exception as e:
                logger.debug(f"Snapshot sync notice: {e}")

            return PrescriptionInDB(**updated_dict)

        # Generate server-authoritative prescription ID
        prescription_id = generate_prescription_id()
        rx_doc = PrescriptionInDB(
            prescription_id=prescription_id,
            consultation_id=consultation_id,
            appointment_id=consult.get("appointment_id"),
            patient_id=consult["patient_id"],
            doctor_id=consult["doctor_id"],
            medical_record_id=medical_record_id,
            medications=meds,
            instructions=request.instructions,
            notes=request.notes,
            follow_up=request.follow_up,
            status=PrescriptionStatus.ACTIVE,
            prescription_date=today_str,
            issued_at=now,
            issued_by=doctor.get("full_name") or doctor_user.full_name or doctor["doctor_id"],
            created_by=doctor_user.user_id,
            created_at=now,
            updated_at=now,
        )

        await db[COLLECTION_PRESCRIPTIONS].insert_one(rx_doc.to_mongo_dict())
        logger.info(f"Issued prescription {prescription_id} for consultation {consultation_id}")

        # Link into consultation document
        await db[COLLECTION_CONSULTATIONS].update_one(
            {"consultation_id": consultation_id},
            {"$set": {"prescription_id": prescription_id}, "$addToSet": {"prescription_ids": prescription_id}}
        )

        # Link into medical record if exists
        if medical_record_id:
            await db[COLLECTION_MEDICAL_RECORDS].update_one(
                {"record_id": medical_record_id},
                {"$addToSet": {"prescription_ids": prescription_id}}
            )

        # Audit Log & Notification
        try:
            from app.services.audit_service import log_audit_event
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType

            await log_audit_event(
                db=db,
                actor_id=doctor_user.user_id,
                role=doctor_user.role.value,
                action="prescription.created",
                resource="prescription",
                resource_id=prescription_id,
                metadata={
                    "consultation_id": consultation_id,
                    "patient_id": consult["patient_id"],
                    "medications_count": len(meds)
                },
            )

            patient = await db[COLLECTION_PATIENTS].find_one({"patient_id": consult["patient_id"]})
            if patient and patient.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=patient["user_id"],
                    notification_type=NotificationType.PRESCRIPTION_ISSUED,
                    title="Prescription Issued",
                    body=f"Prescription {prescription_id} has been issued for your consultation.",
                    reference_id=prescription_id,
                    reference_type="prescription",
                    dedupe_key=f"prescription_issued:{prescription_id}:{patient['user_id']}",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch audit/notification for prescription {prescription_id}: {exc}")

        # Snapshot persistence
        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception as e:
            logger.debug(f"Snapshot sync notice: {e}")

        return rx_doc

    @staticmethod
    async def cancel_prescription(
        db: AsyncIOMotorDatabase,
        prescription_id: str,
        reason: str,
        doctor_user: UserInDB,
    ) -> PrescriptionInDB:
        """Doctor cancels an active prescription."""
        rx = await db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": prescription_id})
        if not rx:
            raise ResourceNotFoundError("Prescription", prescription_id)

        clean_reason = (reason or "").strip()
        if not clean_reason:
            raise AppValidationError("A valid clinical cancellation reason is mandatory.")

        # Verify doctor ownership
        doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": doctor_user.user_id})
        if not doctor or doctor["doctor_id"] != rx["doctor_id"]:
            raise ForbiddenError("You are not authorized to cancel another doctor's prescription.")

        if rx.get("status") in [PrescriptionStatus.CANCELLED.value, "cancelled"]:
            raise AppValidationError("Prescription is already cancelled.")

        now = utc_now()
        res = await db[COLLECTION_PRESCRIPTIONS].update_one(
            {
                "prescription_id": prescription_id,
                "status": {"$in": [PrescriptionStatus.ACTIVE.value, PrescriptionStatus.ISSUED.value, "active", "issued"]}
            },
            {
                "$set": {
                    "status": PrescriptionStatus.CANCELLED.value,
                    "cancelled_at": now,
                    "cancelled_by": doctor_user.user_id,
                    "cancellation_reason": clean_reason,
                    "updated_at": now,
                    "updated_by": doctor_user.user_id,
                }
            }
        )
        if res.modified_count == 0:
            raise AppValidationError("Prescription is already cancelled.")

        updated_dict = await db[COLLECTION_PRESCRIPTIONS].find_one({"prescription_id": prescription_id})
        logger.info(f"Cancelled prescription {prescription_id} by doctor {doctor['doctor_id']}")

        # Audit log
        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=doctor_user.user_id,
                role=doctor_user.role.value,
                action="prescription.cancelled",
                resource="prescription",
                resource_id=prescription_id,
                metadata={
                    "cancellation_reason": reason,
                    "consultation_id": rx.get("consultation_id"),
                    "patient_id": rx.get("patient_id")
                },
            )
        except Exception as exc:
            logger.warning(f"Failed to log audit for prescription cancellation {prescription_id}: {exc}")

        # Snapshot persistence
        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception as e:
            logger.debug(f"Snapshot sync notice: {e}")

        return PrescriptionInDB(**updated_dict)

    @staticmethod
    async def get_prescription_by_id(db: AsyncIOMotorDatabase, prescription_id: str) -> Dict[str, Any]:
        return await PrescriptionService._find_by_prescription_id(db, prescription_id)

    @staticmethod
    async def get_prescription_by_consultation(
        db: AsyncIOMotorDatabase, consultation_id: str
    ) -> Optional[Dict[str, Any]]:
        return await db[COLLECTION_PRESCRIPTIONS].find_one({
            "consultation_id": consultation_id,
            "status": {"$in": [PrescriptionStatus.ACTIVE.value, PrescriptionStatus.ISSUED.value, "active", "issued"]},
            "is_deleted": {"$ne": True}
        })

    @staticmethod
    async def list_prescriptions(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        page: int = 1,
        page_size: int = 20,
        patient_id: Optional[str] = None,
        doctor_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        date_filter: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Role-aware prescription listing."""
        query: Dict[str, Any] = {"is_deleted": {"$ne": True}}

        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient:
                return [], 0
            query["patient_id"] = patient["patient_id"]
        elif current_user.role == UserRole.DOCTOR:
            from app.services.appointment_service import AppointmentService
            from app.database.collections import COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS
            doctor = await AppointmentService.get_doctor_for_user(db, current_user)
            if not doctor:
                return [], 0
            doc_id = doctor["doctor_id"]
            if patient_id:
                has_apt = await db[COLLECTION_APPOINTMENTS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
                has_consult = await db[COLLECTION_CONSULTATIONS].find_one({"patient_id": patient_id, "doctor_id": doc_id})
                if not has_apt and not has_consult:
                    raise ForbiddenError("You are not authorized to view prescriptions for this patient.")
                query["patient_id"] = patient_id
            else:
                query["doctor_id"] = doc_id
        else:  # Admin / Staff
            if patient_id:
                query["patient_id"] = patient_id
            if doctor_id:
                query["doctor_id"] = doctor_id

        if status_filter:
            # Map active/issued consistently
            if status_filter in ["active", "issued"]:
                query["status"] = {"$in": ["active", "issued"]}
            elif status_filter in ["cancelled", "draft"]:
                query["status"] = status_filter

        if date_filter:
            query["prescription_date"] = date_filter

        skip = (page - 1) * page_size
        total = await db[COLLECTION_PRESCRIPTIONS].count_documents(query)
        cursor = db[COLLECTION_PRESCRIPTIONS].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return docs, total

    @staticmethod
    async def list_follow_ups(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        status_filter: Optional[FollowUpStatus] = None,
        doctor_id: Optional[str] = None,
        patient_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Lists follow-up tasks derived from issued prescriptions."""
        query: Dict[str, Any] = {"follow_up.required": True, "is_deleted": {"$ne": True}}

        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient:
                return []
            query["patient_id"] = patient["patient_id"]
        elif current_user.role == UserRole.DOCTOR:
            doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": current_user.user_id})
            if doctor:
                query["doctor_id"] = doctor["doctor_id"]
            else:
                return []
        else:
            if patient_id:
                query["patient_id"] = patient_id
            if doctor_id:
                query["doctor_id"] = doctor_id

        cursor = db[COLLECTION_PRESCRIPTIONS].find(query).sort("follow_up.follow_up_date", 1)
        docs = await cursor.to_list(length=500)

        today_str = utc_now().date().isoformat()
        results = []
        for doc in docs:
            fu = doc.get("follow_up", {})
            fu_date = fu.get("follow_up_date")
            fu_status = fu.get("status", FollowUpStatus.UPCOMING.value)

            # Dynamically compute overdue if upcoming and date is past
            if fu_status == FollowUpStatus.UPCOMING.value and fu_date and fu_date < today_str:
                fu_status = FollowUpStatus.OVERDUE.value
                fu["status"] = fu_status

            if status_filter and fu_status != status_filter.value:
                continue

            results.append(doc)

        return results

