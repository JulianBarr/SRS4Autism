from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_CUMA_CLOUD_ROOT = Path(__file__).resolve().parent.parent
_CUMA_ENV_FILE = _CUMA_CLOUD_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_CUMA_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    jwt_secret: str
    environment: str = "dev"
    cloud_port: int = Field(
        default=8080,
        description="Port for the Cloud Control Plane",
    )

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if "postgresql+asyncpg://" not in v and "postgresql://" not in v:
            raise ValueError("DATABASE_URL must use postgresql+asyncpg:// scheme")
        if "postgresql://" in v and "postgresql+asyncpg://" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        if v not in ("dev", "prod"):
            raise ValueError("ENVIRONMENT must be 'dev' or 'prod'")
        return v


settings = Settings()
