from apps.common.tests.base import BaseAPITestCase


class HealthCheckTests(BaseAPITestCase):
    def test_health_returns_ok_without_auth(self):
        response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok", "service": "sante-ecoute"})
