from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Databáze leží vždy v adresáři backend/, nezávisle na tom, odkud se aplikace spustí.
# Bez toho by spuštění z jiné složky vytvořilo prázdnou DB jinde = zdánlivá ztráta dat.
_DB_FILE = Path(__file__).resolve().parent.parent / "tracking.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(Path(__file__).resolve().parent.parent / ".env"), extra="ignore")

    database_url: str = f"sqlite:///{_DB_FILE.as_posix()}"
    redis_url: str | None = None

    # Povolené originy frontendu (CORS). Lokálně default; v produkci nastav
    # FRONTEND_ORIGIN na URL nasazeného frontendu (lze i víc, oddělené čárkou).
    frontend_origin: str = "http://localhost:3000"

    # Veřejná URL frontendu pro odkazy v e-mailech (magic link). V produkci = doména frontendu.
    public_app_url: str = "http://localhost:3000"

    # Veřejná URL tohoto backendu (pro Strava OAuth callback). V produkci = doména Renderu.
    backend_base_url: str = "http://localhost:8000"

    livetrack_poll_seconds: int = 30

    strava_client_id: str | None = None
    strava_client_secret: str | None = None

    # Autentizace (magic link)
    # podpis session JWT; v produkci nastav náhodný (Render ho vygeneruje sám)
    secret_key: str = "dev-insecure-change-me-please-set-a-real-32B-secret"
    session_ttl_days: int = 180  # po přihlášení zůstává uživatel přihlášený ~6 měsíců
    magic_link_ttl_min: int = 30
    # Odesílání e-mailů přes Resend (https://resend.com). Bez klíče se odkaz vypíše
    # do konzole a vrátí v odpovědi (jen pro vývoj) — v produkci klíč nastav.
    resend_api_key: str | None = None
    mail_from: str = "Race tracker <onboarding@resend.dev>"
    # SMTP (např. Gmail) — má přednost před Resendem. Pro Gmail použij "heslo aplikace".
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    # Lokální vývoj: bez e-mailu se magic link vrátí v odpovědi (pohodlí).
    # V produkci MUSÍ být False (render.yaml to nastaví), jinak by šlo přihlásit
    # se jako kdokoli bez ověření e-mailu.
    dev_mode: bool = True

    # Predikce
    segment_length_m: float = 100.0
    monte_carlo_runs: int = 2000

    # Povolené e-maily (allowlist). Prázdné = otevřené (přihlásit se může kdokoli).
    # Neprázdné = přihlásit se smí jen tyto e-maily (oddělené čárkou).
    allowed_emails: str = ""

    # Administrátoři (vidí admin sekci). Oddělené čárkou.
    admin_emails: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origin.split(",") if o.strip()]

    @property
    def allowlist(self) -> set[str]:
        return {e.strip().lower() for e in self.allowed_emails.split(",") if e.strip()}

    def is_email_allowed(self, email: str) -> bool:
        allow = self.allowlist
        return (not allow) or (email.strip().lower() in allow)

    @property
    def admin_set(self) -> set[str]:
        return {e.strip().lower() for e in self.admin_emails.split(",") if e.strip()}

    def is_admin(self, email: str) -> bool:
        return email.strip().lower() in self.admin_set


settings = Settings()
