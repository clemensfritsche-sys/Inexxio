// ─── API-abgeleitete Typen (Single Source of Truth) ──────────────────────────
//
// `api.ts` wird aus dem FastAPI-OpenAPI-Schema generiert:
//   cd backend && python -m scripts.dump_openapi   # → backend/openapi.json
//   cd frontend && npm run generate:types          # → src/types/api.ts
// NICHT von Hand editieren — stattdessen Backend-Schema ändern und neu generieren.

import type { components } from './api';

// ─── User ─────────────────────────────────────────────────────────────────────

// Von Menschen belegbare Rollen (Rollen-Dropdown). Die System-KI (role='ai',
// ADR 004) ist bewusst NICHT wählbar – sie erscheint nur als Anzeige.
export type UserPlatformRole = 'admin' | 'employee' | 'supplier' | 'customer';
export type UserRole = UserPlatformRole | 'ai';

type UserProfileApi = components['schemas']['UserProfileResponse'];

// Aus dem Backend-Schema abgeleitet; nur `role` wird auf die bekannte Union verengt.
export type UserProfile = Omit<UserProfileApi, 'role'> & {
  role: UserRole;
};

// ─── Article ────────────────────────────────────────────────────────────────

export type ArticleStatus = 'draft' | 'released' | 'inactive';
export type ArticleUnit = 'Stk' | 'mm' | 'm2' | 'm3' | 'kg' | 'l';
export type ArticleSerialization = 'unit' | 'batch';

type ArticleApi = components['schemas']['ArticleResponse'];

// Aus dem Backend-Schema abgeleitet; Status/Einheit/Serialisierung auf Unions verengt.
export type Article = Omit<ArticleApi, 'status' | 'unit' | 'serialization'> & {
  status: ArticleStatus;
  unit: ArticleUnit;
  serialization: ArticleSerialization;
};

// Eingaben für Anlage bzw. Teil-Update aus dem Detailfenster. Pflicht ist nur der Name;
// Einheit/Serialisierung tragen einen Default, Grösse & Gewicht sind optional.
export interface ArticleInput {
  name: string;
  unit?: ArticleUnit;
  serialization?: ArticleSerialization;
  size?: string | null;
  weight_kg?: string | null;
  // Optionale Stammdaten (dynamische Feldliste, nur bei Bedarf)
  material?: string | null;
  cad_url?: string | null;
  surface?: string | null;
  supplier_article_number?: string | null;
  min_order_qty?: string | null;
  safety_stock?: string | null;
  reorder_target?: string | null;      // Zielbestand nach Nachbestellung (E)
  // Beschaffungsquelle (Spezifikation): Modus + Lieferant/Webshop-Link (vom purchase-Schritt geerbt)
  procurement_mode?: ProcessStepMode | null;
  default_supplier_id?: number | null;
  default_webshop_url?: string | null;
}

export type ArticleUpdateInput = Partial<ArticleInput> & {
  status?: ArticleStatus;
  is_active?: boolean;
  expected_updated_at?: string | null;   // Optimistic Locking
};

// Namensvorschlag beim Anlegen (freie Namensgebung + intelligente Dubletten-Vermeidung).
export type ArticleNameSuggestion = components['schemas']['ArticleNameSuggestion'];
// Betriebskosten (Monat-bis-heute) – Admin-Übersicht am Unternehmen.
export type OperatingCosts = components['schemas']['OperatingCostsResponse'];
// Maximale Länge eines Artikelnamens – muss zum Backend (`NAME_MAX_LENGTH`) passen.
export const ARTICLE_NAME_MAX_LENGTH = 32;

// ─── Order (Auftrag) ──────────────────────────────────────────────────────────

export type OrderStatus = 'draft' | 'released' | 'inactive' | 'completed';

type OrderApi = components['schemas']['OrderResponse'];

