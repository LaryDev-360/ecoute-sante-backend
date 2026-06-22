from apps.accounts.models import User, UserRole
from apps.common.tests.base import BaseAPITestCase
from apps.complaints.models import (
    ComplaintCategory,
    ComplaintType,
    SubmissionType,
    SubmitterProfile,
)
from apps.complaints.serializers import ComplaintCreateSerializer
from apps.complaints.services import ComplaintValidationError, validate_complaint_submission
from apps.facilities.models import FacilityService, FacilityType, UserFacilityAssignment


class SubmitterProfileValidationTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.facility = self.create_facility(code="CNHU-TEST")
        self.service = FacilityService.objects.create(facility=self.facility, name="Urgences")
        self.category = ComplaintCategory.objects.create(name="Mauvais accueil")

        self.agent_a = self.create_user(username="agent.a", role=UserRole.FACILITY_AGENT)
        self.agent_b = self.create_user(username="agent.b", role=UserRole.FACILITY_AGENT)
        self.assign_facility(self.agent_a, self.facility)
        self.assign_facility(self.agent_b, self.facility)

        self.base_data = {
            "submitter_profile": SubmitterProfile.CITIZEN,
            "submission_type": SubmissionType.ANONYMOUS,
            "complaint_type": ComplaintType.COMPLAINT,
            "facility": self.facility,
            "service": self.service,
            "category": self.category,
            "title": "Test",
            "description": "Description",
            "severity": "MEDIUM",
        }

    def test_citizen_cannot_target_named_agent(self):
        data = {
            **self.base_data,
            "reported_agent_name": "Jean Agent",
        }
        with self.assertRaises(ComplaintValidationError):
            validate_complaint_submission(data)

    def test_facility_agent_complaint_requires_reported_agent(self):
        data = {
            **self.base_data,
            "submitter_profile": SubmitterProfile.FACILITY_AGENT,
            "submission_type": SubmissionType.CONFIDENTIAL,
        }
        with self.assertRaises(ComplaintValidationError):
            validate_complaint_submission(data, user=self.agent_a)

    def test_facility_agent_can_complain_about_colleague(self):
        data = {
            **self.base_data,
            "submitter_profile": SubmitterProfile.FACILITY_AGENT,
            "submission_type": SubmissionType.CONFIDENTIAL,
            "reported_agent": self.agent_b,
        }
        validate_complaint_submission(data, user=self.agent_a)

    def test_facility_agent_cannot_complain_about_self(self):
        data = {
            **self.base_data,
            "submitter_profile": SubmitterProfile.FACILITY_AGENT,
            "submission_type": SubmissionType.CONFIDENTIAL,
            "reported_agent": self.agent_a,
        }
        with self.assertRaises(ComplaintValidationError):
            validate_complaint_submission(data, user=self.agent_a)

    def test_facility_agent_requires_authentication(self):
        data = {
            **self.base_data,
            "submitter_profile": SubmitterProfile.FACILITY_AGENT,
            "reported_agent_name": "Agent externe",
        }
        with self.assertRaises(ComplaintValidationError):
            validate_complaint_submission(data, user=None)

    def test_serializer_sets_submitted_by_for_facility_agent(self):
        request = type("Request", (), {"user": self.agent_a})()
        serializer = ComplaintCreateSerializer(
            data={
                "submitter_profile": SubmitterProfile.FACILITY_AGENT,
                "submission_type": SubmissionType.CONFIDENTIAL,
                "complaint_type": ComplaintType.COMPLAINT,
                "facility": self.facility.id,
                "service": self.service.id,
                "category": self.category.id,
                "reported_agent": self.agent_b.id,
                "title": "Comportement inapproprié",
                "description": "Un collègue a eu un comportement agressif.",
                "severity": "HIGH",
            },
            context={"request": request},
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        complaint = serializer.save()
        self.assertEqual(complaint.submitted_by, self.agent_a)
        self.assertEqual(complaint.reported_agent, self.agent_b)
        self.assertEqual(complaint.submitter_profile, SubmitterProfile.FACILITY_AGENT)
