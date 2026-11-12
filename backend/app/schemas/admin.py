from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field


class CompanySettingsUpdate(BaseModel):
    """Änderbare Felder einer Firma. Die Kontakt-E-Mail einer eigenen Gesellschaft schreibt
    allein das Postfach (``mailbox._contact``).

    **Bewusst kurz** (Testnotizen #307/#313/#314/#317–#321): nur, was eine Logik trägt.
    Zahlungsziel und Skonto gehören zur **Offerte** (dort ist die Angabe verhandelbar),
    MWST-Methode/-Periode kommen mit der Buchhaltung (Phase 3), die sie auswertet.

    ``website`` fehlt hier absichtlich: die Adresse der Website ist **abgeleitet**
    (``sites.website_url`` = die Deployment-Adresse), keine Eingabe."""
    company_name: Optional[str] = Field(None, description="Name der Firma ohne Rechtsform, z. B. «Digitec Galaxus».")
    legal_form: Optional[str] = Field(None, description="Rechtsform, z. B. «AG», «GmbH».")
    street: Optional[str] = Field(None, description="Strasse – nur eine eigene Gesellschaft trägt eine Anschrift; eine fremde Firma ist Name, Rechtsform und UID (ihre Anschrift steht im Adressbuch ihrer Personen).")
    street_nr: Optional[str] = Field(None, description="Hausnummer – nur eigene Gesellschaft.")
    zip_code: Optional[str] = Field(None, description="Postleitzahl – nur eigene Gesellschaft.")
    city: Optional[str] = Field(None, description="Ort – nur eigene Gesellschaft.")
    country: Optional[str] = Field(None, description="Land als ISO-Code mit 2 Buchstaben (z. B. CH) – nur eigene Gesellschaft.")
    currency: Optional[str] = Field(None, description="Hauswährung als ISO-Code (z. B. CHF) – nur eigene Gesellschaft.")
    uid_number: Optional[str] = Field(None, description="Unternehmens-Identifikationsnummer, z. B. CHE-123.456.789 (Prüfziffer wird geprüft).", examples=["CHE-123.456.789"])
    vat_number: Optional[str] = Field(None, description="MWST-Nummer – nur eigene Gesellschaft.")
    iban: Optional[str] = Field(None, description="IBAN für Zahlungen an uns – nur eigene Gesellschaft.")
    phone: Optional[str] = Field(None, description="Telefon der eigenen Gesellschaft.")
    #: «Eigenes Unternehmen» – setzt nur ein Admin (``sites.apply_update``).
    is_own: Optional[bool] = Field(None, description="Eine unserer Gesellschaften? Nur ein Admin setzt das.")


class CompanyCreate(BaseModel):
    """Neue **Firma** anlegen: Name und Rechtsform (die Rechtsperson), die UID freiwillig.
    Alles Weitere wird danach am Datensatz gepflegt. ``is_own`` setzt nur ein Admin."""
    company_name: str = Field(description="Name der Firma ohne Rechtsform, z. B. «Digitec Galaxus».")
    legal_form: str = Field("", description="Rechtsform, z. B. «AG», «GmbH».")
    uid_number: Optional[str] = Field(None, description="UID (z. B. CHE-123.456.789) – erkennt eine bekannte Firma; Prüfziffer wird geprüft.")
    is_own: bool = Field(False, description="Eine unserer Gesellschaften? Nur ein Admin.")


class EmailCheck(BaseModel):
    """Die neue Anmelde-E-Mail – gefragt, bevor der Bestätigungslink hinausgeht."""
    email: str


class AddressIn(BaseModel):
    """**Eine Anschrift im Adressbuch** – anlegen oder ändern (nur Gesendetes wirkt).

    ``is_default_*: true`` macht sie zum Standard; ``false`` ist keine Handlung – einen
    Standard nimmt man nicht weg, man gibt ihn einer anderen. ``account`` (``private`` ·
    ``business``) gilt nur beim Anlegen – das Konto einer Anschrift ändert sich nie; die
    ``email`` nur im Geschäftskonto."""
    account: Optional[str] = Field(None, description="Konto der Anschrift: 'private' oder 'business' (nur mit Firma); nur beim Anlegen.")
    street1: Optional[str] = Field(None, description="Strasse und Hausnummer.")
    street2: Optional[str] = Field(None, description="Zusatz (Postfach, Abteilung, z. H.).")
    zip: Optional[str] = Field(None, description="Postleitzahl.")
    city: Optional[str] = Field(None, description="Ort.")
    region: Optional[str] = Field(None, description="Kanton, Bundesland, Region (wo üblich).")
    country: Optional[str] = Field(None, description="Land als ISO-Code mit 2 Buchstaben (z. B. CH).")
    email: Optional[str] = Field(None, description="E-Mail für Rechnungen an diese Anschrift – nur im Geschäftskonto.")
    is_default_delivery: Optional[bool] = Field(None, description="true = Standard-Lieferadresse dieses Kontos (false bewirkt nichts).")
    is_default_billing: Optional[bool] = Field(None, description="true = Standard-Rechnungsadresse dieses Kontos (false bewirkt nichts).")


class AddressOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account: str
    street1: str
    street2: Optional[str] = None
    zip: str
    city: str
    region: Optional[str] = None
    country: str
    email: Optional[str] = None
    is_default_delivery: bool
    is_default_billing: bool


class CompanyPerson(BaseModel):
    """Eine Person, die zu dieser Firma gehört – für die Liste am Firmen-Datensatz."""
    object_id: int
    name: str
    email: str
    role: str


class CompanyRef(BaseModel):
    """**Die Firma einer Person** – ihre Identität, mehr nicht: Name, Rechtsform, UID.

    Eine fremde Firma trägt bei uns keine Anschrift (``sites.EXTERNAL_FIELDS``); was eine
    Person an ihr sieht, ist, was sie selbst genannt hat. Gepflegt wird sie am eigenen
    Datensatz – vom Personal."""
    model_config = ConfigDict(from_attributes=True)

    object_id: int
    company_name: str
    legal_form: str
    uid_number: Optional[str] = None
    is_own: bool = False

    @computed_field  # type: ignore[prop-decorator]
    @property
    def legal_name(self) -> str:
        from ..services.sites import legal_name
        return legal_name(self)


class NewCompany(BaseModel):
    """►►► **Eine Firma NENNEN** – die UID, sonst Name und Rechtsform. ◄◄◄

    Der Server erkennt sie (gleiche UID · ohne UID gleicher Name **und** gleiche
    Rechtsform) oder legt sie an (``sites.resolve``). Bei einer bekannten UID zählt der
    getippte Name nicht – die Firma heisst, wie sie heisst."""
    company_name: str = Field("", description="Name der Firma ohne Rechtsform.")
    legal_form: str = Field("", description="Rechtsform, z. B. «AG».")
    uid_number: Optional[str] = Field(None, description="UID – mit ihr wird eine bekannte Firma erkannt statt neu angelegt.")


class CompanySettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int] = None
    # **Abgeleitete** Rolle: ist dies der Betreiber der Website?
    is_operator: bool = False
    # Trägt echte Ortsangaben? Ohne Anschrift bleibt eine Bewegung dorthin innerbetrieblich
    # (ADR 005).
    has_address: bool = False
    # Aktiv? Eine geschlossene Gesellschaft bleibt lesbar, ist aber nicht mehr verwendbar.
    is_active: bool = True
    #: Eine **unserer** Gesellschaften? Nur sie stellt Belege, beschäftigt Personal,
    #: besitzt Gebiete und kann Betreiber sein.
    is_own: bool = False
    company_name: str
    legal_form: str
    # ►►► **Der Datensatzname** – Name, Rechtsform (``sites.legal_name``, nie «AG AG»). ◄◄◄
    # Eine Projektion, keine Spalte.
    legal_name: str = ""
    street: Optional[str]
    street_nr: Optional[str]
    zip_code: Optional[str]
    city: Optional[str]
    country: str
    currency: str = "CHF"
    uid_number: Optional[str]
    vat_number: Optional[str]
    # ►►► **Die eigene IBAN steht ausgeschrieben da** ◄◄◄ – sie steht auf jeder Rechnung und
    # im QR-Code; der Admin muss sie prüfen können.
    iban: Optional[str] = None
    email: str
    phone: Optional[str]
    # **Abgeleitet, nicht gepflegt**: die Adresse dieser Installation (``FRONTEND_BASE_URL``).
    website: str = ""
    #: Wer zu dieser Firma gehört – abgeleitet aus der Zuordnung an der Person.
    people: list[CompanyPerson] = []


