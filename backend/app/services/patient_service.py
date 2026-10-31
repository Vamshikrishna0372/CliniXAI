"""Patient management business logic service."""

from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import (
    ResourceNotFoundError, ResourceConflictError, ForbiddenError, AppValidationError
)
from app.database.collections import COLLECTION_PATIENTS, COLLECTION_USERS
from app.models.patient import PatientInDB, PatientStatus
from app.models.user import UserRole, AccountStatus, AuthProvider, UserInDB
from app.schemas.patients import CreatePatientRequest, UpdatePatientRequest
from app.utils.id_generator import generate_patient_id, generate_user_id
from app.utils.datetime import utc_now
from app.core.security import hash_password


class PatientService:
    """Business logic for patient profile management."""

    # Fields that cannot be updated by any client
    _PROTECTED_FIELDS = {"patient_id", "user_id", "created_at", "_id"}

    @staticmethod
    async def _find_by_patient_id(db: AsyncIOMotorDatabase, patient_id: str) -> Dict[str, Any]:
        """Internal: fetch patient document by patient_id or raise 404."""
        doc = await db[COLLECTION_PATIENTS].find_one({"patient_id": patient_id})
        if not doc:
            raise ResourceNotFoundError("Patient", patient_id)
        return doc

    @staticmethod
    async def create_patient(
        db: AsyncIOMotorDatabase,
        request: CreatePatientRequest,
        created_by_user_id: str,
    ) -> PatientInDB:
        """Staff/Admin creates a new patient profile.

        Does not create a linked user account — operational registration only.
        Patient can later claim the account via self-registration if email matches.
        """
        # Check for duplicate email
        if request.email:
            existing = await db[COLLECTION_PATIENTS].find_one({"email": request.email})
            if existing:
                raise ResourceConflictError(
                    f"A patient with email '{request.email}' already exists."
                )

        patient_id = generate_patient_id()

        address_dict = request.address.model_dump() if request.address else None
        ec_dict = request.emergency_contact.model_dump() if request.emergency_contact else None

        patient = PatientInDB(
            patient_id=patient_id,
            user_id=None,
            first_name=request.first_name,
            last_name=request.last_name,
            email=request.email,
            phone=request.phone,
            date_of_birth=request.date_of_birth,
            gender=request.gender,
            blood_group=request.blood_group,
            address=address_dict,
            emergency_contact=ec_dict,
            allergies=request.allergies,
            status=PatientStatus.ACTIVE,
            registered_by=created_by_user_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )

        await db[COLLECTION_PATIENTS].insert_one(patient.to_mongo_dict())
        logger.info(f"Patient created: {patient_id} by {created_by_user_id}")
        return patient

    @staticmethod
    async def get_patient_by_id(db: AsyncIOMotorDatabase, patient_id: str) -> Dict[str, Any]:
        """Fetch a patient document by patient_id."""
        return await PatientService._find_by_patient_id(db, patient_id)

    @staticmethod
    async def get_patient_by_user_id(
        db: AsyncIOMotorDatabase, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch a patient document linked to a specific user_id."""
        return await db[COLLECTION_PATIENTS].find_one({"user_id": user_id})

    @staticmethod
    async def update_patient(
        db: AsyncIOMotorDatabase,
        patient_id: str,
        request: UpdatePatientRequest,
        updater_user_id: str,
    ) -> Dict[str, Any]:
        """Update allowed patient profile fields."""
        await PatientService._find_by_patient_id(db, patient_id)

        updates: Dict[str, Any] = {}
        data = request.model_dump(exclude_none=True)

        for field, value in data.items():
            if field in PatientService._PROTECTED_FIELDS:
                continue
            if field == "date_of_birth" and value is not None:
                updates[field] = value.isoformat() if hasattr(value, "isoformat") else value
            elif field in ("address", "emergency_contact") and value is not None:
                updates[field] = value if isinstance(value, dict) else value.model_dump()
            else:
                updates[field] = value

        if not updates:
            return await PatientService._find_by_patient_id(db, patient_id)

        updates["updated_at"] = utc_now()
        await db[COLLECTION_PATIENTS].update_one(
            {"patient_id": patient_id},
            {"$set": updates}
        )
        try:
            import asyncio
            from app.database.mongodb import save_in_memory_snapshot
            asyncio.create_task(save_in_memory_snapshot(db))
        except Exception:
            pass
        logger.info(f"Patient {patient_id} updated by {updater_user_id}")
        return await PatientService._find_by_patient_id(db, patient_id)

    @staticmethod
    async def update_patient_status(
        db: AsyncIOMotorDatabase, patient_id: str, status: PatientStatus, updater_user_id: str
    ) -> Dict[str, Any]:
        """Activate or deactivate a patient profile."""
        await PatientService._find_by_patient_id(db, patient_id)
        await db[COLLECTION_PATIENTS].update_one(
            {"patient_id": patient_id},
            {"$set": {"status": status.value, "updated_at": utc_now()}}
        )
        logger.info(f"Patient {patient_id} status set to {status.value} by {updater_user_id}")
        return await PatientService._find_by_patient_id(db, patient_id)

    @staticmethod
    async def list_patients(
        db: AsyncIOMotorDatabase,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[PatientStatus] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Paginated, searchable patient list (Staff/Admin only)."""
        query: Dict[str, Any] = {"is_deleted": {"$ne": True}}

        if status:
            query["status"] = status.value

        if search:
            search_clean = search.strip()
            search_regex = {"$regex": search_clean, "$options": "i"}
            or_clauses = [
                {"patient_id": search_regex},
                {"first_name": search_regex},
                {"last_name": search_regex},
                {"email": search_regex},
                {"phone": search_regex},
            ]
            parts = search_clean.split()
            if len(parts) >= 2:
                or_clauses.append({
                    "first_name": {"$regex": parts[0], "$options": "i"},
                    "last_name": {"$regex": parts[1], "$options": "i"},
                })
            query["$or"] = or_clauses

        skip = (page - 1) * page_size
        total = await db[COLLECTION_PATIENTS].count_documents(query)
        cursor = db[COLLECTION_PATIENTS].find(query).sort("created_at", -1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return docs, total
