"""Unit tests for Health, Liveness, and Readiness endpoints."""

import unittest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport
from app.main import app


class TestHealthEndpoints(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_liveness_endpoint(self) -> None:
        """Verifies that GET /api/v1/health/live returns 200 OK and healthy status."""
        response = await self.client.get("/api/v1/health/live")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")

    async def test_health_endpoint_db_connected(self) -> None:
        """Verifies GET /api/v1/health when database ping succeeds."""
        with patch("app.api.v1.routes.health.ping_database", return_value=True):
            response = await self.client.get("/api/v1/health")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["database"], "connected")
            self.assertEqual(data["version"], "1.0.0")

    async def test_health_endpoint_db_disconnected(self) -> None:
        """Verifies GET /api/v1/health when database ping fails."""
        with patch("app.api.v1.routes.health.ping_database", return_value=False):
            response = await self.client.get("/api/v1/health")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "healthy")
            self.assertEqual(data["database"], "disconnected")

    async def test_readiness_endpoint_success(self) -> None:
        """Verifies GET /api/v1/health/ready returns 200 OK when database is connected."""
        with patch("app.api.v1.routes.health.ping_database", return_value=True):
            response = await self.client.get("/api/v1/health/ready")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["status"], "ready")
            self.assertEqual(data["database"], "connected")

    async def test_readiness_endpoint_failure(self) -> None:
        """Verifies GET /api/v1/health/ready returns 503 Service Unavailable when database ping fails."""
        with patch("app.api.v1.routes.health.ping_database", return_value=False):
            response = await self.client.get("/api/v1/health/ready")
            self.assertEqual(response.status_code, 503)
            data = response.json()
            self.assertEqual(data["status"], "not_ready")
            self.assertEqual(data["database"], "disconnected")