class TerritoryRegion(BaseModel):
    """Eine Weltregion + ihr aktueller Besitzer (fakturierende Gesellschaft) für die Weltkarte."""
    code: str
    label: str
    pos: list[int]                            # grobe Kachel-Position [Spalte, Zeile]
    company_object_id: Optional[int] = None   # Besitzer (Betreiber-Default eingefüllt)


class TerritoryCompany(BaseModel):
    """Schlanke Gesellschaft für die Weltkarte (Picker + Färbung).

    Das Feld heisst **name**, nicht ``company_name``: es trägt den *Datensatznamen*
    (mit Rechtsform, ``sites.legal_name``) und nicht den Spaltenwert – zwei Dinge, die
    gleich hiessen und Verschiedenes meinten, sind die Verwechslung von morgen."""
    object_id: int
    name: str
    is_operator: bool = False


class TerritoryCountry(BaseModel):
    """Ein Land mit seinem **effektiven** Besitzer (Land-Ausnahme ≻ Region ≻ Betreiber).

    Ob ein Land eine **Ausnahme** ist, wird in der Oberfläche abgeleitet (sein Besitzer weicht
    vom Besitzer seiner Region ab) – kein eigenes Flag, das auseinanderlaufen könnte. Der Name
    kommt im Browser aus ``Intl.DisplayNames`` (keine zweite Länderliste im Frontend)."""
    code: str                                 # ISO-2
    region: str                               # Region, in der das Land liegt
    company_object_id: Optional[int] = None


class TerritoryMapResponse(BaseModel):
    """Die vollständige Gebietskarte: jede Region **und jedes Land** hat genau einen Besitzer
    (Betreiber-Default) – jeder Fleck der Erde gehört jemandem."""
    regions: list[TerritoryRegion]
    countries: list[TerritoryCountry] = []
    companies: list[TerritoryCompany]
    operator_object_id: Optional[int] = None


class TerritoryAssign(BaseModel):
    """Ein Gebiet (Region ODER einzelnes Land) einer Gesellschaft zuweisen. ``None`` (oder die
    Gesellschaft, der es ohnehin zufiele) = Standard wiederherstellen."""
    company_object_id: Optional[int] = Field(None, description="Objektnummer der eigenen Gesellschaft, der das Gebiet gehört; leer = Standard.")


class MissingField(BaseModel):
    """Eine fehlende Pflichtangabe: welches Feld, wie es heisst, wo es steht."""
    key: str
    label: str
    #: Wo sie steht: ``person`` (Stammdaten) oder ``adressen``.
    section: str


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    firebase_uid: str
    email: str
    photo_url: Optional[str]
    role: str
    # Anmeldeweg + Passkeys: beantwortet am ERP-Datensatz «wie kommt die Person herein?»
    # (google.com | password | emailLink | custom = Passkey). Rein deskriptiv.
    last_sign_in_provider: Optional[str] = None
    passkey_count: int = 0
    created_at: datetime
    updated_at: datetime

    # Personal identity
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]

    #: ►►► **Das Adressbuch** – beliebig viele Anschriften, je eine Standard-Liefer- und
    #: Standard-Rechnungsadresse (``services/address_book``).
    addresses: list[AddressOut] = []

    # Personal extras
    date_of_birth: Optional[date]
    competences: list[str] = []

    #: ►►► **Die Firma der Person** – eigene (dann arbeitet sie bei uns) oder fremde.
    company_object_id: Optional[int]
    company: Optional[CompanyRef] = None

    #: ►►► **Was im Profil noch fehlt** – die Regel steht EINMAL im Dienst
    #: (``people.missing_fields``); Konto und ERP spiegeln sie (Fortschritt, «zu tun»).
    required_fields: list[str] = []
    missing_fields: list["MissingField"] = []

    # Preferences
    language: str
    notification_email: bool
    notification_inapp: bool

    # Auth
    last_login_at: Optional[datetime]
    #: Darf, wer fragt, diese Person ändern? (``domain/policy``: Kunden jedes Personal,
    #: Mitarbeitende nur der Admin) – die Oberfläche fragt das, nicht die Rolle.
    may_edit: bool = False
    #: Darf, wer fragt, den Zugang dieser Person sehen und ändern (Passkeys, Verbindungen mit
    #: Claude)? (``domain/policy`` «person.access»: sie selbst und der Admin.)
    may_access: bool = False


