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


class MinistryAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.ministry = self.create_user(username="ministry", role=UserRole.MINISTRY_SUPERVISOR)
        self.manager = self.create_user(username="mgr", role=UserRole.HOSPITAL_MANAGER)

        self.facility_littoral = self.create_facility(
            code="CNHU-BJ",
            name="CNHU Cotonou",
            region="Littoral",
            city="Cotonou",
        )
        self.facility_borgou = self.create_facility(
            code="HZ-PKO",
            name="HZ Parakou",
            region="Borgou",
            city="Parakou",
        )
        self.service_a = FacilityService.objects.create(
            facility=self.facility_littoral,
            name="Urgences",
        )
        self.service_b = FacilityService.objects.create(
            facility=self.facility_borgou,
            name="Accueil",
        )
        self.category = ComplaintCategory.objects.create(name="Temps d'attente")

        self.complaint_a = Complaint.objects.create(
            submitter_profile=SubmitterProfile.CITIZEN,
            submission_type=SubmissionType.IDENTIFIED,
            complaint_type=ComplaintType.COMPLAINT,
            facility=self.facility_littoral,
            service=self.service_a,
            category=self.category,
            title="Plainte Littoral",
            description="Desc",
            severity="HIGH",
        )
        self.complaint_b = Complaint.objects.create(
            submitter_profile=SubmitterProfile.CITIZEN,
            submission_type=SubmissionType.ANONYMOUS,
            complaint_type=ComplaintType.COMPLAINT,
            facility=self.facility_borgou,
            service=self.service_b,
            category=self.category,
            title="Plainte Borgou",
            description="Desc",
            severity="MEDIUM",
        )
        change_complaint_status(
            self.complaint_a,
            ComplaintStatus.RESOLVED,
            changed_by=self.ministry,
        )
        change_complaint_status(
            self.complaint_b,
            ComplaintStatus.REJECTED,
            changed_by=self.ministry,
            reason="Hors scope",
        )

    def test_ministry_dashboard(self):
        self.auth_as(self.ministry)
        response = self.client.get("/api/v1/ministry/dashboard/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["total"], 2)
        self.assertEqual(data["summary"]["resolved"], 1)
        self.assertEqual(data["summary"]["rejected"], 1)
        self.assertIn("resolution_rate", data["summary"])
        self.assertIn("by_region", data)
        self.assertIn("monthly_trend", data)

    def test_ministry_analytics(self):
        self.auth_as(self.ministry)
        response = self.client.get("/api/v1/ministry/analytics/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("by_status", data)
        self.assertIn("by_category", data)
        self.assertIn("region_by_status", data)

    def test_ministry_lists_all_complaints(self):
        self.auth_as(self.ministry)
        response = self.client.get("/api/v1/ministry/complaints/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

    def test_ministry_filter_by_region(self):
        self.auth_as(self.ministry)
        response = self.client.get("/api/v1/ministry/complaints/?region=Borgou")

        self.assertEqual(response.json()["count"], 1)
        self.assertEqual(
            response.json()["results"][0]["reference"],
            self.complaint_b.reference,
        )

    def test_ministry_csv_export(self):
        self.auth_as(self.ministry)
        response = self.client.get("/api/v1/ministry/complaints/export/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        content = response.content.decode("utf-8")
        self.assertIn("reference", content)
        self.assertIn(self.complaint_a.reference, content)

    def test_ministry_list_export_query_param(self):
        self.auth_as(self.ministry)
        response = self.client.get("/api/v1/ministry/complaints/?export=csv")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")

    def test_ministry_complaint_pdf_export(self):
        self.auth_as(self.ministry)
        response = self.client.get(
            f"/api/v1/ministry/complaints/{self.complaint_a.id}/export/"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_hospital_manager_denied_ministry_dashboard(self):
        self.auth_as(self.manager)
        response = self.client.get("/api/v1/ministry/dashboard/")
        self.assertEqual(response.status_code, 403)

    def test_admin_can_access_ministry_dashboard(self):
        admin = self.create_user(username="admin2", role=UserRole.ADMIN)
        self.auth_as(admin)
        response = self.client.get("/api/v1/ministry/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_ministry_cannot_delete_complaint(self):
        """Read-only API — no DELETE endpoint exposed."""
        self.auth_as(self.ministry)
        response = self.client.delete(f"/api/v1/ministry/complaints/{self.complaint_a.id}/")
        self.assertIn(response.status_code, (403, 405))
        self.assertTrue(Complaint.objects.filter(pk=self.complaint_a.pk).exists())
