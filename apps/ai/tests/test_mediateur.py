import base64
import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.common.tests.base import BaseAPITestCase

URL = "/api/v1/ai/mediateur/"

VALID_MODEL_RESPONSE = json.dumps(
    {
        "langue_detectee": "fon",
        "transcription_fr": "J'ai attendu trois heures aux urgences sans être reçu.",
        "type": "plainte",
        "service": "urgences",
        "gravite": "urgent",
        "resume": "Patient non pris en charge après une longue attente.",
    }
)


@override_settings(
    MISTRAL_API_KEY="test-key",
    MISTRAL_MODEL="voxtral-small-latest",
    MISTRAL_TIMEOUT=5,
)
class GbegbeAPITests(BaseAPITestCase):
    def test_mediateur_base64_returns_structured_signalement(self):
        payload = {
            "audio_base64": base64.b64encode(b"fake-audio").decode("ascii"),
            "format": "ogg",
        }
        with patch(
            "apps.ai.services.mediateur.audio_chat_completion",
            return_value=VALID_MODEL_RESPONSE,
        ):
            response = self.client.post(URL, payload, format="json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["langue_detectee"], "fon")
        self.assertEqual(data["type"], "plainte")
        self.assertEqual(data["service"], "urgences")

    def test_mediateur_multipart_file_upload(self):
        audio = SimpleUploadedFile("voix.mp3", b"fake-audio", content_type="audio/mpeg")
        with patch(
            "apps.ai.services.mediateur.audio_chat_completion",
            return_value=VALID_MODEL_RESPONSE,
        ):
            response = self.client.post(URL, {"audio": audio}, format="multipart")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["gravite"], "urgent")

    def test_mediateur_parses_markdown_wrapped_json(self):
        payload = {"audio_base64": base64.b64encode(b"x").decode("ascii"), "format": "wav"}
        wrapped = f"```json\n{VALID_MODEL_RESPONSE}\n```"
        with patch(
            "apps.ai.services.mediateur.audio_chat_completion",
            return_value=wrapped,
        ):
            response = self.client.post(URL, payload, format="json")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "urgences")

    def test_mediateur_missing_audio_returns_400(self):
        response = self.client.post(URL, {"format": "ogg"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_mediateur_invalid_base64_returns_400(self):
        response = self.client.post(
            URL, {"audio_base64": "not-base64!!", "format": "ogg"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_mediateur_unsupported_format_returns_400(self):
        payload = {"audio_base64": base64.b64encode(b"x").decode("ascii"), "format": "flac"}
        response = self.client.post(URL, payload, format="json")
        self.assertEqual(response.status_code, 400)

    def test_mediateur_missing_api_key_returns_503(self):
        payload = {"audio_base64": base64.b64encode(b"x").decode("ascii"), "format": "ogg"}
        with self.settings(MISTRAL_API_KEY=""):
            response = self.client.post(URL, payload, format="json")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["success"])

    def test_mediateur_mistral_failure_returns_502(self):
        from apps.ai.services.mistral import MistralError

        payload = {"audio_base64": base64.b64encode(b"x").decode("ascii"), "format": "ogg"}
        with patch(
            "apps.ai.services.mediateur.audio_chat_completion",
            side_effect=MistralError("Erreur Mistral", status_code=502),
        ):
            response = self.client.post(URL, payload, format="json")

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()["success"])

    def test_mediateur_incomplete_model_response_returns_400(self):
        incomplete = json.dumps({"langue_detectee": "fr", "transcription_fr": "Bonjour."})
        payload = {"audio_base64": base64.b64encode(b"x").decode("ascii"), "format": "ogg"}
        with patch(
            "apps.ai.services.mediateur.audio_chat_completion",
            return_value=incomplete,
        ):
            response = self.client.post(URL, payload, format="json")

        self.assertEqual(response.status_code, 400)
