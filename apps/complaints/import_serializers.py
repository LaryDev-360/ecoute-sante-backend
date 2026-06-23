from rest_framework import serializers

from apps.complaints.import_services import ComplaintImportError, create_imported_complaint
from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintType,
    Severity,
    SubmissionType,
    SubmitterProfile,
)
from apps.facilities.models import Facility, FacilityService


class ComplaintCSVUploadSerializer(serializers.Serializer):
    file = serializers.FileField(help_text="Fichier CSV UTF-8")


class StaffComplaintImportSerializer(serializers.Serializer):
    submitter_profile = serializers.ChoiceField(
        choices=SubmitterProfile.choices,
        default=SubmitterProfile.CITIZEN,
    )
    submission_type = serializers.ChoiceField(
        choices=SubmissionType.choices,
        default=SubmissionType.ANONYMOUS,
    )
    complaint_type = serializers.ChoiceField(
        choices=ComplaintType.choices,
        default=ComplaintType.COMPLAINT,
    )
    facility = serializers.PrimaryKeyRelatedField(queryset=Facility.objects.filter(active=True))
    service = serializers.PrimaryKeyRelatedField(queryset=FacilityService.objects.filter(active=True))
    category = serializers.PrimaryKeyRelatedField(
        queryset=ComplaintCategory.objects.filter(active=True)
    )
    title = serializers.CharField(max_length=255)
    description = serializers.CharField()
    severity = serializers.ChoiceField(choices=Severity.choices)
    phone = serializers.CharField(required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")
    requested_actions = serializers.CharField(required=False, allow_blank=True, default="")
    incident_date = serializers.DateField(required=False, allow_null=True)
    registered_on_paper_at = serializers.DateField(required=False, allow_null=True)
    ocr_reviewed = serializers.BooleanField(default=False, write_only=True)
    attachment = serializers.FileField(required=False, write_only=True)

    def validate(self, attrs):
        facility = attrs["facility"]
        service = attrs["service"]
        if service.facility_id != facility.pk:
            raise serializers.ValidationError(
                {"service": "Ce service n'appartient pas à l'établissement sélectionné."}
            )
        return attrs

    def create(self, validated_data):
        actor = self.context["request"].user
        attachment = validated_data.pop("attachment", None)
        ocr_reviewed = validated_data.pop("ocr_reviewed", False)
        attachments = [attachment] if attachment else []
        via = "ocr" if ocr_reviewed else "manual"

        try:
            return create_imported_complaint(
                validated_data,
                actor=actor,
                attachments=attachments,
                via=via,
                ocr_reviewed=ocr_reviewed,
            )
        except ComplaintImportError as exc:
            raise serializers.ValidationError({"detail": exc.message}) from exc


class StaffComplaintImportResponseSerializer(serializers.ModelSerializer):
    message = serializers.SerializerMethodField()

    class Meta:
        model = Complaint
        fields = ("id", "reference", "title", "source", "registered_on_paper_at", "message")

    def get_message(self, obj) -> str:
        return f"Dossier papier enregistré sous la référence {obj.reference}."
