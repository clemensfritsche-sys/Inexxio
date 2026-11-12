/**
 * Prozessschrittmodule und Erfassungspunkt-Typen — **Symbole und Farben**, sonst nichts.
 *
 * Die Listen stehen im Backend (`domain/modules.py`, `domain/capture_types/`, über
 * `GET /erp/orders/module-catalog`); welche Farbfamilie ein Typ trägt, sagt `tone`. Hier liegt
 * nur, was eine Antwort nicht transportieren kann – getippt gegen die generierten Schlüssel
 * (`lib/vocab.ts`): ein Schlüssel ohne Eintrag hier baut nicht.
 */

import {
  Blocks, Camera, CircleHelp, ClipboardCheck,
  HandCoins, Handshake, MoveRight, PackageX, PenLine, Ruler, ShoppingCart,
  ThumbsUp, Type, type LucideIcon,
} from 'lucide-react';

import { emptyLine, type DefinitionLine } from '@/components/erp/definition-lines';
import {
  DISPOSAL_ACTIONS, VOUCHER_DIRECTIONS, VOUCHER_PRESET_LABELS, lookup,
  type CaptureKey, type Competence, type DisposalMode, type ModuleKey, type ModuleTone, type VoucherDirectionKey,
  type VoucherPresetKey,
} from '@/lib/vocab';

/** Erfassungspunkt-Typen (`domain/capture_types/`). */
export const CAPTURE_ICON: Record<CaptureKey, LucideIcon> = {
  text: Type,
  bool: ThumbsUp,
  photo: Camera,
  signature: PenLine,
  measure: Ruler,
};

/** Prozessschrittmodule (`domain/modules.py`). */
const MODULE_ICON: Record<ModuleKey, LucideIcon> = {
  datenerfassung: ClipboardCheck,
  aussondern: PackageX,
  verbrauch: Blocks,
  // Von hier nach dort – kein Transportmittel: womit, entscheidet die Ausführung.
  bewegen: MoveRight,
  // Geld wechselt die Hand – ein Symbol für beide Richtungen (`VOUCHER_DIRECTION`).
  beleg: HandCoins,
};

/**
 * **Die beiden Richtungen eines Geldvorgangs — Symbol und Satz.** Alles Übrige reist mit dem
 * Vorgang (`VoucherEmbed`). Wort, Satz, `partyRef` und `weQuote` kommen aus `lib/vocab`
 * (`domain/voucher.DIRECTIONS`); hier steht nur das Symbol. Keine zwei Farben: Farbe ist im ERP
 * für die Ampel reserviert. «Einnahme» ↔ «Ausgabe», weil das Modul auch Miete, Lohn und Gebühr kann.
 */
const DIRECTION_ICON: Record<VoucherDirectionKey, LucideIcon> = {
  // Der Handschlag – Geld kommt herein, weil eine Zusage nach aussen erfüllt wird.
  in: Handshake,
  // Der Einkaufswagen – Geld geht hinaus, weil wir etwas beziehen.
  out: ShoppingCart,
};
export const VOUCHER_DIRECTION = {
  in: { ...VOUCHER_DIRECTIONS.in, icon: DIRECTION_ICON.in },
  out: { ...VOUCHER_DIRECTIONS.out, icon: DIRECTION_ICON.out },
} satisfies Record<VoucherDirectionKey, unknown>;

/**
 * **Was ist zu tun? — EIN Satz am Modul, freiwillig** («Härten auf 58 HRC»), für jeden Partner
 * gleich. Leer heisst «gemäss Spezifikation».
 */
export const VOUCHER_TASK = 'Was ist zu tun?';
export const VOUCHER_TASK_HINT =
  'Ergänzung zu den Positionen – leer heisst «gemäss Spezifikation»';

/**
 * **Wie bestellen? — je Partner, Pflicht, und nur wo WIR bestellen** (seine
 * Artikelnummer, sein Shop-Link). Eine Eigenschaft der Paarung Modul × Partner; ob es sie
 * gibt, sagt die Richtung (`VOUCHER_DIRECTION[…].partyRef`).
 */
