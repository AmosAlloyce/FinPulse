from __future__ import annotations

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration shared by producers, processors, and serving applications."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: str = Field(default="development", alias="FINPULSE_ENV")
    log_level: str = Field(default="INFO", alias="FINPULSE_LOG_LEVEL")
    random_seed: int = Field(default=42, alias="FINPULSE_RANDOM_SEED")
    countries: list[str] = Field(
        default_factory=lambda: ["KEN", "UGA", "GHA", "TZA", "ZMB"],
        alias="FINPULSE_COUNTRIES",
    )

    kafka_bootstrap_servers: str = "localhost:19092"
    kafka_raw_topic: str = "finpulse.events.raw.v1"
    kafka_dlq_topic: str = "finpulse.events.dlq.v1"

    aws_access_key_id: str = "finpulse"
    aws_secret_access_key: str = "finpulse-secret"
    aws_region: str = "af-south-1"
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "finpulse-lakehouse"

    warehouse_dsn: str = "postgresql://finpulse:finpulse@localhost:5432/finpulse"
    spark_checkpoint_location: str = "s3a://finpulse-lakehouse/checkpoints/credit-events-v1"
    api_url: str = "http://localhost:8000"
    demo_event_rate: float = 20.0

    @field_validator("countries", mode="before")
    @classmethod
    def split_countries(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip().upper() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
