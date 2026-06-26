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
  // Optionale Stammdaten (dynamische Feldliste, nur bei Bedarf)
  material?: string | null;
  cad_url?: string | null;
  surface?: string | null;
  supplier_article_number?: string | null;
  min_order_qty?: string | null;
  safety_stock?: string | null;
}

export type ArticleUpdateInput = Partial<ArticleInput> & {
  status?: ArticleStatus;
  is_active?: boolean;
  expected_updated_at?: string | null;   // Optimistic Locking
};

// ─── Order (Auftrag) ──────────────────────────────────────────────────────────

export type OrderStatus = 'draft' | 'released' | 'inactive' | 'completed';

type OrderApi = components['schemas']['OrderResponse'];

// Eingebetteter Beschaffungsschritt des Auftrags (läuft unter der Auftragsnummer).
export type OrderPurchase = Omit<NonNullable<OrderApi['purchase']>, 'status' | 'mode'> & {
  status: PurchaseOrderStatus;
  mode: ProcessStepMode;
};

// Aus dem Backend-Schema abgeleitet; Status verengt, Prozess-Embed eingehängt.
export type Order = Omit<OrderApi, 'status' | 'purchase'> & {
  status: OrderStatus;
  purchase: OrderPurchase | null;
};

// Schlanke Feed-Sicht (ohne Embeds) – Detail kommt on-demand via getOrder(id).
type OrderSummaryApi = components['schemas']['OrderSummary'];
export type OrderSummary = Omit<OrderSummaryApi, 'status'> & { status: OrderStatus };

// Auftrag-Prozess (Stepper + eingebettete Schritt-Ausführungen)
// EIN «resource»-Schritt fasst Verbrauch & Betriebsmittel zusammen; pro Zeile ein Modus.
export type StepType = 'purchase' | 'inspection' | 'movement' | 'resource' | 'sale';
export type ResourceMode = 'consume' | 'tool';
export type OrderStepState = 'done' | 'active' | 'locked' | 'failed';
export type OrderStep = OrderApi['steps'][number];
export type OrderInstance = NonNullable<OrderApi['instances']>[number];
export type OrderInspection = NonNullable<OrderApi['inspection']>;
export type OrderMovement = NonNullable<OrderApi['movement']>;
export type OrderResource = NonNullable<OrderApi['resource']>;
export type OrderResourceLine = OrderResource['lines'][number];

export interface ResourceToolPickInput {
  article_id: number;
  instance_ids: number[];
}

export interface ResourceUpdateInput {
  tools: ResourceToolPickInput[];
  note?: string | null;
  step_id?: number | null;   // konkrete Schritt-Definition (Mehr-Operationen-Routing)
}

// Verbrauch je Produkt-Instanz (welche Komponenten-Instanz wird wohin verbaut)
export type OrderResourceProduct = NonNullable<OrderResource['products']>[number];
export type OrderResourceComponent = NonNullable<OrderResourceProduct['components']>[number];

// Standort einer Instanz (Bewegung) – immer ein Datensatzobjekt mit Nummer
export type LocationType = 'lagerplatz' | 'user' | 'instance';

export interface MovementTargetInput {
  instance_id: number;       // object_id der Instanz
  location_type: LocationType;
  location_id: number;       // object_id des Zielobjekts
}

export interface MovementUpdateInput {
  targets: MovementTargetInput[];
  note?: string | null;
  step_id?: number | null;   // konkrete Schritt-Definition (Mehr-Operationen-Routing)
}

export type CaptureField = components['schemas']['CaptureField'];
export type CaptureFieldType = 'measure' | 'bool' | 'text';

// Konkrete Stichprobe der Datenerfassung (Instanz + erfasste Werte)
export type InspectionSample = NonNullable<OrderApi['inspection']>['samples'][number];

export interface InspectionSampleInput {
  instance_id: number;
  slot: number;
  values: Record<string, unknown>;
}

export interface InspectionUpdateInput {
  samples: InspectionSampleInput[];
  note?: string | null;
  step_id?: number | null;   // konkrete Schritt-Definition (Mehr-Operationen-Routing)
}

