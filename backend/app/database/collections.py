"""Centralized collection constants for CliniXAI MongoDB database.

The system utilizes core collections for hospital management and clinical AI.
"""

from typing import Final

# Core Collections Constants
COLLECTION_USERS: Final[str] = "users"
COLLECTION_PATIENTS: Final[str] = "patients"
COLLECTION_DOCTORS: Final[str] = "doctors"
COLLECTION_STAFF: Final[str] = "staff"
COLLECTION_DEPARTMENTS: Final[str] = "departments"
COLLECTION_APPOINTMENTS: Final[str] = "appointments"
COLLECTION_CONSULTATIONS: Final[str] = "consultations"
COLLECTION_MEDICAL_RECORDS: Final[str] = "medical_records"
COLLECTION_AI_ANALYSES: Final[str] = "ai_analyses"
COLLECTION_PRESCRIPTIONS: Final[str] = "prescriptions"
COLLECTION_BILLING: Final[str] = "billing"
COLLECTION_NOTIFICATIONS: Final[str] = "notifications"
COLLECTION_FOLLOW_UPS: Final[str] = "follow_ups"
COLLECTION_PAYMENTS: Final[str] = "payments"
COLLECTION_DOCUMENTS: Final[str] = "documents"
COLLECTION_AUDIT_LOGS: Final[str] = "audit_logs"
COLLECTION_NOTIFICATION_EVENTS: Final[str] = "notification_events"
COLLECTION_HOSPITAL_SETTINGS: Final[str] = "hospital_settings"

# Set of all valid collection names for validation and iteration
ALL_COLLECTIONS: Final[set[str]] = {
    COLLECTION_USERS,
    COLLECTION_PATIENTS,
    COLLECTION_DOCTORS,
    COLLECTION_STAFF,
    COLLECTION_DEPARTMENTS,
    COLLECTION_APPOINTMENTS,
    COLLECTION_CONSULTATIONS,
    COLLECTION_MEDICAL_RECORDS,
    COLLECTION_AI_ANALYSES,
    COLLECTION_PRESCRIPTIONS,
    COLLECTION_BILLING,
    COLLECTION_NOTIFICATIONS,
    COLLECTION_FOLLOW_UPS,
    COLLECTION_PAYMENTS,
    COLLECTION_DOCUMENTS,
    COLLECTION_AUDIT_LOGS,
    COLLECTION_NOTIFICATION_EVENTS,
    COLLECTION_HOSPITAL_SETTINGS,
}