export const VOUCHER_ORDER_REF = 'Wie bestellen?';
export const VOUCHER_ORDER_REF_HINT = 'Seine Artikelnummer oder der Link zu seinem Shop';
/** Wofür «Wie bestellen?» da ist – im Unterschied zum Link an der einzelnen Offerte. */
export const VOUCHER_ORDER_REF_TIP = 'Wie bestellen? – gilt für jede Bestellung bei diesem Partner: '
  + 'seine Artikelnummer oder der Link zum Artikel in seinem Shop. Die Nummer einer einzelnen '
  + 'Bestellung steht an der Offerte («Bestellnummer»).';

/**
 * ►►► **Was das Modul dem Beleg vorgeben DARF** (`Beleg.PRESETS` / `PRESET_LABELS`, generiert). ◄◄◄
 * Was hier steht, gilt für jeden Auftrag aus diesem Prozess; leer heisst «wählt der Mensch am
 * Beleg». Schlüssel, Reihenfolge und Wort kommen aus `lib/vocab`; hier stehen Hover und Tage.
 */
const PRESET_UI: Record<VoucherPresetKey, { days?: true; hint: string }> = {
  payment_days: { days: true, hint: 'Tage bis zur Fälligkeit der Rechnung – 0 heisst Vorauszahlung' },
  lead_days: { days: true, hint: 'Tage ab der Zusage bis zur Lieferung' },
  valid_days: { days: true, hint: 'Wie viele Tage die Offerte gilt (1 bis 365)' },
  incoterm: { hint: 'Incoterms 2020 – wer Kosten und Risiko trägt; den Ort nennt der Beleg' },
  ownership: { hint: 'Wem die Stücke gehören, wenn sie das Modul passieren' },
};
export const VOUCHER_PRESETS: { key: VoucherPresetKey; label: string; days?: true; hint: string }[] =
  (Object.keys(VOUCHER_PRESET_LABELS) as VoucherPresetKey[]).map((key) => ({
    key, label: VOUCHER_PRESET_LABELS[key], ...PRESET_UI[key],
  }));

/** **Leer heisst «wählt der Mensch am Beleg»** – kurz im leeren Feld, ausgeschrieben im Hover. */
export const VOUCHER_PRESET_OPEN = 'am Beleg';
export const VOUCHER_PRESETS_HINT = 'Was hier steht, gilt für jeden Auftrag aus diesem Prozess '
  + 'und steht im Beleg fest. Leer heisst: wählt der Mensch am Beleg.';

/** Die Richtung zu einem Schlüssel. Unbekannt → Ausgabe, wie im Backend (`voucher.of`). */
export function voucherDirection(direction: string | undefined | null) {
  return lookup(VOUCHER_DIRECTION, direction) ?? VOUCHER_DIRECTION.out;
}

/**
 * **Die Farbfamilien der Module — die eine Stelle.** Getrennt von der Ampel: ein Modul ist
 * kein Zustand (PROCESS_CORE.md §5.3), darum Neutraltöne statt Signalfarben.
 */
export const MODULE_TONE: Record<ModuleTone | 'teal', { bg: string; fg: string; border: string }> = {
  slate: { bg: 'var(--accent-soft)', fg: 'var(--accent-ink)', border: '#BFD6E2' },
  sand: { bg: '#F4EBDD', fg: '#9A7238', border: '#E4D2B8' },
  moss: { bg: '#E9EFE6', fg: '#5A7048', border: '#CBD9C2' },
  clay: { bg: '#F3E7E4', fg: '#8C5A50', border: '#E2CBC5' },
  // Zahlung: gedämpftes Violett – die einzige Familie, die sonst kein Modul besetzt.
  plum: { bg: '#EFEAF2', fg: '#6B5A78', border: '#DCD2E2' },
  // Kein Modul trägt Blaugrün; die Kommunikation nimmt es als eine der Betreff-Farben.
  teal: { bg: '#E4EEEE', fg: '#4A6E70', border: '#C8DCDC' },
};