// Bestands-Instanz (Reiter «Bestand» am Artikel)
type InstanceApi = components['schemas']['InstanceResponse'];
export type Instance = InstanceApi;
// qc_status in zwei orthogonale Achsen getrennt (siehe Backend domain/event_types):
export type InstanceQuality = 'pending' | 'passed' | 'failed';                       // «ist es gut?»
export type InstanceDisposition = 'in_process' | 'in_stock' | 'consumed' | 'sold' | 'scrapped'; // «wo ist es?»
export type InstanceReference = components['schemas']['InstanceReference'];

// Inaktiv setzen / Ersetzen (ohne Versionierung)
export type DeactivationImpact = components['schemas']['DeactivationImpact'];
export type OrdersMode = 'phase_out' | 'cancel';

// Wiederkehrend ist eine Eigenschaft des Auftrags (kein eigenes Objekt mehr).
export interface OrderRecurrenceInput {
  recurrence_active?: boolean | null;
  recurrence_interval_days?: number | null;
  recurrence_lead_time_days?: number | null;
  recurrence_anchor?: string | null;
}

export interface OrderInput extends OrderRecurrenceInput {
  article_id?: number | null;
  quantity?: number | null;
  desired_delivery_date?: string | null;
  process_id?: number | null;
  subject_instance_id?: number | null;
}

export type OrderUpdateInput = OrderRecurrenceInput & {
  status?: OrderStatus;
  article_id?: number | null;
  quantity?: number | null;
  desired_delivery_date?: string | null;
  process_id?: number | null;
  subject_instance_id?: number | null;
  is_active?: boolean;
  expected_updated_at?: string | null;   // Optimistic Locking
};

// ─── Prozess = Schritte am Artikel (Entstehung) ODER am Auftrag (CUSTOM) ───────
// Es gibt KEIN eigenständiges Prozess-Objekt mehr. Auftrags-Modus:
export type OrderMode = 'make' | 'custom';

// ─── Verkaufsschritt (Spiegel der Beschaffung) ─────────────────────────────────

export type OrderSale = NonNullable<OrderApi['sale']>;
export type SaleStatus = 'requested' | 'confirmed' | 'invoiced' | 'paid' | 'cancelled';

export interface SaleUpdateInput {
  status?: SaleStatus;
  order_total?: number | string | null;
  vat_rate?: number | string | null;
  currency?: string | null;
  customer_id?: number | null;
  invoice_number?: string | null;
  step_id?: number | null;
}


// ─── Article Process Steps (Prozess-Definition) ───────────────────────────────

export type ProcessStepMode = 'supplier' | 'webshop';

type ArticleProcessStepApi = components['schemas']['ArticleProcessStepResponse'];

export type ArticleProcessStep = Omit<ArticleProcessStepApi, 'mode'> & {
  mode: ProcessStepMode;
};

// Ressourcen-Zeile (mini-BOM/Betriebsmittel) am Schritt
export type ResourceLineView = NonNullable<ArticleProcessStepApi['resource_lines']>[number];

export interface ResourceLineInput {
  article_id: number;
  quantity: number;
  mode?: ResourceMode;   // consume (Default) | tool – pro Zeile
}

export interface ArticleProcessStepInput {
  step_type?: StepType;
  position?: number | null;
  mode?: ProcessStepMode;
  supplier_id?: number | null;
  webshop_url?: string | null;
  shared_fields?: string[] | null;
  sample_percent?: number | null;
  capture_fields?: CaptureField[] | null;
  target_location_type?: LocationType | null;
  target_location_id?: number | null;
  resource_lines?: ResourceLineInput[] | null;
}

export interface ArticleProcessStepUpdateInput {
  position?: number;
  mode?: ProcessStepMode;
  supplier_id?: number | null;
  webshop_url?: string | null;
  shared_fields?: string[] | null;
  sample_percent?: number | null;
  capture_fields?: CaptureField[] | null;
  target_location_type?: LocationType | null;
  target_location_id?: number | null;
  resource_lines?: ResourceLineInput[] | null;
  is_active?: boolean;
}

