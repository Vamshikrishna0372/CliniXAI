"""Notification Service — Dispatches, stores, and manages notifications for CliniXAI Phase 17.

Production guarantees:
- MongoDB persistence is the authoritative persistent source of truth.
- Database-level deduplication: idempotent event processing via deterministic dedupe_key.
- Real-time delivery via WebSocket manager and cross-worker shared event bus.
- Object-level security and strict recipient isolation (zero cross-user leakage).
- Deterministic pagination and server-authoritative timestamps.
"""

from typing import Optional, List, Dict, Any, Tuple, Union
from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo.errors import DuplicateKeyError

from app.core.logging import logger
from app.core.exceptions import ResourceNotFoundError, ForbiddenError
from app.database.collections import COLLECTION_NOTIFICATIONS
from app.database.mongodb import save_in_memory_snapshot
from app.models.notification import (
    NotificationInDB, NotificationType, NotificationChannel,
    NotificationStatus, NotificationCategory, NotificationPriority
)
from app.models.user import UserInDB
from app.utils.id_generator import generate_notification_id
from app.utils.datetime import utc_now


def _infer_category(notif_type: Union[NotificationType, str], ref_type: Optional[str] = None) -> str:
    """Infers standard notification category from type or reference."""
    val = (notif_type.value if hasattr(notif_type, "value") else str(notif_type)).lower()
    rt = (ref_type or "").lower()

    if "appointment" in val or "checkin" in val or rt == "appointment":
        return NotificationCategory.APPOINTMENT.value
    if "consultation" in val or rt == "consultation":
        return NotificationCategory.CONSULTATION.value
    if "prescription" in val or "rx" in val or rt == "prescription":
        return NotificationCategory.PRESCRIPTION.value
    if "bill" in val or "payment" in val or rt == "billing":
        return NotificationCategory.BILLING.value
    if "ai" in val or rt == "ai_analysis":
        return NotificationCategory.AI.value
    if "medical_record" in val or "clinical" in val:
        return NotificationCategory.CLINICAL.value
    return NotificationCategory.SYSTEM.value


