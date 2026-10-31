"""Hospital Admin Bootstrap Service.

Provides controlled, idempotent provisioning of the primary Hospital Admin account.
Hospital Admin accounts are NEVER publicly registrable via HTTP endpoints.
"""

import os
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logging import logger
from app.core.security import hash_password, validate_password_policy
from app.database.collections import COLLECTION_USERS
from app.database.mongodb import connect_to_mongo, close_mongo_connection, get_db
from app.models.user import UserInDB, UserRole, AuthProvider, AccountStatus
from app.utils.id_generator import generate_user_id
from app.utils.datetime import utc_now


async def bootstrap_hospital_admin(
    db: AsyncIOMotorDatabase,
    email: str = "admin@clinixai.com",
    password: str = "admin123",
    full_name: str = "Primary Hospital Administrator",
) -> Optional[UserInDB]:
    """Idempotently provisions or updates the primary Hospital Admin account in MongoDB.
    
    Reads credentials from parameters or environment variables ADMIN_EMAIL and ADMIN_PASSWORD.
    Ensures email=admin@clinixai.com, password=admin123 (hashed), role=HOSPITAL_ADMIN,
    account_status=ACTIVE, and email_verified=True.
    """
    admin_email = os.getenv("ADMIN_EMAIL", email).strip().lower()
    admin_pass = os.getenv("ADMIN_PASSWORD", password)
    admin_name = os.getenv("ADMIN_FULL_NAME", full_name).strip()

    validate_password_policy(admin_pass)
    new_hash = hash_password(admin_pass)
    now = utc_now()

    # Check if an admin exists by email OR by HOSPITAL_ADMIN role
    existing = await db[COLLECTION_USERS].find_one({
        "$or": [
            {"email": admin_email},
            {"role": UserRole.HOSPITAL_ADMIN.value},
            {"email": "admin@clinixai.dev"},
        ]
    })

    if existing:
        user_id = existing["user_id"]
        # Update existing admin account to guarantee exact required credentials and status
        await db[COLLECTION_USERS].update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "email": admin_email,
                "full_name": admin_name,
                "password_hash": new_hash,
                "role": UserRole.HOSPITAL_ADMIN.value,
                "account_status": AccountStatus.ACTIVE.value,
                "email_verified": True,
                "is_deleted": False,
                "updated_at": now,
            }}
        )
        updated_dict = await db[COLLECTION_USERS].find_one({"_id": existing["_id"]})
        logger.info(f"Idempotently updated Hospital Admin account: {user_id} ({admin_email})")
        return UserInDB(**updated_dict)

    user_id = generate_user_id()
    admin_doc = UserInDB(
        user_id=user_id,
        email=admin_email,
        full_name=admin_name,
        password_hash=new_hash,
        role=UserRole.HOSPITAL_ADMIN,
        auth_provider=AuthProvider.LOCAL,
        email_verified=True,
        account_status=AccountStatus.ACTIVE,
        created_at=now,
        updated_at=now,
    )

    await db[COLLECTION_USERS].insert_one(admin_doc.to_mongo_dict())
    logger.info(f"Successfully bootstrapped initial Hospital Admin account: {user_id} ({admin_email})")
    return admin_doc

