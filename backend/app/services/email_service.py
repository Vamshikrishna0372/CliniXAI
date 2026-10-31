"""
Email Delivery Service for CliniXAI Phase 9.

Supports HTML and plain-text emails for:
- Email verification
- Password reset
- Appointment booking / rescheduling / cancellation
- Follow-up reminders

Degrades gracefully when EMAIL_ENABLED=False or SMTP credentials are missing.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Dict, Any

from app.core.config import settings
from app.core.logging import logger


class EmailService:
    """Production email delivery service abstraction."""

    @staticmethod
    def is_configured() -> bool:
        """Returns True if email delivery is enabled and SMTP settings are provided."""
        if not settings.EMAIL_ENABLED:
            return False
        if not settings.SMTP_HOST or not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
            return False
        return True

    @classmethod
    async def send_email(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Sends an email via SMTP.
        If EMAIL_ENABLED is False or credentials missing, logs the email dispatch safely without throwing errors.
        """
        if not cls.is_configured():
            logger.info(
                f"[EmailService MOCK/DISABLED] Would send email to '{to_email}' with subject: '{subject}'"
            )
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            msg["To"] = to_email

            if text_content:
                msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                if settings.SMTP_USE_TLS:
                    server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())

            logger.info(f"Successfully sent email to {to_email} (Subject: {subject})")
            return True
        except Exception as exc:
            logger.error(f"Failed to send email to {to_email}: {exc}", exc_info=True)
            return False

    # ── High-Level Business Email Templates ───────────────────────────────────

    @classmethod
    async def send_verification_email(cls, to_email: str, recipient_name: str, verify_url: str) -> bool:
        """Sends email verification link."""
        subject = f"Verify your {settings.APP_NAME} Account"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Welcome to CliniXAI, {recipient_name}!</h2>
            <p>Please verify your email address to activate your clinical portal account.</p>
            <p style="margin: 30px 0;">
                <a href="{verify_url}" style="background-color: #2563eb; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Verify Email Address
                </a>
            </p>
            <p style="color: #666; font-size: 12px;">This link will expire in {settings.VERIFICATION_TOKEN_EXPIRE_HOURS} hours.</p>
        </div>
        """
        text_content = f"Welcome {recipient_name}! Verify your CliniXAI account here: {verify_url}"
        return await cls.send_email(to_email, subject, html_content, text_content)

    @classmethod
    async def send_password_reset_email(cls, to_email: str, recipient_name: str, reset_url: str) -> bool:
        """Sends password reset link."""
        subject = f"Password Reset Request — {settings.APP_NAME}"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Password Reset Request</h2>
            <p>Hello {recipient_name},</p>
            <p>We received a request to reset your password. Click the button below to choose a new password:</p>
            <p style="margin: 30px 0;">
                <a href="{reset_url}" style="background-color: #dc2626; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                    Reset Password
                </a>
            </p>
            <p style="color: #666; font-size: 12px;">If you did not request a password reset, please ignore this email. Link expires in {settings.RESET_TOKEN_EXPIRE_HOURS} hour.</p>
        </div>
        """
        text_content = f"Reset your CliniXAI password: {reset_url}"
        return await cls.send_email(to_email, subject, html_content, text_content)

    @classmethod
    async def send_appointment_email(
        cls,
        to_email: str,
        recipient_name: str,
        action: str,  # "booked", "rescheduled", "cancelled"
        appointment_id: str,
        doctor_name: str,
        department_name: str,
        appointment_date: str,
        slot_time: str,
    ) -> bool:
        """Sends generic non-sensitive appointment confirmation / update email."""
        action_title = action.capitalize()
        subject = f"Appointment {action_title} — {settings.APP_NAME} ({appointment_id})"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Appointment {action_title}</h2>
            <p>Dear {recipient_name},</p>
            <p>Your consultation appointment at <strong>{settings.HOSPITAL_NAME}</strong> has been <strong>{action}</strong>.</p>
            <table style="margin: 20px 0; border-collapse: collapse; width: 100%; max-width: 500px;">
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Appointment ID:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{appointment_id}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Department:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{department_name}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Doctor:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{doctor_name}</td></tr>
                <tr><td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Date & Time:</strong></td><td style="padding: 8px; border-bottom: 1px solid #ddd;">{appointment_date} at {slot_time}</td></tr>
            </table>
            <p style="color: #666; font-size: 13px;">Please arrive 15 minutes prior to your scheduled slot for QR check-in.</p>
        </div>
        """
        text_content = f"Appointment {action_title}: ID {appointment_id} on {appointment_date} at {slot_time} with {doctor_name}."
        return await cls.send_email(to_email, subject, html_content, text_content)

    @classmethod
    async def send_followup_reminder_email(
        cls,
        to_email: str,
        recipient_name: str,
        doctor_name: str,
        followup_date: str,
        notes: Optional[str] = None,
    ) -> bool:
        """Sends follow-up reminder email."""
        subject = f"Clinical Follow-Up Reminder — {settings.APP_NAME}"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Clinical Follow-Up Reminder</h2>
            <p>Dear {recipient_name},</p>
            <p>This is a reminder from <strong>{settings.HOSPITAL_NAME}</strong> regarding your recommended follow-up consultation with <strong>{doctor_name}</strong>.</p>
            <p><strong>Recommended Date:</strong> {followup_date}</p>
            <p style="color: #666; font-size: 13px;">Please log in to your CliniXAI patient portal to schedule your follow-up appointment.</p>
        </div>
        """
        text_content = f"Follow-up reminder with {doctor_name} on {followup_date}. Log in to CliniXAI to schedule."
        return await cls.send_email(to_email, subject, html_content, text_content)

    @classmethod
    async def send_invitation_email(
        cls,
        to_email: str,
        recipient_name: str,
        role_name: str,
        activation_url: str,
    ) -> bool:
        """Sends professional account setup invitation email to provisioned Doctors or Staff."""
        role_title = role_name.replace("_", " ").title()
        subject = f"Account Invitation — {settings.APP_NAME} ({role_title})"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 25px; color: #1e293b; max-width: 600px; margin: 0 auto; border: 1px solid #e2e8f0; border-radius: 8px;">
            <h2 style="color: #0f172a; margin-bottom: 8px;">Welcome to CliniXAI Healthcare</h2>
            <p style="font-size: 16px; color: #475569;">Hello {recipient_name},</p>
            <p style="font-size: 15px; color: #475569; line-height: 1.5;">
                An administrator at <strong>{settings.HOSPITAL_NAME}</strong> has created your <strong>{role_title}</strong> account on the CliniXAI Clinical Decision Support Portal.
            </p>
            <p style="margin: 30px 0; text-align: center;">
                <a href="{activation_url}" style="background-color: #0284c7; color: white; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block;">
                    Activate Your Account
                </a>
            </p>
            <p style="font-size: 13px; color: #64748b; line-height: 1.4;">
                This single-use invitation link will expire in 7 days. You will be prompted to set your secure password upon opening the link.
            </p>
            <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
            <p style="font-size: 12px; color: #94a3b8; text-align: center;">
                If you did not expect this invitation, please contact your hospital system administrator.
            </p>
        </div>
        """
        text_content = f"Hello {recipient_name}! Activate your CliniXAI {role_title} account here: {activation_url}"
        return await cls.send_email(to_email, subject, html_content, text_content)

    @classmethod
    async def send_prescription_email(
        cls,
        to_email: str,
        recipient_name: str,
        prescription_id: str,
        doctor_name: str,
        medication_count: int,
    ) -> bool:
        """Sends prescription notification email to patient."""
        subject = f"Prescription Issued — {settings.APP_NAME} ({prescription_id})"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Prescription Issued</h2>
            <p>Dear {recipient_name},</p>
            <p>Dr. <strong>{doctor_name}</strong> has issued a prescription (<strong>{prescription_id}</strong>) containing {medication_count} medication(s).</p>
            <p style="color: #666; font-size: 13px;">Log in to your CliniXAI portal to view full dosage instructions and details.</p>
        </div>
        """
        text_content = f"Prescription {prescription_id} issued by Dr. {doctor_name} with {medication_count} medication(s)."
        return await cls.send_email(to_email, subject, html_content, text_content)

    @classmethod
    async def send_billing_email(
        cls,
        to_email: str,
        recipient_name: str,
        bill_id: str,
        grand_total: float,
    ) -> bool:
        """Sends bill issued email notification."""
        subject = f"Bill Issued — {settings.APP_NAME} ({bill_id})"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Bill Issued</h2>
            <p>Dear {recipient_name},</p>
            <p>A new bill (<strong>{bill_id}</strong>) for <strong>INR {grand_total:.2f}</strong> has been issued for your consultation at <strong>{settings.HOSPITAL_NAME}</strong>.</p>
            <p style="color: #666; font-size: 13px;">Please log in to your patient portal to review line items and make a payment.</p>
        </div>
        """
        text_content = f"Bill {bill_id} for INR {grand_total:.2f} issued. Log in to CliniXAI to view and pay."
        return await cls.send_email(to_email, subject, html_content, text_content)

    @classmethod
    async def send_payment_email(
        cls,
        to_email: str,
        recipient_name: str,
        bill_id: str,
        payment_id: str,
        amount_paid: float,
        balance_due: float,
    ) -> bool:
        """Sends payment confirmation email notification."""
        subject = f"Payment Receipt — {settings.APP_NAME} ({payment_id})"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px; color: #333;">
            <h2>Payment Confirmation</h2>
            <p>Dear {recipient_name},</p>
            <p>Thank you! We have received your payment of <strong>INR {amount_paid:.2f}</strong> (Receipt: <strong>{payment_id}</strong>) for bill <strong>{bill_id}</strong>.</p>
            <p><strong>Remaining Balance Due:</strong> INR {balance_due:.2f}</p>
        </div>
        """
        text_content = f"Payment receipt {payment_id} received for INR {amount_paid:.2f}. Balance due: INR {balance_due:.2f}."
        return await cls.send_email(to_email, subject, html_content, text_content)


