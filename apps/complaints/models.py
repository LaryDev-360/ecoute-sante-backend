from django.conf import settings
from django.db import models

from apps.facilities.models import Facility, FacilityService


class SubmissionType(models.TextChoices):
    ANONYMOUS = "ANONYMOUS", "Anonyme"
    CONFIDENTIAL = "CONFIDENTIAL", "Confidentiel"
    IDENTIFIED = "IDENTIFIED", "Identifié"


class SubmitterProfile(models.TextChoices):
    CITIZEN = "CITIZEN", "Usager / citoyen"
    FACILITY_AGENT = "FACILITY_AGENT", "Agent d'établissement"


class ComplaintType(models.TextChoices):
    COMPLAINT = "COMPLAINT", "Plainte"
    SUGGESTION = "SUGGESTION", "Suggestion"
    APPRECIATION = "APPRECIATION", "Félicitation"


class Severity(models.TextChoices):
    LOW = "LOW", "Faible"
    MEDIUM = "MEDIUM", "Moyenne"
    HIGH = "HIGH", "Élevée"
    URGENT = "URGENT", "Urgente"


class ComplaintStatus(models.TextChoices):
    RECEIVED = "RECEIVED", "Reçue"
    UNDER_REVIEW = "UNDER_REVIEW", "En examen"
    IN_PROGRESS = "IN_PROGRESS", "En cours"
    WAITING_INFO = "WAITING_INFO", "En attente d'informations"
    RESOLVED = "RESOLVED", "Résolue"
    REJECTED = "REJECTED", "Rejetée"
    CLOSED = "CLOSED", "Clôturée"


class PreferredContactMethod(models.TextChoices):
    EMAIL = "EMAIL", "E-mail"
    PHONE = "PHONE", "Téléphone"
    SMS = "SMS", "SMS"


class ComplaintCategory(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "catégorie de plainte"
        verbose_name_plural = "catégories de plainte"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Complaint(models.Model):
    reference = models.CharField(max_length=30, unique=True, blank=True)
    submitter_profile = models.CharField(
        max_length=20,
        choices=SubmitterProfile.choices,
        default=SubmitterProfile.CITIZEN,
    )
    submission_type = models.CharField(max_length=20, choices=SubmissionType.choices)
    complaint_type = models.CharField(max_length=20, choices=ComplaintType.choices)
    facility = models.ForeignKey(Facility, on_delete=models.PROTECT, related_name="complaints")
    service = models.ForeignKey(FacilityService, on_delete=models.PROTECT, related_name="complaints")
    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.PROTECT,
        related_name="complaints",
    )
    submitted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_complaints",
    )
    reported_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaints_against_agent",
    )
    reported_agent_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Nom de l'agent visé si non enregistré dans le système",
    )
    title = models.CharField(max_length=255)
    description = models.TextField()
    requested_actions = models.TextField(
        blank=True,
        verbose_name="actions souhaitées",
        help_text="Mesures ou actions que le plaignant souhaite voir prises (optionnel).",
    )
    incident_date = models.DateField(null=True, blank=True)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    current_status = models.CharField(
        max_length=30,
        choices=ComplaintStatus.choices,
        default=ComplaintStatus.RECEIVED,
    )
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    preferred_contact_method = models.CharField(
        max_length=30,
        choices=PreferredContactMethod.choices,
        blank=True,
    )
    is_archived = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "plainte"
        verbose_name_plural = "plaintes"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["reference"]),
            models.Index(fields=["current_status"]),
            models.Index(fields=["facility", "current_status"]),
            models.Index(fields=["submitter_profile"]),
            models.Index(fields=["-created_at"]),
        ]

    def __str__(self):
        return self.reference or f"Plainte #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.reference:
            from apps.complaints.services import generate_reference

            self.reference = generate_reference()
        super().save(*args, **kwargs)


class ComplaintAttachment(models.Model):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField(upload_to="complaints/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "pièce jointe"
        verbose_name_plural = "pièces jointes"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"PJ {self.complaint.reference}"


class ComplaintComment(models.Model):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="complaint_comments",
    )
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "commentaire interne"
        verbose_name_plural = "commentaires internes"
        ordering = ["created_at"]

    def __str__(self):
        return f"Commentaire — {self.complaint.reference}"


class ComplaintStatusHistory(models.Model):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    old_status = models.CharField(max_length=30, blank=True)
    new_status = models.CharField(max_length=30, choices=ComplaintStatus.choices)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="complaint_status_changes",
    )
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "historique de statut"
        verbose_name_plural = "historiques de statut"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.complaint.reference}: {self.old_status} → {self.new_status}"


class ComplaintAssignment(models.Model):
    complaint = models.ForeignKey(
        Complaint,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="complaint_assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "affectation de plainte"
        verbose_name_plural = "affectations de plainte"
        ordering = ["-assigned_at"]

    def __str__(self):
        return f"{self.complaint.reference} → {self.assigned_to}"
