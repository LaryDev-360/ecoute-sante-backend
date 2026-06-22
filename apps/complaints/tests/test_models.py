from datetime import date

from django.test import TestCase
from django.utils import timezone

from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintType,
    Severity,
    SubmissionType,
)
from apps.complaints.services import generate_reference, record_status_change
from apps.facilities.models import Facility, FacilityService, FacilityType


class GenerateReferenceTests(TestCase):
    def test_reference_format(self):
        reference = generate_reference(year=2026)
        self.assertEqual(reference, "SE-2026-000001")

    def test_reference_is_sequential(self):
        first = generate_reference(year=2026)
        self._create_complaint(first)
        second = generate_reference(year=2026)
        self.assertEqual(second, "SE-2026-000002")

    def test_reference_sequence_resets_per_year(self):
        self._create_complaint("SE-2025-000099")
        reference = generate_reference(year=2026)
        self.assertEqual(reference, "SE-2026-000001")

    def test_reference_uniqueness_on_complaint_save(self):
        complaint = self._build_complaint()
        complaint.save()
        self.assertTrue(complaint.reference.startswith(f"SE-{timezone.now().year}-"))

        complaint2 = self._build_complaint(title="Autre plainte")
        complaint2.save()
        self.assertNotEqual(complaint.reference, complaint2.reference)

    def _create_complaint(self, reference: str):
        complaint = self._build_complaint()
        complaint.reference = reference
        complaint.save()
        return complaint

    def _build_complaint(self, title="Test"):
        facility = Facility.objects.create(
            name="HZ Test",
            code=f"FAC-{Facility.objects.count() + 1}",
            facility_type=FacilityType.HOSPITAL,
            region="Littoral",
            city="Cotonou",
            address="Test",
        )
        service = FacilityService.objects.create(facility=facility, name="Urgences")
        category = ComplaintCategory.objects.create(name=f"Cat-{ComplaintCategory.objects.count() + 1}")
        return Complaint(
            submission_type=SubmissionType.IDENTIFIED,
            complaint_type=ComplaintType.COMPLAINT,
            facility=facility,
            service=service,
            category=category,
            title=title,
            description="Description test",
            severity=Severity.MEDIUM,
            incident_date=date.today(),
        )


class ComplaintStatusHistoryTests(TestCase):
    def setUp(self):
        facility = Facility.objects.create(
            name="CNHU Test",
            code="CNHU-TEST",
            facility_type=FacilityType.HOSPITAL,
            region="Littoral",
            city="Cotonou",
            address="Test",
        )
        service = FacilityService.objects.create(facility=facility, name="Consultation")
        category = ComplaintCategory.objects.create(name="Temps d'attente")

        self.complaint = Complaint.objects.create(
            submission_type=SubmissionType.ANONYMOUS,
            complaint_type=ComplaintType.COMPLAINT,
            facility=facility,
            service=service,
            category=category,
            title="Longue attente",
            description="Attente de plus de 2 heures.",
            severity=Severity.HIGH,
        )

    def test_initial_status_history_created_on_complaint_creation(self):
        history = ComplaintStatusHistory.objects.filter(complaint=self.complaint)
        self.assertEqual(history.count(), 1)

        entry = history.first()
        self.assertEqual(entry.old_status, "")
        self.assertEqual(entry.new_status, ComplaintStatus.RECEIVED)
        self.assertEqual(entry.reason, "Plainte enregistrée")

    def test_record_status_change_updates_complaint_and_history(self):
        record_status_change(
            self.complaint,
            ComplaintStatus.IN_PROGRESS,
            reason="Prise en charge démarrée",
        )

        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.current_status, ComplaintStatus.IN_PROGRESS)
        self.assertEqual(self.complaint.status_history.count(), 2)

        latest = self.complaint.status_history.order_by("-created_at").first()
        self.assertEqual(latest.old_status, ComplaintStatus.RECEIVED)
        self.assertEqual(latest.new_status, ComplaintStatus.IN_PROGRESS)
