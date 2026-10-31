"""Comprehensive Unit & Integration Test Suite for Phase 13: Notifications, Follow-Ups & Communication Workflows."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.follow_up import FollowUpStatus
from app.core.security import create_access_token
from app.services.email_service import EmailService
from app.utils.datetime import utc_now


def create_mock_cursor(return_data=None):
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db_phase13():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
            col.count_documents = AsyncMock(return_value=1)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase13FollowUpsAndNotifications(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 13 Follow-Ups, Notifications, and Email Workflows."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase13()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.doc_user = UserInDB(
            user_id="USR-DOC-RAO-001",
            email="doctor.arjun@clinixai.com",
            full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.pat_user = UserInDB(
            user_id="USR-PAT-ONE-001",
            email="patient.one@clinixai.com",
            full_name="Patient One",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        def mock_user_find_one(query):
            uid = query.get("user_id")
            if uid == "USR-DOC-RAO-001":
                return self.doc_user.model_dump()
            if uid == "USR-PAT-ONE-001":
                return self.pat_user.model_dump()
            return None

        self.mock_db["users"].find_one.side_effect = AsyncMock(side_effect=mock_user_find_one)

        self.doc_token = create_access_token(user_id=self.doc_user.user_id, role=self.doc_user.role.value)
        self.pat_token = create_access_token(user_id=self.pat_user.user_id, role=self.pat_user.role.value)

        self.doc_headers = {"Authorization": f"Bearer {self.doc_token}"}
        self.pat_headers = {"Authorization": f"Bearer {self.pat_token}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_email_service_fallback(self):
        """Verify EmailService degrades gracefully when SMTP is unconfigured."""
        from unittest.mock import patch
        with patch.object(EmailService, "is_configured", return_value=False):
            sent = await EmailService.send_email(
                to_email="test@example.com",
                subject="Test Fallback",
                html_content="<p>Test</p>",
            )
            self.assertTrue(sent, "EmailService should return True in fallback mode.")

    async def test_create_follow_up(self):
        """Test scheduling a follow-up record."""
        payload = {
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "scheduled_date": "2026-08-25T10:00:00Z",
            "reason": "Post-cardiac therapy evaluation",
            "notes": "Monitor resting heart rate.",
        }
        response = await self.client.post("/api/v1/follow-ups", json=payload, headers=self.doc_headers)
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("follow_up_id", data)
        self.assertEqual(data["patient_id"], "PAT-ONE-001")
        self.assertEqual(data["status"], "scheduled")

    async def test_list_follow_ups(self):
        """Test retrieving follow-ups list."""
        sample_fu = {
            "follow_up_id": "FWU-TEST-001",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "scheduled_date": "2026-08-25T10:00:00Z",
            "reason": "Post-op checkup",
            "status": "scheduled",
            "reminder_sent": False,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["follow_ups"].find.return_value = create_mock_cursor([sample_fu])

        response = await self.client.get("/api/v1/follow-ups", headers=self.doc_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total"], 1)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["follow_up_id"], "FWU-TEST-001")

    async def test_update_follow_up_status(self):
        """Test updating a follow-up status to completed."""
        existing_fu = {
            "follow_up_id": "FWU-TEST-001",
            "patient_id": "PAT-ONE-001",
            "doctor_id": "DOC-RAO-001",
            "scheduled_date": "2026-08-25T10:00:00Z",
            "reason": "Post-op checkup",
            "status": "scheduled",
            "reminder_sent": False,
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        updated_fu = dict(existing_fu)
        updated_fu["status"] = "completed"

        self.mock_db["follow_ups"].find_one.return_value = existing_fu
        self.mock_db["follow_ups"].update_one.return_value = MagicMock(modified_count=1)

        # On re-fetch after update
        def mock_find_one(query):
            if query.get("follow_up_id") == "FWU-TEST-001":
                return updated_fu
            return None
        self.mock_db["follow_ups"].find_one.side_effect = AsyncMock(side_effect=mock_find_one)

        response = await self.client.put(
            "/api/v1/follow-ups/FWU-TEST-001",
            json={"status": "completed"},
            headers=self.doc_headers,
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "completed")

    async def test_notifications_unread_count(self):
        """Test retrieving unread notifications count."""
        self.mock_db["notifications"].count_documents.return_value = 3
        response = await self.client.get("/api/v1/notifications/unread-count", headers=self.pat_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["data"]["unread_count"], 3)

    async def test_mark_notification_as_read(self):
        """Test marking a notification as read."""
        sample_notif = {
            "notification_id": "NTF-001",
            "recipient_user_id": "USR-PAT-ONE-001",
            "notification_type": "follow_up_scheduled",
            "channel": "in_app",
            "status": "sent",
            "title": "Follow-Up Scheduled",
            "body": "Your follow-up is scheduled.",
            "sent_at": utc_now().isoformat(),
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["notifications"].find_one.return_value = sample_notif
        self.mock_db["notifications"].update_one.return_value = MagicMock(modified_count=1)

        response = await self.client.patch("/api/v1/notifications/NTF-001/read", headers=self.pat_headers)
        self.assertEqual(response.status_code, 200)
