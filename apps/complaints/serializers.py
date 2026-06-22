from rest_framework import serializers

from apps.complaints.attachments import AttachmentValidationError, save_complaint_attachments
from apps.complaints.models import (
    Complaint,
    ComplaintAttachment,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintStatusHistory,
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
    Serializer de création — API publique et agents connectés.
    Le déclarant choisit son profil via `submitter_profile`.
  """

    attachments = serializers.ListField(
        child=serializers.FileField(),
        required=False,
        write_only=True,
    )

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
            "attachments",
        )

    def validate_attachments(self, files):
        for uploaded_file in files:
            try:
                from apps.complaints.attachments import validate_complaint_attachment

                validate_complaint_attachment(uploaded_file)
            except AttachmentValidationError as exc:
                raise serializers.ValidationError(exc.message) from exc
        return files

    def create(self, validated_data):
        attachments = validated_data.pop("attachments", [])
        complaint = Complaint.objects.create(**validated_data)
        if attachments:
            save_complaint_attachments(complaint, attachments)
        return complaint

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


class ComplaintAttachmentResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintAttachment
        fields = ("id", "file", "uploaded_at")
        read_only_fields = fields


class ComplaintCreateResponseSerializer(serializers.ModelSerializer):
    attachments = ComplaintAttachmentResponseSerializer(many=True, read_only=True)
    message = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = (
            "id",
            "reference",
            "current_status",
            "submitter_profile",
            "submission_type",
            "complaint_type",
            "created_at",
            "attachments",
            "message",
        )
        read_only_fields = fields

    def get_message(self, obj):
        return (
            f"Votre signalement a été enregistré sous la référence {obj.reference}. "
            "Conservez cette référence pour le suivi."
        )


class ComplaintStatusTimelineSerializer(serializers.ModelSerializer):
    status = serializers.CharField(source="new_status")

    class Meta:
        model = ComplaintStatusHistory
        fields = ("status", "created_at")


class ComplaintTrackSerializer(serializers.ModelSerializer):
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    status_timeline = ComplaintStatusTimelineSerializer(
        source="status_history",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Complaint
        fields = (
            "reference",
            "title",
            "current_status",
            "complaint_type",
            "facility_name",
            "created_at",
            "updated_at",
            "status_timeline",
        )
        read_only_fields = fields


class ComplaintCategoryPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintCategory
        fields = ("id", "name", "description")


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
