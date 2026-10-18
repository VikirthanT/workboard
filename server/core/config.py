"""Settings, read from environment variables only (no .env file is loaded here).

DATABASE_URL has no default: it comes from the environment. `make` builds it from .env (POSTGRES_* parts) for
host targets and docker compose builds it for the containers; this module never reads the file.
DEV_AUTH is off unless explicitly "true"; with it off the only way in is Google sign-in, which needs the
GOOGLE_* settings and a SECRET_KEY (see `google_configured`). Without them protected routes answer 501.
ALLOWED_EMAIL_DOMAIN is the one place the company domain lives: the app checks it when people are
loaded and when anyone signs in. The database only checks that emails are lowercase.
"""
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str  # required, no default: credentials never live in the code
    dev_auth: bool = False
    allowed_email_domain: str = "atimotors.com"
    bootstrap_admin_emails: str = ""

    # Google sign-in. The client id and secret come from the Google Cloud OAuth client; the redirect address is
    # where Google sends the browser back (it must be one of the client's authorised redirect URIs). SECRET_KEY
    # signs the session tokens and the sign-in state cookie: at least 32 characters, e.g. `openssl rand -hex 32`.
    # TOKEN_TTL_SECONDS is how long a session lasts (default 8 hours); all of these are set in .env.
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = ""
    secret_key: str = ""
    token_ttl_seconds: int = 28800

    @property
    def google_configured(self) -> bool:
        """True only when everything Google sign-in needs is set, so half a set-up never looks like a working one."""
        return bool(self.google_client_id and self.google_client_secret and self.google_redirect_uri) and len(self.secret_key) >= 32

    @field_validator("database_url")
    @classmethod
    def _use_the_installed_driver(cls, url: str) -> str:
        """The usual `postgresql://` form works: we install psycopg 3, and without a driver named SQLAlchemy looks for psycopg2."""
        for bare in ("postgresql://", "postgres://"):
            if url.startswith(bare):
                return "postgresql+psycopg://" + url[len(bare):]
        return url

    @property
    def admin_emails(self) -> list[str]:
        return [e.strip().lower() for e in self.bootstrap_admin_emails.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
