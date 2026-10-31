"""Centralized Application Configuration using Pydantic Settings."""

import os
from pathlib import Path
from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings management for CliniXAI backend.
    
    Supports loading from environment variables and local .env file.
    """

    APP_NAME: str = "CliniXAI API"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Database Settings
    MONGODB_URI: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "clinixai"

    # Security & CORS Settings
    CORS_ORIGINS: Union[List[str], str] = [
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8081",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:3100",
        "http://127.0.0.1:3100",
        "http://localhost:3101",
        "http://127.0.0.1:3101",
        "https://clini-xai.vercel.app",
    ]

    # Logging Settings
    LOG_LEVEL: str = "INFO"

    # JWT Authentication Settings
    JWT_SECRET_KEY: str = "clinixai_dev_jwt_secret_key_2026_change_in_production_replace_me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24
    RESET_TOKEN_EXPIRE_HOURS: int = 1

    # Google OAuth & Calendar Settings (Phase 9)
    GOOGLE_AUTH_ENABLED: bool = True
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = "http://localhost:8000/api/v1/auth/google/callback"
    FRONTEND_URL: str = "http://localhost:3100"
    GOOGLE_CALENDAR_ENABLED: bool = False
    GOOGLE_CALENDAR_REDIRECT_URI: Optional[str] = "http://localhost:5173/calendar/callback"

    # Email Service Settings (Phase 9 SMTP / Transactional Email)
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM_EMAIL: str = "noreply@clinixai.com"
    SMTP_FROM_NAME: str = "CliniXAI Healthcare"
    SMTP_USE_TLS: bool = True

    # Storage & File Upload Settings (Phase 5 & 9 Production Object Storage)
    STORAGE_PROVIDER: str = "local"  # "local" or "object" / "s3"
    STORAGE_BUCKET_NAME: Optional[str] = None
    STORAGE_ENDPOINT_URL: Optional[str] = None
    STORAGE_ACCESS_KEY: Optional[str] = None
    STORAGE_SECRET_KEY: Optional[str] = None
    STORAGE_REGION: str = "us-east-1"
    UPLOAD_ROOT: str = "uploads"
    MAX_UPLOAD_SIZE_MB: int = 10
    ALLOWED_IMAGE_TYPES: List[str] = ["image/jpeg", "image/png"]
    ALLOWED_DOCUMENT_TYPES: List[str] = ["application/pdf"]

    # Hospital Location & Maps Settings (Phase 9 Free-First Directions)
    HOSPITAL_NAME: str = "CliniXAI Multi-Specialty Hospital & Research Center"
    HOSPITAL_ADDRESS: str = "100 Healthcare Boulevard, Medical District, Tech City"
    HOSPITAL_DIRECTIONS_URL: str = "https://maps.google.com/?q=100+Healthcare+Boulevard+Medical+District"

    # Security & Rate Limiting (Phase 9)
    RATE_LIMIT_LOGIN_PER_MINUTE: int = 100
    RATE_LIMIT_GENERAL_PER_MINUTE: int = 1000

    # AI Subsystem Configuration (Phase 8)
    AI_ENABLED: bool = True
    AI_MODEL_PATH: str = "ai_models/model.keras"
    AI_METADATA_PATH: str = "ai_models/model_metadata.json"
    AI_CLASS_MAP_PATH: str = "ai_models/class_names.json"
    AI_GRADCAM_LAYER: str = "conv5_block3_out"

    model_config = SettingsConfigDict(
        env_file=(
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            ".env",
            "backend/.env",
        ),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        """Parses comma-separated strings or JSON arrays into a list of allowed CORS origin URLs."""
        parsed: List[str] = []
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                import json
                try:
                    parsed = json.loads(v)
                except Exception:
                    parsed = []
            if not parsed:
                parsed = [item.strip() for item in v.split(",") if item.strip()]
        elif isinstance(v, list):
            parsed = list(v)
        else:
            parsed = [
                "http://localhost:8080",
                "http://localhost:5173",
                "http://localhost:3000",
                "http://localhost:3100",
                "http://127.0.0.1:3100",
                "https://clini-xai.vercel.app",
            ]

        # Always ensure canonical production frontend is allowed
        canonical_prod = "https://clini-xai.vercel.app"
        if canonical_prod not in parsed and "*" not in parsed:
            parsed.append(canonical_prod)

        return parsed

    @property
    def is_production(self) -> bool:
        """Returns True if the application is running in production mode."""
        return self.ENVIRONMENT.lower() == "production"

    @property
    def max_upload_size_bytes(self) -> int:
        """Returns maximum upload size in bytes."""
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    def validate_production_security(self) -> None:
        """Enforces mandatory security constraints for production deployments."""
        if not self.is_production:
            return

        # 1. Reject default development JWT secret key
        if self.JWT_SECRET_KEY == "clinixai_dev_jwt_secret_key_2026_change_in_production_replace_me" or "replace_me" in self.JWT_SECRET_KEY:
            raise RuntimeError("CRITICAL SECURITY ERROR: Production deployment cannot use the default development JWT secret key.")

        # 2. Reject wildcard CORS origins
        origins = self.CORS_ORIGINS if isinstance(self.CORS_ORIGINS, list) else [self.CORS_ORIGINS]
        if "*" in origins:
            raise RuntimeError("CRITICAL SECURITY ERROR: Production deployment cannot use wildcard '*' in CORS_ORIGINS with credentials.")


settings = Settings()

if settings.is_production:
    if settings.DEBUG:
        logger_warn_msg = "PRODUCTION WARNING: DEBUG is True in production mode. Disabling DEBUG mode."
        import logging
        logging.getLogger("clinixai").warning(logger_warn_msg)
        settings.DEBUG = False
    settings.validate_production_security()


