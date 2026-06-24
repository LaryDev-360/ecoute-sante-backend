from apps.common.tests.base import BaseAPITestCase
from apps.accounts.models import UserRole
from apps.audit.models import AuditAction, AuditLog
from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintType,
    SubmissionType,
    SubmitterProfile,
)
from apps.facilities.models import FacilityService


class AuditLogAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.facility_a = self.create_facility(code="HZ-AUDIT-A")
        self.facility_b = self.create_facility(code="HZ-AUDIT-B")
        self.service_a = FacilityService.objects.create(facility=self.facility_a, name="Urgences")
        self.category = ComplaintCategory.objects.create(name="Audit cat")

        self.manager_a = self.create_user(username="manager.audit.a", role=UserRole.HOSPITAL_MANAGER)
        self.manager_b = self.create_user(username="manager.audit.b", role=UserRole.HOSPITAL_MANAGER)
        self.assign_facility(self.manager_a, self.facility_a)
        self.assign_facility(self.manager_b, self.facility_b)

        self.ministry = self.create_user(username="ministry.audit", role=UserRole.MINISTRY_SUPERVISOR)

        self.complaint_a = Complaint.objects.create(
            submitter_profile=SubmitterProfile.CITIZEN,
            submission_type=SubmissionType.IDENTIFIED,
            complaint_type=ComplaintType.COMPLAINT,
            facility=self.facility_a,
            service=self.service_a,
            category=self.category,
            title="Plainte audit A",
            description="Desc",
            severity="HIGH",
            phone="+22997000001",
        )

    def test_status_change_creates_audit_log(self):
        self.auth_as(self.manager_a)
        response = self.client.patch(
            f"/api/v1/hospital/complaints/{self.complaint_a.pk}/status/",
            {"status": ComplaintStatus.IN_PROGRESS, "reason": "Prise en charge"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.COMPLAINT_STATUS_CHANGED,
                resource_id=str(self.complaint_a.pk),
                actor=self.manager_a,
            ).exists()
        )

    def test_hospital_audit_logs_scoped_to_facility(self):
        self.auth_as(self.manager_a)
        self.client.patch(
            f"/api/v1/hospital/complaints/{self.complaint_a.pk}/status/",
            {"status": ComplaintStatus.IN_PROGRESS},
            format="json",
        )

        response = self.client.get("/api/v1/hospital/audit-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)

        self.auth_as(self.manager_b)
        response_b = self.client.get("/api/v1/hospital/audit-logs/")
        self.assertEqual(response_b.status_code, 200)
        self.assertEqual(response_b.data["count"], 0)

    def test_ministry_sees_national_audit_logs(self):
        self.auth_as(self.manager_a)
        self.client.patch(
            f"/api/v1/hospital/complaints/{self.complaint_a.pk}/status/",
            {"status": ComplaintStatus.IN_PROGRESS},
            format="json",
        )

        self.auth_as(self.ministry)
        response = self.client.get("/api/v1/ministry/audit-logs/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data["count"], 1)

    def test_comment_creates_audit_log(self):
        self.auth_as(self.manager_a)
        response = self.client.post(
            f"/api/v1/hospital/complaints/{self.complaint_a.pk}/comments/",
            {"comment": "Note interne de suivi"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.COMPLAINT_COMMENT_ADDED,
                resource_id=str(self.complaint_a.pk),
            ).exists()
        )

    def test_complaint_submit_creates_audit_log(self):
        response = self.client.post(
            "/api/v1/complaints/",
            {
                "submitter_profile": SubmitterProfile.CITIZEN,
                "submission_type": SubmissionType.IDENTIFIED,
                "complaint_type": ComplaintType.COMPLAINT,
                "facility": self.facility_a.pk,
                "service": self.service_a.pk,
                "category": self.category.pk,
                "title": "Nouvelle plainte",
                "description": "Description test audit",
                "severity": "MEDIUM",
                "phone": "+22997000002",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        complaint_id = response.data["id"]
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.COMPLAINT_CREATED,
                resource_id=str(complaint_id),
                actor__isnull=True,
            ).exists()
        )
