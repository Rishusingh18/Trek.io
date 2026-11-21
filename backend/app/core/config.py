"""
Application configuration loaded from environment variables and .env file.
Adheres to NFR-13 (dynamic config defaults).
"""
import os
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_env_file = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))
if not os.path.exists(_env_file):
    _env_file = ".env"


class Settings(BaseSettings):
    PROJECT_NAME: str = "Trek.io Academic Management Portal"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/v1"

    # Database: SQLite default for zero-config local run, or PostgreSQL
    DATABASE_URL: str = "sqlite:///trek.db"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security - Deployment-provided private key required, no published fallback
    SECRET_KEY: str = ""
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    @field_validator("SECRET_KEY")
    @classmethod
    def validate_secret_key(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError(
                "SECRET_KEY must be provided via deployment environment or .env and cannot be empty."
            )
        return v

    # SRS Section 7.3 Default Parameters (can be overridden by DB config)
    DEFAULT_WEIGHT_GAP: float = 0.4
    DEFAULT_WEIGHT_FIT: float = 0.3
    DEFAULT_WEIGHT_READY: float = 0.2
    DEFAULT_WEIGHT_ENG: float = 0.1
    DEFAULT_STRETCH: float = 0.10
    DEFAULT_ETA_LEARNING_RATE: float = 0.10
    DEFAULT_BETA_SENSITIVITY: float = 4.0
    DEFAULT_LAMBDA_DECAY: float = 0.01

    model_config = SettingsConfigDict(
        env_file=_env_file,
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
