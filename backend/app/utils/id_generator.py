"""ID generators — updated with Phase 6 Billing, Notification, and Payment ID generators."""

import secrets
from datetime import datetime, timezone


def generate_user_id() -> str:
    """Generates a human-readable user ID in the format USR-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"USR-{year}-{suffix}"


def generate_patient_id() -> str:
    """Generates a human-readable patient ID in the format PAT-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"PAT-{year}-{suffix}"


def generate_doctor_id() -> str:
    """Generates a human-readable doctor ID in the format DOC-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"DOC-{year}-{suffix}"


def generate_staff_id() -> str:
    """Generates a human-readable staff ID in the format STF-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"STF-{year}-{suffix}"


def generate_department_id() -> str:
    """Generates a human-readable department ID in the format DEP-YYYY-XXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(2).upper()
    return f"DEP-{year}-{suffix}"


def generate_appointment_id() -> str:
    """Generates a human-readable appointment ID in the format APT-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"APT-{year}-{suffix}"


def generate_consultation_id() -> str:
    """Generates a human-readable consultation ID in the format CON-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"CON-{year}-{suffix}"


def generate_prescription_id() -> str:
    """Generates a human-readable prescription ID in the format RX-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"RX-{year}-{suffix}"


def generate_medical_record_id() -> str:
    """Generates a human-readable medical record ID in the format MR-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"MR-{year}-{suffix}"


def generate_bill_id() -> str:
    """Generates a human-readable bill ID in the format BILL-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"BILL-{year}-{suffix}"


def generate_payment_id() -> str:
    """Generates a human-readable payment transaction ID in the format PAY-YYYY-XXXXXXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(5).upper()
    return f"PAY-{year}-{suffix}"


def generate_notification_id() -> str:
    """Generates a human-readable notification ID in the format NTF-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"NTF-{year}-{suffix}"


def generate_ai_analysis_id() -> str:
    """Generates a human-readable AI analysis ID in the format AI-YYYY-XXXXXX."""
    year = datetime.now(timezone.utc).year
    suffix = secrets.token_hex(3).upper()
    return f"AI-{year}-{suffix}"


def generate_queue_token(sequence_number: int, prefix: str = "A") -> str:
    """Generates a human-readable queue token string, e.g., A-001."""
    return f"{prefix}-{sequence_number:03d}"
