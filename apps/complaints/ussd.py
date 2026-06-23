"""
Machine à états USSD (passerelle Africa's Talking) pour le dépôt pas-à-pas
d'une plainte et le suivi par référence.

À chaque requête, la passerelle renvoie le `text` cumulé (saisies séparées par
« * »). On lit uniquement la dernière saisie et on s'appuie sur l'état mémorisé
dans `UssdSession` pour savoir où l'on en est.

Toute réponse commence par :
- « CON » : la session continue (on attend une nouvelle saisie) ;
- « END » : la session se termine (message final).
"""
from django.db import transaction

from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintType,
    Severity,
    SubmissionType,
    SubmitterProfile,
    UssdSession,
)
from apps.facilities.models import Facility, FacilityService

PAGE_SIZE = 4

TYPE_CHOICES = [
    ("1", ComplaintType.COMPLAINT, "Plainte"),
    ("2", ComplaintType.SUGGESTION, "Suggestion"),
    ("3", ComplaintType.APPRECIATION, "Félicitation"),
]
SEVERITY_CHOICES = [
    ("1", Severity.LOW, "Faible"),
    ("2", Severity.MEDIUM, "Moyenne"),
    ("3", Severity.HIGH, "Élevée"),
    ("4", Severity.URGENT, "Urgente"),
]


def _con(text: str) -> str:
    return f"CON {text}"


def _end(text: str) -> str:
    return f"END {text}"


# --- Pagination des listes dynamiques ---------------------------------------


def _page(qs, page: int):
    start = page * PAGE_SIZE
    items = list(qs[start : start + PAGE_SIZE])
    total = qs.count()
    return items, page > 0, start + PAGE_SIZE < total


def _render_menu(title: str, qs, page: int, error: str = "") -> str:
    items, has_prev, has_next = _page(qs, page)
    lines = []
    if error:
        lines.append(error)
    lines.append(title)
    if not items:
        lines.append("(aucun élément disponible)")
    for index, obj in enumerate(items, start=1):
        lines.append(f"{index}. {obj.name[:30]}")
    if has_prev:
        lines.append("98. Précédent")
    if has_next:
        lines.append("99. Suivant")
    return _con("\n".join(lines))


def _paginate_select(qs, page: int, latest: str):
    """Retourne ('page', n) | ('select', obj) | ('invalid', None)."""
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


# --- Menus statiques --------------------------------------------------------


def _menu_home() -> str:
    return _con(
        "Bienvenue à Santé Écoute\n"
        "1. Enregistrer une plainte\n"
        "2. Suivre une plainte"
    )


def _menu_choices(title: str, choices, error: str = "") -> str:
    lines = []
    if error:
        lines.append(error)
    lines.append(title)
    for key, _value, label in choices:
        lines.append(f"{key}. {label}")
    return _con("\n".join(lines))


# --- Entrées dans les étapes à liste ----------------------------------------


def _facilities_qs():
    return Facility.objects.filter(active=True).order_by("name")


def _services_qs(session):
    return FacilityService.objects.filter(
        facility=session.facility, active=True
    ).order_by("name")


def _categories_qs():
    return ComplaintCategory.objects.filter(active=True).order_by("name")


def _enter_facilities(session) -> str:
    qs = _facilities_qs()
    if not qs.exists():
        return _end("Aucun établissement disponible pour le moment.")
    return _render_menu("Choisissez l'établissement:", qs, session.page)


def _enter_services(session) -> str:
    qs = _services_qs(session)
    if not qs.exists():
        return _end("Aucun service disponible pour cet établissement.")
    return _render_menu("Choisissez le service:", qs, session.page)


def _enter_categories(session) -> str:
    qs = _categories_qs()
    if not qs.exists():
        return _end("Aucune catégorie disponible pour le moment.")
    return _render_menu("Choisissez la catégorie:", qs, session.page)


# --- Handlers d'étape -------------------------------------------------------


def _step_home(session, latest: str) -> str:
    if latest == "1":
        session.step = "FACILITY"
        session.page = 0
        session.save()
        return _enter_facilities(session)
    if latest == "2":
        session.step = "TRACK"
        session.save()
        return _con("Entrez votre référence (ex: SE-2026-000001):")
    return _menu_home()


def _step_facility(session, latest: str) -> str:
    qs = _facilities_qs()
    kind, value = _paginate_select(qs, session.page, latest)
    if kind == "page":
        session.page = value
        session.save()
        return _render_menu("Choisissez l'établissement:", qs, session.page)
    if kind == "select":
        session.facility = value
        session.service = None
        session.step = "SERVICE"
        session.page = 0
        session.save()
        return _enter_services(session)
    return _render_menu(
        "Choisissez l'établissement:", qs, session.page, error="Choix invalide."
    )


