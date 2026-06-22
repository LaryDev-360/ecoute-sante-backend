from django.conf import settings
from django.db import models


class FacilityType(models.TextChoices):
    HOSPITAL = "HOSPITAL", "Hôpital"
    HEALTH_CENTER = "HEALTH_CENTER", "Centre de santé"
    CLINIC = "CLINIC", "Clinique"
    PHARMACY = "PHARMACY", "Pharmacie"
    OTHER = "OTHER", "Autre"


class Facility(models.Model):
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=50, unique=True)
    facility_type = models.CharField(max_length=50, choices=FacilityType.choices)
    region = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    address = models.TextField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "établissement"
        verbose_name_plural = "établissements"
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class FacilityService(models.Model):
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name="services",
    )
    name = models.CharField(max_length=150)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "service"
        verbose_name_plural = "services"
        ordering = ["name"]
        unique_together = [("facility", "name")]

    def __str__(self):
        return f"{self.name} — {self.facility.code}"


class UserFacilityAssignment(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="facility_assignment",
    )
    facility = models.ForeignKey(
        Facility,
        on_delete=models.CASCADE,
        related_name="assignments",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "affectation établissement"
        verbose_name_plural = "affectations établissement"

    def __str__(self):
        return f"{self.user.username} → {self.facility.code}"
