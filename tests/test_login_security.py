from __future__ import annotations

import unittest

import pyotp

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from main import (
    build_totp_qr_data,
    decrypt_totp_secret,
    encrypt_totp_secret,
    is_login_captcha_required,
    record_login_failure,
    verify_totp_code,
)


class LoginSecurityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.session = sessionmaker(bind=self.engine)()

    def tearDown(self) -> None:
        self.session.close()
        self.engine.dispose()

    def test_captcha_is_required_after_three_failures(self) -> None:
        username = "admin"
        ip_address = "127.0.0.1"
        for _ in range(2):
            record_login_failure(self.session, username, ip_address)
        self.assertFalse(is_login_captcha_required(self.session, username, ip_address))

        record_login_failure(self.session, username, ip_address)
        self.assertTrue(is_login_captcha_required(self.session, username, ip_address))

    def test_captcha_requirement_is_scoped_to_username_and_ip(self) -> None:
        for _ in range(3):
            record_login_failure(self.session, "admin", "127.0.0.1")
        self.assertFalse(is_login_captcha_required(self.session, "other", "127.0.0.1"))
        self.assertFalse(is_login_captcha_required(self.session, "admin", "127.0.0.2"))

    def test_totp_secret_is_encrypted_and_codes_are_verified(self) -> None:
        secret = pyotp.random_base32()
        encrypted = encrypt_totp_secret(secret)
        self.assertNotIn(secret, encrypted)
        self.assertEqual(decrypt_totp_secret(encrypted), secret)
        self.assertTrue(verify_totp_code(secret, pyotp.TOTP(secret).now()))
        self.assertFalse(verify_totp_code(secret, "00000000"))

    def test_totp_qr_is_returned_as_png_data_url(self) -> None:
        image_data = build_totp_qr_data("otpauth://totp/test?secret=ABC")
        self.assertTrue(image_data.startswith("data:image/png;base64,"))


if __name__ == "__main__":
    unittest.main()
