"""Asynchronous MongoDB connection architecture and lifecycle manager."""

import asyncio
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.core.config import settings
from app.core.logging import logger


class MongoDBManager:
    """Manages the lifecycle of the AsyncIOMotorClient and database handle."""

    def __init__(self) -> None:
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None


db_manager = MongoDBManager()


import json
import os
from pathlib import Path

# Store persistence snapshots at workspace root to prevent uvicorn --reload file-watcher restart loops
_WORKSPACE_DIR = Path(__file__).resolve().parent.parent.parent.parent
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
SNAPSHOT_DIR = _WORKSPACE_DIR / ".data_persist"
if not SNAPSHOT_DIR.exists() and (_BACKEND_DIR / ".data_persist").exists():
    SNAPSHOT_DIR = _BACKEND_DIR / ".data_persist"

ALL_COLLECTIONS = [
    "users", "patients", "doctors", "staff", "departments",
    "appointments", "consultations", "prescriptions", "medical_records",
    "billing", "notifications", "ai_analyses", "follow_ups",
    "payments", "documents", "audit_logs", "user_sessions",
    "hospital_settings"
]


async def save_in_memory_snapshot(db: Optional[AsyncIOMotorDatabase] = None) -> None:
    """Serializes in-memory collections to disk for restart persistence."""
    target_db = db or db_manager.db
    if target_db is None:
        return
    try:
        SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
        for col_name in ALL_COLLECTIONS:
            docs = await target_db[col_name].find({}).to_list(length=1000)
            clean_docs = []
            for d in docs:
                cd = dict(d)
                if "_id" in cd:
                    cd["_id"] = str(cd["_id"])
                # Exclude temporary or malformed test records lacking mandatory schema
                if col_name == "ai_analyses" and ("SAFETY" in cd.get("analysis_id", "") or not cd.get("model")):
                    continue
                if col_name == "users" and (cd.get("email") in ["hacker.admin@clinixai.com", "invited.doc@clinixai.com"] or cd.get("email", "").endswith("@clinixai.test")):
                    continue
                clean_docs.append(cd)
            file_path = SNAPSHOT_DIR / f"{col_name}.json"
            # Merge live collection documents with existing disk snapshot to preserve across test runs
            existing_docs = []
            if file_path.exists() and file_path.stat().st_size > 5:
                try:
                    with open(file_path, "r", encoding="utf-8") as f_in:
                        existing_docs = json.load(f_in)
                    if not isinstance(existing_docs, list):
                        existing_docs = []
                except Exception:
                    existing_docs = []

            # Canonical collection-specific primary keys
            COLLECTION_PK_MAP = {
                "billing": "bill_id",
                "payments": "payment_id",
                "consultations": "consultation_id",
                "prescriptions": "prescription_id",
                "ai_analyses": "analysis_id",
                "medical_records": "record_id",
                "appointments": "appointment_id",
                "notifications": "notification_id",
                "patients": "patient_id",
                "doctors": "doctor_id",
                "staff": "staff_id",
                "departments": "department_id",
                "users": "email",
                "audit_logs": "audit_id",
                "hospital_settings": "setting_id",
                "documents": "document_id",
                "follow_ups": "follow_up_id",
            }
            pk_candidates = [COLLECTION_PK_MAP.get(col_name)] + [
                "document_id", "follow_up_id", "bill_id", "payment_id", "consultation_id", "prescription_id", "analysis_id",
                "record_id", "appointment_id", "notification_id", "user_id", "patient_id",
                "doctor_id", "email", "department_id"
            ]

            # Key-based merge
            merged_dict = {}
            for doc in existing_docs:
                k = None
                for pk in pk_candidates:
                    if pk and doc.get(pk) is not None:
                        k = f"{pk}:{doc[pk]}"
                        break
                if not k and "_id" in doc and doc["_id"] is not None:
                    k = f"_id:{doc['_id']}"
                if k:
                    merged_dict[k] = doc

            for doc in clean_docs:
                k = None
                for pk in pk_candidates:
                    if pk and doc.get(pk) is not None:
                        k = f"{pk}:{doc[pk]}"
                        break
                if not k and "_id" in doc and doc["_id"] is not None:
                    k = f"_id:{doc['_id']}"
                if k:
                    merged_dict[k] = doc
                else:
                    merged_dict[str(len(merged_dict))] = doc

            final_docs = list(merged_dict.values()) if merged_dict else clean_docs

            # Never overwrite a populated disk snapshot with an empty list
            if len(final_docs) == 0 and file_path.exists() and file_path.stat().st_size > 5:
                continue
            tmp_path = file_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(final_docs, f, default=str, indent=2)
            tmp_path.replace(file_path)
        logger.debug("Persisted in-memory database snapshot to disk.")
    except Exception as e:
        logger.warning(f"Could not persist in-memory database snapshot: {e}")