/**
 * **Das Symbol eines Moduls.** Unbekanntes sieht unbekannt aus (Fragezeichen), nie wie ein
 * anderes Modul.
 */
export function moduleIcon(type: string | undefined | null): LucideIcon {
  return lookup(MODULE_ICON, type) ?? CircleHelp;
}

/**
 * **Die Farbe eines Moduls** (`ModuleFacts.tone`). Eine unbekannte Familie ist ein Fehler und
 * sieht auch so aus.
 */
export function moduleTone(tone: string | undefined | null): { bg: string; fg: string; border: string } {
  return lookup(MODULE_TONE, tone) ?? UNKNOWN_TONE;
}

/** Sichtbar kaputt: keine Modulfarbe, sondern die Warnfarbe des Hauses. */
const UNKNOWN_TONE = { bg: 'var(--danger-bg)', fg: 'var(--danger)', border: 'var(--danger)' };

/** Der Schlüssel des Bewegen-Moduls – ein «Holen lassen» baut eines. */
export const MOVE_MODULE = 'bewegen';

/** Der Erfassungspunkt-Typ, der in der Definition einen **Sollwert** braucht (`Measure.clean`). */
export const NEEDS_TARGET = 'measure';

/**
 * **Hinter einem Ausgang kann kein Modul mehr stehen** (wie `domain/chain`, nur früher). Ein
 * dahinter gezogenes Modul bleibt sichtbar (zum Löschen), das Bild sagt, dass so nichts läuft.
 */
export function chainProblems(steps: { label: string; terminal: boolean }[]): string[] {
  const exit = steps.findIndex((s) => s.terminal);
  if (exit < 0 || exit === steps.length - 1) return [];
  return [`Hinter «${steps[exit].label}» kann kein Modul mehr stehen: was hier ankommt, `
    + `verlässt den Auftrag – Schritt ${exit + 2} bekäme nie ein Stück.`];
}

/**
 * **Die Stichprobe ist EINE Zahl: der Anteil an allem, was am Modul wartet**
 * (`domain/sampling.py`); die Kurzwege sind Werte derselben Zahl. `value` ist ein String
 * (halb getippt); geprüft wird serverseitig.
 */
export interface SampleDraft {
  /** Der gewählte Kurzweg – oder `free`, dann zählt `value`. */
  mode: SampleMode;
  value: string;
}

export type SampleMode = 'all' | 'half' | 'quarter' | 'free';

/** Kurzweg → Anteil. Die eine Zuordnung; `free` hat keinen festen Wert. */
export const SAMPLE_PRESETS: { value: SampleMode; label: string; percent?: number }[] = [
  { value: 'all', label: 'Alle', percent: 100 },
  { value: 'half', label: 'Hälfte', percent: 50 },
  { value: 'quarter', label: 'Viertel', percent: 25 },
  { value: 'free', label: 'Anteil' },
];

/** Was ohne Angabe gilt – **alle**, wie im Backend (`sampling.DEFAULT`). */
const SAMPLE_ALL: SampleDraft = { mode: 'all', value: '' };

/** Entwurfsform → das eine Feld des Servers. Ein frei getippter Anteil geht unverändert hinaus. */
export function samplePayload(s: SampleDraft): { percent: string | number } {
  const preset = SAMPLE_PRESETS.find((p) => p.value === s.mode)?.percent;
  return { percent: preset ?? s.value };
}

/**
 * Ein Erfassungspunkt im Entwurf. `key` vergibt der Server aus der Bezeichnung. Ein `required`
 * gibt es nicht: alles Angelegte ist Pflicht.
 */
