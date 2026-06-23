from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from apps.complaints.serializers import UssdRequestSerializer
from apps.complaints.ussd import handle_ussd


class UssdView(APIView):
    """
    Webhook USSD pour Africa's Talking.

    La passerelle envoie en `application/x-www-form-urlencoded` :
    `sessionId`, `phoneNumber`, `serviceCode`, `text`.
    La réponse est du texte brut commençant par « CON » (continuer) ou
    « END » (terminer).
    """

    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [FormParser, MultiPartParser, JSONParser]

    @extend_schema(
        tags=["USSD"],
        summary="Webhook USSD (dépôt et suivi de plainte)",
        description=(
            "Endpoint appelé par Africa's Talking à chaque saisie du patient. "
            "Renvoie le menu à afficher : préfixe « CON » pour continuer la "
            "session, « END » pour la terminer. Au démarrage, `text` est vide."
        ),
        request=UssdRequestSerializer,
        responses={
            200: OpenApiResponse(
                response=OpenApiTypes.STR,
                description="Texte du menu (« CON ... » ou « END ... »).",
            )
        },
        examples=[
            OpenApiExample(
                "Démarrage (accueil)",
                value={"sessionId": "ATUid_1", "phoneNumber": "+22997000000", "text": ""},
                request_only=True,
            ),
            OpenApiExample(
                "Choix « Enregistrer une plainte »",
                value={"sessionId": "ATUid_1", "phoneNumber": "+22997000000", "text": "1"},
                request_only=True,
            ),
        ],
    )
    def post(self, request):
        session_id = request.data.get("sessionId", "")
        phone_number = request.data.get("phoneNumber", "")
        text = request.data.get("text", "")

        reply = handle_ussd(session_id, phone_number, text)
        return HttpResponse(reply, content_type="text/plain; charset=utf-8")
