from rest_framework import serializers

from apps.accounts.models import User, UserRole
from apps.facilities.models import Facility, FacilityService, FacilityType, UserFacilityAssignment


class FacilityServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityService
        fields = ("id", "name", "active")


class FacilityServiceWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacilityService
        fields = ("name", "active")


class FacilityListSerializer(serializers.ModelSerializer):
    services_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Facility
        fields = (
            "id",
            "name",
            "code",
            "facility_type",
            "region",
            "city",
            "address",
            "active",
            "services_count",
            "created_at",
        )


class FacilityWriteSerializer(serializers.ModelSerializer):
    services = FacilityServiceWriteSerializer(many=True, required=False)

    class Meta:
        model = Facility
        fields = (
            "name",
            "code",
            "facility_type",
            "region",
            "city",
            "address",
            "active",
            "services",
        )

    def validate_code(self, value):
        value = value.strip().upper()
        qs = Facility.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ce code établissement existe déjà.")
        return value

    def validate_facility_type(self, value):
        if value not in FacilityType.values:
            raise serializers.ValidationError("Type d'établissement invalide.")
        return value

    def create(self, validated_data):
        services_data = validated_data.pop("services", [])
        facility = Facility.objects.create(**validated_data)
        for service in services_data:
            FacilityService.objects.create(facility=facility, **service)
        return facility

    def update(self, instance, validated_data):
        services_data = validated_data.pop("services", None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if services_data is not None:
            for service in services_data:
                FacilityService.objects.update_or_create(
                    facility=instance,
                    name=service["name"],
                    defaults={"active": service.get("active", True)},
                )
        return instance


class FacilityDetailSerializer(serializers.ModelSerializer):
    services = FacilityServiceSerializer(many=True, read_only=True)

    class Meta:
        model = Facility
        fields = (
            "id",
            "name",
            "code",
            "facility_type",
            "region",
            "city",
            "address",
            "active",
            "services",
            "created_at",
        )


class FacilityImportItemSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=255)
    code = serializers.CharField(max_length=50)
    facility_type = serializers.ChoiceField(choices=FacilityType.choices)
    region = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    address = serializers.CharField()
    active = serializers.BooleanField(default=True)
    services = serializers.ListField(
        child=serializers.CharField(max_length=150),
        required=False,
    )


class FacilityImportSerializer(serializers.Serializer):
    facilities = FacilityImportItemSerializer(many=True, min_length=1)


class UserFacilityAssignmentSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source="user.id", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    facility_code = serializers.CharField(source="facility.code", read_only=True)
    facility_name = serializers.CharField(source="facility.name", read_only=True)

    class Meta:
        model = UserFacilityAssignment
        fields = (
            "id",
            "user",
            "user_id",
            "username",
            "facility",
            "facility_code",
            "facility_name",
            "assigned_at",
        )
        read_only_fields = ("assigned_at",)

    def validate_user(self, user):
        if user.role not in (UserRole.HOSPITAL_MANAGER, UserRole.FACILITY_AGENT):
            raise serializers.ValidationError(
                "Seuls les responsables ou agents d'établissement peuvent être affectés."
            )
        return user
