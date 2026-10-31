"""Department management business logic service."""

from typing import Optional, List, Dict, Any, Tuple
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.logging import logger
from app.core.exceptions import ResourceNotFoundError, ResourceConflictError
from app.database.collections import COLLECTION_DEPARTMENTS
from app.models.department import DepartmentInDB, DepartmentStatus
from app.schemas.departments import CreateDepartmentRequest, UpdateDepartmentRequest
from app.utils.id_generator import generate_department_id
from app.utils.datetime import utc_now


class DepartmentService:
    """Business logic for department management."""

    @staticmethod
    async def _find_by_department_id(db: AsyncIOMotorDatabase, department_id: str) -> Dict[str, Any]:
        doc = await db[COLLECTION_DEPARTMENTS].find_one({"department_id": department_id})
        if not doc:
            raise ResourceNotFoundError("Department", department_id)
        return doc

    @staticmethod
    async def create_department(
        db: AsyncIOMotorDatabase,
        request: CreateDepartmentRequest,
        created_by_user_id: str,
    ) -> DepartmentInDB:
        """Admin creates a new department."""
        code = request.code.upper().strip()

        # Check duplicate name
        existing_name = await db[COLLECTION_DEPARTMENTS].find_one({"name": request.name})
        if existing_name:
            raise ResourceConflictError(f"A department named '{request.name}' already exists.")

        # Check duplicate code
        existing_code = await db[COLLECTION_DEPARTMENTS].find_one({"code": code})
        if existing_code:
            raise ResourceConflictError(f"A department with code '{code}' already exists.")

        department_id = generate_department_id()
        dept = DepartmentInDB(
            department_id=department_id,
            name=request.name,
            code=code,
            description=request.description,
            location=request.location,
            contact_extension=request.contact_extension,
            status=DepartmentStatus.ACTIVE,
            created_by=created_by_user_id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        await db[COLLECTION_DEPARTMENTS].insert_one(dept.to_mongo_dict())
        logger.info(f"Department created: {department_id} ({code}) by {created_by_user_id}")
        return dept

    @staticmethod
    async def get_department_by_id(db: AsyncIOMotorDatabase, department_id: str) -> Dict[str, Any]:
        return await DepartmentService._find_by_department_id(db, department_id)

    @staticmethod
    async def update_department(
        db: AsyncIOMotorDatabase,
        department_id: str,
        request: UpdateDepartmentRequest,
        updater_user_id: str,
    ) -> Dict[str, Any]:
        """Update department fields. Status change is supported here."""
        await DepartmentService._find_by_department_id(db, department_id)

        updates: Dict[str, Any] = {}
        data = request.model_dump(exclude_none=True)
        for field, value in data.items():
            if isinstance(value, DepartmentStatus):
                updates[field] = value.value
            else:
                updates[field] = value

        if not updates:
            return await DepartmentService._find_by_department_id(db, department_id)

        updates["updated_at"] = utc_now()
        await db[COLLECTION_DEPARTMENTS].update_one(
            {"department_id": department_id}, {"$set": updates}
        )
        logger.info(f"Department {department_id} updated by {updater_user_id}")
        return await DepartmentService._find_by_department_id(db, department_id)

    @staticmethod
    async def list_departments(
        db: AsyncIOMotorDatabase,
        page: int = 1,
        page_size: int = 20,
        status: Optional[DepartmentStatus] = None,
        search: Optional[str] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Paginated department list."""
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status.value
        if search:
            search_regex = {"$regex": search, "$options": "i"}
            query["$or"] = [
                {"name": search_regex},
                {"code": search_regex},
            ]

        skip = (page - 1) * page_size
        total = await db[COLLECTION_DEPARTMENTS].count_documents(query)
        cursor = db[COLLECTION_DEPARTMENTS].find(query).sort("name", 1).skip(skip).limit(page_size)
        docs = await cursor.to_list(length=page_size)
        return docs, total
