from apps.common.tests.base import BaseAPITestCase


class HealthCheckTests(BaseAPITestCase):
    def test_health_returns_ok_when_db_ready(self):
        response = self.client.get("/api/v1/health/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "ok")
        self.assertEqual(data["service"], "sante-ecoute")
        self.assertTrue(data["migrations_applied"])
        self.assertTrue(data["ready"])
