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
from apps.facilities.models import FacilityService


class CriticalPathIntegrationTests(BaseAPITestCase):
    """Parcours bout-en-bout : soumission publique, suivi, traitement hôpital."""

    def setUp(self):
        super().setUp()
        self.facility_a = self.create_facility(code="INT-A", name="HZ Intégration A")
        self.facility_b = self.create_facility(code="INT-B", name="HZ Intégration B")
        self.service_a = FacilityService.objects.create(
            facility=self.facility_a,
            name="Urgences",
        )
        self.service_b = FacilityService.objects.create(
            facility=self.facility_b,
            name="Accueil",
        )
        self.category = ComplaintCategory.objects.create(name="Temps d'attente")

        self.manager_a = self.create_user(username="mgr.int.a", role=UserRole.HOSPITAL_MANAGER)
        self.manager_b = self.create_user(username="mgr.int.b", role=UserRole.HOSPITAL_MANAGER)
        self.assign_facility(self.manager_a, self.facility_a)
        self.assign_facility(self.manager_b, self.facility_b)

    def _submit_payload(self, facility_id, service_id):
        return {
            "submitter_profile": SubmitterProfile.CITIZEN,
            "submission_type": SubmissionType.IDENTIFIED,
            "complaint_type": ComplaintType.COMPLAINT,
            "facility": facility_id,
            "service": service_id,
            "category": self.category.id,
            "title": "Parcours intégration",
            "description": "Test bout-en-bout soumission et suivi.",
            "severity": "HIGH",
            "phone": "+22997000099",
            "email": "integration@test.bj",
        }

    def test_citizen_submit_then_track(self):
        create = self.client.post(
            "/api/v1/complaints/",
            self._submit_payload(self.facility_a.id, self.service_a.id),
            format="json",
        )
        self.assertEqual(create.status_code, 201)
        reference = create.json()["reference"]

        track = self.client.get(f"/api/v1/complaints/track/{reference}/")
        self.assertEqual(track.status_code, 200)
        data = track.json()
        self.assertEqual(data["reference"], reference)
        self.assertEqual(data["current_status"], ComplaintStatus.RECEIVED)
        self.assertEqual(len(data["status_timeline"]), 1)

    def test_status_change_reflected_in_hospital_detail_and_public_track(self):
        create = self.client.post(
            "/api/v1/complaints/",
            self._submit_payload(self.facility_a.id, self.service_a.id),
            format="json",
        )
        reference = create.json()["reference"]
        complaint = Complaint.objects.get(reference=reference)

        self.auth_as(self.manager_a)
        status_resp = self.client.patch(
            f"/api/v1/hospital/complaints/{complaint.id}/status/",
            {"status": ComplaintStatus.IN_PROGRESS, "reason": "Prise en charge"},
            format="json",
        )
        self.assertEqual(status_resp.status_code, 200)

        detail = self.client.get(f"/api/v1/hospital/complaints/{complaint.id}/")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["current_status"], ComplaintStatus.IN_PROGRESS)
        self.assertGreaterEqual(len(detail.json()["status_history"]), 2)

        self.client.force_authenticate(user=None)
        track = self.client.get(f"/api/v1/complaints/track/{reference}/")
        self.assertEqual(track.status_code, 200)
        self.assertEqual(track.json()["current_status"], ComplaintStatus.IN_PROGRESS)
        self.assertGreaterEqual(len(track.json()["status_timeline"]), 2)

    def test_hospital_isolation_across_facilities(self):
        payload_a = self._submit_payload(self.facility_a.id, self.service_a.id)
        payload_b = self._submit_payload(self.facility_b.id, self.service_b.id)
        payload_b["title"] = "Plainte établissement B"

        ref_a = self.client.post("/api/v1/complaints/", payload_a, format="json").json()["reference"]
        ref_b = self.client.post("/api/v1/complaints/", payload_b, format="json").json()["reference"]

        complaint_b = Complaint.objects.get(reference=ref_b)

        self.auth_as(self.manager_a)
        list_resp = self.client.get("/api/v1/hospital/complaints/")
        self.assertEqual(list_resp.status_code, 200)
        references = [item["reference"] for item in list_resp.json()["results"]]
        self.assertIn(ref_a, references)
        self.assertNotIn(ref_b, references)

        detail_resp = self.client.get(f"/api/v1/hospital/complaints/{complaint_b.id}/")
        self.assertEqual(detail_resp.status_code, 404)

        self.auth_as(self.manager_b)
        list_b = self.client.get("/api/v1/hospital/complaints/")
        references_b = [item["reference"] for item in list_b.json()["results"]]
        self.assertIn(ref_b, references_b)
        self.assertNotIn(ref_a, references_b)
