import mimetypes

from django.conf import settings

from apps.complaints.models import ComplaintAttachment


class AttachmentValidationError(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(message)


def validate_complaint_attachment(uploaded_file) -> None:
    max_size = getattr(settings, "COMPLAINT_ATTACHMENT_MAX_SIZE", 5 * 1024 * 1024)
    allowed_types = getattr(
        settings,
        "COMPLAINT_ATTACHMENT_ALLOWED_TYPES",
        ["image/jpeg", "image/png", "image/webp", "application/pdf"],
    )

    if uploaded_file.size > max_size:
        raise AttachmentValidationError(
            f"Fichier trop volumineux (max {max_size // (1024 * 1024)} Mo)."
        )

    content_type = uploaded_file.content_type
    if not content_type or content_type == "application/octet-stream":
        content_type, _ = mimetypes.guess_type(uploaded_file.name)
    if content_type not in allowed_types:
        raise AttachmentValidationError(
            f"Type de fichier non autorisé : {content_type or 'inconnu'}."
        )


def save_complaint_attachments(complaint, files) -> list[ComplaintAttachment]:
    saved = []
    for uploaded_file in files:
        validate_complaint_attachment(uploaded_file)
        saved.append(
            ComplaintAttachment.objects.create(complaint=complaint, file=uploaded_file)
        )
    return saved
