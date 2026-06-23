import csv
from io import StringIO

from django.http import HttpResponse
from django.utils import timezone

from apps.complaints.models import Complaint


def complaint_detail_queryset(queryset):
    return queryset.select_related(
        "facility",
        "service",
        "category",
        "submitted_by",
        "reported_agent",
    ).prefetch_related(
        "attachments",
        "comments__author",
        "status_history__changed_by",
    )


def _display_user(user):
    if not user:
        return ""
    return user.get_full_name() or user.username


def export_complaints_csv(queryset) -> HttpResponse:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "reference",
            "title",
            "status",
            "severity",
            "complaint_type",
            "submitter_profile",
            "facility_code",
            "facility_name",
            "region",
            "city",
            "category",
            "service",
            "created_at",
        ]
    )
    for complaint in queryset.iterator():
        writer.writerow(
            [
                complaint.reference,
                complaint.title,
                complaint.current_status,
                complaint.severity,
                complaint.complaint_type,
                complaint.submitter_profile,
                complaint.facility.code,
                complaint.facility.name,
                complaint.facility.region,
                complaint.facility.city,
                complaint.category.name,
                complaint.service.name,
                complaint.created_at.isoformat(),
            ]
        )

    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    filename = f"plaintes_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def export_complaint_detail_csv(complaint: Complaint) -> HttpResponse:
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["section", "champ", "valeur"])

    def row(section: str, field: str, value):
        writer.writerow([section, field, value or ""])

    row("Dossier", "Référence", complaint.reference)
    row("Dossier", "Titre", complaint.title)
    row("Dossier", "Type", complaint.get_complaint_type_display())
    row("Dossier", "Profil déclarant", complaint.get_submitter_profile_display())
    row("Dossier", "Mode de dépôt", complaint.get_submission_type_display())
    row("Dossier", "Statut", complaint.get_current_status_display())
    row("Dossier", "Priorité", complaint.get_severity_display())
    row("Dossier", "Établissement", complaint.facility.name)
    row("Dossier", "Code établissement", complaint.facility.code)
    row("Dossier", "Région", complaint.facility.region)
    row("Dossier", "Ville", complaint.facility.city)
    row("Dossier", "Service", complaint.service.name)
    row("Dossier", "Catégorie", complaint.category.name)
    row("Dossier", "Créé le", complaint.created_at.isoformat())
    row("Dossier", "Mis à jour le", complaint.updated_at.isoformat())
    if complaint.incident_date:
        row("Dossier", "Date de l'incident", complaint.incident_date.isoformat())
    if complaint.submitted_by:
        row("Dossier", "Soumis par", _display_user(complaint.submitted_by))
    reported = _display_user(complaint.reported_agent) or complaint.reported_agent_name
    if reported:
        row("Dossier", "Agent visé", reported)
    row("Dossier", "Description", complaint.description)
    if complaint.requested_actions:
        row("Dossier", "Actions souhaitées", complaint.requested_actions)

    if complaint.submission_type != "ANONYMOUS":
        row("Coordonnées", "Téléphone", complaint.phone)
        row("Coordonnées", "E-mail", complaint.email)
        if complaint.preferred_contact_method:
            row(
                "Coordonnées",
                "Contact préféré",
                complaint.get_preferred_contact_method_display(),
            )

    for attachment in complaint.attachments.all():
        row("Pièces jointes", attachment.uploaded_at.isoformat(), attachment.file.name)

    for entry in complaint.status_history.all():
        old_label = (
            dict(complaint._meta.get_field("current_status").choices).get(
                entry.old_status, entry.old_status
            )
            if entry.old_status
            else ""
        )
        new_label = dict(complaint._meta.get_field("current_status").choices).get(
            entry.new_status, entry.new_status
        )
        transition = f"{old_label} → {new_label}".strip(" →")
        details = " | ".join(
            part
            for part in (
                transition,
                f"Par {_display_user(entry.changed_by)}" if entry.changed_by else "",
                entry.reason,
            )
            if part
        )
        row("Historique statut", entry.created_at.isoformat(), details)

    for comment in complaint.comments.all():
        author = _display_user(comment.author) or "Personnel"
        row(
            "Commentaires internes",
            comment.created_at.isoformat(),
            f"{author}: {comment.comment}",
        )

    response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
    filename = f"{complaint.reference}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
