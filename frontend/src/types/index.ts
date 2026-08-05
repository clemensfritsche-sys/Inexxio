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
  is_hazmat?: boolean | null;
  material?: string | null;
  cad_url?: string | null;
  surface?: string | null;
  supplier_article_number?: string | null;
  min_order_qty?: string | null;
  safety_stock?: string | null;
  reorder_target?: string | null;      // Zielbestand nach Nachbestellung (E)
  // Fixierter Standort (optional): GPS + Adresse, rein deskriptiv.
  fixed_location_lat?: string | null;
  fixed_location_lng?: string | null;
  fixed_location_street?: string | null;
  fixed_location_zip?: string | null;
  fixed_location_city?: string | null;
  fixed_location_country?: string | null;
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
export type TerritoryMap = components['schemas']['TerritoryMapResponse'];
export type TerritoryRegion = components['schemas']['TerritoryRegion'];
export type TerritoryCompany = components['schemas']['TerritoryCompany'];
export type TerritoryCountry = components['schemas']['TerritoryCountry'];
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
export type StepType = 'purchase' | 'inspection' | 'movement' | 'resource' | 'scrap' | 'block' | 'sale' | 'document';
export type ResourceMode = 'consume' | 'tool';
export type OrderStep = OrderApi['steps'][number];
// Was an einem Schritt entschieden wurde, als er unterdeckt war (ersetzt / ohne Ersatz weiter).
export type StepResolution = OrderStep['resolutions'][number];
/** Was einem Auftrag fehlt (Fertigware oder Komponente) – die Fehlmenge gehört dem Auftrag. */
export type OrderShortfall = OrderApi['shortfall'][number];
/** Ein laufender Auftrag, dem die Auswahl dieses Entwurfs etwas wegnimmt (#387). */
export type AffectedOrder = OrderApi['affects'][number];
/** Ein **regulärer** Auftrag, der dasselbe Material vor/nach diesem verarbeitet hat (#493). */
/**
 * **Die fertig gerechnete Fluss-Achse aus dem Backend** (ADR 007): Knoten (Schritt oder
 * Teilung) und Kanten (Material im Zustand von damals, Fortschritt, Prozess-Punkt). Das
 * Frontend zeichnet sie nur – jede Client-Arithmetik darüber war eine Testnotiz.
 */
export type FlowNode = OrderApi['flow_nodes'][number];
export type FlowEdge = OrderApi['flow_edges'][number];
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
export type LocationType = 'user' | 'instance' | 'company';

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

// Versand (ADR 005): abgeleitete Transportklasse + Versand-Beleg am Bewegungs-Schritt.
export type ShipmentEmbed = components['schemas']['ShipmentEmbed'];
export type ShipmentRate = components['schemas']['ShipmentRate'];
// EINE Transport-Achse: innerbetrieblich | Paket | Fracht (die Sendungsart folgt dem Modus).
export type TransportMode = 'internal' | 'parcel' | 'freight';
export interface ShipmentUpdateInput {
  step_id?: number | null;
  transport_mode?: TransportMode | null;
  carrier?: string | null;
  tracking_number?: string | null;
  cost_amount?: number | null;
  cost_currency?: string | null;
  note?: string | null;
  // Fracht (Modus 'freight'): Last/Incoterm/Abholtermin verfeinern.
  load?: Record<string, unknown> | null;
  incoterm?: string | null;
  pickup_date?: string | null;
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
  step_id?: number | null;   // konkrete Schritt-Definition (Mehr-Operationen-Routing)   // digitale Unterschrift (Freigabe), falls verlangt       // Schritt-Foto (Bilderfassung), falls verlangt
}

// Bestands-Instanz (Reiter «Bestand» am Artikel)
type InstanceApi = components['schemas']['InstanceResponse'];
export type Instance = InstanceApi;
/** **Ein einzelnes Stück** – Nummer · Menge · Zustand, die EINE Form überall (#531/#532). */
export type InstanceUnit = components['schemas']['InstanceUnit'];
// Eine Teilmenge einer Charge an einem Standort (Standort-Verteilung ohne Instanz-Teilung)
export type InstanceLocation = components['schemas']['InstanceLocation'];
// qc_status in zwei orthogonale Achsen getrennt (siehe Backend domain/event_types):
// Generischer Objekt-Verweis («Verwendung» je Objektnummer)
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

// Der Prozess eines Unter-Auftrags, angeteasert (Modul + Zustand) – Notiz #409.
export type SubOrderStep = components['schemas']['SubOrderStep'];

// Woher ein Unter-Auftrag kam und wohin er beim Abschluss zurückgibt – Notiz #409.
export type OrderOrigin = components['schemas']['OrderOrigin'];

