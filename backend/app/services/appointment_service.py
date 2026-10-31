"""Appointment, Check-In, and Queue Management Business Logic Service."""

from datetime import datetime, date, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import (
    ResourceNotFoundError, ResourceConflictError, ForbiddenError, AppValidationError
)
from app.database.collections import (
    COLLECTION_APPOINTMENTS, COLLECTION_PATIENTS, COLLECTION_DOCTORS, COLLECTION_DEPARTMENTS
)
from app.models.appointment import (
    AppointmentInDB, AppointmentStatus, AppointmentType, BookingSource,
    CheckInData, CheckInMethod, QueueData, CancellationData, RescheduleRecord,
    VALID_STATUS_TRANSITIONS, TERMINAL_STATUSES, RESCHEDULABLE_STATUSES, CANCELLABLE_STATUSES
)
from app.models.doctor import DoctorInDB, DoctorStatus
from app.models.patient import PatientInDB, PatientStatus
from app.models.user import UserInDB, UserRole
from app.schemas.appointments import (
    BookAppointmentRequest, StaffBookAppointmentRequest, RescheduleAppointmentRequest,
    CancelAppointmentRequest, CheckInRequest
)
from app.services.doctor_service import DoctorService
from app.utils.id_generator import generate_appointment_id, generate_queue_token
from app.utils.datetime import utc_now


