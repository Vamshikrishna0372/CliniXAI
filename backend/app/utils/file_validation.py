"""File validation utilities for CliniXAI Phase 5.

Provides size, extension, MIME type, SHA-256 checksum, magic byte inspection,
and path-traversal safety checks.
"""

import hashlib
import os
import secrets
from typing import Tuple, Optional
from pydantic import BaseModel

from app.core.config import settings
from app.core.exceptions import AppValidationError

# Dangerous executable / script extensions strictly forbidden
FORBIDDEN_EXTENSIONS = {
    ".exe", ".bat", ".cmd", ".sh", ".js", ".html", ".htm", ".php", ".py",
    ".vbs", ".ps1", ".jar", ".dll", ".so", ".app", ".scr", ".pif", ".svg"
}

# Standard magic bytes for file format validation
MAGIC_BYTES = {
    "jpeg": [b"\xff\xd8\xff"],
    "png": [b"\x89PNG\r\n\x1a\n"],
    "pdf": [b"%PDF"],
    "webp": [b"RIFF"],
}

# Supported mime to extension mappings
MIME_TO_EXTENSIONS = {
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
    "image/webp": {".webp"},
    "application/pdf": {".pdf"},
    "application/dicom": {".dcm", ".dicom"},
    "image/dicom": {".dcm", ".dicom"},
}


class FileValidationResult(BaseModel):
    """Result container for file validation."""
    filename: str
    extension: str
    content_type: str
    size_bytes: int
    checksum: str
    is_image: bool


def calculate_sha256_checksum(content_bytes: bytes) -> str:
    """Calculates SHA-256 checksum hex string for content bytes."""
    return hashlib.sha256(content_bytes).hexdigest()


def sanitize_original_filename(filename: str) -> str:
    """Sanitizes an untrusted filename to prevent path traversal, null bytes, and control characters."""
    if not filename:
        return "unnamed_file"

    # Replace backslashes with slashes and take basename
    clean = os.path.basename(filename.replace("\\", "/"))
    # Remove null bytes and carriage return / line feeds
    clean = clean.replace("\x00", "").replace("\r", "").replace("\n", "").strip()
    # Remove any lingering path traversal patterns
    while "../" in clean or "..\\" in clean:
        clean = clean.replace("../", "").replace("..\\", "")
    if not clean or clean in (".", ".."):
        return "unnamed_file"
    return clean


def generate_secure_storage_key(original_filename: str) -> Tuple[str, str]:
    """Generates a secure, un-guessable storage key filename preserving extension.

    Example: 'lab_report.pdf' -> ('A7F39E1B2C4D8E9A.pdf', '.pdf')
    """
    clean_name = sanitize_original_filename(original_filename)
    ext = os.path.splitext(clean_name)[1].lower()
    hex_name = secrets.token_hex(16).upper()
    storage_key = f"{hex_name}{ext}"
    return storage_key, ext


