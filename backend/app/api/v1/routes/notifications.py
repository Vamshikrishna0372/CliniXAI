"""Notification API Routes for CliniXAI Phase 17.

Production guarantees:
- Secure JWT authentication via Bearer header or HttpOnly cookie.
- Strictly rejects JWT tokens in WebSocket URL query strings (?token= is prohibited).
- Strict recipient authorization and anti-IDOR defense on all endpoints.
- Authoritative MongoDB persistence and deterministic pagination.
- Real-time delivery and multi-worker event bus synchronization.
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.dependencies.database import get_database
from app.dependencies.auth import get_current_user
from app.models.user import UserInDB, AccountStatus
from app.schemas.notifications import (
    NotificationResponse, NotificationSummaryResponse, UnreadCountResponse
)
from app.schemas.common import APIResponse, PaginatedResponse, PaginationMeta
from app.services.notification_service import NotificationService
from app.core.security import decode_token
from app.core.websocket_manager import manager
from app.core.logging import logger
from app.database.collections import COLLECTION_USERS

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get(
    "",
    response_model=PaginatedResponse[NotificationSummaryResponse],
    summary="List Notifications Inbox",
)
async def list_notifications(
    page: int = Query(default=1, ge=1),
    page_size: Optional[int] = Query(default=None, ge=1),
    limit: Optional[int] = Query(default=None, ge=1),
    unread_only: bool = Query(default=False),
    category: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns paginated notifications inbox for the authenticated user."""
    resolved_size = page_size or limit or 20
    if resolved_size > 100:
        resolved_size = 100
    docs, total = await NotificationService.list_inbox(
        db=db,
        current_user=current_user,
        page=page,
        page_size=resolved_size,
        unread_only=unread_only,
        category=category,
        notification_type=type,
    )
    meta = PaginationMeta.create(page=page, page_size=resolved_size, total=total)

    results = [
        NotificationSummaryResponse(
            notification_id=d["notification_id"],
            notification_type=d["notification_type"],
            type=d.get("type") or str(d["notification_type"]),
            category=d.get("category", "system"),
            priority=d.get("priority", "normal"),
            title=d["title"],
            body=d.get("body") or d.get("message", ""),
            message=d.get("message") or d.get("body", ""),
            status=d["status"],
            read=bool(d.get("read") or d.get("status") == "read"),
            reference_id=d.get("reference_id") or d.get("source_id"),
            reference_type=d.get("reference_type") or d.get("source_type"),
            source_id=d.get("source_id") or d.get("reference_id"),
            source_type=d.get("source_type") or d.get("reference_type"),
            created_at=d["created_at"],
        )
        for d in docs
    ]
    return PaginatedResponse(data=results, pagination=meta)


