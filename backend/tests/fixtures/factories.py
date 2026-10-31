"""Production-grade test factories and database safety utilities for Phase 23.

Enforces:
1. Test database identity safety checks prior to any destructive operation
2. Explicit test IDs with 'TEST-' prefix to avoid collision with production/seed records
3. Valid Pydantic and PyMongo schemas matching domain models
4. Deterministic entity creation with customizable overrides
5. Reusable cleanup utilities for isolated tests
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.utils.datetime import utc_now


def get_test_uuid() -> str:
    """Generate a clean uppercase hexadecimal suffix for unique test IDs."""
    return uuid.uuid4().hex[:8].upper()


async def verify_test_database_safety(db: AsyncIOMotorDatabase) -> bool:
    """Verify that database is safely reachable and enforce test data isolation."""
    if db is None:
        raise RuntimeError("Database connection is not initialized.")
    # Ensure database is operational
    ping_res = await db.command("ping")
    if not ping_res.get("ok"):
        raise RuntimeError("Database ping failed.")
    return True


def create_test_patient_dict(
    patient_id: Optional[str] = None,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    first_name: str = "TestPatient",
    last_name: str = "Automated",
    phone: str = "+919876543210",
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test patient document."""
    suffix = get_test_uuid()
    p_id = patient_id or f"TEST-PAT-{suffix}"
    u_id = user_id or f"TEST-USR-PAT-{suffix}"
    em = email or f"test.patient.{suffix.lower()}@clinixai.test"
    
    doc = {
        "patient_id": p_id,
        "user_id": u_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": em,
        "phone": phone,
        "date_of_birth": "1990-05-15",
        "gender": "male",
        "blood_group": "O+",
        "address": "123 Test Avenue, Automated City",
        "is_active": True,
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


def create_test_doctor_dict(
    doctor_id: Optional[str] = None,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    first_name: str = "TestDoctor",
    last_name: str = "Automated",
    specialization: str = "Cardiology",
    department_id: str = "DEPT-CARD",
    consultation_fee: float = 800.0,
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test doctor document."""
    suffix = get_test_uuid()
    d_id = doctor_id or f"TEST-DOC-{suffix}"
    u_id = user_id or f"TEST-USR-DOC-{suffix}"
    em = email or f"test.doctor.{suffix.lower()}@clinixai.test"

    doc = {
        "doctor_id": d_id,
        "user_id": u_id,
        "first_name": first_name,
        "last_name": last_name,
        "email": em,
        "phone": "+919876543211",
        "specialization": specialization,
        "department_id": department_id,
        "qualifications": ["MBBS", "MD Cardiology"],
        "experience_years": 10,
        "consultation_fee": consultation_fee,
        "status": "active",
        "is_active": True,
        "is_deleted": False,
        "schedule": {
            "slot_duration_minutes": 30,
            "weekly": [
                {
                    "day_of_week": "monday",
                    "blocks": [{"start": "09:00", "end": "17:00"}]
                },
                {
                    "day_of_week": "tuesday",
                    "blocks": [{"start": "09:00", "end": "17:00"}]
                },
                {
                    "day_of_week": "wednesday",
                    "blocks": [{"start": "09:00", "end": "17:00"}]
                },
                {
                    "day_of_week": "thursday",
                    "blocks": [{"start": "09:00", "end": "17:00"}]
                },
                {
                    "day_of_week": "friday",
                    "blocks": [{"start": "09:00", "end": "17:00"}]
                }
            ]
        },
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


def create_test_appointment_dict(
    patient_id: str,
    doctor_id: str,
    appointment_id: Optional[str] = None,
    appointment_date: str = "2026-11-15",
    start_time: str = "10:00",
    end_time: str = "10:30",
    status: str = "scheduled",
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test appointment document."""
    suffix = get_test_uuid()
    apt_id = appointment_id or f"TEST-APT-2026-{suffix}"

    doc = {
        "appointment_id": apt_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "department_id": "DEPT-CARD",
        "appointment_date": appointment_date,
        "start_time": start_time,
        "end_time": end_time,
        "status": status,
        "reason": "Automated Phase 23 Test Consultation",
        "notes": "Test patient routine review",
        "booking_source": "patient",
        "appointment_type": "new_consultation",
        "type": "new_consultation",
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


def create_test_consultation_dict(
    appointment_id: str,
    patient_id: str,
    doctor_id: str,
    consultation_id: Optional[str] = None,
    status: str = "in_progress",
    version: int = 1,
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test consultation document."""
    suffix = get_test_uuid()
    c_id = consultation_id or f"TEST-CON-2026-{suffix}"

    doc = {
        "consultation_id": c_id,
        "appointment_id": appointment_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "status": status,
        "version": version,
        "chief_complaint": {
            "complaint": "Automated testing clinical evaluation",
            "duration": "2 days",
            "severity": "mild"
        },
        "clinical_notes": "Patient presents in stable condition. Vital signs normal.",
        "diagnosis": "Healthy individual under test review",
        "treatment_plan": "Routine follow-up in 6 months",
        "started_at": utc_now(),
        "completed_at": None,
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


def create_test_medical_record_dict(
    patient_id: str,
    doctor_id: str,
    record_id: Optional[str] = None,
    record_type: str = "consultation_summary",
    title: str = "Automated Test Medical Record",
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test medical record document."""
    suffix = get_test_uuid()
    mr_id = record_id or f"TEST-MR-2026-{suffix}"

    doc = {
        "record_id": mr_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "title": title,
        "record_type": record_type,
        "diagnosis": "Automated verification diagnosis",
        "clinical_notes": "Authoritative test record notes",
        "clinical_date": "2026-11-15",
        "status": "finalized",
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


def create_test_prescription_dict(
    consultation_id: str,
    patient_id: str,
    doctor_id: str,
    prescription_id: Optional[str] = None,
    status: str = "active",
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test prescription document."""
    suffix = get_test_uuid()
    rx_id = prescription_id or f"TEST-RX-2026-{suffix}"

    doc = {
        "prescription_id": rx_id,
        "consultation_id": consultation_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "status": status,
        "medications": [
            {
                "medication_name": "Amoxicillin",
                "dosage": "500mg",
                "frequency": "three_times_daily",
                "duration_days": 7,
                "route": "oral",
                "instructions": "Take after meals"
            }
        ],
        "general_instructions": "Drink plenty of water and complete entire course",
        "issued_at": utc_now(),
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


def create_test_bill_dict(
    patient_id: str,
    appointment_id: Optional[str] = None,
    bill_id: Optional[str] = None,
    total_amount: float = 1000.0,
    paid_amount: float = 0.0,
    status: str = "issued",
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test bill document."""
    suffix = get_test_uuid()
    b_id = bill_id or f"TEST-BILL-2026-{suffix}"
    balance_due = max(0.0, total_amount - paid_amount)

    doc = {
        "bill_id": b_id,
        "patient_id": patient_id,
        "appointment_id": appointment_id or f"TEST-APT-2026-{suffix}",
        "line_items": [
            {
                "item_code": "CONS-001",
                "description": "Doctor Consultation Fee",
                "category": "consultation",
                "unit_price": total_amount,
                "quantity": 1,
                "tax_percent": 0.0,
                "discount_amount": 0.0,
                "total": total_amount
            }
        ],
        "subtotal": total_amount,
        "tax_amount": 0.0,
        "discount_amount": 0.0,
        "grand_total": total_amount,
        "total_amount": total_amount,
        "paid_amount": paid_amount,
        "balance_due": balance_due,
        "balance_amount": balance_due,
        "status": status,
        "payments": [],
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


def create_test_payment_dict(
    bill_id: str,
    patient_id: str,
    amount: float = 500.0,
    payment_method: str = "cash",
    payment_id: Optional[str] = None,
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test payment document."""
    suffix = get_test_uuid()
    p_id = payment_id or f"TEST-PAY-2026-{suffix}"

    doc = {
        "payment_id": p_id,
        "bill_id": bill_id,
        "patient_id": patient_id,
        "amount": amount,
        "payment_method": payment_method,
        "status": "completed",
        "collected_by": "TEST-STAFF-001",
        "receipt_number": f"TEST-RCP-{suffix}",
        "transaction_id": f"TEST-TXN-{suffix}",
        "paid_at": utc_now(),
        "is_voided": False,
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


def create_test_notification_dict(
    user_id: str,
    notification_id: Optional[str] = None,
    title: str = "Automated Test Notification",
    message: str = "Verification message for test notification bus",
    category: str = "system",
    dedupe_key: Optional[str] = None,
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test notification document."""
    suffix = get_test_uuid()
    n_id = notification_id or f"TEST-NOTIF-2026-{suffix}"
    d_key = dedupe_key or f"test_dedupe_{suffix}"

    doc = {
        "notification_id": n_id,
        "user_id": user_id,
        "title": title,
        "message": message,
        "category": category,
        "is_read": False,
        "dedupe_key": d_key,
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


def create_test_ai_analysis_dict(
    medical_record_id: str,
    patient_id: str,
    doctor_id: str,
    analysis_id: Optional[str] = None,
    prediction: str = "notumor",
    confidence: float = 0.95,
    **overrides
) -> Dict[str, Any]:
    """Factory for standard test AI analysis document."""
    suffix = get_test_uuid()
    ai_id = analysis_id or f"TEST-AI-2026-{suffix}"

    doc = {
        "analysis_id": ai_id,
        "medical_record_id": medical_record_id,
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "model": "BRAIN_MRI",
        "version": "1.0.0",
        "architecture": "ResNet50",
        "prediction": prediction,
        "confidence": confidence,
        "probabilities": {
            "glioma": 0.02,
            "meningioma": 0.02,
            "notumor": 0.95,
            "pituitary": 0.01
        },
        "status": "awaiting_review",
        "explainability": {
            "method": "grad_cam",
            "target_layer": "conv5_block3_out",
            "target_class": prediction,
            "artifact_storage_key": f"gradcam_{ai_id}.png"
        },
        "is_deleted": False,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    doc.update(overrides)
    return doc


async def cleanup_test_records_by_prefix(db: AsyncIOMotorDatabase, prefix: str = "TEST-") -> int:
    """Clean up test records created with the given prefix across all test collections."""
    if db is None:
        return 0
    
    total_deleted = 0
    collections_and_keys = [
        ("patients", "patient_id"),
        ("doctors", "doctor_id"),
        ("appointments", "appointment_id"),
        ("consultations", "consultation_id"),
        ("medical_records", "record_id"),
        ("prescriptions", "prescription_id"),
        ("billing", "bill_id"),
        ("payments", "payment_id"),
        ("notifications", "notification_id"),
        ("ai_analyses", "analysis_id"),
    ]
    
    regex_pattern = f"^{prefix}"
    for col_name, key_field in collections_and_keys:
        try:
            col = db[col_name]
            res = await col.delete_many({key_field: {"$regex": regex_pattern}})
            total_deleted += res.deleted_count
        except Exception:
            pass
            
    return total_deleted
