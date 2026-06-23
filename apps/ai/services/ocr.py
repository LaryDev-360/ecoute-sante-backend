import base64
import mimetypes

from django.conf import settings

from apps.ai.services.classifier import ClassificationError, classify_description
from apps.ai.services.openrouter import OpenRouterError, chat_completion, extract_json_object


class OCRExtractionError(Exception):
    def __init__(self, message, code="ocr_failed"):
        self.message = message
        self.code = code
        super().__init__(message)


OCR_ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"]


def _encode_upload(uploaded_file) -> tuple[str, str]:
    content_type = uploaded_file.content_type
    if not content_type or content_type == "application/octet-stream":
        content_type, _ = mimetypes.guess_type(uploaded_file.name)
    content_type = content_type or "application/octet-stream"

    if content_type not in OCR_ALLOWED_TYPES:
        raise OCRExtractionError(
            "Format non supporté. Utilisez JPEG, PNG, WebP ou PDF.",
            code="unsupported_format",
        )

    raw = uploaded_file.read()
    if len(raw) > 5 * 1024 * 1024:
        raise OCRExtractionError("Fichier trop volumineux (max 5 Mo).", code="file_too_large")

    if content_type == "application/pdf":
        raise OCRExtractionError(
            "PDF non pris en charge pour l'OCR automatique. Photographiez le document ou saisissez manuellement.",
            code="pdf_not_supported",
        )

    b64 = base64.standard_b64encode(raw).decode("ascii")
    return b64, content_type


def _build_ocr_prompt() -> str:
    return (
        "Tu analyses un formulaire papier de plainte/signalement du système de santé au Bénin.\n"
        "Extrais les champs lisibles et réponds UNIQUEMENT en JSON valide avec ces clés :\n"
        "{\n"
        '  "title": "titre court",\n'
        '  "description": "récit complet",\n'
        '  "complaint_type": "COMPLAINT|SUGGESTION|APPRECIATION",\n'
        '  "submission_type": "ANONYMOUS|IDENTIFIED|CONFIDENTIAL",\n'
        '  "phone": "",\n'
        '  "email": "",\n'
        '  "incident_date": "YYYY-MM-DD ou vide",\n'
        '  "registered_on_paper_at": "YYYY-MM-DD ou vide",\n'
        '  "facility_hint": "nom établissement si visible",\n'
        '  "service_hint": "service si visible",\n'
        '  "requested_actions": ""\n'
        "}\n"
        "Utilise des chaînes vides pour les champs illisibles ou absents."
    )


def extract_complaint_from_scan(uploaded_file) -> dict:
    """
    Extrait des champs indicatifs depuis une image de formulaire papier.
    Résultat à réviser obligatoirement par un agent avant création du dossier.
    """
    image_b64, content_type = _encode_upload(uploaded_file)
    data_url = f"data:{content_type};base64,{image_b64}"
    model = getattr(settings, "OPENROUTER_VISION_MODEL", settings.OPENROUTER_MODEL)

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": _build_ocr_prompt()},
                {"type": "image_url", "image_url": {"url": data_url}},
            ],
        }
    ]

    try:
        content = chat_completion(messages, model=model)
        parsed = extract_json_object(content)
    except OpenRouterError as exc:
        raise OCRExtractionError(exc.message, code=exc.code) from exc
    except (ValueError, TypeError) as exc:
        raise OCRExtractionError(
            "Impossible d'interpréter la réponse du modèle OCR.",
            code="invalid_model_response",
        ) from exc

    description = (parsed.get("description") or "").strip()
    classification = None
    if len(description) >= 10:
        try:
            classification = classify_description(description)
        except (ClassificationError, OpenRouterError):
            classification = None

    return {
        "title": (parsed.get("title") or "").strip(),
        "description": description,
        "complaint_type": (parsed.get("complaint_type") or "COMPLAINT").strip().upper(),
        "submission_type": (parsed.get("submission_type") or "ANONYMOUS").strip().upper(),
        "phone": (parsed.get("phone") or "").strip(),
        "email": (parsed.get("email") or "").strip(),
        "incident_date": (parsed.get("incident_date") or "").strip() or None,
        "registered_on_paper_at": (parsed.get("registered_on_paper_at") or "").strip() or None,
        "facility_hint": (parsed.get("facility_hint") or "").strip(),
        "service_hint": (parsed.get("service_hint") or "").strip(),
        "requested_actions": (parsed.get("requested_actions") or "").strip(),
        "suggested_category": classification["category"] if classification else None,
        "suggested_severity": classification["priority"] if classification else None,
        "disclaimer": (
            "Extraction indicative — vérifiez chaque champ avant de créer le dossier."
        ),
    }
