// ⚠ GENERIERT aus backend/app/domain/… – NICHT EDITIEREN.
//   Neu erzeugen: cd backend && python -m scripts.dump_vocab
//
// **Das Vokabular ist eine Quelle, kein Spiegel.** Ein neuer Schlüssel wird ausschliesslich
// im Backend ergänzt. Was die Oberfläche selbst hält (Symbol, Farbwert, Hover-Satz), tippt
// sie gegen die Typen hier (`Record<ModuleKey, …>`) – fehlt ein Eintrag, baut sie nicht.

/** Instanz-Arten (`models/instance.KINDS`). */
export const INSTANCE_KINDS = ["einzeln", "batch"] as const;
export type InstanceKind = (typeof INSTANCE_KINDS)[number];

/** Die Prozessschrittmodule (`domain/modules.KEYS`). */
export const MODULE_KEYS = ["datenerfassung", "aussondern", "bewegen", "beleg", "verbrauch"] as const;
export type ModuleKey = (typeof MODULE_KEYS)[number];

/** Die Farbfamilie je Modul (`Module.tone`). */
export const MODULE_TONES = {
  "datenerfassung": "slate",
  "aussondern": "clay",
  "bewegen": "moss",
  "beleg": "plum",
  "verbrauch": "sand",
} as const;

export type ModuleTone = (typeof MODULE_TONES)[ModuleKey];

/** Die Kompetenzen – eine Liste (`domain/competences`). */
export const COMPETENCES = ["Kommunizieren", "Verrechnen", "Bewegen", "Bauen", "Prüfen", "Schweissen", "Elektrik", "Kranprüfung"] as const;
export type Competence = (typeof COMPETENCES)[number];

/** Die Vorgabe je Modul (`Module.competence`), am Schritt tauschbar. */
export const MODULE_COMPETENCES = {
  "datenerfassung": "Prüfen",
  "aussondern": "Bewegen",
  "bewegen": "Bewegen",
  "beleg": "Verrechnen",
  "verbrauch": "Bauen",
} as const;

/** Erfassungspunkt-Typen (`domain/capture_types.KEYS`). */
export const CAPTURE_KEYS = ["text", "bool", "photo", "signature", "measure"] as const;
export type CaptureKey = (typeof CAPTURE_KEYS)[number];

/** Aussondern: Ausprägung → Verb (`Aussondern.ACTIONS`). */
export const DISPOSAL_ACTIONS = {
  "scrap": "Verschrotten",
  "block": "Sperren",
} as const;
export type DisposalMode = keyof typeof DISPOSAL_ACTIONS;

/** Die Richtungen eines Geldvorgangs (`voucher.DIRECTIONS`) – `weQuote`: wir nennen den Preis (`quoted_by`). */
export const VOUCHER_DIRECTIONS = {
  "in": {"label": "Einnahme", "hint": "Einnahme – wir stellen Rechnung, Geld kommt herein.", "partyRef": false, "weQuote": true},
  "out": {"label": "Ausgabe", "hint": "Ausgabe – wir bekommen Rechnung, Geld geht hinaus.", "partyRef": true, "weQuote": false},
} as const;
export type VoucherDirectionKey = keyof typeof VOUCHER_DIRECTIONS;

/** Die Gegenpartei – in beiden Richtungen gleich (`voucher.PARTY`). */
export const VOUCHER_PARTY = "Partner";

/** Stufen und Ausgänge eines Geldvorgangs (`voucher.STAGES`, `DONE`, `CANCELLED`) – Schlüssel, keine Wörter. */
export const VOUCHER_STAGE = {
  "offer": "offer",
  "agreed": "agreed",
  "billed": "billed",
  "done": "done",
  "cancelled": "cancelled",
} as const;
export type VoucherStageKey = keyof typeof VOUCHER_STAGE;

/** Der Stand eines Belegs – Karte und Zahlungsliste (`voucher.STATES`): Schlüssel → Wort. */
export const VOUCHER_STATES = {
  "open": "Offen",
  "partial": "Teilweise bezahlt",
  "overdue": "Überfällig",
  "overpaid": "Überzahlt",
  "settled": "Beglichen",
  "void": "Storniert",
} as const;
export type VoucherStateKey = keyof typeof VOUCHER_STATES;

/** Zustände einer Angebotszeile (`voucher.ASKED` …). */
export const QUOTE_STATE = {
  "asked": "angefragt",
  "quoted": "offeriert",
  "declined": "abgelehnt",
  "chosen": "gewaehlt",
} as const;

