"""Storage Service Abstraction Layer for CliniXAI.

Provides a clean interface for file storage.
- LocalStorageService handles filesystem storage for local development.
- Abstracted so future S3 / Cloud Object Storage can replace local storage without changing business logic.
"""

import os
import secrets
from abc import ABC, abstractmethod
from typing import Tuple, Optional
from pathlib import Path

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import AppValidationError, ResourceNotFoundError


class BaseStorageService(ABC):
    """Abstract Base Class for file storage providers."""

    @abstractmethod
    async def save_file(self, content_bytes: bytes, storage_key: str, subfolder: str = "medical-records") -> str:
        """Saves file content bytes and returns storage key / path reference."""
        pass

    @abstractmethod
    async def read_file(self, storage_key: str, subfolder: str = "medical-records") -> bytes:
        """Reads and returns file bytes."""
        pass

    @abstractmethod
    async def delete_file(self, storage_key: str, subfolder: str = "medical-records") -> bool:
        """Deletes file from storage."""
        pass

    @abstractmethod
    async def file_exists(self, storage_key: str, subfolder: str = "medical-records") -> bool:
        """Checks if file exists in storage."""
        pass


class LocalStorageService(BaseStorageService):
    """Local filesystem storage implementation for development environment."""

    def __init__(self, base_root: Optional[str] = None):
        self.base_root = Path(base_root or settings.UPLOAD_ROOT).resolve()
        self.base_root.mkdir(parents=True, exist_ok=True)

    def _resolve_safe_path(self, storage_key: str, subfolder: str = "medical-records") -> Path:
        """Resolves path and enforces strict path traversal protection."""
        if not storage_key:
            raise AppValidationError("Storage key cannot be empty.")

        # Reject null bytes and control characters
        if "\x00" in storage_key or "\r" in storage_key or "\n" in storage_key:
            raise AppValidationError("Illegal characters detected in storage key.")

        # Explicitly reject directory traversal sequences
        if ".." in storage_key or ".." in subfolder:
            raise AppValidationError("Illegal path traversal attempt detected in storage key.")

        # Reject absolute paths or drive letters
        if storage_key.startswith("/") or storage_key.startswith("\\") or (len(storage_key) > 1 and storage_key[1] == ":"):
            raise AppValidationError("Absolute path not permitted in storage key.")

        # Normalize slashes and extract base file name
        normalized_key = storage_key.replace("\\", "/")
        clean_key = os.path.basename(normalized_key)
        clean_subfolder = os.path.basename(subfolder.replace("\\", "/"))

        if not clean_key or clean_key in (".", ".."):
            raise AppValidationError("Illegal or empty storage key.")

        target_dir = (self.base_root / clean_subfolder).resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        target_path = (target_dir / clean_key).resolve()

        # Strict boundary check against path traversal
        if not str(target_path).startswith(str(self.base_root)):
            raise AppValidationError("Illegal path traversal attempt detected in storage key.")

        return target_path

    async def save_file(self, content_bytes: bytes, storage_key: str, subfolder: str = "medical-records") -> str:
        """Saves bytes to local disk safely."""
        path = self._resolve_safe_path(storage_key, subfolder)
        try:
            with open(path, "wb") as f:
                f.write(content_bytes)
            logger.info(f"Saved file to storage path: {path}")
            return storage_key
        except Exception as exc:
            logger.error(f"Failed to write file to disk {path}: {exc}")
            raise AppValidationError(f"Storage write error: {str(exc)}")

    async def read_file(self, storage_key: str, subfolder: str = "medical-records") -> bytes:
        """Reads file bytes from local disk."""
        path = self._resolve_safe_path(storage_key, subfolder)
        if not path.exists() or not path.is_file():
            raise ResourceNotFoundError("File in storage", storage_key)

        try:
            with open(path, "rb") as f:
                return f.read()
        except Exception as exc:
            logger.error(f"Error reading file from disk {path}: {exc}")
            raise ResourceNotFoundError("File in storage", storage_key)

    async def delete_file(self, storage_key: str, subfolder: str = "medical-records") -> bool:
        """Deletes file from local disk."""
        path = self._resolve_safe_path(storage_key, subfolder)
        if path.exists() and path.is_file():
            try:
                os.remove(path)
                logger.info(f"Deleted file from storage path: {path}")
                return True
            except Exception as exc:
                logger.warning(f"Error deleting file {path}: {exc}")
                return False
        return False

    async def file_exists(self, storage_key: str, subfolder: str = "medical-records") -> bool:
        """Checks if file exists on disk."""
        path = self._resolve_safe_path(storage_key, subfolder)
        return path.exists() and path.is_file()


# Singleton instance selector based on STORAGE_PROVIDER
def get_storage_service() -> BaseStorageService:
    """Factory returning active storage provider implementation."""
    provider = settings.STORAGE_PROVIDER.lower()
    if provider in {"object", "s3", "cloud"}:
        from app.services.object_storage import ObjectStorageService
        return ObjectStorageService()
    return LocalStorageService()


storage_service = get_storage_service()