class UserProfileUpdate(BaseModel):
    """Self-service update — only fields a user may edit themselves.
    Employment/role fields are intentionally excluded; use ErpAdminUpdate for those."""
    first_name: Optional[str] = Field(None, description="Vorname. Hat ein Partner keinen Menschen (ein Shop), nennt er die Rolle, z. B. «Bestellung».")
    last_name: Optional[str] = Field(None, description="Nachname. Bei einem Shop ohne Menschen der Shop, z. B. «Galaxus».")
    date_of_birth: Optional[date] = Field(None, description="Geburtsdatum (Personal: Pflicht für die Zeiterfassung).")
    phone: Optional[str] = Field(None, description="Telefon, international lesbar (z. B. +41 44 123 45 67).")

    # ─── Firma ─────────────────────────────────────────────────────────────────
    #: ►►► **Die Firma ist ein Datensatz.** ◄◄◄ Gewählt (``company_object_id``, ``None`` =
    #: Privatperson) oder genannt (``new_company`` → ``sites.resolve``). Ihre Angaben ändert
    #: man an ihrem Datensatz, nicht hier.
    company_object_id: Optional[int] = Field(None, description="Objektnummer der Firma, zu der die Person gehört; leer = Privatperson.")
    new_company: Optional[NewCompany] = Field(None, description="Statt einer Nummer: die Firma nennen – sie wird erkannt oder angelegt.")
    # ``notification_email``/``notification_inapp`` nimmt keine Seite mehr an: keine Oberfläche
    # zeigt sie, nichts liest sie – ein Wert, den nur das Konto schreiben konnte und das ERP nie sah
    # (``docs/history/2026-11-11-erp-master-pruefung.md``). Die Spalten bleiben (Backlog).


# Gültige Rollen – EINE Quelle (``PATCH /erp/records/{id}``, ``POST /erp/records``).
#
# ►►► **Die Rolle ist der ZUGANG, nichts weiter.** ◄◄◄ Lieferant ↔ Kunde ist eine Aussage
# über Vorgänge. Jedes Tor fragt ``policy.STAFF_ROLES``.
Role = Literal["admin", "employee", "user"]


class ErpAdminUpdate(UserProfileUpdate):
    """Was am **ERP-Benutzer-Datensatz** änderbar ist.

    **ERP ist Master:** das sind ALLE Felder, die die Person selbst pflegen kann
    (geerbt von ``UserProfileUpdate``) **plus** die Anstellungsdaten. Vorher war
    dies eine schmale Extra-Liste – das ERP konnte Name, Adresse, Firmenangaben und
    Bankverbindung nur ANZEIGEN, editieren konnte sie allein die Person in ihrem
    Konto. Damit lag die Wahrheit ausserhalb des ERP, also genau verkehrt herum.
    Durch die Vererbung kann die Liste auch nicht mehr auseinanderlaufen."""
    # Dieselbe Literal-Whitelist wie beim Anlegen – Rollen werden exakt verglichen.
    role: Optional[Role] = Field(None, description="Zugang: 'admin', 'employee' (Personal) oder 'user' (Kunde, Lieferant). Nur der Admin.")
    #: **Was die Person kann** (Projektakte «Aufgaben») – Wörter aus ``domain/competences``;
    #: nur am Personal, nur der Admin (Angaben von Mitarbeitenden, ``person.staff``).
    competences: Optional[list[str]] = Field(None, description="Was die Person kann (nur Personal, nur der Admin): Wörter aus der Liste der Kompetenzen.")


class PersonCreate(BaseModel):
    """►►► **Eine Person anlegen** – das Minimum ist Vorname, Nachname, E-Mail und Rolle.
    ◄◄◄ Sie bekommt sofort eine Objektnummer und ein Firebase-Konto; meldet sie sich
    später mit dieser E-Mail an, ist sie **dieser** Datensatz, samt Historie."""
    first_name: str = Field(description="Vorname. Ein Shop ohne Menschen heisst nach der Rolle, z. B. «Bestellung».")
    last_name: str = Field(description="Nachname. Bei einem Shop der Shop, z. B. «Galaxus».")
    email: str = Field(description="E-Mail – mit ihr meldet sie sich an und bekommt Belege.")
    role: Role = Field("user", description="'user' für Kunden und Lieferanten; Personal ('employee', 'admin') legt nur der Admin an.")
    company_object_id: Optional[int] = Field(None, description="Objektnummer der Firma, zu der sie gehört; leer = Privatperson.")
    new_company: Optional[NewCompany] = Field(None, description="Statt einer Nummer: die Firma nennen – sie wird erkannt oder angelegt.")