// Eingebetteter Beschaffungsschritt des Auftrags (läuft unter der Auftragsnummer).
export type OrderPurchase = Omit<NonNullable<OrderApi['purchase']>, 'status' | 'mode'> & {
  status: PurchaseOrderStatus;
  mode: ProcessStepMode;
};

// EIN Beschaffungs-Schritt kann bei einem Mehrpositionen-Auftrag mehrere Bestellungen
// tragen (eine je Artikel/Position, gleicher step_id) – Spiegel von ``OrderSale``/``sales``.

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
export type StepType = 'purchase' | 'inspection' | 'movement' | 'resource' | 'scrap' | 'sale' | 'document';
export type ResourceMode = 'consume' | 'tool';
export type OrderStep = OrderApi['steps'][number];

// Dokument: Inhalt (Titel/Untertitel/Abschnitte) + eingebetteter Stand im Auftrag.
// Der Inhalt wird WÄHREND der Auftragsausführung verfasst und ausgestellt.
export type DocumentContent = components['schemas']['DocumentContent'];
export type OrderDocument = NonNullable<OrderApi['document']>;
export type DocumentUpdateInput = components['schemas']['DocumentUpdate'];

// Dokument-Freigabe: endliche Freigabe-Parteien (Unterschriften-/Bestätigungs-Layer).
export type SignoffView = components['schemas']['SignoffView'];
export type SignoffAction = components['schemas']['SignoffAction'];
export type MySignoffDocument = components['schemas']['MySignoffDocument'];
export type MyHistoryDocument = components['schemas']['MyHistoryDocument'];
export type UserDocumentOverview = components['schemas']['UserDocumentOverview'];
export type DocSigner = components['schemas']['DocSigner'];
export type DocSignAction = 'confirm' | 'sign';
export type DocAudience = 'all' | 'roles' | 'persons';
export type DocVisibility = 'public' | 'internal' | 'confidential';
export type DocAudienceRole = 'customer' | 'supplier' | 'employee' | 'admin';

// Hochgeladene Fremd-Dokumente (Belege/Anleitungen) – KI-Aufnahme + Reiter «Dokumente».
export type ObjectDocument = components['schemas']['ObjectDocument'];
export type DocumentAnalyzeResponse = components['schemas']['DocumentAnalyzeResponse'];
export type SuggestedLink = components['schemas']['SuggestedLink'];
export type DocumentConfirmInput = components['schemas']['DocumentConfirmRequest'];
export type DocumentLinkInput = components['schemas']['DocumentLinkInput'];
export type DocumentFileType = 'invoice' | 'delivery_note' | 'manual' | 'datasheet' | 'certificate' | 'contract' | 'receipt' | 'other';

// Öffentliches Rechtsdokument (AGB/Datenschutz/…) – aufgelöster Zeiger (D).
export interface LegalDocument {
  kind: string;
  object_number: number | null;
  document_date: string | null;
  content: DocumentContent | null;
}

// Zu bestätigendes Pflichtdokument (Consent-Gate) – versioniert über die Objektnummer.
export type PendingDocument = components['schemas']['PendingDocument'];
// Erfolgte Bestätigung (am Benutzer-ERP-Datensatz sichtbar).
export type Acknowledgement = components['schemas']['Acknowledgement'];

// Registrierter Passkey (WebAuthn/FIDO2) – Kontoverwaltung (ohne Krypto-Material).
export type Passkey = components['schemas']['PasskeyResponse'];
export type OrderInstance = NonNullable<OrderApi['instances']>[number];
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

// Standort einer Instanz (Bewegung) – immer ein Datensatzobjekt mit Nummer
export type LocationType = 'lagerplatz' | 'user' | 'instance' | 'company';

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

// Verschrotten: zu verschrottende Instanzen + optionale Notiz. ``items`` erlaubt je Instanz
// eine Teilmenge (Charge teilverschrotten); ``instance_ids`` bleibt die Kurzform (ganze Instanz).
export interface ScrapItemInput {
  instance_id: number;
  quantity?: number | null;   // weglassen = ganze (Rest-)Menge
}
export interface ScrapUpdateInput {
  instance_ids?: number[];
  items?: ScrapItemInput[];
  note?: string | null;
  step_id?: number | null;   // konkrete Schritt-Definition (Mehr-Operationen-Routing)
}


