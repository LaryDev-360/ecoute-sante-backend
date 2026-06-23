from apps.accounts.models import UserRole
from apps.audit.models import AuditAction, AuditLog
from apps.common.tests.base import BaseAPITestCase
from apps.facilities.models import FacilityService


class StaffUserAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.facility_a = self.create_facility(code="HZ-USER-A")
        self.facility_b = self.create_facility(code="HZ-USER-B")
        FacilityService.objects.create(facility=self.facility_a, name="Accueil")

        self.ministry = self.create_user(
            username="ministry.users",
            role=UserRole.MINISTRY_SUPERVISOR,
        )
        self.manager_a = self.create_user(
            username="manager.user.a",
            role=UserRole.HOSPITAL_MANAGER,
        )
        self.manager_b = self.create_user(
            username="manager.user.b",
            role=UserRole.HOSPITAL_MANAGER,
        )
        self.assign_facility(self.manager_a, self.facility_a)
        self.assign_facility(self.manager_b, self.facility_b)

    def test_ministry_creates_manager_with_facility(self):
        self.auth_as(self.ministry)
        response = self.client.post(
            "/api/v1/ministry/users/",
            {
                "username": "new.manager",
                "email": "new.manager@test.bj",
                "role": UserRole.HOSPITAL_MANAGER,
                "facility_id": self.facility_b.pk,
                "first_name": "Nouveau",
                "last_name": "Manager",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("initial_password", data)
        self.assertEqual(data["user"]["username"], "new.manager")
        self.assertEqual(data["user"]["facility"]["code"], "HZ-USER-B")
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.USER_CREATED,
                resource_id=str(data["user"]["id"]),
            ).exists()
        )

    def test_manager_creates_agent(self):
        self.auth_as(self.manager_a)
        response = self.client.post(
            "/api/v1/hospital/users/",
            {
                "username": "agent.new",
                "email": "agent.new@test.bj",
                "first_name": "Agent",
                "last_name": "Test",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user"]["role"], UserRole.FACILITY_AGENT)

    def test_manager_cannot_list_other_facility_via_hospital_api(self):
        self.auth_as(self.manager_a)
        agent_b = self.create_user(username="agent.b.only", role=UserRole.FACILITY_AGENT)
        self.assign_facility(agent_b, self.facility_b)

        response = self.client.get("/api/v1/hospital/users/")
        self.assertEqual(response.status_code, 200)
        usernames = [u["username"] for u in response.json()["results"]]
        self.assertNotIn("agent.b.only", usernames)

    def test_register_requires_ministry(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "public.try",
                "email": "public@test.bj",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_ministry_deactivates_user(self):
        agent = self.create_user(username="agent.off", role=UserRole.FACILITY_AGENT)
        self.assign_facility(agent, self.facility_a)

        self.auth_as(self.ministry)
        response = self.client.patch(
            f"/api/v1/ministry/users/{agent.pk}/",
            {"is_active": False},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        agent.refresh_from_db()
        self.assertFalse(agent.is_active)
        self.assertTrue(
            AuditLog.objects.filter(
                action=AuditAction.USER_DEACTIVATED,
                resource_id=str(agent.pk),
            ).exists()
        )
