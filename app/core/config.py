from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Literal


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_SQLITE_PATH = BASE_DIR / "shop_records.db"


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: list[str]) -> list[str]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    values = [item.strip() for item in raw_value.split(",")]
    return [item for item in values if item]


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    try:
        return max(minimum, int(raw_value.strip()))
    except ValueError:
        return default


def _env_choice(name: str, default: str, allowed: set[str]) -> str:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if normalized in allowed:
        return normalized

    return default


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_env: str
    debug: bool
    base_dir: Path
    database_url: str
    sql_echo: bool
    auto_create_schema: bool
    redis_enabled: bool
    redis_url: str
    redis_prefix: str
    cors_allowed_origins: tuple[str, ...]
    session_cookie_secure: bool
    session_cookie_samesite: Literal["lax", "strict", "none"]
    trust_proxy_headers: bool
    public_registration_enabled: bool
    public_registration_role: Literal["viewer", "editor"]
    dingtalk_profit_sync_token: str
    dingtalk_robot_webhook: str
    dingtalk_robot_secret: str
    public_app_base_url: str
    auth_encryption_key: str
    server_status_node_id: str
    server_status_node_label: str
    server_status_remote_nodes: str
    server_status_push_token: str
    server_status_stale_after_seconds: int

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    database_url = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")
    app_env = os.getenv("APP_ENV", "development")

    return Settings(
        app_name=os.getenv("APP_NAME", "Shop Record API"),
        app_env=app_env,
        debug=_env_bool("APP_DEBUG", True),
        base_dir=BASE_DIR,
        database_url=database_url,
        sql_echo=_env_bool("SQL_ECHO", False),
        auto_create_schema=_env_bool("AUTO_CREATE_SCHEMA", True),
        redis_enabled=_env_bool("REDIS_ENABLED", False),
        redis_url=os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
        redis_prefix=os.getenv("REDIS_PREFIX", "shop-records"),
        cors_allowed_origins=tuple(
            _env_list(
                "CORS_ALLOWED_ORIGINS",
                [
                    "http://127.0.0.1:8000",
                    "http://localhost:8000",
                    "http://127.0.0.1:5173",
                    "http://localhost:5173",
                ],
            ),
        ),
        session_cookie_secure=_env_bool("SESSION_COOKIE_SECURE", app_env != "development"),
        session_cookie_samesite=_env_choice("SESSION_COOKIE_SAMESITE", "strict", {"lax", "strict", "none"}),  # type: ignore[arg-type]
        trust_proxy_headers=_env_bool("TRUST_PROXY_HEADERS", False),
        public_registration_enabled=_env_bool("PUBLIC_REGISTRATION_ENABLED", False),
        public_registration_role=_env_choice("PUBLIC_REGISTRATION_ROLE", "editor", {"viewer", "editor"}),  # type: ignore[arg-type]
        dingtalk_profit_sync_token=os.getenv("DINGTALK_PROFIT_SYNC_TOKEN", "").strip(),
        dingtalk_robot_webhook=os.getenv("DINGTALK_ROBOT_WEBHOOK", "").strip(),
        dingtalk_robot_secret=os.getenv("DINGTALK_ROBOT_SECRET", "").strip(),
        public_app_base_url=os.getenv("PUBLIC_APP_BASE_URL", "https://xiaoxu666.asia").strip().rstrip("/"),
        auth_encryption_key=os.getenv("AUTH_ENCRYPTION_KEY", "development-only-auth-key").strip(),
        # The machine running this process. Its id has to differ from every
        # reporting peer, so it is configurable rather than derived from hostname.
        server_status_node_id=os.getenv("SERVER_STATUS_NODE_ID", "primary").strip() or "primary",
        server_status_node_label=os.getenv("SERVER_STATUS_NODE_LABEL", "主服务器").strip() or "主服务器",
        # "id:label,id:label" -- listing a peer here is what makes it render as
        # missing before its first report ever arrives.
        server_status_remote_nodes=os.getenv("SERVER_STATUS_REMOTE_NODES", "").strip(),
        server_status_push_token=os.getenv("SERVER_STATUS_PUSH_TOKEN", "").strip(),
        server_status_stale_after_seconds=_env_int("SERVER_STATUS_STALE_AFTER_SECONDS", 180, minimum=30),
    )


settings = get_settings()