// ─── Beschaffungsschritt (läuft unter dem Auftrag, keine eigene Nummer) ────────

export type PurchaseOrderStatus =
  | 'requested' | 'quoted' | 'ordered' | 'received' | 'rejected';

export interface PurchaseOrderUpdateInput {
  status?: PurchaseOrderStatus;
  order_total?: number | string | null;
  lead_time_days?: number | null;
  payment_terms_days?: number | null;
  tracking_number?: string | null;
  receiving_location_id?: number | null;   // Pflicht beim Wareneingang («received»)
}

// ─── Storage Location (Lagerplatz) ────────────────────────────────────────────

export type StorageLocationStatus = 'draft' | 'released' | 'inactive';
export type StorageLocationType = 'rack' | 'pallet' | 'floor' | 'drawer' | 'picking' | 'external';

type StorageLocationApi = components['schemas']['StorageLocationResponse'];

export type StorageLocation = Omit<StorageLocationApi, 'status'> & {
  status: StorageLocationStatus;
};

export interface StorageLocationInput {
  code?: string | null;
  location_type?: string | null;
  note?: string | null;
  max_load_kg?: number | string | null;
  width_mm?: number | null;
  depth_mm?: number | null;
  height_mm?: number | null;
  is_dry?: boolean;
  is_tempered?: boolean;
  is_hazmat?: boolean;
  is_blocked?: boolean;
  latitude?: number | string | null;
  longitude?: number | string | null;
  address_street?: string | null;
  address_zip?: string | null;
  address_city?: string | null;
  address_country?: string | null;
}

export interface StorageLocationUpdateInput {
  status?: StorageLocationStatus;
  name?: string;
  code?: string | null;
  location_type?: string | null;
  note?: string | null;
  max_load_kg?: number | string | null;
  width_mm?: number | null;
  depth_mm?: number | null;
  height_mm?: number | null;
  is_dry?: boolean;
  is_tempered?: boolean;
  is_hazmat?: boolean;
  is_blocked?: boolean;
  latitude?: number | string | null;
  longitude?: number | string | null;
  address_street?: string | null;
  address_zip?: string | null;
  address_city?: string | null;
  address_country?: string | null;
  is_active?: boolean;
  expected_updated_at?: string | null;   // Optimistic Locking
}

// ─── Claim (Reklamation / RMA) ────────────────────────────────────────────────

export type ClaimStatus = 'open' | 'accepted' | 'rejected' | 'closed';
export type ClaimDirection = 'internal' | 'supplier' | 'customer';
export type ClaimReason = 'defect' | 'damage' | 'wrong_item' | 'quantity' | 'documentation' | 'other';
export type ClaimResolution = 'none' | 'rework' | 'replace' | 'return' | 'credit';

type ClaimApi = components['schemas']['ClaimResponse'];

export type Claim = Omit<ClaimApi, 'status' | 'direction' | 'reason' | 'resolution'> & {
  status: ClaimStatus;
  direction: ClaimDirection;
  reason: ClaimReason;
  resolution: ClaimResolution;
};

export interface ClaimInput {
  instance_object_id: number;
  direction?: ClaimDirection;
  reason?: ClaimReason;
  title?: string | null;
  description?: string | null;
  quantity?: number | null;
}

export interface ClaimUpdateInput {
  status?: ClaimStatus;
  direction?: ClaimDirection;
  reason?: ClaimReason;
  title?: string | null;
  description?: string | null;
  quantity?: number | null;
  resolution?: ClaimResolution;
  resolution_note?: string | null;
  is_active?: boolean;
}

// ─── Unified ERP record (Universal Feed) ──────────────────────────────────────

export type ErpRecordType = 'user' | 'article' | 'order' | 'instance' | 'storage_location' | 'claim';

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
  google_maps_api_key: string | null;
  default_receiving_location_id: number | null;
  article_names: string[];
}

// ─── API response wrappers ────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages?: number;
}
