from unittest.mock import patch

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.accounts.models import UserRole
from apps.facilities.models import Facility, FacilityType, UserFacilityAssignment

User = get_user_model()


class BaseAPITestCase(APITestCase):
    """Base API test case with throttling disabled."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._throttle_patch = patch(
            "rest_framework.throttling.SimpleRateThrottle.allow_request",
            return_value=True,
        )
        cls._throttle_patch.start()

    @classmethod
    def tearDownClass(cls):
        cls._throttle_patch.stop()
        super().tearDownClass()

    def create_user(
        self,
        role=UserRole.HOSPITAL_MANAGER,
        username="user",
        email=None,
        password="password123",
        **extra,
    ):
        email = email or f"{username}@test.bj"
        return User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            **extra,
        )

    def create_facility(self, code="FAC-001", **overrides):
        defaults = {
            "name": "HZ Test",
            "code": code,
            "facility_type": FacilityType.HOSPITAL,
            "region": "Littoral",
            "city": "Cotonou",
            "address": "Adresse test",
        }
        defaults.update(overrides)
        return Facility.objects.create(**defaults)

    def assign_facility(self, user, facility):
        return UserFacilityAssignment.objects.create(user=user, facility=facility)

    def auth_as(self, user):
        self.client.force_authenticate(user=user)
