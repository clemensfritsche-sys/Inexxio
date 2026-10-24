from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin

if TYPE_CHECKING:
    from .address_book import Address
    from .admin import CompanySettings


class UserProfile(Base, TimestampMixin):
    __tablename__ = "user_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    object_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    firebase_uid: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    photo_url: Mapped[Optional[str]] = mapped_column(Text)
    # Wie sich die Person zuletzt angemeldet hat (aus dem Firebase-ID-Token:
    # google.com | password | emailLink | custom = Passkey). Rein deskriptiv – die
    # Support-Frage «wie kommt der überhaupt rein?» war sonst nicht beantwortbar.
    last_sign_in_provider: Mapped[Optional[str]] = mapped_column(String(40))
    #: ►►► **Die Rolle beantwortet GENAU EINE Frage: darf diese Person ins ERP?** ◄◄◄
    #:
    #: ``admin`` · ``employee`` · ``user`` – mehr nicht. *Lieferant ↔ Kunde ist eine
    #: Eigenschaft des VORGANGS*, nicht der Person. Wer Partner einer Ausgabe ist, ist dort
    #: Lieferant; bei einer Einnahme Kunde – dieselbe Person kann beides sein, und zwar
    #: gleichzeitig. Eine Spalte am Datensatz muss sich für eines entscheiden und liegt
    #: damit in der Hälfte der Fälle falsch. Dieselbe Bauart wie
    #: ``order_units.return_to_order_id``: die **Verbindung** trägt es, nicht der Datensatz.
    #:
    #: Gelesen wird sie ausschliesslich als Zugang (``people.STAFF_ROLES``).
    role: Mapped[str] = mapped_column(String(20), default="user", nullable=False)

    # Personal identity
    first_name: Mapped[Optional[str]] = mapped_column(String(100))
    last_name: Mapped[Optional[str]] = mapped_column(String(100))
    phone: Mapped[Optional[str]] = mapped_column(String(50))

    # ►►► **Die Anschriften stehen im ADRESSBUCH** (``models/address_book.Address``,
    # Migration 143). ◄◄◄ Eine Person hat beliebig viele Orte (Wohnung, Büro, Lager,
    # Baustelle), und wohin Ware und Rechnung gehen, entscheidet die Bestellung. Die alten
    # Anschrift-Spalten am Benutzer sind gedroppt (Migration 152).
    #: Das Adressbuch – nur lesend und nur die aktiven, älteste zuerst.
    addresses: Mapped[list["Address"]] = relationship(
        "Address",
        primaryjoin="and_(Address.owner_id == UserProfile.id, Address.is_active == True)",
        viewonly=True, lazy="select", order_by="Address.id",
    )

    # Personal extras
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # ─── Firma ──────────────────────────────────────────────────────────────────
    # ►►► **Die Firma ist ein eigener DATENSATZ, nicht ein Satz Felder an der Person**
    # (CRM Schritt 1). ◄◄◄ Name, Rechtsform und UID leben am Unternehmen
    # (``company_settings``); die Person zeigt darauf: ``company_object_id`` weiter unten,
    # gelesen über ``company``. Eine Bankverbindung hat die Person nicht – eine IBAN gibt
    # es nur an einer EIGENEN Gesellschaft (Überweisung, QR-Rechnung).

    #: ►►► **Die Firma dieser Person** – eine eigene Gesellschaft (dann arbeitet sie
    #: bei uns) oder eine fremde (Kunde, Lieferant, Interessent). EINE Zuordnung für
    #: beide, die Unterscheidung trägt die Firma (``is_own``). ``NULL`` = Privatperson.
    #:
    #: **Keine Fremdschlüssel-Spalte**, sondern die Objektnummer – die Adresse, unter der
    #: im Haus auf einen Datensatz gezeigt wird. Personal braucht eine **eigene** Firma
    #: (``people.assert_employment``) – auf einem Beleg steht, wer ihn stellt.
    company_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    #: Die Firma als Datensatz – nur lesend; geschrieben wird ``company_object_id``.
    company: Mapped[Optional["CompanySettings"]] = relationship(
        "CompanySettings",
        primaryjoin="foreign(UserProfile.company_object_id) == CompanySettings.object_id",
        viewonly=True, lazy="select", uselist=False,
    )
    department: Mapped[Optional[str]] = mapped_column(String(100))
    job_title: Mapped[Optional[str]] = mapped_column(String(100))
    # ``employment_start_date`` und ``weekly_hours`` sind kein Feld mehr: Eintritt, Pensum und
    # Austritt stehen im **Vertrag** der Zeiterfassung (``models/timekeeping``, Migration
    # 154); die Spalten fallen im Folge-Deploy.

    # Preferences & notifications
    language: Mapped[str] = mapped_column(String(10), default="de")
    notification_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_inapp: Mapped[bool] = mapped_column(Boolean, default=True)
    # ``newsletter_opt_in`` ist kein Feld mehr: die Einwilligung ist ein Nachweis
    # (``models/newsletter``, Migration 153); die Spalte fällt im Folge-Deploy.

    # Auth / compliance
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    @property
    def missing_fields(self) -> list[dict]:
        """Was im Profil noch fehlt – die Regel steht in ``people.missing_fields``."""
        from ..services.people import missing_fields
        return missing_fields(self)

    @property
    def required_fields(self) -> list[str]:
        from ..services.people import required_fields
        return [key for key, _, _ in required_fields(self)]

    @property
    def display_name(self) -> str:
        """Anzeigename – EINE Regel für alle Anzeigen und ALLE Rollen:
        **«Vorname Nachname» → E-Mail** (Notiz #291). Es wird immer der **Name der
        Person** gezeigt; die Firma ist ein eigener Datensatz mit eigenem Namen."""
        name = " ".join(p for p in [self.first_name, self.last_name] if p).strip()
        return name or self.email
