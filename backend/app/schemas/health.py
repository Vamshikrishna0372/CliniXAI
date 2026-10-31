"""Pydantic schemas for health, liveness, and readiness endpoints."""

from typing import Optional
from pydantic import BaseModel, Field


class RootResponse(BaseModel):
    """Response schema for the root API endpoint."""
    application: str = Field(..., example="CliniXAI API")
    version: str = Field(..., example="1.0.0")
    status: str = Field(..., example="running")
    environment: str = Field(..., example="development")
    docs_url: Optional[str] = Field(None, example="/docs")


class LivenessResponse(BaseModel):
    """Response schema for the process liveness check endpoint."""
    status: str = Field("healthy", example="healthy")


class ReadinessResponse(BaseModel):
    """Response schema for the dependency readiness check endpoint."""
    status: str = Field(..., example="ready")
    database: str = Field(..., example="connected")


class HealthResponse(BaseModel):
    """Response schema for the detailed health status check endpoint."""
    status: str = Field("healthy", example="healthy")
    database: str = Field(..., example="connected")
    version: str = Field(..., example="1.0.0")
    environment: str = Field(..., example="development")
