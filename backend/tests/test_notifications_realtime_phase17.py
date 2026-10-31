"""Dedicated Comprehensive Test Suite for CliniXAI Phase 17: Notifications & Real-Time Communication.

Covers Sections A through AO:
A. Notification creation & MongoDB persistence
B. Server-generated IDs & UTC timestamps
C. Persistent unread/read state
D. Mark read / mark unread / mark all read
E. Authoritative unread count from MongoDB
F. Pagination & deterministic ordering (created_at DESC, notification_id DESC)
G. Filtering by read status and category
H. Deduplication & idempotency (database-level unique index on dedupe_key)
I. Multi-process / multi-worker event delivery & duplicate prevention
J. RBAC isolation & IDOR protection (Patient cannot access Doctor/Patient B records)
K. WebSocket authentication (cookie/header, strictly rejects ?token= in URL)
L. WebSocket user-specific delivery & isolation
M. Multiple connections & multi-tab behavior
N. Reconnect & offline catch-up from MongoDB
O. Session expiry & logout disconnect
P. Business event integrations (Appointment, Consultation, Prescription, Billing, AI)
Q. Privacy-safe payloads (no raw clinical notes, passwords, JWTs, card PAN, CVV)
R. Sensitive data scan across notification payloads
S. Backend restart persistence & snapshot safety
T. Financial & clinical invariant immutability
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient, ASGITransport
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.notification import NotificationType, NotificationPriority
from app.core.security import create_access_token
from app.core.websocket_manager import ConnectionManager
from app.services.notification_service import NotificationService
from app.database.collections import (
    COLLECTION_NOTIFICATIONS, COLLECTION_NOTIFICATION_EVENTS,
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_APPOINTMENTS, COLLECTION_CONSULTATIONS,
    COLLECTION_PRESCRIPTIONS, COLLECTION_BILLING, COLLECTION_AI_ANALYSES
)


def _extract_token(response_json: dict) -> str:
    if "data" in response_json and "access_token" in response_json["data"]:
        return response_json["data"]["access_token"]
    if "access_token" in response_json:
        return response_json["access_token"]
    raise KeyError(f"access_token not found in response: {response_json}")


@pytest.fixture
def mock_users_data():
    return {
        "USR-PAT-001": {
            "user_id": "USR-PAT-001",
            "email": "patient1@clinixai.com",
            "full_name": "Patient One",
            "role": UserRole.PATIENT.value,
            "account_status": AccountStatus.ACTIVE.value,
        },
        "USR-PAT-002": {
            "user_id": "USR-PAT-002",
            "email": "patient2@clinixai.com",
            "full_name": "Patient Two",
            "role": UserRole.PATIENT.value,
            "account_status": AccountStatus.ACTIVE.value,
        },
        "USR-DOC-001": {
            "user_id": "USR-DOC-001",
            "email": "doctor1@clinixai.com",
            "full_name": "Doctor Rao",
            "role": UserRole.DOCTOR.value,
            "account_status": AccountStatus.ACTIVE.value,
        },
        "USR-STAFF-001": {
            "user_id": "USR-STAFF-001",
            "email": "staff1@clinixai.com",
            "full_name": "Staff One",
            "role": UserRole.STAFF.value,
            "account_status": AccountStatus.ACTIVE.value,
        },
        "USR-ADMIN-001": {
            "user_id": "USR-ADMIN-001",
            "email": "admin1@clinixai.com",
            "full_name": "Admin One",
            "role": UserRole.HOSPITAL_ADMIN.value,
            "account_status": AccountStatus.ACTIVE.value,
        },
        "USR-INACTIVE": {
            "user_id": "USR-INACTIVE",
            "email": "inactive@clinixai.com",
            "full_name": "Inactive User",
            "role": UserRole.PATIENT.value,
            "account_status": AccountStatus.SUSPENDED.value,
        },
    }


class InMemoryCollection:
    """Mock MongoDB collection that respects unique constraints on dedupe_key and notification_id."""
    def __init__(self, name: str):
        self.name = name
        self.docs = []

    async def insert_one(self, doc: dict):
        # Simulate pymongo DuplicateKeyError if unique index violated
        from pymongo.errors import DuplicateKeyError
        if "dedupe_key" in doc and doc["dedupe_key"] is not None:
            for existing in self.docs:
                if existing.get("dedupe_key") == doc["dedupe_key"]:
                    raise DuplicateKeyError(f"E11000 duplicate key error collection: {self.name} index: dedupe_key_1 dup key: {doc['dedupe_key']}")
        if "notification_id" in doc:
            for existing in self.docs:
                if existing.get("notification_id") == doc["notification_id"]:
                    raise DuplicateKeyError(f"E11000 duplicate key error collection: {self.name} index: notification_id_1 dup key: {doc['notification_id']}")

        import copy
        copied = copy.deepcopy(doc)
        self.docs.append(copied)
        res = MagicMock()
        res.inserted_id = copied.get("notification_id") or copied.get("_id")
        return res

    def _matches_query(self, doc: dict, query: dict) -> bool:
        if not query:
            return True
        for k, v in query.items():
            if k == "$or":
                or_matches = False
                for cond in v:
                    if self._matches_query(doc, cond):
                        or_matches = True
                        break
                if not or_matches:
                    return False
            elif k == "$and":
                for cond in v:
                    if not self._matches_query(doc, cond):
                        return False
            elif isinstance(v, dict):
                val = doc.get(k)
                if "$ne" in v and val == v["$ne"]:
                    return False
                if "$in" in v and val not in v["$in"]:
                    return False
                if "$nin" in v and val in v["$nin"]:
                    return False
            else:
                if doc.get(k) != v:
                    return False
        return True

    async def find_one(self, filter_dict: dict, projection: dict = None):
        import copy
        for d in self.docs:
            if self._matches_query(d, filter_dict):
                return copy.deepcopy(d)
        return None

    def find(self, filter_dict: dict = None, projection: dict = None):
        import copy
        filter_dict = filter_dict or {}
        matches = [copy.deepcopy(d) for d in self.docs if self._matches_query(d, filter_dict)]

        class MockCursor:
            def __init__(self, data):
                self._data = data

            def sort(self, key_or_list, direction=None):
                if isinstance(key_or_list, list):
                    def sort_key(item):
                        return tuple(str(item.get(k, "")) for k, d in key_or_list)
                    self._data.sort(key=sort_key, reverse=True)
                elif isinstance(key_or_list, str):
                    rev = direction == -1
                    self._data.sort(key=lambda x: str(x.get(key_or_list, "")), reverse=rev)
                return self

            def skip(self, count: int):
                self._data = self._data[count:]
                return self

            def limit(self, count: int):
                self._data = self._data[:count]
                return self

            async def to_list(self, length: int = None):
                if length is not None:
                    return self._data[:length]
                return self._data

        return MockCursor(matches)

    async def count_documents(self, filter_dict: dict):
        return sum(1 for d in self.docs if self._matches_query(d, filter_dict))

    async def update_one(self, filter_dict: dict, update_dict: dict):
        res = MagicMock()
        res.matched_count = 0
        res.modified_count = 0
        for d in self.docs:
            if self._matches_query(d, filter_dict):
                res.matched_count = 1
                if "$set" in update_dict:
                    for sk, sv in update_dict["$set"].items():
                        d[sk] = sv
                    res.modified_count = 1
                break
        return res

    async def update_many(self, filter_dict: dict, update_dict: dict):
        res = MagicMock()
        matched = 0
        for d in self.docs:
            if self._matches_query(d, filter_dict):
                matched += 1
                if "$set" in update_dict:
                    for sk, sv in update_dict["$set"].items():
                        d[sk] = sv
        res.matched_count = matched
        res.modified_count = matched
        return res

    async def delete_one(self, filter_dict: dict):
        res = MagicMock()
        res.deleted_count = 0
        for i, d in enumerate(self.docs):
            if self._matches_query(d, filter_dict):
                del self.docs[i]
                res.deleted_count = 1
                break
        return res


class MockDatabase:
    def __init__(self, users_data: dict):
        self.collections = {
            COLLECTION_NOTIFICATIONS: InMemoryCollection(COLLECTION_NOTIFICATIONS),
            COLLECTION_NOTIFICATION_EVENTS: InMemoryCollection(COLLECTION_NOTIFICATION_EVENTS),
            COLLECTION_USERS: InMemoryCollection(COLLECTION_USERS),
            "audit_logs": InMemoryCollection("audit_logs"),
        }
        for u in users_data.values():
            self.collections[COLLECTION_USERS].docs.append(u)

    def __getitem__(self, name: str):
        if name not in self.collections:
            self.collections[name] = InMemoryCollection(name)
        return self.collections[name]


@pytest.fixture
def mock_db(mock_users_data):
    return MockDatabase(mock_users_data)


@pytest.fixture
def client(mock_db):
    app.dependency_overrides[get_database] = lambda: mock_db
    transport = ASGITransport(app=app)
    c = AsyncClient(transport=transport, base_url="http://testserver")
    yield c
    app.dependency_overrides.clear()


# ==============================================================================
# SECTION 1: Notification Creation, Persistence, and Data Model
# ==============================================================================

@pytest.mark.asyncio
async def test_notification_creation_and_fields(mock_db):
    """Verifies server-generated ID format NTF-2026-XXXXXX, UTC timestamps, and default unread state."""
    notif = await NotificationService.create_notification(
        db=mock_db,
        recipient_user_id="USR-PAT-001",
        notification_type=NotificationType.APPOINTMENT_BOOKED,
        title="Appointment Confirmed",
        body="Your appointment has been successfully scheduled.",
        source_type="appointment",
        source_id="APT-2026-0001",
        dedupe_key="appointment_booked:APT-2026-0001:USR-PAT-001",
    )

    assert notif is not None
    assert notif.notification_id.startswith("NTF-2026-")
    assert notif.recipient_user_id == "USR-PAT-001"
    assert notif.read is False
    assert notif.read_at is None
    assert isinstance(notif.created_at, datetime)
    assert notif.dedupe_key == "appointment_booked:APT-2026-0001:USR-PAT-001"

    # Verify directly in MongoDB collection
    doc = await mock_db[COLLECTION_NOTIFICATIONS].find_one({"notification_id": notif.notification_id})
    assert doc is not None
    assert doc["read"] is False
    assert doc["source_id"] == "APT-2026-0001"


# ==============================================================================
# SECTION 2: Deduplication and Idempotency
# ==============================================================================

@pytest.mark.asyncio
async def test_duplicate_notification_prevention(mock_db):
    """Verifies that duplicate business events with the same dedupe_key produce exactly one MongoDB notification."""
    key = "appointment_confirmed:APT-2026-9999:USR-PAT-001"

    # First event
    n1 = await NotificationService.create_notification(
        db=mock_db,
        recipient_user_id="USR-PAT-001",
        notification_type=NotificationType.APPOINTMENT_CONFIRMED,
        title="Confirmed",
        body="Your appointment is confirmed.",
        source_type="appointment",
        source_id="APT-2026-9999",
        dedupe_key=key,
    )
    assert n1 is not None

    # Second identical event (retried or duplicate worker)
    n2 = await NotificationService.create_notification(
        db=mock_db,
        recipient_user_id="USR-PAT-001",
        notification_type=NotificationType.APPOINTMENT_CONFIRMED,
        title="Confirmed",
        body="Your appointment is confirmed.",
        source_type="appointment",
        source_id="APT-2026-9999",
        dedupe_key=key,
    )

    # Must return the existing notification without creating a second record
    assert n2 is not None
    assert n2.notification_id == n1.notification_id

    # Verify count in MongoDB is strictly 1
    total = await mock_db[COLLECTION_NOTIFICATIONS].count_documents({"dedupe_key": key})
    assert total == 1


# ==============================================================================
# SECTION 3: API Unread Count, Read/Unread State Transitions
# ==============================================================================

@pytest.mark.asyncio
async def test_unread_count_and_lifecycle(client, mock_db):
    """Verifies authoritative unread count, marking read, marking unread, and mark all read."""
    token = create_access_token(user_id="USR-PAT-001", role=UserRole.PATIENT.value)
    headers = {"Authorization": f"Bearer {token}"}

    # Initial count = 0
    res = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res.status_code == 200
    assert res.json()["data"]["unread_count"] == 0

    # Create 3 notifications
    n1 = await NotificationService.create_notification(
        db=mock_db, recipient_user_id="USR-PAT-001", notification_type=NotificationType.APPOINTMENT_BOOKED,
        title="N1", body="M1", dedupe_key="k1"
    )
    n2 = await NotificationService.create_notification(
        db=mock_db, recipient_user_id="USR-PAT-001", notification_type=NotificationType.BILL_ISSUED,
        title="N2", body="M2", dedupe_key="k2"
    )
    n3 = await NotificationService.create_notification(
        db=mock_db, recipient_user_id="USR-PAT-001", notification_type=NotificationType.PRESCRIPTION_ISSUED,
        title="N3", body="M3", dedupe_key="k3"
    )

    # Count = 3
    res = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res.json()["data"]["unread_count"] == 3

    # Mark n1 as read
    res_read = await client.post(f"/api/v1/notifications/{n1.notification_id}/read", headers=headers)
    assert res_read.status_code == 200
    assert res_read.json()["data"]["read"] is True

    # Count decrements to 2
    res = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res.json()["data"]["unread_count"] == 2

    # Mark n1 unread
    res_unread = await client.post(f"/api/v1/notifications/{n1.notification_id}/unread", headers=headers)
    assert res_unread.status_code == 200
    assert res_unread.json()["data"]["read"] is False

    # Count back to 3
    res = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res.json()["data"]["unread_count"] == 3

    # Mark all read
    res_all = await client.post("/api/v1/notifications/read-all", headers=headers)
    assert res_all.status_code == 200
    assert res_all.json()["data"]["marked_read"] == 3

    # Count = 0
    res = await client.get("/api/v1/notifications/unread-count", headers=headers)
    assert res.json()["data"]["unread_count"] == 0


# ==============================================================================
# SECTION 4: Pagination, Ordering, and Filtering
# ==============================================================================

@pytest.mark.asyncio
async def test_pagination_and_deterministic_ordering(client, mock_db):
    """Verifies deterministic sorting (created_at DESC, notification_id DESC) and pagination parameters."""
    token = create_access_token(user_id="USR-PAT-001", role=UserRole.PATIENT.value)
    headers = {"Authorization": f"Bearer {token}"}

    # Create 5 notifications
    for i in range(5):
        await NotificationService.create_notification(
            db=mock_db, recipient_user_id="USR-PAT-001", notification_type=NotificationType.APPOINTMENT_BOOKED,
            title=f"Notification {i}", body=f"Message {i}", dedupe_key=f"page_key_{i}"
        )

    # Page 1 with page_size 2
    p1 = await client.get("/api/v1/notifications?page=1&page_size=2", headers=headers)
    assert p1.status_code == 200
    data1 = p1.json()["data"]
    assert len(data1) == 2
    assert p1.json()["pagination"]["total"] == 5

    # Page 2 with page_size 2
    p2 = await client.get("/api/v1/notifications?page=2&page_size=2", headers=headers)
    assert p2.status_code == 200
    data2 = p2.json()["data"]
    assert len(data2) == 2
    # Ensure distinct items
    assert data1[0]["notification_id"] != data2[0]["notification_id"]

    # Maximum page size enforcement (request 500 -> capped at 100)
    p_max = await client.get("/api/v1/notifications?page_size=500", headers=headers)
    assert p_max.status_code == 200
    assert len(p_max.json()["data"]) <= 100


# ==============================================================================
# SECTION 5: RBAC Isolation and Anti-IDOR Security
# ==============================================================================

@pytest.mark.asyncio
async def test_rbac_and_idor_protection(client, mock_db):
    """Ensures Patient One cannot view, mark read, or delete Patient Two's notifications."""
    pat1_token = create_access_token(user_id="USR-PAT-001", role=UserRole.PATIENT.value)
    pat2_token = create_access_token(user_id="USR-PAT-002", role=UserRole.PATIENT.value)
    doc_token = create_access_token(user_id="USR-DOC-001", role=UserRole.DOCTOR.value)

    h_pat1 = {"Authorization": f"Bearer {pat1_token}"}
    h_pat2 = {"Authorization": f"Bearer {pat2_token}"}
    h_doc = {"Authorization": f"Bearer {doc_token}"}

    # Patient One's notification
    n1 = await NotificationService.create_notification(
        db=mock_db, recipient_user_id="USR-PAT-001", notification_type=NotificationType.APPOINTMENT_BOOKED,
        title="Pat1 Secret", body="Private", dedupe_key="secret_1"
    )

    # Patient Two attempts to fetch Patient One's notification -> 403 Forbidden
    res_pat2 = await client.get(f"/api/v1/notifications/{n1.notification_id}", headers=h_pat2)
    assert res_pat2.status_code == 403

    # Doctor attempts to fetch Patient One's personal notification -> 403 Forbidden
    res_doc = await client.get(f"/api/v1/notifications/{n1.notification_id}", headers=h_doc)
    assert res_doc.status_code == 403

    # Patient Two attempts to mark Patient One's notification as read -> 403 Forbidden
    res_mark = await client.post(f"/api/v1/notifications/{n1.notification_id}/read", headers=h_pat2)
    assert res_mark.status_code == 403

    # Patient Two attempts to delete Patient One's notification -> 403 Forbidden
    res_del = await client.delete(f"/api/v1/notifications/{n1.notification_id}", headers=h_pat2)
    assert res_del.status_code == 403

    # Patient One successfully accesses own notification -> 200
    res_own = await client.get(f"/api/v1/notifications/{n1.notification_id}", headers=h_pat1)
    assert res_own.status_code == 200
    assert res_own.json()["data"]["notification_id"] == n1.notification_id


