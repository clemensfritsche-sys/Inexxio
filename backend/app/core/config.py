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

    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://inexxio-dev.web.app",
        "https://inexxio.web.app",
        "https://inexxio.com",
    ]

    initial_admin_email: str = "clemens.fritsche@gmail.com"

    # ── Shop / Verkauf ───────────────────────────────────────────────────────────
    # Zahlungs-Provider: 'manual' (Default, kein externer Call – überbrückbar für Tests)
    # oder 'stripe' (Gerüst; ohne STRIPE_SECRET_KEY niemals aktiv, kein Crash).
    payments_provider: str = "manual"
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Stripe Tax: Default-Steuercode (physische Güter). Pro Artikel überschreibbar (später).
    stripe_default_tax_code: str = "txcd_99999999"   # General - Tangible Goods
    # Preisauszeichnung: Basispreise sind brutto (inkl. MWST). Bei False: netto (MWST oben drauf).
    prices_tax_inclusive: bool = True
    # Stripe Tax (automatic_tax) am Checkout. NUR aktivieren, wenn im Stripe-Dashboard
    # eingerichtet (Sitz-Adresse + Registrierung) – sonst schlägt die Checkout-Erstellung fehl.
    stripe_tax_enabled: bool = False
    # Länder, in die wir liefern (Stripe Checkout shipping_address_collection). Komma-Liste.
    shop_ship_countries: str = "CH,LI,DE,AT,FR,IT,NL,BE,LU,ES,PT,SE,DK,FI,IE,PL,US"
    # Kostenlose FX-Quelle (Tageskurs) – exchangerate.host-Format ({"rates": {...}},
    # Basis CHF). Schlägt der Abruf fehl, wird der letzte bekannte Kurs verwendet.
    fx_source_url: str = "https://api.exchangerate.host/latest"
    # Öffentliche Basis-URL des Frontends (für interne Zahl-/Bestätigungs-Links).
    frontend_base_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
