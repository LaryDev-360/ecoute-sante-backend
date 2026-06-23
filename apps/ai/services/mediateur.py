from apps.ai.services.mistral import MistralError, audio_chat_completion
from apps.ai.services.openrouter import extract_json_object

SUPPORTED_FORMATS = ("ogg", "mp3", "wav", "webm")

SYSTEM_PROMPT = (
    "Tu es Gbègbe, un médiateur vocal bienveillant dans un hôpital au Bénin. "
    "Détecte automatiquement la langue parlée (fon, yoruba ou français). "
    "Transcris fidèlement et intégralement ce que dit le patient, mot pour mot, "
    "sans rien inventer ni répéter. Si c'est en fon ou yoruba, traduis fidèlement "
    "en français. Génère UNIQUEMENT ce JSON sans texte autour ni balises markdown : "
    "{ langue_detectee, transcription_fr, type (plainte/suggestion/felicitation), "
    "service (urgences/consultation/pharmacie/autre), gravite (faible/moyen/urgent), "
    "resume }"
)

EXPECTED_KEYS = (
    "langue_detectee",
    "transcription_fr",
    "type",
    "service",
    "gravite",
    "resume",
)


class GbegbeError(Exception):
    def __init__(self, message, code="mediateur_failed"):
        self.message = message
        self.code = code
        super().__init__(message)


def mediate_audio(audio_base64: str, audio_format: str) -> dict:
    """
    Transmet un audio (base64) au médiateur vocal Gbègbe via Mistral et retourne
    le signalement structuré. Résultat indicatif — jamais persisté automatiquement.
    """
    audio_format = (audio_format or "").strip().lower()
    if audio_format not in SUPPORTED_FORMATS:
        raise GbegbeError(
            f"Format audio non supporté. Formats acceptés : {', '.join(SUPPORTED_FORMATS)}.",
            code="unsupported_format",
        )
    if not audio_base64:
        raise GbegbeError("Audio manquant.", code="missing_audio")

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": [
                {
                    "type": "input_audio",
                    "input_audio": {"data": audio_base64, "format": audio_format},
                }
            ],
        },
    ]

    try:
        content = audio_chat_completion(messages, temperature=0)
        parsed = extract_json_object(content)
    except MistralError:
        raise
    except (ValueError, TypeError) as exc:
        raise GbegbeError(
            "Impossible d'interpréter la réponse du modèle vocal.",
            code="invalid_model_response",
        ) from exc

    missing = [key for key in EXPECTED_KEYS if key not in parsed]
    if missing:
        raise GbegbeError(
            "Réponse du modèle incomplète : " + ", ".join(missing) + ".",
            code="incomplete_model_response",
        )

    return {key: parsed[key] for key in EXPECTED_KEYS}
