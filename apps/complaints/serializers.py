from rest_framework import serializers

from apps.complaints.attachments import AttachmentValidationError, save_complaint_attachments
from apps.complaints.models import (
    Complaint,
    ComplaintAttachment,
    ComplaintCategory,
    ComplaintComment,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintType,
    SubmissionType,
    SubmitterProfile,
)
from apps.complaints.services import (
    ComplaintValidationError,
    apply_submitter_context,
    change_complaint_status,
    reject_complaint,
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
            "requested_actions",
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


class FacilityServicePublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityService
        fields = ("id", "name")


class FacilityPublicSerializer(serializers.ModelSerializer):
    services = FacilityServicePublicSerializer(many=True, read_only=True)

    class Meta:
        model = Facility
        fields = ("id", "name", "code", "region", "city", "services")


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


# --- Hospital API ---


class HospitalComplaintListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    facility_code = serializers.CharField(source="facility.code", read_only=True)
    facility_region = serializers.CharField(source="facility.region", read_only=True)

    class Meta:
        model = Complaint
        fields = (
            "id",
            "reference",
            "title",
            "submitter_profile",
            "submission_type",
            "complaint_type",
            "current_status",
            "severity",
            "category_name",
            "service_name",
            "facility_name",
            "facility_code",
            "facility_region",
            "created_at",
            "updated_at",
        )


class HospitalStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintStatusHistory
        fields = (
            "id",
            "old_status",
            "new_status",
            "changed_by_name",
            "reason",
            "created_at",
        )

    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return obj.changed_by.get_full_name() or obj.changed_by.username
        return None


class HospitalCommentSerializer(serializers.ModelSerializer):
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = ComplaintComment
        fields = ("id", "author_name", "comment", "created_at")

    def get_author_name(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return None


class HospitalComplaintDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)
    submitted_by_name = serializers.SerializerMethodField()
    reported_agent_name_display = serializers.SerializerMethodField()
    attachments = ComplaintAttachmentResponseSerializer(many=True, read_only=True)
    comments = HospitalCommentSerializer(many=True, read_only=True)
    status_history = HospitalStatusHistorySerializer(many=True, read_only=True)
    contact = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = (
            "id",
            "reference",
            "submitter_profile",
            "submission_type",
            "complaint_type",
            "title",
            "description",
            "requested_actions",
            "incident_date",
            "severity",
            "current_status",
            "category_name",
            "service_name",
            "facility_name",
            "submitted_by_name",
            "reported_agent_name_display",
            "contact",
            "created_at",
            "updated_at",
            "attachments",
            "comments",
            "status_history",
        )

    def get_submitted_by_name(self, obj):
        if obj.submitted_by:
            return obj.submitted_by.get_full_name() or obj.submitted_by.username
        return None

    def get_reported_agent_name_display(self, obj):
        if obj.reported_agent:
            return obj.reported_agent.get_full_name() or obj.reported_agent.username
        return obj.reported_agent_name or None

    def get_contact(self, obj):
        if obj.submission_type == SubmissionType.ANONYMOUS:
            return None
        return {
            "phone": obj.phone,
            "email": obj.email,
            "preferred_contact_method": obj.preferred_contact_method,
        }


class ComplaintStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=ComplaintStatus.choices)
    reason = serializers.CharField(required=False, allow_blank=True, default="")

    def save(self, complaint, user):
        try:
            return change_complaint_status(
                complaint,
                self.validated_data["status"],
                changed_by=user,
                reason=self.validated_data.get("reason", ""),
            )
        except ValueError as exc:
            raise serializers.ValidationError({"status": str(exc)}) from exc


class ComplaintRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=3)

    def save(self, complaint, user):
        try:
            return reject_complaint(complaint, user, self.validated_data["reason"])
        except ValueError as exc:
            raise serializers.ValidationError({"reason": str(exc)}) from exc


class ComplaintCommentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ComplaintComment
        fields = ("comment",)

    def create(self, validated_data):
        complaint = self.context["complaint"]
        user = self.context["request"].user
        return ComplaintComment.objects.create(
            complaint=complaint,
            author=user,
            **validated_data,
        )
