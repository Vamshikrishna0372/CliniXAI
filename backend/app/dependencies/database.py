"""FastAPI dependency for accessing the MongoDB database instance."""

from motor.motor_asyncio import AsyncIOMotorDatabase
from app.database.mongodb import get_db, db_manager
from app.core.exceptions import DatabaseUnavailableError


async def get_database() -> AsyncIOMotorDatabase:
    """FastAPI Dependency providing access to the initialized MongoDB database instance.
    
    Raises DatabaseUnavailableError if the connection is unavailable.
    """
    if db_manager.db is None:
        raise DatabaseUnavailableError("MongoDB database connection is not initialized.")
    return get_db()
