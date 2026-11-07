from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, computed_field


class CompanySettingsUpdate(BaseModel):
    """Änderbare Felder einer Firma. Die Kontakt-E-Mail einer eigenen Gesellschaft schreibt
    allein das Postfach (``mailbox._contact``).

    **Bewusst kurz** (Testnotizen #307/#313/#314/#317–#321): nur, was eine Logik trägt.
    Zahlungsziel und Skonto gehören zur **Offerte** (dort ist die Angabe verhandelbar),
    MWST-Methode/-Periode kommen mit der Buchhaltung (Phase 3), die sie auswertet.

    ``website`` fehlt hier absichtlich: die Adresse der Website ist **abgeleitet**
    (``sites.website_url`` = die Deployment-Adresse), keine Eingabe."""
    company_name: Optional[str] = None
    legal_form: Optional[str] = None
    street: Optional[str] = None
    street_nr: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
    currency: Optional[str] = None
    uid_number: Optional[str] = None
    vat_number: Optional[str] = None
    iban: Optional[str] = None
    phone: Optional[str] = None
    #: «Eigenes Unternehmen» – setzt nur ein Admin (``sites.apply_update``).
    is_own: Optional[bool] = None


class CompanyCreate(BaseModel):
    """Neue **Firma** anlegen: Name und Rechtsform (die Rechtsperson), die UID freiwillig.
    Alles Weitere wird danach am Datensatz gepflegt. ``is_own`` setzt nur ein Admin."""
    company_name: str
    legal_form: str = ""
    uid_number: Optional[str] = None
    is_own: bool = False


class EmailCheck(BaseModel):
    """Die neue Anmelde-E-Mail – gefragt, bevor der Bestätigungslink hinausgeht."""
    email: str


class AddressIn(BaseModel):
    """**Eine Anschrift im Adressbuch** – anlegen oder ändern (nur Gesendetes wirkt).

    ``is_default_*: true`` macht sie zum Standard; ``false`` ist keine Handlung – einen
    Standard nimmt man nicht weg, man gibt ihn einer anderen. ``account`` (``private`` ·
    ``business``) gilt nur beim Anlegen – das Konto einer Anschrift ändert sich nie; die
    ``email`` nur im Geschäftskonto."""
    account: Optional[str] = None
    street1: Optional[str] = None
    street2: Optional[str] = None
    zip: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country: Optional[str] = None
    email: Optional[str] = None
    is_default_delivery: Optional[bool] = None
    is_default_billing: Optional[bool] = None


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
    company_name: str = ""
    legal_form: str = ""
    uid_number: Optional[str] = None


class CompanySettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int] = None
    # **Abgeleitete** Rolle (kein gespeichertes Flag, kein Rang): ist dies das älteste
    # Unternehmen = der Betreiber der Website (Impressum/Systemkonfiguration/Fallback)?
    is_operator: bool = False
    # Trägt echte Ortsangaben? Ohne Anschrift ist eine Gesellschaft gültig, aber logistisch
    # stumm (eine Bewegung dorthin bleibt innerbetrieblich statt Versand – ADR 005).
    has_address: bool = False
    # Aktiv? Eine geschlossene Gesellschaft bleibt als Datensatz lesbar (Halter historischer
    # Instanzen, Absender alter Belege), ist aber nicht mehr verwendbar – und **endgültig**.
    is_active: bool = True
    #: Eine **unserer** Gesellschaften? Nur sie stellt Belege, beschäftigt Personal,
    #: besitzt Gebiete und kann Betreiber sein.
    is_own: bool = False
    company_name: str
    legal_form: str
    # ►►► **Der Datensatzname** – Unternehmensname, Abstand, Rechtsform (Testnotiz #910).
    # ◄◄◄ Eine **Projektion**, keine Spalte: die Regel (und die Ausnahme «Muster AG» +
    # «AG» = «Muster AG», nicht «Muster AG AG») steht genau einmal in
    # ``sites.legal_name``. Wer sie im Browser nachbaute, hätte die Ausnahme beim ersten
    # Mal vergessen – und die zweite Fassung sähe trotzdem richtig aus.
    legal_name: str = ""
    street: Optional[str]
    street_nr: Optional[str]
    zip_code: Optional[str]
    city: Optional[str]
    country: str
    currency: str = "CHF"
    uid_number: Optional[str]
    vat_number: Optional[str]
    # ►►► **Die eigene IBAN steht ausgeschrieben da** (Testnotiz #870). ◄◄◄
    #
    # **Sie ist kein Geheimnis.** Sie steht auf jeder Rechnung, die wir stellen, und im
    # QR-Code, den wir dem Zahlenden hinlegen – gegenüber genau den Personen, die sie hier
    # sehen (Admin). Maskiert wird, was der Empfänger nicht sehen **soll**; hier war es
    # das, was er sehen **muss**, um zu prüfen, ob es stimmt.
    iban: Optional[str] = None
    email: str
    phone: Optional[str]
    # **Abgeleitet, nicht gepflegt** (Testnotiz #309): die Adresse, unter der diese
    # Installation läuft (``FRONTEND_BASE_URL``). Sie steht im Impressum und auf dem
    # Beleg-Briefkopf – und wäre als Eingabefeld eine zweite Wahrheit neben dem Deployment.
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
    company_object_id: Optional[int] = None


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
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Personal identity
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]

    #: ►►► **Das Adressbuch** – beliebig viele Anschriften, je eine Standard-Liefer- und
    #: Standard-Rechnungsadresse (``services/address_book``). Die festen Felder
    #: ``address_*``/``invoice_*`` sind darin aufgegangen.
    addresses: list[AddressOut] = []

    # Personal extras
    date_of_birth: Optional[date]

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