/** Was das Modul dem Beleg vorgeben darf (`Beleg.PRESETS` / `PRESET_LABELS`), in dieser Reihenfolge. */
export const VOUCHER_PRESET_LABELS = {
  "payment_days": "Zahlungsfrist",
  "lead_days": "Lieferfrist",
  "valid_days": "Gültig",
  "incoterm": "Lieferbedingung",
  "ownership": "Eigentum",
} as const;
export type VoucherPresetKey = keyof typeof VOUCHER_PRESET_LABELS;

/** Wem die Stücke danach gehören (`voucher.OWNERSHIP`). */
export const VOUCHER_OWNERSHIP = [{"value": "party", "label": "geht an die Partei"}, {"value": "us", "label": "geht an uns"}] as const;
export type VoucherOwnership = (typeof VOUCHER_OWNERSHIP)[number];

/** Die Klauseln der Incoterms 2020 (`incoterms.INCOTERMS`). */
export const INCOTERMS = [{"key": "EXW", "label": "Ab Werk"}, {"key": "FCA", "label": "Frei Frachtführer"}, {"key": "CPT", "label": "Frachtfrei"}, {"key": "CIP", "label": "Frachtfrei versichert"}, {"key": "DAP", "label": "Geliefert benannter Ort"}, {"key": "DPU", "label": "Geliefert entladen"}, {"key": "DDP", "label": "Geliefert verzollt"}, {"key": "FAS", "label": "Frei Längsseite Schiff"}, {"key": "FOB", "label": "Frei an Bord"}, {"key": "CFR", "label": "Kosten und Fracht"}, {"key": "CIF", "label": "Kosten, Versicherung, Fracht"}] as const;
export type Incoterm = (typeof INCOTERMS)[number];

/** Versandarten einer E-Mail (`communication.DELIVERIES`). */
export const DELIVERY_LABELS = {
  "mail": "Mail",
  "circular": "Rundschreiben",
  "newsletter": "Newsletter",
} as const;
export type DeliveryKey = keyof typeof DELIVERY_LABELS;

/** Arten eines Kanals (`communication.CHANNELS` + Postfach). */
export const CHANNEL_KINDS = ["phone", "internal", "note", "email"] as const;
export type ChannelKind = (typeof CHANNEL_KINDS)[number];

/** Lucide-Namen der Zeiterfassung (`timekeeping.ARTS`, `HINTS`). */
export const TIME_ICON_NAMES = ["sun", "thermometer", "activity", "shield", "baby", "calendar-check", "calendar-x", "alert-triangle", "octagon-alert", "file-warning"] as const;
export type TimeIconName = (typeof TIME_ICON_NAMES)[number];

/** Takte der Wiederholung (`loop.EVERY`). */
export const LOOP_EVERY = {
  "week": "wöchentlich",
  "month": "monatlich",
  "quarter": "vierteljährlich",
  "half": "halbjährlich",
  "year": "jährlich",
} as const;
export type LoopEvery = keyof typeof LOOP_EVERY;

/** Was eine Wiederholung je Zeile nimmt (`loop.TAKES`). */
export const LOOP_TAKES = {
  "same": "gleiche Einzelinstanzen",
  "fifo": "FIFO",
  "new": "neu erzeugt",
} as const;
export type LoopTake = keyof typeof LOOP_TAKES;

/** Das eine Datum am Auftrag (`order_date.KINDS`): Wort im Prozessbild. */
export const ORDER_DATE_KINDS = {
  "until": "bis",
  "from": "ab",
} as const;
export type OrderDateKind = keyof typeof ORDER_DATE_KINDS;

/** Die Rollen – die Rolle ist der Zugang (`policy.ROLES`). */
export const ROLES = ["admin", "employee", "user"] as const;
export type Role = (typeof ROLES)[number];

/** Wer ins ERP darf (`policy.STAFF_ROLES`) – gefragt nur über `record-status.isStaff`. */
export const STAFF_ROLES = ["admin", "employee"] as const;
export type StaffRole = (typeof STAFF_ROLES)[number];

/** Wie ein Entwurf im Prozessbild heisst (`schemas/order.DRAFT_OBJECT_ID`). */
export const DRAFT_OBJECT_ID = 0;

/** `app.schemas.process.CapturePoint` */
export interface CapturePoint {
  key: string;
  label: string;
  type: string;
  target?: number | null;
  tolerance?: number | null;
  unit?: string | null;
}

/** Ein Eintrag einer Tabelle zu einem Schlüssel, der von aussen kommt (Antwort, Entwurf)
 *  – `undefined`, wenn es ihn nicht gibt (auch nicht über den Prototyp). */
export function lookup<K extends string, V>(table: Readonly<Record<K, V>>,
                                            key: string | null | undefined): V | undefined {
  return key != null && Object.prototype.hasOwnProperty.call(table, key)
    ? table[key as K] : undefined;
}
