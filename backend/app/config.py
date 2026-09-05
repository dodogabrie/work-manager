"""Configurazione applicativa, letta dall'ambiente (vedi .env.example)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://workplanner:workplanner@db:5432/workplanner"
    owner_password_hash: str = ""
    session_secret: str = "dev-insecure-change-me"
    public_base_url: str = "http://localhost:8000"
    #: Origini ammesse dal browser, separate da virgola. In produzione va messo
    #: il sottodominio da cui è servito il frontend: cablarle nel codice
    #: significherebbe ricompilare per cambiare ambiente.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    tz: str = "Europe/Rome"
    #: Dove finiscono i PDF/PNG generati (§20): un report è un allegato, resta su disco.
    reports_dir: str = "data/reports"
    #: APScheduler in-process (§32). Off nei test e nei comandi CLI.
    enable_jobs: bool = True


    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return [*dict.fromkeys([*origins, self.public_base_url])]


settings = Settings()
