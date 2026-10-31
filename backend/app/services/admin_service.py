"""Hospital Admin Operations Business Logic Service for CliniXAI Phase 19.

Handles:
- Operational Dashboard Aggregations (authoritative MongoDB metrics)
- User Account Lifecycle Management (Active, Disabled, Password Setup Required, Re-invitation)
- Doctor & Staff Account Administration & Status Synchronization
- Patient Operational Oversight & Data Protection
- Administrative Appointment Operations (Search, Cancel)
- Hospital Configuration Settings Management (Persisted, Secrets Protected)
- Operational Multi-Collection Search
"""

import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import (
    ResourceNotFoundError,
    ResourceConflictError,
    AppValidationError,
    ForbiddenError,
)
from app.database.collections import (
    COLLECTION_USERS,
    COLLECTION_PATIENTS,
    COLLECTION_DOCTORS,
    COLLECTION_STAFF,
    COLLECTION_DEPARTMENTS,
    COLLECTION_APPOINTMENTS,
    COLLECTION_CONSULTATIONS,
    COLLECTION_BILLING,
    COLLECTION_AUDIT_LOGS,
    COLLECTION_HOSPITAL_SETTINGS,
    COLLECTION_NOTIFICATIONS,
)
from app.database.indexes import COLLECTION_USER_SESSIONS
from app.models.user import UserInDB, UserRole, AccountStatus
from app.models.doctor import DoctorStatus
from app.models.staff import StaffStatus
from app.models.settings import HospitalSettingsInDB
from app.schemas.admin import (
    AdminUserListItem,
    UpdateHospitalSettingsRequest,
)
from app.services.audit_service import log_audit_event
from app.utils.datetime import utc_now
from app.utils.tokens import generate_secure_token, hash_token


