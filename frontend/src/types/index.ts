// ─── API-abgeleitete Typen (Single Source of Truth) ──────────────────────────
//
// `api.ts` wird aus dem FastAPI-OpenAPI-Schema generiert:
//   cd backend && python -m scripts.dump_openapi   # → backend/openapi.json
//   cd frontend && npm run generate:types          # → src/types/api.ts
// NICHT von Hand editieren — stattdessen Backend-Schema ändern und neu generieren.

import type { components } from './api';

// ─── User ─────────────────────────────────────────────────────────────────────

// **Die Rolle beantwortet genau eine Frage: darf diese Person ins ERP?** Lieferant ↔ Kunde
// ist eine Eigenschaft des Vorgangs. Spiegel von `schemas/admin.Role` (Wächter).
export type UserRole = 'admin' | 'employee' | 'user';

type UserProfileApi = components['schemas']['UserProfileResponse'];

// Aus dem Backend-Schema abgeleitet; nur `role` wird auf die bekannte Union verengt.
export type UserProfile = Omit<UserProfileApi, 'role'> & {
  role: UserRole;
};

/** Was eine Person an sich selbst ändert (`PATCH /auth/me`, `people.apply_profile_update`). */
export type UserProfileUpdate = components['schemas']['UserProfileUpdate'];
/** Was das ERP an einer Person ändert – dasselbe plus Rolle und Anstellung. */
export type ErpAdminUpdate = components['schemas']['ErpAdminUpdate'];

// ─── Article ────────────────────────────────────────────────────────────────

export type ArticleUnit = 'Stk' | 'mm' | 'm2' | 'm3' | 'kg' | 'l';
export type ArticleSerialization = 'unit' | 'batch';

type ArticleApi = components['schemas']['ArticleResponse'];

// Aus dem Backend-Schema abgeleitet; Status/Einheit/Serialisierung auf Unions verengt.
export type Article = Omit<ArticleApi, 'status' | 'unit' | 'serialization'> & {
  // Aus der EINEN Statusliste (`domain/statuses`); gesetzt von niemandem – die Projektion
  // von `replaced_by_id`.
  status: 'freigegeben' | 'inaktiv';
  unit: ArticleUnit;
  serialization: ArticleSerialization;
};

// Eingaben für die Anlage (`ArticleCreate`), Einheit und Serialisierung verengt. Die Module
// reisen getrennt (`steps`).
export type ArticleInput = Omit<components['schemas']['ArticleCreate'], 'unit' | 'serialization' | 'steps'> & {
  unit?: ArticleUnit;
  serialization?: ArticleSerialization;
};

// Namensvorschlag beim Anlegen (freie Namensgebung + intelligente Dubletten-Vermeidung).
export type ArticleNameSuggestion = components['schemas']['ArticleNameSuggestion'];

// Die **geplante** Stückliste in beide Richtungen (`services/bom.py`) – nur am Detail.
// `Article.bom === null` heisst «nicht geladen», nicht «nichts gefunden».
export type ArticleLink = components['schemas']['ArticleLink'];
export type ArticleBom = components['schemas']['ArticleBom'];
export type TerritoryMap = components['schemas']['TerritoryMapResponse'];
// Maximale Länge eines Artikelnamens – muss zum Backend (`NAME_MAX_LENGTH`) passen.
export const ARTICLE_NAME_MAX_LENGTH = 32;

// ─── Order (Auftrag) ──────────────────────────────────────────────────────────
//
// Der Auftrag entsteht erst mit der Freigabe; das Detail trägt seine Schritte, seine
// Stücke und die eingefrorene Historie (PROCESS_CORE.md §10).

