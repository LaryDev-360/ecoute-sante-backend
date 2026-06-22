from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import UserRole
from apps.common.tests.base import BaseAPITestCase
from apps.facilities.models import Facility, FacilityService, UserFacilityAssignment


class FacilityAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="admin", role=UserRole.ADMIN)
        self.manager = self.create_user(username="manager", role=UserRole.HOSPITAL_MANAGER)
        self.other_manager = self.create_user(
            username="other.manager",
            role=UserRole.HOSPITAL_MANAGER,
        )
        self.facility_a = self.create_facility(code="CNHU-HKM", name="CNHU Cotonou")
        self.facility_b = self.create_facility(code="HZ-PARAKOU", name="HZ Parakou")
        self.assign_facility(self.manager, self.facility_a)

    def test_list_facilities_admin_sees_all(self):
        self.auth_as(self.admin)
        response = self.client.get("/api/v1/facilities/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 2)

    def test_list_facilities_manager_sees_only_own(self):
        self.auth_as(self.manager)
        response = self.client.get("/api/v1/facilities/")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        self.assertEqual(data["results"][0]["code"], "CNHU-HKM")

    def test_retrieve_other_facility_returns_404_for_manager(self):
        self.auth_as(self.manager)
        response = self.client.get(f"/api/v1/facilities/{self.facility_b.id}/")
        self.assertEqual(response.status_code, 404)

    def test_admin_can_create_facility_with_services(self):
        self.auth_as(self.admin)
        response = self.client.post(
            "/api/v1/facilities/",
            {
                "name": "HZ Lokossa",
                "code": "HZ-LOKOSSA",
                "facility_type": "HOSPITAL",
                "region": "Mono",
                "city": "Lokossa",
                "address": "Centre-ville",
                "services": [{"name": "Accueil"}, {"name": "Urgences"}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        facility = Facility.objects.get(code="HZ-LOKOSSA")
        self.assertEqual(facility.services.count(), 2)

    def test_unassigned_manager_create_auto_assigns_facility(self):
        self.auth_as(self.other_manager)
        response = self.client.post(
            "/api/v1/facilities/",
            {
                "name": "CS Bohicon",
                "code": "CS-BOHICON",
                "facility_type": "HEALTH_CENTER",
                "region": "Zou",
                "city": "Bohicon",
                "address": "Marché",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        assignment = UserFacilityAssignment.objects.get(user=self.other_manager)
        self.assertEqual(assignment.facility.code, "CS-BOHICON")

    def test_assigned_manager_cannot_create_second_facility(self):
        self.auth_as(self.manager)
        response = self.client.post(
            "/api/v1/facilities/",
            {
                "name": "Autre",
                "code": "AUTRE",
                "facility_type": "HOSPITAL",
                "region": "Littoral",
                "city": "Cotonou",
                "address": "X",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_manager_can_update_own_facility(self):
        self.auth_as(self.manager)
        response = self.client.patch(
            f"/api/v1/facilities/{self.facility_a.id}/",
            {"address": "Nouvelle adresse"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.facility_a.refresh_from_db()
        self.assertEqual(self.facility_a.address, "Nouvelle adresse")

    def test_manager_cannot_deactivate_facility(self):
        self.auth_as(self.manager)
        response = self.client.delete(f"/api/v1/facilities/{self.facility_a.id}/")
        self.assertEqual(response.status_code, 403)

    def test_admin_soft_deletes_facility(self):
        self.auth_as(self.admin)
        response = self.client.delete(f"/api/v1/facilities/{self.facility_a.id}/")

        self.assertEqual(response.status_code, 204)
        self.facility_a.refresh_from_db()
        self.assertFalse(self.facility_a.active)

    def test_admin_json_import(self):
        self.auth_as(self.admin)
        response = self.client.post(
            "/api/v1/facilities/import/",
            {
                "facilities": [
                    {
                        "name": "HZ Natitingou",
                        "code": "HZ-NATI",
                        "facility_type": "HOSPITAL",
                        "region": "Atacora",
                        "city": "Natitingou",
                        "address": "Centre",
                        "services": ["Urgences"],
                    }
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["created"], 1)
        self.assertTrue(Facility.objects.filter(code="HZ-NATI").exists())

    def test_admin_csv_import(self):
        self.auth_as(self.admin)
        csv_content = (
            "code,name,facility_type,region,city,address,services\n"
            "CSV-API,HZ CSV,HOSPITAL,Littoral,Cotonou,Rue,Urgences|Accueil\n"
        )
        upload = SimpleUploadedFile("facilities.csv", csv_content.encode("utf-8"))

        response = self.client.post(
            "/api/v1/facilities/import/csv/",
            {"file": upload},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        facility = Facility.objects.get(code="CSV-API")
        self.assertEqual(facility.services.count(), 2)


class FacilityServiceAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="admin", role=UserRole.ADMIN)
        self.manager = self.create_user(username="manager", role=UserRole.HOSPITAL_MANAGER)
        self.facility = self.create_facility(code="FAC-SVC")
        self.assign_facility(self.manager, self.facility)

    def test_manager_can_add_service_to_own_facility(self):
        self.auth_as(self.manager)
        response = self.client.post(
            f"/api/v1/facilities/{self.facility.id}/services/",
            {"name": "Imagerie médicale"},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            FacilityService.objects.filter(
                facility=self.facility,
                name="Imagerie médicale",
            ).exists()
        )

    def test_manager_cannot_add_service_to_other_facility(self):
        other = self.create_facility(code="OTHER-FAC")
        self.auth_as(self.manager)

        response = self.client.post(
            f"/api/v1/facilities/{other.id}/services/",
            {"name": "Test"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)


class AssignmentAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="admin", role=UserRole.ADMIN)
        self.manager = self.create_user(username="manager", role=UserRole.HOSPITAL_MANAGER)
        self.facility = self.create_facility(code="FAC-ASSIGN")

    def test_admin_can_create_assignment(self):
        self.auth_as(self.admin)
        response = self.client.post(
            "/api/v1/assignments/",
            {"user": self.manager.id, "facility": self.facility.id},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            UserFacilityAssignment.objects.filter(
                user=self.manager,
                facility=self.facility,
            ).exists()
        )

    def test_manager_cannot_create_assignment(self):
        self.auth_as(self.manager)
        response = self.client.post(
            "/api/v1/assignments/",
            {"user": self.manager.id, "facility": self.facility.id},
            format="json",
        )
        self.assertEqual(response.status_code, 403)
