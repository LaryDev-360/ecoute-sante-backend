from django.db import models

from apps.complaints.models import ComplaintCategory
from apps.facilities.models import Facility, FacilityService


class WhatsappSession(models.Model):
    """
    État d'une conversation WhatsApp (Green API) pour le dépôt pas-à-pas d'un
    signalement. Identifiée par le numéro de l'expéditeur (chatId Green API).

    Le numéro sert uniquement à router la conversation ; il n'est pas recopié
    sur la plainte si le patient choisit le mode anonyme.
    """

    chat_id = models.CharField(max_length=64, unique=True)
    language = models.CharField(max_length=5, default="fr")
    step = models.CharField(max_length=30, default="ASK_LANG")
    page = models.PositiveIntegerField(default=0)
    anonymous = models.BooleanField(default=False)
    facility = models.ForeignKey(
        Facility,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    service = models.ForeignKey(
        FacilityService,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    category = models.ForeignKey(
        ComplaintCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    complaint_type = models.CharField(max_length=20, blank=True)
    severity = models.CharField(max_length=20, blank=True)
    description = models.TextField(blank=True)
    transcription_ia = models.TextField(blank=True)
    complaint = models.ForeignKey(
        "complaints.Complaint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "session WhatsApp"
        verbose_name_plural = "sessions WhatsApp"
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["chat_id"])]

    def __str__(self):
        return f"WhatsApp {self.chat_id} ({self.step})"
