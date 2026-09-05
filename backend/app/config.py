"""Configurazione applicativa, letta dall'ambiente (vedi .env.example)."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://workplanner:workplanner@db:5432/workplanner"
    owner_password_hash: str = ""
    #: Percorso di un file contenente l'hash della password owner. Ha la
    #: precedenza sulla variabile d'ambiente ed è il modo consigliato: un hash
    #: argon2 è pieno di `$` ($argon2id$v=19$m=...) e Docker Compose li
    #: interpola come variabili, consegnando al container un hash mutilato e un
    #: login che fallisce senza spiegare perché.
    owner_password_hash_file: str = ""
    session_secret: str = "dev-insecure-change-me"
    public_base_url: str = "http://localhost:8000"
    #: Origini ammesse dal browser, separate da virgola. In produzione va messo
    #: il sottodominio da cui è servito il frontend: cablarle nel codice
    #: significherebbe ricompilare per cambiare ambiente.
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    tz: str = "Europe/Rome"
    #: Dove finiscono i PDF/PNG generati (§20): un report è un allegato, resta su disco.
    reports_dir: str = "reports_out"
    #: APScheduler in-process (§32). Off nei test e nei comandi CLI.
    enable_jobs: bool = True


    @property
    def resolved_owner_password_hash(self) -> str:
        if self.owner_password_hash_file:
            path = Path(self.owner_password_hash_file)
            if path.is_file():
                return path.read_text().strip()
        return self.owner_password_hash

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        return [*dict.fromkeys([*origins, self.public_base_url])]


settings = Settings()
