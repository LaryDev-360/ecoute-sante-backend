import csv
from io import BytesIO, StringIO

from django.http import HttpResponse
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from apps.complaints.models import Complaint, ComplaintStatus


BRAND_GREEN = colors.HexColor("#00875A")
MUTED = colors.HexColor("#64748B")
BORDER = colors.HexColor("#E2E8F0")


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


def _format_datetime(value):
    if not value:
        return ""
    local = timezone.localtime(value)
    return local.strftime("%d/%m/%Y %H:%M")


def _status_label(code: str) -> str:
    if not code:
        return ""
    return dict(ComplaintStatus.choices).get(code, code)


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


def _pdf_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=colors.HexColor("#0F172A"),
            spaceAfter=4,
        ),
        "reference": ParagraphStyle(
            "Reference",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=BRAND_GREEN,
            spaceAfter=8,
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
            parent=base["Normal"],
            fontSize=10,
            textColor=MUTED,
            spaceAfter=14,
        ),
        "section": ParagraphStyle(
            "Section",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=colors.HexColor("#0F172A"),
            spaceBefore=10,
            spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body",
            parent=base["Normal"],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor("#334155"),
        ),
        "meta_label": ParagraphStyle(
            "MetaLabel",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            textColor=MUTED,
        ),
        "meta_value": ParagraphStyle(
            "MetaValue",
            parent=base["Normal"],
            fontSize=10,
            textColor=colors.HexColor("#0F172A"),
        ),
        "footer": ParagraphStyle(
            "Footer",
            parent=base["Normal"],
            fontSize=8,
            textColor=MUTED,
            alignment=TA_LEFT,
        ),
    }


def _escape(text) -> str:
    if text is None:
        return ""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("\n", "<br/>")
    )


def _meta_table(rows, styles):
    data = [
        [
            Paragraph(f"<b>{_escape(label)}</b>", styles["meta_label"]),
            Paragraph(_escape(value), styles["meta_value"]),
        ]
        for label, value in rows
        if value
    ]
    if not data:
        return None

    table = Table(data, colWidths=[45 * mm, None])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("LINEBELOW", (0, 0), (-1, -2), 0.5, BORDER),
            ]
        )
    )
    return table


def export_complaint_detail_pdf(complaint: Complaint) -> HttpResponse:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Dossier {complaint.reference}",
    )
    styles = _pdf_styles()
    story = []

    story.append(Paragraph("Santé Écoute", styles["reference"]))
    story.append(Paragraph("Dossier de plainte", styles["title"]))
    story.append(Paragraph(_escape(complaint.reference), styles["reference"]))
    story.append(Paragraph(_escape(complaint.title), styles["subtitle"]))
    story.append(
        Paragraph(
            _escape(
                f"{complaint.facility.name} · {complaint.service.name} · "
                f"{complaint.category.name}"
            ),
            styles["subtitle"],
        )
    )

    meta_rows = [
        ("Type", complaint.get_complaint_type_display()),
        ("Profil déclarant", complaint.get_submitter_profile_display()),
        ("Mode de dépôt", complaint.get_submission_type_display()),
        ("Statut", complaint.get_current_status_display()),
        ("Priorité", complaint.get_severity_display()),
        ("Établissement", complaint.facility.name),
        ("Code établissement", complaint.facility.code),
        ("Région", complaint.facility.region),
        ("Ville", complaint.facility.city),
        ("Service", complaint.service.name),
        ("Catégorie", complaint.category.name),
        ("Créé le", _format_datetime(complaint.created_at)),
        ("Mis à jour le", _format_datetime(complaint.updated_at)),
    ]
    if complaint.incident_date:
        meta_rows.append(("Date de l'incident", complaint.incident_date.strftime("%d/%m/%Y")))
    if complaint.submitted_by:
        meta_rows.append(("Soumis par", _display_user(complaint.submitted_by)))
    reported = _display_user(complaint.reported_agent) or complaint.reported_agent_name
    if reported:
        meta_rows.append(("Agent visé", reported))

    meta_table = _meta_table(meta_rows, styles)
    if meta_table:
        story.append(meta_table)

    if complaint.submission_type != "ANONYMOUS":
        story.append(Paragraph("Coordonnées", styles["section"]))
        contact_rows = [
            ("Téléphone", complaint.phone),
            ("E-mail", complaint.email),
        ]
        if complaint.preferred_contact_method:
            contact_rows.append(
                ("Contact préféré", complaint.get_preferred_contact_method_display())
            )
        contact_table = _meta_table(contact_rows, styles)
        if contact_table:
            story.append(contact_table)

    story.append(Paragraph("Description", styles["section"]))
    story.append(Paragraph(_escape(complaint.description), styles["body"]))

    if complaint.requested_actions:
        story.append(Paragraph("Actions souhaitées", styles["section"]))
        story.append(Paragraph(_escape(complaint.requested_actions), styles["body"]))

    attachments = list(complaint.attachments.all())
    if attachments:
        story.append(Paragraph("Pièces jointes", styles["section"]))
        for attachment in attachments:
            story.append(
                Paragraph(
                    _escape(
                        f"{_format_datetime(attachment.uploaded_at)} — "
                        f"{attachment.file.name}"
                    ),
                    styles["body"],
                )
            )

    history = list(complaint.status_history.all())
    if history:
        story.append(Paragraph("Historique des statuts", styles["section"]))
        for entry in history:
            old_label = _status_label(entry.old_status)
            new_label = _status_label(entry.new_status)
            transition = f"{old_label} → {new_label}".strip(" →")
            parts = [f"<b>{_format_datetime(entry.created_at)}</b> — {transition}"]
            if entry.changed_by:
                parts.append(f"Par {_escape(_display_user(entry.changed_by))}")
            if entry.reason:
                parts.append(f"<i>{_escape(entry.reason)}</i>")
            story.append(Paragraph(" · ".join(parts), styles["body"]))
            story.append(Spacer(1, 4))

    comments = list(complaint.comments.all())
    if comments:
        story.append(Paragraph("Commentaires internes", styles["section"]))
        for comment in comments:
            author = _display_user(comment.author) or "Personnel"
            story.append(
                Paragraph(
                    f"<b>{_escape(author)}</b> — "
                    f"{_format_datetime(comment.created_at)}<br/>"
                    f"{_escape(comment.comment)}",
                    styles["body"],
                )
            )
            story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))
    story.append(
        Paragraph(
            _escape(
                f"Document généré le {_format_datetime(timezone.now())} — "
                f"Santé Écoute · Ministère de la Santé, République du Bénin"
            ),
            styles["footer"],
        )
    )

    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = f"{complaint.reference}.pdf"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