async def restore_in_memory_snapshot(db: AsyncIOMotorDatabase) -> bool:
    """Restores collections from disk snapshot if present."""
    if not SNAPSHOT_DIR.exists():
        return False
    restored = False
    COLLECTION_PK_MAP = {
        "billing": "bill_id",
        "payments": "payment_id",
        "consultations": "consultation_id",
        "prescriptions": "prescription_id",
        "ai_analyses": "analysis_id",
        "medical_records": "record_id",
        "appointments": "appointment_id",
        "notifications": "notification_id",
        "patients": "patient_id",
        "doctors": "doctor_id",
        "staff": "staff_id",
        "departments": "department_id",
        "users": "email",
        "audit_logs": "audit_id",
        "hospital_settings": "setting_id",
        "documents": "document_id",
        "follow_ups": "follow_up_id",
    }
    for col_name in ALL_COLLECTIONS:
        try:
            file_path = SNAPSHOT_DIR / f"{col_name}.json"
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    docs = json.load(f)
                if docs and isinstance(docs, list):
                    pk_candidates = [COLLECTION_PK_MAP.get(col_name)] + [
                        "document_id", "follow_up_id", "bill_id", "payment_id", "consultation_id", "prescription_id", "analysis_id",
                        "record_id", "appointment_id", "notification_id", "user_id", "patient_id",
                        "doctor_id", "email", "department_id"
                    ]
                    if await db[col_name].count_documents({}) == 0:
                        clean_docs = [{k: v for k, v in d.items() if k != "_id"} for d in docs]
                        if clean_docs:
                            await db[col_name].insert_many(clean_docs, ordered=False)
                            restored = True
                    else:
                        pk_key = COLLECTION_PK_MAP.get(col_name)
                        if pk_key:
                            existing_ids = set()
                            cursor = db[col_name].find({pk_key: {"$exists": True}}, {pk_key: 1})
                            async for doc_item in cursor:
                                if pk_key in doc_item:
                                    existing_ids.add(doc_item[pk_key])
                            missing_docs = [{k: v for k, v in d.items() if k != "_id"} for d in docs if d.get(pk_key) is not None and d.get(pk_key) not in existing_ids]
                            if missing_docs:
                                await db[col_name].insert_many(missing_docs, ordered=False)
                                restored = True
                        else:
                            for d in docs:
                                query = {}
                                for key in pk_candidates:
                                    if key and d.get(key) is not None:
                                        query = {key: d[key]}
                                        break
                                if not query and "_id" in d and d["_id"] is not None:
                                    query = {"_id": d["_id"]}
                                if query:
                                    clean_d = {k: v for k, v in d.items() if k != "_id"}
                                    res = await db[col_name].update_one(
                                        query,
                                        {"$setOnInsert": clean_d},
                                        upsert=True
                                    )
                                    if res.upserted_id is not None:
                                        restored = True
        except Exception as col_err:
            logger.warning(f"Failed to restore collection {col_name} from snapshot: {col_err}")
    if restored:
        logger.info("Restored persisted database snapshot from disk (atomic $setOnInsert, live records protected).")
    return restored


async def connect_to_mongo() -> None:
    """Initializes the MongoDB client and selects the configured database.
    
    Executed during application startup lifespan.
    """
    if db_manager.db is not None:
        return
    logger.info("Initializing MongoDB client pool...")
    if os.environ.get("PYTEST_CURRENT_TEST") or os.environ.get("USE_IN_MEMORY_DB"):
        from mongomock_motor import AsyncMongoMockClient
        db_manager.client = AsyncMongoMockClient()
        db_manager.db = db_manager.client[settings.MONGODB_DB_NAME]
        await restore_in_memory_snapshot(db_manager.db)
        logger.info("In-memory database pool initialized for testing.")
        return
    try:
        import certifi
        client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            tlsCAFile=certifi.where(),
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
        )
        db = client[settings.MONGODB_DB_NAME]
        await asyncio.wait_for(db.command("ping"), timeout=3.0)
        db_manager.client = client
        db_manager.db = db
        logger.info(f"MongoDB connection initialized for database: '{settings.MONGODB_DB_NAME}'")
    except Exception as exc:
        logger.warning(f"Remote MongoDB connection unavailable ({exc}). Initializing in-memory database pool.")
        try:
            from mongomock_motor import AsyncMongoMockClient
            db_manager.client = AsyncMongoMockClient()
            db_manager.db = db_manager.client[settings.MONGODB_DB_NAME]
            await restore_in_memory_snapshot(db_manager.db)
            logger.info("In-memory database pool initialized successfully.")
        except Exception as fallback_exc:
            logger.error(f"Failed to initialize fallback MongoDB client: {fallback_exc}")
            db_manager.client = None
            db_manager.db = None


async def close_mongo_connection() -> None:
    """Closes active MongoDB client connection pool cleanly.
    
    Executed during application shutdown lifespan.
    """
    logger.info("Closing MongoDB connection pool...")
    if db_manager.db is not None:
        try:
            await save_in_memory_snapshot(db_manager.db)
        except Exception:
            pass
    if db_manager.client is not None:
        try:
            db_manager.client.close()
        except Exception:
            pass
        db_manager.client = None
        db_manager.db = None
        logger.info("MongoDB connection pool closed.")


async def ping_database() -> bool:
    """Pings MongoDB to confirm database connectivity and availability.
    
    Returns True if reachable within timeout, False otherwise.
    """
    if db_manager.client is None or db_manager.db is None:
        return False
    try:
        await asyncio.wait_for(
            db_manager.db.command("ping"),
            timeout=3.0,
        )
        return True
    except Exception as exc:
        logger.warning(f"Database ping check failed: {exc}")
        return False


def get_db() -> AsyncIOMotorDatabase:
    """Returns active AsyncIOMotorDatabase instance or raises RuntimeError if uninitialized."""
    if db_manager.db is None:
        raise RuntimeError("Database instance is not initialized or MongoDB is unreachable.")
    return db_manager.db