class AdminService:
    """Core administrative business service."""

    # ── 1. Operational Dashboard ─────────────────────────────────────────────

    @staticmethod
    async def get_dashboard_metrics(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
        """Dynamically computes all operational hospital administration metrics from MongoDB."""
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Counts
        total_patients = await db[COLLECTION_PATIENTS].count_documents({"is_deleted": {"$ne": True}})
        active_doctors = await db[COLLECTION_DOCTORS].count_documents({
            "status": DoctorStatus.ACTIVE.value,
            "is_deleted": {"$ne": True}
        })
        total_doctors = await db[COLLECTION_DOCTORS].count_documents({"is_deleted": {"$ne": True}})

        active_staff = await db[COLLECTION_STAFF].count_documents({
            "status": StaffStatus.ACTIVE.value,
            "is_deleted": {"$ne": True}
        })
        total_staff = await db[COLLECTION_STAFF].count_documents({"is_deleted": {"$ne": True}})

        active_users = await db[COLLECTION_USERS].count_documents({
            "account_status": AccountStatus.ACTIVE.value,
            "is_deleted": {"$ne": True}
        })
        disabled_users = await db[COLLECTION_USERS].count_documents({
            "account_status": {"$in": [AccountStatus.DISABLED.value, AccountStatus.SUSPENDED.value]},
            "is_deleted": {"$ne": True}
        })
        pw_setup_users = await db[COLLECTION_USERS].count_documents({
            "$or": [
                {"account_status": AccountStatus.PASSWORD_SETUP_REQUIRED.value},
                {"invitation_token_hash": {"$ne": None}}
            ],
            "is_deleted": {"$ne": True}
        })

        # Today's appointments & status
        today_appointments = await db[COLLECTION_APPOINTMENTS].count_documents({
            "appointment_date": today_str,
            "is_deleted": {"$ne": True}
        })
        waiting_patients = await db[COLLECTION_APPOINTMENTS].count_documents({
            "appointment_date": today_str,
            "status": {"$in": ["checked_in", "in_queue"]},
            "is_deleted": {"$ne": True}
        })
        today_completed_consultations = await db[COLLECTION_CONSULTATIONS].count_documents({
            "status": "completed",
            "is_deleted": {"$ne": True}
        })
        pending_appointments = await db[COLLECTION_APPOINTMENTS].count_documents({
            "status": {"$in": ["scheduled", "confirmed"]},
            "is_deleted": {"$ne": True}
        })
        cancelled_appointments = await db[COLLECTION_APPOINTMENTS].count_documents({
            "status": {"$in": ["cancelled", "no_show"]},
            "is_deleted": {"$ne": True}
        })

        # Billing totals
        pending_bills = await db[COLLECTION_BILLING].count_documents({
            "status": {"$in": ["issued", "partially_paid", "unpaid", "draft"]},
            "is_deleted": {"$ne": True}
        })

        # Aggregate total revenue collected
        billing_cursor = db[COLLECTION_BILLING].find({"is_deleted": {"$ne": True}})
        bills = await billing_cursor.to_list(length=2000)
        collected_revenue = sum(float(b.get("amount_paid", 0.0)) for b in bills)

        # Revenue collected today
        today_revenue = 0.0
        for b in bills:
            # Check payments array
            for p in b.get("payments", []):
                if p.get("status") == "completed":
                    p_date = p.get("created_at") or p.get("payment_date")
                    if p_date and str(p_date).startswith(today_str):
                        today_revenue += float(p.get("amount", 0.0))

        # Recent administrative activity from audit_logs
        recent_activity_cursor = db[COLLECTION_AUDIT_LOGS].find({}).sort("timestamp", -1).limit(6)
        activity_docs = await recent_activity_cursor.to_list(length=6)
        recent_activity = []
        for doc in activity_docs:
            recent_activity.append({
                "audit_id": doc.get("audit_id"),
                "actor_id": doc.get("actor_id"),
                "role": doc.get("role"),
                "action": doc.get("action"),
                "resource": doc.get("resource"),
                "resource_id": doc.get("resource_id"),
                "timestamp": doc.get("timestamp"),
            })

        # Operational alerts
        operational_alerts = []
        if waiting_patients > 10:
            operational_alerts.append({
                "severity": "warning",
                "title": "High Patient Queue Volume",
                "message": f"{waiting_patients} patients currently waiting in consultation queue.",
            })
        if pending_bills > 0:
            operational_alerts.append({
                "severity": "info",
                "title": "Outstanding Patient Invoices",
                "message": f"{pending_bills} invoices pending settlement at reception/cashier.",
            })
        if disabled_users > 0:
            operational_alerts.append({
                "severity": "info",
                "title": "Disabled User Accounts",
                "message": f"{disabled_users} user account(s) currently marked disabled.",
            })

        return {
            "total_patients": total_patients,
            "active_doctors": active_doctors,
            "total_doctors": total_doctors,
            "active_staff": active_staff,
            "total_staff": total_staff,
            "active_users": active_users,
            "disabled_users": disabled_users,
            "password_setup_required_users": pw_setup_users,
            "today_appointments": today_appointments,
            "today_completed_consultations": today_completed_consultations,
            "waiting_patients": waiting_patients,
            "pending_appointments": pending_appointments,
            "cancelled_appointments": cancelled_appointments,
            "pending_bills": pending_bills,
            "collected_revenue": round(collected_revenue, 2),
            "today_revenue": round(today_revenue, 2),
            "recent_activity": recent_activity,
            "operational_alerts": operational_alerts,
            "system_status": "operational",
            "generated_at": utc_now(),
        }

    # ── 2. User & Account Lifecycle Management ───────────────────────────────

    @staticmethod
    async def list_users(
        db: AsyncIOMotorDatabase,
        search: Optional[str] = None,
        role: Optional[UserRole] = None,
        account_status: Optional[AccountStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[AdminUserListItem], int]:
        """Lists users with filtering and role/status checks. Strictly excludes password hashes and token hashes."""
        query: Dict[str, Any] = {"is_deleted": {"$ne": True}}

        if role:
            query["role"] = role.value
        if account_status:
            query["account_status"] = account_status.value
        if search and search.strip():
            safe_query = re.escape(search.strip())
            pattern = re.compile(safe_query, re.IGNORECASE)
            query["$or"] = [
                {"email": pattern},
                {"full_name": pattern},
                {"user_id": pattern},
            ]

        total = await db[COLLECTION_USERS].count_documents(query)
        cursor = db[COLLECTION_USERS].find(query).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        items = []
        for doc in docs:
            items.append(
                AdminUserListItem(
                    user_id=doc["user_id"],
                    email=doc["email"],
                    full_name=doc.get("full_name", ""),
                    role=UserRole.normalize(doc.get("role", "patient")),
                    account_status=AccountStatus(doc.get("account_status", "active")),
                    email_verified=bool(doc.get("email_verified", False)),
                    created_at=doc.get("created_at", utc_now()),
                    updated_at=doc.get("updated_at", utc_now()),
                    last_login_at=doc.get("last_login_at"),
                )
            )

        return items, total

    @staticmethod
    async def get_user_detail(db: AsyncIOMotorDatabase, user_id: str) -> Dict[str, Any]:
        """Returns detailed user operational overview and linked role profile. Excludes all secrets."""
        user_doc = await db[COLLECTION_USERS].find_one({"user_id": user_id, "is_deleted": {"$ne": True}})
        if not user_doc:
            raise ResourceNotFoundError("User", user_id)

        role = UserRole.normalize(user_doc.get("role", "patient"))
        profile_data = None

        if role == UserRole.DOCTOR:
            doc = await db[COLLECTION_DOCTORS].find_one({"user_id": user_id, "is_deleted": {"$ne": True}})
            if doc:
                profile_data = {
                    "doctor_id": doc.get("doctor_id"),
                    "specialization": doc.get("specialization"),
                    "qualification": doc.get("qualification"),
                    "department_id": doc.get("department_id"),
                    "experience_years": doc.get("experience_years"),
                    "consultation_fee": doc.get("consultation_fee"),
                    "status": doc.get("status"),
                }
        elif role == UserRole.HOSPITAL_STAFF:
            st = await db[COLLECTION_STAFF].find_one({"user_id": user_id, "is_deleted": {"$ne": True}})
            if st:
                profile_data = {
                    "staff_id": st.get("staff_id"),
                    "job_title": st.get("job_title"),
                    "employee_number": st.get("employee_number"),
                    "department_id": st.get("department_id"),
                    "status": st.get("status"),
                }
        elif role == UserRole.PATIENT:
            pat = await db[COLLECTION_PATIENTS].find_one({"user_id": user_id, "is_deleted": {"$ne": True}})
            if pat:
                profile_data = {
                    "patient_id": pat.get("patient_id"),
                    "gender": pat.get("gender"),
                    "date_of_birth": pat.get("date_of_birth"),
                    "blood_group": pat.get("blood_group"),
                    "status": pat.get("status"),
                }

        return {
            "user_id": user_doc["user_id"],
            "email": user_doc["email"],
            "full_name": user_doc.get("full_name", ""),
            "role": role.value,
            "account_status": user_doc.get("account_status", "active"),
            "email_verified": bool(user_doc.get("email_verified", False)),
            "created_at": user_doc.get("created_at"),
            "updated_at": user_doc.get("updated_at"),
            "last_login_at": user_doc.get("last_login_at"),
            "profile": profile_data,
        }

    @staticmethod
    async def update_user_status(
        db: AsyncIOMotorDatabase,
        user_id: str,
        new_status: AccountStatus,
        admin_user: UserInDB,
    ) -> Dict[str, Any]:
        """Enables, disables, or updates user lifecycle state.

        - Admin cannot disable their own account.
        - Disabling immediately revokes all active refresh sessions.
        - Synchronizes doctor/staff profile status if linked.
        - Logs audit event.
        """
        user_doc = await db[COLLECTION_USERS].find_one({"user_id": user_id, "is_deleted": {"$ne": True}})
        if not user_doc:
            raise ResourceNotFoundError("User", user_id)

        # Prohibit self-disable
        if user_id == admin_user.user_id and new_status in (AccountStatus.DISABLED, AccountStatus.SUSPENDED, AccountStatus.INACTIVE):
            raise ForbiddenError("Hospital administrators cannot disable their own account.")

        old_status = user_doc.get("account_status", AccountStatus.ACTIVE.value)
        now = utc_now()

        # Update user status
        await db[COLLECTION_USERS].update_one(
            {"user_id": user_id},
            {"$set": {"account_status": new_status.value, "updated_at": now}}
        )

        # If disabling or suspending, revoke all refresh sessions
        if new_status in (AccountStatus.DISABLED, AccountStatus.SUSPENDED, AccountStatus.INACTIVE):
            await db[COLLECTION_USER_SESSIONS].delete_many({"user_id": user_id})
            await db["sessions"].delete_many({"user_id": user_id})
            await db["refresh_tokens"].delete_many({"user_id": user_id})
            logger.info(f"Revoked sessions for disabled user: {user_id}")

            # Close active WebSocket connection if open
            try:
                from app.core.websocket_manager import manager
                await manager.close_user_connections(user_id, code=1000, reason="Account disabled by administrator")
            except Exception:
                pass

        # Synchronize linked professional account profiles
        role = UserRole.normalize(user_doc.get("role", "patient"))
        if role == UserRole.DOCTOR:
            doc_status = DoctorStatus.ACTIVE.value if new_status == AccountStatus.ACTIVE else DoctorStatus.INACTIVE.value
            await db[COLLECTION_DOCTORS].update_one(
                {"user_id": user_id},
                {"$set": {"status": doc_status, "updated_at": now}}
            )
        elif role == UserRole.HOSPITAL_STAFF:
            staff_status = StaffStatus.ACTIVE.value if new_status == AccountStatus.ACTIVE else StaffStatus.INACTIVE.value
            await db[COLLECTION_STAFF].update_one(
                {"user_id": user_id},
                {"$set": {"status": staff_status, "updated_at": now}}
            )

        # Audit logging
        await log_audit_event(
            db=db,
            actor_id=admin_user.user_id,
            role=admin_user.role.value,
            action="ACCOUNT_STATUS_CHANGED",
            resource="users",
            resource_id=user_id,
            metadata={"old_status": old_status, "new_status": new_status.value, "target_email": user_doc.get("email")},
        )

        return {
            "user_id": user_id,
            "email": user_doc["email"],
            "previous_status": old_status,
            "account_status": new_status.value,
            "status": new_status.value,
            "updated_at": now,
        }

    @staticmethod
    async def reinvite_user(
        db: AsyncIOMotorDatabase,
        user_id: str,
        admin_user: UserInDB,
    ) -> Dict[str, Any]:
        """Regenerates and redispatches setup invitation token for unverified or invited accounts."""
        user_doc = await db[COLLECTION_USERS].find_one({"user_id": user_id, "is_deleted": {"$ne": True}})
        if not user_doc:
            raise ResourceNotFoundError("User", user_id)

        email = user_doc["email"]
        raw_token = generate_secure_token()
        token_hash = hash_token(raw_token)
        expires_at = utc_now() + timedelta(days=7)

        await db[COLLECTION_USERS].update_one(
            {"user_id": user_id},
            {"$set": {
                "invitation_token_hash": token_hash,
                "invitation_expires_at": expires_at,
                "account_status": AccountStatus.PASSWORD_SETUP_REQUIRED.value,
                "updated_at": utc_now(),
            }}
        )

        # Dispatch email
        from app.services.email_service import EmailService
        activation_url = f"http://localhost:5173/accept-invitation?token={raw_token}"
        await EmailService.send_invitation_email(
            to_email=email,
            recipient_name=user_doc.get("full_name", email),
            role_name=user_doc.get("role", "staff"),
            activation_url=activation_url,
        )

        await log_audit_event(
            db=db,
            actor_id=admin_user.user_id,
            role=admin_user.role.value,
            action="USER_REINVITED",
            resource="users",
            resource_id=user_id,
            metadata={"email": email, "role": user_doc.get("role")},
        )

        return {
            "user_id": user_id,
            "email": email,
            "status": "invitation_dispatched",
            "expires_at": expires_at,
        }

    # ── 3. Doctor Administration ─────────────────────────────────────────────

    @staticmethod
    async def update_doctor_status(
        db: AsyncIOMotorDatabase,
        doctor_id: str,
        new_status: str,
        admin_user: UserInDB,
    ) -> Dict[str, Any]:
        """Updates doctor operational status and syncs linked user account."""
        doc = await db[COLLECTION_DOCTORS].find_one({"doctor_id": doctor_id, "is_deleted": {"$ne": True}})
        if not doc:
            raise ResourceNotFoundError("Doctor", doctor_id)

        now = utc_now()
        await db[COLLECTION_DOCTORS].update_one(
            {"doctor_id": doctor_id},
            {"$set": {"status": new_status, "updated_at": now}}
        )

        user_status = AccountStatus.ACTIVE.value if new_status == "active" else AccountStatus.DISABLED.value
        user_id = doc.get("user_id")
        if user_id:
            await db[COLLECTION_USERS].update_one(
                {"user_id": user_id},
                {"$set": {"account_status": user_status, "updated_at": now}}
            )
            if user_status == AccountStatus.DISABLED.value:
                await db[COLLECTION_USER_SESSIONS].delete_many({"user_id": user_id})

        await log_audit_event(
            db=db,
            actor_id=admin_user.user_id,
            role=admin_user.role.value,
            action="DOCTOR_STATUS_CHANGED",
            resource="doctors",
            resource_id=doctor_id,
            metadata={"status": new_status, "user_id": user_id},
        )

        return {"doctor_id": doctor_id, "status": new_status, "updated_at": now}

    # ── 4. Staff Administration ──────────────────────────────────────────────

    @staticmethod
    async def update_staff_status(
        db: AsyncIOMotorDatabase,
        staff_id: str,
        new_status: str,
        admin_user: UserInDB,
    ) -> Dict[str, Any]:
        """Updates staff operational status and syncs linked user account."""
        st = await db[COLLECTION_STAFF].find_one({"staff_id": staff_id, "is_deleted": {"$ne": True}})
        if not st:
            raise ResourceNotFoundError("Hospital Staff", staff_id)

        now = utc_now()
        await db[COLLECTION_STAFF].update_one(
            {"staff_id": staff_id},
            {"$set": {"status": new_status, "updated_at": now}}
        )

        user_status = AccountStatus.ACTIVE.value if new_status == "active" else AccountStatus.DISABLED.value
        user_id = st.get("user_id")
        if user_id:
            await db[COLLECTION_USERS].update_one(
                {"user_id": user_id},
                {"$set": {"account_status": user_status, "updated_at": now}}
            )
            if user_status == AccountStatus.DISABLED.value:
                await db[COLLECTION_USER_SESSIONS].delete_many({"user_id": user_id})

        await log_audit_event(
            db=db,
            actor_id=admin_user.user_id,
            role=admin_user.role.value,
            action="STAFF_STATUS_CHANGED",
            resource="staff",
            resource_id=staff_id,
            metadata={"status": new_status, "user_id": user_id},
        )

        return {"staff_id": staff_id, "status": new_status, "updated_at": now}

    # ── 5. Administrative Appointment Cancellation ───────────────────────────

    @staticmethod
    async def cancel_appointment(
        db: AsyncIOMotorDatabase,
        appointment_id: str,
        reason: str,
        admin_user: UserInDB,
    ) -> Dict[str, Any]:
        """Admin cancels an appointment with justification, respecting lifecycle invariants."""
        apt = await db[COLLECTION_APPOINTMENTS].find_one({
            "appointment_id": appointment_id,
            "is_deleted": {"$ne": True}
        })
        if not apt:
            raise ResourceNotFoundError("Appointment", appointment_id)

        if apt.get("status") in ("completed", "in_consultation"):
            raise AppValidationError(f"Cannot cancel appointment with status '{apt.get('status')}'.")
        if apt.get("status") == "cancelled":
            raise AppValidationError("Appointment is already cancelled.")

        now = utc_now()
        await db[COLLECTION_APPOINTMENTS].update_one(
            {"appointment_id": appointment_id},
            {"$set": {
                "status": "cancelled",
                "cancellation_reason": reason,
                "cancelled_by": admin_user.user_id,
                "cancelled_at": now,
                "updated_at": now,
            }}
        )

        await log_audit_event(
            db=db,
            actor_id=admin_user.user_id,
            role=admin_user.role.value,
            action="APPOINTMENT_CANCELLED_BY_ADMIN",
            resource="appointments",
            resource_id=appointment_id,
            metadata={"reason": reason, "patient_id": apt.get("patient_id"), "doctor_id": apt.get("doctor_id")},
        )

        return {
            "appointment_id": appointment_id,
            "status": "cancelled",
            "reason": reason,
            "cancelled_at": now,
        }

    # ── 6. Hospital Settings ─────────────────────────────────────────────────

    @staticmethod
    async def get_hospital_settings(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
        """Fetches persisted hospital settings. If not found, persists and returns default configuration."""
        settings_doc = await db[COLLECTION_HOSPITAL_SETTINGS].find_one({"setting_id": "default"})
        if not settings_doc:
            default_settings = HospitalSettingsInDB()
            await db[COLLECTION_HOSPITAL_SETTINGS].insert_one(default_settings.to_mongo_dict())
            settings_doc = default_settings.to_mongo_dict()

        if "_id" in settings_doc:
            settings_doc["_id"] = str(settings_doc["_id"])
        return settings_doc

    @staticmethod
    async def update_hospital_settings(
        db: AsyncIOMotorDatabase,
        request: UpdateHospitalSettingsRequest,
        admin_user: UserInDB,
    ) -> Dict[str, Any]:
        """Updates hospital settings with strict allowlist validation and audit logging."""
        updates: Dict[str, Any] = {}
        for field, value in request.model_dump(exclude_unset=True).items():
            if value is not None:
                updates[field] = value

        if not updates:
            return await AdminService.get_hospital_settings(db)

        updates["updated_at"] = utc_now()
        updates["updated_by"] = admin_user.user_id

        await db[COLLECTION_HOSPITAL_SETTINGS].update_one(
            {"setting_id": "default"},
            {"$set": updates},
            upsert=True
        )

        await log_audit_event(
            db=db,
            actor_id=admin_user.user_id,
            role=admin_user.role.value,
            action="HOSPITAL_SETTINGS_UPDATED",
            resource="hospital_settings",
            resource_id="default",
            metadata={"updated_fields": list(updates.keys())},
        )

        return await AdminService.get_hospital_settings(db)

    # ── 7. Operational Search ────────────────────────────────────────────────

    @staticmethod
    async def operational_search(
        db: AsyncIOMotorDatabase,
        q: str,
        limit_per_resource: int = 10,
    ) -> Dict[str, Any]:
        """Global administrative search across users, patients, doctors, staff, appointments, billing."""
        clean_q = q.strip()
        if not clean_q:
            return {"query": q, "results": {}}

        safe_pattern = re.compile(re.escape(clean_q), re.IGNORECASE)
        results: Dict[str, List[Dict[str, Any]]] = {
            "users": [],
            "patients": [],
            "doctors": [],
            "staff": [],
            "appointments": [],
            "billing": [],
        }

        # Users
        u_cursor = db[COLLECTION_USERS].find(
            {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"email": safe_pattern},
                    {"full_name": safe_pattern},
                    {"user_id": safe_pattern},
                ]
            }
        ).limit(limit_per_resource)
        async for u in u_cursor:
            results["users"].append({
                "user_id": u["user_id"],
                "email": u["email"],
                "full_name": u.get("full_name"),
                "role": u.get("role"),
                "status": u.get("account_status"),
            })

        # Patients
        p_cursor = db[COLLECTION_PATIENTS].find(
            {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"first_name": safe_pattern},
                    {"last_name": safe_pattern},
                    {"email": safe_pattern},
                    {"phone": safe_pattern},
                    {"patient_id": safe_pattern},
                ]
            }
        ).limit(limit_per_resource)
        async for p in p_cursor:
            results["patients"].append({
                "patient_id": p["patient_id"],
                "name": f"{p.get('first_name', '')} {p.get('last_name', '')}".strip(),
                "email": p.get("email"),
                "phone": p.get("phone"),
                "status": p.get("status"),
            })

        # Doctors
        d_cursor = db[COLLECTION_DOCTORS].find(
            {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"first_name": safe_pattern},
                    {"last_name": safe_pattern},
                    {"specialization": safe_pattern},
                    {"doctor_id": safe_pattern},
                ]
            }
        ).limit(limit_per_resource)
        async for d in d_cursor:
            results["doctors"].append({
                "doctor_id": d["doctor_id"],
                "name": f"Dr. {d.get('first_name', '')} {d.get('last_name', '')}".strip(),
                "specialization": d.get("specialization"),
                "status": d.get("status"),
            })

        # Staff
        s_cursor = db[COLLECTION_STAFF].find(
            {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"first_name": safe_pattern},
                    {"last_name": safe_pattern},
                    {"job_title": safe_pattern},
                    {"staff_id": safe_pattern},
                ]
            }
        ).limit(limit_per_resource)
        async for s in s_cursor:
            results["staff"].append({
                "staff_id": s["staff_id"],
                "name": f"{s.get('first_name', '')} {s.get('last_name', '')}".strip(),
                "job_title": s.get("job_title"),
                "status": s.get("status"),
            })

        # Appointments
        a_cursor = db[COLLECTION_APPOINTMENTS].find(
            {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"appointment_id": safe_pattern},
                    {"appointment_date": safe_pattern},
                    {"reason": safe_pattern},
                ]
            }
        ).limit(limit_per_resource)
        async for a in a_cursor:
            results["appointments"].append({
                "appointment_id": a["appointment_id"],
                "patient_id": a.get("patient_id"),
                "doctor_id": a.get("doctor_id"),
                "date": a.get("appointment_date"),
                "status": a.get("status"),
            })

        # Billing
        b_cursor = db[COLLECTION_BILLING].find(
            {
                "is_deleted": {"$ne": True},
                "$or": [
                    {"bill_id": safe_pattern},
                    {"invoice_number": safe_pattern},
                    {"patient_id": safe_pattern},
                ]
            }
        ).limit(limit_per_resource)
        async for b in b_cursor:
            results["billing"].append({
                "bill_id": b["bill_id"],
                "patient_id": b.get("patient_id"),
                "grand_total": b.get("grand_total"),
                "status": b.get("status"),
            })

        total_matches = sum(len(items) for items in results.values())
        return {"query": q, "total_matches": total_matches, "results": results}
