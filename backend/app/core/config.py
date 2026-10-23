"""
Application configuration loaded from environment variables and .env file.
Adheres to NFR-13 (dynamic config defaults).
"""
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "Personalized Learning Path Recommender"
    ENVIRONMENT: str = "development"
    API_V1_STR: str = "/v1"

    # Database
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/learning_recommender"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Security
    SECRET_KEY: str = "change_this_to_a_super_secure_random_key_for_production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

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
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()
