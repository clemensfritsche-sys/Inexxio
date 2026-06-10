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
