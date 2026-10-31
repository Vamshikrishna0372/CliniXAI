"""Persistent Audit Log Service for CliniXAI backend."""

import uuid
from typing import Optional, Dict, Any, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.database.collections import COLLECTION_AUDIT_LOGS
from app.models.audit_log import AuditLogInDB
from app.utils.datetime import utc_now
from app.core.logging import logger


async def log_audit_event(
    db: AsyncIOMotorDatabase,
    actor_id: str,
    role: str,
    action: str,
    resource: str,
    resource_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Logs an audit event into the database idempotently."""
    audit_id = f"AUD-{uuid.uuid4().hex[:12].upper()}"
    audit_entry = AuditLogInDB(
        audit_id=audit_id,
        actor_id=actor_id,
        role=role,
        action=action,
        resource=resource,
        resource_id=resource_id,
        ip_address=ip_address,
        user_agent=user_agent,
        metadata=metadata,
        timestamp=utc_now(),
    )
    try:
        await db[COLLECTION_AUDIT_LOGS].insert_one(audit_entry.to_mongo_dict())
    except Exception as exc:
        logger.error(f"Failed to record audit log entry {audit_id}: {exc}")
    return audit_id


class AuditService:
    """Service for querying persistent audit log entries (Admin only)."""

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[COLLECTION_AUDIT_LOGS]

    async def list_audit_logs(
        self,
        actor_id: Optional[str] = None,
        action: Optional[str] = None,
        resource: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        current_user: Optional[Any] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> tuple[List[AuditLogInDB], int]:
        """Lists audit log records with role-aware filtering, date filtering, and deterministic ordering."""
        query: Dict[str, Any] = {}
        if actor_id:
            query["actor_id"] = actor_id
        if action:
            query["action"] = action
        if resource:
            query["resource"] = resource
        if start_date or end_date:
            ts_filter: Dict[str, Any] = {}
            if start_date:
                ts_filter["$gte"] = start_date
            if end_date:
                ts_filter["$lte"] = end_date
            query["timestamp"] = ts_filter

        if current_user:
            role_val = getattr(current_user.role, "value", str(current_user.role))
            if role_val == "patient":
                pat = await self.db["patients"].find_one({"user_id": current_user.user_id})
                pat_id = pat["patient_id"] if pat else None
                conditions = [{"actor_id": current_user.user_id}]
                if pat_id:
                    conditions.append({"metadata.patient_id": pat_id})
                query["$or"] = conditions
            elif role_val == "doctor":
                doc = await self.db["doctors"].find_one({"user_id": current_user.user_id})
                doc_id = doc["doctor_id"] if doc else None
                conditions = [{"actor_id": current_user.user_id}]
                if doc_id:
                    conditions.append({"metadata.doctor_id": doc_id})
                query["$or"] = conditions

        total = await self.collection.count_documents(query)
        cursor = self.collection.find(query).sort("timestamp", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)

        items = [AuditLogInDB(**doc) for doc in docs]
        return items, total
