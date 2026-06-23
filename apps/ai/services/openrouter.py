import json
import re
import urllib.error
import urllib.request

from django.conf import settings


class OpenRouterError(Exception):
    def __init__(self, message, code="openrouter_error", status_code=502):
        self.message = message
        self.code = code
        self.status_code = status_code
        super().__init__(message)


def chat_completion(messages: list[dict], *, timeout: float | None = None, model: str | None = None) -> str:
    """
    Appelle l'API OpenRouter chat/completions et retourne le contenu texte.
    """
    api_key = getattr(settings, "OPENROUTER_API_KEY", "")
    if not api_key:
        raise OpenRouterError(
            "Service de classification non configuré (OPENROUTER_API_KEY manquante).",
            code="ai_not_configured",
            status_code=503,
        )

    timeout = timeout if timeout is not None else settings.OPENROUTER_TIMEOUT
    payload = {
        "model": model or settings.OPENROUTER_MODEL,
        "messages": messages,
        "temperature": 0.2,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # "HTTP-Referer": settings.OPENROUTER_APP_URL,
            "X-Title": settings.OPENROUTER_APP_NAME,
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise OpenRouterError(
            f"OpenRouter a répondu avec une erreur HTTP {exc.code}.",
            code="openrouter_http_error",
            status_code=502 if exc.code >= 500 else 503,
        ) from exc
    except urllib.error.URLError as exc:
        if "timed out" in str(exc.reason).lower():
            raise OpenRouterError(
                "Délai dépassé lors de l'appel au modèle.",
                code="openrouter_timeout",
                status_code=504,
            ) from exc
        raise OpenRouterError(
            "Impossible de joindre OpenRouter.",
            code="openrouter_unreachable",
            status_code=503,
        ) from exc
    except TimeoutError as exc:
        raise OpenRouterError(
            "Délai dépassé lors de l'appel au modèle.",
            code="openrouter_timeout",
            status_code=504,
        ) from exc

    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise OpenRouterError(
            "Réponse OpenRouter inattendue.",
            code="openrouter_invalid_response",
            status_code=502,
        ) from exc


def extract_json_object(text: str) -> dict:
    """Extrait un objet JSON depuis une réponse LLM (éventuellement entourée de markdown)."""
    text = text.strip()
    if not text:
        raise ValueError("Réponse vide.")

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        text = fenced.group(1)

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Objet JSON introuvable.")

    return json.loads(text[start : end + 1])
