"""
Middleware for Production Security Headers and Rate Limiting for CliniXAI Phase 9.
"""

import time
from collections import defaultdict
from typing import Dict, List
from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import settings
from app.core.logging import logger

# In-memory rate limiting cache (IP/User bucket -> timestamps)
_rate_limit_cache: Dict[str, List[float]] = defaultdict(list)


class ProductionSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds standard security & cache-control headers to responses."""

    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Standard Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Cache Control for API routes
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
            response.headers["Pragma"] = "no-cache"

        return response


class RateLimiterMiddleware(BaseHTTPMiddleware):
    """
    In-memory Rate Limiting Middleware for sensitive authentication, inference, and mutation endpoints.
    Enforces per-IP request frequency bounds.
    """

    SENSITIVE_PREFIXES = (
        "/api/v1/auth/login",
        "/api/v1/auth/register",
        "/api/v1/auth/forgot-password",
        "/api/v1/auth/reset-password",
        "/api/v1/auth/accept-invitation",
        "/api/v1/auth/google",
        "/api/v1/check-in/qr",
        "/api/v1/ai/infer",
        "/api/v1/documents",
    )

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Always bypass OPTIONS preflight requests for CORS
        if request.method == "OPTIONS":
            return await call_next(request)

        # Check if route matches sensitive prefixes or test rate limit header is present
        test_mode = bool(request.headers.get("X-Test-Rate-Limit"))
        is_sensitive = any(path.startswith(prefix) for prefix in self.SENSITIVE_PREFIXES)

        if is_sensitive or test_mode:
            client_ip = request.client.host if request.client else "127.0.0.1"
            forwarded_for = request.headers.get("X-Forwarded-For")
            if forwarded_for:
                client_ip = forwarded_for.split(",")[0].strip()

            # Skip localhost unless explicitly requested by test suite
            if not test_mode and (client_ip in ("127.0.0.1", "localhost", "::1") or settings.DEBUG):
                return await call_next(request)

            key = f"{client_ip}:{path}"
            now = time.time()

            # Clean timestamps older than 60 seconds
            timestamps = [t for t in _rate_limit_cache[key] if now - t < 60]
            _rate_limit_cache[key] = timestamps

            limit = 5 if test_mode else settings.RATE_LIMIT_LOGIN_PER_MINUTE
            if len(timestamps) >= limit:
                logger.warning(f"Rate limit exceeded for IP {client_ip} on path {path}")
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "success": False,
                        "error": {
                            "code": "RATE_LIMIT_EXCEEDED",
                            "message": "Too many requests. Please wait a minute before trying again.",
                        },
                    },
                    headers={"Retry-After": "60"},
                )

            _rate_limit_cache[key].append(now)

        return await call_next(request)

