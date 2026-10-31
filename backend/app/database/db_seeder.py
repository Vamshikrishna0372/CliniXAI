"""Idempotent MongoDB Database Seeder for CliniXAI.

Seeds 5 Doctors, 3 Test Patients, 2 Staff Members, 20+ Appointments, 10+ Consultations,
8+ Prescriptions, 8+ Medical Records, 10+ Bills, 6+ Follow-ups, and Notifications directly into MongoDB.
"""

from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.logging import logger
from app.core.security import hash_password
from app.database.collections import (
    COLLECTION_USERS, COLLECTION_PATIENTS, COLLECTION_DOCTORS,
    COLLECTION_STAFF, COLLECTION_DEPARTMENTS, COLLECTION_APPOINTMENTS,
    COLLECTION_CONSULTATIONS, COLLECTION_PRESCRIPTIONS, COLLECTION_MEDICAL_RECORDS,
    COLLECTION_BILLING, COLLECTION_FOLLOW_UPS, COLLECTION_DOCUMENTS,
    COLLECTION_NOTIFICATIONS, COLLECTION_AUDIT_LOGS, COLLECTION_AI_ANALYSES
)
from app.models.user import UserRole, AuthProvider, AccountStatus
from app.models.doctor import DoctorStatus
from app.models.patient import PatientStatus, Gender, BloodGroup
from app.models.appointment import AppointmentStatus, AppointmentType, BookingSource
from app.models.consultation import ConsultationStatus, RiskLevel, SymptomSeverity, DiagnosisType
from app.models.prescription import PrescriptionStatus
from app.models.follow_up import FollowUpStatus
from app.models.billing import BillingStatus, PaymentMethod, PaymentStatus
from app.models.medical_record import RecordType, RecordSource, RecordStatus
from app.models.document import DocumentCategory
from app.utils.datetime import utc_now
from app.core.bootstrap import bootstrap_hospital_admin