// Eine Materialmenge auf einer Kante des Flusses («4 × 100000590») – Notiz #413.
export type FlowLot = components['schemas']['FlowLot'];

// Ein kurz benannter Auftrag – für die Kette über einem Unter-Auftrag.

// Eine weitere Position zu einem bestehenden Auftrag hinzufügen (POST .../lines) –
// jederzeit möglich, auch nachdem der Auftrag schon gespeichert wurde. Macht den
// Auftrag (falls noch nicht) zu einem Mehrpositionen-Auftrag (kein «Herstellen» mehr).
/**
 * **Ein Anteil, kein Ding.** Eine Instanz ist eine Menge, und ihre Menge ist immer
 * vollständig aufgeteilt: jeder Anteil gehört genau einem Auftrag oder ist frei. Wer
 * auswählt, klickt eine **Zeile** an – Instanz · Menge · Halter – und beantwortet damit
 * zugleich, WEM er etwas wegnimmt. `from_order_object_id` leer = freier Anteil.
 */
export type InstancePickInput = {
  instance_object_id: number;
  quantity?: number | null;
  from_order_object_id?: number | null;
};

export interface OrderLineCreateInput {
  article_id: number;
  quantity: number;
  /** «Auswählen» statt FIFO – die Position bringt ihre Anteile gleich mit (#386). */
  picks?: InstancePickInput[] | null;
}
// Gewählte Anteile EINER Position statt FIFO (PATCH .../lines/{line_id}).
export interface OrderLinePinsInput {
  picks: InstancePickInput[];
}

/**
 * **Ein Auftrag entsteht als Ganzes** (Testnotiz #386): der Entwurf lebt im Browser, und
 * beim Erteilen kommt alles auf einmal – Bedarf, Positionen, Ablauf und Auswahl. Erst
 * dann bekommt er seine Objektnummer.
 */
export interface OrderInput extends OrderRecurrenceInput {
  article_id?: number | null;
  quantity?: number | null;
  /** **Vorauswahl**, keine Fixierung: der Abkürzungs-Knopf an einer Instanz trägt sie gleich
   *  ein – danach frei änderbar wie jede andere Auswahl (Notiz #371). */
  picks?: InstancePickInput[] | null;
  desired_delivery_date?: string | null;
  /** Weitere Positionen (der Anker oben ist Position 0) – je mit eigener Auswahl. */
  lines?: OrderLineCreateInput[] | null;
  /** Der auftragseigene Ablauf – derselbe Editor, nur noch nicht gespeichert. */
  steps?: ArticleProcessStepInput[] | null;
  /** **Die Rückführung ist gekappt** (Testnotiz #563): was dieser Auftrag übernimmt, kommt
   *  nicht zurück – der Halter endet an dieser Stelle, abgebrochen und hier fortgeführt.
   *  Im Entwurf ist das die gekappte Rückgabe-Linie. */
  returns_nothing?: boolean | null;
}

export type OrderUpdateInput = OrderRecurrenceInput & {
  status?: OrderStatus;
  article_id?: number | null;
  quantity?: number | null;
  // Gewählte **Anteile** im Entwurf anpassen. **Die Auswahl bestimmt die Art des
  // Auftrags**: verkauft → Retoure · gebunden (in Arbeit/reserviert/gesperrt) →
  // Abweichung · frei → gewöhnlicher Auftrag.
  picks?: InstancePickInput[] | null;
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
  /** Nur innerhalb des Moduls «Aussondern» (scrap ↔ block): EIN Modul, zwei Wirkungen
   *  (#277) – die Wirkung ist eine Konfiguration, kein anderes Modul. Der Server erzwingt es. */
  step_type?: StepType;
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
  doc_signers?: DocSigner[] | null;
  sign_sequential?: boolean;
  doc_audience?: DocAudience | null;
  doc_audience_roles?: DocAudienceRole[] | null;
  doc_audience_person_ids?: number[] | null;
  doc_visibility?: DocVisibility;
  is_active?: boolean;
}

// ─── Beschaffungsschritt (läuft unter dem Auftrag, keine eigene Nummer) ────────

// «Storniert» setzt das System, nicht der Mensch: verliert die Bestellung ihren Gegenstand
// (der Auftrag ist abgebrochen), ist sie gegenstandslos – siehe `services/rebase.py`.
export type PurchaseOrderStatus =
  | 'requested' | 'quoted' | 'ordered' | 'received' | 'rejected' | 'cancelled';

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

export type ErpRecordType = 'user' | 'article' | 'order' | 'instance' | 'organization';

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
// abweichenden Namen (zip_code, uid_number, street_nr …); api.ts mappt sie auf
// diese camelCase-nahe Frontend-Sicht (mapSettingsFromBackend/ToBackend).

