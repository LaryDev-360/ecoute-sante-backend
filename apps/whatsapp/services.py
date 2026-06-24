"""
Machine à états de la conversation WhatsApp (Green API).

Parcours : type → anonymat → établissement → service → catégorie →
description (texte ou note vocale transcrite par Voxtral) → création de la
plainte (réutilise le modèle `Complaint` existant).

Les notes vocales sont transcrites via le service Mistral déjà en place
(`apps.ai.services.mediateur`). L'audio brut n'est jamais sauvegardé : seule
la transcription en français est conservée.
"""
import base64

from django.db import transaction

from apps.ai.services.mediateur import GbegbeError, mediate_audio
from apps.ai.services.mistral import MistralError
from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintType,
    Severity,
    SubmissionType,
    SubmitterProfile,
)
from apps.facilities.models import Facility, FacilityService
from apps.whatsapp.models import WhatsappSession

PAGE_SIZE = 8

LANG_CHOICES = [
    ("1", "fr", "Français"),
    ("2", "fon", "Fɔngbe"),
    ("3", "yo", "Yorùbá"),
]

TYPE_CHOICES = [
    ("1", ComplaintType.COMPLAINT, "Plainte"),
    ("2", ComplaintType.SUGGESTION, "Suggestion"),
    ("3", ComplaintType.APPRECIATION, "Félicitation"),
]

_AI_TYPE_MAP = {
    "plainte": ComplaintType.COMPLAINT,
    "suggestion": ComplaintType.SUGGESTION,
    "felicitation": ComplaintType.APPRECIATION,
    "félicitation": ComplaintType.APPRECIATION,
}
_AI_SEVERITY_MAP = {
    "faible": Severity.LOW,
    "moyen": Severity.MEDIUM,
    "moyenne": Severity.MEDIUM,
    "eleve": Severity.HIGH,
    "élevé": Severity.HIGH,
    "elevee": Severity.HIGH,
    "urgent": Severity.URGENT,
}


# --- Pagination des listes dynamiques ---------------------------------------


def _page(qs, page: int):
    start = page * PAGE_SIZE
    items = list(qs[start : start + PAGE_SIZE])
    total = qs.count()
    return items, page > 0, start + PAGE_SIZE < total


def _render_menu(title: str, qs, page: int, error: str = "", with_other: bool = False) -> str:
    items, has_prev, has_next = _page(qs, page)
    lines = []
    if error:
        lines.append(f"⚠️ {error}")
    lines.append(title)
    if not items:
        lines.append("(aucun élément disponible)")
    for index, obj in enumerate(items, start=1):
        lines.append(f"{index}. {obj.name}")
    if with_other:
        lines.append("0. Autre (préciser)")
    nav = []
    if has_prev:
        nav.append("98 ⬅️ précédent")
    if has_next:
        nav.append("99 ➡️ suivant")
    lines.append("\nRépondez par le numéro." + (" " + " | ".join(nav) if nav else ""))
    return "\n".join(lines)


def _paginate_select(qs, page: int, latest: str):
    items, has_prev, has_next = _page(qs, page)
    if latest == "99" and has_next:
        return "page", page + 1
    if latest == "98" and has_prev:
        return "page", page - 1
    if latest.isdigit():
        idx = int(latest)
        if 1 <= idx <= len(items):
            return "select", items[idx - 1]
    return "invalid", None


def _facilities_qs():
    return Facility.objects.filter(active=True).order_by("name")


def _services_qs(session):
    return FacilityService.objects.filter(facility=session.facility, active=True).order_by("name")


def _categories_qs():
    return ComplaintCategory.objects.filter(active=True).order_by("name")


# --- Menus statiques --------------------------------------------------------


def _menu_langue(error: str = "") -> str:
    prefix = f"⚠️ {error}\n" if error else ""
    return (
        f"{prefix}Bienvenue à Gbègbe 👋\n"
        "Choisissez votre langue / Sɔ́ gbè towe / Yan èdè rẹ:\n"
        "1. Français\n"
        "2. Fɔngbe\n"
        "3. Yorùbá\n\n"
        "🎧 Une note vocale accompagne chaque étape."
    )


def _menu_type(error: str = "") -> str:
    prefix = f"⚠️ {error}\n" if error else ""
    return (
        f"{prefix}Que souhaitez-vous faire ?\n"
        "1. Déposer une plainte\n"
        "2. Faire une suggestion\n"
        "3. Envoyer une félicitation\n\n"
        "💡 Vous pouvez aussi envoyer directement une *note vocale* "
        "(fon, yoruba ou français)."
    )


def _menu_anonymat(error: str = "") -> str:
    prefix = f"⚠️ {error}\n" if error else ""
    return (
        f"{prefix}Souhaitez-vous rester anonyme ?\n"
        "1. Oui, anonyme\n"
        "2. Non, je donne mon numéro"
    )


# --- Transcription d'une note vocale ----------------------------------------


