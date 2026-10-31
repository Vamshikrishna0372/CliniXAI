"""Health, Liveness, and Readiness check endpoints for CliniXAI backend."""

from fastapi import APIRouter, status, Response
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.database.mongodb import ping_database
from app.schemas.health import HealthResponse, LivenessResponse, ReadinessResponse

router = APIRouter(prefix="/health", tags=["Health & Diagnostics"])


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Comprehensive Health Check",
    description="Returns current status of the API, database connection status, and version info.",
)
async def health_check() -> HealthResponse:
    """Returns general health status of the application and database connection state."""
    db_ok = await ping_database()
    db_status = "connected" if db_ok else "disconnected"
    
    return HealthResponse(
        status="healthy",
        database=db_status,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
    )


@router.get(
    "/live",
    response_model=LivenessResponse,
    status_code=status.HTTP_200_OK,
    summary="Process Liveness Check",
    description="Lightweight liveness check confirming the FastAPI process is active.",
)
async def liveness_check() -> LivenessResponse:
    """Returns process liveness indicator."""
    return LivenessResponse(status="healthy")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Dependency Readiness Check",
    description="Checks whether critical downstream dependencies (such as MongoDB) are reachable.",
    responses={
        200: {"model": ReadinessResponse, "description": "System ready"},
        503: {"description": "Database dependency unavailable"},
    },
)
async def readiness_check() -> Response:
    """Checks database dependency readiness. Returns HTTP 503 if MongoDB is unreachable."""
    db_ok = await ping_database()
    if db_ok:
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={"status": "ready", "database": "connected"},
        )
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"status": "not_ready", "database": "disconnected"},
    )
