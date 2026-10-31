"""Master Async Unit Test Suite for CliniXAI backend using Python's standard unittest."""

import unittest
from unittest.mock import patch
from httpx import AsyncClient, ASGITransport

from app.main import app
from tests.test_auth import TestAuthEndpoints
from tests.test_rbac import TestRBACDependencies
from tests.test_password_reset import TestPasswordResetFlows
from tests.test_email_verification import TestEmailVerification
from tests.test_phase3 import TestPhase3Endpoints
from tests.test_phase4 import TestPhase4ClinicalEndpoints
from tests.test_phase5 import TestPhase5MedicalRecordEndpoints
from tests.test_phase6 import TestPhase6BillingAndNotifications
from tests.test_phase8 import TestPhase8AIIntegration
from tests.test_medical_records_phase8 import TestMedicalRecordsPhase8


class TestCliniXAIBackendRootAndHealth(unittest.IsolatedAsyncioTestCase):
    """Async test suite for Root and Health endpoints."""

    async def asyncSetUp(self) -> None:
        transport = ASGITransport(app=app)
        self.client = AsyncClient(transport=transport, base_url="http://testserver")

    async def asyncTearDown(self) -> None:
        await self.client.aclose()

    async def test_root_endpoint(self) -> None:
        response = await self.client.get("/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["application"], "CliniXAI API")
        self.assertEqual(data["version"], "1.0.0")
        self.assertEqual(data["status"], "running")

    async def test_liveness_endpoint(self) -> None:
        response = await self.client.get("/api/v1/health/live")
        self.assertEqual(response.status_code, 200)

    async def test_health_endpoint_db_connected(self) -> None:
        with patch("app.api.v1.routes.health.ping_database", return_value=True):
            response = await self.client.get("/api/v1/health")
            self.assertEqual(response.status_code, 200)

    async def test_readiness_endpoint_success(self) -> None:
        with patch("app.api.v1.routes.health.ping_database", return_value=True):
            response = await self.client.get("/api/v1/health/ready")
            self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
