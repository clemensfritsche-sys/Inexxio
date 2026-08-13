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

// Aus der EINEN Statusliste (`domain/statuses.ARTICLE_STATUSES`) – einen Entwurf gibt es
// nicht: der Artikel entsteht erst mit seiner Freigabe.
export type ArticleStatus = 'freigegeben' | 'inaktiv';
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
export type TerritoryMap = components['schemas']['TerritoryMapResponse'];
export type TerritoryRegion = components['schemas']['TerritoryRegion'];
export type TerritoryCompany = components['schemas']['TerritoryCompany'];
export type TerritoryCountry = components['schemas']['TerritoryCountry'];
// Maximale Länge eines Artikelnamens – muss zum Backend (`NAME_MAX_LENGTH`) passen.
export const ARTICLE_NAME_MAX_LENGTH = 32;

// ─── Order (Auftrag) ──────────────────────────────────────────────────────────
//
// Der Auftrag entsteht erst mit der Freigabe; das Detail trägt seine Schritte, seine
// Stücke und die eingefrorene Historie (PROCESS_CORE.md §10).

export type Order = components['schemas']['OrderResponse'];
export type OrderSummary = components['schemas']['OrderSummary'];
export type OrderValidation = components['schemas']['OrderValidation'];
export type ProcessStepResponse = components['schemas']['ProcessStepResponse'];
export type OrderUnitResponse = components['schemas']['OrderUnitResponse'];
export type ProcessEventResponse = components['schemas']['ProcessEventResponse'];
export type UnitOption = components['schemas']['UnitOption'];
/** Ein Nachbar-Auftrag in der Journey einer Einzelinstanz – gruppiert, mit Stückzahl. */
export type JourneyStop = components['schemas']['JourneyNeighbour'];
/** Ein Nachbar-Auftrag mit seinem **vollständigen** Ablauf – links übergeordnet, rechts
 *  eine Abweichung. Er wird mit derselben Komponente gerendert wie die Mitte. */
export type RelatedOrder = components['schemas']['RelatedOrder'];
export type ArticleOption = components['schemas']['ArticleOption'];
export type OrderLineResponse = components['schemas']['OrderLineResponse'];
/** **Das Prozessbild, wie der Server es sieht** – Knoten, Kanten, Positionen.
 *  Das Frontend layoutet und zeichnet es; abgeleitet wird nichts mehr davon. */
export type ProcessGraph = components['schemas']['FlowGraph'];
export type GraphNode = components['schemas']['FlowNode'];
export type GraphEdge = components['schemas']['FlowEdge'];
export type GraphUnits = components['schemas']['FlowUnits'];
export type OrderUnitPage = components['schemas']['OrderUnitPage'];

/** Der Erzeugungsprozess eines Artikels – die Vorlage, die ein Erzeugungsauftrag kopiert. */
export type ArticleProcess = components['schemas']['ArticleProcess'];
export type ArticleProcessStep = components['schemas']['ArticleProcessStepResponse'];

/** Ein Auftragsentwurf. Er lebt NUR im Browser – es gibt dafür keine Zeile in der
 *  Datenbank, keine vorreservierte Objektnummer und kein Autosave. */
export type OrderDraft = Record<string, unknown>;


export type DocAudienceRole = 'customer' | 'supplier' | 'employee' | 'admin';

export type DocumentFileType = 'invoice' | 'delivery_note' | 'manual' | 'datasheet' | 'certificate' | 'contract' | 'receipt' | 'other';

export type Passkey = components['schemas']['PasskeyResponse'];
export interface ResourceToolPickInput {
  article_id: number;
  instance_ids: number[];
}

export interface ResourceUpdateInput {
  tools: ResourceToolPickInput[];
  note?: string | null;
  step_id?: number | null;   // konkrete Schritt-Definition (Mehr-Operationen-Routing)
}

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

// Feed-Zeile: ohne die Einzelinstanzen, aber mit ihrer Anzahl.
export type InstanceSummary = components['schemas']['InstanceSummary'];
// Die Einzelinstanz – das einzige Arbeitsobjekt. Nummer = <Instanznr>-<suffix>.
export type InstanceUnit = components['schemas']['InstanceUnitResponse'];
// Ein Zustand mit seiner Menge – ein Segment der Bestandsleiste.
export type StockState = components['schemas']['StockState'];
// Der Bestand eines Artikels: Aufstellung über alles + eine Seite Instanzen.
export type ArticleStock = components['schemas']['ArticleStock'];
// Eine Seite Einzelinstanz-Nummern (Ebene 3, auf Klick).
export type UnitPage = components['schemas']['UnitPage'];
export type Genealogy = components['schemas']['Genealogy'];
export type GenealogyPart = components['schemas']['GenealogyPart'];

/**
 * Ein Erfassungspunkt aus der Definition eines Moduls (`process_steps.config`).
 *
 * **Von Hand gespiegelt**, weil `config` am Prozessschritt ein freies Objekt ist: was
 * darin steht, entscheidet der Modultyp (`domain/modules.Module.clean_config`), nicht
 * ein festes Schema. Es fest zu typisieren hiesse, die Konfiguration aller künftigen
 * Modultypen auf die des heutigen einen festzunageln.
 *
 * Der Abgleich mit `schemas/process.CapturePoint` ist getestet
 * (`tests/test_frontend_mirrors.py`) – ein Spiegel darf existieren, aber nicht
 * unbemerkt auseinanderlaufen. Die Typen selbst sind eine geschlossene Liste im Backend
 * (`domain/capture_types/`) und kommen über den Modul-Katalog.
 */
export interface CapturePoint {
  key: string;
  label: string;
  type: string;
  target?: number | null;
  tolerance?: number | null;
  /**
   * **Worin wird gemessen?** (mm · kg · °C …) Ein freies, kurzes Wort – bewusst keine
   * Liste. Die Mengeneinheiten des Artikels beantworten eine andere Frage («worin wird
   * die Menge geführt»), und eine zweite Liste wäre endlos: jede Branche misst anders,
   * und das System rechnet nie mit der Einheit, es zeigt sie an.
   */
  unit?: string | null;
}
/** Was an einem Modul für **eine Instanz** ansteht (`process.step_work`). */
export type StepWork = components['schemas']['StepWork'];
/** Eine Zeile der Stückliste, gegen den Bestand gehalten (`services/consumption`). */
export type StepNeed = components['schemas']['StepNeed'];
export type ModuleCatalog = components['schemas']['ModuleCatalog'];
export type ArticleValidation = components['schemas']['ArticleValidation'];
export type ObjectReference = components['schemas']['ObjectReference'];
export type SalesVisibility = 'public' | 'private';
export type SalesFulfillment = 'make' | 'stock';
export type PriceKind = 'one_time' | 'subscription';
export type PriceInterval = 'month' | 'year';
export type PriceSubType = 'usage' | 'product';   // Nutzungsabo | Produktabo

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

export type ProcessStepMode = 'supplier' | 'webshop';

export type ErpRecordType = 'user' | 'article' | 'order' | 'instance' | 'organization';

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
