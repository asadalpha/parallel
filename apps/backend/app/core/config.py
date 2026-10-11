from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../../.env", extra="ignore")

    app_name: str = "Parallel API"
    database_url: str = "postgresql+asyncpg://parallel:parallel@localhost:5432/parallel"
    cors_origins: str = "http://localhost:3000"
    environment: str = "development"

    auth_jwks_url: str | None = None
    auth_issuer: str | None = None
    auth_audience: str | None = None
    auth_jwt_algorithms: str = "EdDSA"
    auth_user_id_claim: str = "id"
    auth_role_claim: str = "role"

    ai_provider: str = "openrouter"
    ai_base_url: str | None = "https://openrouter.ai/api/v1"
    ai_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    ai_model: str | None = "google/gemma-4-26b-a4b-it:free"
    ai_timeout_seconds: float = Field(default=20.0, gt=0, le=120)

    sentry_dsn: str | None = None
    sentry_traces_sample_rate: float = Field(default=0.0, ge=0, le=1)

    elevenlabs_api_key: SecretStr | None = None
    elevenlabs_voice_id: str | None = None
    elevenlabs_model_id: str = "eleven_multilingual_v2"

    # Neon exposes its S3-compatible credentials using AWS_* names. The
    # OBJECT_STORAGE_* fields remain as a provider-neutral fallback.
    aws_endpoint_url_s3: str | None = None
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_region: str | None = None
    object_storage_endpoint: str | None = None
    object_storage_bucket: str = "parrellel-b1"
    object_storage_access_key_id: SecretStr | None = None
    object_storage_secret_access_key: SecretStr | None = None
    object_storage_region: str = "us-east-2"
    object_storage_addressing_style: str = "path"
    object_storage_public_base_url: str | None = None
    object_storage_url_ttl_seconds: int = Field(default=3600, ge=60, le=604_800)
    upload_max_bytes: int = Field(default=10_000_000, ge=1_024, le=25_000_000)

    @property
    def allowed_auth_algorithms(self) -> list[str]:
        return [value.strip() for value in self.auth_jwt_algorithms.split(",") if value.strip()]

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
