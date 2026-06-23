from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field

from apps.accounts.models import User, UserRole
from apps.facilities.models import Facility


class FacilityBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ("id", "name", "code")
        read_only_fields = fields


class StaffUserSerializer(serializers.ModelSerializer):
    facility = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "phone",
            "role",
            "is_active",
            "facility",
            "date_joined",
        )
        read_only_fields = fields

    @extend_schema_field(FacilityBriefSerializer)
    def get_facility(self, obj: User) -> dict | None:
        try:
            assignment = obj.facility_assignment
        except Exception:
            return None
        if assignment is None:
            return None
        return FacilityBriefSerializer(assignment.facility).data


class StaffUserCreateResponseSerializer(serializers.Serializer):
    user = StaffUserSerializer()
    initial_password = serializers.CharField()
    message = serializers.CharField()


class MinistryUserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    role = serializers.ChoiceField(
        choices=[
            (UserRole.HOSPITAL_MANAGER, UserRole.HOSPITAL_MANAGER.label),
            (UserRole.FACILITY_AGENT, UserRole.FACILITY_AGENT.label),
            (UserRole.MINISTRY_SUPERVISOR, UserRole.MINISTRY_SUPERVISOR.label),
        ]
    )
    facility_id = serializers.IntegerField(required=False, allow_null=True)
    password = serializers.CharField(min_length=8, required=False, allow_blank=True, write_only=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value

    def validate_facility_id(self, value):
        if value is None:
            return None
        try:
            return Facility.objects.get(pk=value, active=True)
        except Facility.DoesNotExist as exc:
            raise serializers.ValidationError("Établissement introuvable.") from exc


class HospitalUserCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, required=False, allow_blank=True, write_only=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")

    def validate_password(self, value):
        if value:
            validate_password(value)
        return value


class StaffUserUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    email = serializers.EmailField(required=False)
    is_active = serializers.BooleanField(required=False)
