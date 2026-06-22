from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.complaints.models import Complaint
from apps.complaints.services import record_initial_status


@receiver(post_save, sender=Complaint)
def create_initial_complaint_status_history(sender, instance, created, **kwargs):
    if created:
        record_initial_status(instance)