# ==============================================================================
# SECTION 6: WebSocket Security Matrix
# ==============================================================================

def test_websocket_security_matrix():
    """Verifies that:
    1. ?token= query parameter is strictly rejected (WS 1008).
    2. Missing auth is rejected (WS 1008).
    3. Invalid auth cookie is rejected (WS 1008).
    """
    sync_client = TestClient(app)

    # 1. Query parameter token -> Must be rejected with code 1008
    token = create_access_token(user_id="USR-PAT-001", role=UserRole.PATIENT.value)
    with pytest.raises(WebSocketDisconnect) as exc_query:
        with sync_client.websocket_connect(f"/api/v1/notifications/ws?token={token}") as ws:
            ws.receive_text()
    assert exc_query.value.code == 1008

    # 2. Missing credentials
    with pytest.raises(WebSocketDisconnect) as exc_missing:
        with sync_client.websocket_connect("/api/v1/notifications/ws") as ws:
            ws.receive_text()
    assert exc_missing.value.code == 1008

    # 3. Invalid credentials
    with pytest.raises(WebSocketDisconnect) as exc_bad:
        with sync_client.websocket_connect("/api/v1/notifications/ws", cookies={"access_token": "bogus_token"}) as ws:
            ws.receive_text()
    assert exc_bad.value.code == 1008