export type Order = components['schemas']['OrderResponse'];
export type OrderSummary = components['schemas']['OrderSummary'];
/** Die Wiederholung eines Auftrags (Projektakte `docs/konzept/wiederkehr.md`). */
export type LoopView = components['schemas']['LoopView'];
export type LoopIn = components['schemas']['LoopIn'];
export type OrderValidation = components['schemas']['OrderValidation'];
export type ProcessStepResponse = components['schemas']['ProcessStepResponse'];
export type ProcessEventResponse = components['schemas']['ProcessEventResponse'];
export type UnitOption = components['schemas']['UnitOption'];
// Die Auswahl: eine Seite wählbarer Einzelinstanzen samt Aggregat und FIFO-Vorauswahl.
// Nicht `UnitPage` (eine Seite blosser Nummern am Instanz-Datensatz).
export type UnitChoices = components['schemas']['UnitChoices'];
/** Ein Nachbar-Auftrag in der Journey einer Einzelinstanz – gruppiert, mit Stückzahl. */
export type JourneyStop = components['schemas']['JourneyNeighbour'];
/** Ein Nachbar-Auftrag mit seinem **vollständigen** Ablauf – links übergeordnet, rechts
 *  eine Abweichung. Er wird mit derselben Komponente gerendert wie die Mitte. */
export type RelatedOrder = components['schemas']['RelatedOrder'];
export type ArticleOption = components['schemas']['ArticleOption'];
/** **Das Prozessbild, wie der Server es sieht** – Knoten, Kanten, Positionen; das Frontend zeichnet. */
export type ProcessGraph = components['schemas']['FlowGraph'];
export type GraphNode = components['schemas']['FlowNode'];
export type GraphEdge = components['schemas']['FlowEdge'];
export type GraphUnits = components['schemas']['FlowUnits'];
export type OrderUnitPage = components['schemas']['OrderUnitPage'];

/** Der Erzeugungsprozess eines Artikels – die Vorlage, die ein Erzeugungsauftrag kopiert. */
export type ArticleProcess = components['schemas']['ArticleProcess'];

/** Ein Auftragsentwurf – lebt NUR im Browser (keine Zeile, keine Nummer, kein Autosave). */
export type OrderDraft = Record<string, unknown>;

export type Passkey = components['schemas']['PasskeyResponse'];
// Eine Instanz (Gruppe von Einzelinstanzen) mit ihrem Detail.
export type Instance = components['schemas']['InstanceResponse'];

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
 * Ein Erfassungspunkt aus der Definition eines Moduls (`process_steps.config`). Von Hand
 * gespiegelt, weil `config` frei ist (der Modultyp entscheidet, `Module.clean_config`); der
 * Abgleich mit `schemas/process.CapturePoint` ist getestet (`tests/test_frontend_mirrors.py`).
 */
export interface CapturePoint {
  key: string;
  label: string;
  type: string;
  target?: number | null;
  tolerance?: number | null;
  /** Worin wird gemessen? (mm · kg · °C …) Ein freies Wort – das System zeigt es nur an. */
  unit?: string | null;
}
/** Was an einem Modul für **eine Instanz** ansteht (`process.step_work`). */
export type StepWork = components['schemas']['StepWork'];
/** Eine Zeile der Stückliste, gegen den Bestand gehalten (`services/consumption`). */
export type StepNeed = components['schemas']['StepNeed'];
/** **Was an einem Modul passiert ist** – lückenlos, je Einzelinstanz (`services/record`). */
export type StepRecord = components['schemas']['StepRecord'];
export type RecordEntry = components['schemas']['RecordEntry'];
export type RecordValue = components['schemas']['RecordValue'];
/**
 * **Alles, was unsere Bezahlkarte braucht** (`services/stripe_pay.prepare`) – inkl. der Angaben,
 * die im ERP schon stehen.
 */
export type PaymentSetup = components['schemas']['PaymentSetup'];
/**
 * **Wie man eine Rechnung überweist** – Bankverbindung, Referenz, QR-Rechnung als Bild. Eine
 * Auskunft, keine Buchung.
 */