export type CaptureField = components['schemas']['CaptureField'];

// Konkrete Stichprobe der Datenerfassung (Instanz + erfasste Werte)

export interface InspectionSampleInput {
  instance_id: number;
  slot: number;
  values: Record<string, unknown>;
}

export interface InspectionUpdateInput {
  samples: InspectionSampleInput[];
  note?: string | null;
  step_id?: number | null;   // konkrete Schritt-Definition (Mehr-Operationen-Routing)
  signature_url?: string | null;   // digitale Unterschrift (Freigabe), falls verlangt
  photo_url?: string | null;       // Schritt-Foto (Bilderfassung), falls verlangt
}

// Bestands-Instanz (Reiter «Bestand» am Artikel)
type InstanceApi = components['schemas']['InstanceResponse'];
export type Instance = InstanceApi;
// Eine Teilmenge einer Charge an einem Standort (Standort-Verteilung ohne Instanz-Teilung)
export type InstanceLocation = components['schemas']['InstanceLocation'];
// qc_status in zwei orthogonale Achsen getrennt (siehe Backend domain/event_types):
// Generischer Objekt-Verweis (Lagerplatz-Verwendung)
export type ObjectReference = components['schemas']['ObjectReference'];
// Auftrag, der eine Instanz angefasst hat (Instanz = Summe aller Prozesse)
export type InstanceOrderRef = components['schemas']['InstanceOrderRef'];

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

// Eine Position eines Mehrpositionen-Auftrags (``order.article_id`` ist dann NULL).
export type OrderLineInfo = components['schemas']['OrderLineInfo'];

// Kurzinfo eines Unter-Auftrags (Abweichung/Nachschub) am Eltern-Auftrag.
export type OrderDeviationInfo = components['schemas']['OrderDeviationInfo'];

// Eine weitere Position zu einem bestehenden Auftrag hinzufügen (POST .../lines) –
// jederzeit möglich, auch nachdem der Auftrag schon gespeichert wurde. Macht den
// Auftrag (falls noch nicht) zu einem Mehrpositionen-Auftrag (kein «Herstellen» mehr).
export interface OrderLineCreateInput {
  article_id: number;
  quantity: number;
}
// Fixierte Instanzen EINER Position statt FIFO (PATCH .../lines/{line_id}).
export interface OrderLinePinsInput {
  instance_object_ids: number[];
}

export interface OrderInput extends OrderRecurrenceInput {
  article_id?: number | null;
  quantity?: number | null;
  desired_delivery_date?: string | null;
}

export type OrderUpdateInput = OrderRecurrenceInput & {
  status?: OrderStatus;
  article_id?: number | null;
  quantity?: number | null;
  // Vorgewählte Subjekt-Instanzen im Entwurf anpassen (Mehrfachauswahl).
  instance_object_ids?: number[] | null;
  desired_delivery_date?: string | null;
  is_active?: boolean;
  expected_updated_at?: string | null;   // Optimistic Locking
};

// ─── Prozess = Schritte am Artikel (Entstehung) ODER am Auftrag (individuell) ──
// Es gibt KEIN eigenständiges Prozess-Objekt und KEIN Auftrags-Modus-Flag mehr –
// die Subjektart (produce | stock | instance) wird im Backend abgeleitet.

// ─── Verkaufsschritt (Spiegel der Beschaffung) ─────────────────────────────────

