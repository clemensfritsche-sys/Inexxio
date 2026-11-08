from typing import Optional

from sqlalchemy import JSON, BigInteger, Boolean, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base


class CompanySettings(Base):
    """Ein **Unternehmen** (eine Gesellschaft) – ein gleichrangiger ERP-Datensatz.

    n **gleichrangige** Zeilen, jede eine juristische Einheit mit eigener Objektnummer und
    Rechtsidentität; als **Halter** verwendbar. Felder je Gesellschaft:
    ``sites.ENTITY_FIELDS`` (bewusst **klein**); aufgelöst nur über ``services/sites.py``.
    """

    __tablename__ = "company_settings"
    __table_args__ = (
        Index("uq_company_settings_uid_key", "uid_key", unique=True,
              postgresql_where=text("is_active AND uid_key IS NOT NULL")),
        Index("uq_company_settings_name_key", "name_key", unique=True,
              postgresql_where=text("is_active AND uid_key IS NULL AND name_key IS NOT NULL")),
    )

    # ►►► **Die Nummer kommt aus der Sequenz** ◄◄◄ – kein Python-Default.
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Universelle Objektnummer (``sites.operator`` bzw. ``sites.create``).
    object_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    # **Betreiber der Website** – genau EINE (partieller Unique-Index), wählbar
    # (``sites.set_operator``); ohne Markierung gilt die älteste (``sites.find_operator``).
    is_operator: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    # **Aktiv?** – Soft-Delete; die Objektnummer bleibt auflösbar.
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False)
    #: ►►► **Eine UNSERER Gesellschaften?** ◄◄◄ Nur eine eigene stellt Belege, beschäftigt
    #: Personal, besitzt Gebiete und kann Betreiber sein (Kunde ↔ Lieferant ist eine
    #: Eigenschaft des Vorgangs). Gesetzt nur von Admins; gelesen über ``services/sites.py``.
    is_own: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False)
    # **Funktionswährung** (ISO-3), vorbelegt aus dem Land (``sites.currency_for_country``).
    currency: Mapped[str] = mapped_column(
        String(3), default="CHF", server_default="CHF", nullable=False)
    # Der Name, zugleich das Halter-Label; ohne Vorgabewert.
    company_name: Mapped[str] = mapped_column(String(255))
    legal_form: Mapped[str] = mapped_column(String(50), default="AG")
    street: Mapped[Optional[str]] = mapped_column(String(255))
    street_nr: Mapped[Optional[str]] = mapped_column(String(20))
    zip_code: Mapped[Optional[str]] = mapped_column(String(20))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="Schweiz")
    # **Rechtsidentität**: UID/Steuernummer und MWST-Nummer (Briefkopf, Impressum).
    uid_number: Mapped[Optional[str]] = mapped_column(String(30))
    vat_number: Mapped[Optional[str]] = mapped_column(String(30))
    #: ►►► **Woran eine Firma erkannt wird – zwei Schlüssel, abgeleitet**.
    #: ◄◄◄ ``uid_key`` = UID ohne Satzzeichen (``domain/uid.normalize``), ``name_key`` = Name
    #: und Rechtsform normalisiert; geschrieben allein von ``sites._rekey``. **Eindeutig in
    #: der Datenbank**: eine Dublette ist unmöglich.
    uid_key: Mapped[Optional[str]] = mapped_column(String(20))
    name_key: Mapped[Optional[str]] = mapped_column(String(320))
    # Bank = **eine** Zahl: die IBAN. Die Spalte heisst ``iban_encrypted``; verschlüsselt
    # wird nichts (sie steht auf jeder Rechnung).
    iban: Mapped[Optional[str]] = mapped_column("iban_encrypted", Text)
    email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    #: ►►► **Zeiterfassung einer eigenen Gesellschaft**: der Kanton (er
    #: bestimmt den Vorschlag der Feiertage) und je Absenzart, ab welchem Arbeitstag ein
    #: Nachweis nötig ist – ``{"canton": "TG", "proof": {"krank": 3}}``. Was fehlt, ist die
    #: Vorgabe aus ``domain/timekeeping``.
    time_rules: Mapped[Optional[dict]] = mapped_column(JSON)


class CompanyTerritory(Base):
    """Ein **Gebietsanspruch**: dieses Gebiet fakturiert diese Gesellschaft (ADR 006).

    Feste Regionen (``services/geography.REGIONS``); die Tabelle hält NUR die **Abweichungen
    vom Default**. Ein Gebiet ist eine Region ODER ein Land (ISO-2, ``geography.is_country_code``)
    in der Spalte ``region``, **unique**. Auflösung: ``services/sites.company_for_country``
    (**Land ≻ Region ≻ Betreiber**).
"""

    __tablename__ = "company_territories"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # Gebiets-Code: Regions-Code («EUR») ODER ISO-2-Land als Ausnahme («LI»).
    region: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    company_id: Mapped[int] = mapped_column(Integer, index=True, nullable=False)
