from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..core.database import Base
from .base import TimestampMixin

if TYPE_CHECKING:
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
    #: ``admin`` · ``employee`` · ``user`` – mehr nicht. «Lieferant» und «Kunde» standen
    #: hier einmal daneben und waren beide eine **Lüge über die Person**: *Lieferant ↔
    #: Kunde ist eine Eigenschaft des VORGANGS*. Wer Partner einer Ausgabe ist, ist dort
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

    # Contact address
    address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    city: Mapped[Optional[str]] = mapped_column(String(100))
    postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    state_region: Mapped[Optional[str]] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="CH")

    # ►►► **ZWEI Anschriften, nicht drei** (Testnotiz #1043). ◄◄◄
    #
    # Hier stand ein dritter Satz ``ship_*`` (acht Spalten mit eigenem Namen und eigener
    # Firma). Er hatte **keinen einzigen Leser und keinen Schreiber**: die Oberfläche hat
    # ihn nie angeboten, und ``voucher.billing_of`` liest als Lieferadresse die
    # **Hauptadresse** darüber. Eine dritte Adresse, die niemand füllt, ist keine
    # Vorsorge – sie ist die Stelle, an der jemand künftig die falsche erwischt. Das
    # Mapping ist weg, die Spalten fallen im Folge-Deploy.

    # Invoice / billing address
    #: ►►► **Die Rechnungsadresse ist FREIWILLIG – leer gilt die Lieferadresse.** ◄◄◄
    #:
    #: Daneben stand ein Schalter ``invoice_same_as_shipping``, und er war eine **zweite
    #: Wahrheit über dieselbe Sache**: ob eine eigene Rechnungsadresse hinterlegt ist,
    #: sagen die Felder selbst (``billing_of`` liest genau das). Schlimmer, er liess die
    #: Oberfläche bei «gleich wie» die Hauptadresse **hineinkopieren** – und die Kopie
    #: veraltete beim nächsten Umzug, genau wie damals ``invoice_company``.
    #:
    #: Jetzt gilt dieselbe Regel wie bei der Rechnungs-E-Mail (#1042): **leer heisst
    #: erben**, und das sagt das Feld. Kein Schalter, keine Checkbox, keine Kopie.
    invoice_first_name: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_last_name: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    invoice_city: Mapped[Optional[str]] = mapped_column(String(100))
    invoice_postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    invoice_country: Mapped[Optional[str]] = mapped_column(String(100))
    #: ►►► **Die Rechnungs-E-Mail gibt es GENAU EINMAL** (Testnotiz #1042) ◄◄◄ – und sie
    #: ist ein Attribut der **Rechnungsadresse**, nicht der Firma und nicht des Logins.
    #: Daneben stand einmal ``company_billing_email`` («Rechnungs-E-Mail (Firma)»): zwei
    #: Eingabefelder für eine Angabe, von denen das zweite **keinen einzigen Leser**
    #: hatte – wer es ausfüllte, schrieb in ein Feld, das nirgends ankam.
    #:
    #: **Leer heisst «die Login-/Kontakt-Adresse»** (``billing_of``) – darum kein zweites
    #: Feld und keine Checkbox: die Vererbung steht als Platzhalter im Feld.
    invoice_email: Mapped[Optional[str]] = mapped_column(String(255))

    # Personal extras
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # ─── Firma ──────────────────────────────────────────────────────────────────
    # ►►► **Die Firma ist ein eigener DATENSATZ, nicht ein Satz Felder an der Person**
    # (CRM Schritt 1). ◄◄◄ Hier standen Firmenname, Rechtsform, UID, MWST-Nr.,
    # Handelsregister und Website als Text an jeder Person – zwei Mitarbeiter derselben
    # Kundenfirma trugen damit zwei Fassungen derselben Firma, und keine war ein
    # Datensatz. Sie leben jetzt am Unternehmen (``company_settings``), und die Person
    # zeigt darauf: ``company_object_id`` weiter unten, gelesen über ``company``.

    # ►►► **Die Bankverbindung hängt an NICHTS** (Testnotiz #1043). ◄◄◄ Sie hing an der
    # Rolle «Lieferant» mit der Begründung «eine IBAN braucht, wen *wir* bezahlen» – und
    # genau das ist die Eigenschaft eines **Vorgangs**, nicht der Person: eine Erstattung
    # geht an einen Privatkunden, eine Spesenabrechnung an einen Mitarbeiter. Also ohne
    # Bedingung, wie jede andere Angabe des Datensatzes.
    bank_account_holder: Mapped[Optional[str]] = mapped_column(String(255))
    bank_iban: Mapped[Optional[str]] = mapped_column(String(50))
    bank_bic: Mapped[Optional[str]] = mapped_column(String(20))
    bank_name: Mapped[Optional[str]] = mapped_column(String(255))

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
    employment_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    weekly_hours: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)

    # Preferences & notifications
    language: Mapped[str] = mapped_column(String(10), default="de")
    notification_email: Mapped[bool] = mapped_column(Boolean, default=True)
    notification_inapp: Mapped[bool] = mapped_column(Boolean, default=True)
    newsletter_opt_in: Mapped[bool] = mapped_column(Boolean, default=False)

    # Auth / compliance
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    terms_version: Mapped[Optional[str]] = mapped_column(String(20))

    @property
    def display_name(self) -> str:
        """Anzeigename – EINE Regel für alle Anzeigen und ALLE Rollen:
        **«Vorname Nachname» → E-Mail** (Notiz #291). Es wird immer der **Name der
        Person** gezeigt; die Firma ist ein eigener Datensatz mit eigenem Namen."""
        name = " ".join(p for p in [self.first_name, self.last_name] if p).strip()
        return name or self.email
