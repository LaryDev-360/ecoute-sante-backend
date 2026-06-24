import base64
import json
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings

from apps.common.tests.base import BaseAPITestCase
from apps.complaints.models import ComplaintCategory
from apps.facilities.models import Facility, FacilityService, FacilityType

URL = "/api/v1/ai/mediateur/prefill/"

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
class GbegbePrefillAPITests(BaseAPITestCase):
    def setUp(self):
        self.facility = Facility.objects.create(
            name="HZ Cotonou",
            code="HZ-COT-01",
            facility_type=FacilityType.HOSPITAL,
            region="Littoral",
            city="Cotonou",
            address="Adresse test",
        )
        self.service = FacilityService.objects.create(
            facility=self.facility,
            name="Urgences",
            active=True,
        )
        self.category = ComplaintCategory.objects.create(
            name="Autre",
            description="Catégorie par défaut",
            active=True,
        )

    def test_prefill_resolves_facility_service_category(self):
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
        self.assertTrue(data["success"])
        self.assertFalse(data["needs_manual_review"])
        prefill = data["prefill"]
        self.assertEqual(prefill["submitter_profile"], "CITIZEN")
        self.assertEqual(prefill["submission_type"], "ANONYMOUS")
        self.assertEqual(prefill["complaint_type"], "COMPLAINT")
        self.assertEqual(prefill["nature_ui"], "plainte")
        self.assertEqual(prefill["facility"], self.facility.id)
        self.assertEqual(prefill["service"], self.service.id)
        self.assertEqual(prefill["category"], self.category.id)
        self.assertEqual(prefill["severity"], "URGENT")
        self.assertEqual(prefill["detected_language"], "fon")
        self.assertEqual(prefill["title"], "Patient non pris en charge après une longue attente.")
        self.assertEqual(
            prefill["description"],
            "J'ai attendu trois heures aux urgences sans être reçu.",
        )

    def test_prefill_multipart_upload(self):
        audio = SimpleUploadedFile("voix.mp3", b"fake-audio", content_type="audio/mpeg")
        with patch(
            "apps.ai.services.mediateur.audio_chat_completion",
            return_value=VALID_MODEL_RESPONSE,
        ):
            response = self.client.post(URL, {"audio": audio}, format="multipart")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["needs_manual_review"])

    def test_prefill_unknown_service_returns_manual_review(self):
        response_data = json.dumps(
            {
                "langue_detectee": "fr",
                "transcription_fr": "Problème à la maternité.",
                "type": "plainte",
                "service": "maternité inconnue",
                "gravite": "moyen",
                "resume": "Problème signalé à la maternité.",
            }
        )
        payload = {
            "audio_base64": base64.b64encode(b"fake-audio").decode("ascii"),
            "format": "ogg",
        }
        with patch(
            "apps.ai.services.mediateur.audio_chat_completion",
            return_value=response_data,
        ):
            response = self.client.post(URL, payload, format="json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])
        self.assertTrue(data["needs_manual_review"])
        self.assertIsNone(data["prefill"]["facility"])
        self.assertIsNone(data["prefill"]["service"])
        self.assertEqual(data["prefill"]["category"], self.category.id)
        self.assertEqual(data["prefill"]["severity"], "MEDIUM")

    def test_prefill_maps_suggestion_and_appreciation(self):
        response_data = json.dumps(
            {
                "langue_detectee": "fr",
                "transcription_fr": "Je propose d'ajouter des bancs dans la salle d'attente.",
                "type": "suggestion",
                "service": "urgences",
                "gravite": "faible",
                "resume": "Suggestion d'aménagement.",
            }
        )
        payload = {
            "audio_base64": base64.b64encode(b"fake-audio").decode("ascii"),
            "format": "ogg",
        }
        with patch(
            "apps.ai.services.mediateur.audio_chat_completion",
            return_value=response_data,
        ):
            response = self.client.post(URL, payload, format="json")

        self.assertEqual(response.status_code, 200)
        prefill = response.json()["prefill"]
        self.assertEqual(prefill["complaint_type"], "SUGGESTION")
        self.assertEqual(prefill["nature_ui"], "suggestion")
        self.assertEqual(prefill["severity"], "LOW")

    def test_prefill_no_resume_uses_description_fallback(self):
        response_data = json.dumps(
            {
                "langue_detectee": "fr",
                "transcription_fr": "J'ai attendu trois heures aux urgences sans être reçu.",
                "type": "plainte",
                "service": "urgences",
                "gravite": "urgent",
                "resume": "",
            }
        )
        payload = {
            "audio_base64": base64.b64encode(b"fake-audio").decode("ascii"),
            "format": "ogg",
        }
        with patch(
            "apps.ai.services.mediateur.audio_chat_completion",
            return_value=response_data,
        ):
            response = self.client.post(URL, payload, format="json")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        prefill = data["prefill"]
        self.assertTrue(prefill["title"].startswith("J'ai attendu"))
        # Fallback title is sufficient to avoid manual review when service/category resolve.
        self.assertFalse(data["needs_manual_review"])

    def test_prefill_missing_api_key_returns_503(self):
        payload = {
            "audio_base64": base64.b64encode(b"x").decode("ascii"),
            "format": "ogg",
        }
        with self.settings(MISTRAL_API_KEY=""):
            response = self.client.post(URL, payload, format="json")

        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.json()["success"])

    def test_prefill_missing_audio_returns_400(self):
        response = self.client.post(URL, {"format": "ogg"}, format="json")
        self.assertEqual(response.status_code, 400)
