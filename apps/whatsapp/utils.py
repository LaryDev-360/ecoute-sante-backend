"""
Intégration Green API (WhatsApp) — envoi de messages et téléchargement des
fichiers entrants (notes vocales). Utilise `urllib` (stdlib) pour rester
cohérent avec le reste du projet.
"""
import json
import urllib.error
import urllib.request

from django.conf import settings


class GreenApiError(Exception):
    def __init__(self, message, code="green_api_error"):
        self.message = message
        self.code = code
        super().__init__(message)


def _instance_base() -> str:
    base = settings.GREEN_API_BASE_URL.rstrip("/")
    return f"{base}/waInstance{settings.GREEN_API_ID_INSTANCE}"


def _chat_id(numero: str) -> str:
    """Normalise un numéro en chatId Green API (`<numero>@c.us`)."""
    numero = str(numero).strip()
    if "@" in numero:
        return numero
    return f"{numero.lstrip('+')}@c.us"


def envoyer_message_whatsapp(numero: str, message: str) -> dict:
    """Envoie un message texte au patient via Green API."""
    if not settings.GREEN_API_ID_INSTANCE or not settings.GREEN_API_TOKEN:
        raise GreenApiError(
            "Green API non configuré (GREEN_API_ID_INSTANCE / GREEN_API_TOKEN).",
            code="green_api_not_configured",
        )

    url = f"{_instance_base()}/sendMessage/{settings.GREEN_API_TOKEN}"
    payload = json.dumps({"chatId": _chat_id(numero), "message": message}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.GREEN_API_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GreenApiError(
            f"Green API a répondu avec une erreur HTTP {exc.code}.",
            code="green_api_http_error",
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise GreenApiError(
            "Impossible de joindre Green API.",
            code="green_api_unreachable",
        ) from exc


def envoyer_fichier_url_whatsapp(
    numero: str,
    url_fichier: str,
    nom_fichier: str = "gbegbe.mp3",
    caption: str = "",
) -> dict:
    """Envoie un fichier accessible par URL (note vocale TTS) via `sendFileByUrl`."""
    if not settings.GREEN_API_ID_INSTANCE or not settings.GREEN_API_TOKEN:
        raise GreenApiError("Green API non configuré.", code="green_api_not_configured")

    url = f"{_instance_base()}/sendFileByUrl/{settings.GREEN_API_TOKEN}"
    payload = {"chatId": _chat_id(numero), "urlFile": url_fichier, "fileName": nom_fichier}
    if caption:
        payload["caption"] = caption
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=settings.GREEN_API_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise GreenApiError(
            f"Green API a répondu avec une erreur HTTP {exc.code}.",
            code="green_api_http_error",
        ) from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise GreenApiError(
            "Impossible de joindre Green API (envoi fichier).",
            code="green_api_unreachable",
        ) from exc


def telecharger_fichier(download_url: str) -> bytes:
    """Télécharge le contenu binaire d'un fichier entrant (note vocale)."""
    try:
        with urllib.request.urlopen(download_url, timeout=settings.GREEN_API_TIMEOUT) as response:
            return response.read()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise GreenApiError(
            "Impossible de télécharger le fichier audio.",
            code="audio_download_failed",
        ) from exc


def format_audio_depuis_mime(mime_type: str) -> str:
    """Déduit le format audio (Voxtral) depuis le type MIME Green API."""
    mime = (mime_type or "").lower()
    if "ogg" in mime or "opus" in mime:
        return "ogg"
    if "mpeg" in mime or "mp3" in mime:
        return "mp3"
    if "wav" in mime:
        return "wav"
    if "webm" in mime:
        return "webm"
    return "ogg"  # note vocale WhatsApp par défaut
