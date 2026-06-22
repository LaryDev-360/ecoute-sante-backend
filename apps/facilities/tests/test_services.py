from apps.accounts.models import UserRole
from apps.common.tests.base import BaseAPITestCase
from apps.facilities.models import FacilityService
from apps.facilities.services import (
    deactivate_facility,
    get_facilities_queryset_for_user,
    get_user_facility,
    import_facilities_csv,
    import_facilities_payload,
)


class FacilityServiceLayerTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.admin = self.create_user(username="admin", role=UserRole.ADMIN)
        self.manager = self.create_user(username="manager", role=UserRole.HOSPITAL_MANAGER)
        self.ministry = self.create_user(username="ministry", role=UserRole.MINISTRY_SUPERVISOR)
        self.facility_a = self.create_facility(code="FAC-A", name="HZ A")
        self.facility_b = self.create_facility(code="FAC-B", name="HZ B")

    def test_get_user_facility_returns_none_for_admin(self):
        self.assertIsNone(get_user_facility(self.admin))

    def test_get_user_facility_returns_assigned_facility(self):
        self.assign_facility(self.manager, self.facility_a)
        self.assertEqual(get_user_facility(self.manager), self.facility_a)

    def test_get_facilities_queryset_scopes_manager_to_own_facility(self):
        self.assign_facility(self.manager, self.facility_a)
        qs = get_facilities_queryset_for_user(self.manager)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first(), self.facility_a)

    def test_get_facilities_queryset_returns_all_for_admin(self):
        qs = get_facilities_queryset_for_user(self.admin)
        self.assertEqual(qs.count(), 2)

    def test_deactivate_facility_sets_active_false(self):
        deactivate_facility(self.facility_a)
        self.facility_a.refresh_from_db()
        self.assertFalse(self.facility_a.active)

    def test_import_facilities_payload_creates_services(self):
        result = import_facilities_payload(
            self.admin,
            [
                {
                    "name": "CS Import",
                    "code": "CS-IMPORT",
                    "facility_type": "HEALTH_CENTER",
                    "region": "Ouémé",
                    "city": "Porto-Novo",
                    "address": "Test",
                    "services": ["Accueil", "Urgences"],
                }
            ],
        )

        self.assertEqual(result["created"], 1)
        facility = self.facility_a.__class__.objects.get(code="CS-IMPORT")
        self.assertEqual(facility.services.count(), 2)

    def test_manager_import_limited_to_one_facility(self):
        with self.assertRaises(ValueError):
            import_facilities_payload(
                self.manager,
                [
                    {
                        "name": "A",
                        "code": "A",
                        "facility_type": "HOSPITAL",
                        "region": "Littoral",
                        "city": "Cotonou",
                        "address": "A",
                    },
                    {
                        "name": "B",
                        "code": "B",
                        "facility_type": "HOSPITAL",
                        "region": "Littoral",
                        "city": "Cotonou",
                        "address": "B",
                    },
                ],
            )

    def test_csv_import_parses_pipe_separated_services(self):
        csv_content = (
            "code,name,facility_type,region,city,address,services\n"
            "CSV-001,HZ CSV,HOSPITAL,Littoral,Cotonou,Adresse,Urgences|Maternité\n"
        )
        result = import_facilities_csv(self.admin, csv_content)

        self.assertEqual(result["created"], 1)
        facility = self.facility_a.__class__.objects.get(code="CSV-001")
        service_names = set(facility.services.values_list("name", flat=True))
        self.assertEqual(service_names, {"Urgences", "Maternité"})
