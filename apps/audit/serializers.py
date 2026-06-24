from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from apps.audit.models import AuditAction, AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    actor = UserSerializer(read_only=True)
    action_label = serializers.SerializerMethodField()

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "actor",
            "action",
            "action_label",
            "resource_type",
            "resource_id",
            "resource_label",
            "summary",
            "metadata",
            "facility",
            "created_at",
        )
        read_only_fields = fields

    def get_action_label(self, obj: AuditLog) -> str:
        try:
            return AuditAction(obj.action).label
        except ValueError:
            return obj.action
