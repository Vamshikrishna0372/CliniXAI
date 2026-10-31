"""Custom Application Exceptions and Centralized FastAPI Exception Handlers."""

from typing import Any, Optional, Dict
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError

from app.core.logging import logger
from app.core.config import settings


class CliniXAIException(Exception):
    """Base application exception for CliniXAI."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Any] = None,
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details
        super().__init__(self.message)


class ResourceNotFoundError(CliniXAIException):
    """Exception raised when a requested resource is not found."""

    def __init__(self, resource_name: str = "Resource", identifier: Optional[Any] = None):
        msg = f"{resource_name} not found." if identifier is None else f"{resource_name} with identifier '{identifier}' not found."
        super().__init__(
            message=msg,
            code="RESOURCE_NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        )


NotFoundError = ResourceNotFoundError


class ResourceConflictError(CliniXAIException):
    """Exception raised when a resource conflict occurs (e.g. duplicate key)."""

    def __init__(self, message: str = "A resource conflict occurred."):
        super().__init__(
            message=message,
            code="RESOURCE_CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
        )


class DatabaseUnavailableError(CliniXAIException):
    """Exception raised when database connection fails or times out."""

    def __init__(self, message: str = "Database service is currently unavailable."):
        super().__init__(
            message=message,
            code="DATABASE_UNAVAILABLE",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class UnauthorizedError(CliniXAIException):
    """Exception raised when authentication fails."""

    def __init__(self, message: str = "Authentication required."):
        super().__init__(
            message=message,
            code="UNAUTHORIZED",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class ForbiddenError(CliniXAIException):
    """Exception raised when access is denied due to insufficient permissions."""

    def __init__(self, message: str = "Access forbidden."):
        super().__init__(
            message=message,
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )


class AppValidationError(CliniXAIException):
    """Exception raised for business logic validation failures."""

    def __init__(self, message: str, details: Optional[Any] = None):
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


def _add_cors_headers(request: Request, response: JSONResponse) -> JSONResponse:
    """Ensures CORS headers are attached to exception responses."""
    origin = request.headers.get("origin")
    if origin:
        allowed = settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS]
        if "*" in allowed or origin in allowed or "http://localhost:8080" in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type, Accept, Origin, User-Agent, X-Requested-With"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    return response


from pymongo.errors import PyMongoError


def register_exception_handlers(app: FastAPI) -> None:
    """Registers exception handlers onto the FastAPI application instance."""

    @app.exception_handler(CliniXAIException)
    async def clinixai_exception_handler(request: Request, exc: CliniXAIException) -> JSONResponse:
        method = getattr(request, "method", "WEBSOCKET")
        path = getattr(request, "url", None)
        path_str = path.path if path else "unknown"
        logger.warning(
            f"CliniXAIException [{exc.code}] on {method} {path_str}: {exc.message}"
        )
        content: Dict[str, Any] = {
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
            },
        }
        if exc.details is not None:
            content["error"]["details"] = exc.details
        resp = JSONResponse(status_code=exc.status_code, content=content)
        return _add_cors_headers(request, resp)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        method = getattr(request, "method", "WEBSOCKET")
        path = getattr(request, "url", None)
        path_str = path.path if path else "unknown"
        logger.warning(f"Request validation error on {method} {path_str}")
        from fastapi.encoders import jsonable_encoder
        resp = JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters or payload.",
                    "details": jsonable_encoder(exc.errors()),
                },
            },
        )
        return _add_cors_headers(request, resp)

    from pydantic import ValidationError as PydanticValidationError

    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_exception_handler(request: Request, exc: PydanticValidationError) -> JSONResponse:
        logger.warning(f"Pydantic validation error on {request.method} {request.url.path}: {exc.errors()}")
        from fastapi.encoders import jsonable_encoder
        try:
            details = jsonable_encoder(exc.errors())
        except Exception:
            details = [str(err) for err in exc.errors()]
        resp = JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters or payload.",
                    "details": details,
                },
            },
        )
        return _add_cors_headers(request, resp)

    @app.exception_handler(PyMongoError)
    async def pymongo_exception_handler(request: Request, exc: PyMongoError) -> JSONResponse:
        logger.error(f"Database error on {request.method} {request.url.path}: {exc}")
        resp = JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "success": False,
                "error": {
                    "code": "DATABASE_UNAVAILABLE",
                    "message": "Database service is currently unavailable. Please try again later.",
                },
            },
        )
        return _add_cors_headers(request, resp)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error(
            f"Unhandled server error on {request.method} {request.url.path}: {str(exc)}",
            exc_info=True,
        )
        # Avoid leaking internal filesystem or stack trace info to client
        message = "An unexpected error occurred. Please try again later."
        details = str(exc) if settings.DEBUG else None

        content: Dict[str, Any] = {
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": message,
            },
        }
        if details:
            content["error"]["details"] = details
        resp = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=content,
        )
        return _add_cors_headers(request, resp)

