from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.database import Base
from ..domain import accounts
from .base import TimestampMixin


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
    role: Mapped[str] = mapped_column(String(20), default="customer", nullable=False)

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

    # Unified shipping address
    ship_name: Mapped[Optional[str]] = mapped_column(String(255))
    ship_company: Mapped[Optional[str]] = mapped_column(String(255))
    ship_address_line1: Mapped[Optional[str]] = mapped_column(String(255))
    ship_address_line2: Mapped[Optional[str]] = mapped_column(String(255))
    ship_city: Mapped[Optional[str]] = mapped_column(String(100))
    ship_postal_code: Mapped[Optional[str]] = mapped_column(String(20))
    ship_state_region: Mapped[Optional[str]] = mapped_column(String(100))
    ship_country: Mapped[Optional[str]] = mapped_column(String(100))

    # Invoice / billing address
    #: ►►► **Der Firmenname der Rechnungsadresse ist ABGELEITET** (Testnotiz #1042) ◄◄◄
    #: – die erste Zeile trägt bei Kontotyp «Geschäft» die Firma, und die steht in
    #: ``company_name``. Daneben stand ein eigenes Feld ``invoice_company``, das die
    #: Oberfläche bei «Rechnung = Lieferung» aus ``company_name`` **kopierte**: zwei
    #: Wahrheiten über dieselbe Firma, und die Kopie veraltete beim ersten Umfirmieren.
    #: Zusammengesetzt wird die Anschrift an einer Stelle (``people.billing_name``).
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
    invoice_same_as_shipping: Mapped[bool] = mapped_column(Boolean, default=False)

    # Personal extras
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)

    # ─── Kontotyp + Firmenangaben ──────────────────────────────────────────────
    #: ►►► **Privat ↔ Geschäft – eine STAMMDATEN-, keine Berechtigungsfrage.** ◄◄◄
    #:
    #: ``NULL`` heisst «noch nicht entschieden»; dann leitet ``domain/accounts.effective``
    #: ab (steht ein Firmenname da, war es ein Geschäftskonto). Darum **kein** Backfill
    #: und **kein** Default auf beiden Seiten, der auseinanderlaufen könnte: es gibt
    #: keinen. Die Rolle ``supplier`` **erzwingt** «Geschäft» – gelesen, nicht
    #: geschrieben, sonst stünde dieselbe Aussage zweimal da.
    account_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Business / company info – nur bei Kontotyp «Geschäft» sichtbar. **Vorhandene Werte
    # bleiben**, wenn jemand auf «Privat» wechselt: gelöscht wird nichts, benutzt wird
    # nichts (``people.is_business`` ist die eine Frage danach).
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    #: Die Rechtsform der Firma – dieselbe Angabe, die ``sites.legal_name`` an unserer
    #: eigenen Seite an den Namen hängt: «Muster» + «AG» ist die Rechtsperson, «Muster»
    #: allein ist keine. Freitext mit Vorschlägen je Land (#303), keine Auswahlliste –
    #: die verbindliche Quelle (ISO 20275) hat 2600 Einträge und keinen Endpunkt.
    legal_form: Mapped[Optional[str]] = mapped_column(String(50))
    uid_number: Mapped[Optional[str]] = mapped_column(String(20))
    vat_number: Mapped[Optional[str]] = mapped_column(String(20))
    vat_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    trade_register_nr: Mapped[Optional[str]] = mapped_column(String(50))
    trade_register_canton: Mapped[Optional[str]] = mapped_column(String(50))
    company_website: Mapped[Optional[str]] = mapped_column(String(255))

    # Supplier bank details
    bank_account_holder: Mapped[Optional[str]] = mapped_column(String(255))
    bank_iban: Mapped[Optional[str]] = mapped_column(String(50))
    bank_bic: Mapped[Optional[str]] = mapped_column(String(20))
    bank_name: Mapped[Optional[str]] = mapped_column(String(255))

    # Employee info
    #: ►►► **Für WELCHE Gesellschaft arbeitet diese Person?** (Testnotiz #905) ◄◄◄
    #:
    #: Die Objektnummer eines Unternehmens (``company_settings``). Es gab sie bis hierher
    #: nicht – und damit konnte ein Beleg nicht sagen, wer ihn stellt: er nahm immer den
    #: **Betreiber**, also die Gesellschaft, die die Website vertritt, auch wenn eine
    #: Schwestergesellschaft fakturiert.
    #:
    #: **Keine Fremdschlüssel-Spalte**, sondern die Objektnummer – dieselbe Bauart wie
    #: ``Deal.party_id`` und ``InstanceUnit.place_object_id``: sie ist die Adresse, unter
    #: der im Haus auf einen Datensatz gezeigt wird.
    #:
    #: ``NULL`` ist regulär für jeden, der **nicht** bei uns arbeitet (Kunde, Lieferant);
    #: für Personal ist es eine **Lücke**, die der Geldvorgang meldet, statt sie zu raten.
    company_object_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
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
        """Anzeigename – EINE Regel für alle Anzeigen und ALLE Rollen (Lieferant/Kunde/Prüfer):
        **«Vorname Nachname» → Firma → E-Mail** (Notiz #291). Es wird immer der **Name der
        Person** im Datensatz gezeigt, nicht der Firmenname – der ist nur Rückfall, wenn keine
        Person hinterlegt ist. (Der Versand-Empfängername bleibt firmen-first – eigene Regel in
        ``stripe_provider._full_name`` – denn das Paket geht an die Firma.)

        ►►► **Der Rückfall gilt nur einem GESCHÄFTSKONTO** (Testnotiz #1042). ◄◄◄ Wer auf
        «Privat» steht, behält seinen Firmennamen in der Zeile – **benutzt** wird er nicht,
        und das gilt auch hier: sonst trüge derselbe Datensatz an einer Stelle die Firma und
        auf dem Beleg die Person."""
        name = " ".join(p for p in [self.first_name, self.last_name] if p).strip()
        if name:
            return name
        business = accounts.effective(self.role, self.account_type,
                                      company_name=self.company_name)
        if business == accounts.BUSINESS and (self.company_name or "").strip():
            return self.company_name  # type: ignore[return-value]
        return self.email
