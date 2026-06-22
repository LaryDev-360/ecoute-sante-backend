from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import UserRole
from apps.common.tests.base import BaseAPITestCase
from apps.complaints.models import (
    Complaint,
    ComplaintCategory,
    ComplaintStatus,
    ComplaintStatusHistory,
    ComplaintType,
    SubmissionType,
    SubmitterProfile,
)
from apps.facilities.models import FacilityService


class PublicComplaintAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.facility = self.create_facility(code="CNHU-PUB")
        self.service = FacilityService.objects.create(
            facility=self.facility,
            name="Urgences",
        )
        self.category = ComplaintCategory.objects.create(name="Temps d'attente")

    def _payload(self, **overrides):
        data = {
            "submitter_profile": SubmitterProfile.CITIZEN,
            "submission_type": SubmissionType.IDENTIFIED,
            "complaint_type": ComplaintType.COMPLAINT,
            "facility": self.facility.id,
            "service": self.service.id,
            "category": self.category.id,
            "title": "Longue attente",
            "description": "Plus de 2 heures aux urgences.",
            "severity": "HIGH",
            "phone": "+22997000001",
            "email": "citoyen@test.bj",
        }
        data.update(overrides)
        return data

    def test_submit_complaint_creates_reference_and_history(self):
        response = self.client.post("/api/v1/complaints/", self._payload(), format="json")

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertTrue(data["reference"].startswith("SE-"))
        self.assertEqual(data["current_status"], ComplaintStatus.RECEIVED)

        complaint = Complaint.objects.get(reference=data["reference"])
        self.assertEqual(complaint.status_history.count(), 1)
        self.assertIn("Conservez cette référence", data["message"])

    def test_track_complaint_by_reference(self):
        create = self.client.post("/api/v1/complaints/", self._payload(), format="json")
        reference = create.json()["reference"]

        response = self.client.get(f"/api/v1/complaints/track/{reference}/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["reference"], reference)
        self.assertEqual(data["current_status"], ComplaintStatus.RECEIVED)
        self.assertIn("status_timeline", data)
        self.assertEqual(len(data["status_timeline"]), 1)
        self.assertNotIn("description", data)
        self.assertNotIn("phone", data)

    def test_track_unknown_reference_returns_404(self):
        response = self.client.get("/api/v1/complaints/track/SE-2099-999999/")
        self.assertEqual(response.status_code, 404)

    def test_submit_with_attachment(self):
        upload = SimpleUploadedFile(
            "preuve.jpg",
            b"fake-image-content",
            content_type="image/jpeg",
        )
        response = self.client.post(
            "/api/v1/complaints/",
            {**self._payload(), "attachments": [upload]},
            format="multipart",
        )

        self.assertEqual(response.status_code, 201)
        complaint = Complaint.objects.get(reference=response.json()["reference"])
        self.assertEqual(complaint.attachments.count(), 1)

    def test_submit_rejects_invalid_attachment_type(self):
        upload = SimpleUploadedFile(
            "virus.exe",
            b"bad",
            content_type="application/x-msdownload",
        )
        response = self.client.post(
            "/api/v1/complaints/",
            {**self._payload(), "attachments": [upload]},
            format="multipart",
        )
        self.assertEqual(response.status_code, 400)

    def test_facility_agent_submit_requires_auth(self):
        response = self.client.post(
            "/api/v1/complaints/",
            self._payload(
                submitter_profile=SubmitterProfile.FACILITY_AGENT,
                submission_type=SubmissionType.CONFIDENTIAL,
                reported_agent_name="Agent X",
            ),
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_facility_agent_submit_with_jwt(self):
        agent_a = self.create_user(username="agent.pub.a", role=UserRole.FACILITY_AGENT)
        agent_b = self.create_user(username="agent.pub.b", role=UserRole.FACILITY_AGENT)
        self.assign_facility(agent_a, self.facility)
        self.assign_facility(agent_b, self.facility)
        self.auth_as(agent_a)

        response = self.client.post(
            "/api/v1/complaints/",
            {
                **self._payload(
                    submitter_profile=SubmitterProfile.FACILITY_AGENT,
                    submission_type=SubmissionType.CONFIDENTIAL,
                    reported_agent=agent_b.id,
                ),
                "phone": "",
                "email": "",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        complaint = Complaint.objects.get(reference=response.json()["reference"])
        self.assertEqual(complaint.submitted_by, agent_a)
        self.assertEqual(complaint.reported_agent, agent_b)

    def test_list_categories_public(self):
        response = self.client.get("/api/v1/complaints/categories/")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.json()), 1)

    def test_list_submitter_profiles(self):
        response = self.client.get("/api/v1/complaints/meta/submitter-profiles/")
        self.assertEqual(response.status_code, 200)
        profiles = {p["value"] for p in response.json()}
        self.assertIn(SubmitterProfile.CITIZEN, profiles)
        self.assertIn(SubmitterProfile.FACILITY_AGENT, profiles)

    def test_track_shows_status_updates(self):
        complaint = Complaint.objects.create(
            submitter_profile=SubmitterProfile.CITIZEN,
            submission_type=SubmissionType.ANONYMOUS,
            complaint_type=ComplaintType.COMPLAINT,
            facility=self.facility,
            service=self.service,
            category=self.category,
            title="Test suivi",
            description="Desc",
            severity="MEDIUM",
            current_status=ComplaintStatus.IN_PROGRESS,
        )
        ComplaintStatusHistory.objects.create(
            complaint=complaint,
            old_status=ComplaintStatus.RECEIVED,
            new_status=ComplaintStatus.IN_PROGRESS,
            reason="Prise en charge",
        )

        response = self.client.get(f"/api/v1/complaints/track/{complaint.reference}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["status_timeline"]), 2)
