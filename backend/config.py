"""
Configuration management using Pydantic BaseSettings.

This module centralizes all configuration values and supports:
- Environment variables
- .env file loading
- Type validation
- Default values
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings with environment variable support."""

    # Fuseki/Knowledge Graph Configuration
    fuseki_url: str = "http://localhost:3030/srs4autism/query"
    fuseki_host: str = "localhost"
    fuseki_port: int = 3030
    fuseki_dataset: str = "srs4autism"

    # Database Configuration
    database_url: Optional[str] = None

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Logging Configuration
    log_level: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields in .env file


# Global settings instance
settings = Settings()