def _transcrire_audio(session, audio_bytes: bytes, audio_format: str) -> dict | None:
    audio_base64 = base64.b64encode(audio_bytes).decode("ascii")
    try:
        result = mediate_audio(audio_base64, audio_format)
    except (GbegbeError, MistralError):
        return None

    session.transcription_ia = result.get("transcription_fr", "")
    session.description = result.get("transcription_fr", "")
    ai_type = (result.get("type") or "").strip().lower()
    if ai_type in _AI_TYPE_MAP:
        session.complaint_type = _AI_TYPE_MAP[ai_type]
    ai_gravite = (result.get("gravite") or "").strip().lower()
    if ai_gravite in _AI_SEVERITY_MAP:
        session.severity = _AI_SEVERITY_MAP[ai_gravite]
    return result


# --- Étapes -----------------------------------------------------------------


def _step_lang(session, latest: str) -> str:
    mapping = {key: value for key, value, _ in LANG_CHOICES}
    if latest in mapping:
        session.language = mapping[latest]
        session.step = "ASK_TYPE"
        session.save()
        return _menu_type()
    return _menu_langue(error="Choix invalide.")


def _step_type(session, latest: str) -> str:
    mapping = {key: value for key, value, _ in TYPE_CHOICES}
    if latest in mapping:
        session.complaint_type = mapping[latest]
        session.step = "ASK_ANON"
        session.save()
        return _menu_anonymat()
    return _menu_type(error="Choix invalide.")


def _step_anon(session, latest: str) -> str:
    if latest == "1":
        session.anonymous = True
    elif latest == "2":
        session.anonymous = False
    else:
        return _menu_anonymat(error="Répondez 1 (anonyme) ou 2 (non).")
    session.step = "ASK_FACILITY"
    session.page = 0
    session.save()
    return _enter_facilities(session)


def _enter_facilities(session) -> str:
    qs = _facilities_qs()
    if not qs.exists():
        session.step = "DONE"
        session.save()
        return "Aucun établissement n'est disponible pour le moment. Réessayez plus tard."
    return _render_menu("🏥 Choisissez l'établissement :", qs, session.page)


def _step_facility(session, latest: str) -> str:
    qs = _facilities_qs()
    kind, value = _paginate_select(qs, session.page, latest)
    if kind == "page":
        session.page = value
        session.save()
        return _render_menu("🏥 Choisissez l'établissement :", qs, session.page)
    if kind == "select":
        session.facility = value
        session.service = None
        session.step = "ASK_SERVICE"
        session.page = 0
        session.save()
        return _enter_services(session)
    return _render_menu("🏥 Choisissez l'établissement :", qs, session.page, error="Choix invalide.")


def _enter_services(session) -> str:
    qs = _services_qs(session)
    if not qs.exists():
        # Aucun service prédéfini : on demande directement la saisie libre.
        session.step = "ASK_SERVICE_OTHER"
        session.save()
        return "✍️ Indiquez le service concerné :"
    return _render_menu("🩺 Choisissez le service :", qs, session.page, with_other=True)


def _step_service(session, latest: str) -> str:
    if latest == "0":
        session.step = "ASK_SERVICE_OTHER"
        session.save()
        return "✍️ Précisez le service concerné :"
    qs = _services_qs(session)
    kind, value = _paginate_select(qs, session.page, latest)
    if kind == "page":
        session.page = value
        session.save()
        return _render_menu("🩺 Choisissez le service :", qs, session.page, with_other=True)
    if kind == "select":
        session.service = value
        session.step = "ASK_CATEGORY"
        session.page = 0
        session.save()
        return _enter_categories(session)
    return _render_menu(
        "🩺 Choisissez le service :", qs, session.page, error="Choix invalide.", with_other=True
    )


def _step_service_other(session, latest: str) -> str:
    name = " ".join((latest or "").split()).strip()[:150]
    if len(name) < 2:
        return "Nom de service trop court. Indiquez le service concerné :"
    service, _ = FacilityService.objects.get_or_create(facility=session.facility, name=name)
    session.service = service
    session.step = "ASK_CATEGORY"
    session.page = 0
    session.save()
    return _enter_categories(session)


def _enter_categories(session) -> str:
    qs = _categories_qs()
    if not qs.exists():
        session.step = "DONE"
        session.save()
        return "Aucune catégorie n'est disponible pour le moment."
    return _render_menu("🗂️ Choisissez la catégorie :", qs, session.page)


def _step_category(session, latest: str) -> str:
    qs = _categories_qs()
    kind, value = _paginate_select(qs, session.page, latest)
    if kind == "page":
        session.page = value
        session.save()
        return _render_menu("🗂️ Choisissez la catégorie :", qs, session.page)
    if kind == "select":
        session.category = value
        session.save()
        return _apres_categorie(session)
    return _render_menu("🗂️ Choisissez la catégorie :", qs, session.page, error="Choix invalide.")