export interface PointDraft {
  label: string;
  type: string;
  target?: string;
  tolerance?: string;
  /** Worin gemessen wird – nur beim Soll-Ist (mm · kg · °C …); ein freies Wort, nur angezeigt. */
  unit?: string;
}

/**
 * Ein Modul im Entwurf — dieselbe Form am Artikel wie im Auftrag. Kein Name (den sagt der Typ);
 * `id` ist lokal, die Identität vergibt der Server.
 */
export interface ModuleDraft {
  id: number;
  moduleType: string;
  /** **Wer kann das?** – eine Kompetenz aus `COMPETENCES`; leer = die Vorgabe des Moduls
   *  (`MODULE_COMPETENCES`, Projektakte «Aufgaben» §3). Für jedes Modul gleich. */
  competence: string;
  points: PointDraft[];
  /** **Wie viele der wartenden Stücke erfasst werden** – der Anteil an der Gesamtmenge.
   *  Pflichtfeld der Entwurfsform; ihr Vorgabewert ist `SAMPLE_ALL`. */
  sample: SampleDraft;
  /** Nur «Aussondern»: verschrotten (endgültig) oder sperren (aufhebbar). */
  mode: DisposalMode;
  /**
   * Nur «Aussondern»: **warum** hier ausgesondert wird. Pflicht beim **Modellieren**,
   * nicht am Band – der Anlass lautet bei jedem Stück gleich (`Aussondern.clean_config`).
   */
  reason: string;
  /**
   * Nur «Verbrauch»: die Stückliste – je Zeile Artikel und Menge pro Einzelinstanz (auch in
   * der Artikel-Vorlage, darum Artikel statt Definitionszeilen).
   */
  lines: DefinitionLine[];
  /**
   * Nur «Bewegen»: **wohin** die Stücke gebracht werden – die Objektnummer eines Halters.
   * **Optional**: leer heisst «wird beim Ausführen gewählt». Ein String (Eingabefeld).
   */
  target: string;
  /** Nur «Zahlung»: kommt Geld herein oder geht es hinaus? (`in` ↔ `out`). */
  direction: string;
  /**
   * Nur «Zahlung»: die zugelassenen Gegenparteien – Nummer und Bestellangabe (nur, wo wir
   * bestellen). Leer heisst frei.
   */
  parties: { party: number; ref: string }[];
  /** Nur «Zahlung»: **was ist zu tun?** – ein Satz am Modul, freiwillig. */
  instruction: string;
  /**
   * Nur «Zahlung»: die **Vorgaben an den Beleg** (`VOUCHER_PRESETS`) – je Schlüssel ein
   * String (ein halb getipptes Feld hat keine Zahl). Leer heisst «wählt der Mensch am Beleg».
   */
  presets: Record<VoucherPresetKey, string>;
  /**
   * Nur «Zahlung», nur bei einer Einnahme: vorgegebene Einzelpreise je Artikel (`Beleg.PRICES`).
   * `name` nur für die Anzeige.
   */
  prices: PricePreset[];
}

/** Ein vorgegebener Preis im Editor: Artikel (Nummer, Name zur Anzeige) und Einzelpreis. */
export interface PricePreset { article: number | null; name: string; price: string }

/** **Die Ausprägungen des Aussonderns** – Schlüssel und Verb aus dem Backend (`Aussondern.ACTIONS`,
 *  generiert), den Zielzustand sagt der Server; hier steht nur der Hover. */
const DISPOSAL_HINT: Record<DisposalMode, string> = {
  scrap: 'Physisch entsorgt – endgültig, kein Weg zurück',
  block: 'Bleibt vorhanden, ist aber nicht mehr einplanbar',
};
export const DISPOSAL_MODES: { value: DisposalMode; label: string; hint: string }[] =
  (Object.keys(DISPOSAL_ACTIONS) as DisposalMode[]).map((value) => ({
    value, label: DISPOSAL_ACTIONS[value], hint: DISPOSAL_HINT[value],
  }));

