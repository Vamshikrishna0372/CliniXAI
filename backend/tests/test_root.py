"""Unit tests for the Root API endpoint (GET /)."""

import unittest
from httpx import AsyncClient, ASGITransport
from app.main import app


class TestRootEndpoint(unittest.IsolatedAsyncioTestCase):

    async def asyncSetUp(self) -> None:
        self.transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=self.transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_root_endpoint(self) -> None:
        """Verifies that GET / returns 200 OK with correct application metadata."""
        response = await self.client.get("/")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["application"], "CliniXAI API")
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["status"], "running")
        self.assertIn("environment", data)
        self.assertEqual(data["docs_url"], "/docs")
