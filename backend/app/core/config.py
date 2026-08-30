from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Inexxio ECS API"
    app_version: str = "1.0.0"
    debug: bool = False
    # Umgebung (per APP_ENV gesetzt). Ausserhalb der Produktion werden
    # Fehlerdetails in der API-Antwort offengelegt (zur Diagnose); in der
    # Produktion nur eine generische Meldung. Default = sicher (production).
    app_env: str = "production"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/inexxio_local"

    firebase_project_id: str = ""
    firebase_service_account_path: Optional[str] = None

    # ── Passkeys / WebAuthn (FIDO2) ───────────────────────────────────────────────
    # Passwortlose Anmeldung mit Passkeys (Face/Touch ID, Windows Hello, Security-Key).
    # Die WebAuthn-Zeremonien laufen im Backend; bei Erfolg wird ein Firebase **Custom
    # Token** ausgestellt (Frontend: signInWithCustomToken) – der bestehende Firebase-
    # Session-/ID-Token-Fluss bleibt damit unverändert (Backend-Verifikation identisch).
    #
    # RP-ID (die Domain, an die ein Passkey gebunden ist) und die erwartete Origin werden
    # pro Request aus dem ``Origin``-Header abgeleitet – so funktioniert dasselbe Deployment
    # auf localhost, inexxio-dev.web.app und inexxio-prod.web.app, ohne eine Domain fest
    # zu verdrahten.
    # Die Origin wird gegen die erlaubten Origins (``cors_origins`` + ``webauthn_extra_origins``)
    # geprüft; ``webauthn_rp_id`` kann die abgeleitete RP-ID bei Bedarf überschreiben.
    webauthn_rp_name: str = "Inexxio AG"
    webauthn_rp_id: str = ""                    # leer → aus Origin-Host abgeleitet
    webauthn_extra_origins: list[str] = []      # zusätzliche erlaubte Origins

    #: Die erlaubten Origins sind zugleich die erlaubten WebAuthn-Origins (siehe oben) –
    #: was hier fehlt, kann sich nicht anmelden. Darum stehen hier genau die Adressen,
    #: unter denen die Oberfläche wirklich läuft (`.github/workflows/deploy-*.yml`);
    #: keine der beiden Bereitstellungen setzt CORS_ORIGINS, dieser Default IST also der
    #: Betrieb. Frühere Einträge (`inexxio.web.app`, `inexxio.com`) waren nie ein Ziel.
    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://inexxio-dev.web.app",
        "https://inexxio-prod.web.app",
    ]

    initial_admin_email: str = "clemens.fritsche@gmail.com"

    #: Öffentliche Basis-URL des Frontends. Unter welcher Adresse die Website läuft, weiss
    #: das **Deployment** – kein Eingabefeld daneben, das beim ersten Domain-Wechsel still
    #: falsch wird (``services/sites.website_url`` ist die eine Ableitung daraus).
    frontend_base_url: str = "http://localhost:3000"

    # ── Zahlungsdienst (``services/stripe_pay``) ─────────────────────────────────
    #: **Leer heisst: es gibt keinen.** Kein Schalter daneben, der ohne Schlüssel auf «an»
    #: stünde – ``stripe_pay.available()`` ist eine Ableitung aus genau dieser Zeile. Ohne
    #: sie erscheint der Zahllink-Knopf gar nicht erst, und alles andere läuft unverändert:
    #: eine Überweisung ist kein Fallback, sondern der B2B-Normalfall.
    #:
    #: Beide Werte kommen aus dem Google Secret Manager (``docs/stripe-setup.md``), nie
    #: aus dem Repo. Sandbox-Schlüssel beginnen mit ``sk_test_`` bzw. ``whsec_``.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
