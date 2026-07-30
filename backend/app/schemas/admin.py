from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict


class CompanySettingsUpdate(BaseModel):
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
    trade_register_nr: Optional[str] = None
    trade_register_canton: Optional[str] = None
    share_capital: Optional[str] = None
    iban: Optional[str] = None
    qr_iban: Optional[str] = None
    bank: Optional[str] = None
    bic_swift: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    vat_method: Optional[str] = None
    vat_period: Optional[str] = None
    default_payment_days: Optional[int] = None
    default_skonto_pct: Optional[Decimal] = None
    default_skonto_days: Optional[int] = None
    oss_active: Optional[bool] = None
    oss_reg_number: Optional[str] = None
    vies_active: Optional[bool] = None
    stripe_publishable_key: Optional[str] = None
    plausible_domain: Optional[str] = None
    hcaptcha_site_key: Optional[str] = None
    google_maps_api_key: Optional[str] = None
    # Shop / Verkauf
    shop_currencies: Optional[list[str]] = None
    shop_country_currency: Optional[dict] = None
    shop_default_currency: Optional[str] = None
    payments_provider: Optional[str] = None
    pricing_zone_factors: Optional[dict] = None
    infra_monthly_chf: Optional[Decimal] = None
    legal_documents: Optional[dict] = None


class CompanyCreate(BaseModel):
    """Neue **Gesellschaft** anlegen. Nur der Name ist Pflicht (zugleich das Halter-Label);
    alle übrigen Entitäts-Felder sind optional und werden danach am Datensatz gepflegt –
    wie jeder andere ERP-Datensatz auch (anlegen, dann ausfüllen)."""
    company_name: str


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
    company_name: str
    legal_form: str
    street: Optional[str]
    street_nr: Optional[str]
    zip_code: Optional[str]
    city: Optional[str]
    country: str
    currency: str = "CHF"
    uid_number: Optional[str]
    vat_number: Optional[str]
    trade_register_nr: Optional[str]
    trade_register_canton: Optional[str]
    share_capital: Optional[str]
    iban_masked: Optional[str] = None
    qr_iban_masked: Optional[str] = None
    bank: Optional[str]
    bic_swift: Optional[str]
    email: str
    phone: Optional[str]
    website: str
    vat_method: str
    vat_period: str
    default_payment_days: int
    default_skonto_pct: Optional[Decimal]
    default_skonto_days: Optional[int]
    oss_active: bool
    oss_reg_number: Optional[str]
    vies_active: bool
    logo_path: Optional[str]
    stripe_publishable_key: Optional[str]
    plausible_domain: Optional[str]
    hcaptcha_site_key: Optional[str]
    google_maps_api_key: Optional[str]
    # Shop / Verkauf
    shop_currencies: Optional[list[str]] = None
    shop_country_currency: Optional[dict] = None
    shop_default_currency: str = "CHF"
    payments_provider: Optional[str] = None
    pricing_zone_factors: Optional[dict] = None
    infra_monthly_chf: Optional[Decimal] = None
    # Öffentliche Rechtsdokumente (D): {"agb": <Artikel-Objektnr>, "datenschutz": …}
    legal_documents: Optional[dict] = None
    # Bestätigungspflicht je Dokument-Art: {"agb": ["all"], …} (Consent-Gate)


class TerritoryRegion(BaseModel):
    """Eine Weltregion + ihr aktueller Besitzer (fakturierende Gesellschaft) für die Weltkarte."""
    code: str
    label: str
    pos: list[int]                            # grobe Kachel-Position [Spalte, Zeile]
    company_object_id: Optional[int] = None   # Besitzer (Betreiber-Default eingefüllt)


class TerritoryCompany(BaseModel):
    """Schlanke Gesellschaft für die Weltkarte (Picker + Färbung)."""
    object_id: int
    company_name: str
    is_operator: bool = False


class TerritoryMapResponse(BaseModel):
    """Die vollständige Gebietskarte: jede Region hat genau einen Besitzer (Betreiber-Default)."""
    regions: list[TerritoryRegion]
    companies: list[TerritoryCompany]
    operator_object_id: Optional[int] = None


