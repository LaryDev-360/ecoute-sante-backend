from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.accounts.managers import UserManager


class UserRole(models.TextChoices):
    ADMIN = "ADMIN", "Administrateur"
    MINISTRY_SUPERVISOR = "MINISTRY_SUPERVISOR", "Superviseur ministère"
    HOSPITAL_MANAGER = "HOSPITAL_MANAGER", "Responsable hôpital"
    FACILITY_AGENT = "FACILITY_AGENT", "Agent d'établissement"


class User(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=30, choices=UserRole.choices)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    class Meta:
        verbose_name = "utilisateur"
        verbose_name_plural = "utilisateurs"

    def __str__(self):
        return self.username

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN

    @property
    def is_ministry_supervisor(self):
        return self.role == UserRole.MINISTRY_SUPERVISOR

    @property
    def is_hospital_manager(self):
        return self.role == UserRole.HOSPITAL_MANAGER

    @property
    def is_facility_agent(self):
        return self.role == UserRole.FACILITY_AGENT

    @property
    def is_facility_staff(self):
        return self.role in (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT)


class OTPPurpose(models.TextChoices):
    LOGIN = "LOGIN", "Connexion"
    RESET_PASSWORD = "RESET_PASSWORD", "Réinitialisation mot de passe"


class OTPChannel(models.TextChoices):
    EMAIL = "EMAIL", "E-mail"
    SMS = "SMS", "SMS"


class OTPVerification(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="otp_verifications",
    )
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(max_length=30, choices=OTPPurpose.choices)
    channel = models.CharField(max_length=10, choices=OTPChannel.choices)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "code OTP"
        verbose_name_plural = "codes OTP"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "is_used"]),
        ]

    def __str__(self):
        return f"OTP {self.purpose} — {self.user.username}"
