// ─── Core domain types ────────────────────────────────────────────────────────

export type ObjectType = 'item' | 'bom' | 'work_plan' | 'company' | 'contact' | 'user';

export type ItemStatus = 'Entwurf' | 'Freigegeben' | 'Ersetzt' | 'Gesperrt';
export type CompanyRole = 'Kunde' | 'Lieferant' | 'Interessent' | 'Partner';
export type WorkPlanStatus = 'Entwurf' | 'Aktiv' | 'Archiviert';
export type BOMStatus = 'Entwurf' | 'Freigegeben' | 'Archiviert';

// ─── Item ─────────────────────────────────────────────────────────────────────

export interface Item {
  id: number;
  number: string; // 9-digit padded
  name: string;
  description: string | null;
  unit: string;
  item_type: 'Kauf' | 'Eigen' | 'Phantom';
  status: ItemStatus;
  weight_kg: number | null;
  dimensions: string | null;
  material: string | null;
  surface_finish: string | null;
  tolerance_class: string | null;
  drawing_number: string | null;
  manufacturer: string | null;
  manufacturer_part_number: string | null;
  lead_time_days: number | null;
  cost_price: string | null; // Decimal as string
  sales_price: string | null;
  currency: string;
  tags: string[];
  created_at: string; // ISO datetime
  updated_at: string;
  created_by: string | null;
}

// ─── BOM (Bill of Materials) ──────────────────────────────────────────────────

export interface BOMLine {
  id: number;
  bom_id: number;
  position: number;
  item_id: number;
  item?: Item;
  quantity: string; // Decimal as string
  unit: string;
  notes: string | null;
}

export interface BOM {
  id: number;
  number: string;
  name: string;
  description: string | null;
  status: BOMStatus;
  parent_item_id: number | null;
  parent_item?: Item;
  lines: BOMLine[];
  version: number;
  valid_from: string | null;
  valid_until: string | null;
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

// ─── Work Plan ────────────────────────────────────────────────────────────────

export interface WorkPlanStep {
  id: number;
  work_plan_id: number;
  step_number: number;
  name: string;
  description: string | null;
  work_center: string | null;
  machine: string | null;
  setup_time_min: number | null;
  run_time_min: number | null;
  tools: string[];
  notes: string | null;
}

export interface WorkPlan {
  id: number;
  number: string;
  name: string;
  description: string | null;
  status: WorkPlanStatus;
  item_id: number | null;
  item?: Item;
  steps: WorkPlanStep[];
  version: number;
  created_at: string;
  updated_at: string;
  created_by: string | null;
}

// ─── Company / Contact ────────────────────────────────────────────────────────

export interface Address {
  street: string;
  street_number: string | null;
  zip: string;
  city: string;
  country: string;
  country_code: string;
}

export interface Company {
  id: number;
  number: string;
  name: string;
  legal_form: string | null;
  role: CompanyRole;
  is_active: boolean;
  address: Address | null;
  uid: string | null;
  vat_number: string | null;
  website: string | null;
  email: string | null;
  phone: string | null;
  notes: string | null;
  payment_terms_days: number | null;
  discount_percent: string | null;
  created_at: string;
  updated_at: string;
}

export interface Contact {
  id: number;
  number: string;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  mobile: string | null;
  title: string | null;
  department: string | null;
  position: string | null;
  company_id: number | null;
  company?: Company;
  is_active: boolean;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

// ─── Company Settings ─────────────────────────────────────────────────────────

export interface CompanySettings {
  // General
  company_name: string;
  legal_form: string | null;
  street: string;
  street_number: string | null;
  zip: string;
  city: string;
  country: string;
  // Legal IDs
  uid: string | null;
  vat_number: string | null;
  trade_register_number: string | null;
  trade_register_canton: string | null;
  share_capital: string | null;
  // Contact & web
  email: string;
  phone: string | null;
  website: string;
  logo_url: string | null;
  // Banking (masked for non-admins)
  iban: string | null;
  iban_masked: string | null;
  qr_iban: string | null;
  qr_iban_masked: string | null;
  bank_name: string | null;
  bic: string | null;
  // VAT
  vat_method: 'effektiv' | 'saldosteuersatz' | null;
  vat_period: 'quartal' | 'semester' | 'jahr' | null;
  default_payment_days: number;
  default_discount_percent: string | null;
  default_discount_days: number | null;
  // EU
  oss_active: boolean;
  oss_number: string | null;
  vies_validation: boolean;
  // Integrations
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
  display_name: string | null;
  photo_url: string | null;
  role: UserPlatformRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;

  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  phone_mobile: string | null;

  address_line1: string | null;
  address_line2: string | null;
  city: string | null;
  postal_code: string | null;
  state_canton: string | null;
  country: string;

  ship_b2c_first_name: string | null;
  ship_b2c_last_name: string | null;
  ship_b2c_address_line1: string | null;
  ship_b2c_address_line2: string | null;
  ship_b2c_city: string | null;
  ship_b2c_postal_code: string | null;
  ship_b2c_country: string | null;

  ship_b2b_company: string | null;
  ship_b2b_contact: string | null;
  ship_b2b_address_line1: string | null;
  ship_b2b_address_line2: string | null;
  ship_b2b_city: string | null;
  ship_b2b_postal_code: string | null;
  ship_b2b_country: string | null;

  invoice_company: string | null;
  invoice_first_name: string | null;
  invoice_last_name: string | null;
  invoice_address_line1: string | null;
  invoice_address_line2: string | null;
  invoice_city: string | null;
  invoice_postal_code: string | null;
  invoice_country: string | null;
  invoice_vat_id: string | null;
  invoice_email: string | null;

  salutation: string | null;
  date_of_birth: string | null;

  company_name: string | null;
  company_legal_form: string | null;
  uid_number: string | null;
  vat_number: string | null;
  vat_registered: boolean;
  trade_register_nr: string | null;
  trade_register_canton: string | null;
  company_website: string | null;
  company_billing_email: string | null;

  customer_group: string | null;
  credit_limit: string | null;
  accepts_marketing: boolean;

  stripe_customer_id: string | null;

  department: string | null;
  job_title: string | null;
  employment_start_date: string | null;
  weekly_hours: string | null;

  language: string;
  timezone: string;
  notification_email: boolean;
  notification_inapp: boolean;
  newsletter_opt_in: boolean;

  last_login_at: string | null;
  terms_accepted_at: string | null;
  terms_version: string | null;
}

// ─── Universal ERP Object ─────────────────────────────────────────────────────

export interface UniversalObject {
  id: number;
  object_type: ObjectType;
  title: string;
  subtitle: string | null;
  status: string;
  number: string;
  created_at: string;
  updated_at: string;
  // Polymorphic payload
  data?: Item | BOM | WorkPlan | Company | Contact | UserProfile;
}

// ─── API response wrappers ────────────────────────────────────────────────────

export interface ApiResponse<T> {
  data: T;
  message?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface ApiError {
  error: string;
  code: string;
  detail?: string;
}

// ─── Audit log ────────────────────────────────────────────────────────────────

export interface AuditEntry {
  id: number;
  object_type: ObjectType;
  object_id: number;
  action: 'created' | 'updated' | 'deleted' | 'status_changed';
  user_email: string;
  changes: Record<string, { from: unknown; to: unknown }> | null;
  created_at: string;
}

// ─── Filter / query ───────────────────────────────────────────────────────────

export interface ObjectFilter {
  q?: string;
  object_type?: ObjectType;
  status?: string;
  page?: number;
  page_size?: number;
}