def _step_service(session, latest: str) -> str:
    qs = _services_qs(session)
    kind, value = _paginate_select(qs, session.page, latest)
    if kind == "page":
        session.page = value
        session.save()
        return _render_menu("Choisissez le service:", qs, session.page)
    if kind == "select":
        session.service = value
        session.step = "CATEGORY"
        session.page = 0
        session.save()
        return _enter_categories(session)
    return _render_menu(
        "Choisissez le service:", qs, session.page, error="Choix invalide."
    )


def _step_category(session, latest: str) -> str:
    qs = _categories_qs()
    kind, value = _paginate_select(qs, session.page, latest)
    if kind == "page":
        session.page = value
        session.save()
        return _render_menu("Choisissez la catégorie:", qs, session.page)
    if kind == "select":
        session.category = value
        session.step = "TYPE"
        session.page = 0
        session.save()
        return _menu_choices("Type de signalement:", TYPE_CHOICES)
    return _render_menu(
        "Choisissez la catégorie:", qs, session.page, error="Choix invalide."
    )


def _step_type(session, latest: str) -> str:
    mapping = {key: value for key, value, _label in TYPE_CHOICES}
    if latest in mapping:
        session.complaint_type = mapping[latest]
        session.step = "SEVERITY"
        session.save()
        return _menu_choices("Gravité:", SEVERITY_CHOICES)
    return _menu_choices("Type de signalement:", TYPE_CHOICES, error="Choix invalide.")


def _step_severity(session, latest: str) -> str:
    mapping = {key: value for key, value, _label in SEVERITY_CHOICES}
    if latest in mapping:
        session.severity = mapping[latest]
        session.step = "DESCRIPTION"
        session.save()
        return _con("Décrivez votre signalement:")
    return _menu_choices("Gravité:", SEVERITY_CHOICES, error="Choix invalide.")


def _step_description(session, latest: str) -> str:
    description = latest.strip()
    if len(description) < 5:
        return _con("Description trop courte. Décrivez votre signalement (min. 5 caractères):")
    complaint = _create_complaint(session, description)
    return _end(
        "Merci. Votre signalement est enregistré.\n"
        f"Référence: {complaint.reference}\n"
        "Conservez-la pour le suivi."
    )


def _step_track(session, latest: str) -> str:
    reference = latest.strip().upper()
    complaint = Complaint.objects.filter(
        reference__iexact=reference, is_archived=False
    ).first()
    if not complaint:
        return _end("Référence introuvable. Vérifiez et réessayez.")
    label = ComplaintStatus(complaint.current_status).label
    return _end(f"Référence: {complaint.reference}\nStatut: {label}")


_STEP_HANDLERS = {
    "HOME": _step_home,
    "FACILITY": _step_facility,
    "SERVICE": _step_service,
    "CATEGORY": _step_category,
    "TYPE": _step_type,
    "SEVERITY": _step_severity,
    "DESCRIPTION": _step_description,
    "TRACK": _step_track,
}


@transaction.atomic
def _create_complaint(session, description: str) -> Complaint:
    title = description[:120].strip() or f"Signalement {session.category.name}"
    complaint = Complaint.objects.create(
        submitter_profile=SubmitterProfile.CITIZEN,
        submission_type=SubmissionType.IDENTIFIED,
        complaint_type=session.complaint_type,
        facility=session.facility,
        service=session.service,
        category=session.category,
        title=title,
        description=description,
        severity=session.severity,
        phone=session.phone_number,
    )
    session.complaint = complaint
    session.step = "DONE"
    session.save()
    return complaint


def handle_ussd(session_id: str, phone_number: str, text: str) -> str:
    """
    Point d'entrée : reçoit les paramètres bruts de la passerelle et renvoie la
    réponse texte (préfixée par « CON » ou « END »).
    """
    session, _created = UssdSession.objects.get_or_create(
        session_id=session_id,
        defaults={"phone_number": phone_number},
    )

    # Début de session (ou retour à l'accueil) : la passerelle envoie un text vide.
    if not text:
        session.step = "HOME"
        session.page = 0
        session.save()
        return _menu_home()

    latest = text.split("*")[-1].strip()
    handler = _STEP_HANDLERS.get(session.step, _step_home)
    return handler(session, latest)