export type TransferInfo = components['schemas']['TransferInfo'];
export type ModuleCatalog = components['schemas']['ModuleCatalog'];
/**
 * **Der Beleg** – das Modul «Zahlung» (`services/voucher`). `null` bei jedem anderen
 * Modultyp – die Oberfläche braucht damit keine Fallunterscheidung, genau wie bei `needs`.
 */
export type VoucherEmbed = components['schemas']['VoucherEmbed'];
export type PaperOut = components['schemas']['PaperOut'];
/** Die Vorschau der Papiere einer Handlung (`voucher_docs.preview`). */
export type VoucherPapers = components['schemas']['PapersOut'];
/** **Eine Angebotszeile** – eine Gegenpartei, ein Preis, zwei Fristen; `id` adressiert die Zeile. */
export type VoucherQuoteOut = components['schemas']['VoucherQuoteOut'];
/** **Ein Beleg, den dieser hier mindern könnte** – meist aus einem anderen Auftrag. */
export type VoucherCorrectable = components['schemas']['VoucherCorrectable'];
/** Eine wählbare Gegenpartei – dieselbe Form wie jede Referenz (`ObjectSelect`). */
export type VoucherParty = components['schemas']['VoucherParty'];
/** **Eine Partei des Belegkopfs** – Leistungserbringer bzw. -empfänger (MWSTG Art. 26). */
export type VoucherSide = components['schemas']['VoucherSide'];
/**
 * **Ein Halter** – Objektnummer, Typ, Name (`services/places`); dieselbe Form für Modul-Ziel,
 * Halter einer Einzelinstanz und jede Station ihrer Kette.
 */
export type PlaceRef = components['schemas']['PlaceRef'];
/**
 * **Wo ein Stück liegt** – `chain` von innen nach aussen, mit dem Halter als erstem Element
 * (`holder`). Leer heisst standortlos – ein regulärer Zustand.
 */
export type UnitPlace = components['schemas']['UnitPlace'];
export type ArticleValidation = components['schemas']['ArticleValidation'];
export type CompanyRef = components['schemas']['CompanyRef'];
/** **Eine Anschrift im Adressbuch einer Person** (`services/address_book`). */
export type AddressEntry = components['schemas']['AddressOut'];
export type AddressInput = components['schemas']['AddressIn'];
export type NewCompany = components['schemas']['NewCompany'];
export type PersonCreate = components['schemas']['PersonCreate'];
export type ErpRecordType = 'user' | 'article' | 'order' | 'instance' | 'organization' | 'document';

/** **Ein Dokument** – jede freigegebene Datei (`services/documents`). */
export type DocumentSummary = components['schemas']['DocumentSummary'];
export type DocumentDetail = components['schemas']['DocumentDetail'];
export type DocumentRefOut = components['schemas']['DocumentRefOut'];
export type DocumentProposal = components['schemas']['ProposalOut'];
export type DocumentTarget = components['schemas']['TargetIn'];
export type RecordRef = components['schemas']['RecordOut'];

/**
 * **Ein Unternehmen** (`company_settings`), wie der Server es liefert – mit den Feldnamen
 * des Backends (`street_nr`, `zip_code`, `uid_number`). Abgeleitet und nur lesbar:
 * `is_operator`, `has_address`, `legal_name` (Name + Rechtsform), `website`, `people`.
 */
export type CompanySettings = components['schemas']['CompanySettingsResponse'];
/** Was sich an einem Unternehmen ändern lässt – die Abgeleiteten fehlen hier von selbst. */
export type CompanySettingsUpdate = components['schemas']['CompanySettingsUpdate'];

