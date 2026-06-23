from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import UserRole
from apps.common.tests.base import BaseAPITestCase
from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintType,
    SubmissionType,
    SubmitterProfile,
)
from apps.complaints.services import change_complaint_status
from apps.facilities.models import FacilityService


class HospitalComplaintAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.facility_a = self.create_facility(code="HZ-A")
        self.facility_b = self.create_facility(code="HZ-B")
        self.service_a = FacilityService.objects.create(facility=self.facility_a, name="Urgences")
        self.service_b = FacilityService.objects.create(facility=self.facility_b, name="Accueil")
        self.category = ComplaintCategory.objects.create(name="Temps d'attente")

        self.manager = self.create_user(username="manager.h", role=UserRole.HOSPITAL_MANAGER)
        self.assign_facility(self.manager, self.facility_a)

        self.other_manager = self.create_user(
            username="manager.other",
            role=UserRole.HOSPITAL_MANAGER,
        )
        self.assign_facility(self.other_manager, self.facility_b)

        self.complaint_a = Complaint.objects.create(
            submitter_profile=SubmitterProfile.CITIZEN,
            submission_type=SubmissionType.IDENTIFIED,
            complaint_type=ComplaintType.COMPLAINT,
            facility=self.facility_a,
            service=self.service_a,
            category=self.category,
            title="Plainte A",
            description="Desc A",
            severity="HIGH",
            phone="+22997000001",
        )
        self.complaint_b = Complaint.objects.create(
            submitter_profile=SubmitterProfile.CITIZEN,
            submission_type=SubmissionType.ANONYMOUS,
            complaint_type=ComplaintType.COMPLAINT,
            facility=self.facility_b,
            service=self.service_b,
            category=self.category,
            title="Plainte B",
            description="Desc B",
            severity="MEDIUM",
        )

    def test_manager_lists_only_own_facility_complaints(self):
        self.auth_as(self.manager)
        response = self.client.get("/api/v1/hospital/complaints/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(response.json()["results"][0]["reference"], self.complaint_a.reference)

    def test_manager_cannot_retrieve_other_facility_complaint(self):
        self.auth_as(self.manager)
        response = self.client.get(f"/api/v1/hospital/complaints/{self.complaint_b.id}/")
        self.assertEqual(response.status_code, 404)

    def test_unassigned_manager_gets_403(self):
        unassigned = self.create_user(username="unassigned", role=UserRole.HOSPITAL_MANAGER)
        self.auth_as(unassigned)
        response = self.client.get("/api/v1/hospital/complaints/")
        self.assertEqual(response.status_code, 403)

    def test_update_status_creates_history(self):
        self.auth_as(self.manager)
        response = self.client.patch(
            f"/api/v1/hospital/complaints/{self.complaint_a.id}/status/",
            {"status": ComplaintStatus.IN_PROGRESS, "reason": "Prise en charge"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.complaint_a.refresh_from_db()
        self.assertEqual(self.complaint_a.current_status, ComplaintStatus.IN_PROGRESS)
        self.assertEqual(self.complaint_a.status_history.count(), 2)

    def test_reject_complaint_with_reason(self):
        self.auth_as(self.manager)
        response = self.client.patch(
            f"/api/v1/hospital/complaints/{self.complaint_a.id}/reject/",
            {"reason": "Hors périmètre"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.complaint_a.refresh_from_db()
        self.assertEqual(self.complaint_a.current_status, ComplaintStatus.REJECTED)
        latest = self.complaint_a.status_history.order_by("-created_at").first()
        self.assertEqual(latest.reason, "Hors périmètre")

    def test_rejected_complaint_still_listed_and_in_dashboard(self):
        change_complaint_status(
            self.complaint_a,
            ComplaintStatus.REJECTED,
            changed_by=self.manager,
            reason="Test rejet",
        )
        self.auth_as(self.manager)

        list_response = self.client.get("/api/v1/hospital/complaints/")
        self.assertEqual(list_response.json()["count"], 1)

        dashboard = self.client.get("/api/v1/hospital/dashboard/").json()
        self.assertEqual(dashboard["summary"]["rejected"], 1)
        self.assertEqual(dashboard["summary"]["total"], 1)

    def test_add_internal_comment(self):
        self.auth_as(self.manager)
        response = self.client.post(
            f"/api/v1/hospital/complaints/{self.complaint_a.id}/comments/",
            {"comment": "Contacté le service concerné."},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(self.complaint_a.comments.count(), 1)

    def test_detail_includes_history_and_hides_anonymous_contact(self):
        self.auth_as(self.manager)
        response = self.client.get(f"/api/v1/hospital/complaints/{self.complaint_a.id}/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("status_history", data)
        self.assertIn("contact", data)
        self.assertIsNotNone(data["contact"])

    def test_filter_by_status(self):
        change_complaint_status(
            self.complaint_a,
            ComplaintStatus.RESOLVED,
            changed_by=self.manager,
        )
        Complaint.objects.create(
            submitter_profile=SubmitterProfile.CITIZEN,
            submission_type=SubmissionType.ANONYMOUS,
            complaint_type=ComplaintType.COMPLAINT,
            facility=self.facility_a,
            service=self.service_a,
            category=self.category,
            title="Plainte ouverte",
            description="Desc",
            severity="LOW",
        )
        self.auth_as(self.manager)
        response = self.client.get(
            f"/api/v1/hospital/complaints/?status={ComplaintStatus.RESOLVED}"
        )
        self.assertEqual(response.json()["count"], 1)

    def test_hospital_complaint_csv_export(self):
        self.auth_as(self.manager)
        response = self.client.get(
            f"/api/v1/hospital/complaints/{self.complaint_a.id}/export/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        content = response.content.decode("utf-8")
        self.assertIn(self.complaint_a.reference, content)
        self.assertIn("Description", content)
        self.assertIn("Plainte A", content)

    def test_hospital_complaint_export_denied_other_facility(self):
        self.auth_as(self.other_manager)
        response = self.client.get(
            f"/api/v1/hospital/complaints/{self.complaint_a.id}/export/"
        )
        self.assertEqual(response.status_code, 404)

    def test_dashboard_summary(self):
        change_complaint_status(
            self.complaint_a,
            ComplaintStatus.RESOLVED,
            changed_by=self.manager,
        )
        self.complaint_a.updated_at = timezone.now() + timedelta(hours=2)
        self.complaint_a.save(update_fields=["updated_at"])

        self.auth_as(self.manager)
        response = self.client.get("/api/v1/hospital/dashboard/")

        self.assertEqual(response.status_code, 200)
        summary = response.json()["summary"]
        self.assertEqual(summary["total"], 1)
        self.assertEqual(summary["resolved"], 1)
        self.assertIsNotNone(summary["avg_processing_hours"])
