class ActiveQuerySetMixin:
    """Filter queryset to active records only (soft-delete pattern)."""

    active_field = "active"

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(queryset.model, self.active_field):
            return queryset.filter(**{self.active_field: True})
        return queryset


class ArchivedQuerySetMixin:
    """Exclude archived records."""

    archived_field = "is_archived"

    def get_queryset(self):
        queryset = super().get_queryset()
        if hasattr(queryset.model, self.archived_field):
            return queryset.filter(**{self.archived_field: False})
        return queryset
