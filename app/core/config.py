from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_path(project_root: Path, value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Black Tonny Backend"
    app_env: str = "development"
    app_timezone: str = "Asia/Shanghai"
    capture_db_url: str | None = None
    serving_db_url: str | None = None
    analysis_db_url: str | None = None
    app_db_url: str | None = None
    admin_api_token: str = Field(default="change-me", min_length=1)
    frontend_auth_secret: str = Field(
        default="black-tonny-frontend-auth-secret",
        min_length=1,
    )
    frontend_auth_access_token_ttl_seconds: int = Field(
        default=604800,
        ge=300,
    )
    owner_login_username: str = Field(default="owner", min_length=1)
    owner_login_password: str = Field(default="123456", min_length=1)
    owner_login_real_name: str = Field(default="老板", min_length=1)
    owner_login_avatar_url: str = "https://avatar.vercel.sh/black-tonny.svg?text=BT"
    owner_login_home_path: str = Field(default="/dashboard", min_length=1)
    payload_cache_dir: str = "data/cache"
    sample_data_dir: str = "data/sample"
    rebuild_cron: str = "30 7 * * *"

    @property
    def project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]

    @property
    def payload_cache_path(self) -> Path:
        return _resolve_path(self.project_root, self.payload_cache_dir)

    @property
    def sample_data_path(self) -> Path:
        return _resolve_path(self.project_root, self.sample_data_dir)

    @property
    def capture_database_url(self) -> str:
        return self.capture_db_url or self.analysis_db_url or (
            "mysql+pymysql://black_tonny:change_me@127.0.0.1:3306/black_tonny_capture?charset=utf8mb4"
        )

    @property
    def serving_database_url(self) -> str:
        return self.serving_db_url or self.app_db_url or (
            "mysql+pymysql://black_tonny:change_me@127.0.0.1:3306/black_tonny_serving?charset=utf8mb4"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
