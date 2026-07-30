from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class CompanySettings(Base):
    """Ein **Unternehmen** (eine Gesellschaft) – ein gleichrangiger ERP-Datensatz.

    Bis Juli 2026 war das ein Singleton (``id == 1``); danach kurz ein «Hauptsitz +
    kastrierte Standorte»-Modell. Jetzt trägt die Tabelle n **gleichrangige** Zeilen –
    jede eine vollständige juristische Einheit vom Feed-Typ ``organization``: eigene
    Objektnummer, eigener Name, Anschrift, **eigene Rechtsidentität** (UID/EIN/VAT), Bank,
    MWST. Als **Halter** verwendbar (``instances.location_type='company'`` zeigt auf die
    Objektnummer). Keine Zeile ist einer anderen untergeordnet.

    **Zwei Reichweiten, und wo eine Angabe gilt, entscheidet die Schreibstelle** – nicht
    ein Rang (``services/sites.py`` ist die eine Auflösung):

      * **je Gesellschaft** (``sites.ENTITY_FIELDS``, editierbar an JEDEM Datensatz):
        Name, Anschrift, Rechtsidentität, Bank, MWST/Zahlung. Die US-Gesellschaft hat
        ihre EIGENE EIN/Steuer/Bank – deshalb ist Rechtsidentität hier bewusst dabei.
      * **die eine Website/Integration** (``sites.PLATFORM_FIELDS``): Stripe-Key,
        Shop-Währungen, ``pricing_zone_factors``, ``legal_documents``, Plausible, Maps.
        Diese gibt es genau EINMAL; sie liegen (vorerst) als Spalten auf dem **Betreiber**
        (dem ältesten Unternehmen) und werden nur über die Systemkonfiguration gepflegt.

    **Der «Betreiber» ist abgeleitet, kein Flag** (``sites.operator`` = ältestes
    Unternehmen). Das frühere ``is_primary`` ist entfallen: es stellte eine Zeile über die
    anderen und war die Ursache eines Deploy-Ausfalls. Die Rolle «wer vertritt die eine
    Website» braucht keine Markierung – die kleinste ``id`` (der Ursprung) ist die Antwort.
    """

    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    # Universelle Objektnummer: Jede Gesellschaft ist ein vollwertiger ERP-Datensatz
    # (im Feed als «Unternehmen» geführt, vom Admin pflegbar). Wird bei der ersten
    # Abfrage lazy vergeben (services/sites.operator) bzw. beim Anlegen (sites.create).
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, index=True)
    # Der Name der Gesellschaft. Das ist zugleich das Halter-Label:
    # ``locations.location_label`` gibt für einen ``company``-Halter genau dieses Feld zurück.
    #
    # ``is_primary`` ist aus dem MODELL entfernt (Rolle «Betreiber» wird abgeleitet). Die
    # Spalte bleibt vorübergehend in der DB (Migration 091 dropt sie im Folge-Deploy);
    # SQLAlchemy ignoriert die nicht gemappte Spalte, das Lifespan-Netz hält sie für die
    # noch laufende Vorgänger-Revision während des Rollouts intakt.
    company_name: Mapped[str] = mapped_column(String(255), default="Inexxio AG")
    legal_form: Mapped[str] = mapped_column(String(50), default="AG")
    street: Mapped[Optional[str]] = mapped_column(String(255))
    street_nr: Mapped[Optional[str]] = mapped_column(String(20))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="Schweiz")
    uid_number: Mapped[Optional[str]] = mapped_column(String(30))
    vat_number: Mapped[Optional[str]] = mapped_column(String(30))
    trade_register_nr: Mapped[Optional[str]] = mapped_column(String(50))
    trade_register_canton: Mapped[Optional[str]] = mapped_column(String(50))
    share_capital: Mapped[Optional[str]] = mapped_column(String(100))
    iban_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    qr_iban_encrypted: Mapped[Optional[str]] = mapped_column(Text)
    bank: Mapped[Optional[str]] = mapped_column(String(255))
    bic_swift: Mapped[Optional[str]] = mapped_column(String(20))
    email: Mapped[str] = mapped_column(String(255), default="info@inexxio.com")
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    website: Mapped[str] = mapped_column(String(255), default="https://inexxio.com")
    vat_method: Mapped[str] = mapped_column(String(50), default="effektiv")
    vat_period: Mapped[str] = mapped_column(String(20), default="quartal")
    default_payment_days: Mapped[int] = mapped_column(Integer, default=30)
    default_skonto_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2))
    default_skonto_days: Mapped[Optional[int]] = mapped_column(Integer)
    oss_active: Mapped[bool] = mapped_column(Boolean, default=False)
    oss_reg_number: Mapped[Optional[str]] = mapped_column(String(50))
    vies_active: Mapped[bool] = mapped_column(Boolean, default=False)
    logo_path: Mapped[Optional[str]] = mapped_column(String(500))

    # API Keys / Integrations
    stripe_publishable_key: Mapped[Optional[str]] = mapped_column(String(255))
    plausible_domain: Mapped[Optional[str]] = mapped_column(String(255))
    hcaptcha_site_key: Mapped[Optional[str]] = mapped_column(String(255))
    google_maps_api_key: Mapped[Optional[str]] = mapped_column(String(255))

    # ── Shop / Verkauf ──────────────────────────────────────────────────────────
    # Im Shop wählbare Währungen (Default CHF/EUR/USD) sowie die Zuordnung
    # Land → Default-Währung (editierbar) und die Fallback-Währung.
    shop_currencies: Mapped[Optional[list]] = mapped_column(JSONB)
    shop_country_currency: Mapped[Optional[dict]] = mapped_column(JSONB)
    shop_default_currency: Mapped[str] = mapped_column(
        String(3), default="CHF", server_default="CHF", nullable=False)
    # Zahlungs-Provider (überschreibt die Env ``PAYMENTS_PROVIDER``): 'manual' | 'stripe'.
    payments_provider: Mapped[Optional[str]] = mapped_column(String(16))
    # Optionale Preis-Pipeline-Stufe ② (PPP/Kaufkraft): Land → Faktor, z. B.
    # {"Deutschland": 1.1, "USA": 0.9}. Leer/NULL = Stufe abgeschaltet (Default).
    pricing_zone_factors: Mapped[Optional[dict]] = mapped_column(JSONB)

    # ── Öffentliche Rechtsdokumente (D): Zeiger auf einen **Artikel** ───────────────
    # Je Rechtsdokument-Art (AGB/Datenschutz/…) die **Objektnummer eines Artikels**. Die
    # Website zieht dessen erste freigegebene Instanz (den ausgestellten Dokument-Beleg).
    # Map ``{"agb": 100000123, "datenschutz": …}`` (Wert = Artikel-Objektnummer). Neue
    # Fassung = neuer Artikel + «Ersetzen» (``replaced_by_id``): die Auflösung folgt der
    # Kette automatisch auf die neueste Fassung mit freigegebenem Beleg; alte Fassungen
    # bleiben über ihre Instanz-Objektnummer archiviert (``services/legal.py``).
    legal_documents: Mapped[Optional[dict]] = mapped_column(JSONB)

    # (``legal_ack_config`` – die frühere konfigurierbare Bestätigungspflicht – ist
    # entfernt: die Pflicht ist HART verdrahtet (``consent.MUST_ACKNOWLEDGE_KINDS``),
    # Rollen-Publikum läuft über die Dokument-Schritte (``doc_audience``). Migration 075.)