class NotificationService:
    """Notification creation, inbox retrieval, mark-read, unread-count, and real-time delivery."""

    @staticmethod
    async def dispatch(
        db: AsyncIOMotorDatabase,
        recipient_user_id: str,
        notification_type: Union[NotificationType, str],
        title: str,
        body: str,
        reference_id: Optional[str] = None,
        reference_type: Optional[str] = None,
        source_id: Optional[str] = None,
        source_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        category: Optional[str] = None,
        priority: str = "normal",
        actor_user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        dedupe_key: Optional[str] = None,
        channel: NotificationChannel = NotificationChannel.IN_APP,
    ) -> NotificationInDB:
        """
        Creates, persists, and real-time delivers an authoritative notification.
        Supports deterministic deduplication via dedupe_key with database-level uniqueness.
        """
        resolved_type = notification_type if isinstance(notification_type, NotificationType) else NotificationType(notification_type)
        ref_id = source_id or reference_id or entity_id
        ref_type = source_type or reference_type or entity_type
        resolved_category = category or _infer_category(resolved_type, ref_type)

        # 1. Idempotency Check via Dedupe Key
        if dedupe_key:
            existing = await db[COLLECTION_NOTIFICATIONS].find_one({"dedupe_key": dedupe_key, "is_deleted": {"$ne": True}})
            if existing:
                logger.info(f"Duplicate event prevented via dedupe_key [{dedupe_key}]. Returning existing notification {existing['notification_id']}.")
                return NotificationInDB(**existing)

        now = utc_now()
        notification_id = generate_notification_id()
        notification = NotificationInDB(
            notification_id=notification_id,
            recipient_user_id=recipient_user_id,
            user_id=recipient_user_id,
            notification_type=resolved_type,
            type=resolved_type.value,
            category=resolved_category,
            priority=priority,
            channel=channel,
            status=NotificationStatus.SENT,
            read=False,
            title=title,
            body=body,
            message=body,
            reference_id=ref_id,
            reference_type=ref_type,
            source_id=ref_id,
            source_type=ref_type,
            entity_id=ref_id,
            entity_type=ref_type,
            actor_user_id=actor_user_id,
            metadata=metadata or {},
            dedupe_key=dedupe_key,
            sent_at=now,
            created_at=now,
            updated_at=now,
        )

        doc_dict = notification.to_mongo_dict()

        # 2. Authoritative MongoDB Persistence (Atomic insertion)
        try:
            await db[COLLECTION_NOTIFICATIONS].insert_one(doc_dict)
            logger.info(
                f"Notification [{resolved_type.value}] dispatched to user {recipient_user_id} "
                f"(ID: {notification.notification_id}, DedupeKey: {dedupe_key})"
            )
        except DuplicateKeyError:
            # Concurrent race caught: another worker inserted the exact same dedupe_key simultaneously
            if dedupe_key:
                existing = await db[COLLECTION_NOTIFICATIONS].find_one({"dedupe_key": dedupe_key})
                if existing:
                    logger.info(f"Concurrent race duplicate prevented via dedupe_key [{dedupe_key}].")
                    return NotificationInDB(**existing)
            raise

        # 3. Snapshot Synchronization
        await save_in_memory_snapshot(db)

        # 4. Real-time Multi-Worker Event Bus Publication
        await NotificationService.publish_realtime(db, notification)

        return notification

    @staticmethod
    async def create_notification(
        db: AsyncIOMotorDatabase,
        recipient_user_id: str,
        notification_type: Union[NotificationType, str],
        title: str,
        body: str,
        **kwargs,
    ) -> NotificationInDB:
        """Alias for dispatch providing uniform service interface."""
        return await NotificationService.dispatch(
            db=db,
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            title=title,
            body=body,
            **kwargs,
        )

    @staticmethod
    async def publish_realtime(
        db: Optional[AsyncIOMotorDatabase],
        notification: NotificationInDB,
    ) -> None:
        """Emits structured real-time event to active WebSocket connections across workers."""
        try:
            from app.core.websocket_manager import manager

            safe_created_at = (
                notification.created_at.isoformat()
                if hasattr(notification.created_at, "isoformat")
                else str(notification.created_at)
            )

            # Standardized Phase 17 event payload (safe summary only, zero sensitive bytes/passwords)
            payload = {
                "event": "notification.created",
                "notification": {
                    "notification_id": notification.notification_id,
                    "type": notification.type or notification.notification_type.value,
                    "category": notification.category,
                    "priority": notification.priority,
                    "title": notification.title,
                    "message": notification.message or notification.body,
                    "body": notification.body,
                    "read": notification.read,
                    "status": notification.status.value if hasattr(notification.status, "value") else str(notification.status),
                    "source_type": notification.source_type,
                    "source_id": notification.source_id,
                    "reference_type": notification.reference_type,
                    "reference_id": notification.reference_id,
                    "created_at": safe_created_at,
                },
                # Backward-compatibility key for existing UI consumers
                "data": {
                    "notification_id": notification.notification_id,
                    "recipient_user_id": notification.recipient_user_id,
                    "user_id": notification.recipient_user_id,
                    "notification_type": notification.notification_type.value,
                    "category": notification.category,
                    "title": notification.title,
                    "body": notification.body,
                    "message": notification.body,
                    "status": notification.status.value if hasattr(notification.status, "value") else str(notification.status),
                    "read": notification.read,
                    "reference_id": notification.reference_id,
                    "reference_type": notification.reference_type,
                    "source_id": notification.source_id,
                    "source_type": notification.source_type,
                    "created_at": safe_created_at,
                },
            }

            await manager.publish_event(
                db=db,
                user_id=notification.recipient_user_id,
                event_name="notification.created",
                payload=payload,
            )
        except Exception as ws_err:
            logger.warning(f"Real-time delivery notice for {notification.notification_id}: {ws_err}")

    @staticmethod
    async def list_inbox(
        db: AsyncIOMotorDatabase,
        current_user: UserInDB,
        page: int = 1,
        page_size: int = 20,
        unread_only: bool = False,
        category: Optional[str] = None,
        notification_type: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Returns paginated notification inbox for current user with deterministic ordering.
        Strictly enforces user isolation (anti-IDOR: users only see own notifications).
        """
        user_id = current_user.user_id
        query: Dict[str, Any] = {
            "$or": [{"recipient_user_id": user_id}, {"user_id": user_id}],
            "is_deleted": {"$ne": True},
        }

        if unread_only:
            query["$and"] = [
                {"$or": [{"read": False}, {"status": {"$in": [NotificationStatus.SENT.value, NotificationStatus.PENDING.value]}}]}
            ]

        if category:
            query["category"] = category.lower().strip()

        if notification_type:
            nt = notification_type.lower().strip()
            query["$or"] = [{"notification_type": nt}, {"type": nt}]

        # Bound pagination arguments
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        skip = (page - 1) * page_size

        total = await db[COLLECTION_NOTIFICATIONS].count_documents(query)

        # Deterministic ordering: created_at DESC, notification_id DESC
        cursor = (
            db[COLLECTION_NOTIFICATIONS]
            .find(query)
            .sort([("created_at", -1), ("notification_id", -1)])
            .skip(skip)
            .limit(page_size)
        )
        docs = await cursor.to_list(length=page_size)
        return docs, total

    @staticmethod
    async def get_notification_by_id(
        db: AsyncIOMotorDatabase,
        notification_id: str,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """
        Retrieves a single notification with object-level authorization verification.
        Rejects cross-user access with 403 Forbidden without leaking unauthorized content.
        """
        doc = await db[COLLECTION_NOTIFICATIONS].find_one({
            "notification_id": notification_id,
            "is_deleted": {"$ne": True},
        })
        if not doc:
            raise ResourceNotFoundError("Notification", notification_id)

        recip = doc.get("recipient_user_id") or doc.get("user_id")
        if recip != current_user.user_id:
            raise ForbiddenError("You are not authorized to view this notification.")

        return doc

    @staticmethod
    async def get_unread_count(db: AsyncIOMotorDatabase, user_id: str) -> int:
        """Returns authoritative count of unread notifications from MongoDB."""
        query = {
            "$or": [{"recipient_user_id": user_id}, {"user_id": user_id}],
            "is_deleted": {"$ne": True},
            "$or": [
                {"read": False},
                {"status": {"$in": [NotificationStatus.SENT.value, NotificationStatus.PENDING.value]}},
            ],
        }
        return await db[COLLECTION_NOTIFICATIONS].count_documents(query)

    @staticmethod
    async def mark_read(
        db: AsyncIOMotorDatabase,
        notification_id: str,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Marks a single notification as read after ownership verification and broadcasts update."""
        doc = await db[COLLECTION_NOTIFICATIONS].find_one({"notification_id": notification_id})
        if not doc or doc.get("is_deleted") is True:
            raise ResourceNotFoundError("Notification", notification_id)

        recip = doc.get("recipient_user_id") or doc.get("user_id")
        if recip != current_user.user_id:
            raise ForbiddenError("You are not authorized to update this notification.")

        now = utc_now()
        await db[COLLECTION_NOTIFICATIONS].update_one(
            {"notification_id": notification_id},
            {"$set": {
                "status": NotificationStatus.READ.value,
                "read": True,
                "read_at": now,
                "updated_at": now,
            }},
        )
        doc["status"] = NotificationStatus.READ.value
        doc["read"] = True
        doc["read_at"] = now
        doc["updated_at"] = now

        await save_in_memory_snapshot(db)

        # Broadcast state synchronization event
        try:
            from app.core.websocket_manager import manager
            await manager.publish_event(
                db=db,
                user_id=current_user.user_id,
                event_name="notification.read",
                payload={
                    "event": "notification.read",
                    "notification_id": notification_id,
                    "read": True,
                    "read_at": now.isoformat(),
                },
            )
        except Exception:
            pass

        return doc

    @staticmethod
    async def mark_unread(
        db: AsyncIOMotorDatabase,
        notification_id: str,
        current_user: UserInDB,
    ) -> Dict[str, Any]:
        """Marks a single notification as unread after ownership verification and broadcasts update."""
        doc = await db[COLLECTION_NOTIFICATIONS].find_one({"notification_id": notification_id})
        if not doc or doc.get("is_deleted") is True:
            raise ResourceNotFoundError("Notification", notification_id)

        recip = doc.get("recipient_user_id") or doc.get("user_id")
        if recip != current_user.user_id:
            raise ForbiddenError("You are not authorized to update this notification.")

        now = utc_now()
        await db[COLLECTION_NOTIFICATIONS].update_one(
            {"notification_id": notification_id},
            {"$set": {
                "status": NotificationStatus.SENT.value,
                "read": False,
                "read_at": None,
                "updated_at": now,
            }},
        )
        doc["status"] = NotificationStatus.SENT.value
        doc["read"] = False
        doc["read_at"] = None
        doc["updated_at"] = now

        await save_in_memory_snapshot(db)

        # Broadcast state synchronization event
        try:
            from app.core.websocket_manager import manager
            await manager.publish_event(
                db=db,
                user_id=current_user.user_id,
                event_name="notification.unread",
                payload={
                    "event": "notification.unread",
                    "notification_id": notification_id,
                    "read": False,
                },
            )
        except Exception:
            pass

        return doc

    @staticmethod
    async def mark_all_read(db: AsyncIOMotorDatabase, current_user: UserInDB) -> int:
        """Marks all unread notifications as read for current user and broadcasts update."""
        now = utc_now()
        user_id = current_user.user_id
        result = await db[COLLECTION_NOTIFICATIONS].update_many(
            {
                "$or": [{"recipient_user_id": user_id}, {"user_id": user_id}],
                "is_deleted": {"$ne": True},
                "$or": [
                    {"read": False},
                    {"status": {"$in": [NotificationStatus.SENT.value, NotificationStatus.PENDING.value]}},
                ],
            },
            {"$set": {
                "status": NotificationStatus.READ.value,
                "read": True,
                "read_at": now,
                "updated_at": now,
            }},
        )
        updated = result.modified_count
        logger.info(f"Marked {updated} notifications as read for user {user_id}")

        await save_in_memory_snapshot(db)

        # Broadcast state synchronization event
        try:
            from app.core.websocket_manager import manager
            await manager.publish_event(
                db=db,
                user_id=user_id,
                event_name="notification.read_all",
                payload={
                    "event": "notification.read_all",
                    "user_id": user_id,
                    "updated_count": updated,
                },
            )
        except Exception:
            pass

        return updated

    @staticmethod
    async def delete_notification(
        db: AsyncIOMotorDatabase,
        notification_id: str,
        current_user: UserInDB,
    ) -> bool:
        """Soft-deletes a notification after recipient ownership verification."""
        doc = await db[COLLECTION_NOTIFICATIONS].find_one({"notification_id": notification_id})
        if not doc or doc.get("is_deleted") is True:
            raise ResourceNotFoundError("Notification", notification_id)

        recip = doc.get("recipient_user_id") or doc.get("user_id")
        if recip != current_user.user_id:
            raise ForbiddenError("You are not authorized to delete this notification.")

        now = utc_now()
        await db[COLLECTION_NOTIFICATIONS].update_one(
            {"notification_id": notification_id},
            {"$set": {"is_deleted": True, "deleted_at": now, "deleted_by": current_user.user_id}},
        )
        await save_in_memory_snapshot(db)
        return True
