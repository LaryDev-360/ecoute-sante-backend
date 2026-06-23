from django.core import mail
from django.test import TestCase

from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintType,
    PreferredContactMethod,
    Severity,
    SubmissionType,
)
from apps.complaints.notifications import can_notify_complainant, notify_complainant_status_change
from apps.complaints.services import record_status_change
from apps.facilities.models import Facility, FacilityService, FacilityType


class ComplaintNotificationTests(TestCase):
    def setUp(self):
        self.facility = Facility.objects.create(
            name="CNHU Test",
            code="CNHU-NOTIF",
            facility_type=FacilityType.HOSPITAL,
            region="Littoral",
            city="Cotonou",
            address="Test",
        )
        self.service = FacilityService.objects.create(facility=self.facility, name="Accueil")
        self.category = ComplaintCategory.objects.create(name="Accueil")

    def _create_complaint(self, **overrides):
        data = {
            "submission_type": SubmissionType.IDENTIFIED,
            "complaint_type": ComplaintType.COMPLAINT,
            "facility": self.facility,
            "service": self.service,
            "category": self.category,
            "title": "Plainte test notification",
            "description": "Description",
            "severity": Severity.MEDIUM,
            "email": "citoyen@test.bj",
            "phone": "+22997000001",
        }
        data.update(overrides)
        return Complaint.objects.create(**data)

    def test_can_notify_identified_complainant_with_email(self):
        complaint = self._create_complaint()
        self.assertTrue(can_notify_complainant(complaint))

    def test_cannot_notify_anonymous_complainant(self):
        complaint = self._create_complaint(
            submission_type=SubmissionType.ANONYMOUS,
            email="",
            phone="",
        )
        self.assertFalse(can_notify_complainant(complaint))

    def test_status_change_sends_email(self):
        mail.outbox.clear()
        complaint = self._create_complaint()

        record_status_change(
            complaint,
            ComplaintStatus.IN_PROGRESS,
            reason="Prise en charge démarrée",
        )

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn(complaint.reference, body)
        self.assertIn("En cours", body)
        self.assertIn("Prise en charge démarrée", body)
        self.assertIn("/suivi?ref=", body)

    def test_initial_status_does_not_notify(self):
        mail.outbox.clear()
        self._create_complaint()
        self.assertEqual(len(mail.outbox), 0)

    def test_reject_notification_includes_reason(self):
        mail.outbox.clear()
        complaint = self._create_complaint()

        record_status_change(
            complaint,
            ComplaintStatus.REJECTED,
            reason="Hors périmètre de l'établissement",
        )

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Rejetée", mail.outbox[0].body)
        self.assertIn("Hors périmètre", mail.outbox[0].body)

    def test_notify_prefers_sms_when_configured(self):
        mail.outbox.clear()
        complaint = self._create_complaint(
            preferred_contact_method=PreferredContactMethod.SMS,
        )
        sent = notify_complainant_status_change(
            complaint,
            old_status=ComplaintStatus.RECEIVED,
            new_status=ComplaintStatus.RESOLVED,
        )
        self.assertTrue(sent)
        self.assertEqual(len(mail.outbox), 0)

    def test_confidential_complainant_is_notified(self):
        mail.outbox.clear()
        complaint = self._create_complaint(submission_type=SubmissionType.CONFIDENTIAL)
        notify_complainant_status_change(
            complaint,
            old_status=ComplaintStatus.RECEIVED,
            new_status=ComplaintStatus.UNDER_REVIEW,
        )
        self.assertEqual(len(mail.outbox), 1)