export type OrderSale = NonNullable<OrderApi['sale']>;
export type SaleStatus = 'requested' | 'confirmed' | 'invoiced' | 'paid' | 'cancelled';
// Herkunft: 'shop' (Kunde über die Kasse/Stripe) | 'direct' (Personal im ERP erfasst).
// Zahlungsart des manuellen Zahlungseingangs – Rechnung ist der übliche B2B-Weg, KEIN
// Kartenterminal nötig. 'stripe' setzt das System selbst (Shop-Zahlung).
export type PaymentMethod = 'invoice' | 'cash' | 'twint' | 'other' | 'stripe';

export interface SaleUpdateInput {
  status?: SaleStatus;
  order_total?: number | string | null;
  vat_rate?: number | string | null;
  currency?: string | null;
  customer_id?: number | null;
  invoice_number?: string | null;
  payment_method?: PaymentMethod | null;
  payment_reference?: string | null;
  step_id?: number | null;
}


// ─── Verkauf / Shop ────────────────────────────────────────────────────────────
// Der Verkauf lebt AM ARTIKEL (dritte, lebende Ebene) – kein eigenes Objekt.

export type SalesVisibility = 'public' | 'private';
export type SalesFulfillment = 'make' | 'stock';
export type PriceKind = 'one_time' | 'subscription';
export type PriceInterval = 'month' | 'year';
export type PriceSubType = 'usage' | 'product';   // Nutzungsabo | Produktabo

export type ArticlePrice = components['schemas']['ArticlePriceResponse'];
export type AudienceMember = components['schemas']['AudienceMember'];
export type ShopProduct = components['schemas']['ShopProduct'];
export type ShopPriceOption = components['schemas']['ShopPriceOption'];
export type ShopCheckoutResult = components['schemas']['ShopCheckoutResult'];
export type CustomerOrder = components['schemas']['CustomerOrder'];

// Lokalisierter Verkaufs-Inhalt (de/en) – Titel/Untertitel/Beschreibung/Bilder.
export interface SalesContentBlock {
  title?: string;
  subtitle?: string;
  description?: string;
  images?: string[];
}
export interface SalesContent {
  de?: SalesContentBlock;
  en?: SalesContentBlock;
}

type ArticleSalesProfileApi = components['schemas']['ArticleSalesProfile'];
export type ArticleSalesProfile = Omit<ArticleSalesProfileApi, 'sales_visibility' | 'sales_fulfillment' | 'sales_content'> & {
  sales_visibility: SalesVisibility;
  sales_fulfillment: SalesFulfillment;
  sales_content: SalesContent | null;
};

export interface ArticleSalesUpdateInput {
  sales_published?: boolean;
  sales_visibility?: SalesVisibility;
  sales_fulfillment?: SalesFulfillment;
  sales_content?: SalesContent | null;
}

export interface ArticlePriceInput {
  kind: PriceKind;
  interval?: PriceInterval | null;
  sub_type?: PriceSubType | null;
  amount_chf: number | string;
  compare_at_chf?: number | string | null;
  is_primary?: boolean;
}

// Warenkorb-Position (lokaler State) – konkretes Produkt + gewählte Preis-Option.
export interface CartItem {
  article_object_id: number;
  price_id: number;
  quantity: number;
  title: string;
  unit?: string | null;
  fulfillment: SalesFulfillment;
  kind: PriceKind;
  interval?: PriceInterval | null;
  sub_type?: PriceSubType | null;
  currency: string;
  gross: number;          // Stück-Bruttopreis (indikativ, CHF)
  image?: string | null;
}

export type ArticlePriceUpdateInput = Partial<ArticlePriceInput> & { is_active?: boolean };

export interface ShopConfig {
  currencies: string[];
  default_currency: string;
  provider: string;                       // 'stripe' | 'manual'
  stripe_publishable_key: string | null;  // öffentlich – für die eingebettete Kasse
}

export interface PaymentStatus {
  order_object_id: number | null;
  order_object_ids?: number[];
  status: SaleStatus;
  currency: string;
  net_total: number | string;
  vat_rate: number | string;
  gross_total: number | string;
  provider: string;
  paid: boolean;
}

