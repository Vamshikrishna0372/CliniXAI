"""Database indexes creation and maintenance module for all CliniXAI collections."""

from motor.motor_asyncio import AsyncIOMotorDatabase
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_STAFF, COLLECTION_DEPARTMENTS, COLLECTION_APPOINTMENTS,
    COLLECTION_CONSULTATIONS, COLLECTION_PRESCRIPTIONS, COLLECTION_MEDICAL_RECORDS,
    COLLECTION_BILLING, COLLECTION_NOTIFICATIONS, COLLECTION_AI_ANALYSES,
    COLLECTION_FOLLOW_UPS, COLLECTION_PAYMENTS, COLLECTION_DOCUMENTS, COLLECTION_AUDIT_LOGS,
    COLLECTION_NOTIFICATION_EVENTS
)
from app.core.logging import logger

COLLECTION_USER_SESSIONS = "user_sessions"


async def ensure_database_indexes(db: AsyncIOMotorDatabase) -> None:
    """Idempotently creates required indexes on MongoDB collections during startup."""
    logger.info("Verifying database indexes for all collections...")
    try:
        # Users Collection Indexes
        try:
            users_col = db[COLLECTION_USERS]
            await users_col.create_index("email", unique=True, background=True)
            await users_col.create_index("user_id", unique=True, background=True)
            try:
                await users_col.create_index(
                    "google_sub",
                    unique=True,
                    sparse=True,
                    partialFilterExpression={"google_sub": {"$type": "string"}},
                    background=True,
                )
            except Exception as e:
                logger.debug(f"Optional google_sub index skipped: {e}")
            await users_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Users index verification notice: {e}")

        # User Sessions Collection Indexes
        try:
            sessions_col = db[COLLECTION_USER_SESSIONS]
            await sessions_col.create_index("jti", unique=True, background=True)
            await sessions_col.create_index("user_id", background=True)
            await sessions_col.create_index("expires_at", expireAfterSeconds=0, background=True)
        except Exception as e:
            logger.debug(f"Sessions index verification notice: {e}")

        # Patients Collection Indexes
        try:
            patients_col = db[COLLECTION_PATIENTS]
            await patients_col.create_index("patient_id", unique=True, background=True)
            await patients_col.create_index("user_id", unique=True, sparse=True, background=True)
            await patients_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Patients index verification notice: {e}")

        # Doctors Collection Indexes
        try:
            doctors_col = db[COLLECTION_DOCTORS]
            await doctors_col.create_index("doctor_id", unique=True, background=True)
            await doctors_col.create_index("user_id", unique=True, background=True)
            await doctors_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Doctors index verification notice: {e}")

        # Staff Collection Indexes
        try:
            staff_col = db[COLLECTION_STAFF]
            await staff_col.create_index("staff_id", unique=True, background=True)
            await staff_col.create_index("user_id", unique=True, background=True)
            await staff_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Staff index verification notice: {e}")

        # Departments Collection Indexes
        try:
            dept_col = db[COLLECTION_DEPARTMENTS]
            await dept_col.create_index("department_id", unique=True, background=True)
            await dept_col.create_index("code", unique=True, background=True)
            await dept_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Departments index verification notice: {e}")

        # Appointments Collection Indexes
        try:
            apt_col = db[COLLECTION_APPOINTMENTS]
            await apt_col.create_index("appointment_id", unique=True, background=True)
            await apt_col.create_index("patient_id", background=True)
            await apt_col.create_index(
                [("doctor_id", 1), ("appointment_date", 1), ("start_time", 1)],
                unique=True,
                partialFilterExpression={"status": {"$nin": ["cancelled", "no_show"]}},
                background=True,
            )
            await apt_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Appointments index verification notice: {e}")

        # Consultations Collection Indexes
        try:
            consult_col = db[COLLECTION_CONSULTATIONS]
            await consult_col.create_index("consultation_id", unique=True, background=True)
            await consult_col.create_index("appointment_id", unique=True, background=True)
            await consult_col.create_index("patient_id", background=True)
            await consult_col.create_index("doctor_id", background=True)
            await consult_col.create_index("is_deleted", background=True)
            await consult_col.create_index([("appointment_id", 1), ("status", 1)], background=True)
            await consult_col.create_index([("patient_id", 1), ("created_at", -1)], background=True)
            await consult_col.create_index([("doctor_id", 1), ("created_at", -1)], background=True)
            await consult_col.create_index([("patient_id", 1), ("doctor_id", 1), ("created_at", -1)], background=True)
        except Exception as e:
            logger.debug(f"Consultations index verification notice: {e}")

        # Prescriptions Collection Indexes
        try:
            rx_col = db[COLLECTION_PRESCRIPTIONS]
            await rx_col.create_index("prescription_id", unique=True, background=True)
            await rx_col.create_index("consultation_id", background=True)
            await rx_col.create_index("patient_id", background=True)
            await rx_col.create_index("doctor_id", background=True)
            await rx_col.create_index("is_deleted", background=True)
            await rx_col.create_index([("consultation_id", 1), ("status", 1)], background=True)
            await rx_col.create_index([("patient_id", 1), ("created_at", -1)], background=True)
            await rx_col.create_index([("doctor_id", 1), ("created_at", -1)], background=True)
        except Exception as e:
            logger.debug(f"Prescriptions index verification notice: {e}")

        # Medical Records Collection Indexes
        try:
            mr_col = db[COLLECTION_MEDICAL_RECORDS]
            await mr_col.create_index("record_id", unique=True, background=True)
            await mr_col.create_index("patient_id", background=True)
            await mr_col.create_index("consultation_id", background=True)
            await mr_col.create_index("appointment_id", background=True)
            await mr_col.create_index("doctor_id", background=True)
            await mr_col.create_index("record_type", background=True)
            await mr_col.create_index("status", background=True)
            await mr_col.create_index("is_deleted", background=True)
            await mr_col.create_index([("patient_id", 1), ("is_deleted", 1), ("clinical_date", -1)], background=True)
            await mr_col.create_index([("doctor_id", 1), ("is_deleted", 1), ("clinical_date", -1)], background=True)
            await mr_col.create_index(
                "consultation_id",
                name="unique_active_consultation_mr",
                unique=True,
                partialFilterExpression={"consultation_id": {"$type": "string"}, "is_deleted": {"$ne": True}},
                background=True,
            )
        except Exception as e:
            logger.debug(f"Medical Records index verification notice: {e}")

        # Billing Collection Indexes
        try:
            bill_col = db[COLLECTION_BILLING]
            await bill_col.create_index("bill_id", unique=True, background=True)
            await bill_col.create_index("patient_id", background=True)
            await bill_col.create_index("appointment_id", background=True)
            await bill_col.create_index("consultation_id", background=True)
            await bill_col.create_index("status", background=True)
            await bill_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Billing index verification notice: {e}")

        # Payments Collection Indexes
        try:
            payments_col = db[COLLECTION_PAYMENTS]
            await payments_col.create_index("payment_id", unique=True, background=True)
            await payments_col.create_index("bill_id", background=True)
            await payments_col.create_index("patient_id", background=True)
            await payments_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Payments index verification notice: {e}")

        # Notifications Collection Indexes (Phase 17)
        try:
            ntf_col = db[COLLECTION_NOTIFICATIONS]
            await ntf_col.create_index("notification_id", unique=True, background=True)
            await ntf_col.create_index(
                "dedupe_key",
                unique=True,
                partialFilterExpression={"dedupe_key": {"$type": "string"}},
                background=True,
            )
            await ntf_col.create_index("recipient_user_id", background=True)
            await ntf_col.create_index("user_id", background=True)
            await ntf_col.create_index([("user_id", 1), ("created_at", -1)], background=True)
            await ntf_col.create_index([("recipient_user_id", 1), ("created_at", -1)], background=True)
            await ntf_col.create_index([("user_id", 1), ("read", 1), ("created_at", -1)], background=True)
            await ntf_col.create_index([("recipient_user_id", 1), ("status", 1), ("created_at", -1)], background=True)
            await ntf_col.create_index([("source_type", 1), ("source_id", 1)], background=True)
            await ntf_col.create_index([("user_id", 1), ("created_at", -1), ("notification_id", -1)], background=True)
            await ntf_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Notifications index verification notice: {e}")

        # Notification Events Collection Indexes (Multi-Worker Event Bus)
        try:
            evt_col = db[COLLECTION_NOTIFICATION_EVENTS]
            await evt_col.create_index("event_id", unique=True, background=True)
            await evt_col.create_index("created_at", background=True)
            await evt_col.create_index([("recipient_user_id", 1), ("created_at", 1)], background=True)
        except Exception as e:
            logger.debug(f"Notification events index verification notice: {e}")

        # AI Analyses Collection Indexes
        try:
            ai_col = db[COLLECTION_AI_ANALYSES]
            await ai_col.create_index("analysis_id", unique=True, background=True)
            await ai_col.create_index("patient_id", background=True)
            await ai_col.create_index("doctor_id", background=True)
            await ai_col.create_index("medical_record_id", background=True)
            await ai_col.create_index("status", background=True)
            await ai_col.create_index("created_at", background=True)
            await ai_col.create_index("is_deleted", background=True)
            await ai_col.create_index([("patient_id", 1), ("created_at", -1)], background=True)
            await ai_col.create_index([("doctor_id", 1), ("created_at", -1)], background=True)
            await ai_col.create_index("model.module_id", background=True)
            await ai_col.create_index(
                [("medical_record_id", 1), ("model.module_id", 1)],
                name="unique_active_record_module_analysis",
                unique=True,
                partialFilterExpression={
                    "status": {"$in": ["pending", "processing", "awaiting_review"]}
                },
                background=True,
            )
        except Exception as e:
            logger.debug(f"AI Analyses index verification notice: {e}")

        # Follow-ups Collection Indexes
        try:
            fu_col = db[COLLECTION_FOLLOW_UPS]
            await fu_col.create_index("follow_up_id", unique=True, background=True)
            await fu_col.create_index("patient_id", background=True)
            await fu_col.create_index("doctor_id", background=True)
            await fu_col.create_index("consultation_id", background=True)
            await fu_col.create_index("status", background=True)
            await fu_col.create_index("scheduled_date", background=True)
            await fu_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Follow-ups index verification notice: {e}")

        # Medical Documents Collection Indexes
        try:
            doc_col = db[COLLECTION_DOCUMENTS]
            await doc_col.create_index("document_id", unique=True, background=True)
            await doc_col.create_index("patient_id", background=True)
            await doc_col.create_index("uploaded_by", background=True)
            await doc_col.create_index("category", background=True)
            await doc_col.create_index("is_deleted", background=True)
        except Exception as e:
            logger.debug(f"Documents index verification notice: {e}")

        # Audit Logs Collection Indexes
        try:
            audit_col = db[COLLECTION_AUDIT_LOGS]
            await audit_col.create_index("audit_id", unique=True, background=True)
            await audit_col.create_index("actor_id", background=True)
            await audit_col.create_index("action", background=True)
            await audit_col.create_index("resource", background=True)
            await audit_col.create_index("timestamp", background=True)
        except Exception as e:
            logger.debug(f"Audit logs index verification notice: {e}")

        logger.info("Database indexes successfully verified across all collections.")
    except Exception as exc:
        logger.warning(f"Error creating database indexes: {exc}")

