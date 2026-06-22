from rest_framework import serializers

from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintType,
    SubmissionType,
    SubmitterProfile,
)
from apps.complaints.services import (
    ComplaintValidationError,
    apply_submitter_context,
    validate_complaint_submission,
)
from apps.facilities.models import Facility, FacilityService


class ComplaintCreateSerializer(serializers.ModelSerializer):
    """
  Serializer de création — utilisé par l'API publique et les agents connectés.
    Le déclarant choisit son profil via `submitter_profile`.
    """

    class Meta:
        model = Complaint
        fields = (
            "submitter_profile",
            "submission_type",
            "complaint_type",
            "facility",
            "service",
            "category",
            "reported_agent",
            "reported_agent_name",
            "title",
            "description",
            "incident_date",
            "severity",
            "phone",
            "email",
            "preferred_contact_method",
        )

    def validate(self, attrs):
        user = self.context.get("request").user if self.context.get("request") else None
        if user and not user.is_authenticated:
            user = None

        try:
            validate_complaint_submission(attrs, user=user)
        except ComplaintValidationError as exc:
            field = exc.field or "non_field_errors"
            raise serializers.ValidationError({field: exc.message}) from exc

        return apply_submitter_context(attrs, user=user)

    def validate_service(self, service):
        facility_id = self.initial_data.get("facility")
        if facility_id and str(service.facility_id) != str(facility_id):
            raise serializers.ValidationError(
                "Le service n'appartient pas à l'établissement sélectionné."
            )
        return service

    def validate_category(self, category):
        if not category.active:
            raise serializers.ValidationError("Cette catégorie n'est plus active.")
        return category

    def validate_facility(self, facility):
        if not facility.active:
            raise serializers.ValidationError("Cet établissement n'est plus actif.")
        return facility


class SubmitterProfileChoicesSerializer(serializers.Serializer):
    """Métadonnées exposées à l'UI pour le choix du profil déclarant."""

    value = serializers.CharField()
    label = serializers.CharField()
    description = serializers.CharField()
    requires_auth = serializers.BooleanField()
    allows_reported_agent = serializers.BooleanField()


SUBMITTER_PROFILE_META = [
    {
        "value": SubmitterProfile.CITIZEN,
        "label": SubmitterProfile.CITIZEN.label,
        "description": "Je dépose en tant qu'usager, patient ou visiteur.",
        "requires_auth": False,
        "allows_reported_agent": False,
    },
    {
        "value": SubmitterProfile.FACILITY_AGENT,
        "label": SubmitterProfile.FACILITY_AGENT.label,
        "description": (
            "Je suis agent d'un établissement et je signale un problème "
            "impliquant un autre agent (compte ou nom)."
        ),
        "requires_auth": True,
        "allows_reported_agent": True,
    },
]