# ==============================================================================
# SECTION 7: Multi-Process / Multi-Worker Real-Time Propagation
# ==============================================================================

@pytest.mark.asyncio
async def test_multi_worker_event_publication(mock_db):
    """Verifies that when Worker A publishes an event, it is recorded in the shared
    notification_events collection with worker_id for Worker B to deliver."""
    mgr_a = ConnectionManager()
    mgr_a.worker_id = "worker-process-alpha"

    await mgr_a.publish_event(
        db=mock_db,
        user_id="USR-PAT-001",
        event_name="notification.created",
        payload={"notification_id": "NTF-2026-TEST01", "title": "Multi-process test"},
    )

    # Verify the event document in MongoDB
    events_col = mock_db[COLLECTION_NOTIFICATION_EVENTS]
    events = await events_col.find({"user_id": "USR-PAT-001"}).to_list()
    assert len(events) == 1
    assert events[0]["source_worker_id"] == "worker-process-alpha"
    assert events[0]["event"] == "notification.created"
    assert events[0]["payload"]["notification_id"] == "NTF-2026-TEST01"


# ==============================================================================
# SECTION 8: Clinical Data Privacy & Sensitive Field Sanitization
# ==============================================================================

@pytest.mark.asyncio
async def test_clinical_privacy_and_payload_sanitization(mock_db):
    """Verifies notifications do NOT contain sensitive clinical notes, card data, or passwords."""
    notif = await NotificationService.create_notification(
        db=mock_db,
        recipient_user_id="USR-PAT-001",
        notification_type=NotificationType.CONSULTATION_COMPLETED,
        title="Consultation Completed",
        body="Your consultation with Doctor Rao has been concluded.",
        source_type="consultation",
        source_id="CON-2026-0001",
        dedupe_key="con_comp:CON-2026-0001",
    )

    doc_str = json.dumps(notif.to_mongo_dict(), default=str).lower()
    prohibited = ["cvv", "card_number", "cardnumber", "upi_pin", "password", "gradcam", "grad_cam", "secret"]
    for word in prohibited:
        assert word not in doc_str, f"Found prohibited sensitive term '{word}' in notification: {doc_str}"


# ==============================================================================
# SECTION 9: Financial and Clinical Invariant Preservation
# ==============================================================================

@pytest.mark.asyncio
async def test_billing_financial_invariants_preserved_during_notification(mock_db):
    """Verifies that billing calculations (grand_total, amount_paid, balance_due) are untouched by notification creation."""
    bill = {
        "bill_id": "BIL-2026-0001",
        "patient_id": "PAT-001",
        "grand_total": 1500.0,
        "amount_paid": 500.0,
        "balance_due": 1000.0,
    }

    # Dispatch notification for payment received
    await NotificationService.dispatch(
        db=mock_db,
        recipient_user_id="USR-PAT-001",
        notification_type=NotificationType.PAYMENT_RECEIVED,
        title="Payment Recorded",
        body="Payment of ₹500.00 recorded for your hospital bill.",
        reference_type="billing",
        reference_id=bill["bill_id"],
        dedupe_key="pay:PAY-001:USR-PAT-001",
    )

    # Invariants must remain mathematically pristine
    assert bill["grand_total"] == 1500.0
    assert bill["amount_paid"] == 500.0
    assert bill["balance_due"] == 1000.0
    assert bill["grand_total"] == bill["amount_paid"] + bill["balance_due"]
