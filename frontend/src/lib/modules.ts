/**
 * Prozessschrittmodule und Erfassungspunkt-Typen — **Symbole und Farben**, sonst nichts.
 *
 * Die Listen selbst stehen im Backend (`domain/modules.py`, `domain/capture_types/`) und
 * kommen über `GET /erp/orders/module-catalog`. Hier liegt nur, was eine Antwort nicht
 * transportieren kann: das Icon und die konkreten Farbwerte. **Welche** Farbfamilie ein
 * Modultyp trägt, sagt das Backend (`tone`) – ein neuer Modultyp ist damit ein Eintrag in
 * der Registry und kein Eingriff in die Oberfläche.
 *
 * `backend/tests/test_frontend_mirrors.py` prüft, dass Symbole und Farbfamilien **genau**
 * die Schlüssel des Backends abdecken: ein Typ ohne Symbol wäre eine leere Fläche, ein
 * Symbol ohne Typ eine tote Zeile.
 */

import {
  Blocks, Camera, CircleHelp, ClipboardCheck,
  HandCoins, Handshake, MoveRight, PackageX, PenLine, Ruler, ShoppingCart,
  ThumbsUp, Type, type LucideIcon,
} from 'lucide-react';

import { emptyLine, type DefinitionLine } from '@/components/erp/definition-lines';

/** Erfassungspunkt-Typen (`domain/capture_types/`). */
export const CAPTURE_ICON: Record<string, LucideIcon> = {
  text: Type,
  bool: ThumbsUp,
  photo: Camera,
  signature: PenLine,
  measure: Ruler,
};

/** Prozessschrittmodule (`domain/modules.py`). */
export const MODULE_ICON: Record<string, LucideIcon> = {
  datenerfassung: ClipboardCheck,
  aussondern: PackageX,
  verbrauch: Blocks,
  // Von hier nach dort – bewusst **kein** Transportmittel (kein Lastwagen, kein
  // Gabelstapler): womit bewegt wird, entscheidet sich erst bei der Ausführung.
  bewegen: MoveRight,
  // Geld wechselt die Hand – in beide Richtungen dasselbe Symbol, denn es ist dasselbe
  // Modul; die Richtung zeigt das Zeichen im Vorgang (`VOUCHER_DIRECTION`).
  beleg: HandCoins,
};

/**
 * **Die beiden Richtungen eines Geldvorgangs — Symbol und Satz.**
 *
 * Alles Übrige zur Richtung (Wörter, Stufen, Verben) reist mit dem Vorgang
 * (`VoucherEmbed`); hier steht nur, was eine Antwort nicht transportieren kann. Gespiegelt
 * von `backend/app/domain/voucher.py`, deckungsgleich gehalten von `test_frontend_mirrors`.
 * Keine zwei Farben: Farbe ist im ERP für die Ampel reserviert.
 *
 * Die Werte heissen «Einnahme» ↔ «Ausgabe» (#831) – das Modul kann auch Miete, Lohn und
 * Gebühr, ein «Verkauf» wäre enger. Die Symbole (Handschlag ↔ Einkaufswagen, #845) zeigen
 * die häufigste Gestalt der Sache; zwei gespiegelte Pfeile wären auf 15 px dasselbe Zeichen.
 */
export const VOUCHER_DIRECTION: Record<string, {
  icon: LucideIcon; label: string; hint: string;
  /**
   * **Gibt es hier die Frage «wie bestelle ich bei ihm?»** Nur, wo **wir** bestellen.
   * Gespiegelt von `Direction.party_ref` – der Dienst verwirft einen trotzdem gesendeten
   * Wert; dies ist die freundliche Hälfte derselben Regel, nie ein zweiter Massstab.
   */
  partyRef: boolean;
}> = {
  in: {
    // Der Handschlag – Geld kommt herein, weil eine Zusage nach aussen erfüllt wird.
    icon: Handshake, label: 'Einnahme',
    hint: 'Einnahme – wir stellen Rechnung, Geld kommt herein.',
    partyRef: false,
  },
  out: {
    // Der Einkaufswagen – Geld geht hinaus, weil wir etwas beziehen.
    icon: ShoppingCart, label: 'Ausgabe',
    hint: 'Ausgabe – wir bekommen Rechnung, Geld geht hinaus.',
    partyRef: true,
  },
};

/**
 * **Die Gegenpartei heisst in beiden Richtungen gleich** – es ist dieselbe Rolle, der
 * andere im Geschäft. Singular = Plural (#787). Gespiegelt von `domain/voucher`.
 */
