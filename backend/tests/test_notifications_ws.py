"""Unit and integration tests for Notification WebSocket stream."""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from unittest.mock import AsyncMock, MagicMock

from app.main import app
from app.dependencies.database import get_database
from app.core.security import create_access_token
from app.models.user import UserRole, AccountStatus
from app.database.collections import COLLECTION_USERS


def create_mock_db_ws():
    mock_db = MagicMock()
    users_col = MagicMock()

    async def mock_find_one(query):
        user_id = query.get("user_id")
        if user_id == "USR-ADM001":
            return {
                "user_id": "USR-ADM001",
                "email": "admin@clinixai.com",
                "full_name": "System Admin",
                "role": UserRole.HOSPITAL_ADMIN.value,
                "account_status": AccountStatus.ACTIVE.value,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        if user_id == "USR-INACTIVE":
            return {
                "user_id": "USR-INACTIVE",
                "email": "inactive@clinixai.com",
                "full_name": "Inactive User",
                "role": UserRole.PATIENT.value,
                "account_status": AccountStatus.SUSPENDED.value,
                "created_at": "2026-01-01T00:00:00Z",
                "updated_at": "2026-01-01T00:00:00Z",
            }
        return None

    users_col.find_one = AsyncMock(side_effect=mock_find_one)

    def get_collection(name):
        if name == COLLECTION_USERS:
            return users_col
        col = MagicMock()
        col.find_one = AsyncMock(return_value=None)
        col.count_documents = AsyncMock(return_value=0)
        return col

    mock_db.__getitem__.side_effect = get_collection
    return mock_db


@pytest.fixture
def ws_client():
    mock_db = create_mock_db_ws()
    app.dependency_overrides[get_database] = lambda: mock_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_ws_notifications_missing_token(ws_client):
    """WebSocket connection without token should close cleanly with WS code 1008."""
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with ws_client.websocket_connect("/api/v1/notifications/ws") as ws:
            ws.receive_text()
    assert excinfo.value.code == 1008


def test_ws_notifications_query_token_rejected(ws_client):
    """WebSocket connection with token in query param must be rejected with code 1008."""
    token = create_access_token(user_id="USR-ADM001", role="hospital_admin")
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with ws_client.websocket_connect(f"/api/v1/notifications/ws?token={token}") as ws:
            ws.receive_text()
    assert excinfo.value.code == 1008


def test_ws_notifications_invalid_cookie_token(ws_client):
    """WebSocket connection with bogus cookie token should close with WS code 1008."""
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with ws_client.websocket_connect("/api/v1/notifications/ws", cookies={"access_token": "invalid_token"}) as ws:
            ws.receive_text()
    assert excinfo.value.code == 1008


def test_ws_notifications_inactive_user(ws_client):
    """WebSocket connection for suspended user should close with WS code 1008."""
    token = create_access_token(user_id="USR-INACTIVE", role="patient")
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with ws_client.websocket_connect("/api/v1/notifications/ws", cookies={"access_token": token}) as ws:
            ws.receive_text()
    assert excinfo.value.code == 1008


def test_ws_notifications_success_and_ping_pong(ws_client):
    """Valid authenticated active user via HttpOnly cookie should successfully establish WebSocket session and respond to ping."""
    token = create_access_token(user_id="USR-ADM001", role="hospital_admin")
    with ws_client.websocket_connect("/api/v1/notifications/ws", cookies={"access_token": token}) as websocket:
        websocket.send_text("ping")
        response = websocket.receive_text()
        assert response == "pong"