class TerritoryAssign(BaseModel):
    """Eine Region einer Gesellschaft zuweisen. ``None`` (oder der Betreiber) = Default."""
    company_object_id: Optional[int] = None


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

    # Contact address
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    state_region: Optional[str]
    country: str

    # Unified shipping address
    ship_name: Optional[str]
    ship_company: Optional[str]
    ship_address_line1: Optional[str]
    ship_address_line2: Optional[str]
    ship_city: Optional[str]
    ship_postal_code: Optional[str]
    ship_state_region: Optional[str]
    ship_country: Optional[str]

    # Invoice
    invoice_company: Optional[str]
    invoice_first_name: Optional[str]
    invoice_last_name: Optional[str]
    invoice_address_line1: Optional[str]
    invoice_address_line2: Optional[str]
    invoice_city: Optional[str]
    invoice_postal_code: Optional[str]
    invoice_country: Optional[str]
    invoice_email: Optional[str]
    invoice_same_as_shipping: bool

    # Personal extras
    date_of_birth: Optional[date]

    # Business / company info
    company_name: Optional[str]
    uid_number: Optional[str]
    vat_number: Optional[str]
    vat_registered: bool
    trade_register_nr: Optional[str]
    trade_register_canton: Optional[str]
    company_website: Optional[str]
    company_billing_email: Optional[str]

    # Supplier bank details
    bank_account_holder: Optional[str]
    bank_iban: Optional[str]
    bank_bic: Optional[str]
    bank_name: Optional[str]

    # Employee
    department: Optional[str]
    job_title: Optional[str]
    employment_start_date: Optional[date]
    weekly_hours: Optional[Decimal]

    # Preferences
    language: str
    notification_email: bool
    notification_inapp: bool
    newsletter_opt_in: bool

    # Auth
    last_login_at: Optional[datetime]
    terms_accepted_at: Optional[datetime]
    terms_version: Optional[str]


class UserProfileUpdate(BaseModel):
    """Self-service update — only fields a user may edit themselves.
    Employment/role fields are intentionally excluded; use ErpAdminUpdate for those."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    phone: Optional[str] = None

    # Contact address
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    state_region: Optional[str] = None
    country: Optional[str] = None

    # Invoice / billing address
    invoice_company: Optional[str] = None
    invoice_first_name: Optional[str] = None
    invoice_last_name: Optional[str] = None
    invoice_address_line1: Optional[str] = None
    invoice_address_line2: Optional[str] = None
    invoice_city: Optional[str] = None
    invoice_postal_code: Optional[str] = None
    invoice_country: Optional[str] = None
    invoice_email: Optional[str] = None
    invoice_same_as_shipping: Optional[bool] = None

    # Business / company info (supplier-visible fields)
    company_name: Optional[str] = None
    uid_number: Optional[str] = None
    company_billing_email: Optional[str] = None

    # Supplier bank details
    bank_account_holder: Optional[str] = None
    bank_iban: Optional[str] = None
    bank_bic: Optional[str] = None
    bank_name: Optional[str] = None

    # Preferences
    notification_email: Optional[bool] = None
    notification_inapp: Optional[bool] = None
    newsletter_opt_in: Optional[bool] = None


# Gültige Rollen – EINE Quelle der Wahrheit für beide Rollen-Endpunkte
# (PATCH /admin/users/{id}/role und PATCH /erp/records/{id}).
Role = Literal["admin", "employee", "supplier", "customer"]


class UserRoleUpdate(BaseModel):
    role: Role


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
    department: Optional[str] = None
    job_title: Optional[str] = None
    employment_start_date: Optional[date] = None
    weekly_hours: Optional[Decimal] = None


# ─── Betriebskosten (Monat-bis-heute, tatsächlich wo messbar) ────────────────────
class CostItem(BaseModel):
    label: str
    value_chf: float
    hint: Optional[str] = None


class CostGroup(BaseModel):
    key: str            # ai | payments | infrastructure
    label: str
    total_chf: float    # Monat-bis-heute
    basis: str          # 'actual' (gemessen) | 'estimate' (geschätzt)
    items: list[CostItem] = []


class OperatingCostsResponse(BaseModel):
    """Betriebskosten des laufenden Monats bis heute (tatsächlich, wo messbar) +
    Hochrechnung aufs Monatsende."""
    period_label: str          # z. B. «Juli 2026»
    day_of_month: int
    days_in_month: int
    groups: list[CostGroup] = []
    total_mtd_chf: float
    projected_month_chf: float