export const VOUCHER_PARTY = 'Partner';

/**
 * **Was ist zu tun? — EIN Satz am Modul, freiwillig** («Härten auf 58 HRC»). Er lautet
 * für jeden Partner gleich. Leer heisst «gemäss Spezifikation»: *was* es ist, sagen die
 * Positionen.
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

/**
 * ►►► **Was das Modul dem Beleg vorgeben DARF** (`Beleg.PRESETS` / `PRESET_LABELS`). ◄◄◄
 *
 * Das Modul ist Master: was hier steht, gilt für jeden Auftrag aus diesem Prozess und steht
 * im Beleg fest; **leer heisst «wählt der Mensch am Beleg»**. Gespiegelt von
 * `domain/modules.Beleg`, deckungsgleich gehalten von `test_frontend_mirrors`.
 */
export type VoucherPresetKey = 'payment_days' | 'lead_days' | 'valid_days' | 'incoterm' | 'ownership';
export const VOUCHER_PRESETS: { key: VoucherPresetKey; label: string; days?: true; hint: string }[] = [
  { key: 'payment_days', label: 'Zahlungsfrist', days: true,
    hint: 'Tage bis zur Fälligkeit der Rechnung – 0 heisst Vorauszahlung' },
  { key: 'lead_days', label: 'Lieferfrist', days: true,
    hint: 'Tage ab der Zusage bis zur Lieferung' },
  { key: 'valid_days', label: 'Gültig', days: true,
    hint: 'Wie viele Tage die Offerte gilt (1 bis 365)' },
  { key: 'incoterm', label: 'Lieferbedingung',
    hint: 'Incoterms 2020 – wer Kosten und Risiko trägt; den Ort nennt der Beleg' },
  { key: 'ownership', label: 'Eigentum',
    hint: 'Wem die Stücke gehören, wenn sie das Modul passieren' },
];

/** **Leer heisst «wählt der Mensch am Beleg»** – kurz im leeren Feld, ausgeschrieben im Hover. */
export const VOUCHER_PRESET_OPEN = 'am Beleg';
export const VOUCHER_PRESETS_HINT = 'Was hier steht, gilt für jeden Auftrag aus diesem Prozess '
  + 'und steht im Beleg fest. Leer heisst: wählt der Mensch am Beleg.';

/** **Wem die Stücke danach gehören** – Spiegel von `domain/voucher.OWNERSHIP`. */
export const VOUCHER_OWNERSHIP: { value: string; label: string }[] = [
  { value: 'party', label: 'geht an die Partei' },
  { value: 'us', label: 'geht an uns' },
];

/**
 * **Die elf Klauseln der Incoterms 2020** – Kürzel und Name, Spiegel von
 * `domain/incoterms.INCOTERMS` (die Erklärung je Klausel reist mit dem Beleg).
 */
export const INCOTERMS: { key: string; label: string }[] = [
  { key: 'EXW', label: 'Ab Werk' },
  { key: 'FCA', label: 'Frei Frachtführer' },
  { key: 'CPT', label: 'Frachtfrei' },
  { key: 'CIP', label: 'Frachtfrei versichert' },
  { key: 'DAP', label: 'Geliefert benannter Ort' },
  { key: 'DPU', label: 'Geliefert entladen' },
  { key: 'DDP', label: 'Geliefert verzollt' },
  { key: 'FAS', label: 'Frei Längsseite Schiff' },
  { key: 'FOB', label: 'Frei an Bord' },
  { key: 'CFR', label: 'Kosten und Fracht' },
  { key: 'CIF', label: 'Kosten, Versicherung, Fracht' },
];

/** Die Richtung zu einem Schlüssel. Unbekannt → Ausgabe, wie im Backend (`voucher.of`). */
export function voucherDirection(direction: string | undefined | null) {
  return VOUCHER_DIRECTION[direction ?? ''] ?? VOUCHER_DIRECTION.out;
}

/**
 * **Die Stufen eines Geldvorgangs — als Schlüssel, nicht als Wort.**
 *
 * Wie sie *heissen*, sagt der Server (`VoucherEmbed.stages[].label`) – das hängt an der
 * Richtung. Was die Oberfläche braucht, ist die **Identität**: an welcher Stufe die
 * Zusage steht und an welcher die Rechnung. `test_frontend_mirrors` hält sie mit
 * `domain/voucher.STAGES` deckungsgleich; deutsche Wörter im Rumpf wären an einem Vorgang
 * der anderen Richtung still falsch.
 */
