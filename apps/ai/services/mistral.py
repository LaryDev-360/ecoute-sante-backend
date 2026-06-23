import json
import urllib.error
import urllib.request

from django.conf import settings


class MistralError(Exception):
    def __init__(self, message, code="mistral_error", status_code=502):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def audio_chat_completion(
    messages: list[dict],
    *,
    temperature: float = 0,
    timeout: float | None = None,
) -> str:
    """
    Appelle l'API Mistral chat/completions (modèle audio Voxtral) et retourne
    le contenu texte de la réponse.
    """
    api_key = getattr(settings, "MISTRAL_API_KEY", "")
    if not api_key:
        raise MistralError(
            "Service de médiation vocale non configuré (MISTRAL_API_KEY manquante).",
            code="mediateur_not_configured",
            status_code=503,
        )

    timeout = timeout if timeout is not None else settings.MISTRAL_TIMEOUT
    payload = {
        "model": settings.MISTRAL_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.MISTRAL_BASE_URL.rstrip('/')}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise MistralError(
            f"Mistral a répondu avec une erreur HTTP {exc.code}.",
            code="mistral_http_error",
            status_code=502 if exc.code >= 500 else 503,
        ) from exc
    except urllib.error.URLError as exc:
        if "timed out" in str(exc.reason).lower():
            raise MistralError(
                "Délai dépassé lors de l'appel au modèle vocal.",
                code="mistral_timeout",
                status_code=504,
            ) from exc
        raise MistralError(
            "Impossible de joindre Mistral.",
            code="mistral_unreachable",
            status_code=503,
        ) from exc
    except TimeoutError as exc:
        raise MistralError(
            "Délai dépassé lors de l'appel au modèle vocal.",
            code="mistral_timeout",
            status_code=504,
        ) from exc

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise MistralError(
            "Réponse Mistral inattendue.",
            code="mistral_invalid_response",
            status_code=502,
        ) from exc
