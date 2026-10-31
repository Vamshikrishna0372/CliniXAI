"""Hospital Staff management business logic service."""

from datetime import timedelta
from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import ResourceNotFoundError, ResourceConflictError
from app.database.collections import (
    COLLECTION_STAFF, COLLECTION_USERS, COLLECTION_DEPARTMENTS,
    COLLECTION_APPOINTMENTS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_BILLING, COLLECTION_PAYMENTS, COLLECTION_AUDIT_LOGS,
    COLLECTION_CONSULTATIONS
)
from app.models.staff import StaffInDB, StaffStatus
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.schemas.staff import CreateStaffRequest, UpdateStaffRequest
from app.utils.id_generator import generate_staff_id, generate_user_id
from app.utils.datetime import utc_now
from app.utils.tokens import generate_secure_token, hash_token


class StaffService:
    """Business logic for Hospital Staff profile management."""

    @staticmethod
    async def _find_by_staff_id(db: AsyncIOMotorDatabase, staff_id: str) -> Dict[str, Any]:
        doc = await db[COLLECTION_STAFF].find_one({"staff_id": staff_id})
        if not doc:
            raise ResourceNotFoundError("Hospital Staff", staff_id)
        return doc

    @staticmethod
    async def create_staff(
        db: AsyncIOMotorDatabase,
        request: CreateStaffRequest,
        admin_user_id: str,
    ) -> Tuple[StaffInDB, str]:
        """Admin provisions a new Hospital Staff profile and linked User account."""
        email = request.email.lower().strip()

        existing_user = await db[COLLECTION_USERS].find_one({"email": email})
        if existing_user:
            raise ResourceConflictError(f"Account with email '{email}' already exists.")

        if request.department_id:
            dept = await db[COLLECTION_DEPARTMENTS].find_one({"department_id": request.department_id})
            if not dept:
                raise ResourceNotFoundError("Department", request.department_id)

        user_id = generate_user_id()
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = utc_now() + timedelta(days=7)

        # User document
        user_doc = UserInDB(
            user_id=user_id,
            email=email,
            full_name=request.full_name,
            password_hash=None,
            role=UserRole.HOSPITAL_STAFF,
            auth_provider=AuthProvider.LOCAL,
            email_verified=False,
            account_status=AccountStatus.ACTIVE,
            invitation_token_hash=token_hash,
            invitation_expires_at=expires_at,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        await db[COLLECTION_USERS].insert_one(user_doc.to_mongo_dict())

        # Staff document
        staff_id = generate_staff_id()
        staff_doc = StaffInDB(
            staff_id=staff_id,
            user_id=user_id,
            first_name=request.first_name,
            last_name=request.last_name,
            email=email,
            phone=request.phone,
            department_id=request.department_id,
            job_title=request.job_title,
            employee_number=request.employee_number,
            status=StaffStatus.ACTIVE,
            created_by=admin_user_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        await db[COLLECTION_STAFF].insert_one(staff_doc.to_mongo_dict())
        logger.info(f"Staff provisioned: staff_id={staff_id}, user_id={user_id} by admin={admin_user_id}")

        # Dispatch SMTP invitation email
        from app.services.email_service import EmailService
        activation_url = f"http://localhost:5173/accept-invitation?token={raw_token}"
        await EmailService.send_invitation_email(
            to_email=email,
            recipient_name=request.full_name,
            role_name="Hospital Staff",
            activation_url=activation_url,
        )

        return staff_doc, raw_token

    @staticmethod
    async def get_staff_by_id(db: AsyncIOMotorDatabase, staff_id: str) -> Dict[str, Any]:
        return await StaffService._find_by_staff_id(db, staff_id)

    @staticmethod
    async def get_staff_by_user_id(db: AsyncIOMotorDatabase, user_id: str) -> Optional[Dict[str, Any]]:
        return await db[COLLECTION_STAFF].find_one({"user_id": user_id})

    @staticmethod
    async def update_staff(
        db: AsyncIOMotorDatabase,
        staff_id: str,
        request: UpdateStaffRequest,
        updater_user_id: str,
    ) -> Dict[str, Any]:
        """Update staff profile details."""
        await StaffService._find_by_staff_id(db, staff_id)

        if request.department_id:
            dept = await db[COLLECTION_DEPARTMENTS].find_one({"department_id": request.department_id})
            if not dept:
                raise ResourceNotFoundError("Department", request.department_id)

        updates: Dict[str, Any] = {}
        data = request.model_dump(exclude_none=True)
        for field, value in data.items():
            if isinstance(value, StaffStatus):
                updates[field] = value.value
            else:
                updates[field] = value

        if updates:
            updates["updated_at"] = utc_now()
            await db[COLLECTION_STAFF].update_one(
                {"staff_id": staff_id}, {"$set": updates}
            )
            if "status" in updates:
                staff_doc = await StaffService._find_by_staff_id(db, staff_id)
                user_status = AccountStatus.SUSPENDED.value if updates["status"] == StaffStatus.INACTIVE.value else AccountStatus.ACTIVE.value
                await db[COLLECTION_USERS].update_one(
                    {"user_id": staff_doc["user_id"]},
                    {"$set": {"account_status": user_status, "updated_at": utc_now()}}
                )
            logger.info(f"Staff {staff_id} updated by {updater_user_id}")

        return await StaffService._find_by_staff_id(db, staff_id)

    @staticmethod
    async def list_staff(
        db: AsyncIOMotorDatabase,
        page: int = 1,
        page_size: int = 20,
        department_id: Optional[str] = None,
        status: Optional[StaffStatus] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Paginated staff list."""
        query: Dict[str, Any] = {}
        if department_id:
            query["department_id"] = department_id
        if status:
            query["status"] = status.value

        if search:
            search_regex = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"staff_id": search_regex},
                {"first_name": search_regex},
                {"last_name": search_regex},
                {"email": search_regex},
                {"job_title": search_regex},
            ]

        skip = (page - 1) * page_size
        total = await db[COLLECTION_STAFF].count_documents(query)
        cursor = db[COLLECTION_STAFF].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return docs, total

    @staticmethod
    async def get_operational_dashboard(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Aggregates real-time hospital operational metrics for today's staff dashboard."""
        today_str = utc_now().date().isoformat()

        # 1. Appointments counts today
        today_apts = await db[COLLECTION_APPOINTMENTS].find({
            "appointment_date": today_str,
            "is_deleted": {"$ne": True},
        }).to_list(length=1000)

        today_appointments_count = len([a for a in today_apts if a.get("status") != "cancelled"])
        waiting_count = len([a for a in today_apts if a.get("status") in ("checked_in", "in_queue")])
        checked_in_count = len([a for a in today_apts if a.get("status") in ("checked_in", "in_queue", "in_consultation", "completed")])
        completed_count = len([a for a in today_apts if a.get("status") == "completed"])
        total_registered_patients = await db[COLLECTION_PATIENTS].count_documents({"is_deleted": {"$ne": True}})

        # 2. Billing & collections today
        pending_bills_count = await db[COLLECTION_BILLING].count_documents({
            "status": {"$in": ["draft", "issued", "partially_paid"]},
            "is_deleted": {"$ne": True},
        })

        payments_cursor = db[COLLECTION_PAYMENTS].find({
            "status": {"$in": ["completed", "recorded"]},
            "$or": [
                {"paid_at": {"$regex": f"^{today_str}"}},
                {"recorded_at": {"$regex": f"^{today_str}"}},
            ],
        })
        today_payments = await payments_cursor.to_list(length=1000)
        today_collected_amount = round(sum(p.get("amount", 0.0) for p in today_payments), 2)

        # 3. Upcoming appointments today (scheduled or confirmed, sorted by start_time)
        upcoming_raw = [a for a in today_apts if a.get("status") in ("scheduled", "confirmed", "checked_in")]
        upcoming_raw.sort(key=lambda x: x.get("start_time", ""))

        upcoming_list = []
        for a in upcoming_raw[:10]:
            pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": a.get("patient_id")}) or {}
            doc = await db[COLLECTION_DOCTORS].find_one({"doctor_id": a.get("doctor_id")}) or {}
            upcoming_list.append({
                "appointment_id": a.get("appointment_id"),
                "patient_id": a.get("patient_id"),
                "patient_name": f"{pat.get('first_name', '')} {pat.get('last_name', '')}".strip() or "Patient",
                "doctor_id": a.get("doctor_id"),
                "doctor_name": f"Dr. {doc.get('first_name', '')} {doc.get('last_name', '')}".strip() or "Doctor",
                "appointment_date": a.get("appointment_date"),
                "start_time": a.get("start_time"),
                "status": a.get("status"),
                "reason": a.get("reason"),
            })

        # 4. Active Queue for today
        queue_raw = [a for a in today_apts if a.get("status") in ("checked_in", "in_queue", "in_consultation")]
        queue_raw.sort(key=lambda x: x.get("queue", {}).get("position", 999))
        queue_list = []
        for q in queue_raw:
            pat = await db[COLLECTION_PATIENTS].find_one({"patient_id": q.get("patient_id")}) or {}
            doc = await db[COLLECTION_DOCTORS].find_one({"doctor_id": q.get("doctor_id")}) or {}
            queue_list.append({
                "appointment_id": q.get("appointment_id"),
                "token_number": q.get("queue", {}).get("token_number"),
                "position": q.get("queue", {}).get("position"),
                "patient_id": q.get("patient_id"),
                "patient_name": f"{pat.get('first_name', '')} {pat.get('last_name', '')}".strip() or "Patient",
                "doctor_id": q.get("doctor_id"),
                "doctor_name": f"Dr. {doc.get('first_name', '')} {doc.get('last_name', '')}".strip() or "Doctor",
                "status": q.get("status"),
                "checked_in_at": q.get("check_in", {}).get("checked_in_at"),
                "called_at": q.get("queue", {}).get("called_at"),
            })

        # 5. Operational Alerts
        alerts = []
        if waiting_count > 5:
            alerts.append({
                "severity": "warning",
                "message": f"{waiting_count} patients currently waiting in queue. Consider coordinating with doctors.",
            })
        if pending_bills_count > 10:
            alerts.append({
                "severity": "info",
                "message": f"{pending_bills_count} bills pending payment/issuance.",
            })

        # 6. Recent activity from audit logs
        activity_cursor = db[COLLECTION_AUDIT_LOGS].find({}).sort("timestamp", -1).limit(10)
        recent_activity = await activity_cursor.to_list(length=10)
        clean_activity = []
        for act in recent_activity:
            clean_activity.append({
                "action": act.get("action"),
                "resource": act.get("resource"),
                "resource_id": act.get("resource_id"),
                "actor_id": act.get("actor_id"),
                "timestamp": str(act.get("timestamp")),
            })

        return {
            "metrics": {
                "today_appointments": today_appointments_count,
                "waiting_patients": waiting_count,
                "checked_in_today": checked_in_count,
                "completed_consultations": completed_count,
                "pending_bills": pending_bills_count,
                "today_collected_amount": today_collected_amount,
                "total_registered_patients": total_registered_patients,
            },
            "upcoming_appointments": upcoming_list,
            "active_queue": queue_list,
            "recent_activity": clean_activity,
            "operational_alerts": alerts,
        }

