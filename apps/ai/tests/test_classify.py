from unittest.mock import patch

from django.test import override_settings

from apps.common.tests.base import BaseAPITestCase


@override_settings(
    OPENROUTER_API_KEY="test-key",
    OPENROUTER_MODEL="openrouter/free",
    OPENROUTER_TIMEOUT=5,
)
class AIClassifyAPITests(BaseAPITestCase):
    def test_classify_returns_suggestion(self):
        mock_response = '{"category": "Temps d\'attente", "priority": "HIGH"}'
        with patch(
            "apps.ai.services.classifier.chat_completion",
            return_value=mock_response,
        ):
            response = self.client.post(
                "/api/v1/ai/classify/",
                {"description": "Attente de 4 heures aux urgences sans information."},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["category"], "Temps d'attente")
        self.assertEqual(data["priority"], "HIGH")
        self.assertIn("disclaimer", data)

    def test_classify_short_description_returns_400(self):
        response = self.client.post(
            "/api/v1/ai/classify/",
            {"description": "court"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_classify_openrouter_failure_returns_503(self):
        from apps.ai.services.openrouter import OpenRouterError

        with patch(
            "apps.ai.services.classifier.chat_completion",
            side_effect=OpenRouterError("Service indisponible", status_code=503),
        ):
            response = self.client.post(
                "/api/v1/ai/classify/",
                {"description": "Personnel très impoli à l'accueil ce matin."},
                format="json",
            )

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["success"])

    def test_classify_missing_api_key_returns_503(self):
        with self.settings(OPENROUTER_API_KEY=""):
            response = self.client.post(
                "/api/v1/ai/classify/",
                {"description": "Rupture de médicaments à la pharmacie depuis une semaine."},
                format="json",
            )

        self.assertEqual(response.status_code, 503)

    def test_classify_parses_markdown_json_response(self):
        mock_response = '```json\n{"category": "Hygiène", "priority": "MEDIUM"}\n```'
        with patch(
            "apps.ai.services.classifier.chat_completion",
            return_value=mock_response,
        ):
            response = self.client.post(
                "/api/v1/ai/classify/",
                {"description": "Les toilettes publiques sont très sales et sans savon."},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "Hygiène")
        self.assertEqual(response.json()["priority"], "MEDIUM")

    def test_classify_normalizes_unknown_category_to_autre(self):
        mock_response = '{"category": "Problème inconnu", "priority": "LOW"}'
        with patch(
            "apps.ai.services.classifier.chat_completion",
            return_value=mock_response,
        ):
            response = self.client.post(
                "/api/v1/ai/classify/",
                {"description": "Situation atypique difficile à qualifier précisément."},
                format="json",
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["category"], "Autre")
