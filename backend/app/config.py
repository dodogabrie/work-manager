"""Configurazione applicativa, letta dall'ambiente (vedi .env.example)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://workplanner:workplanner@db:5432/workplanner"
    owner_password_hash: str = ""
    session_secret: str = "dev-insecure-change-me"
    public_base_url: str = "http://localhost:8000"
    tz: str = "Europe/Rome"


settings = Settings()
