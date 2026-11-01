"""CliniXAI API Main FastAPI Application Entrypoint."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.models import SecurityScheme, HTTPBearer

from app.core.config import settings
from app.core.logging import logger
from app.core.exceptions import register_exception_handlers
from app.database.mongodb import connect_to_mongo, close_mongo_connection, db_manager
from app.database.indexes import ensure_database_indexes
from app.api.v1.router import api_v1_router
from app.schemas.health import RootResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application startup and shutdown lifecycle events."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION} ({settings.ENVIRONMENT})...")
    # Initialize MongoDB connection pool
    await connect_to_mongo()
    if db_manager.db is not None:
        await ensure_database_indexes(db_manager.db)
        from app.database.db_seeder import seed_initial_data
        await seed_initial_data(db_manager.db)
        from app.core.websocket_manager import manager
        await manager.start_event_listener(db_manager.db)
    if settings.AI_ENABLED:
        async def _preload_ai_subsystem() -> None:
            try:
                import asyncio
                from app.ai.model_loader import get_model_loader
                loader = await asyncio.to_thread(get_model_loader)
                logger.info("AI Subsystem: Initialized ModelLoader successfully.")
            except Exception as ai_e:
                logger.warning("AI Subsystem model preload deferred: %s", ai_e)
        import asyncio
        asyncio.create_task(_preload_ai_subsystem())
    yield
    # Stop WebSocket event bus listener
    try:
        from app.core.websocket_manager import manager
        await manager.stop_event_listener()
    except Exception:
        pass
    # Shutdown MongoDB connection pool
    await close_mongo_connection()
    logger.info(f"Shutdown complete for {settings.APP_NAME}.")


from app.middleware.security_middleware import SecurityHeadersMiddleware
from app.middleware.rate_limit_middleware import RateLimiterMiddleware

# Instantiate FastAPI application
app = FastAPI(
    title="CliniXAI API",
    description="Backend API for the CliniXAI AI-Powered Hospital Management & Clinical Decision Support Platform",
    version=settings.APP_VERSION,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
    lifespan=lifespan,
)

# Register custom exception handlers
register_exception_handlers(app)

# Security Headers & Cache-Control Middleware
app.add_middleware(SecurityHeadersMiddleware)

# Rate Limiter Middleware
app.add_middleware(RateLimiterMiddleware)

# CORS Middleware (outermost)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_origin_regex=r"^https://([a-zA-Z0-9_-]+\.)*vercel\.app$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Include API v1 Router
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


@app.get(
    "/",
    response_model=RootResponse,
    status_code=status.HTTP_200_OK,
    summary="Root Endpoint",
    description="Returns application metadata, version, and status.",
    tags=["Root"],
)
async def root() -> RootResponse:
    """Root application endpoint providing status and documentation link."""
    return RootResponse(
        application=settings.APP_NAME,
        version=settings.APP_VERSION,
        status="running",
        environment=settings.ENVIRONMENT,
        docs_url="/docs",
    )
