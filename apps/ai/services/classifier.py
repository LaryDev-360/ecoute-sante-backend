from apps.ai.constants import DEFAULT_CATEGORIES, VALID_PRIORITIES
from apps.ai.services.openrouter import OpenRouterError, chat_completion, extract_json_object
from apps.complaints.models import ComplaintCategory, Severity


class ClassificationError(Exception):
    def __init__(self, message, code="classification_failed"):
        self.message = message
        self.code = code
        super().__init__(message)


def get_valid_categories() -> list[str]:
    names = list(
        ComplaintCategory.objects.filter(active=True)
        .order_by("name")
        .values_list("name", flat=True)
    )
    return names or DEFAULT_CATEGORIES.copy()


def _build_prompt(description: str, categories: list[str]) -> str:
    category_list = ", ".join(f'"{name}"' for name in categories)
    priority_list = ", ".join(VALID_PRIORITIES)
    return (
        "Tu es un assistant pour Santé Écoute, plateforme de signalements sanitaires au Bénin.\n"
        "Analyse la description ci-dessous et propose une catégorie et une priorité INDICATIVES.\n"
        "Ne réponds pas au citoyen, ne donne pas de conseil médical.\n\n"
        f"Catégories valides (nom exact) : {category_list}\n"
        f"Priorités valides : {priority_list}\n\n"
        'Réponds UNIQUEMENT avec un JSON valide : {"category": "...", "priority": "..."}\n\n'
        f"Description :\n{description.strip()}"
    )


def _normalize_category(raw: str, categories: list[str]) -> str:
    value = (raw or "").strip()
    if not value:
        return "Autre" if "Autre" in categories else categories[-1]

    for name in categories:
        if name.lower() == value.lower():
            return name

    for name in categories:
        if value.lower() in name.lower() or name.lower() in value.lower():
            return name

    return "Autre" if "Autre" in categories else categories[0]


def _normalize_priority(raw: str) -> str:
    value = (raw or "").strip().upper()
    if value in VALID_PRIORITIES:
        return value
    if value in Severity.values:
        return value
    return Severity.MEDIUM


def classify_description(description: str) -> dict:
    """
    Classifie une description via OpenRouter.
    Résultat indicatif — jamais persisté automatiquement sur une plainte.
    """
    description = (description or "").strip()
    if len(description) < 10:
        raise ClassificationError(
            "La description doit contenir au moins 10 caractères.",
            code="description_too_short",
        )

    categories = get_valid_categories()
    prompt = _build_prompt(description, categories)
    messages = [
        {
            "role": "system",
            "content": (
                "Tu classifies des signalements sanitaires. "
                "Réponds uniquement en JSON compact, sans texte additionnel."
            ),
        },
        {"role": "user", "content": prompt},
    ]

    try:
        content = chat_completion(messages)
        parsed = extract_json_object(content)
    except OpenRouterError:
        raise
    except (ValueError, TypeError) as exc:
        raise ClassificationError(
            "Impossible d'interpréter la réponse du modèle.",
            code="invalid_model_response",
        ) from exc

    category = _normalize_category(str(parsed.get("category", "")), categories)
    priority = _normalize_priority(str(parsed.get("priority", "")))

    return {
        "category": category,
        "priority": priority,
        "disclaimer": (
            "Suggestion indicative générée par IA — à valider par le déclarant "
            "avant soumission."
        ),
    }