def validate_file_content(
    original_filename: str,
    content_type: str,
    content_bytes: bytes,
) -> FileValidationResult:
    """Validates file upload content against safety, size, extension, MIME, magic bytes, and image decode rules.

    Raises AppValidationError if invalid.
    """
    if not content_bytes or len(content_bytes) == 0:
        raise AppValidationError("Uploaded file is empty (0 bytes).")

    # 1. Size validation
    max_bytes = settings.max_upload_size_bytes
    size_bytes = len(content_bytes)
    if size_bytes > max_bytes:
        raise AppValidationError(
            f"File size ({size_bytes / (1024 * 1024):.2f} MB) exceeds maximum allowed limit of {settings.MAX_UPLOAD_SIZE_MB} MB."
        )

    # 2. Filename sanitization & extension validation
    clean_filename = sanitize_original_filename(original_filename)
    ext = os.path.splitext(clean_filename)[1].lower()

    if ext in FORBIDDEN_EXTENSIONS:
        raise AppValidationError(f"File type '{ext}' is forbidden for security reasons.")

    allowed_exts = {".pdf", ".jpg", ".jpeg", ".png", ".webp", ".dcm", ".dicom"}
    if ext not in allowed_exts:
        raise AppValidationError(f"File extension '{ext}' is not supported. Allowed: PDF, JPEG, PNG, WEBP, DICOM.")

    # 3. Content-Type check & extension compatibility
    mime = (content_type or "").lower().strip()
    allowed_mimes = set(
        settings.ALLOWED_IMAGE_TYPES +
        settings.ALLOWED_DOCUMENT_TYPES +
        ["image/webp", "application/dicom", "image/dicom", "application/octet-stream"]
    )

    if not mime or mime not in allowed_mimes:
        # Fallback MIME inference for standard extensions if octet-stream or missing
        if ext in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif ext == ".png":
            mime = "image/png"
        elif ext == ".webp":
            mime = "image/webp"
        elif ext == ".pdf":
            mime = "application/pdf"
        elif ext in (".dcm", ".dicom"):
            mime = "application/dicom"
        else:
            raise AppValidationError(f"Content-Type '{content_type}' is not supported.")

    # If MIME is a specific recognized type (not generic octet-stream), verify extension compatibility
    if mime in MIME_TO_EXTENSIONS and ext not in MIME_TO_EXTENSIONS[mime]:
        raise AppValidationError(
            f"Content-Type '{mime}' does not match file extension '{ext}'."
        )

    # If generic octet-stream was supplied, normalize to canonical MIME
    if mime == "application/octet-stream":
        if ext in (".jpg", ".jpeg"):
            mime = "image/jpeg"
        elif ext == ".png":
            mime = "image/png"
        elif ext == ".webp":
            mime = "image/webp"
        elif ext == ".pdf":
            mime = "application/pdf"
        elif ext in (".dcm", ".dicom"):
            mime = "application/dicom"

    is_image = mime.startswith("image/") or ext in (".jpg", ".jpeg", ".png", ".webp", ".dcm", ".dicom")

    # 4. Magic Bytes Inspection
    if ext == ".pdf" and not content_bytes.startswith(b"%PDF"):
        raise AppValidationError("File header does not match a valid PDF document.")
    elif ext in (".jpg", ".jpeg") and not content_bytes.startswith(b"\xff\xd8\xff"):
        raise AppValidationError("File header does not match a valid JPEG image.")
    elif ext == ".png" and not content_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise AppValidationError("File header does not match a valid PNG image.")
    elif ext == ".webp" and not (content_bytes.startswith(b"RIFF") and len(content_bytes) >= 12 and content_bytes[8:12] == b"WEBP"):
        raise AppValidationError("File header does not match a valid WEBP image.")
    elif ext in (".dcm", ".dicom") and len(content_bytes) >= 132:
        if content_bytes[128:132] != b"DICM" and not content_bytes.startswith(b"\x00"):
            raise AppValidationError("File header does not match a valid DICOM medical image.")

    # 5. Deep Image Validation with Pillow (corrupt image rejection, decompression bomb guard)
    if ext in (".jpg", ".jpeg", ".png", ".webp"):
        try:
            import io
            from PIL import Image

            # Decompression bomb defense: max pixels limit
            Image.MAX_IMAGE_PIXELS = 64_000_000

            with Image.open(io.BytesIO(content_bytes)) as img:
                img.verify()
                width, height = img.size
                if width > 8192 or height > 8192:
                    raise AppValidationError(
                        f"Image dimensions ({width}x{height}) exceed maximum allowed dimensions of 8192x8192 pixels."
                    )
        except AppValidationError:
            raise
        except Exception as exc:
            raise AppValidationError(f"Invalid or corrupted image content: {str(exc)}")

    checksum = calculate_sha256_checksum(content_bytes)

    return FileValidationResult(
        filename=clean_filename,
        extension=ext,
        content_type=mime,
        size_bytes=size_bytes,
        checksum=checksum,
        is_image=is_image,
    )
