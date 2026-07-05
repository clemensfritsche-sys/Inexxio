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
    # Kostenlose FX-Quelle (Tageskurs) – exchangerate.host-Format ({"rates": {...}},
    # Basis CHF). Schlägt der Abruf fehl, wird der letzte bekannte Kurs verwendet.
    fx_source_url: str = "https://api.exchangerate.host/latest"
    # Öffentliche Basis-URL des Frontends (für interne Zahl-/Bestätigungs-Links).
    frontend_base_url: str = "http://localhost:3000"

    # ── KI-Layer (ADR 004) ────────────────────────────────────────────────────────
    # Anbieter hinter dem AI-Gateway – Wechsel an EINER Stelle, ohne Fachlogik:
    #   'vertex'    → Claude via Google Vertex AI (EU-Datenresidenz, GCP-ADC-Auth) – Default
    #   'anthropic' → Claude direkt (ANTHROPIC_API_KEY nötig)
    #   'disabled'  → KI aus; alle KI-Endpunkte antworten 503, das ERP läuft normal.
    # Ohne konfiguriertes Projekt/Key ist die KI automatisch inaktiv (kein Crash).
    ai_provider: str = "vertex"
    vertex_project_id: str = ""                 # GCP-Projekt (leer = KI inaktiv bei 'vertex')
    vertex_region: str = "europe-west1"         # EU-Region (Datenresidenz CH/EU)
    anthropic_api_key: str = ""                 # nur für ai_provider='anthropic'
    # Modell-IDs – konfigurierbar, Registry in services/ai/registry.py.
    ai_chat_model: str = "claude-opus-4-8"
    ai_image_model: str = "gemini-3.1-flash-image"   # «Nano Banana 2» (Shop-Bildbearbeitung)
    ai_max_output_tokens: int = 2048
    ai_request_timeout: float = 55.0            # Sekunden je Modell-Aufruf

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
