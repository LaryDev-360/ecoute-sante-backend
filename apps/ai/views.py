from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView

from apps.ai.serializers import (
    ClassifyRequestSerializer,
    ClassifyResponseSerializer,
    GbegbeRequestSerializer,
    GbegbeResponseSerializer,
)
from apps.ai.services.classifier import ClassificationError, classify_description
from apps.ai.services.mediateur import GbegbeError, mediate_audio
from apps.ai.services.mistral import MistralError
from apps.ai.services.openrouter import OpenRouterError
from apps.common.schema import COMMON_ERRORS, ERROR_503, ERROR_504


class AIClassifyThrottle(AnonRateThrottle):
    scope = "ai_classify"


class ClassifyView(APIView):
    """
    Assistance à la qualification lors de la soumission publique.
    Le résultat n'est jamais enregistré automatiquement sur une plainte.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AIClassifyThrottle]

    @extend_schema(
        tags=["AI"],
        summary="Classifier une description (indicatif)",
        description=(
            "Appelle un modèle gratuit via OpenRouter pour suggérer une catégorie "
            "et une priorité. **Résultat indicatif uniquement** — le frontend doit "
            "laisser l'utilisateur confirmer ou modifier avant soumission."
        ),
        request=ClassifyRequestSerializer,
        responses={
            200: ClassifyResponseSerializer,
            400: COMMON_ERRORS[400],
            503: ERROR_503,
            504: ERROR_504,
        },
        examples=[
            OpenApiExample(
                "Description d'attente",
                value={
                    "description": (
                        "J'ai attendu plus de 4 heures aux urgences sans aucune "
                        "information du personnel."
                    ),
                },
                request_only=True,
            ),
            OpenApiExample(
                "Suggestion",
                value={
                    "category": "Temps d'attente",
                    "priority": "HIGH",
                    "disclaimer": (
                        "Suggestion indicative générée par IA — à valider par le "
                        "déclarant avant soumission."
                    ),
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = ClassifyRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = classify_description(serializer.validated_data["description"])
        except ClassificationError as exc:
            return Response(
                {"success": False, "error": {"detail": exc.message, "code": exc.code}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except OpenRouterError as exc:
            return Response(
                {"success": False, "error": {"detail": exc.message, "code": exc.code}},
                status=exc.status_code,
            )

        return Response(result)


class GbegbeView(APIView):
    """
    Médiateur vocal Gbègbe : reçoit un audio (fon, yoruba ou français), le confie
    au modèle Voxtral de Mistral et renvoie un signalement structuré.
    Résultat indicatif — jamais enregistré automatiquement sur une plainte.
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AIClassifyThrottle]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        tags=["AI"],
        summary="Médiation vocale (Gbègbe)",
        description=(
            "Transcrit et structure un message vocal de patient. Accepte un fichier "
            "audio (`multipart/form-data`, champ `audio`) ou un audio encodé en base64 "
            "(`application/json`, champ `audio_base64`). Formats : ogg, mp3, wav, webm."
        ),
        request=GbegbeRequestSerializer,
        responses={
            200: GbegbeResponseSerializer,
            400: COMMON_ERRORS[400],
            503: ERROR_503,
            504: ERROR_504,
        },
        examples=[
            OpenApiExample(
                "Audio base64 (JSON)",
                value={"audio_base64": "<base64>", "format": "ogg"},
                request_only=True,
            ),
            OpenApiExample(
                "Signalement structuré",
                value={
                    "langue_detectee": "fon",
                    "transcription_fr": "J'ai attendu trois heures aux urgences sans être reçu.",
                    "type": "plainte",
                    "service": "urgences",
                    "gravite": "urgent",
                    "resume": "Patient non pris en charge après une longue attente aux urgences.",
                },
                response_only=True,
            ),
        ],
    )
    def post(self, request):
        serializer = GbegbeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            result = mediate_audio(
                serializer.validated_data["audio_base64"],
                serializer.validated_data["format"],
            )
        except GbegbeError as exc:
            return Response(
                {"success": False, "error": {"detail": exc.message, "code": exc.code}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except MistralError as exc:
            return Response(
                {"success": False, "error": {"detail": exc.message, "code": exc.code}},
                status=exc.status_code,
            )

        return Response(result)