def _apres_categorie(session) -> str:
    """La description peut déjà exister (note vocale transcrite en amont)."""
    if session.description.strip():
        return _creer_et_confirmer(session)
    session.step = "ASK_DESCRIPTION"
    session.save()
    return "✍️ Décrivez votre signalement (message texte ou *note vocale*) :"


def _step_description(session, latest: str) -> str:
    description = (latest or "").strip()
    if len(description) < 5:
        return "Description trop courte. Décrivez votre signalement (min. 5 caractères) :"
    session.description = description
    session.save()
    return _creer_et_confirmer(session)


@transaction.atomic
def _creer_et_confirmer(session) -> str:
    severity = session.severity or Severity.MEDIUM
    anonyme = session.anonymous
    title = session.description[:120].strip() or f"Signalement {session.category.name}"

    complaint = Complaint.objects.create(
        submitter_profile=SubmitterProfile.CITIZEN,
        submission_type=SubmissionType.ANONYMOUS if anonyme else SubmissionType.IDENTIFIED,
        complaint_type=session.complaint_type or ComplaintType.COMPLAINT,
        facility=session.facility,
        service=session.service,
        category=session.category,
        title=title,
        description=session.description,
        severity=severity,
        phone="" if anonyme else session.chat_id.split("@")[0],
    )
    session.complaint = complaint
    session.step = "DONE"
    session.save()

    confidentialite = (
        "🔒 Votre signalement est *anonyme*."
        if anonyme
        else "Votre numéro a été enregistré pour le suivi."
    )
    transcription = (
        f"\n\n🗣️ Transcription : {session.transcription_ia.strip()}"
        if session.transcription_ia.strip()
        else ""
    )
    return (
        "✅ Merci ! Votre signalement a bien été enregistré.\n"
        f"📁 Numéro de dossier : *{complaint.reference}*\n"
        f"{confidentialite}\n"
        "Conservez ce numéro pour suivre votre dossier."
        f"{transcription}"
    )


_STEP_HANDLERS = {
    "ASK_LANG": _step_lang,
    "ASK_TYPE": _step_type,
    "ASK_ANON": _step_anon,
    "ASK_FACILITY": _step_facility,
    "ASK_SERVICE": _step_service,
    "ASK_SERVICE_OTHER": _step_service_other,
    "ASK_CATEGORY": _step_category,
    "ASK_DESCRIPTION": _step_description,
}

# Mots-clés qui ramènent à l'accueil à n'importe quelle étape.
_RESTART_KEYWORDS = {"menu", "recommencer", "restart", "annuler", "cancel", "accueil"}


def _reset(session) -> None:
    session.step = "ASK_LANG"
    session.page = 0
    session.anonymous = False
    session.facility = None
    session.service = None
    session.category = None
    session.complaint_type = ""
    session.severity = ""
    session.description = ""
    session.transcription_ia = ""
    session.complaint = None
    session.save()


@transaction.atomic
def handle_incoming(
    chat_id: str,
    *,
    text: str = "",
    audio_bytes: bytes | None = None,
    audio_format: str = "ogg",
) -> str:
    """
    Traite un message entrant et renvoie le texte de la réponse à envoyer au
    patient. `chat_id` est l'identifiant Green API de l'expéditeur.

    Le traitement est sérialisé par conversation (verrou sur la ligne de
    session) afin que des messages rapprochés du même patient soient traités
    dans l'ordre, sans réponses qui se croisent.
    """
    _, created = WhatsappSession.objects.get_or_create(chat_id=chat_id)
    session = WhatsappSession.objects.select_for_update().get(chat_id=chat_id)

    message = (text or "").strip()

    # Premier contact (ou reprise après un dossier finalisé) : message d'accueil.
    # Une note vocale envoyée d'emblée est traitée directement (voir plus bas).
    if (created or session.step == "DONE") and audio_bytes is None:
        _reset(session)
        return _menu_langue()
    if session.step == "DONE":
        _reset(session)

    # Note vocale : transcription Voxtral, puis on enchaîne sur l'anonymat.
    if audio_bytes is not None:
        result = _transcrire_audio(session, audio_bytes, audio_format)
        if result is None:
            return (
                "❌ Impossible de traiter votre note vocale pour le moment. "
                "Vous pouvez décrire votre signalement par écrit."
            )
        if session.step in ("ASK_TYPE", "ASK_ANON"):
            session.step = "ASK_ANON"
            session.save()
            return "🗣️ J'ai bien reçu votre message vocal.\n\n" + _menu_anonymat()
        if session.step == "ASK_DESCRIPTION":
            return _creer_et_confirmer(session)
        session.save()
        return "🗣️ Message vocal reçu. Veuillez répondre au menu en cours."

    # Mots-clés de navigation : ramènent à l'accueil à tout moment.
    if message.lower() in _RESTART_KEYWORDS:
        _reset(session)
        return _menu_langue()

    handler = _STEP_HANDLERS.get(session.step, _step_type)
    return handler(session, message)