@router.get(
    "/unread-count",
    response_model=APIResponse[UnreadCountResponse],
    summary="Get Unread Notification Count",
)
async def get_unread_count(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Returns authoritative total number of unread notifications from MongoDB."""
    count = await NotificationService.get_unread_count(db, current_user.user_id)
    return APIResponse(data={"unread_count": count})


@router.get(
    "/{notification_id}",
    response_model=APIResponse[NotificationResponse],
    summary="Get Single Notification Detail",
)
async def get_notification_detail(
    notification_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Retrieves a single notification with object-level ownership authorization."""
    doc = await NotificationService.get_notification_by_id(db, notification_id, current_user)
    resp = NotificationResponse(
        notification_id=doc["notification_id"],
        recipient_user_id=doc.get("recipient_user_id") or doc.get("user_id"),
        user_id=doc.get("user_id") or doc.get("recipient_user_id"),
        notification_type=doc["notification_type"],
        type=doc.get("type") or str(doc["notification_type"]),
        category=doc.get("category", "system"),
        priority=doc.get("priority", "normal"),
        channel=doc.get("channel", "in_app"),
        status=doc["status"],
        read=bool(doc.get("read") or doc.get("status") == "read"),
        title=doc["title"],
        body=doc.get("body") or doc.get("message", ""),
        message=doc.get("message") or doc.get("body", ""),
        reference_id=doc.get("reference_id") or doc.get("source_id"),
        reference_type=doc.get("reference_type") or doc.get("source_type"),
        source_id=doc.get("source_id") or doc.get("reference_id"),
        source_type=doc.get("source_type") or doc.get("reference_type"),
        entity_id=doc.get("entity_id") or doc.get("source_id"),
        entity_type=doc.get("entity_type") or doc.get("source_type"),
        actor_user_id=doc.get("actor_user_id"),
        metadata=doc.get("metadata"),
        dedupe_key=doc.get("dedupe_key"),
        read_at=doc.get("read_at"),
        sent_at=doc.get("sent_at"),
        created_at=doc["created_at"],
        updated_at=doc.get("updated_at", doc["created_at"]),
    )
    return APIResponse(data=resp)


@router.post(
    "/{notification_id}/read",
    response_model=APIResponse[NotificationResponse],
    summary="Mark Notification as Read (POST)",
)
@router.patch(
    "/{notification_id}/read",
    response_model=APIResponse[NotificationResponse],
    summary="Mark Notification as Read (PATCH)",
)
async def mark_notification_read(
    notification_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Marks a single notification as read and returns updated notification."""
    updated = await NotificationService.mark_read(db, notification_id, current_user)
    resp = NotificationResponse(
        notification_id=updated["notification_id"],
        recipient_user_id=updated.get("recipient_user_id") or updated.get("user_id"),
        user_id=updated.get("user_id") or updated.get("recipient_user_id"),
        notification_type=updated["notification_type"],
        type=updated.get("type") or str(updated["notification_type"]),
        category=updated.get("category", "system"),
        priority=updated.get("priority", "normal"),
        channel=updated.get("channel", "in_app"),
        status=updated["status"],
        read=bool(updated.get("read") or updated.get("status") == "read"),
        title=updated["title"],
        body=updated.get("body") or updated.get("message", ""),
        message=updated.get("message") or updated.get("body", ""),
        reference_id=updated.get("reference_id") or updated.get("source_id"),
        reference_type=updated.get("reference_type") or updated.get("source_type"),
        source_id=updated.get("source_id") or updated.get("reference_id"),
        source_type=updated.get("source_type") or updated.get("reference_type"),
        read_at=updated.get("read_at"),
        created_at=updated["created_at"],
        updated_at=updated.get("updated_at", updated["created_at"]),
    )
    return APIResponse(message="Notification marked as read", data=resp)


@router.post(
    "/{notification_id}/unread",
    response_model=APIResponse[NotificationResponse],
    summary="Mark Notification as Unread (POST)",
)
@router.patch(
    "/{notification_id}/unread",
    response_model=APIResponse[NotificationResponse],
    summary="Mark Notification as Unread (PATCH)",
)
async def mark_notification_unread(
    notification_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Marks a single notification as unread and returns updated notification."""
    updated = await NotificationService.mark_unread(db, notification_id, current_user)
    resp = NotificationResponse(
        notification_id=updated["notification_id"],
        recipient_user_id=updated.get("recipient_user_id") or updated.get("user_id"),
        user_id=updated.get("user_id") or updated.get("recipient_user_id"),
        notification_type=updated["notification_type"],
        type=updated.get("type") or str(updated["notification_type"]),
        category=updated.get("category", "system"),
        priority=updated.get("priority", "normal"),
        channel=updated.get("channel", "in_app"),
        status=updated["status"],
        read=bool(updated.get("read") or updated.get("status") == "read"),
        title=updated["title"],
        body=updated.get("body") or updated.get("message", ""),
        message=updated.get("message") or updated.get("body", ""),
        reference_id=updated.get("reference_id") or updated.get("source_id"),
        reference_type=updated.get("reference_type") or updated.get("source_type"),
        source_id=updated.get("source_id") or updated.get("reference_id"),
        source_type=updated.get("source_type") or updated.get("reference_type"),
        read_at=updated.get("read_at"),
        created_at=updated["created_at"],
        updated_at=updated.get("updated_at", updated["created_at"]),
    )
    return APIResponse(message="Notification marked as unread", data=resp)


@router.post(
    "/read-all",
    response_model=APIResponse[dict],
    summary="Mark All Notifications as Read (POST)",
)
@router.patch(
    "/read-all",
    response_model=APIResponse[dict],
    summary="Mark All Notifications as Read (PATCH)",
)
async def mark_all_notifications_read(
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Marks all unread notifications as read for current user."""
    count = await NotificationService.mark_all_read(db, current_user)
    return APIResponse(message=f"Marked {count} notifications as read", data={"updated_count": count, "marked_read": count})


@router.delete(
    "/{notification_id}",
    response_model=APIResponse[dict],
    summary="Delete Notification",
)
async def delete_notification(
    notification_id: str,
    current_user: UserInDB = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_database),
):
    """Soft-deletes a notification from user's inbox."""
    await NotificationService.delete_notification(db, notification_id, current_user)
    return APIResponse(message="Notification deleted successfully", data={"notification_id": notification_id})


async def handle_websocket_notifications(
    websocket: WebSocket,
    db: Optional[AsyncIOMotorDatabase] = None,
):
    """
    Core WebSocket notification connection handler.
    Strict Security Protocol:
    1. Rejects any attempt to pass tokens in URL query string (?token=).
    2. Authenticates via HttpOnly cookie `access_token` or `Authorization: Bearer <token>` header.
    3. Verifies active account status in MongoDB.
    4. Connects and maintains user-specific isolated channel.
    """
    # Security Rule: JWT tokens in URL query string are strictly prohibited
    if "token" in websocket.query_params:
        await websocket.accept()
        await websocket.close(
            code=1008,
            reason="WebSocket token in URL query parameter is prohibited. Authenticate via HttpOnly cookie or Authorization header."
        )
        return

    # Check Sec-WebSocket-Protocol header first
    ws_proto_header: Optional[str] = websocket.headers.get("sec-websocket-protocol")
    selected_subprotocol: Optional[str] = None
    if ws_proto_header:
        selected_subprotocol = ws_proto_header.split(",")[0].strip()

    # Extract token from cookies, Authorization header, or Sec-WebSocket-Protocol
    token: Optional[str] = websocket.cookies.get("access_token")
    if not token:
        auth_header = websocket.headers.get("authorization")
        if auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header[7:].strip()

    if not token and selected_subprotocol and selected_subprotocol.startswith("bearer."):
        token = selected_subprotocol.split(".", 1)[1].strip()

    if not token:
        await websocket.accept(subprotocol=selected_subprotocol)
        await websocket.close(code=1008, reason="Missing authorization credentials")
        return

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            await websocket.accept(subprotocol=selected_subprotocol)
            await websocket.close(code=1008, reason="Invalid token type")
            return
        user_id = payload.get("sub")
        if not user_id:
            await websocket.accept(subprotocol=selected_subprotocol)
            await websocket.close(code=1008, reason="Invalid token payload")
            return
    except Exception:
        await websocket.accept(subprotocol=selected_subprotocol)
        await websocket.close(code=1008, reason="Invalid or expired token")
        return

    # Verify user account validity in MongoDB
    try:
        target_db = db
        if target_db is None:
            from app.dependencies.database import get_database
            from app.main import app
            if get_database in app.dependency_overrides:
                override = app.dependency_overrides[get_database]
                target_db = override() if callable(override) else override
                if hasattr(target_db, "__await__"):
                    target_db = await target_db
            else:
                from app.database.mongodb import get_db
                target_db = get_db()

        user_dict = await target_db[COLLECTION_USERS].find_one({"user_id": user_id, "is_deleted": {"$ne": True}})
        if not user_dict or user_dict.get("account_status") != AccountStatus.ACTIVE.value:
            await websocket.accept(subprotocol=selected_subprotocol)
            await websocket.close(code=1008, reason="User account invalid or inactive")
            return
    except Exception as db_exc:
        logger.warning(f"Database validation error during WebSocket handshake: {db_exc}")
        await websocket.accept(subprotocol=selected_subprotocol)
        await websocket.close(code=1008, reason="Database validation error during WebSocket handshake")
        return

    await manager.connect(user_id, websocket, subprotocol=selected_subprotocol)
    try:
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception:
        manager.disconnect(user_id, websocket)


@router.websocket("/ws")
async def websocket_notifications(
    websocket: WebSocket,
):
    """Primary WebSocket stream endpoint at /api/v1/notifications/ws."""
    await handle_websocket_notifications(websocket, None)
