/**
 * Shared TypeScript types for Inexxio Enterprise Central System
 * Used by both frontend and any TypeScript tooling.
 */

// ─── Universal Object System ─────────────────────────────────────────────────

export type ObjectType =
  | 'item'
  | 'bom'
  | 'work_plan'
  | 'production_order'
  | 'purchase_order'
  | 'sales_order'
  | 'serialization'
  | 'complaint'
  | 'maintenance_order'
  | 'audit'
  | 'capa'
  | 'risk'
  | 'document'
  | 'company'
  | 'contact'
  | 'invoice'
  | 'credit_note';

export interface UniversalObject {
  id: number;
  object_type: ObjectType;
  created_at: string;
  updated_at: string;
  created_by: number | null;
  updated_by: number | null;
  is_active: boolean;
}

export interface FeedItem {
  id: number;
  object_type: ObjectType;
  title: string;
  status: string;
  created_at: string;
  updated_at?: string;
}

// ─── Items ───────────────────────────────────────────────────────────────────

export type SerialMode = 'unit' | 'batch';
export type PurchaseType = 'one_time' | 'subscription' | 'both';

export interface Item extends UniversalObject {
  name: string;
  description: string | null;
  size: string | null;
  unit: string;
  category: string | null;
  is_equipment: boolean;
  serial_mode: SerialMode;
  replaced_by_id: number | null;
  replaces_id: number | null;
  is_sales_product: boolean;
  shop_description: string | null;
  purchase_type: PurchaseType;
  list_price_chf: string | null;
  hs_code: string | null;
  min_stock: string | null;
  reorder_point: string | null;
  max_stock: string | null;
  preferred_supplier_id: number | null;
  lead_time_days: number | null;
  is_approved: boolean;
  approved_by: number | null;
  approved_at: string | null;
  current_stock: string;
}

export interface ItemCreate {
  name: string;
  description?: string;
  size?: string;
  unit?: string;
  category?: string;
  is_equipment?: boolean;
  serial_mode?: SerialMode;
  is_sales_product?: boolean;
  shop_description?: string;
  purchase_type?: PurchaseType;
  list_price_chf?: number;
  hs_code?: string;
  min_stock?: number;
  reorder_point?: number;
  max_stock?: number;
  preferred_supplier_id?: number;
  lead_time_days?: number;
}

// ─── BOM ─────────────────────────────────────────────────────────────────────

export interface BOMLine {
  id: number;
  bom_id: number;
  component_item_id: number;
  quantity: string;
  unit: string;
  position: number;
  note: string | null;
}

export interface BOM extends UniversalObject {
  parent_item_id: number;
  note: string | null;
  lines: BOMLine[];
}

export interface BOMCreate {
  parent_item_id: number;
  note?: string;
  lines?: BOMLineCreate[];
}

export interface BOMLineCreate {
  component_item_id: number;
  quantity: number;
  unit?: string;
  position?: number;
  note?: string;
}

// ─── Work Plans ──────────────────────────────────────────────────────────────

export type StepType = 'operation' | 'qc_check';

export interface WorkPlanStep {
  id: number;
  work_plan_id: number;
  step_nr: number;
  step_type: StepType;
  name: string;
  resource: string | null;
  setup_min: string | null;
  exec_min_per_unit: string | null;
  nominal_value: string | null;
  tolerance: string | null;
  unit: string | null;
  is_mandatory: boolean;
}

export interface WorkPlan extends UniversalObject {
  item_id: number | null;
  name: string;
  description: string | null;
  steps: WorkPlanStep[];
}

// ─── Companies & Contacts ────────────────────────────────────────────────────

export type CompanyType = 'customer' | 'supplier' | 'both';

export interface Address {
  street?: string;
  street_nr?: string;
  zip_code?: string;
  city?: string;
  country?: string;
}

export interface Company extends UniversalObject {
  name: string;
  company_type: CompanyType;
  uid: string | null;
  vat_id: string | null;
  vat_validated_at: string | null;
  address: Address | null;
  country_code: string;
  iban: string | null;
  payment_term_days: number;
  notes: string | null;
}

export interface Contact extends UniversalObject {
  company_id: number;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  role: string | null;
  is_primary: boolean;
}

// ─── Admin / Company Settings ────────────────────────────────────────────────

export interface CompanySettings {
  id: number;
  company_name: string;
  legal_form: string;
  street: string | null;
  street_nr: string | null;
  zip_code: string | null;
  city: string | null;
  country: string;
  uid_number: string | null;
  vat_number: string | null;
  trade_register_nr: string | null;
  trade_register_canton: string | null;
  share_capital: string | null;
  iban_masked: string | null;
  qr_iban_masked: string | null;
  bank: string | null;
  bic_swift: string | null;
  email: string;
  phone: string | null;
  website: string;
  vat_method: string;
  vat_period: string;
  default_payment_days: number;
  default_skonto_pct: string | null;
  default_skonto_days: number | null;
  oss_active: boolean;
  oss_reg_number: string | null;
  vies_active: boolean;
  logo_path: string | null;
  stripe_publishable_key: string | null;
  plausible_domain: string | null;
  hcaptcha_site_key: string | null;
}

export interface PublicCompanyInfo {
  company_name: string;
  legal_form: string;
  street: string | null;
  street_nr: string | null;
  zip_code: string | null;
  city: string | null;
  country: string;
  uid_number: string | null;
  vat_number: string | null;
  trade_register_nr: string | null;
  trade_register_canton: string | null;
  share_capital: string | null;
  email: string;
  phone: string | null;
  website: string;
}

// ─── Users & Auth ────────────────────────────────────────────────────────────

export type UserRole = 'admin' | 'staff' | 'supplier' | 'customer';

export interface UserProfile {
  id: number;
  firebase_uid: string;
  email: string;
  display_name: string | null;
  photo_url: string | null;
  role: UserRole;
  phone: string | null;
  department: string | null;
  job_title: string | null;
  language: string;
  is_active: boolean;
}

// ─── API Responses ───────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  items: T[];
}

export interface ApiError {
  error: string;
  code: string;
  details?: unknown;
}

// ─── ERP Status Maps ─────────────────────────────────────────────────────────

export const ITEM_STATUS_LABELS: Record<string, string> = {
  draft: 'Entwurf',
  approved: 'Freigegeben',
  obsolete: 'Veraltet',
};

export const OBJECT_TYPE_LABELS: Record<ObjectType, string> = {
  item: 'Artikel',
  bom: 'Stückliste',
  work_plan: 'Arbeitsplan',
  production_order: 'Produktionsauftrag',
  purchase_order: 'Bestellung',
  sales_order: 'Kundenauftrag',
  serialization: 'Serialisierung',
  complaint: 'Reklamation',
  maintenance_order: 'Wartungsauftrag',
  audit: 'Audit',
  capa: 'CAPA',
  risk: 'Risiko',
  document: 'Dokument',
  company: 'Firma',
  contact: 'Kontakt',
  invoice: 'Rechnung',
  credit_note: 'Gutschrift',
};

export const COMPANY_TYPE_LABELS: Record<CompanyType, string> = {
  customer: 'Kunde',
  supplier: 'Lieferant',
  both: 'Kunde & Lieferant',
};
