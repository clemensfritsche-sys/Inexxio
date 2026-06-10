// ─── Company Settings ─────────────────────────────────────────────────────────

export interface CompanySettings {
  company_name: string;
  legal_form: string | null;
  street: string;
  street_number: string | null;
  zip: string;
  city: string;
  country: string;
  uid: string | null;
  vat_number: string | null;
  trade_register_number: string | null;
  trade_register_canton: string | null;
  share_capital: string | null;
  email: string;
  phone: string | null;
  website: string;
  logo_url: string | null;
  iban: string | null;
  iban_masked: string | null;
  qr_iban: string | null;
  qr_iban_masked: string | null;
  bank_name: string | null;
  bic: string | null;
  vat_method: 'effektiv' | 'saldosteuersatz' | null;
  vat_period: 'quartal' | 'semester' | 'jahr' | null;
  default_payment_days: number;
  default_discount_percent: string | null;
  default_discount_days: number | null;
  oss_active: boolean;
  oss_number: string | null;
  vies_validation: boolean;
  stripe_publishable_key: string | null;
  plausible_domain: string | null;
  hcaptcha_site_key: string | null;
}

// ─── User ─────────────────────────────────────────────────────────────────────

export type UserPlatformRole = 'admin' | 'employee' | 'supplier' | 'customer';

export interface UserProfile {
  id: number;
  object_id: number | null;
  firebase_uid: string;
  email: string;
  photo_url: string | null;
  role: UserPlatformRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;

  // Personal
  first_name: string | null;
  last_name: string | null;
  date_of_birth: string | null;
  phone: string | null;

  // Contact address (international)
  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  postal_code: string | null;
  state_region: string | null;
  country: string;

  // Unified shipping address
  ship_name: string | null;
  ship_company: string | null;
  ship_address_line1: string | null;
  ship_address_line2: string | null;
  ship_city: string | null;
  ship_postal_code: string | null;
  ship_state_region: string | null;
  ship_country: string | null;

  // Invoice / billing
  invoice_company: string | null;
  invoice_first_name: string | null;
  invoice_last_name: string | null;
  invoice_address_line1: string | null;
  invoice_address_line2: string | null;
  invoice_city: string | null;
  invoice_postal_code: string | null;
  invoice_country: string | null;
  invoice_email: string | null;
  invoice_same_as_shipping: boolean;

  // Company (B2B)
  company_name: string | null;
  uid_number: string | null;
  vat_number: string | null;
  vat_registered: boolean;
  trade_register_nr: string | null;
  trade_register_canton: string | null;
  company_website: string | null;
  company_billing_email: string | null;

  // Supplier bank details
  bank_account_holder: string | null;
  bank_iban: string | null;
  bank_bic: string | null;
  bank_name: string | null;

  // Employee
  department: string | null;
  job_title: string | null;
  employment_start_date: string | null;
  weekly_hours: string | null;

  // Preferences
  language: string;
  notification_email: boolean;
  notification_inapp: boolean;
  newsletter_opt_in: boolean;

  // Auth / compliance
  last_login_at: string | null;
  terms_accepted_at: string | null;
  terms_version: string | null;
}

// ─── API response wrappers ────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages?: number;
}
