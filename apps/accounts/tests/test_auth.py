from apps.accounts.models import UserRole
from apps.common.tests.base import BaseAPITestCase


class RegisterTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.ministry = self.create_user(
            username="ministry.register",
            role=UserRole.MINISTRY_SUPERVISOR,
        )

    def test_register_requires_staff_auth(self):
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "new.manager",
                "email": "new.manager@test.bj",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
            format="json",
        )
        self.assertIn(response.status_code, (401, 403))

    def test_register_creates_hospital_manager_with_tokens(self):
        self.auth_as(self.ministry)
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "new.manager",
                "email": "new.manager@test.bj",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "phone": "+22961000000",
                "first_name": "Kofi",
                "last_name": "Agbessi",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertEqual(data["user"]["role"], UserRole.HOSPITAL_MANAGER)
        self.assertEqual(data["user"]["username"], "new.manager")

    def test_register_rejects_duplicate_username(self):
        self.create_user(username="existing")
        self.auth_as(self.ministry)

        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "existing",
                "email": "other@test.bj",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("username", response.json()["error"])

    def test_register_rejects_password_mismatch(self):
        self.auth_as(self.ministry)
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "username": "mismatch",
                "email": "mismatch@test.bj",
                "password": "SecurePass123!",
                "password_confirm": "DifferentPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("password_confirm", response.json()["error"])


class LoginTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user(
            username="login.user",
            role=UserRole.ADMIN,
            password="adminpass123",
        )

    def test_login_returns_jwt_and_user(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "login.user", "password": "adminpass123"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access", data)
        self.assertIn("refresh", data)
        self.assertEqual(data["user"]["username"], "login.user")
        self.assertEqual(data["user"]["role"], UserRole.ADMIN)

    def test_login_rejects_invalid_credentials(self):
        response = self.client.post(
            "/api/v1/auth/login/",
            {"username": "login.user", "password": "wrong"},
            format="json",
        )

        self.assertEqual(response.status_code, 401)

    def test_refresh_returns_new_access_token(self):
        login = self.client.post(
            "/api/v1/auth/login/",
            {"username": "login.user", "password": "adminpass123"},
            format="json",
        ).json()

        response = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh": login["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())


class MeTests(BaseAPITestCase):
    def test_me_requires_authentication(self):
        response = self.client.get("/api/v1/auth/me/")
        self.assertEqual(response.status_code, 401)

    def test_me_returns_current_user(self):
        user = self.create_user(username="me.user", email="me@test.bj")
        self.auth_as(user)

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["username"], "me.user")
        self.assertEqual(response.json()["email"], "me@test.bj")
