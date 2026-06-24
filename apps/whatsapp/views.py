import logging

from django.conf import settings
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.whatsapp.serializers import WhatsappWebhookSerializer
from apps.whatsapp.services import handle_incoming
from apps.whatsapp.tts import synthetiser_fr
from apps.whatsapp.utils import (
    GreenApiError,
    envoyer_fichier_url_whatsapp,
    envoyer_message_whatsapp,
    format_audio_depuis_mime,
    telecharger_fichier,
)

logger = logging.getLogger(__name__)


class WhatsappWebhookView(APIView):
    """
    Webhook entrant Green API (WhatsApp).

    Green API envoie un JSON par évènement. On ne traite que
    `typeWebhook == incomingMessageReceived` (texte, audio, image) ; les autres
    évènements sont acquittés sans action.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def _token_valide(self, request) -> bool:
        expected = getattr(settings, "GREEN_API_WEBHOOK_TOKEN", "")
        if not expected:
            return True  # validation désactivée si aucun token configuré
        auth = request.headers.get("Authorization", "")
        provided = auth[7:] if auth.startswith("Bearer ") else auth
        return provided == expected

    @extend_schema(
        tags=["WhatsApp"],
        summary="Webhook entrant Green API",
        description=(
            "Reçoit les messages WhatsApp (texte, audio, image). Les notes "
            "vocales sont transcrites par Mistral Voxtral, puis le patient est "
            "guidé pour déposer un signalement. Répond toujours `200` à la "
            "passerelle ; les réponses au patient partent via l'API d'envoi."
        ),
        request=WhatsappWebhookSerializer,
        responses={200: OpenApiResponse(response=OpenApiTypes.OBJECT, description="Acquittement.")},
    )
    def post(self, request):
        if not self._token_valide(request):
            return Response(
                {"success": False, "error": {"detail": "Token webhook invalide."}},
                status=status.HTTP_403_FORBIDDEN,
            )

        payload = request.data if isinstance(request.data, dict) else {}
        if payload.get("typeWebhook") != "incomingMessageReceived":
            return Response({"status": "ignored"})

        sender = (payload.get("senderData") or {}).get("sender")
        message_data = payload.get("messageData") or {}
        type_message = message_data.get("typeMessage")

        if not sender or not type_message:
            return Response({"status": "ignored"})

        try:
            reply = self._traiter_message(sender, type_message, message_data)
        except Exception:  # noqa: BLE001 — on ne casse jamais l'accusé de réception
            logger.exception("Erreur lors du traitement du message WhatsApp")
            reply = (
                "❌ Une erreur est survenue. Merci de réessayer dans un instant."
            )

        if reply:
            self._envoyer_reponse(sender, reply)

        return Response({"status": "processed"})

    def _envoyer_reponse(self, sender, reply):
        # Note vocale (TTS français) d'abord, pour les patients non-lecteurs.
        try:
            audio_url = synthetiser_fr(reply)
            if audio_url:
                envoyer_fichier_url_whatsapp(sender, audio_url)
        except Exception:  # noqa: BLE001 — la voix ne bloque jamais le texte
            logger.exception("Échec de l'envoi de la note vocale WhatsApp")
        # Puis le texte (toujours envoyé).
        try:
            envoyer_message_whatsapp(sender, reply)
        except GreenApiError:
            logger.exception("Échec de l'envoi du message WhatsApp")

    def _traiter_message(self, sender, type_message, message_data) -> str:
        if type_message == "textMessage":
            text = (message_data.get("textMessageData") or {}).get("textMessage", "")
            return handle_incoming(sender, text=text)

        if type_message in ("audioMessage", "voiceMessage"):
            file_data = message_data.get("fileMessageData") or {}
            download_url = file_data.get("downloadUrl")
            if not download_url:
                return "Je n'ai pas pu récupérer votre note vocale. Réessayez."
            audio_bytes = telecharger_fichier(download_url)
            audio_format = format_audio_depuis_mime(file_data.get("mimeType"))
            return handle_incoming(sender, audio_bytes=audio_bytes, audio_format=audio_format)

        if type_message == "imageMessage":
            caption = (message_data.get("fileMessageData") or {}).get("caption", "")
            if caption.strip():
                return handle_incoming(sender, text=caption)
            return (
                "📷 Les images seules ne sont pas analysées. Décrivez votre "
                "signalement par texte ou *note vocale*."
            )

        return handle_incoming(sender, text="")
