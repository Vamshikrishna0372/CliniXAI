"""Comprehensive Unit & Integration Test Suite for Phase 15: Notifications, Alerts, Email, SMTP & Real-Time Communication."""

import unittest
from unittest.mock import AsyncMock, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.dependencies.database import get_database
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.models.notification import NotificationType, NotificationChannel, NotificationStatus
from app.core.security import create_access_token
from app.services.notification_service import NotificationService
from app.services.email_service import EmailService
from app.utils.datetime import utc_now


def create_mock_cursor(return_data=None):
    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    mock_cursor.to_list = AsyncMock(return_value=return_data if return_data is not None else [])
    return mock_cursor


def create_mock_db_phase15():
    collections = {}

    def get_collection(name):
        if name not in collections:
            col = MagicMock()
            col.find_one = AsyncMock(return_value=None)
            col.insert_one = AsyncMock(return_value=None)
            col.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
            col.update_many = AsyncMock(return_value=MagicMock(modified_count=2))
            col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
            col.count_documents = AsyncMock(return_value=2)
            col.find = MagicMock(return_value=create_mock_cursor([]))
            collections[name] = col
        return collections[name]

    mock_db = MagicMock()
    mock_db.__getitem__.side_effect = get_collection
    return mock_db


class TestPhase15NotificationsAndEmail(unittest.IsolatedAsyncioTestCase):
    """Test suite for Phase 15 Notifications, Real-Time WebSockets, SMTP Email Delivery, and Security."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

        self.mock_db = create_mock_db_phase15()
        app.dependency_overrides[get_database] = lambda: self.mock_db

        self.pat_user_1 = UserInDB(
            user_id="USR-PAT-ONE-001",
            email="patient.one@clinixai.com",
            full_name="Patient One",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.pat_user_2 = UserInDB(
            user_id="USR-PAT-TWO-002",
            email="patient.two@clinixai.com",
            full_name="Patient Two",
            role=UserRole.PATIENT,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        self.doc_user = UserInDB(
            user_id="USR-DOC-RAO-001",
            email="doctor.arjun@clinixai.com",
            full_name="Dr. Arjun Rao",
            role=UserRole.DOCTOR,
            auth_provider=AuthProvider.LOCAL,
            account_status=AccountStatus.ACTIVE,
        )

        def mock_user_find_one(query):
            uid = query.get("user_id")
            if uid == "USR-PAT-ONE-001":
                return self.pat_user_1.model_dump()
            if uid == "USR-PAT-TWO-002":
                return self.pat_user_2.model_dump()
            if uid == "USR-DOC-RAO-001":
                return self.doc_user.model_dump()
            return None

        self.mock_db["users"].find_one.side_effect = AsyncMock(side_effect=mock_user_find_one)

        self.pat1_token = create_access_token(user_id=self.pat_user_1.user_id, role=self.pat_user_1.role.value)
        self.pat2_token = create_access_token(user_id=self.pat_user_2.user_id, role=self.pat_user_2.role.value)
        self.doc_token = create_access_token(user_id=self.doc_user.user_id, role=self.doc_user.role.value)

        self.pat1_headers = {"Authorization": f"Bearer {self.pat1_token}"}
        self.pat2_headers = {"Authorization": f"Bearer {self.pat2_token}"}
        self.doc_headers = {"Authorization": f"Bearer {self.doc_token}"}

    async def asyncTearDown(self) -> None:
        await self.client.aclose()
        app.dependency_overrides.clear()

    async def test_notification_service_dispatch(self):
        """Test dispatching a notification stores record in MongoDB and triggers WebSocket push."""
        notif = await NotificationService.dispatch(
            db=self.mock_db,
            recipient_user_id="USR-PAT-ONE-001",
            notification_type=NotificationType.APPOINTMENT_BOOKED,
            title="Appointment Confirmed",
            body="Your appointment with Dr. Arjun Rao is confirmed.",
            reference_id="APT-001",
            reference_type="appointment",
        )
        self.assertEqual(notif.recipient_user_id, "USR-PAT-ONE-001")
        self.assertEqual(notif.notification_type, NotificationType.APPOINTMENT_BOOKED)
        self.mock_db["notifications"].insert_one.assert_called_once()

    async def test_list_notifications_inbox_isolation(self):
        """Test listing notifications returns user-scoped records."""
        sample_notif = {
            "notification_id": "NTF-100",
            "recipient_user_id": "USR-PAT-ONE-001",
            "notification_type": "appointment_booked",
            "channel": "in_app",
            "status": "sent",
            "title": "Appointment Confirmed",
            "body": "Your appointment is confirmed.",
            "reference_id": "APT-100",
            "reference_type": "appointment",
            "sent_at": utc_now().isoformat(),
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["notifications"].find.return_value = create_mock_cursor([sample_notif])

        response = await self.client.get("/api/v1/notifications", headers=self.pat1_headers)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("data", data)
        self.assertEqual(data["data"][0]["notification_id"], "NTF-100")

    async def test_mark_notification_read_and_unread(self):
        """Test marking a notification as read and then unread."""
        sample_notif = {
            "notification_id": "NTF-101",
            "recipient_user_id": "USR-PAT-ONE-001",
            "notification_type": "clinical",
            "channel": "in_app",
            "status": "sent",
            "title": "Prescription Issued",
            "body": "Your prescription is ready.",
            "sent_at": utc_now().isoformat(),
            "created_at": utc_now().isoformat(),
            "updated_at": utc_now().isoformat(),
        }
        self.mock_db["notifications"].find_one.return_value = sample_notif

        # Mark Read
        res_read = await self.client.patch("/api/v1/notifications/NTF-101/read", headers=self.pat1_headers)
        self.assertEqual(res_read.status_code, 200)

        # Mark Unread
        res_unread = await self.client.patch("/api/v1/notifications/NTF-101/unread", headers=self.pat1_headers)
        self.assertEqual(res_unread.status_code, 200)

    async def test_mark_all_read(self):
        """Test marking all unread notifications as read."""
        response = await self.client.patch("/api/v1/notifications/read-all", headers=self.pat1_headers)
        self.assertEqual(response.status_code, 200)

    async def test_delete_notification(self):
        """Test deleting a notification document."""
        sample_notif = {
            "notification_id": "NTF-102",
            "recipient_user_id": "USR-PAT-ONE-001",
            "status": "sent",
        }
        self.mock_db["notifications"].find_one.return_value = sample_notif

        response = await self.client.delete("/api/v1/notifications/NTF-102", headers=self.pat1_headers)
        self.assertEqual(response.status_code, 200)

    async def test_notification_ownership_isolation_forbidden(self):
        """Verify Patient 2 cannot mark Patient 1's notification as read (403 Forbidden)."""
        sample_notif = {
            "notification_id": "NTF-PAT1-ONLY",
            "recipient_user_id": "USR-PAT-ONE-001", # Belongs to Patient 1
            "status": "sent",
        }
        self.mock_db["notifications"].find_one.return_value = sample_notif

        response = await self.client.patch("/api/v1/notifications/NTF-PAT1-ONLY/read", headers=self.pat2_headers)
        self.assertEqual(response.status_code, 403)

    async def test_email_service_dispatches(self):
        """Test EmailService templates for appointment, follow-up, prescription, billing, and payment."""
        from unittest.mock import patch
        with patch.object(EmailService, "is_configured", return_value=False):
            sent_appt = await EmailService.send_appointment_email(
                to_email="patient.one@clinixai.com",
                recipient_name="Patient One",
                action="booked",
                appointment_id="APT-001",
                doctor_name="Dr. Arjun Rao",
                department_name="Cardiology",
                appointment_date="2026-08-20",
                slot_time="10:00 AM",
            )
            self.assertTrue(sent_appt)

            sent_fu = await EmailService.send_followup_reminder_email(
                to_email="patient.one@clinixai.com",
                recipient_name="Patient One",
                doctor_name="Dr. Arjun Rao",
                followup_date="2026-08-25",
            )
            self.assertTrue(sent_fu)

            sent_rx = await EmailService.send_prescription_email(
                to_email="patient.one@clinixai.com",
                recipient_name="Patient One",
                prescription_id="PRX-001",
                doctor_name="Dr. Arjun Rao",
                medication_count=2,
            )
            self.assertTrue(sent_rx)

            sent_bill = await EmailService.send_billing_email(
                to_email="patient.one@clinixai.com",
                recipient_name="Patient One",
                bill_id="BIL-001",
                grand_total=1500.0,
            )
            self.assertTrue(sent_bill)

            sent_pay = await EmailService.send_payment_email(
                to_email="patient.one@clinixai.com",
                recipient_name="Patient One",
                bill_id="BIL-001",
                payment_id="PAY-001",
                amount_paid=1500.0,
                balance_due=0.0,
            )
            self.assertTrue(sent_pay)

