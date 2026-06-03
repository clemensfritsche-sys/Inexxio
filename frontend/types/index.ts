// Shared TypeScript types – kept in sync with backend Pydantic schemas

export type UserRole = "admin" | "employee" | "supplier" | "customer";

export interface UserProfile {
  id: number;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: UserRole;
  language: string;
  avatar_url: string | null;
  totp_enabled: boolean;
}

export type SerialMode = "unit" | "batch";
export type PurchaseType = "one_time" | "subscription" | "both";

export interface Item {
  id: number;
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
  purchase_type: PurchaseType | null;
  list_price_chf: number | null;
  hs_code: string | null;
  min_stock: number | null;
  reorder_point: number | null;
  max_stock: number | null;
  preferred_supplier_id: number | null;
  lead_time_days: number | null;
  is_approved: boolean;
  approved_by: number | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
  is_active: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

export interface ApiError {
  error: string;
  code: string;
  details?: unknown;
}

export type CompanyType = "customer" | "supplier" | "both";

export interface Company {
  id: number;
  name: string;
  company_type: CompanyType;
  uid: string | null;
  vat_id: string | null;
  country_code: string;
  payment_term_days: number;
  is_active: boolean;
}