// ─── Article Process Steps (Prozess-Definition) ───────────────────────────────

export type ProcessStepMode = 'supplier' | 'webshop';

type ArticleProcessStepApi = components['schemas']['ArticleProcessStepResponse'];

export type ArticleProcessStep = Omit<ArticleProcessStepApi, 'mode'> & {
  mode: ProcessStepMode;
};

// Ressourcen-Zeile (mini-BOM/Betriebsmittel) am Schritt

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
  require_signature?: boolean;
  signer_ids?: number[] | null;
  require_photo?: boolean;
  photo_instruction?: string | null;
  target_location_type?: LocationType | null;
  target_location_id?: number | null;
  resource_lines?: ResourceLineInput[] | null;
  doc_signers?: DocSigner[] | null;
  sign_sequential?: boolean;
  doc_audience?: DocAudience | null;
  doc_audience_roles?: DocAudienceRole[] | null;
  doc_audience_person_ids?: number[] | null;
  doc_visibility?: DocVisibility;
}

export interface ArticleProcessStepUpdateInput {
  position?: number;
  mode?: ProcessStepMode;
  supplier_id?: number | null;
  webshop_url?: string | null;
  shared_fields?: string[] | null;
  sample_percent?: number | null;
  capture_fields?: CaptureField[] | null;
  require_signature?: boolean;
  signer_ids?: number[] | null;
  require_photo?: boolean;
  photo_instruction?: string | null;
  target_location_type?: LocationType | null;
  target_location_id?: number | null;
  resource_lines?: ResourceLineInput[] | null;
  doc_signers?: DocSigner[] | null;
  sign_sequential?: boolean;
  doc_audience?: DocAudience | null;
  doc_audience_roles?: DocAudienceRole[] | null;
  doc_audience_person_ids?: number[] | null;
  doc_visibility?: DocVisibility;
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
  step_id?: number | null;                 // Mehr-Operationen-Routing
  article_id?: number | null;              // Mehrpositionen: welche Position (bei >1 Bestellung)
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

// ─── Unified ERP record (Universal Feed) ──────────────────────────────────────
// Reklamationen sind KEIN eigener Typ mehr: eine «Abweichung» ist ein Auftrag mit
// parent_order_id (Unterauftrag) – siehe Order.parent_order_id / abort_into_id.

export type ErpRecordType = 'user' | 'article' | 'order' | 'instance' | 'storage_location' | 'organization';

// ─── KI-Layer (ADR 004) ───────────────────────────────────────────────────────

export type AiConfig = components['schemas']['AiConfig'];
export type AiChatMessage = components['schemas']['AiChatMessage'];
export type AiChatResponse = components['schemas']['AiChatResponse'];
export type AiProposal = components['schemas']['AiProposal'];
export type AiDocContent = components['schemas']['AiDocContent'];
export type AiImageEditResponse = components['schemas']['AiImageEditResponse'];

// ─── Company Settings ─────────────────────────────────────────────────────────
//
// Bewusst NICHT aus dem Schema abgeleitet: die API liefert snake_case-Felder mit
// abweichenden Namen (zip_code, uid_number, bic_swift …); api.ts mappt sie auf
// diese camelCase-nahe Frontend-Sicht (mapSettingsFromBackend/ToBackend).

export interface CompanySettings {
  object_id?: number | null;   // universelle ERP-Objektnummer des Unternehmens
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
  // Shop / Verkauf
  shop_currencies: string[];
  shop_country_currency: Record<string, string> | null;
  shop_default_currency: string;
  payments_provider: string | null;
  pricing_zone_factors: Record<string, number> | null;
  // Öffentliche Rechtsdokumente (D): {"agb": <Artikel-Objektnr>, "datenschutz": …}
  legal_documents: Record<string, number> | null;
  // Bestätigungspflicht je Dokument-Art (Consent-Gate): {"agb": ["all"], …}
  legal_ack_config: Record<string, string[]> | null;
}