/**
 * **Die Definition eines Geld-Moduls — Richtung, zugelassene Partner, Auftrag.** Kein Steuersatz,
 * keine Vorauszahlungs-Sperre: beides steht erst fest, wenn ein Auftrag läuft.
 */
const MONEY_FORM = {
  draft: (c: Record<string, unknown>) => ({
    // Tolerant gelesen: eine fehlende Richtung ist eine Ausgabe, wie im Backend.
    direction: (c.direction === 'in' ? 'in' : 'out') as 'in' | 'out',
    // Je Partner eine Zeile `{ party, ref }` – die einzige Form, die der Editor schreibt.
    parties: asRows(c.parties).map((r) => ({
      party: Number(r.party), ref: String(r.ref ?? ''),
    })).filter((r) => Number.isFinite(r.party)),
    instruction: String(c.instruction ?? ''),
    presets: presetsDraft(c),
    prices: asRows(c.prices).map((r) => ({
      article: Number.isFinite(Number(r.article)) ? Number(r.article) : null,
      name: '', price: String(r.price ?? ''),
    })),
  }),
  config: (m: ModuleDraft) => ({
    direction: m.direction,
    parties: m.parties.map((r) => ({ party: r.party, ref: r.ref.trim() })),
    instruction: m.instruction.trim(),
    // Ein Preis ohne Artikel oder Betrag ist noch keine Vorgabe – er geht nicht hinaus.
    prices: voucherDirection(m.direction).weQuote
      ? m.prices.filter((p) => p.article !== null && p.price.trim() !== '')
        .map((p) => ({ article: p.article, price: p.price.trim() }))
      : [],
    // Leer geht als `null` hinaus; eine Zahl unverändert – ob sie gilt, sagt der Server.
    ...Object.fromEntries(VOUCHER_PRESETS.map(({ key }) => {
      const v = (m.presets[key] ?? '').trim();
      return [key, v === '' ? null : v];
    })),
  }),
};

/** Die gespeicherten Vorgaben zurück in die Eingabeform – fehlend = leer. */
function presetsDraft(c: Record<string, unknown>): Record<VoucherPresetKey, string> {
  return Object.fromEntries(VOUCHER_PRESETS.map(({ key }) => [
    key, c[key] == null ? '' : String(c[key]),
  ])) as Record<VoucherPresetKey, string>;
}

/** Ein leerer Satz Vorgaben – alles wählt der Mensch am Beleg. */
function blankPresets(): Record<VoucherPresetKey, string> {
  return presetsDraft({});
}

/**
 * **Was ein Modultyp im Entwurf ausmacht — je Typ ein Eintrag, nicht je Stelle ein `if`.**
 * Ob ein Entwurf vollständig ist, sagt der Server (`POST …/validate`, `Module.clean_config`);
 * hier steht nur die Form der Eingabe. Getippt gegen `ModuleKey`: ein Modultyp ohne Eintrag baut nicht.
 */
