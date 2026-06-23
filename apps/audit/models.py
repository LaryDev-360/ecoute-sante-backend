from django.conf import settings
from django.db import models

from apps.facilities.models import Facility


class AuditAction(models.TextChoices):
    COMPLAINT_CREATED = "COMPLAINT_CREATED", "Signalement enregistré"
    COMPLAINT_STATUS_CHANGED = "COMPLAINT_STATUS_CHANGED", "Statut modifié"
    COMPLAINT_REJECTED = "COMPLAINT_REJECTED", "Plainte rejetée"
    COMPLAINT_COMMENT_ADDED = "COMPLAINT_COMMENT_ADDED", "Commentaire interne ajouté"


class AuditResourceType(models.TextChoices):
    COMPLAINT = "complaint", "Plainte"


class AuditLog(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=40, choices=AuditAction.choices)
    resource_type = models.CharField(max_length=30, choices=AuditResourceType.choices)
    resource_id = models.CharField(max_length=64)
    resource_label = models.CharField(max_length=255, blank=True)
    summary = models.TextField()
    metadata = models.JSONField(default=dict, blank=True)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "entrée de journal"
        verbose_name_plural = "journal d'audit"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["-created_at"]),
            models.Index(fields=["facility", "-created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
            models.Index(fields=["action"]),
        ]

    def __str__(self):
        return f"{self.action} — {self.resource_label or self.resource_id}"
