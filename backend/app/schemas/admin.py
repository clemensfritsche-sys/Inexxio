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
    display_name: Optional[str]
    photo_url: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    # Personal identity
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    phone_mobile: Optional[str]

    # Contact address
    address_line1: Optional[str]
    address_line2: Optional[str]
    city: Optional[str]
    postal_code: Optional[str]
    state_canton: Optional[str]
    country: str

    # Shipping B2C
    ship_b2c_first_name: Optional[str]
    ship_b2c_last_name: Optional[str]
    ship_b2c_address_line1: Optional[str]
    ship_b2c_address_line2: Optional[str]
    ship_b2c_city: Optional[str]
    ship_b2c_postal_code: Optional[str]
    ship_b2c_country: Optional[str]

    # Shipping B2B
    ship_b2b_company: Optional[str]
    ship_b2b_contact: Optional[str]
    ship_b2b_address_line1: Optional[str]
    ship_b2b_address_line2: Optional[str]
    ship_b2b_city: Optional[str]
    ship_b2b_postal_code: Optional[str]
    ship_b2b_country: Optional[str]

    # Invoice
    invoice_company: Optional[str]
    invoice_first_name: Optional[str]
    invoice_last_name: Optional[str]
    invoice_address_line1: Optional[str]
    invoice_address_line2: Optional[str]
    invoice_city: Optional[str]
    invoice_postal_code: Optional[str]
    invoice_country: Optional[str]
    invoice_vat_id: Optional[str]
    invoice_email: Optional[str]

    # Payment
    payment_terms: int
    stripe_customer_id: Optional[str]
    preferred_currency: str

    # Employee
    department: Optional[str]
    job_title: Optional[str]
    employee_number: Optional[str]
    employment_start_date: Optional[date]
    weekly_hours: Optional[Decimal]

    # Preferences
    language: str
    timezone: str
    notification_email: bool
    notification_inapp: bool
    newsletter_opt_in: bool

    # Auth
    last_login_at: Optional[datetime]
    terms_accepted_at: Optional[datetime]
    terms_version: Optional[str]


class UserProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    job_title: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    notification_email: Optional[bool] = None
    notification_inapp: Optional[bool] = None


class UserRoleUpdate(BaseModel):
    role: str
