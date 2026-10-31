"""HTTP Request execution logging and performance measurement middleware."""

import time
from typing import Callable, Awaitable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import logger


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for measuring HTTP request execution duration and logging method, path, and status code."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        start_time = time.perf_counter()
        
        try:
            response = await call_next(request)
        except Exception:
            raise
        
        process_time_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"HTTP {request.method} {request.url.path} -> {response.status_code} "
            f"[{process_time_ms:.2f}ms]"
        )
        
        # Set timing header on response
        response.headers["X-Process-Time-Ms"] = f"{process_time_ms:.2f}"
        
        return response
