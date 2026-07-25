from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from .config import settings


ACCOUNT_PASSWORD_ENCRYPTION_KEY_ENV = "ACCOUNT_PASSWORD_ENCRYPTION_KEY"
ACCOUNT_PASSWORD_KEY_DIRNAME = ".runtime-secrets"
ACCOUNT_PASSWORD_KEY_FILENAME = "account-password.key"
ACCOUNT_PASSWORD_CIPHERTEXT_PREFIX = "enc:v1:"


class AccountPasswordEncryptionError(RuntimeError):
    pass


def get_account_password_key_path() -> Path:
    return settings.base_dir / ACCOUNT_PASSWORD_KEY_DIRNAME / ACCOUNT_PASSWORD_KEY_FILENAME


def _load_or_create_account_password_key() -> bytes:
    env_key = os.getenv(ACCOUNT_PASSWORD_ENCRYPTION_KEY_ENV)
    if env_key:
        return env_key.strip().encode("utf-8")

    key_path = get_account_password_key_path()
    if key_path.exists():
        return key_path.read_text(encoding="utf-8").strip().encode("utf-8")

    key_path.parent.mkdir(parents=True, exist_ok=True)
    generated_key = Fernet.generate_key()
    key_path.write_text(generated_key.decode("utf-8"), encoding="utf-8")
    return generated_key


@lru_cache(maxsize=1)
def get_account_password_cipher() -> Fernet:
    raw_key = _load_or_create_account_password_key()
    try:
        return Fernet(raw_key)
    except (ValueError, TypeError) as exc:
        key_path = get_account_password_key_path()
        raise AccountPasswordEncryptionError(
            f"Invalid account password encryption key. "
            f"Set {ACCOUNT_PASSWORD_ENCRYPTION_KEY_ENV} or fix {key_path}.",
        ) from exc


def is_account_usage_secret_encrypted(value: str | None) -> bool:
    return bool(value) and value.startswith(ACCOUNT_PASSWORD_CIPHERTEXT_PREFIX)


def encrypt_account_usage_secret(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    if is_account_usage_secret_encrypted(normalized):
        return normalized

    token = get_account_password_cipher().encrypt(normalized.encode("utf-8")).decode("utf-8")
    return f"{ACCOUNT_PASSWORD_CIPHERTEXT_PREFIX}{token}"


def decrypt_account_usage_secret(value: str | None) -> str | None:
    if value is None:
        return None

    if not is_account_usage_secret_encrypted(value):
        return value

    token = value[len(ACCOUNT_PASSWORD_CIPHERTEXT_PREFIX) :]
    try:
        return get_account_password_cipher().decrypt(token.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise AccountPasswordEncryptionError("Account password ciphertext is invalid") from exc


def is_account_password_encrypted(value: str | None) -> bool:
    return is_account_usage_secret_encrypted(value)


def encrypt_account_password(value: str | None) -> str | None:
    return encrypt_account_usage_secret(value)


def decrypt_account_password(value: str | None) -> str | None:
    return decrypt_account_usage_secret(value)