export const VOUCHER_STAGE = {
  offer: 'offer',
  agreed: 'agreed',
  /** **Die Rechnung steht** – Nummer, Betrag, Steuer und Fälligkeit sind eingefroren. */
  billed: 'billed',
  /** **Ausgänge, keine Stufen** – man kommt dort an, statt hindurchzugehen. */
  done: 'done',
  cancelled: 'cancelled',
} as const;

/**
 * **Die Zustände einer Angebotszeile.** `gewaehlt` entsteht dadurch, dass bei dieser Zeile
 * zugesagt wurde. Gespiegelt von `domain/voucher.QUOTE_STATES`.
 */
export const QUOTE_STATE = {
  asked: 'angefragt',
  quoted: 'offeriert',
  declined: 'abgelehnt',
  chosen: 'gewaehlt',
} as const;

/**
 * **Die Farbfamilien der Module — die eine Stelle.**
 *
 * Bewusst **getrennt von der Ampel** (grün = Anfang/Ende · orange = im Prozess ·
 * rot = Problem): ein Modul ist kein Zustand und darf nicht wie einer aussehen
 * (PROCESS_CORE.md §5.3). Darum kühle und warme Neutraltöne statt Signalfarben.
 *
 * Kein Farbwert steht in einer Komponente – wer eine Modulfarbe braucht, fragt hier.
 */
