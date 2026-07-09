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
    # auf localhost, inexxio-dev.web.app und inexxio.com, ohne Domain fest zu verdrahten.
    # Die Origin wird gegen die erlaubten Origins (``cors_origins`` + ``webauthn_extra_origins``)
    # geprüft; ``webauthn_rp_id`` kann die abgeleitete RP-ID bei Bedarf überschreiben.
    webauthn_rp_name: str = "Inexxio AG"
    webauthn_rp_id: str = ""                    # leer → aus Origin-Host abgeleitet
    webauthn_extra_origins: list[str] = []      # zusätzliche erlaubte Origins

    cors_origins: list[str] = [
        "http://localhost:3000",
        "https://inexxio-dev.web.app",
        "https://inexxio.web.app",
        "https://inexxio.com",
    ]

    initial_admin_email: str = "clemens.fritsche@gmail.com"

    # ── Datei-Ablage (Belege/Dokumente) ──────────────────────────────────────────
    # Google Cloud Storage für hochgeladene Dokumente (PDF/Bilder). Ist ``gcs_bucket``
    # gesetzt, landen Dateien im Bucket (Cloud-Run-ADC-Auth, kein Key); sonst als
    # Fallback in der DB (``document_blobs``) – sofort lauffähig ohne Bucket/IAM-Setup.
    gcs_bucket: str = ""
    gcs_document_prefix: str = "documents"

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
    # ── Logistik / Versand ────────────────────────────────────────────────────────
    # Carrier-Aggregator (Rate-Shopping + Label-Kauf): 'shippo' aktiviert sich von selbst,
    # sobald SHIPPO_API_KEY gesetzt ist (Self-Serve wie Stripe: Test-Key sofort sichtbar
    # nach Registrierung, Pay-per-Label, keine Vertrags-Eintrittsbarriere; solide EU-
    # Carrier-Abdeckung). Ohne Key läuft der 'manual'-Fallback (Carrier/Tracking von Hand
    # erfassen) – nie kaputt. Der Anbieter ist hinter dem Gateway austauschbar.
    shippo_api_key: str = ""
    shippo_api_url: str = "https://api.goshippo.com"

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
    # Vertex-Standort: 'eu' = EU-Multi-Region-Endpunkt (Datenresidenz CH/EU, breite
    # Modellabdeckung inkl. Opus 4.6) | eine feste Region (europe-west1/-west4) | 'global'
    # (keine EU-Garantie). Für DSGVO/CH-DSG bewusst 'eu' als Default.
    vertex_region: str = "eu"
    anthropic_api_key: str = ""                 # nur für ai_provider='anthropic'
    # Modell-IDs – konfigurierbar, Registry in services/ai/registry.py.
    # Dynamische Modellwahl (Kosten/Latenz): einfache Anfragen laufen auf dem leichten,
    # schnellen Modell; nur komplexe/mehrstufige Aufgaben nutzen das starke Modell.
    ai_chat_model: str = "claude-opus-4-8"                    # stark (komplex/Aktionen)
    ai_chat_model_light: str = "claude-haiku-4-5-20251001"   # leicht/günstig/schnell (einfache Reads)
    ai_image_model: str = "gemini-3.1-flash-image"   # «Nano Banana 2» (Shop-Bildbearbeitung)
    ai_max_output_tokens: int = 2048
    ai_request_timeout: float = 55.0            # Sekunden je Modell-Aufruf

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()