async def seed_initial_data(db: AsyncIOMotorDatabase) -> None:
    """Idempotently seeds departments, 5 doctors, 3 test patients, 2 staff, and clinical records into MongoDB."""
    try:
        now = utc_now()
        today_str = now.strftime("%Y-%m-%d")

        # 1. Seed Departments
        dept_col = db[COLLECTION_DEPARTMENTS]
        default_departments = [
            {"department_id": "DEPT-CARD", "name": "Cardiology", "code": "CARD", "description": "Cardiovascular healthcare and diagnostics.", "icon": "Heart", "status": "active", "is_deleted": False, "created_at": now, "updated_at": now},
            {"department_id": "DEPT-NEUR", "name": "Neurology", "code": "NEUR", "description": "Brain and nervous system clinical care.", "icon": "Brain", "status": "active", "is_deleted": False, "created_at": now, "updated_at": now},
            {"department_id": "DEPT-DERM", "name": "Dermatology", "code": "DERM", "description": "Skin and nail diagnosis and therapy.", "icon": "Sun", "status": "active", "is_deleted": False, "created_at": now, "updated_at": now},
            {"department_id": "DEPT-ORTH", "name": "Orthopedics", "code": "ORTH", "description": "Musculoskeletal system and joint care.", "icon": "Bone", "status": "active", "is_deleted": False, "created_at": now, "updated_at": now},
            {"department_id": "DEPT-PED", "name": "Pediatrics", "code": "PED", "description": "Infant, child, and adolescent healthcare.", "icon": "Baby", "status": "active", "is_deleted": False, "created_at": now, "updated_at": now},
            {"department_id": "DEPT-GEN", "name": "General Medicine", "code": "GEN", "description": "Primary healthcare and routine consultations.", "icon": "Stethoscope", "status": "active", "is_deleted": False, "created_at": now, "updated_at": now},
        ]
        for dept in default_departments:
            await dept_col.update_one({"department_id": dept["department_id"]}, {"$set": dept}, upsert=True)

        users_col = db[COLLECTION_USERS]
        patients_col = db[COLLECTION_PATIENTS]
        doctors_col = db[COLLECTION_DOCTORS]
        staff_col = db[COLLECTION_STAFF]
        appts_col = db[COLLECTION_APPOINTMENTS]
        consults_col = db[COLLECTION_CONSULTATIONS]
        rxs_col = db[COLLECTION_PRESCRIPTIONS]
        med_recs_col = db[COLLECTION_MEDICAL_RECORDS]
        billing_col = db[COLLECTION_BILLING]
        followups_col = db[COLLECTION_FOLLOW_UPS]
        docs_col = db[COLLECTION_DOCUMENTS]
        notifs_col = db[COLLECTION_NOTIFICATIONS]
        ai_analyses_col = db[COLLECTION_AI_ANALYSES]

        # 2. Seed 5 Active Doctor Accounts
        doctors_data = [
            {
                "user_id": "USR-DOC-RAO-001",
                "email": "doctor.arjun@clinixai.com",
                "full_name": "Dr. Arjun Rao",
                "password_hash": hash_password("Doctor@123"),
                "role": UserRole.DOCTOR.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "email_verified": True,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False, "created_at": now, "updated_at": now,
                "doctor_profile": {
                    "doctor_id": "DOC-RAO-001", "user_id": "USR-DOC-RAO-001", "first_name": "Arjun", "last_name": "Rao",
                    "full_name": "Dr. Arjun Rao", "email": "doctor.arjun@clinixai.com", "phone": "+91 98765 10001",
                    "department_id": "DEPT-CARD", "specialization": "Cardiology", "qualification": "MBBS, MD",
                    "registration_number": "MED-REG-10001", "experience_years": 10, "consultation_fee": 800.0,
                    "schedule": {
                        "slot_duration_minutes": 30,
                        "weekly": [
                            {"day": "monday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}, {"start": "14:00", "end": "18:00"}]},
                            {"day": "tuesday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}, {"start": "14:00", "end": "18:00"}]},
                            {"day": "wednesday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}, {"start": "14:00", "end": "18:00"}]},
                            {"day": "thursday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}, {"start": "14:00", "end": "18:00"}]},
                            {"day": "friday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}, {"start": "14:00", "end": "18:00"}]},
                            {"day": "saturday", "is_available": True, "slots": [{"start": "09:00", "end": "13:00"}]},
                            {"day": "sunday", "is_available": False, "slots": []}
                        ]
                    },
                    "status": DoctorStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
                }
            },
            {
                "user_id": "USR-DOC-SHARMA-002",
                "email": "doctor.priya@clinixai.com",
                "full_name": "Dr. Priya Sharma",
                "password_hash": hash_password("Doctor@123"),
                "role": UserRole.DOCTOR.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "email_verified": True,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False, "created_at": now, "updated_at": now,
                "doctor_profile": {
                    "doctor_id": "DOC-SHARMA-002", "user_id": "USR-DOC-SHARMA-002", "first_name": "Priya", "last_name": "Sharma",
                    "full_name": "Dr. Priya Sharma", "email": "doctor.priya@clinixai.com", "phone": "+91 98765 10002",
                    "department_id": "DEPT-NEUR", "specialization": "Neurology", "qualification": "MBBS, MD, DM",
                    "registration_number": "MED-REG-10002", "experience_years": 8, "consultation_fee": 1000.0,
                    "status": DoctorStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
                }
            },
            {
                "user_id": "USR-DOC-MEHTA-003",
                "email": "doctor.rahul@clinixai.com",
                "full_name": "Dr. Rahul Mehta",
                "password_hash": hash_password("Doctor@123"),
                "role": UserRole.DOCTOR.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "email_verified": True,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False, "created_at": now, "updated_at": now,
                "doctor_profile": {
                    "doctor_id": "DOC-MEHTA-003", "user_id": "USR-DOC-MEHTA-003", "first_name": "Rahul", "last_name": "Mehta",
                    "full_name": "Dr. Rahul Mehta", "email": "doctor.rahul@clinixai.com", "phone": "+91 98765 10003",
                    "department_id": "DEPT-GEN", "specialization": "General Medicine", "qualification": "MBBS, MD",
                    "registration_number": "MED-REG-10003", "experience_years": 7, "consultation_fee": 600.0,
                    "status": DoctorStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
                }
            },
            {
                "user_id": "USR-DOC-REDDY-004",
                "email": "doctor.ananya@clinixai.com",
                "full_name": "Dr. Ananya Reddy",
                "password_hash": hash_password("Doctor@123"),
                "role": UserRole.DOCTOR.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "email_verified": True,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False, "created_at": now, "updated_at": now,
                "doctor_profile": {
                    "doctor_id": "DOC-REDDY-004", "user_id": "USR-DOC-REDDY-004", "first_name": "Ananya", "last_name": "Reddy",
                    "full_name": "Dr. Ananya Reddy", "email": "doctor.ananya@clinixai.com", "phone": "+91 98765 10004",
                    "department_id": "DEPT-PED", "specialization": "Pediatrics", "qualification": "MBBS, MD",
                    "registration_number": "MED-REG-10004", "experience_years": 6, "consultation_fee": 700.0,
                    "status": DoctorStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
                }
            },
            {
                "user_id": "USR-DOC-SINGH-005",
                "email": "doctor.vikram@clinixai.com",
                "full_name": "Dr. Vikram Singh",
                "password_hash": hash_password("Doctor@123"),
                "role": UserRole.DOCTOR.value,
                "auth_provider": AuthProvider.LOCAL.value,
                "email_verified": True,
                "account_status": AccountStatus.ACTIVE.value,
                "is_deleted": False, "created_at": now, "updated_at": now,
                "doctor_profile": {
                    "doctor_id": "DOC-SINGH-005", "user_id": "USR-DOC-SINGH-005", "first_name": "Vikram", "last_name": "Singh",
                    "full_name": "Dr. Vikram Singh", "email": "doctor.vikram@clinixai.com", "phone": "+91 98765 10005",
                    "department_id": "DEPT-ORTH", "specialization": "Orthopedics", "qualification": "MBBS, MS",
                    "registration_number": "MED-REG-10005", "experience_years": 12, "consultation_fee": 900.0,
                    "status": DoctorStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
                }
            },
        ]

        for d in doctors_data:
            doc_profile = d.pop("doctor_profile")
            email = d["email"]
            await users_col.update_one({"email": email}, {"$set": d}, upsert=True)
            await doctors_col.update_one({"email": email}, {"$set": doc_profile}, upsert=True)

        # 3. Seed 3 Specific Patient Accounts
        patients_data = [
            ("PAT-ONE-001", "USR-PAT-ONE-001", "Patient", "One", "patient.one@clinixai.com", "+91 98765 30001", "male", "1992-01-10", "A+", ["Pollen"]),
            ("PAT-TWO-002", "USR-PAT-TWO-002", "Patient", "Two", "patient.two@clinixai.com", "+91 98765 30002", "female", "1995-05-15", "O+", ["Peanuts"]),
            ("PAT-THREE-003", "USR-PAT-THREE-003", "Patient", "Three", "patient.three@clinixai.com", "+91 98765 30003", "male", "1988-11-20", "B+", ["Aspirin"]),
        ]

        pwd_patient_hash = hash_password("Patient@123")

        for pid, uid, fn, ln, email, phone, gender, dob, bg, allergies in patients_data:
            user_doc = {
                "user_id": uid, "email": email, "full_name": f"{fn} {ln}", "password_hash": pwd_patient_hash,
                "role": UserRole.PATIENT.value, "auth_provider": AuthProvider.LOCAL.value, "email_verified": True,
                "account_status": AccountStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
            }
            patient_doc = {
                "patient_id": pid, "user_id": uid, "first_name": fn, "last_name": ln, "full_name": f"{fn} {ln}",
                "email": email, "phone": phone, "gender": gender, "date_of_birth": dob, "blood_group": bg,
                "address": {"street": "123 Health Ave", "city": "Tech City", "state": "State", "postal_code": "500001", "country": "India"},
                "emergency_contact": {"name": f"Contact for {fn}", "relationship": "Family", "phone": phone},
                "allergies": allergies, "status": PatientStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
            }
            await users_col.update_one({"email": email}, {"$set": user_doc}, upsert=True)
            await patients_col.update_one({"patient_id": pid}, {"$set": patient_doc}, upsert=True)

        # 4. Seed 2 Staff Accounts
        staff_data = [
            {
                "user_id": "USR-STF-ONE-001", "email": "staff.one@clinixai.com", "full_name": "Staff One",
                "password_hash": hash_password("Staff@123"), "role": UserRole.HOSPITAL_STAFF.value, "auth_provider": AuthProvider.LOCAL.value,
                "email_verified": True, "account_status": AccountStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
                "staff_profile": {
                    "staff_id": "STF-ONE-001", "user_id": "USR-STF-ONE-001", "full_name": "Staff One", "email": "staff.one@clinixai.com",
                    "phone": "+91 98765 40001", "department_id": "DEPT-GEN", "designation": "Senior Desk Coordinator", "status": "active",
                    "is_deleted": False, "created_at": now, "updated_at": now,
                }
            },
            {
                "user_id": "USR-STF-TWO-002", "email": "staff.two@clinixai.com", "full_name": "Staff Two",
                "password_hash": hash_password("Staff@123"), "role": UserRole.HOSPITAL_STAFF.value, "auth_provider": AuthProvider.LOCAL.value,
                "email_verified": True, "account_status": AccountStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
                "staff_profile": {
                    "staff_id": "STF-TWO-002", "user_id": "USR-STF-TWO-002", "full_name": "Staff Two", "email": "staff.two@clinixai.com",
                    "phone": "+91 98765 40002", "department_id": "DEPT-CARD", "designation": "Clinical Operations Executive", "status": "active",
                    "is_deleted": False, "created_at": now, "updated_at": now,
                }
            },
        ]

        for s in staff_data:
            s_prof = s.pop("staff_profile")
            email = s["email"]
            await users_col.update_one({"email": email}, {"$set": s}, upsert=True)
            await staff_col.update_one({"email": email}, {"$set": s_prof}, upsert=True)

        # 4b. Seed Alias Accounts for convenience (patient@clinixai.dev, doctor@clinixai.dev, staff@clinixai.dev)
        alias_accounts = [
            ("USR-PAT-DEV-001", "patient@clinixai.dev", "Priya Sharma", hash_password("patient123"), UserRole.PATIENT.value),
            ("USR-DOC-DEV-001", "doctor@clinixai.dev", "Dr. Arjun Mehta", hash_password("doctor123"), UserRole.DOCTOR.value),
            ("USR-STF-DEV-001", "staff@clinixai.dev", "Neha Kulkarni", hash_password("staff123"), UserRole.HOSPITAL_STAFF.value),
        ]
        for uid, email, name, pwd_h, r_val in alias_accounts:
            alias_user = {
                "user_id": uid, "email": email, "full_name": name, "password_hash": pwd_h,
                "role": r_val, "auth_provider": AuthProvider.LOCAL.value, "email_verified": True,
                "account_status": AccountStatus.ACTIVE.value, "is_deleted": False, "created_at": now, "updated_at": now,
            }
            await users_col.update_one({"email": email}, {"$set": alias_user}, upsert=True)

        # 5. Seed 20+ Appointments across ALL 5 Doctors and 3 Patients
        appointments_list = [
            # Dr. Arjun Rao (Cardiology) - 4 appointments
            {"appointment_id": "APT-2026-001", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "appointment_date": today_str, "start_time": "09:00", "end_time": "09:30", "reason": "Cardiac Evaluation", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.CONFIRMED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-002", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "appointment_date": today_str, "start_time": "10:00", "end_time": "10:30", "reason": "Hypertension Checkup", "appointment_type": AppointmentType.FOLLOW_UP.value, "status": "checked_in", "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-003", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "appointment_date": today_str, "start_time": "11:00", "end_time": "11:30", "reason": "Palpitations Screening", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": "in_consultation", "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-004", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "appointment_date": today_str, "start_time": "14:00", "end_time": "14:30", "reason": "Routine ECG Review", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.COMPLETED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},

            # Dr. Priya Sharma (Neurology) - 4 appointments
            {"appointment_id": "APT-2026-005", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SHARMA-002", "department_id": "DEPT-NEUR", "appointment_date": today_str, "start_time": "10:30", "end_time": "11:00", "reason": "Migraine Follow-up", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.COMPLETED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-006", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-SHARMA-002", "department_id": "DEPT-NEUR", "appointment_date": today_str, "start_time": "11:30", "end_time": "12:00", "reason": "Dizziness & Vertigo Check", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": "checked_in", "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-007", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-SHARMA-002", "department_id": "DEPT-NEUR", "appointment_date": "2026-08-09", "start_time": "15:00", "end_time": "15:30", "reason": "Nerve Conduction Review", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.COMPLETED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-008", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SHARMA-002", "department_id": "DEPT-NEUR", "appointment_date": "2026-08-05", "start_time": "16:00", "end_time": "16:30", "reason": "Sleep Apnea Evaluation", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.CANCELLED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},

            # Dr. Rahul Mehta (General Medicine) - 4 appointments
            {"appointment_id": "APT-2026-009", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "appointment_date": today_str, "start_time": "09:30", "end_time": "10:00", "reason": "Annual Wellness Checkup", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.COMPLETED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-010", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "appointment_date": today_str, "start_time": "10:00", "end_time": "10:30", "reason": "Fever & Cold Consultation", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.SCHEDULED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-011", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "appointment_date": "2026-08-18", "start_time": "11:00", "end_time": "11:30", "reason": "Thyroid Profile Screening", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.SCHEDULED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-012", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "appointment_date": "2026-08-07", "start_time": "14:30", "end_time": "15:00", "reason": "Blood Sugar Check", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.COMPLETED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},

            # Dr. Ananya Reddy (Pediatrics) - 4 appointments
            {"appointment_id": "APT-2026-013", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-REDDY-004", "department_id": "DEPT-PED", "appointment_date": today_str, "start_time": "10:00", "end_time": "10:30", "reason": "Child Health Assessment", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.COMPLETED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-014", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-REDDY-004", "department_id": "DEPT-PED", "appointment_date": "2026-08-19", "start_time": "11:00", "end_time": "11:30", "reason": "Vaccination Booster", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.CONFIRMED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-015", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-REDDY-004", "department_id": "DEPT-PED", "appointment_date": "2026-08-06", "start_time": "15:00", "end_time": "15:30", "reason": "Eczema Rash Consultation", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.COMPLETED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-016", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-REDDY-004", "department_id": "DEPT-PED", "appointment_date": "2026-08-04", "start_time": "16:00", "end_time": "16:30", "reason": "Dietary Allergy Evaluation", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.CANCELLED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},

            # Dr. Vikram Singh (Orthopedics) - 4 appointments
            {"appointment_id": "APT-2026-017", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "appointment_date": today_str, "start_time": "15:00", "end_time": "15:30", "reason": "Knee Pain Examination", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": "in_consultation", "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-018", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "appointment_date": today_str, "start_time": "16:00", "end_time": "16:30", "reason": "Ankle Ligament Rehabilitation", "appointment_type": AppointmentType.FOLLOW_UP.value, "status": AppointmentStatus.CONFIRMED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-019", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "appointment_date": "2026-08-05", "start_time": "11:00", "end_time": "11:30", "reason": "Post Spine Injury Rehab", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.COMPLETED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
            {"appointment_id": "APT-2026-020", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "appointment_date": "2026-08-03", "start_time": "14:00", "end_time": "14:30", "reason": "Shoulder Stiffness Consultation", "appointment_type": AppointmentType.NEW_CONSULTATION.value, "status": AppointmentStatus.COMPLETED.value, "booking_source": BookingSource.PATIENT.value, "created_at": now, "updated_at": now},
        ]

        for appt in appointments_list:
            await appts_col.update_one({"appointment_id": appt["appointment_id"]}, {"$set": appt}, upsert=True)

        # 6. Seed 10 Consultations linked to completed appointments
        completed_consultations = [
            {"consultation_id": "CNS-2026-001", "appointment_id": "APT-2026-002", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "Hypertension follow-up", "duration": "2 weeks"}, "symptoms": [{"name": "Mild Headaches", "severity": SymptomSeverity.MILD.value}], "vitals": {"bp_systolic": 130, "bp_diastolic": 85, "heart_rate_bpm": 74, "temperature_c": 36.8, "spo2_percent": 99.0}, "clinical_assessment": {"summary": "BP stabilized on current therapy.", "risk_level": RiskLevel.LOW.value}, "diagnoses": [{"name": "Essential Hypertension", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-I10"}], "doctor_instructions": ["Continue low sodium diet", "Daily 30 min walk"], "created_at": now, "started_at": now, "updated_at": now},
            {"consultation_id": "CNS-2026-002", "appointment_id": "APT-2026-004", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "Chest discomfort on exertion", "duration": "3 days"}, "symptoms": [{"name": "Chest Tightness", "severity": SymptomSeverity.MODERATE.value}], "vitals": {"bp_systolic": 135, "bp_diastolic": 88, "heart_rate_bpm": 82, "temperature_c": 37.0, "spo2_percent": 98.0}, "clinical_assessment": {"summary": "Mild stable angina. ECG normal.", "risk_level": RiskLevel.MODERATE.value}, "diagnoses": [{"name": "Angina Pectoris", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-I20"}], "doctor_instructions": ["Avoid heavy physical strain", "TMT test scheduled"], "created_at": now, "started_at": now, "updated_at": now},
            {"consultation_id": "CNS-2026-003", "appointment_id": "APT-2026-005", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SHARMA-002", "department_id": "DEPT-NEUR", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "Chronic Migraine episodes", "duration": "1 month"}, "symptoms": [{"name": "Throbbing Headache", "severity": SymptomSeverity.SEVERE.value}], "vitals": {"bp_systolic": 118, "bp_diastolic": 76, "heart_rate_bpm": 70, "temperature_c": 36.7, "spo2_percent": 99.0}, "clinical_assessment": {"summary": "Migraine without aura.", "risk_level": RiskLevel.LOW.value}, "diagnoses": [{"name": "Migraine", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-G43"}], "doctor_instructions": ["Maintain sleep cycle", "Hydrate adequately"], "created_at": now, "started_at": now, "updated_at": now},
            {"consultation_id": "CNS-2026-004", "appointment_id": "APT-2026-007", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-SHARMA-002", "department_id": "DEPT-NEUR", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "Peripheral numbness", "duration": "10 days"}, "symptoms": [{"name": "Hand Tingling", "severity": SymptomSeverity.MILD.value}], "vitals": {"bp_systolic": 122, "bp_diastolic": 80, "heart_rate_bpm": 72, "temperature_c": 36.6, "spo2_percent": 98.5}, "clinical_assessment": {"summary": "Mild cervical radiculopathy.", "risk_level": RiskLevel.LOW.value}, "diagnoses": [{"name": "Cervical Radiculopathy", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-M54.2"}], "doctor_instructions": ["Physiotherapy recommended", "Posture corrections"], "created_at": now, "started_at": now, "updated_at": now},
            {"consultation_id": "CNS-2026-005", "appointment_id": "APT-2026-009", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "General weakness & lethargy", "duration": "2 weeks"}, "symptoms": [{"name": "Fatigue", "severity": SymptomSeverity.MILD.value}], "vitals": {"bp_systolic": 120, "bp_diastolic": 80, "heart_rate_bpm": 72, "temperature_c": 36.7, "spo2_percent": 98.0}, "clinical_assessment": {"summary": "Vitamin D deficiency.", "risk_level": RiskLevel.LOW.value}, "diagnoses": [{"name": "Vitamin D Deficiency", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-E55.9"}], "doctor_instructions": ["Weekly Vitamin D sachet", "Sunlight exposure"], "created_at": now, "started_at": now, "updated_at": now},
            {"consultation_id": "CNS-2026-006", "appointment_id": "APT-2026-010", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "Fever & body pain", "duration": "2 days"}, "symptoms": [{"name": "High Fever", "severity": SymptomSeverity.MODERATE.value}], "vitals": {"bp_systolic": 115, "bp_diastolic": 75, "heart_rate_bpm": 88, "temperature_c": 38.5, "spo2_percent": 97.5}, "clinical_assessment": {"summary": "Viral Upper Respiratory Fever.", "risk_level": RiskLevel.LOW.value}, "diagnoses": [{"name": "Viral Fever", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-B34.9"}], "doctor_instructions": ["Paracetamol 650mg as needed", "Bed rest"], "created_at": now, "started_at": now, "updated_at": now},
            {"consultation_id": "CNS-2026-007", "appointment_id": "APT-2026-012", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "Routine HbA1c review", "duration": "3 months"}, "symptoms": [{"name": "Mild Thirst", "severity": SymptomSeverity.MILD.value}], "vitals": {"bp_systolic": 126, "bp_diastolic": 82, "heart_rate_bpm": 76, "temperature_c": 36.8, "spo2_percent": 99.0}, "clinical_assessment": {"summary": "Type 2 Diabetes well controlled.", "risk_level": RiskLevel.LOW.value}, "diagnoses": [{"name": "Type 2 Diabetes", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-E11"}], "doctor_instructions": ["Continue Metformin", "Low glycemic index diet"], "created_at": now, "started_at": now, "updated_at": now},
            {"consultation_id": "CNS-2026-008", "appointment_id": "APT-2026-013", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-REDDY-004", "department_id": "DEPT-PED", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "Pediatric Atopic Rash", "duration": "2 weeks"}, "symptoms": [{"name": "Skin Redness", "severity": SymptomSeverity.MILD.value}], "vitals": {"bp_systolic": 105, "bp_diastolic": 68, "heart_rate_bpm": 80, "temperature_c": 36.6, "spo2_percent": 99.0}, "clinical_assessment": {"summary": "Mild infantile eczema.", "risk_level": RiskLevel.LOW.value}, "diagnoses": [{"name": "Atopic Dermatitis", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-L20"}], "doctor_instructions": ["Apply moisturizer twice daily", "Gentle cleanser"], "created_at": now, "started_at": now, "updated_at": now},
            {"consultation_id": "CNS-2026-009", "appointment_id": "APT-2026-017", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "Right Knee pain during stairs", "duration": "3 weeks"}, "symptoms": [{"name": "Joint Crepitus", "severity": SymptomSeverity.MODERATE.value}], "vitals": {"bp_systolic": 124, "bp_diastolic": 82, "heart_rate_bpm": 74, "temperature_c": 36.8, "spo2_percent": 98.0}, "clinical_assessment": {"summary": "Patellofemoral Pain Syndrome.", "risk_level": RiskLevel.LOW.value}, "diagnoses": [{"name": "Patellofemoral Syndrome", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-M22.2"}], "doctor_instructions": ["Quadriceps strengthening", "Ice compression"], "created_at": now, "started_at": now, "updated_at": now},
            {"consultation_id": "CNS-2026-010", "appointment_id": "APT-2026-019", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "status": ConsultationStatus.COMPLETED.value, "chief_complaint": {"complaint": "Lumbar back strain", "duration": "1 week"}, "symptoms": [{"name": "Lower Back Stiffness", "severity": SymptomSeverity.MODERATE.value}], "vitals": {"bp_systolic": 128, "bp_diastolic": 84, "heart_rate_bpm": 76, "temperature_c": 36.9, "spo2_percent": 98.5}, "clinical_assessment": {"summary": "Acute lumbar muscle strain.", "risk_level": RiskLevel.LOW.value}, "diagnoses": [{"name": "Lumbar Strain", "type": DiagnosisType.PRIMARY.value, "code": "ICD-10-S39.012"}], "doctor_instructions": ["Avoid heavy lifting", "Ergonomic chair lumbar support"], "created_at": now, "started_at": now, "updated_at": now},
        ]

        for c in completed_consultations:
            await consults_col.update_one({"consultation_id": c["consultation_id"]}, {"$set": c}, upsert=True)

        # 7. Seed 8 Prescriptions
        prescriptions_list = [
            {"prescription_id": "RX-2026-001", "consultation_id": "CNS-2026-001", "appointment_id": "APT-2026-002", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-RAO-001", "diagnosis": "Essential Hypertension", "medications": [{"name": "Amlodipine", "strength": "5 mg", "dosage": "1 tablet", "frequency": "Once daily morning", "duration": "30 days"}], "instructions": "Take after breakfast.", "status": PrescriptionStatus.ISSUED.value, "created_at": now, "updated_at": now},
            {"prescription_id": "RX-2026-002", "consultation_id": "CNS-2026-002", "appointment_id": "APT-2026-004", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-RAO-001", "diagnosis": "Angina Pectoris", "medications": [{"name": "Nitroglycerin", "strength": "0.4 mg", "dosage": "1 spray", "frequency": "As needed for chest pain", "duration": "30 days"}], "instructions": "Sublingual spray during episodes.", "status": PrescriptionStatus.ISSUED.value, "created_at": now, "updated_at": now},
            {"prescription_id": "RX-2026-003", "consultation_id": "CNS-2026-003", "appointment_id": "APT-2026-005", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SHARMA-002", "diagnosis": "Migraine", "medications": [{"name": "Naratriptan", "strength": "2.5 mg", "dosage": "1 tablet", "frequency": "At onset of headache", "duration": "10 days"}], "instructions": "Take with water.", "status": PrescriptionStatus.ISSUED.value, "created_at": now, "updated_at": now},
            {"prescription_id": "RX-2026-004", "consultation_id": "CNS-2026-005", "appointment_id": "APT-2026-009", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-MEHTA-003", "diagnosis": "Vitamin D Deficiency", "medications": [{"name": "Cholecalciferol", "strength": "60,000 IU", "dosage": "1 sachet", "frequency": "Weekly once", "duration": "8 weeks"}], "instructions": "Mix in warm milk.", "status": PrescriptionStatus.ISSUED.value, "created_at": now, "updated_at": now},
            {"prescription_id": "RX-2026-005", "consultation_id": "CNS-2026-006", "appointment_id": "APT-2026-010", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-MEHTA-003", "diagnosis": "Viral Fever", "medications": [{"name": "Paracetamol", "strength": "650 mg", "dosage": "1 tablet", "frequency": "Thrice daily", "duration": "5 days"}], "instructions": "Take after meals.", "status": PrescriptionStatus.ISSUED.value, "created_at": now, "updated_at": now},
            {"prescription_id": "RX-2026-006", "consultation_id": "CNS-2026-007", "appointment_id": "APT-2026-012", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-MEHTA-003", "diagnosis": "Type 2 Diabetes", "medications": [{"name": "Metformin", "strength": "500 mg", "dosage": "1 tablet", "frequency": "Twice daily", "duration": "60 days"}], "instructions": "Take with breakfast and dinner.", "status": PrescriptionStatus.ISSUED.value, "created_at": now, "updated_at": now},
            {"prescription_id": "RX-2026-007", "consultation_id": "CNS-2026-009", "appointment_id": "APT-2026-017", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SINGH-005", "diagnosis": "Patellofemoral Syndrome", "medications": [{"name": "Etoricoxib", "strength": "90 mg", "dosage": "1 tablet", "frequency": "Once daily for 5 days", "duration": "5 days"}], "instructions": "Take after food.", "status": PrescriptionStatus.ISSUED.value, "created_at": now, "updated_at": now},
            {"prescription_id": "RX-2026-008", "consultation_id": "CNS-2026-010", "appointment_id": "APT-2026-019", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-SINGH-005", "diagnosis": "Lumbar Strain", "medications": [{"name": "Thiocolchicoside", "strength": "4 mg", "dosage": "1 capsule", "frequency": "Twice daily", "duration": "7 days"}], "instructions": "Muscle relaxant after food.", "status": PrescriptionStatus.ISSUED.value, "created_at": now, "updated_at": now},
        ]

        for rx in prescriptions_list:
            await rxs_col.update_one({"prescription_id": rx["prescription_id"]}, {"$set": rx}, upsert=True)

        # 8. Seed 8 Medical Records
        med_records_list = [
            {"record_id": "MR-2026-001", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "record_type": RecordType.LAB_REPORT.value, "title": "Lipid Profile & Resting ECG", "clinical_date": "2026-08-08", "file": {"storage_key": "ecg_001.pdf", "original_filename": "ECG_PAT001.pdf", "content_type": "application/pdf", "size_bytes": 245000, "checksum": "abc123hash", "extension": ".pdf", "storage_provider": "local", "uploaded_at": now}, "uploaded_by": "USR-DOC-RAO-001", "source": RecordSource.DOCTOR.value, "status": RecordStatus.ACTIVE.value, "created_at": now, "updated_at": now},
            {"record_id": "MR-2026-002", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SHARMA-002", "department_id": "DEPT-NEUR", "record_type": RecordType.RADIOLOGY_REPORT.value, "title": "Brain MRI Scan Report", "clinical_date": "2026-08-11", "file": {"storage_key": "mri_pat002.pdf", "original_filename": "Brain_MRI_PAT002.pdf", "content_type": "application/pdf", "size_bytes": 1400000, "checksum": "mri456hash", "extension": ".pdf", "storage_provider": "local", "uploaded_at": now}, "uploaded_by": "USR-DOC-SHARMA-002", "source": RecordSource.DOCTOR.value, "status": RecordStatus.ACTIVE.value, "created_at": now, "updated_at": now},
            {"record_id": "MR-2026-003", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "record_type": RecordType.LAB_REPORT.value, "title": "Comprehensive Blood Panel & HbA1c", "clinical_date": "2026-08-12", "file": {"storage_key": "blood_panel_003.pdf", "original_filename": "BloodPanel_PAT003.pdf", "content_type": "application/pdf", "size_bytes": 310000, "checksum": "bld789hash", "extension": ".pdf", "storage_provider": "local", "uploaded_at": now}, "uploaded_by": "USR-DOC-MEHTA-003", "source": RecordSource.DOCTOR.value, "status": RecordStatus.ACTIVE.value, "created_at": now, "updated_at": now},
            {"record_id": "MR-2026-004", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-REDDY-004", "department_id": "DEPT-PED", "record_type": RecordType.CLINICAL_DOCUMENT.value, "title": "Pediatric Skin Allergy Panel", "clinical_date": "2026-08-13", "file": {"storage_key": "allergy_001.pdf", "original_filename": "SkinAllergy_PAT001.pdf", "content_type": "application/pdf", "size_bytes": 180000, "checksum": "alg111hash", "extension": ".pdf", "storage_provider": "local", "uploaded_at": now}, "uploaded_by": "USR-DOC-REDDY-004", "source": RecordSource.DOCTOR.value, "status": RecordStatus.ACTIVE.value, "created_at": now, "updated_at": now},
            {"record_id": "MR-2026-005", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "record_type": RecordType.RADIOLOGY_REPORT.value, "title": "Knee Joint X-Ray Digital Imaging", "clinical_date": "2026-08-12", "file": {"storage_key": "xray_pat002.pdf", "original_filename": "Knee_XRay_PAT002.pdf", "content_type": "application/pdf", "size_bytes": 850000, "checksum": "xry222hash", "extension": ".pdf", "storage_provider": "local", "uploaded_at": now}, "uploaded_by": "USR-DOC-SINGH-005", "source": RecordSource.DOCTOR.value, "status": RecordStatus.ACTIVE.value, "created_at": now, "updated_at": now},
            {"record_id": "MR-2026-006", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "record_type": RecordType.CLINICAL_DOCUMENT.value, "title": "Echocardiogram Diagnostic Assessment", "clinical_date": "2026-08-07", "file": {"storage_key": "echo_pat003.pdf", "original_filename": "Echo_PAT003.pdf", "content_type": "application/pdf", "size_bytes": 520000, "checksum": "ech333hash", "extension": ".pdf", "storage_provider": "local", "uploaded_at": now}, "uploaded_by": "USR-DOC-RAO-001", "source": RecordSource.DOCTOR.value, "status": RecordStatus.ACTIVE.value, "created_at": now, "updated_at": now},
            {"record_id": "MR-2026-007", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "record_type": RecordType.RADIOLOGY_REPORT.value, "title": "Lumbar Spine MRI Scan", "clinical_date": "2026-08-05", "file": {"storage_key": "spine_mri_pat001.pdf", "original_filename": "Spine_MRI_PAT001.pdf", "content_type": "application/pdf", "size_bytes": 1600000, "checksum": "spn444hash", "extension": ".pdf", "storage_provider": "local", "uploaded_at": now}, "uploaded_by": "USR-DOC-SINGH-005", "source": RecordSource.DOCTOR.value, "status": RecordStatus.ACTIVE.value, "created_at": now, "updated_at": now},
            {"record_id": "MR-2026-008", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "record_type": RecordType.LAB_REPORT.value, "title": "Thyroid Function Test (T3, T4, TSH)", "clinical_date": "2026-08-04", "file": {"storage_key": "thyroid_pat002.pdf", "original_filename": "Thyroid_PAT002.pdf", "content_type": "application/pdf", "size_bytes": 220000, "checksum": "thy555hash", "extension": ".pdf", "storage_provider": "local", "uploaded_at": now}, "uploaded_by": "USR-DOC-MEHTA-003", "source": RecordSource.DOCTOR.value, "status": RecordStatus.ACTIVE.value, "created_at": now, "updated_at": now},
        ]

        for mr in med_records_list:
            await med_recs_col.update_one({"record_id": mr["record_id"]}, {"$set": mr}, upsert=True)

        # 9. Seed 10 Billing Records
        bills_list = [
            {"bill_id": "BILL-2026-001", "patient_id": "PAT-ONE-001", "appointment_id": "APT-2026-001", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "line_items": [{"item_code": "CONSULT-CARD", "description": "Cardiology Consultation Fee", "quantity": 1, "unit_price": 800.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 800.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 800.0, "amount_paid": 800.0, "balance_due": 0.0, "payments": [{"payment_id": "PAY-001", "amount": 800.0, "method": PaymentMethod.UPI.value, "status": PaymentStatus.COMPLETED.value, "reference_number": "UPI-987654", "paid_at": now, "recorded_by": "USR-ADM-DEMO-001"}], "status": BillingStatus.PAID.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
            {"bill_id": "BILL-2026-002", "patient_id": "PAT-TWO-002", "appointment_id": "APT-2026-002", "doctor_id": "DOC-RAO-001", "department_id": "DEPT-CARD", "line_items": [{"item_code": "CONSULT-CARD", "description": "Cardiology Consultation Fee", "quantity": 1, "unit_price": 800.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 800.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 800.0, "amount_paid": 800.0, "balance_due": 0.0, "payments": [{"payment_id": "PAY-002", "amount": 800.0, "method": PaymentMethod.CARD.value, "status": PaymentStatus.COMPLETED.value, "reference_number": "CARD-112233", "paid_at": now, "recorded_by": "USR-ADM-DEMO-001"}], "status": BillingStatus.PAID.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
            {"bill_id": "BILL-2026-003", "patient_id": "PAT-TWO-002", "appointment_id": "APT-2026-005", "doctor_id": "DOC-SHARMA-002", "department_id": "DEPT-NEUR", "line_items": [{"item_code": "CONSULT-NEUR", "description": "Neurology Consultation Fee", "quantity": 1, "unit_price": 1000.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 1000.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 1000.0, "amount_paid": 1000.0, "balance_due": 0.0, "payments": [{"payment_id": "PAY-003", "amount": 1000.0, "method": PaymentMethod.UPI.value, "status": PaymentStatus.COMPLETED.value, "reference_number": "UPI-445566", "paid_at": now, "recorded_by": "USR-ADM-DEMO-001"}], "status": BillingStatus.PAID.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
            {"bill_id": "BILL-2026-004", "patient_id": "PAT-ONE-001", "appointment_id": "APT-2026-007", "doctor_id": "DOC-SHARMA-002", "department_id": "DEPT-NEUR", "line_items": [{"item_code": "CONSULT-NEUR", "description": "Neurology Consultation Fee", "quantity": 1, "unit_price": 1000.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 1000.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 1000.0, "amount_paid": 0.0, "balance_due": 1000.0, "payments": [], "status": BillingStatus.ISSUED.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
            {"bill_id": "BILL-2026-005", "patient_id": "PAT-THREE-003", "appointment_id": "APT-2026-009", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "line_items": [{"item_code": "CONSULT-GEN", "description": "General Medicine Consultation Fee", "quantity": 1, "unit_price": 600.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 600.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 600.0, "amount_paid": 600.0, "balance_due": 0.0, "payments": [{"payment_id": "PAY-004", "amount": 600.0, "method": PaymentMethod.CASH.value, "status": PaymentStatus.COMPLETED.value, "reference_number": "CASH-778899", "paid_at": now, "recorded_by": "USR-ADM-DEMO-001"}], "status": BillingStatus.PAID.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
            {"bill_id": "BILL-2026-006", "patient_id": "PAT-ONE-001", "appointment_id": "APT-2026-010", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "line_items": [{"item_code": "CONSULT-GEN", "description": "General Medicine Consultation Fee", "quantity": 1, "unit_price": 600.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 600.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 600.0, "amount_paid": 0.0, "balance_due": 600.0, "payments": [], "status": BillingStatus.ISSUED.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
            {"bill_id": "BILL-2026-007", "patient_id": "PAT-ONE-001", "appointment_id": "APT-2026-013", "doctor_id": "DOC-REDDY-004", "department_id": "DEPT-PED", "line_items": [{"item_code": "CONSULT-PED", "description": "Pediatric Consultation Fee", "quantity": 1, "unit_price": 700.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 700.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 700.0, "amount_paid": 700.0, "balance_due": 0.0, "payments": [{"payment_id": "PAY-005", "amount": 700.0, "method": PaymentMethod.UPI.value, "status": PaymentStatus.COMPLETED.value, "reference_number": "UPI-332211", "paid_at": now, "recorded_by": "USR-ADM-DEMO-001"}], "status": BillingStatus.PAID.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
            {"bill_id": "BILL-2026-008", "patient_id": "PAT-TWO-002", "appointment_id": "APT-2026-017", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "line_items": [{"item_code": "CONSULT-ORTH", "description": "Orthopedic Consultation Fee", "quantity": 1, "unit_price": 900.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 900.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 900.0, "amount_paid": 900.0, "balance_due": 0.0, "payments": [{"payment_id": "PAY-006", "amount": 900.0, "method": PaymentMethod.CARD.value, "status": PaymentStatus.COMPLETED.value, "reference_number": "CARD-998877", "paid_at": now, "recorded_by": "USR-ADM-DEMO-001"}], "status": BillingStatus.PAID.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
            {"bill_id": "BILL-2026-009", "patient_id": "PAT-ONE-001", "appointment_id": "APT-2026-019", "doctor_id": "DOC-SINGH-005", "department_id": "DEPT-ORTH", "line_items": [{"item_code": "CONSULT-ORTH", "description": "Orthopedic Consultation Fee", "quantity": 1, "unit_price": 900.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 900.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 900.0, "amount_paid": 0.0, "balance_due": 900.0, "payments": [], "status": BillingStatus.ISSUED.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
            {"bill_id": "BILL-2026-010", "patient_id": "PAT-THREE-003", "appointment_id": "APT-2026-012", "doctor_id": "DOC-MEHTA-003", "department_id": "DEPT-GEN", "line_items": [{"item_code": "CONSULT-GEN", "description": "General Medicine Consultation Fee", "quantity": 1, "unit_price": 600.0, "tax_percent": 0.0, "discount_amount": 0.0}], "subtotal": 600.0, "total_tax": 0.0, "total_discount": 0.0, "grand_total": 600.0, "amount_paid": 600.0, "balance_due": 0.0, "payments": [{"payment_id": "PAY-007", "amount": 600.0, "method": PaymentMethod.UPI.value, "status": PaymentStatus.COMPLETED.value, "reference_number": "UPI-554433", "paid_at": now, "recorded_by": "USR-ADM-DEMO-001"}], "status": BillingStatus.PAID.value, "created_by": "USR-ADM-DEMO-001", "created_at": now, "updated_at": now},
        ]

        for b in bills_list:
            await billing_col.update_one({"bill_id": b["bill_id"]}, {"$set": b}, upsert=True)

        # 10. Seed 6 Follow-ups
        followups_list = [
            {"follow_up_id": "FWU-2026-001", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-RAO-001", "appointment_id": "APT-2026-001", "scheduled_date": now, "reason": "Cardiac Angina Follow-up", "status": FollowUpStatus.SCHEDULED.value, "created_at": now, "updated_at": now},
            {"follow_up_id": "FWU-2026-002", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-RAO-001", "appointment_id": "APT-2026-002", "scheduled_date": now, "reason": "Hypertension BP Evaluation", "status": FollowUpStatus.COMPLETED.value, "created_at": now, "updated_at": now},
            {"follow_up_id": "FWU-2026-003", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SHARMA-002", "appointment_id": "APT-2026-005", "scheduled_date": now, "reason": "Migraine Treatment Response", "status": FollowUpStatus.COMPLETED.value, "created_at": now, "updated_at": now},
            {"follow_up_id": "FWU-2026-004", "patient_id": "PAT-THREE-003", "doctor_id": "DOC-MEHTA-003", "appointment_id": "APT-2026-009", "scheduled_date": now, "reason": "Vitamin D Level Recheck", "status": FollowUpStatus.SCHEDULED.value, "created_at": now, "updated_at": now},
            {"follow_up_id": "FWU-2026-005", "patient_id": "PAT-ONE-001", "doctor_id": "DOC-REDDY-004", "appointment_id": "APT-2026-013", "scheduled_date": now, "reason": "Eczema Rash Monitoring", "status": FollowUpStatus.COMPLETED.value, "created_at": now, "updated_at": now},
            {"follow_up_id": "FWU-2026-006", "patient_id": "PAT-TWO-002", "doctor_id": "DOC-SINGH-005", "appointment_id": "APT-2026-017", "scheduled_date": now, "reason": "Knee Mobility & Quad Strengthening", "status": FollowUpStatus.SCHEDULED.value, "created_at": now, "updated_at": now},
        ]

        for f in followups_list:
            await followups_col.update_one({"follow_up_id": f["follow_up_id"]}, {"$set": f}, upsert=True)

        # 11. Seed Medical Documents and Imaging with real patient linkage
        from pathlib import Path
        doc_storage_dir = Path("uploads/documents").resolve()
        doc_storage_dir.mkdir(parents=True, exist_ok=True)

        # Valid sample JPEG bytes for image preview & download
        sample_img_bytes = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xff\xdb\x00C\x00"
            b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19"
            b"\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f"
            b"'9=82<.342\xff\xc0\x00\x0b\x08\x00\x10\x00\x10\x01\x01\x11\x00\xff\xc4\x00\x1f"
            b"\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02"
            b"\x03\x04\x05\x06\x07\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )
        sample_pdf_bytes = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\nxref\n0 4\n0000000000 65535 f \n0000000009 00000 n \n0000000052 00000 n \n0000000109 00000 n \ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF\n"

        # Resolve training dataset sample images if available for realistic AI model execution
        root_dir = Path(__file__).resolve().parent.parent.parent.parent
        notumor_sample = root_dir / "model-training" / "brain" / "dataset" / "Training" / "notumor" / "Tr-no_15.jpg"
        glioma_sample = root_dir / "model-training" / "brain" / "dataset" / "Training" / "glioma" / "Tr-gl_15.jpg"

        mri_pat1_bytes = notumor_sample.read_bytes() if notumor_sample.exists() else sample_img_bytes
        mri_pat2_bytes = glioma_sample.read_bytes() if glioma_sample.exists() else sample_img_bytes

        documents_list = [
            {
                "document_id": "DOC-2026-001",
                "patient_id": "PAT-ONE-001",
                "uploaded_by": "USR-DOC-RAO-001",
                "title": "Brain MRI T1 Axial Scan",
                "category": DocumentCategory.MRI.value,
                "file_name": "doc_brain_mri_pat1.jpg",
                "original_file_name": "Brain_MRI_T1_Axial.jpg",
                "mime_type": "image/jpeg",
                "file_size_bytes": len(mri_pat1_bytes),
                "storage_path": str(doc_storage_dir / "doc_brain_mri_pat1.jpg"),
                "notes": "High-resolution axial brain MRI scan.",
                "medical_record_id": "MR-2026-001",
                "appointment_id": "APT-2026-001",
                "consultation_id": "CNS-2026-002",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
            },
            {
                "document_id": "DOC-2026-002",
                "patient_id": "PAT-ONE-001",
                "uploaded_by": "USR-DOC-RAO-001",
                "title": "Resting ECG Electrocardiogram",
                "category": DocumentCategory.LAB_REPORT.value,
                "file_name": "resting_ecg_pat001.pdf",
                "original_file_name": "Resting_ECG_PAT001.pdf",
                "mime_type": "application/pdf",
                "file_size_bytes": len(sample_pdf_bytes),
                "storage_path": str(doc_storage_dir / "resting_ecg_pat001.pdf"),
                "notes": "Normal sinus rhythm, 72 bpm.",
                "medical_record_id": "MR-2026-001",
                "appointment_id": "APT-2026-004",
                "consultation_id": "CNS-2026-002",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
            },
            {
                "document_id": "DOC-2026-003",
                "patient_id": "PAT-TWO-002",
                "uploaded_by": "USR-DOC-SHARMA-002",
                "title": "Brain MRI T1/T2 Axial Scan",
                "category": DocumentCategory.MRI.value,
                "file_name": "brain_mri_pat002.jpg",
                "original_file_name": "Brain_MRI_Axial.jpg",
                "mime_type": "image/jpeg",
                "file_size_bytes": len(mri_pat2_bytes),
                "storage_path": str(doc_storage_dir / "brain_mri_pat002.jpg"),
                "notes": "High resolution neuro-imaging; negative for intracranial masses.",
                "medical_record_id": "MR-2026-002",
                "appointment_id": "APT-2026-005",
                "consultation_id": "CNS-2026-003",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
            },
            {
                "document_id": "DOC-2026-004",
                "patient_id": "PAT-TWO-002",
                "uploaded_by": "USR-DOC-SINGH-005",
                "title": "Right Knee Joint X-Ray",
                "category": DocumentCategory.XRAY.value,
                "file_name": "knee_xray_pat002.jpg",
                "original_file_name": "Right_Knee_XRay.jpg",
                "mime_type": "image/jpeg",
                "file_size_bytes": len(sample_img_bytes),
                "storage_path": str(doc_storage_dir / "knee_xray_pat002.jpg"),
                "notes": "Minor patellofemoral joint space narrowing.",
                "medical_record_id": "MR-2026-005",
                "appointment_id": "APT-2026-017",
                "consultation_id": "CNS-2026-009",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
            },
            {
                "document_id": "DOC-2026-005",
                "patient_id": "PAT-THREE-003",
                "uploaded_by": "USR-DOC-MEHTA-003",
                "title": "Retinal Fundus Photography",
                "category": DocumentCategory.FUNDUS.value,
                "file_name": "fundus_pat003.jpg",
                "original_file_name": "Retinal_Fundus_Color.jpg",
                "mime_type": "image/jpeg",
                "file_size_bytes": len(sample_img_bytes),
                "storage_path": str(doc_storage_dir / "fundus_pat003.jpg"),
                "notes": "Diabetic retinopathy screening photograph.",
                "medical_record_id": "MR-2026-003",
                "appointment_id": "APT-2026-009",
                "consultation_id": "CNS-2026-005",
                "ai_analysis_id": "AI-2026-003",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now,
            },
        ]

        for d in documents_list:
            fpath = doc_storage_dir / d["file_name"]
            if d["file_name"] == "doc_brain_mri_pat1.jpg":
                fpath.write_bytes(mri_pat1_bytes)
            elif d["file_name"] == "brain_mri_pat002.jpg":
                fpath.write_bytes(mri_pat2_bytes)
            elif not fpath.exists():
                fbytes = sample_pdf_bytes if d["mime_type"] == "application/pdf" else sample_img_bytes
                fpath.write_bytes(fbytes)
            await docs_col.update_one({"document_id": d["document_id"]}, {"$set": d}, upsert=True)

        # 13. Seed AI Analyses
        ai_analyses_list = [
            {
                "analysis_id": "AI-2026-001",
                "patient_id": "PAT-ONE-001",
                "doctor_id": "DOC-RAO-001",
                "appointment_id": "APT-2026-001",
                "consultation_id": "CNS-2026-002",
                "medical_record_id": "MR-2026-001",
                "analysis_type": "Chest X-Ray",
                "model": {"module_id": "CHEST_XRAY", "name": "Chest X-Ray Diagnostic Model", "version": "1.0.0", "architecture": "ResNet50"},
                "input": {"medical_record_id": "MR-2026-001", "record_type": "RADIOLOGY_REPORT", "content_type": "image/jpeg"},
                "prediction": {
                    "predicted_class": "Pneumonia",
                    "confidence": 0.94,
                    "class_probabilities": {"Pneumonia": 0.94, "Normal": 0.04, "COVID-19": 0.02},
                    "clinical_summary": "High probability of consolidative infiltrate in right lower lobe."
                },
                "status": "awaiting_review",
                "gradcam_path": "available",
                "requested_by": "USR-DOC-RAO-001",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "analysis_id": "AI-2026-002",
                "patient_id": "PAT-TWO-002",
                "doctor_id": "DOC-SHARMA-002",
                "appointment_id": "APT-2026-005",
                "consultation_id": "CNS-2026-003",
                "medical_record_id": "MR-2026-002",
                "analysis_type": "Brain MRI",
                "model": {"module_id": "BRAIN_MRI", "name": "Brain MRI Neuro-Analysis", "version": "1.0.0", "architecture": "DenseNet121"},
                "input": {"medical_record_id": "MR-2026-002", "record_type": "RADIOLOGY_REPORT", "content_type": "image/jpeg"},
                "prediction": {
                    "predicted_class": "No Tumor Detected",
                    "confidence": 0.98,
                    "class_probabilities": {"No Tumor Detected": 0.98, "Glioma": 0.01, "Meningioma": 0.01},
                    "clinical_summary": "Unremarkable cerebral parenchyma without focal mass lesion or midline shift."
                },
                "status": "reviewed",
                "review": {
                    "decision": "accepted",
                    "clinical_interpretation": "Confirmed no intracranial space-occupying lesion.",
                    "reviewed_by": "USR-DOC-SHARMA-002",
                    "reviewed_at": now
                },
                "gradcam_path": "available",
                "requested_by": "USR-DOC-SHARMA-002",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now
            },
            {
                "analysis_id": "AI-2026-003",
                "patient_id": "PAT-THREE-003",
                "doctor_id": "DOC-MEHTA-003",
                "appointment_id": "APT-2026-009",
                "consultation_id": "CNS-2026-005",
                "medical_record_id": "MR-2026-003",
                "analysis_type": "Retinopathy",
                "model": {"module_id": "RETINOPATHY", "name": "Diabetic Retinopathy Screener", "version": "1.0.0", "architecture": "EfficientNetB0"},
                "input": {"medical_record_id": "MR-2026-003", "record_type": "LAB_REPORT", "content_type": "image/jpeg"},
                "prediction": {
                    "predicted_class": "Mild Nonproliferative Retinopathy",
                    "confidence": 0.89,
                    "class_probabilities": {"Mild Nonproliferative Retinopathy": 0.89, "No DR": 0.08, "Moderate DR": 0.03},
                    "clinical_summary": "Scattered microaneurysms detected in peripheral retina."
                },
                "status": "awaiting_review",
                "gradcam_path": "available",
                "requested_by": "USR-DOC-MEHTA-003",
                "is_deleted": False,
                "created_at": now,
                "updated_at": now
            }
        ]
        # 14. Seed Persistent Notifications across all roles (Patients, Doctors, Staff, Admin)
        notifications_col = db[COLLECTION_NOTIFICATIONS]
        notifications_list = [
            # Patient 1 (patient.one@clinixai.com / USR-PAT-ONE-001)
            {
                "notification_id": "NTF-SEED-001",
                "recipient_user_id": "USR-PAT-ONE-001",
                "notification_type": "appointment_confirmed",
                "channel": "in_app",
                "status": "sent",
                "title": "Appointment Confirmed",
                "body": "Your appointment APT-2026-001 with Dr. Arjun Rao on 2026-08-15 at 09:00 AM is confirmed.",
                "reference_id": "APT-2026-001",
                "reference_type": "appointment",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "notification_id": "NTF-SEED-002",
                "recipient_user_id": "USR-PAT-ONE-001",
                "notification_type": "prescription_issued",
                "channel": "in_app",
                "status": "sent",
                "title": "Prescription Issued",
                "body": "Dr. Arjun Rao issued prescription RX-2026-002 for Angina Pectoris.",
                "reference_id": "RX-2026-002",
                "reference_type": "prescription",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "notification_id": "NTF-SEED-003",
                "recipient_user_id": "USR-PAT-ONE-001",
                "notification_type": "bill_issued",
                "channel": "in_app",
                "status": "sent",
                "title": "Invoice Generated",
                "body": "Bill BILL-2026-001 for ₹800.00 is ready for payment.",
                "reference_id": "BILL-2026-001",
                "reference_type": "billing",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "notification_id": "NTF-SEED-004",
                "recipient_user_id": "USR-PAT-ONE-001",
                "notification_type": "follow_up_scheduled",
                "channel": "in_app",
                "status": "sent",
                "title": "Follow-Up Scheduled",
                "body": "Follow-up consultation FWU-2026-001 with Dr. Arjun Rao is scheduled.",
                "reference_id": "FWU-2026-001",
                "reference_type": "follow_up",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },

            # Patient 2 (patient.two@clinixai.com / USR-PAT-TWO-002)
            {
                "notification_id": "NTF-SEED-005",
                "recipient_user_id": "USR-PAT-TWO-002",
                "notification_type": "appointment_confirmed",
                "channel": "in_app",
                "status": "sent",
                "title": "Appointment Confirmed",
                "body": "Your appointment APT-2026-002 with Dr. Arjun Rao is confirmed.",
                "reference_id": "APT-2026-002",
                "reference_type": "appointment",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "notification_id": "NTF-SEED-006",
                "recipient_user_id": "USR-PAT-TWO-002",
                "notification_type": "consultation_completed",
                "channel": "in_app",
                "status": "sent",
                "title": "Consultation Completed",
                "body": "Your consultation CNS-2026-003 with Dr. Priya Sharma is completed.",
                "reference_id": "CNS-2026-003",
                "reference_type": "consultation",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "notification_id": "NTF-SEED-007",
                "recipient_user_id": "USR-PAT-TWO-002",
                "notification_type": "bill_issued",
                "channel": "in_app",
                "status": "sent",
                "title": "Invoice Generated",
                "body": "Bill BILL-2026-002 for ₹800.00 is generated.",
                "reference_id": "BILL-2026-002",
                "reference_type": "billing",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },

            # Patient 3 (patient.three@clinixai.com / USR-PAT-THREE-003)
            {
                "notification_id": "NTF-SEED-008",
                "recipient_user_id": "USR-PAT-THREE-003",
                "notification_type": "medical_record_uploaded",
                "channel": "in_app",
                "status": "sent",
                "title": "Medical Record Uploaded",
                "body": "Comprehensive Blood Panel MR-2026-003 has been added to your records.",
                "reference_id": "MR-2026-003",
                "reference_type": "document",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "notification_id": "NTF-SEED-009",
                "recipient_user_id": "USR-PAT-THREE-003",
                "notification_type": "bill_issued",
                "channel": "in_app",
                "status": "sent",
                "title": "Invoice Generated",
                "body": "Bill BILL-2026-005 for ₹600.00 is generated.",
                "reference_id": "BILL-2026-005",
                "reference_type": "billing",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },

            # Doctor 1 (Dr. Arjun Rao / USR-DOC-RAO-001)
            {
                "notification_id": "NTF-SEED-010",
                "recipient_user_id": "USR-DOC-RAO-001",
                "notification_type": "appointment_booked",
                "channel": "in_app",
                "status": "sent",
                "title": "New Appointment Scheduled",
                "body": "Patient Patient One booked appointment APT-2026-001 for Cardiac Evaluation.",
                "reference_id": "APT-2026-001",
                "reference_type": "appointment",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },
            {
                "notification_id": "NTF-SEED-011",
                "recipient_user_id": "USR-DOC-RAO-001",
                "notification_type": "ai_analysis_completed",
                "channel": "in_app",
                "status": "sent",
                "title": "AI Chest X-Ray Analysis Ready",
                "body": "Chest X-Ray analysis AI-2026-001 for Patient One is awaiting clinical review.",
                "reference_id": "AI-2026-001",
                "reference_type": "ai_analysis",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },

            # Doctor 2 (Dr. Priya Sharma / USR-DOC-SHARMA-002)
            {
                "notification_id": "NTF-SEED-012",
                "recipient_user_id": "USR-DOC-SHARMA-002",
                "notification_type": "medical_record_uploaded",
                "channel": "in_app",
                "status": "sent",
                "title": "Patient Document Uploaded",
                "body": "Patient Patient Two uploaded Brain MRI scan MR-2026-002 for review.",
                "reference_id": "MR-2026-002",
                "reference_type": "document",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },

            # Doctor 3 (Dr. Rahul Mehta / USR-DOC-MEHTA-003)
            {
                "notification_id": "NTF-SEED-013",
                "recipient_user_id": "USR-DOC-MEHTA-003",
                "notification_type": "ai_analysis_completed",
                "channel": "in_app",
                "status": "sent",
                "title": "Retinopathy AI Screener Result",
                "body": "Retinopathy screening AI-2026-003 for Patient Three is ready for review.",
                "reference_id": "AI-2026-003",
                "reference_type": "ai_analysis",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },

            # Doctor 4 (Dr. Ananya Reddy / USR-DOC-REDDY-004)
            {
                "notification_id": "NTF-SEED-014",
                "recipient_user_id": "USR-DOC-REDDY-004",
                "notification_type": "appointment_booked",
                "channel": "in_app",
                "status": "sent",
                "title": "New Appointment Scheduled",
                "body": "Patient Patient One booked pediatric appointment APT-2026-013.",
                "reference_id": "APT-2026-013",
                "reference_type": "appointment",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },

            # Doctor 5 (Dr. Vikram Singh / USR-DOC-SINGH-005)
            {
                "notification_id": "NTF-SEED-015",
                "recipient_user_id": "USR-DOC-SINGH-005",
                "notification_type": "follow_up_scheduled",
                "channel": "in_app",
                "status": "sent",
                "title": "Orthopedic Follow-Up Scheduled",
                "body": "Follow-up FWU-2026-006 for Patient Two is scheduled.",
                "reference_id": "FWU-2026-006",
                "reference_type": "follow_up",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },

            # Staff (staff.one@clinixai.com / USR-STF-ONE-001)
            {
                "notification_id": "NTF-SEED-016",
                "recipient_user_id": "USR-STF-ONE-001",
                "notification_type": "checkin_success",
                "channel": "in_app",
                "status": "sent",
                "title": "Patient Checked In",
                "body": "Patient Two checked in at reception. Token issued for APT-2026-002.",
                "reference_id": "APT-2026-002",
                "reference_type": "appointment",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },

            # Admin (admin@clinixai.com / USR-ADM-DEMO-001)
            {
                "notification_id": "NTF-SEED-017",
                "recipient_user_id": "USR-ADM-DEMO-001",
                "notification_type": "system",
                "channel": "in_app",
                "status": "sent",
                "title": "Clinical Portal Initialization",
                "body": "CliniXAI portal initialized with 5 specialized departments and live MongoDB sync.",
                "reference_id": "SYS-INIT",
                "reference_type": "system",
                "sent_at": now,
                "created_at": now,
                "updated_at": now,
            },
        ]

        for ntf_doc in notifications_list:
            await notifications_col.update_one({"notification_id": ntf_doc["notification_id"]}, {"$set": ntf_doc}, upsert=True)

        # 15. Seed Persistent Audit Logs
        audit_col = db[COLLECTION_AUDIT_LOGS]
        audit_logs_list = [
            {
                "audit_id": "AUD-SEED-001",
                "actor_id": "USR-ADM-DEMO-001",
                "role": "hospital_admin",
                "action": "bootstrap_system",
                "resource": "system",
                "resource_id": "SYS-001",
                "timestamp": now,
                "metadata": {"event": "Initial system bootstrapping and security configuration"}
            },
            {
                "audit_id": "AUD-SEED-002",
                "actor_id": "USR-PAT-ONE-001",
                "role": "patient",
                "action": "create_appointment",
                "resource": "appointment",
                "resource_id": "APT-2026-001",
                "timestamp": now,
                "metadata": {"patient_id": "PAT-ONE-001", "doctor_id": "DOC-RAO-001"}
            },
            {
                "audit_id": "AUD-SEED-003",
                "actor_id": "USR-DOC-RAO-001",
                "role": "doctor",
                "action": "start_consultation",
                "resource": "consultation",
                "resource_id": "CNS-2026-001",
                "timestamp": now,
                "metadata": {"appointment_id": "APT-2026-001", "doctor_id": "DOC-RAO-001", "patient_id": "PAT-ONE-001"}
            },
            {
                "audit_id": "AUD-SEED-004",
                "actor_id": "USR-DOC-RAO-001",
                "role": "doctor",
                "action": "complete_consultation",
                "resource": "consultation",
                "resource_id": "CNS-2026-001",
                "timestamp": now,
                "metadata": {"appointment_id": "APT-2026-001", "doctor_id": "DOC-RAO-001", "patient_id": "PAT-ONE-001"}
            },
            {
                "audit_id": "AUD-SEED-005",
                "actor_id": "USR-STF-ONE-001",
                "role": "hospital_staff",
                "action": "create_bill",
                "resource": "billing",
                "resource_id": "BILL-2026-001",
                "timestamp": now,
                "metadata": {"patient_id": "PAT-ONE-001", "amount": 800.0}
            },
            {
                "audit_id": "AUD-SEED-006",
                "actor_id": "USR-PAT-ONE-001",
                "role": "patient",
                "action": "record_payment",
                "resource": "billing",
                "resource_id": "BILL-2026-001",
                "timestamp": now,
                "metadata": {"patient_id": "PAT-ONE-001", "payment_method": "UPI", "amount": 800.0}
            },
            {
                "audit_id": "AUD-SEED-007",
                "actor_id": "USR-DOC-SHARMA-002",
                "role": "doctor",
                "action": "review_ai_analysis",
                "resource": "ai_analysis",
                "resource_id": "AI-2026-002",
                "timestamp": now,
                "metadata": {"patient_id": "PAT-TWO-002", "decision": "accepted"}
            },
        ]

        for audit_doc in audit_logs_list:
            await audit_col.update_one({"audit_id": audit_doc["audit_id"]}, {"$set": audit_doc}, upsert=True)

        # 16. Bootstrap Hospital Admin User explicitly
        admin_user_doc = {
            "user_id": "USR-ADM-DEMO-001",
            "email": "admin@clinixai.com",
            "full_name": "Primary Hospital Administrator",
            "password_hash": hash_password("admin123"),
            "role": UserRole.HOSPITAL_ADMIN.value,
            "auth_provider": AuthProvider.LOCAL.value,
            "email_verified": True,
            "account_status": AccountStatus.ACTIVE.value,
            "is_deleted": False,
            "created_at": now,
            "updated_at": now,
        }
        await users_col.update_one({"email": "admin@clinixai.com"}, {"$set": admin_user_doc}, upsert=True)
        await bootstrap_hospital_admin(db)

        logger.info("Idempotent MongoDB dataset seeding completed successfully.")
        try:
            from app.database.mongodb import save_in_memory_snapshot
            await save_in_memory_snapshot(db)
        except Exception:
            pass

    except Exception as exc:
        logger.warning(f"Database seeder warning: {exc}")


if __name__ == "__main__":
    import asyncio
    from app.database.mongodb import connect_to_mongo, close_mongo_connection, db_manager
    async def _run():
        await connect_to_mongo()
        if db_manager.db is not None:
            await seed_initial_data(db_manager.db)
        await close_mongo_connection()
    asyncio.run(_run())