class AppointmentService:
    """Core appointment lifecycle, double-booking prevention, check-in, and queue management service."""

    @staticmethod
    async def _find_by_appointment_id(db: AsyncIOMotorDatabase, appointment_id: str) -> Dict[str, Any]:
        doc = await db[COLLECTION_APPOINTMENTS].find_one({"appointment_id": appointment_id, "is_deleted": {"$ne": True}})
        if not doc:
            raise ResourceNotFoundError("Appointment", appointment_id)
        return doc

    @staticmethod
    async def get_doctor_for_user(db: AsyncIOMotorDatabase, current_user: Any) -> Optional[Dict[str, Any]]:
        """Resolves doctor profile for authenticated user via user_id, email, or doctor_id."""
        if isinstance(current_user, str):
            doctor = await db[COLLECTION_DOCTORS].find_one({
                "$or": [
                    {"user_id": current_user},
                    {"email": current_user},
                    {"doctor_id": current_user},
                ]
            })
            return doctor
        user_id = getattr(current_user, "user_id", None)
        email = getattr(current_user, "email", None)
        doctor = None
        if user_id:
            doctor = await db[COLLECTION_DOCTORS].find_one({"user_id": user_id})
        if not doctor and email:
            doctor = await db[COLLECTION_DOCTORS].find_one({"email": email})
        if not doctor and user_id:
            doctor = await db[COLLECTION_DOCTORS].find_one({"doctor_id": user_id})
        return doctor

    @staticmethod
    async def validate_slot_and_book(
        db: AsyncIOMotorDatabase,
        patient_id: str,
        doctor_id: str,
        department_id: str,
        appointment_date_str: str,
        start_time_str: str,
        reason: Optional[str],
        appointment_type: AppointmentType,
        booking_source: BookingSource,
        created_by_user_id: str,
        created_by_role: str,
    ) -> AppointmentInDB:
        """Core booking validation engine.

        Ensures:
        1. Patient exists and is ACTIVE.
        2. Doctor exists and is ACTIVE.
        3. Department exists.
        4. Doctor belongs to Department if assigned.
        5. Slot is within Doctor's calculated availability for that date.
        6. Double booking conflict check (atomic query).
        """
        # 1. Verify Patient
        patient_doc = await db[COLLECTION_PATIENTS].find_one({"patient_id": patient_id})
        if not patient_doc:
            raise ResourceNotFoundError("Patient", patient_id)
        if patient_doc.get("status") != PatientStatus.ACTIVE.value:
            raise AppValidationError(f"Patient profile '{patient_id}' is inactive.")

        # 2. Verify Doctor
        doctor_doc = await db[COLLECTION_DOCTORS].find_one({"doctor_id": doctor_id})
        if not doctor_doc:
            raise ResourceNotFoundError("Doctor", doctor_id)
        if doctor_doc.get("status") != DoctorStatus.ACTIVE.value:
            raise AppValidationError(f"Doctor '{doctor_id}' is currently inactive or on leave.")

        # 3. Verify Department
        dept_doc = await db[COLLECTION_DEPARTMENTS].find_one({"department_id": department_id})
        if not dept_doc:
            doc_dept = doctor_doc.get("department_id")
            if doc_dept:
                dept_doc = await db[COLLECTION_DEPARTMENTS].find_one({"department_id": doc_dept})
                if dept_doc:
                    department_id = doc_dept
            if not dept_doc:
                raise ResourceNotFoundError("Department", department_id)

        # 4. Department association check
        doc_dept = doctor_doc.get("department_id")
        if doc_dept and doc_dept != department_id:
            # Reconcile to doctor's canonical department
            department_id = doc_dept

        # 5. Dynamic slot availability check
        availability = await DoctorService.calculate_available_slots(db, doctor_id, appointment_date_str)
        matched_slot = None
        for slot in availability.available_slots:
            if slot.start_time == start_time_str:
                matched_slot = slot
                break

        if not matched_slot:
            raise AppValidationError(
                f"Requested slot '{start_time_str}' on {appointment_date_str} is not available for Doctor '{doctor_id}'."
            )

        end_time_str = matched_slot.end_time

        # 6. Double booking check (Backend/Database level concurrency safeguard & interval overlap check)
        existing_conflict = await db[COLLECTION_APPOINTMENTS].find_one({
            "doctor_id": doctor_id,
            "appointment_date": appointment_date_str,
            "status": {"$nin": [AppointmentStatus.CANCELLED.value, AppointmentStatus.NO_SHOW.value]},
            "start_time": {"$lt": end_time_str},
            "$or": [
                {"end_time": {"$gt": start_time_str}},
                {"end_time": {"$exists": False}, "start_time": start_time_str},
            ]
        })
        if existing_conflict:
            doc_name = f"Dr. {doctor_doc.get('first_name', '')} {doctor_doc.get('last_name', '')}".strip() or f"Doctor '{doctor_id}'"
            raise ResourceConflictError(
                f"{doc_name} is already booked for this time slot. Please select another time."
            )

        appointment_id = generate_appointment_id()
        appointment_doc = AppointmentInDB(
            appointment_id=appointment_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
            department_id=department_id,
            appointment_date=appointment_date_str,
            start_time=start_time_str,
            end_time=end_time_str,
            reason=reason,
            appointment_type=appointment_type,
            status=AppointmentStatus.SCHEDULED,
            booking_source=booking_source,
            created_by=created_by_user_id,
            created_by_role=created_by_role,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        import asyncio
        from pymongo.errors import DuplicateKeyError

        try:
            await db[COLLECTION_APPOINTMENTS].insert_one(appointment_doc.to_mongo_dict())
        except DuplicateKeyError:
            doc_name = f"Dr. {doctor_doc.get('first_name', '')} {doctor_doc.get('last_name', '')}".strip() or f"Doctor '{doctor_id}'"
            raise ResourceConflictError(
                f"{doc_name} is already booked for this time slot. Please select another time."
            )

        logger.info(f"Booked appointment: {appointment_id} (Patient: {patient_id}, Doctor: {doctor_id}, Date: {appointment_date_str} {start_time_str})")

        try:
            from app.database.mongodb import save_in_memory_snapshot
            asyncio.create_task(save_in_memory_snapshot(db))
        except Exception:
            pass

        # Audit Log & In-App Notification
        try:
            from app.services.audit_service import log_audit_event
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType

            await log_audit_event(
                db=db,
                actor_id=created_by_user_id,
                role=created_by_role,
                action="create_appointment",
                resource="appointment",
                resource_id=appointment_id,
                metadata={"patient_id": patient_id, "doctor_id": doctor_id, "date": appointment_date_str, "time": start_time_str},
            )

            pat_user_id = patient_doc.get("user_id")
            doc_user_id = doctor_doc.get("user_id")
            doc_name = f"Dr. {doctor_doc.get('first_name', '')} {doctor_doc.get('last_name', '')}".strip()
            pat_name = f"{patient_doc.get('first_name', '')} {patient_doc.get('last_name', '')}".strip() or "Patient"

            if pat_user_id:
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=pat_user_id,
                    notification_type=NotificationType.APPOINTMENT_BOOKED,
                    title="Appointment Booked",
                    body=f"Your appointment {appointment_id} with {doc_name} on {appointment_date_str} at {start_time_str} is booked.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_booked:{appointment_id}:{pat_user_id}",
                )

            if doc_user_id:
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=doc_user_id,
                    notification_type=NotificationType.APPOINTMENT_BOOKED,
                    title="New Appointment Scheduled",
                    body=f"New appointment {appointment_id} scheduled for patient {pat_name} on {appointment_date_str} at {start_time_str}.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_booked:{appointment_id}:{doc_user_id}",
                )
        except Exception as audit_exc:
            logger.warning(f"Failed to record audit/notification for booking {appointment_id}: {audit_exc}")

        # Phase 9: Non-blocking Email & Google Calendar Integration Dispatches
        try:
            from app.services.email_service import EmailService
            from app.integrations.google_calendar import GoogleCalendarService

            doc_name = f"Dr. {doctor_doc.get('first_name', '')} {doctor_doc.get('last_name', '')}".strip()
            dept_name = dept_doc.get("department_name", "Clinical Department")
            patient_email = patient_doc.get("email")

            if patient_email:
                patient_name = f"{patient_doc.get('first_name', '')} {patient_doc.get('last_name', '')}".strip() or "Patient"
                await EmailService.send_appointment_email(
                    to_email=patient_email,
                    recipient_name=patient_name,
                    action="booked",
                    appointment_id=appointment_id,
                    doctor_name=doc_name,
                    department_name=dept_name,
                    appointment_date=appointment_date_str,
                    slot_time=start_time_str,
                )

            if patient_doc.get("user_id"):
                await GoogleCalendarService.create_appointment_event(
                    db=db,
                    user_id=patient_doc["user_id"],
                    appointment_id=appointment_id,
                    doctor_name=doc_name,
                    department_name=dept_name,
                    appointment_date=appointment_date_str,
                    slot_time=start_time_str,
                )
        except Exception as exc:
            logger.warning(f"Non-blocking integration dispatch error for appointment {appointment_id}: {exc}")

        return appointment_doc

    @staticmethod
    async def get_appointment_by_id(
        db: AsyncIOMotorDatabase,
        appointment_id: str,
        current_user: Optional[UserInDB] = None,
    ) -> Dict[str, Any]:
        doc = await AppointmentService._find_by_appointment_id(db, appointment_id)
        if current_user:
            if current_user.role == UserRole.PATIENT:
                patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
                if not patient or patient["patient_id"] != doc["patient_id"]:
                    raise ForbiddenError("You are not authorized to view another patient's appointment.")
            elif current_user.role == UserRole.DOCTOR:
                doctor = await AppointmentService.get_doctor_for_user(db, current_user)
                if not doctor or doctor["doctor_id"] != doc["doctor_id"]:
                    raise ForbiddenError("You are not authorized to view another doctor's private appointment.")
        return doc

    @staticmethod
    async def list_appointments(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        page: int = 1,
        page_size: int = 20,
        patient_id: Optional[str] = None,
        doctor_id: Optional[str] = None,
        department_id: Optional[str] = None,
        status: Optional[AppointmentStatus] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Role-aware appointment list retrieval with filtering and pagination.

        - Patient: strictly forced to filter by own linked patient_id.
        - Doctor: default filter to own assigned doctor_id (unless admin override).
        - Staff / Admin: full operational access across hospital.
        """
        query: Dict[str, Any] = {}

        if current_user.role == UserRole.PATIENT:
            # Resolve patient_id for current user
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient:
                return [], 0
            query["patient_id"] = patient["patient_id"]
        elif current_user.role == UserRole.DOCTOR:
            doctor = await AppointmentService.get_doctor_for_user(db, current_user)
            if not doctor:
                return [], 0
            if doctor_id and doctor_id != doctor["doctor_id"]:
                raise ForbiddenError("Doctors can only access their own appointments.")
            query["doctor_id"] = doctor["doctor_id"]
            if patient_id:
                query["patient_id"] = patient_id
        else: # Staff or Admin
            if patient_id:
                query["patient_id"] = patient_id
            if doctor_id:
                query["doctor_id"] = doctor_id

        if department_id:
            query["department_id"] = department_id
        if status:
            query["status"] = status.value if hasattr(status, "value") else str(status)

        if date_from or date_to:
            date_query: Dict[str, Any] = {}
            if date_from:
                date_query["$gte"] = date_from
            if date_to:
                date_query["$lte"] = date_to
            query["appointment_date"] = date_query

        skip = (page - 1) * page_size
        total = await db[COLLECTION_APPOINTMENTS].count_documents(query)
        cursor = db[COLLECTION_APPOINTMENTS].find(query).sort([("appointment_date", -1), ("start_time", 1)]).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)

        # Batch-populate patient names where missing
        pids = list({d.get("patient_id") for d in docs if d.get("patient_id") and not d.get("patient_name")})
        patient_map = {}
        if pids:
            try:
                p_cursor = db[COLLECTION_PATIENTS].find({"patient_id": {"$in": pids}})
                if hasattr(p_cursor, "to_list"):
                    p_list = await p_cursor.to_list(length=len(pids))
                else:
                    p_list = [p for p in p_cursor]
                for p in p_list:
                    patient_map[p["patient_id"]] = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            except Exception:
                pass

        for doc in docs:
            doc.pop("_id", None)
            if not doc.get("patient_name") and doc.get("patient_id") in patient_map:
                doc["patient_name"] = patient_map[doc["patient_id"]]
            if not doc.get("start_time"):
                doc["start_time"] = doc.get("appointment_time", "09:00")
            if not doc.get("end_time"):
                doc["end_time"] = "09:30"
            if not doc.get("appointment_type"):
                doc["appointment_type"] = "new_consultation"
        return docs, total

    @staticmethod
    async def reschedule_appointment(
        db: AsyncIOMotorDatabase,
        appointment_id: str,
        request: RescheduleAppointmentRequest,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Reschedules an existing appointment to a new date/time slot."""
        apt_dict = await AppointmentService._find_by_appointment_id(db, appointment_id)
        current_status = AppointmentStatus(apt_dict["status"])

        if current_status not in RESCHEDULABLE_STATUSES:
            raise AppValidationError(
                f"Appointment '{appointment_id}' in status '{current_status.value}' cannot be rescheduled."
            )

        # Authorization checks
        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient or patient["patient_id"] != apt_dict["patient_id"]:
                raise ForbiddenError("You are not authorized to reschedule this appointment.")
        elif current_user.role == UserRole.DOCTOR:
            doctor = await AppointmentService.get_doctor_for_user(db, current_user)
            if not doctor or doctor["doctor_id"] != apt_dict["doctor_id"]:
                raise ForbiddenError("You are not authorized to reschedule another doctor's appointment.")

        new_date_str = request.appointment_date.isoformat()
        new_start_time = request.start_time

        # Validate slot availability for new date/time
        availability = await DoctorService.calculate_available_slots(db, apt_dict["doctor_id"], new_date_str)
        matched_slot = None
        for slot in availability.available_slots:
            if slot.start_time == new_start_time:
                matched_slot = slot
                break

        if not matched_slot:
            raise AppValidationError(f"Requested new slot '{new_start_time}' on {new_date_str} is not available.")

        # Double booking check (exact match & overlapping interval)
        conflict = await db[COLLECTION_APPOINTMENTS].find_one({
            "doctor_id": apt_dict["doctor_id"],
            "appointment_date": new_date_str,
            "appointment_id": {"$ne": appointment_id},
            "status": {"$nin": [AppointmentStatus.CANCELLED.value, AppointmentStatus.NO_SHOW.value]},
            "start_time": {"$lt": matched_slot.end_time},
            "$or": [
                {"end_time": {"$gt": new_start_time}},
                {"end_time": {"$exists": False}, "start_time": new_start_time},
            ]
        })
        if conflict:
            raise ResourceConflictError(f"New slot '{new_start_time}' on {new_date_str} is already booked.")

        # Record reschedule history
        history_entry = RescheduleRecord(
            previous_date=apt_dict["appointment_date"],
            previous_start_time=apt_dict["start_time"],
            previous_end_time=apt_dict["end_time"],
            rescheduled_by=current_user.user_id,
            rescheduled_by_role=current_user.role.value,
            rescheduled_at=utc_now(),
        ).model_dump()

        now = utc_now()
        try:
            await db[COLLECTION_APPOINTMENTS].update_one(
                {"appointment_id": appointment_id},
                {
                    "$set": {
                        "appointment_date": new_date_str,
                        "start_time": new_start_time,
                        "end_time": matched_slot.end_time,
                        "updated_at": now,
                    },
                    "$push": {"reschedule_history": history_entry}
                }
            )
        except DuplicateKeyError:
            raise ResourceConflictError(f"New slot '{new_start_time}' on {new_date_str} is already booked.")
        logger.info(f"Rescheduled appointment {appointment_id} to {new_date_str} {new_start_time} by {current_user.user_id}")

        try:
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType
            pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": apt_dict["patient_id"]})
            doc = await db[COLLECTION_DOCTORS].find_one({"doctor_id": apt_dict["doctor_id"]})
            if pat and pat.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=pat["user_id"],
                    notification_type=NotificationType.APPOINTMENT_RESCHEDULED,
                    title="Appointment Rescheduled",
                    body=f"Your appointment {appointment_id} is rescheduled to {new_date_str} at {new_start_time}.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_rescheduled:{appointment_id}:{new_date_str}:{new_start_time}:{pat['user_id']}",
                )
            if doc and doc.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=doc["user_id"],
                    notification_type=NotificationType.APPOINTMENT_RESCHEDULED,
                    title="Appointment Rescheduled",
                    body=f"Appointment {appointment_id} for patient {apt_dict['patient_id']} is moved to {new_date_str} at {new_start_time}.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_rescheduled:{appointment_id}:{new_date_str}:{new_start_time}:{doc['user_id']}",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch reschedule notification for {appointment_id}: {exc}")

        return await AppointmentService._find_by_appointment_id(db, appointment_id)

    @staticmethod
    async def cancel_appointment(
        db: AsyncIOMotorDatabase,
        appointment_id: str,
        request: CancelAppointmentRequest,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Cancels an appointment."""
        apt_dict = await AppointmentService._find_by_appointment_id(db, appointment_id)
        current_status = AppointmentStatus(apt_dict["status"])

        if current_status not in CANCELLABLE_STATUSES:
            raise AppValidationError(
                f"Appointment '{appointment_id}' in status '{current_status.value}' cannot be cancelled."
            )

        # Authorization checks
        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient or patient["patient_id"] != apt_dict["patient_id"]:
                raise ForbiddenError("You are not authorized to cancel this appointment.")
        elif current_user.role == UserRole.DOCTOR:
            doctor = await AppointmentService.get_doctor_for_user(db, current_user)
            if not doctor or doctor["doctor_id"] != apt_dict["doctor_id"]:
                raise ForbiddenError("You are not authorized to cancel another doctor's appointment.")

        cancellation_data = CancellationData(
            cancelled_by=current_user.user_id,
            cancelled_by_role=current_user.role.value,
            reason=request.reason,
            cancelled_at=utc_now(),
        ).model_dump()

        now = utc_now()
        res = await db[COLLECTION_APPOINTMENTS].update_one(
            {
                "appointment_id": appointment_id,
                "status": {"$in": [s.value for s in CANCELLABLE_STATUSES]},
            },
            {
                "$set": {
                    "status": AppointmentStatus.CANCELLED.value,
                    "cancellation": cancellation_data,
                    "updated_at": now,
                }
            }
        )

        if res.matched_count == 0:
            fresh_apt = await AppointmentService._find_by_appointment_id(db, appointment_id)
            if fresh_apt["status"] == AppointmentStatus.CANCELLED.value:
                return fresh_apt
            raise ResourceConflictError(
                f"Appointment '{appointment_id}' in status '{fresh_apt['status']}' cannot be cancelled."
            )

        logger.info(f"Cancelled appointment {appointment_id} by {current_user.user_id}")

        try:
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType
            pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": apt_dict["patient_id"]})
            doc = await db[COLLECTION_DOCTORS].find_one({"doctor_id": apt_dict["doctor_id"]})
            if pat and pat.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=pat["user_id"],
                    notification_type=NotificationType.APPOINTMENT_CANCELLED,
                    title="Appointment Cancelled",
                    body=f"Your appointment {appointment_id} has been cancelled. Reason: {request.reason or 'User cancelled'}.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_cancelled:{appointment_id}:{pat['user_id']}",
                )
            if doc and doc.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=doc["user_id"],
                    notification_type=NotificationType.APPOINTMENT_CANCELLED,
                    title="Appointment Cancelled",
                    body=f"Appointment {appointment_id} for patient {apt_dict['patient_id']} has been cancelled.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_cancelled:{appointment_id}:{doc['user_id']}",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch cancellation notification for {appointment_id}: {exc}")

        return await AppointmentService._find_by_appointment_id(db, appointment_id)

    @staticmethod
    async def check_in_patient(
        db: AsyncIOMotorDatabase,
        appointment_id: str,
        request: CheckInRequest,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Performs patient check-in for an appointment, generating daily queue token and joining queue."""
        apt_dict = await AppointmentService._find_by_appointment_id(db, appointment_id)
        current_status = AppointmentStatus(apt_dict["status"])

        if current_status in TERMINAL_STATUSES:
            raise AppValidationError(f"Cannot check in. Appointment is in terminal state '{current_status.value}'.")
        if current_status in (AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_QUEUE, AppointmentStatus.IN_CONSULTATION):
            raise ResourceConflictError("Patient is already checked in or in queue.")

        today_local = datetime.now().date().isoformat()
        today_utc = utc_now().date().isoformat()
        apt_date = apt_dict["appointment_date"]
        if apt_date not in (today_local, today_utc):
            raise AppValidationError(
                f"Check-in is only allowed on the scheduled date ({apt_date}). Today is {today_local}."
            )

        # Count checked-in/in_queue appointments for doctor today to calculate queue token and position safely
        count = await db[COLLECTION_APPOINTMENTS].count_documents({
            "doctor_id": apt_dict["doctor_id"],
            "appointment_date": apt_date,
            "status": {"$in": [AppointmentStatus.CHECKED_IN.value, AppointmentStatus.IN_QUEUE.value, AppointmentStatus.IN_CONSULTATION.value, AppointmentStatus.COMPLETED.value]}
        })
        sequence = count + 1
        token_number = generate_queue_token(sequence, prefix="A")

        now = utc_now()
        check_in_data = CheckInData(
            checked_in_at=now,
            checked_in_by=current_user.user_id,
            method=request.method,
        ).model_dump()

        queue_data = QueueData(
            token_number=token_number,
            position=sequence,
            joined_at=now,
        ).model_dump()

        update_result = await db[COLLECTION_APPOINTMENTS].update_one(
            {
                "appointment_id": appointment_id,
                "status": {"$in": [AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value]}
            },
            {
                "$set": {
                    "status": AppointmentStatus.IN_QUEUE.value,
                    "check_in": check_in_data,
                    "queue": queue_data,
                    "updated_at": now,
                }
            }
        )
        if update_result.matched_count == 0:
            raise ResourceConflictError("Patient is already checked in, in queue, or in terminal state.")

        logger.info(f"Checked in appointment {appointment_id}. Token: {token_number}, Queue position: {sequence}")

        # Record persistent audit event for check-in
        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
                action="appointment_check_in",
                resource="appointment",
                resource_id=appointment_id,
                metadata={"token_number": token_number, "position": sequence, "method": request.method}
            )
        except Exception as exc:
            logger.warning(f"Failed to record audit log for check-in {appointment_id}: {exc}")

        try:
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType
            pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": apt_dict["patient_id"]})
            doc = await db[COLLECTION_DOCTORS].find_one({"doctor_id": apt_dict["doctor_id"]})
            if pat and pat.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=pat["user_id"],
                    notification_type=NotificationType.CHECKIN_SUCCESS,
                    title="Check-In Successful",
                    body=f"You are checked in for appointment {appointment_id}. Queue Token: {token_number}, Position: {sequence}.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_checked_in:{appointment_id}:{pat['user_id']}",
                )
            if doc and doc.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=doc["user_id"],
                    notification_type=NotificationType.APPOINTMENT_CHECKED_IN,
                    title="Patient Checked In",
                    body=f"Patient {apt_dict['patient_id']} has checked in for appointment {appointment_id}. Token: {token_number}.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_checked_in:{appointment_id}:{doc['user_id']}",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch check-in notification for {appointment_id}: {exc}")

        return await AppointmentService._find_by_appointment_id(db, appointment_id)

    @staticmethod
    async def get_queue(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        doctor_id: Optional[str] = None,
        department_id: Optional[str] = None,
        target_date_str: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves active patient queue for a doctor/department on target date."""
        today_str = target_date_str or utc_now().date().isoformat()
        query: Dict[str, Any] = {
            "appointment_date": today_str,
            "status": {"$in": [AppointmentStatus.CHECKED_IN.value, AppointmentStatus.IN_QUEUE.value, AppointmentStatus.IN_CONSULTATION.value]}
        }

        if current_user.role == UserRole.DOCTOR:
            doctor = await AppointmentService.get_doctor_for_user(db, current_user)
            if doctor:
                if doctor_id and doctor_id != doctor["doctor_id"]:
                    raise ForbiddenError("Doctors can only access their own queue.")
                query["doctor_id"] = doctor["doctor_id"]
            else:
                return []
        elif doctor_id:
            query["doctor_id"] = doctor_id

        if department_id:
            query["department_id"] = department_id

        cursor = db[COLLECTION_APPOINTMENTS].find(query).sort("queue.position", 1)
        return await cursor.to_list(length=500)

    @staticmethod
    async def get_patient_queue_position(
        db: AsyncIOMotorDatabase, appointment_id: str, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Calculates current queue position for a patient's checked-in appointment."""
        apt_dict = await AppointmentService._find_by_appointment_id(db, appointment_id)
        
        if current_user.role == UserRole.PATIENT:
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient or patient["patient_id"] != apt_dict["patient_id"]:
                raise ForbiddenError("Access denied.")

        if apt_dict["status"] not in (AppointmentStatus.CHECKED_IN.value, AppointmentStatus.IN_QUEUE.value):
            return {
                "appointment_id": appointment_id,
                "status": apt_dict["status"],
                "token_number": apt_dict.get("queue", {}).get("token_number"),
                "patients_ahead": 0,
                "current_position": apt_dict.get("queue", {}).get("position"),
            }

        # Count patients ahead in the same doctor queue today with earlier position
        pos = apt_dict.get("queue", {}).get("position", 1)
        ahead = await db[COLLECTION_APPOINTMENTS].count_documents({
            "doctor_id": apt_dict["doctor_id"],
            "appointment_date": apt_dict["appointment_date"],
            "status": {"$in": [AppointmentStatus.CHECKED_IN.value, AppointmentStatus.IN_QUEUE.value]},
            "queue.position": {"$lt": pos}
        })

        return {
            "appointment_id": appointment_id,
            "status": apt_dict["status"],
            "token_number": apt_dict.get("queue", {}).get("token_number"),
            "patients_ahead": ahead,
            "current_position": pos,
        }

    @staticmethod
    async def call_next_patient(
        db: AsyncIOMotorDatabase, appointment_id: str, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Advances appointment status from queue into consultation prep / call stage."""
        apt_dict = await AppointmentService._find_by_appointment_id(db, appointment_id)
        current_status = AppointmentStatus(apt_dict["status"])

        if current_status not in (AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_QUEUE):
            raise AppValidationError(f"Cannot call patient in status '{current_status.value}'.")

        now = utc_now()
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
        logger.info(f"Called patient for appointment {appointment_id} into consultation by {current_user.user_id}")

        # Record persistent audit event for calling patient
        try:
            from app.services.audit_service import log_audit_event
            await log_audit_event(
                db=db,
                actor_id=current_user.user_id,
                role=current_user.role.value if hasattr(current_user.role, 'value') else str(current_user.role),
                action="appointment_called",
                resource="appointment",
                resource_id=appointment_id,
                metadata={"status": AppointmentStatus.IN_CONSULTATION.value}
            )
        except Exception as exc:
            logger.warning(f"Failed to record audit log for calling patient {appointment_id}: {exc}")

        try:
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType
            pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": apt_dict["patient_id"]})
            if pat and pat.get("user_id"):
                token = apt_dict.get("queue", {}).get("token_number", "")
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=pat["user_id"],
                    notification_type=NotificationType.CONSULTATION_STARTED,
                    title="You Are Being Called",
                    body=f"Doctor is ready for your appointment (Token: {token}). Please proceed to the consultation room.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_called:{appointment_id}:{pat['user_id']}",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch call notification for {appointment_id}: {exc}")

        return await AppointmentService._find_by_appointment_id(db, appointment_id)

    @staticmethod
    async def confirm_appointment(
        db: AsyncIOMotorDatabase, appointment_id: str, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Confirms a scheduled appointment (Doctor, Staff, Admin)."""
        apt_dict = await AppointmentService._find_by_appointment_id(db, appointment_id)
        current_status = AppointmentStatus(apt_dict["status"])

        if current_status != AppointmentStatus.SCHEDULED:
            if current_status == AppointmentStatus.CONFIRMED:
                return apt_dict
            raise AppValidationError(f"Cannot confirm appointment in status '{current_status.value}'. Must be 'scheduled'.")

        if current_user.role == UserRole.DOCTOR:
            doctor = await AppointmentService.get_doctor_for_user(db, current_user)
            if not doctor or doctor["doctor_id"] != apt_dict["doctor_id"]:
                raise ForbiddenError("You are not authorized to confirm another doctor's appointment.")

        now = utc_now()
        res = await db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": appointment_id, "status": AppointmentStatus.SCHEDULED.value},
            {
                "$set": {
                    "status": AppointmentStatus.CONFIRMED.value,
                    "updated_at": now,
                }
            }
        )
        if res.matched_count == 0:
            fresh_apt = await AppointmentService._find_by_appointment_id(db, appointment_id)
            if fresh_apt["status"] == AppointmentStatus.CONFIRMED.value:
                return fresh_apt
            raise ResourceConflictError(
                f"Cannot confirm appointment '{appointment_id}' because status is '{fresh_apt['status']}'."
            )
        logger.info(f"Confirmed appointment {appointment_id} by user {current_user.user_id}")

        try:
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType
            pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": apt_dict["patient_id"]})
            if pat and pat.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=pat["user_id"],
                    notification_type=NotificationType.APPOINTMENT_CONFIRMED,
                    title="Appointment Confirmed",
                    body=f"Your appointment {appointment_id} on {apt_dict['appointment_date']} at {apt_dict['start_time']} has been confirmed.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_confirmed:{appointment_id}:{pat['user_id']}",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch confirmation notification for {appointment_id}: {exc}")

        return await AppointmentService._find_by_appointment_id(db, appointment_id)

    @staticmethod
    async def complete_appointment(
        db: AsyncIOMotorDatabase, appointment_id: str, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Completes an active appointment (Doctor, Staff, Admin)."""
        apt_dict = await AppointmentService._find_by_appointment_id(db, appointment_id)
        current_status = AppointmentStatus(apt_dict["status"])

        if current_status == AppointmentStatus.COMPLETED:
            return apt_dict
        if current_status in TERMINAL_STATUSES:
            raise AppValidationError(f"Cannot complete appointment in terminal status '{current_status.value}'.")

        if current_user.role == UserRole.DOCTOR:
            doctor = await AppointmentService.get_doctor_for_user(db, current_user)
            if not doctor or doctor["doctor_id"] != apt_dict["doctor_id"]:
                raise ForbiddenError("You are not authorized to complete another doctor's appointment.")

        now = utc_now()
        res = await db[COLLECTION_APPOINTMENTS].update_one(
            {
                "appointment_id": appointment_id,
                "status": {"$nin": [s.value for s in TERMINAL_STATUSES]},
            },
            {
                "$set": {
                    "status": AppointmentStatus.COMPLETED.value,
                    "queue.completed_at": now,
                    "updated_at": now,
                }
            }
        )
        if res.matched_count == 0:
            fresh_apt = await AppointmentService._find_by_appointment_id(db, appointment_id)
            if fresh_apt["status"] == AppointmentStatus.COMPLETED.value:
                return fresh_apt
            raise ResourceConflictError(
                f"Appointment '{appointment_id}' cannot be completed because status is '{fresh_apt['status']}'."
            )
        logger.info(f"Completed appointment {appointment_id} by user {current_user.user_id}")

        try:
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType
            pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": apt_dict["patient_id"]})
            if pat and pat.get("user_id"):
                await NotificationService.dispatch(
                    db=db,
                    recipient_user_id=pat["user_id"],
                    notification_type=NotificationType.APPOINTMENT_COMPLETED,
                    title="Appointment Completed",
                    body=f"Your appointment {appointment_id} has been completed.",
                    reference_id=appointment_id,
                    reference_type="appointment",
                    dedupe_key=f"appointment_completed:{appointment_id}:{pat['user_id']}",
                )
        except Exception as exc:
            logger.warning(f"Failed to dispatch completion notification for {appointment_id}: {exc}")

        return await AppointmentService._find_by_appointment_id(db, appointment_id)

    @staticmethod
    async def update_status(
        db: AsyncIOMotorDatabase, appointment_id: str, new_status: AppointmentStatus, current_user: UserInDB
    ) -> Dict[str, Any]:
        """Generic validated status transition endpoint enforcing centralized state machine."""
        apt_dict = await AppointmentService._find_by_appointment_id(db, appointment_id)
        current_status = AppointmentStatus(apt_dict["status"])

        if current_status == new_status:
            return apt_dict

        allowed_targets = VALID_STATUS_TRANSITIONS.get(current_status, [])
        if new_status not in allowed_targets:
            raise AppValidationError(
                f"Invalid status transition from '{current_status.value}' to '{new_status.value}'. Allowed: {[s.value for s in allowed_targets]}"
            )

        if current_user.role == UserRole.PATIENT:
            if new_status != AppointmentStatus.CANCELLED:
                raise ForbiddenError("Patients can only cancel appointments.")
            patient = await db[COLLECTION_PATIENTS].find_one({"user_id": current_user.user_id})
            if not patient or patient["patient_id"] != apt_dict["patient_id"]:
                raise ForbiddenError("You are not authorized to modify this appointment.")
        elif current_user.role == UserRole.DOCTOR:
            doctor = await AppointmentService.get_doctor_for_user(db, current_user)
            if not doctor or doctor["doctor_id"] != apt_dict["doctor_id"]:
                raise ForbiddenError("You are not authorized to modify another doctor's appointment.")

        now = utc_now()
        update_doc: Dict[str, Any] = {"status": new_status.value, "updated_at": now}
        if new_status == AppointmentStatus.COMPLETED:
            update_doc["queue.completed_at"] = now
        elif new_status == AppointmentStatus.IN_CONSULTATION:
            update_doc["queue.called_at"] = now

        await db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": appointment_id},
            {"$set": update_doc}
        )
        logger.info(f"Updated status of appointment {appointment_id} to '{new_status.value}' by {current_user.user_id}")

        if new_status == AppointmentStatus.NO_SHOW:
            try:
                from app.services.notification_service import NotificationService
                from app.models.notification import NotificationType
                pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": apt_dict["patient_id"]})
                if pat and pat.get("user_id"):
                    await NotificationService.dispatch(
                        db=db,
                        recipient_user_id=pat["user_id"],
                        notification_type=NotificationType.APPOINTMENT_NO_SHOW,
                        title="Appointment Marked No-Show",
                        body=f"Your appointment {appointment_id} on {apt_dict.get('appointment_date')} was marked as no-show.",
                        reference_id=appointment_id,
                        reference_type="appointment",
                        dedupe_key=f"appointment_no_show:{appointment_id}:{pat['user_id']}",
                    )
            except Exception as exc:
                logger.warning(f"Failed to dispatch no-show notification for {appointment_id}: {exc}")

        return await AppointmentService._find_by_appointment_id(db, appointment_id)

