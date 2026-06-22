from unittest.mock import patch

from django.core import mail

from apps.accounts.models import OTPPurpose, UserRole
from apps.accounts.services.otp import (
    OTPError,
    create_and_send_otp,
    find_user_by_identifier,
    verify_otp,
)
from apps.common.tests.base import BaseAPITestCase

FIXED_OTP = "123456"


class OTPServiceTests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user(
            username="otp.user",
            email="otp.user@test.bj",
            phone="+22962000000",
        )

    @patch("apps.accounts.services.otp._generate_otp_code", return_value=FIXED_OTP)
    def test_create_and_send_otp_stores_hashed_code(self, _mock):
        create_and_send_otp(self.user, OTPPurpose.LOGIN, self.user.email)

        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(FIXED_OTP, mail.outbox[0].body)
        self.assertEqual(self.user.otp_verifications.count(), 1)

    @patch("apps.accounts.services.otp._generate_otp_code", return_value=FIXED_OTP)
    def test_verify_otp_accepts_valid_code(self, _mock):
        create_and_send_otp(self.user, OTPPurpose.RESET_PASSWORD, self.user.email)
        otp = verify_otp(self.user, OTPPurpose.RESET_PASSWORD, FIXED_OTP)

        self.assertTrue(otp.is_used)

    @patch("apps.accounts.services.otp._generate_otp_code", return_value=FIXED_OTP)
    def test_verify_otp_rejects_invalid_code(self, _mock):
        create_and_send_otp(self.user, OTPPurpose.LOGIN, self.user.email)

        with self.assertRaises(OTPError):
            verify_otp(self.user, OTPPurpose.LOGIN, "000000")

    def test_find_user_by_identifier_supports_email_username_phone(self):
        self.assertEqual(find_user_by_identifier("otp.user@test.bj"), self.user)
        self.assertEqual(find_user_by_identifier("otp.user"), self.user)
        self.assertEqual(find_user_by_identifier("+22962000000"), self.user)


class OTPPasswordAPITests(BaseAPITestCase):
    def setUp(self):
        super().setUp()
        self.user = self.create_user(
            username="pwd.user",
            email="pwd.user@test.bj",
            password="OldPass123!",
        )

    @patch("apps.accounts.services.otp._generate_otp_code", return_value=FIXED_OTP)
    def test_forgot_password_returns_generic_message(self, _mock):
        response = self.client.post(
            "/api/v1/auth/password/forgot/",
            {"identifier": "pwd.user@test.bj"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("detail", response.json())
        self.assertEqual(len(mail.outbox), 1)

    @patch("apps.accounts.services.otp._generate_otp_code", return_value=FIXED_OTP)
    def test_reset_password_with_valid_otp(self, _mock):
        self.client.post(
            "/api/v1/auth/password/forgot/",
            {"identifier": "pwd.user@test.bj"},
            format="json",
        )

        response = self.client.post(
            "/api/v1/auth/password/reset/",
            {
                "identifier": "pwd.user@test.bj",
                "otp": FIXED_OTP,
                "new_password": "NewSecure456!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecure456!"))

    def test_change_password_requires_authentication(self):
        response = self.client.post(
            "/api/v1/auth/password/change/",
            {"old_password": "OldPass123!", "new_password": "NewSecure456!"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_change_password_with_valid_old_password(self):
        self.auth_as(self.user)

        response = self.client.post(
            "/api/v1/auth/password/change/",
            {"old_password": "OldPass123!", "new_password": "NewSecure456!"},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewSecure456!"))

    @patch("apps.accounts.services.otp._generate_otp_code", return_value=FIXED_OTP)
    def test_otp_login_returns_jwt(self, _mock):
        self.client.post(
            "/api/v1/auth/otp/request/",
            {"identifier": "pwd.user@test.bj", "purpose": OTPPurpose.LOGIN},
            format="json",
        )

        response = self.client.post(
            "/api/v1/auth/otp/verify/",
            {
                "identifier": "pwd.user@test.bj",
                "otp": FIXED_OTP,
                "purpose": OTPPurpose.LOGIN,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access", data)
        self.assertEqual(data["user"]["username"], "pwd.user")
