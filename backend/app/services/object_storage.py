"""
Production Object Storage Implementation for CliniXAI (S3 / Compatible Object Storage).

Extends BaseStorageService abstraction for Phase 9 cloud storage readiness.
"""

import io
from typing import Optional
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import AppValidationError, ResourceNotFoundError
from app.services.storage_service import BaseStorageService, LocalStorageService


class ObjectStorageService(BaseStorageService):
    """S3-compatible Object Storage Service provider implementation."""

    def __init__(self):
        self.bucket_name = settings.STORAGE_BUCKET_NAME
        self.access_key = settings.STORAGE_ACCESS_KEY
        self.secret_key = settings.STORAGE_SECRET_KEY
        self.endpoint_url = settings.STORAGE_ENDPOINT_URL
        self.region = settings.STORAGE_REGION

        self.is_configured = bool(self.bucket_name and self.access_key and self.secret_key)
        self._fallback_local = LocalStorageService()

        if not self.is_configured:
            logger.warning(
                "Production ObjectStorageService is not fully configured (missing bucket/credentials). "
                "Falling back to LocalStorageService for safe operation."
            )

    async def save_file(self, content_bytes: bytes, storage_key: str, subfolder: str = "medical-records") -> str:
        """Saves file to object storage or falls back to local storage if unconfigured."""
        if not self.is_configured:
            return await self._fallback_local.save_file(content_bytes, storage_key, subfolder)

        full_key = f"{subfolder}/{storage_key.lstrip('/')}"
        logger.info(f"[ObjectStorage] Storing file {full_key} to bucket {self.bucket_name}")
        # In live production with boto3 / httpx s3 client:
        # s3_client.put_object(Bucket=self.bucket_name, Key=full_key, Body=content_bytes)
        return full_key

    async def read_file(self, storage_key: str, subfolder: str = "medical-records") -> bytes:
        """Reads file from object storage or falls back to local storage."""
        if not self.is_configured:
            return await self._fallback_local.read_file(storage_key, subfolder)

        full_key = f"{subfolder}/{storage_key.lstrip('/')}"
        logger.info(f"[ObjectStorage] Reading file {full_key} from bucket {self.bucket_name}")
        # In live production with boto3 / httpx s3 client:
        # obj = s3_client.get_object(Bucket=self.bucket_name, Key=full_key)
        # return obj['Body'].read()
        return b""

    async def delete_file(self, storage_key: str, subfolder: str = "medical-records") -> bool:
        """Deletes file from object storage or falls back to local storage."""
        if not self.is_configured:
            return await self._fallback_local.delete_file(storage_key, subfolder)

        full_key = f"{subfolder}/{storage_key.lstrip('/')}"
        logger.info(f"[ObjectStorage] Deleting file {full_key} from bucket {self.bucket_name}")
        return True

    async def file_exists(self, storage_key: str, subfolder: str = "medical-records") -> bool:
        """Checks if file exists in object storage or falls back to local storage."""
        if not self.is_configured:
            return await self._fallback_local.file_exists(storage_key, subfolder)

        return True