export interface CompanySettings {
  object_id?: number | null;   // universelle ERP-Objektnummer des Unternehmens
  // Abgeleitete Rollen (KEIN gespeichertes Flag, KEIN Rang): ältestes Unternehmen =
  // Betreiber der Website (Impressum/Systemkonfiguration/Fallback); has_address = trägt
  // echte Ortsangaben (sonst logistisch stumm – eine Bewegung dorthin bleibt intern).
  is_operator?: boolean;
  has_address?: boolean;
  /** Aktiv? Eine geschlossene Gesellschaft bleibt lesbar, ist aber endgültig (keine Reaktivierung). */
  is_active?: boolean;
  company_name: string;
  legal_form: string | null;
  street: string;
  street_number: string | null;
  zip: string;
  city: string;
  country: string;
  // Funktionswährung der Gesellschaft (ISO-3, auto aus dem Land vorbelegt).
  currency: string;
  // Rechtsidentität – das Minimum, das ein Beleg und das Impressum ausweisen müssen
  // (Testnotizen #307/#313/#314/#317–#321): Handelsregister-Nr./-Kanton, Aktienkapital,
  // QR-IBAN, Bankname, BIC, MWST-Methode/-Periode, Zahlungsfrist und Skonto sind entfallen.
  uid: string | null;
  vat_number: string | null;
  email: string;
  phone: string | null;
  /** **Abgeleitet** (read-only): die Adresse, unter der diese Installation läuft (#309). */
  website: string;
  logo_url: string | null;
  iban: string | null;
  iban_masked: string | null;
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
  // Realer Infrastruktur-Monatsbetrag (CHF) – gesetzt = «fix» in den Betriebskosten (#293).
  infra_monthly_chf: number | null;
  // Öffentliche Rechtsdokumente (D): {"agb": <Artikel-Objektnr>, "datenschutz": …}
  legal_documents: Record<string, number> | null;
}

// Es gibt genau EINEN Datensatztyp für Unternehmen/Gesellschaften: `CompanySettings`
// (oben). Der frühere separate `Site`-Typ (kastrierter «Standort») ist entfallen – jede
// Gesellschaft ist vollständig und gleichrangig.


// ─── Testnotizen (in-app Feedback, nur Testumgebung) ─────────────────────────
// Eine angeheftete Notiz aus der laufenden Oberfläche. Bewusst OHNE Objektnummer –
// ein Meta-Artefakt über dem System, kein Geschäftsobjekt (siehe docs/feedback.md).

/** WO die Notiz hängt. `label` (sichtbarer Text) ist der greppbare Anker im Code. */
export interface FeedbackAnchor {
  label: string;
  tag: string;
  selector: string;
  html: string;
  /** Umgebender Abschnitt (Prozessschritt-Panel, Sektionstitel) – trägt bei dynamischen Listen mehr als der Selektor. */
  section: string;
  rx: number;   // relative Position im Element (0–1) – der Pin sitzt wieder gleich
  ry: number;
}

/** WOMIT es passiert ist – Umgebung inkl. der letzten Laufzeitfehler. */
export interface FeedbackContext {
  viewport: string;
  ua: string;
  role: string;
  version: string;
  /** Offener Datensatz + aktiver Reiter, z. B. «Artikel · Prozess». */
  view: string;
  errors: string[];
}

export type FeedbackStatus = 'open' | 'done' | 'dismissed';

export interface FeedbackNote {
  id: number;
  status: FeedbackStatus;
  body: string;
  route: string;
  target_object_id: number | null;
  anchor: FeedbackAnchor | null;
  context: FeedbackContext | null;
  resolution: string | null;
  resolved_at: string | null;
  created_at: string;
  created_by: number | null;
  author_name: string;
  mine: boolean;
}

export interface FeedbackCreateInput {
  body: string;
  route: string;
  target_object_id?: number | null;
  anchor?: FeedbackAnchor | null;
  context?: FeedbackContext | null;
}

export interface FeedbackUpdateInput {
  status?: FeedbackStatus;
  resolution?: string | null;
}

/**
 * **Das Systemprotokoll eines Auftrags** (Befund + Chronologie) – die Grundlage eines
 * Fehlerberichts. Kein Domänen-Objekt, sondern eine **Sicht**: `snapshot` ist der
 * abgeleitete Zustand zum Abfragezeitpunkt, `entries` sind die drei Ströme
 * (Audit · Ereignisse · Material-Journal) chronologisch nebeneinander.
 */
export type OrderDiagnostics = components['schemas']['OrderDiagnostics'];
export type DiagnosticEntry = components['schemas']['DiagnosticEntry'];