/** **Eine Nachricht** – das einzige Objekt der Kommunikation. */
export type Message = components['schemas']['MessageOut'];
export type MessageIn = components['schemas']['MessageIn'];
export type MessageChannel = components['schemas']['ChannelOut'];
/** **Der Verlauf eines Datensatzes** (`services/history`) – eine Seite, die neuesten zuerst. */
export type HistoryPage = components['schemas']['HistoryPage'];
export type HistoryEntry = components['schemas']['HistoryEntry'];
export type ChangeBlock = components['schemas']['ChangeBlock'];
/** **Was an einem Datensatz zu tun ist** – die Zahl am Symbol in Feed und Kopf (Nachrichten,
 *  Zeiterfassung, Pflichtangaben, Feiertage). */
export type Todo = components['schemas']['TodoOut'];
export type TodoItem = components['schemas']['TodoItem'];

/** Zeiterfassung (docs/zeiterfassung-spezifikation.md) – jede Zahl in Minuten. */
export type TimeView = components['schemas']['TimeView'];
export type TimeDay = components['schemas']['DayOut'];
export type TimeStamp = components['schemas']['StampOut'];
export type TimeAbsence = components['schemas']['AbsenceOut'];
export type TimeContract = components['schemas']['ContractOut'];
export type TimeVocab = components['schemas']['TimeVocab'];
export type TimeEntryIn = components['schemas']['EntryIn'];
export type EntryPreview = components['schemas']['EntryPreview'];
export type TimeContractIn = components['schemas']['ContractIn'];
export type CompanyTimeView = components['schemas']['CompanyTimeView'];
export type HolidayOut = components['schemas']['HolidayOut'];
export type HolidayIn = components['schemas']['HolidayIn'];
export type TimeRulesIn = components['schemas']['TimeRulesIn'];
export type NewsletterState = components['schemas']['NewsletterState'];
export type Mailbox = components['schemas']['MailboxOut'];
/** **Eine Zeile der Zahlungen** einer Person bzw. einer eigenen Gesellschaft – eine Ableitung
 *  aus den Zahlungsmodulen (`services/payments`). */
export type PaymentRow = components['schemas']['PaymentRow'];

// ─── Öffentliche Seiten: Beleg, Dokument, Rechtstexte ───────────────────────
/** Die Kundenseite eines Belegs (`/beleg?t=…`) – Papier, Weg, Handlungen der Partei. */
export type BelegView = components['schemas']['BelegView'];
export type BelegNote = components['schemas']['NoteOut'];
/** Eine Station des Wegs (Angebot · Auftrag · Rechnung · Bezahlt). */
export type Station = components['schemas']['StationOut'];
/** Die Seite eines Dokuments (`/dokument?t=…`) – Papier, Unterschriften, Handlungen. */
export type PublicDocument = components['schemas']['PublicDocument'];
/** AGB, Datenschutz oder Impressum als A4-Dokument bzw. Link auf die Datei. */
export type LegalText = components['schemas']['LegalOut'];
/** Eine Runde Verfassen (KI) – das Papier als A4-HTML, nichts gespeichert. */
export type ComposeResult = components['schemas']['ComposeOut'];
/** Ein hochgeladenes Bild, das kein Dokument ist (die gezeichnete Unterschrift). */
export type UploadResult = components['schemas']['UploadResult'];

// ─── Phase 5 · Der Assistent (docs/konzept/phase5-bauplan.md) ─────────────────

/** **Gespräch und Handgriff** – Backend `schemas/assistant.py`. Beides sind Ereignisse im Log;
 *  offen ist abgeleitet. */
export type Talk = components['schemas']['TalkOut'];
export type TalkFile = components['schemas']['FileRef'];
export type Handgriff = components['schemas']['HandgriffOut'];
export type HandgriffOperation = components['schemas']['OperationOut'];
export type HandgriffRun = components['schemas']['RunOut'];
export type HandgriffProbe = components['schemas']['ProbeOut'];
export type Pinned = components['schemas']['PinnedOut'];

/** Eine **Aufnahme** (Phase 4): Nummer = Log-Id von `recording.start`; `talk`, sobald der Text
 *  im Gespräch steht (`docs/konzept/phase4-bauplan.md`). */
export type Recording = components['schemas']['Recording'];
