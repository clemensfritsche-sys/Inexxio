// ─── API-abgeleitete Typen (Single Source of Truth) ──────────────────────────
//
// `api.ts` wird aus dem FastAPI-OpenAPI-Schema generiert:
//   cd backend && python -m scripts.dump_openapi   # → backend/openapi.json
//   cd frontend && npm run generate:types          # → src/types/api.ts
// NICHT von Hand editieren — stattdessen Backend-Schema ändern und neu generieren.

import type { components } from './api';

// ─── User ─────────────────────────────────────────────────────────────────────

export type UserPlatformRole = 'admin' | 'employee' | 'supplier' | 'customer';

type UserProfileApi = components['schemas']['UserProfileResponse'];

// Aus dem Backend-Schema abgeleitet; nur `role` wird auf die bekannte Union verengt.
export type UserProfile = Omit<UserProfileApi, 'role'> & {
  role: UserPlatformRole;
};

// ─── Article ────────────────────────────────────────────────────────────────

export type ArticleStatus = 'draft' | 'released' | 'inactive';
export type ArticleUnit = 'Stk' | 'mm' | 'm2' | 'kg' | 'l';
export type ArticleSerialization = 'unit' | 'batch';

type ArticleApi = components['schemas']['ArticleResponse'];

// Aus dem Backend-Schema abgeleitet; Status/Einheit/Serialisierung auf Unions verengt.
export type Article = Omit<ArticleApi, 'status' | 'unit' | 'serialization'> & {
  status: ArticleStatus;
  unit: ArticleUnit;
  serialization: ArticleSerialization;
};

// Eingaben für Anlage (alle Pflicht) bzw. Teil-Update aus dem Detailfenster.
export interface ArticleInput {
  name: string;
  unit: ArticleUnit;
  serialization: ArticleSerialization;
  size: string;
  weight_kg: string;
}

export type ArticleUpdateInput = Partial<ArticleInput> & {
  status?: ArticleStatus;
  is_active?: boolean;
};

// ─── Order (Auftrag) ──────────────────────────────────────────────────────────

export type OrderStatus = 'draft' | 'released' | 'inactive';

type OrderApi = components['schemas']['OrderResponse'];

// Aus dem Backend-Schema abgeleitet; nur `status` auf die bekannte Union verengt.
export type Order = Omit<OrderApi, 'status'> & {
  status: OrderStatus;
};

export interface OrderInput {
  title?: string | null;
}

export type OrderUpdateInput = {
  status?: OrderStatus;
  title?: string | null;
  is_active?: boolean;
};

// ─── Unified ERP record (Universal Feed) ──────────────────────────────────────

export type ErpRecordType = 'user' | 'article' | 'order';

// ─── Company Settings ─────────────────────────────────────────────────────────
//
// Bewusst NICHT aus dem Schema abgeleitet: die API liefert snake_case-Felder mit
// abweichenden Namen (zip_code, uid_number, bic_swift …); api.ts mappt sie auf
// diese camelCase-nahe Frontend-Sicht (mapSettingsFromBackend/ToBackend).

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

// ─── API response wrappers ────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages?: number;
}
