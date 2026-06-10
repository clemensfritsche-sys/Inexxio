from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CompanySettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    legal_form: Optional[str] = None
    street: Optional[str] = None
    street_nr: Optional[str] = None
    zip_code: Optional[str] = None
    city: Optional[str] = None
    country: Optional[str] = None
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


class CompanySettingsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_name: str
    legal_form: str
    street: Optional[str]
    street_nr: Optional[str]
    zip_code: Optional[str]
    city: Optional[str]
    country: str
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


class UserProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    object_id: Optional[int]
    firebase_uid: str
    email: str
    photo_url: Optional[str]
    role: str
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

    # Unified shipping address
    ship_name: Optional[str] = None
    ship_company: Optional[str] = None
    ship_address_line1: Optional[str] = None
    ship_address_line2: Optional[str] = None
    ship_city: Optional[str] = None
    ship_postal_code: Optional[str] = None
    ship_state_region: Optional[str] = None
    ship_country: Optional[str] = None

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

    # Business / company info
    company_name: Optional[str] = None
    uid_number: Optional[str] = None
    vat_number: Optional[str] = None
    vat_registered: Optional[bool] = None
    trade_register_nr: Optional[str] = None
    trade_register_canton: Optional[str] = None
    company_website: Optional[str] = None
    company_billing_email: Optional[str] = None

    # Supplier bank details
    bank_account_holder: Optional[str] = None
    bank_iban: Optional[str] = None
    bank_bic: Optional[str] = None
    bank_name: Optional[str] = None

    # Employee
    department: Optional[str] = None
    job_title: Optional[str] = None
    employment_start_date: Optional[date] = None
    weekly_hours: Optional[Decimal] = None

    # Preferences
    language: Optional[str] = None
    notification_email: Optional[bool] = None
    notification_inapp: Optional[bool] = None
    newsletter_opt_in: Optional[bool] = None


class UserRoleUpdate(BaseModel):
    role: str