class UserProfileUpdate(BaseModel):
    """Self-service update — only fields a user may edit themselves.
    Employment/role fields are intentionally excluded; use ErpAdminUpdate for those."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None

    # ─── Firma ─────────────────────────────────────────────────────────────────
    #: ►►► **Die Firma ist ein Datensatz** (CRM Schritt 1). ◄◄◄ Gewählt wird sie
    #: (``company_object_id``, ``None`` = Privatperson) oder genannt (``new_company`` –
    #: dann wird sie gefunden, wenn sie eindeutig dieselbe ist, sonst angelegt). Ihre
    #: **Angaben** ändert man an ihrem Datensatz, nicht hier: sonst änderte jeder Kunde
    #: die Firmendaten seiner Kollegen.
    company_object_id: Optional[int] = None
    new_company: Optional[NewCompany] = None

    # Preferences
    notification_email: Optional[bool] = None
    notification_inapp: Optional[bool] = None


# Gültige Rollen – EINE Quelle der Wahrheit (``PATCH /erp/records/{id}``,
# ``POST /erp/records``).
#
# ►►► **Die Rolle ist der ZUGANG, nichts weiter** (Testnotiz #1043). ◄◄◄ Lieferant ↔
# Kunde ist eine Aussage über **Vorgänge**, nicht über die Person. Jedes Tor im Haus fragt
# ``people.STAFF_ROLES``.
Role = Literal["admin", "employee", "user"]


class ErpAdminUpdate(UserProfileUpdate):
    """Was am **ERP-Benutzer-Datensatz** änderbar ist.

    **ERP ist Master:** das sind ALLE Felder, die die Person selbst pflegen kann
    (geerbt von ``UserProfileUpdate``) **plus** die Anstellungsdaten. Vorher war
    dies eine schmale Extra-Liste – das ERP konnte Name, Adresse, Firmenangaben und
    Bankverbindung nur ANZEIGEN, editieren konnte sie allein die Person in ihrem
    Konto. Damit lag die Wahrheit ausserhalb des ERP, also genau verkehrt herum.
    Durch die Vererbung kann die Liste auch nicht mehr auseinanderlaufen."""
    # FIX: ``role`` war hier ein freier String (anders als beim Rollen-Endpoint) – ein
    # Tippfehler wie "empoyee" hätte den Benutzer still aus allen Staff-Endpunkten
    # ausgesperrt (Rollen werden exakt verglichen). Jetzt dieselbe Literal-Whitelist.
    role: Optional[Role] = None


class PersonCreate(BaseModel):
    """►►► **Eine Person anlegen** – das Minimum ist Vorname, Nachname, E-Mail und Rolle.
    ◄◄◄ Sie bekommt sofort eine Objektnummer und ein Firebase-Konto; meldet sie sich
    später mit dieser E-Mail an, ist sie **dieser** Datensatz, samt Historie."""
    first_name: str
    last_name: str
    email: str
    role: Role = "user"
    company_object_id: Optional[int] = None
    new_company: Optional[NewCompany] = None
