"""Follow-up service managing patient follow-up appointments and reminders."""

import uuid
from typing import Optional, List, Tuple
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import COLLECTION_FOLLOW_UPS
from app.models.follow_up import FollowUpInDB, FollowUpStatus
from app.schemas.follow_ups import CreateFollowUpRequest, UpdateFollowUpRequest
from app.core.exceptions import NotFoundError, ForbiddenError
from app.utils.datetime import utc_now


class FollowUpService:
    """Service handling follow-up record lifecycle."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[COLLECTION_FOLLOW_UPS]

    async def create_follow_up(self, req: CreateFollowUpRequest, actor_id: str) -> FollowUpInDB:
        """Create a new follow-up entry."""
        fu_id = f"FU-{uuid.uuid4().hex[:12].upper()}"
        follow_up = FollowUpInDB(
            follow_up_id=fu_id,
            patient_id=req.patient_id,
            doctor_id=req.doctor_id,
            consultation_id=req.consultation_id,
            appointment_id=req.appointment_id,
            scheduled_date=req.scheduled_date,
            reason=req.reason,
            notes=req.notes,
            status=FollowUpStatus.SCHEDULED,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        await self.collection.insert_one(follow_up.to_mongo_dict())

        # Notification & Email dispatches & Audit Log
        try:
            from app.database.collections import COLLECTION_PATIENTS, COLLECTION_DOCTORS
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType
            from app.services.email_service import EmailService
            from app.services.audit_service import log_audit_event

            await log_audit_event(
                db=self.db,
                actor_id=actor_id,
                role="doctor",
                action="schedule_follow_up",
                resource="follow_up",
                resource_id=fu_id,
                metadata={"patient_id": req.patient_id, "doctor_id": req.doctor_id, "scheduled_date": str(req.scheduled_date)},
            )

            pat = await self.db[COLLECTION_PATIENTS].find_one({"patient_id": req.patient_id})
            doc = await self.db[COLLECTION_DOCTORS].find_one({"doctor_id": req.doctor_id})
            doc_name = f"Dr. {doc.get('first_name', '')} {doc.get('last_name', '')}".strip() if doc else "Doctor"
            pat_name = f"{pat.get('first_name', '')} {pat.get('last_name', '')}".strip() if pat else "Patient"

            if pat and pat.get("user_id"):
                await NotificationService.dispatch(
                    db=self.db,
                    recipient_user_id=pat["user_id"],
                    notification_type=NotificationType.FOLLOW_UP_SCHEDULED,
                    title="Follow-Up Scheduled",
                    body=f"Follow-up with {doc_name} scheduled for {req.scheduled_date}. Reason: {req.reason}",
                    reference_id=fu_id,
                    reference_type="follow_up",
                )
            if doc and doc.get("user_id"):
                await NotificationService.dispatch(
                    db=self.db,
                    recipient_user_id=doc["user_id"],
                    notification_type=NotificationType.FOLLOW_UP_SCHEDULED,
                    title="Follow-Up Scheduled",
                    body=f"Follow-up for patient {pat_name} scheduled for {req.scheduled_date}.",
                    reference_id=fu_id,
                    reference_type="follow_up",
                )

            if pat and pat.get("email"):
                await EmailService.send_followup_reminder_email(
                    to_email=pat["email"],
                    recipient_name=pat_name,
                    doctor_name=doc_name,
                    followup_date=str(req.scheduled_date),
                    notes=req.notes,
                )
        except Exception as exc:
            pass

        return follow_up

    async def get_follow_up(self, follow_up_id: str) -> FollowUpInDB:
        """Get a single follow-up record."""
        doc = await self.collection.find_one({"follow_up_id": follow_up_id, "is_deleted": {"$ne": True}})
        if not doc:
            raise NotFoundError(f"Follow-up record '{follow_up_id}' not found.")
        return FollowUpInDB(**doc)

    async def update_follow_up(self, follow_up_id: str, req: UpdateFollowUpRequest) -> FollowUpInDB:
        """Update follow-up details or status."""
        existing = await self.get_follow_up(follow_up_id)
        update_data = req.model_dump(exclude_unset=True)
        if not update_data:
            return existing

        update_data["updated_at"] = utc_now()
        await self.collection.update_one(
            {"follow_up_id": follow_up_id},
            {"$set": update_data}
        )
        updated_item = await self.get_follow_up(follow_up_id)

        # Notify on status or date change
        try:
            from app.database.collections import COLLECTION_PATIENTS, COLLECTION_DOCTORS
            from app.services.notification_service import NotificationService
            from app.models.notification import NotificationType

            pat = await self.db[COLLECTION_PATIENTS].find_one({"patient_id": updated_item.patient_id})
            doc = await self.db[COLLECTION_DOCTORS].find_one({"doctor_id": updated_item.doctor_id})
            
            if req.status:
                notif_type = (
                    NotificationType.FOLLOW_UP_COMPLETED
                    if req.status == FollowUpStatus.COMPLETED
                    else NotificationType.FOLLOW_UP_REMINDER
                )
                status_text = req.status.value.capitalize()
                if pat and pat.get("user_id"):
                    await NotificationService.dispatch(
                        db=self.db,
                        recipient_user_id=pat["user_id"],
                        notification_type=notif_type,
                        title=f"Follow-Up {status_text}",
                        body=f"Your follow-up record {follow_up_id} has been marked as {req.status.value}.",
                        reference_id=follow_up_id,
                        reference_type="follow_up",
                    )
                if doc and doc.get("user_id"):
                    await NotificationService.dispatch(
                        db=self.db,
                        recipient_user_id=doc["user_id"],
                        notification_type=notif_type,
                        title=f"Follow-Up {status_text}",
                        body=f"Follow-up {follow_up_id} for patient {updated_item.patient_id} is {req.status.value}.",
                        reference_id=follow_up_id,
                        reference_type="follow_up",
                    )
        except Exception:
            pass

        return updated_item

    async def list_follow_ups(
        self,
        patient_id: Optional[str] = None,
        doctor_id: Optional[str] = None,
        status: Optional[FollowUpStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[FollowUpInDB], int]:
        """List follow-up records with filtering."""
        query = {"is_deleted": {"$ne": True}}
        if patient_id:
            query["patient_id"] = patient_id
        if doctor_id:
            query["doctor_id"] = doctor_id
        if status:
            query["status"] = status.value

        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("scheduled_date", 1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        items = [FollowUpInDB(**doc) for doc in docs]
        return items, total

    async def soft_delete_follow_up(self, follow_up_id: str, deleted_by: str) -> bool:
        """Soft deletes a follow-up record."""
        existing = await self.get_follow_up(follow_up_id)
        await self.collection.update_one(
            {"follow_up_id": follow_up_id},
            {"$set": {"is_deleted": True, "deleted_at": utc_now(), "deleted_by": deleted_by}}
        )
        return True
