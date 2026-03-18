"""
Configuration management using Pydantic BaseSettings.

This module centralizes all configuration values and supports:
- Environment variables
- .env file loading
- Type validation
- Default values
"""

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Cloud Sync Configuration
    cloud_base_url: str = "http://localhost:8080"

    # Fuseki/Knowledge Graph Configuration (deprecated, use KG_STORE_PATH instead)
    fuseki_url: str = "http://localhost:3030/srs4autism/query"
    fuseki_host: str = "localhost"
    fuseki_port: int = 3030
    fuseki_dataset: str = "srs4autism"

    # Oxigraph Configuration
    kg_store_path: str = "./cuma_knowledge_graph"

    # Database Configuration
    database_url: Optional[str] = None

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging Configuration
    log_level: str = "INFO"

    @field_validator("cloud_base_url", mode="before")
    @classmethod
    def strip_trailing_slash(cls, v: str) -> str:
        """Ensure cloud_base_url has no trailing slash for consistent URL construction."""
        if isinstance(v, str):
            return v.rstrip("/")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file


# Global settings instance
settings = Settings()
