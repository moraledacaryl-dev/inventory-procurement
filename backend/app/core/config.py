from functools import lru_cache
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Hidden Oasis Inventory & Procurement"
    api_v1_prefix: str = "/api/v1"
    database_url: str = "sqlite:///./inventory.db"
    jwt_secret: str = "development-secret-change-me-please"
    access_token_minutes: int = 480
    cors_origins: list[str] | str = ["http://localhost:3000"]
    bootstrap_owner_email: str = "owner@hiddenoasis.local"
    bootstrap_owner_name: str = "Owner"
    bootstrap_owner_password: str = "change-this-password-now"
    max_request_bytes: int = 10_485_760
    backup_max_age_hours: int = 48
    trusted_hosts: list[str] | str = ["localhost","127.0.0.1","testserver"]
    model_config = SettingsConfigDict(env_file="../.env", extra="ignore")

    @field_validator("cors_origins","trusted_hosts", mode="before")
    @classmethod
    def parse_lists(cls, value):
        if isinstance(value, str):
            if value.strip().startswith('['):
                import json
                return json.loads(value)
            return [part.strip() for part in value.split(",") if part.strip()]
        return value

@lru_cache
def get_settings() -> Settings:
    return Settings()

settings = get_settings()