export const MODULE_TONE: Record<string, { bg: string; fg: string; border: string }> = {
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
 * **Das Symbol eines Moduls.** Unbekanntes sieht **unbekannt** aus (Fragezeichen) und
 * borgt nie das Symbol eines anderen Moduls – ein Browser-Stand, der älter ist als das
 * Backend, gäbe ein neues Modul sonst als ein bekanntes aus.
 */
export function moduleIcon(type: string | undefined | null): LucideIcon {
  return MODULE_ICON[type ?? ''] ?? CircleHelp;
}

/**
 * **Die Farbe eines Moduls.** Die Familie reist mit dem Schritt (`ModuleFacts.tone`);
 * eine unbekannte – ein neueres Backend – ist ein Fehler und sieht auch so aus, statt die
 * Farbe eines echten anderen Moduls zu tragen.
 */
export function moduleTone(tone: string | undefined | null): { bg: string; fg: string; border: string } {
  return MODULE_TONE[tone ?? ''] ?? UNKNOWN_TONE;
}

/** Sichtbar kaputt: keine Modulfarbe, sondern die Warnfarbe des Hauses. */
const UNKNOWN_TONE = { bg: 'var(--danger-bg)', fg: 'var(--danger)', border: 'var(--danger)' };

/**
 * **Der Schlüssel des Bewegen-Moduls** – gebraucht an genau einer Stelle: ein «Holen
 * lassen» **baut** ein Bewegen-Modul, es fragt nicht danach.
 */
export const MOVE_MODULE = 'bewegen';

/** Der Erfassungspunkt-Typ, der in der Definition einen **Sollwert** braucht (`Measure.clean`). */
export const NEEDS_TARGET = 'measure';

/**
 * **Hinter einem Ausgang kann kein Modul mehr stehen** – dieselbe Regel wie serverseitig
 * (`domain/chain`), nur früher. Die Palette verschwindet hinter einem terminalen Modul;
 * übrig bleibt das **Umsortieren**: ein dahinter gezogenes Modul bleibt sichtbar (sonst
 * liesse es sich nicht löschen), aber das Bild sagt, dass so nichts läuft.
 */
export function chainProblems(steps: { label: string; terminal: boolean }[]): string[] {
  const exit = steps.findIndex((s) => s.terminal);
  if (exit < 0 || exit === steps.length - 1) return [];
  return [`Hinter «${steps[exit].label}» kann kein Modul mehr stehen: was hier ankommt, `
    + `verlässt den Auftrag – Schritt ${exit + 2} bekäme nie ein Stück.`];
}

/**
 * **Die Stichprobe ist EINE Zahl: der Anteil an allem, was am Modul wartet**
 * (`domain/sampling.py`). Die Kurzwege sind Werte derselben Zahl (alle = 100 %, Hälfte =
 * 50 %, Viertel = 25 %), keine eigenen Modi. `value` ist ein **String** (ein halb
 * getipptes Feld hat keine Zahl); geprüft wird serverseitig.
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

/**
 * Entwurfsform → das eine Feld, das der Server kennt. Ein frei getippter Anteil geht
 * **unverändert** hinaus, auch halb getippt: ihn hier in etwas umzudeuten wäre eine
 * stille Änderung der Konfiguration – der Server sagt stattdessen, dass die Zahl fehlt.
 */
export function samplePayload(s: SampleDraft): { percent: string | number } {
  const preset = SAMPLE_PRESETS.find((p) => p.value === s.mode)?.percent;
  return { percent: preset ?? s.value };
}

/**
 * Ein Erfassungspunkt im Entwurf. `key` fehlt: er wird serverseitig aus der Bezeichnung
 * abgeleitet — ihn hier zu vergeben hiesse, zwei Stellen für dieselbe Regel zu haben.
 *
 * Ein `required` gibt es **nicht**: alles, was angelegt ist, ist Pflicht.
 */
export interface PointDraft {
  label: string;
  type: string;
  target?: string;
  tolerance?: string;
  /**
   * **Worin gemessen wird** – nur beim Soll-Ist-Vergleich (mm · kg · °C …). Ein freies
   * Wort, bewusst keine Liste: das System rechnet nie mit der Einheit, es zeigt sie an.
   */
  unit?: string;
}

/**
 * Ein Modul im Entwurf — dieselbe Form am Artikel wie im Auftrag. **Kein Name**: wie ein
 * Modul heisst, sagt sein Typ (#682). `id` ist eine lokale Nummer; die Identität vergibt
 * der Server beim Anlegen.
 */
export interface ModuleDraft {
  id: number;
  moduleType: string;
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
   * Nur «Verbrauch»: die **Stückliste** – je Zeile Artikel und Menge **pro Einzelinstanz**.
   * Artikel, nicht Definitionszeilen: dasselbe Modul steht auch in der Artikel-Vorlage,
   * und dort gibt es noch keine Zeilen. Dieselbe Zeile wie im Bedarf (`DefinitionLine`),
   * ohne Herkunft und ohne konkrete Stücke – die wählt der Lagerist beim Ausführen.
   */
  lines: DefinitionLine[];
  /**
   * Nur «Bewegen»: **wohin** die Stücke gebracht werden – die Objektnummer eines Halters.
   * **Optional**: leer heisst «wird beim Ausführen gewählt». Ein String (Eingabefeld).
   */
  target: string;
  /**
   * Nur «Zahlung»: **kommt Geld herein oder geht es hinaus?** (`in` ↔ `out`). Daraus folgt
   * jedes Wort des Moduls; es ist seine Einstellung, kein zweiter Modul-Schlüssel.
   */
  direction: string;
  /**
   * Nur «Zahlung»: die **zugelassenen Gegenparteien** – je Zeile Nummer und Bestellangabe
   * (nur, wo wir bestellen: `VOUCHER_DIRECTION[…].partyRef`). **Leer heisst frei**: dann
   * wird beim Ausführen gesucht.
   */
  parties: { party: number; ref: string }[];
  /** Nur «Zahlung»: **was ist zu tun?** – ein Satz am Modul, freiwillig. */
  instruction: string;
  /**
   * Nur «Zahlung»: die **Vorgaben an den Beleg** (`VOUCHER_PRESETS`) – je Schlüssel ein
   * String (ein halb getipptes Feld hat keine Zahl). Leer heisst «wählt der Mensch am Beleg».
   */
  presets: Record<VoucherPresetKey, string>;
}

/**
 * **Die Ausprägungen des Aussonderns.** Zwei Fälle, ein Modul – sie tun dasselbe, nur
 * der Zielzustand unterscheidet sie. Welcher das ist, sagt das Backend
 * (`Aussondern.MODES`); hier stehen nur Wort und Erklärung.
 */
export type DisposalMode = 'scrap' | 'block';

export const DISPOSAL_MODES: { value: DisposalMode; label: string; hint: string }[] = [
  { value: 'scrap', label: 'Verschrotten', hint: 'Physisch entsorgt – endgültig, kein Weg zurück' },
  { value: 'block', label: 'Sperren', hint: 'Bleibt vorhanden, ist aber nicht mehr einplanbar' },
];

/**
 * **Die Definition eines Geld-Moduls — Richtung, zugelassene Partner, Auftrag.** Kein
 * Steuersatz (er hängt an der Sache, #851) und keine Vorauszahlungs-Sperre (sie folgt aus
 * der Zahlungsfrist, #854) – beides steht erst fest, wenn ein Auftrag läuft.
 */
const MONEY_FORM = {
  draft: (c: Record<string, unknown>) => ({
    // Tolerant gelesen: eine fehlende Richtung ist eine **Ausgabe**, wie im Backend. (Die
    // Vorgabe eines **neuen** Moduls ist die Einnahme, #791 – eine andere Frage.)
    direction: (c.direction === 'in' ? 'in' : 'out') as 'in' | 'out',
    // Tolerant gelesen wie im Backend: die alte Form war die blosse Objektnummer, und ein
    // freigegebener Prozess ist eingefroren – sie steht in laufenden Aufträgen.
    parties: asRows(c.parties).map((r) => ({
      party: Number(r.party ?? r), ref: String(r.ref ?? ''),
    })).filter((r) => Number.isFinite(r.party)),
    instruction: String(c.instruction ?? ''),
    presets: presetsDraft(c),
  }),
  config: (m: ModuleDraft) => ({
    direction: m.direction,
    parties: m.parties.map((r) => ({ party: r.party, ref: r.ref.trim() })),
    instruction: m.instruction.trim(),
    // Leer geht als `null` hinaus («wählt der Mensch am Beleg»); eine Zahl **unverändert** –
    // ob sie gilt, sagt der Server (`Beleg._clean_presets`), nicht dieses Formular.
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
 * hier steht nur die Form der Eingabe. `test_frontend_mirrors` hält die Schlüssel deckungsgleich.
 */
export const MODULE_FORM: Record<string, {
  config: (m: ModuleDraft) => Record<string, unknown>;
  /**
   * **Die Umkehrform — gespeicherte Konfiguration → Entwurf** (#771): damit zeigt ein
   * freigegebener Prozess dieselben Felder wie ein Entwurf, nur gesperrt.
   */
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
        // Die Einheit gehört zum Sollwert – ohne ihn gäbe es nichts, worauf sie sich
        // bezieht (der Server verwirft sie bei jedem anderen Typ ohnehin).
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
    // Zwei Angaben, beide Pflicht: **was** passiert (verschrotten ↔ sperren) und
    // **warum**. Erfassungspunkte gibt es keine – was ankommt, wird ausgesondert, und
    // der Grund steht bereits hier statt bei jedem Stück noch einmal.
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

/** Eine gespeicherte Liste als Zeilen lesen – tolerant, denn sie kommt aus JSONB. */
function asRows(value: unknown): Record<string, unknown>[] {
  if (!Array.isArray(value)) return [];
  return value.map((v) => (v && typeof v === 'object' ? v as Record<string, unknown> : { party: v }));
}

/**
 * **Der gespeicherte Anteil zurück in seine Eingabeform.** Die Kurzwege sind Werte
 * derselben Zahl (`SAMPLE_PRESETS`) – trifft die Zahl einen, steht der Regler dort;
 * sonst ist es ein frei getippter Anteil.
 */
function sampleDraft(value: unknown): SampleDraft {
  const percent = Number((value as { percent?: unknown } | null)?.percent ?? NaN);
  if (!Number.isFinite(percent)) return { ...SAMPLE_ALL };
  const preset = SAMPLE_PRESETS.find((p) => p.percent === percent);
  return preset ? { mode: preset.value, value: '' } : { mode: 'free', value: String(percent) };
}

/**
 * **Ein gespeichertes Modul als Entwurf** (#771). Ein Typ, den diese Oberfläche nicht
 * kennt, liefert den leeren Entwurf – die Karte sagt dann, dass sie ihn nicht kennt.
 */
export function moduleFromConfig(id: number, moduleType: string,
                                 config: Record<string, unknown> | null | undefined): ModuleDraft {
  return { ...blankModule(id, moduleType),
           ...(MODULE_FORM[moduleType]?.draft(config ?? {}) ?? {}) };
}

/** Ein frischer Entwurf dieses Modultyps – mit den Vorgaben, die das Backend kennt. */
export function blankModule(id: number, moduleType: string): ModuleDraft {
  return {
    id, moduleType, points: [], sample: { ...SAMPLE_ALL }, mode: 'scrap', reason: '',
    lines: [], target: '',
    // **Die Vorgabe ist die EINNAHME** (#791). Die Richtung bleibt eine ausdrückliche
    // Angabe – der Server verlangt sie (`Beleg.clean_config`).
    direction: 'in', parties: [], instruction: '', presets: blankPresets(),
  };
}

/** Entwurfsform → API-Form (`schemas/process.ModuleInput`). */
export function toModulePayload(m: ModuleDraft) {
  return { module_type: m.moduleType, config: MODULE_FORM[m.moduleType]?.config(m) ?? {} };
}
