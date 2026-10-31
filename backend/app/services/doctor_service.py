"""Doctor management and availability business logic service."""

import re
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import (
    ResourceNotFoundError, ResourceConflictError, AppValidationError
)
from app.database.collections import (
    COLLECTION_DOCTORS, COLLECTION_USERS, COLLECTION_APPOINTMENTS, COLLECTION_DEPARTMENTS
)
from app.models.doctor import (
    DoctorInDB, DoctorStatus, DoctorSchedule, DaySchedule, TimeSlotBlock, DayOfWeek
)
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.schemas.doctors import (
    CreateDoctorRequest, UpdateDoctorRequest, UpdateDoctorScheduleRequest,
    AvailableSlot, DoctorAvailabilityResponse
)
from app.utils.id_generator import generate_doctor_id, generate_user_id
from app.utils.datetime import utc_now
from app.utils.tokens import generate_secure_token, hash_token


class DoctorService:
    """Business logic for Doctor profile, schedule management, and dynamic slot availability calculation."""

    # Fields that cannot be mutated by self/update endpoints
    _PROTECTED_FIELDS = {"doctor_id", "user_id", "created_at", "created_by", "_id"}

    @staticmethod
    async def _find_by_doctor_id(db: AsyncIOMotorDatabase, doctor_id: str) -> Dict[str, Any]:
        doc = await db[COLLECTION_DOCTORS].find_one({
            "doctor_id": doctor_id,
            "is_deleted": {"$ne": True}
        })
        if not doc:
            raise ResourceNotFoundError("Doctor", doctor_id)
        return doc

    @staticmethod
    async def create_doctor(
        db: AsyncIOMotorDatabase,
        request: CreateDoctorRequest,
        admin_user_id: str,
    ) -> Tuple[DoctorInDB, str]:
        """Admin creates a Doctor profile and associated User account/invitation.

        Reuses Phase 2 architecture for invitation token hashing.
        """
        email = request.email.lower().strip()

        # Check existing user
        existing_user = await db[COLLECTION_USERS].find_one({"email": email})
        if existing_user:
            raise ResourceConflictError(f"Account with email '{email}' already exists.")

        # Validate department if provided
        if request.department_id:
            dept = await db[COLLECTION_DEPARTMENTS].find_one({"department_id": request.department_id})
            if not dept:
                raise ResourceNotFoundError("Department", request.department_id)

        user_id = generate_user_id()
        raw_invitation_token = generate_secure_token()
        token_hash = hash_token(raw_invitation_token)
        invitation_expires_at = utc_now() + timedelta(days=7)

        # Create user account
        user_doc = UserInDB(
            user_id=user_id,
            email=email,
            full_name=request.full_name,
            password_hash=None,
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            email_verified=False,
            account_status=AccountStatus.ACTIVE,
            invitation_token_hash=token_hash,
            invitation_expires_at=invitation_expires_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        await db[COLLECTION_USERS].insert_one(user_doc.to_mongo_dict())

        # Create doctor profile
        doctor_id = generate_doctor_id()
        # Default empty weekly schedule for all 7 days
        default_weekly = [
            DaySchedule(day=day, is_available=(day not in [DayOfWeek.SATURDAY, DayOfWeek.SUNDAY]),
                        slots=[TimeSlotBlock(start="09:00", end="13:00"), TimeSlotBlock(start="14:00", end="17:00")] if day not in [DayOfWeek.SATURDAY, DayOfWeek.SUNDAY] else [])
            for day in DayOfWeek
        ]
        schedule = DoctorSchedule(slot_duration_minutes=30, weekly=default_weekly)

        doctor_doc = DoctorInDB(
            doctor_id=doctor_id,
            user_id=user_id,
            first_name=request.first_name,
            last_name=request.last_name,
            email=email,
            phone=request.phone,
            department_id=request.department_id,
            specialization=request.specialization,
            qualification=request.qualification,
            experience_years=request.experience_years,
            registration_number=request.registration_number,
            consultation_fee=request.consultation_fee,
            schedule=schedule,
            status=DoctorStatus.ACTIVE,
            created_by=admin_user_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        await db[COLLECTION_DOCTORS].insert_one(doctor_doc.to_mongo_dict())
        logger.info(f"Doctor provisioned: doctor_id={doctor_id}, user_id={user_id} by admin={admin_user_id}")

        # Dispatch SMTP invitation email
        from app.services.email_service import EmailService
        activation_url = f"http://localhost:5173/accept-invitation?token={raw_invitation_token}"
        await EmailService.send_invitation_email(
            to_email=email,
            recipient_name=request.full_name,
            role_name="Doctor",
            activation_url=activation_url,
        )

        return doctor_doc, raw_invitation_token

    @staticmethod
    async def get_doctor_by_id(db: AsyncIOMotorDatabase, doctor_id: str) -> Dict[str, Any]:
        return await DoctorService._find_by_doctor_id(db, doctor_id)

    @staticmethod
    async def get_doctor_by_user_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[Dict[str, Any]]:
        return await db[COLLECTION_DOCTORS].find_one({"user_id": user_id})

    @staticmethod
    async def update_doctor(
        db: AsyncIOMotorDatabase,
        doctor_id: str,
        request: UpdateDoctorRequest,
        updater_user_id: str,
    ) -> Dict[str, Any]:
        """Update doctor profile details."""
        await DoctorService._find_by_doctor_id(db, doctor_id)

        if request.department_id:
            dept = await db[COLLECTION_DEPARTMENTS].find_one({"department_id": request.department_id})
            if not dept:
                raise ResourceNotFoundError("Department", request.department_id)

        updates: Dict[str, Any] = {}
        data = request.model_dump(exclude_none=True)
        for field, value in data.items():
            if field in DoctorService._PROTECTED_FIELDS:
                continue
            if isinstance(value, DoctorStatus):
                updates[field] = value.value
            else:
                updates[field] = value

        if updates:
            updates["updated_at"] = utc_now()
            await db[COLLECTION_DOCTORS].update_one(
                {"doctor_id": doctor_id}, {"$set": updates}
            )
            if "status" in updates:
                doc_record = await DoctorService._find_by_doctor_id(db, doctor_id)
                user_status = AccountStatus.SUSPENDED.value if updates["status"] == DoctorStatus.INACTIVE.value else AccountStatus.ACTIVE.value
                await db[COLLECTION_USERS].update_one(
                    {"user_id": doc_record["user_id"]},
                    {"$set": {"account_status": user_status, "updated_at": utc_now()}}
                )
            try:
                import asyncio
                from app.database.mongodb import save_in_memory_snapshot
                asyncio.create_task(save_in_memory_snapshot(db))
            except Exception:
                pass
            logger.info(f"Doctor {doctor_id} updated by {updater_user_id}")

        return await DoctorService._find_by_doctor_id(db, doctor_id)

    @staticmethod
    async def update_doctor_schedule(
        db: AsyncIOMotorDatabase,
        doctor_id: str,
        request: UpdateDoctorScheduleRequest,
        updater_user_id: str,
    ) -> Dict[str, Any]:
        """Update doctor's weekly schedule configuration."""
        await DoctorService._find_by_doctor_id(db, doctor_id)
        schedule_dict = request.schedule.model_dump()
        
        await db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": doctor_id},
            {"$set": {"schedule": schedule_dict, "updated_at": utc_now()}}
        )
        logger.info(f"Doctor {doctor_id} schedule updated by {updater_user_id}")
        return await DoctorService._find_by_doctor_id(db, doctor_id)

    @staticmethod
    async def list_doctors(
        db: AsyncIOMotorDatabase,
        page: int = 1,
        page_size: int = 20,
        department_id: Optional[str] = None,
        specialization: Optional[str] = None,
        status: Optional[DoctorStatus] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Paginated, filterable doctor list."""
        query: Dict[str, Any] = {
            "is_deleted": {"$ne": True}
        }
        if department_id:
            query["department_id"] = department_id
        if specialization:
            safe_spec = re.escape(specialization.strip())
            query["specialization"] = {"$regex": safe_spec, "$options": "i"}
        
        # If status is specified use it; otherwise default to active for discovery
        if status:
            query["status"] = status.value
        else:
            query["status"] = DoctorStatus.ACTIVE.value

        if search and search.strip():
            safe_search = re.escape(search.strip())
            search_regex = {"$regex": safe_search, "$options": "i"}
            query["$or"] = [
                {"doctor_id": search_regex},
                {"first_name": search_regex},
                {"last_name": search_regex},
                {"full_name": search_regex},
                {"specialization": search_regex},
                {"email": search_regex},
            ]

        skip = (page - 1) * page_size
        total = await db[COLLECTION_DOCTORS].count_documents(query)
        cursor = db[COLLECTION_DOCTORS].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return docs, total

    @staticmethod
    async def calculate_available_slots(
        db: AsyncIOMotorDatabase,
        doctor_id: str,
        target_date_str: str,
    ) -> DoctorAvailabilityResponse:
        """Dynamically calculates available appointment slots for a given date.

        Slot computation rules:
        - Doctor must exist and be ACTIVE.
        - Date must be parsed and matched against Doctor's weekly schedule for that day of week.
        - Existing booked appointments (not cancelled or no_show) on target date are excluded.
        - Past slots (if target date is today or past) are excluded.
        """
        doctor_dict = await DoctorService._find_by_doctor_id(db, doctor_id)
        doctor = DoctorInDB(**doctor_dict)

        if doctor.status != DoctorStatus.ACTIVE:
            return DoctorAvailabilityResponse(
                doctor_id=doctor_id,
                date=target_date_str,
                slot_duration_minutes=doctor.schedule.slot_duration_minutes,
                available_slots=[],
                total_available=0,
            )

        try:
            target_date = date.fromisoformat(target_date_str)
        except ValueError:
            raise AppValidationError(f"Invalid date format '{target_date_str}'. Expected YYYY-MM-DD.")

        # Determine day of week
        weekday_name = target_date.strftime("%A").lower()  # e.g., "monday"
        
        # Find day schedule
        day_sched = None
        if doctor.schedule and doctor.schedule.weekly:
            for ds in doctor.schedule.weekly:
                day_str = ds.day.value if isinstance(ds.day, DayOfWeek) else str(ds.day).lower()
                if day_str == weekday_name:
                    day_sched = ds
                    break

        # If doctor has no configured schedule or no schedule for this day, return 0 slots
        if not day_sched or not day_sched.is_available:
            return DoctorAvailabilityResponse(
                doctor_id=doctor_id,
                date=target_date_str,
                slot_duration_minutes=doctor.schedule.slot_duration_minutes if doctor.schedule else 30,
                available_slots=[],
                total_available=0,
            )

        slot_duration = doctor.schedule.slot_duration_minutes if doctor.schedule else 30

        # Generate candidate slots from time blocks
        candidate_slots: List[Tuple[str, str]] = []
        for block in day_sched.slots:
            start_parts = [int(x) for x in block.start.split(":")]
            end_parts = [int(x) for x in block.end.split(":")]
            
            curr_minutes = start_parts[0] * 60 + start_parts[1]
            end_minutes = end_parts[0] * 60 + end_parts[1]

            while curr_minutes + slot_duration <= end_minutes:
                s_h, s_m = divmod(curr_minutes, 60)
                e_h, e_m = divmod(curr_minutes + slot_duration, 60)
                slot_start_str = f"{s_h:02d}:{s_m:02d}"
                slot_end_str = f"{e_h:02d}:{e_m:02d}"
                candidate_slots.append((slot_start_str, slot_end_str))
                curr_minutes += slot_duration

        # Fetch existing appointments for this doctor on target date
        existing_apts = await db[COLLECTION_APPOINTMENTS].find({
            "doctor_id": doctor_id,
            "appointment_date": target_date_str,
            "status": {"$nin": ["cancelled", "no_show"]}
        }).to_list(length=1000)

        booked_start_times = {
            apt.get("start_time") or apt.get("appointment_time")
            for apt in existing_apts
            if apt.get("start_time") or apt.get("appointment_time")
        }

        # Filter out booked slots and past slots using local system date/time
        now_local = datetime.now()
        today_local = now_local.date()
        now_time_str = now_local.strftime("%H:%M")

        # If target date is in the past, no slots can be available
        if target_date < today_local:
            return DoctorAvailabilityResponse(
                doctor_id=doctor_id,
                date=target_date_str,
                slot_duration_minutes=slot_duration,
                available_slots=[],
                total_available=0,
            )

        available_slots: List[AvailableSlot] = []
        for start_t, end_t in candidate_slots:
            # Check if booked by any active or completed appointment
            # Interval overlap rule: [start_t, end_t) overlaps with [apt_start, apt_end) iff start_t < apt_end and end_t > apt_start
            is_overlapping = False
            for apt in existing_apts:
                apt_start = apt.get("start_time")
                apt_end = apt.get("end_time") or apt_start
                if apt_start and apt_end:
                    if apt_start == apt_end:
                        if start_t == apt_start:
                            is_overlapping = True
                            break
                    elif start_t < apt_end and end_t > apt_start:
                        is_overlapping = True
                        break
            if is_overlapping:
                continue

            # If target date is today, exclude past slots
            if target_date == today_local and start_t <= now_time_str:
                continue

            available_slots.append(
                AvailableSlot(
                    date=target_date_str,
                    start_time=start_t,
                    end_time=end_t,
                    doctor_id=doctor_id,
                    is_available=True,
                )
            )

        return DoctorAvailabilityResponse(
            doctor_id=doctor_id,
            date=target_date_str,
            slot_duration_minutes=slot_duration,
            available_slots=available_slots,
            total_available=len(available_slots),
        )