const MODULE_FORM: Record<ModuleKey, {
  config: (m: ModuleDraft) => Record<string, unknown>;
  /** Die Umkehrform – gespeicherte Konfiguration → Entwurf (eingefroren: dieselben Felder, gesperrt). */
  draft: (config: Record<string, unknown>) => Partial<ModuleDraft>;
}> = {
  datenerfassung: {
    draft: (c) => ({
      points: asRows(c.points).map((p) => ({
        label: String(p.label ?? ''),
        type: String(p.type ?? 'text'),
        target: p.target == null ? '' : String(p.target),
        tolerance: p.tolerance == null ? '' : String(p.tolerance),
        unit: p.unit == null ? '' : String(p.unit),
      })),
      sample: sampleDraft(c.sample),
    }),
    config: (m) => ({
      points: m.points.map((p) => ({
        label: p.label,
        type: p.type,
        target: p.type === NEEDS_TARGET && p.target !== '' ? Number(p.target) : null,
        tolerance: p.type === NEEDS_TARGET && p.tolerance !== '' ? Number(p.tolerance) : null,
        // Die Einheit gehört zum Sollwert.
        unit: p.type === NEEDS_TARGET ? (p.unit ?? '').trim() : null,
      })),
      sample: samplePayload(m.sample),
    }),
  },
  aussondern: {
    draft: (c) => ({
      mode: (c.mode === 'block' ? 'block' : 'scrap') as DisposalMode,
      reason: String(c.reason ?? ''),
    }),
    // Zwei Angaben, beide Pflicht: was passiert (verschrotten ↔ sperren) und warum.
    config: (m) => ({ mode: m.mode, reason: m.reason }),
  },
  bewegen: {
    draft: (c) => ({ target: c.target == null ? '' : String(c.target) }),
    // Eine Angabe, optional: leer geht ausdrücklich als `null` hinaus.
    config: (m) => ({ target: m.target.trim() === '' ? null : Number(m.target) }),
  },
  beleg: MONEY_FORM,
  verbrauch: {
    draft: (c) => ({
      lines: asRows(c.lines).map((r, i) => ({
        ...emptyLine(i + 1),
        articleObjectId: Number(r.article),
        quantity: Number(r.quantity ?? 1),
      })).filter((l) => Number.isFinite(l.articleObjectId as number)),
    }),
    // Zwei Angaben je Zeile, beide Pflicht: welcher Artikel und wie viele je Einzelinstanz.
    config: (m) => ({
      lines: m.lines
        .filter((l) => l.articleObjectId !== null)
        .map((l) => ({ article: l.articleObjectId as number, quantity: l.quantity })),
    }),
  },
};

/** Eine gespeicherte Liste als Zeilen lesen (sie kommt aus JSONB) – was keine Zeile ist, fällt weg. */
function asRows(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.filter((v): v is Record<string, unknown> => !!v && typeof v === 'object');
}

/** Der gespeicherte Anteil zurück in die Eingabeform – trifft er einen Kurzweg, steht der Regler dort. */
function sampleDraft(value: unknown): SampleDraft {
  const percent = Number((value as { percent?: unknown } | null)?.percent ?? NaN);
  if (!Number.isFinite(percent)) return { ...SAMPLE_ALL };
  const preset = SAMPLE_PRESETS.find((p) => p.percent === percent);
  return preset ? { mode: preset.value, value: '' } : { mode: 'free', value: String(percent) };
}

/** Ein gespeichertes Modul als Entwurf; ein unbekannter Typ liefert den leeren Entwurf. */
export function moduleFromConfig(id: number, moduleType: string,
                                 config: Record<string, unknown> | null | undefined): ModuleDraft {
  return { ...blankModule(id, moduleType),
           ...(lookup(MODULE_FORM, moduleType)?.draft(config ?? {}) ?? {}),
           competence: typeof config?.competence === 'string' ? config.competence : '' };
}

/** Ein frischer Entwurf dieses Modultyps – mit den Vorgaben, die das Backend kennt. */
export function blankModule(id: number, moduleType: string): ModuleDraft {
  return {
    id, moduleType, competence: '', points: [], sample: { ...SAMPLE_ALL }, mode: 'scrap', reason: '',
    lines: [], target: '',
    // Die Vorgabe ist die Einnahme; der Server verlangt die Richtung (`Beleg.clean_config`).
    direction: 'in', parties: [], instruction: '', presets: blankPresets(), prices: [],
  };
}

/** Entwurfsform → API-Form (`schemas/process.ModuleInput`). Der Typ geht hinaus, wie er dasteht –
 *  ein unbekannter weist der Server mit einem Satz ab (`modules.get`), nicht die Oberfläche. */
export function toModulePayload(m: ModuleDraft) {
  return { module_type: m.moduleType as ModuleKey,
           config: { ...(lookup(MODULE_FORM, m.moduleType)?.config(m) ?? {}),
                     ...(m.competence ? { competence: m.competence as Competence } : {}) } };
}
