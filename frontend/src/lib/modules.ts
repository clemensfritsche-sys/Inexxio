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
  Blocks, Camera, ClipboardCheck, PackageX, PenLine, Ruler, ScanLine, ThumbsUp, Type,
  type LucideIcon,
} from 'lucide-react';

/** Erfassungspunkt-Typen (`domain/capture_types/`). */
export const CAPTURE_ICON: Record<string, LucideIcon> = {
  text: Type,
  bool: ThumbsUp,
  photo: Camera,
  signature: PenLine,
  measure: Ruler,
  object: ScanLine,
};

/** Prozessschrittmodule (`domain/modules.py`). */
export const MODULE_ICON: Record<string, LucideIcon> = {
  datenerfassung: ClipboardCheck,
  aussondern: PackageX,
  verbrauch: Blocks,
};

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
};

/**
 * **Eine unbekannte Farbfamilie ist ein Fehler und sieht auch so aus.**
 *
 * Hier stand ein stiller Rückfall auf `slate` – und `slate` ist die Farbe der
 * Datenerfassung. Wo die Farbe nicht ankam (im freigegebenen Auftrag: sie wurde aus dem
 * Modul-Katalog geholt, und den lädt nur der Editor), trug **jedes** Modul plötzlich die
 * Farbe eines echten anderen Moduls. Der Fehler war damit nicht zu sehen, sondern zu
 * verwechseln – die schlimmste Form.
 *
 * Die Ursache ist strukturell behoben: die Farbe reist als Feld mit dem Schritt
 * (`ModuleFacts.tone`), ein Aufrufer kann sie nicht mehr vergessen. Bleibt der Fall, dass
 * ein **neueres Backend** eine Familie nennt, die diese Oberfläche nicht kennt – und der
 * gehört gemeldet, nicht überspielt.
 */
export function moduleTone(tone: string | undefined | null): { bg: string; fg: string; border: string } {
  return MODULE_TONE[tone ?? ''] ?? UNKNOWN_TONE;
}

/** Sichtbar kaputt: keine Modulfarbe, sondern die Warnfarbe des Hauses. */
const UNKNOWN_TONE = { bg: 'var(--danger-bg)', fg: 'var(--danger)', border: 'var(--danger)' };

/** Typen, die in der Definition einen **Sollwert** brauchen (`Measure.clean`). */
export const NEEDS_TARGET = 'measure';

/**
 * **Hinter einem Ausgang kann kein Modul mehr stehen.**
 *
 * Dieselbe Regel wie serverseitig (`domain/chain.assert_closes`), nur früher: dort weist
 * sie die Freigabe ab, hier sagt sie es, während man modelliert. Sie steht **hier** und
 * nicht im Diagramm, weil sie eine Aussage über Modultypen ist – das Bild rendert nur,
 * was es bekommt.
 *
 * Der Normalfall braucht sie gar nicht: die Palette verschwindet hinter einem terminalen
 * Modul, es lässt sich also keines dahinter setzen. Übrig bleibt das **Umsortieren** –
 * ein Modul, das hinter den Ausgang gezogen wurde. Es bleibt sichtbar (sonst liesse es
 * sich nicht mehr löschen), aber das Bild sagt, dass so nichts läuft.
 */
export function chainProblems(steps: { label: string; terminal: boolean }[]): string[] {
  const exit = steps.findIndex((s) => s.terminal);
  if (exit < 0 || exit === steps.length - 1) return [];
  return [`Hinter «${steps[exit].label}» kann kein Modul mehr stehen: was hier ankommt, `
    + `verlässt den Auftrag – Schritt ${exit + 2} bekäme nie ein Stück.`];
}

/**
 * **Die Stichprobe ist EINE Zahl: der Anteil an allem, was am Modul wartet.**
 *
 * Nicht je Instanz – ein Modul sieht die Summe der Einzelinstanzen vor sich, und «10 %
 * von drei Chargen» hiesse sonst dreimal eine eigene Ziehung, deren keine mit der Zahl
 * auf dem Bildschirm übereinstimmt (`domain/sampling.py`).
 *
 * Die Kurzwege sind darum **keine eigenen Modi**, sondern Werte derselben Zahl: alle =
 * 100 %, Hälfte = 50 %, Viertel = 25 %. Frei getippt wird nur, wer etwas anderes will.
 *
 * `value` ist bewusst ein **String**: es ist ein Eingabefeld, und ein halb getipptes Feld
 * hat keine Zahl. Geprüft wird sie serverseitig (`sampling.clean`), die Antwort kommt als
 * Satz durch `validate` zurück – hier steht keine zweite Regel.
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
export const SAMPLE_ALL: SampleDraft = { mode: 'all', value: '' };

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
   * **Worin gemessen wird** – nur beim Soll-Ist-Vergleich (mm · kg · °C …).
   *
   * Ein freies, kurzes Wort. Bewusst **keine Liste**: die Mengeneinheiten des Artikels
   * (`Stk · mm · m2 · m3 · kg · l`) beantworten eine andere Frage – worin die **Menge**
   * geführt wird – und kennen weder °C noch bar noch Nm; sie hier wiederzuverwenden
   * hiesse, genau die Einheit nicht anbieten zu können, die der Anlass war. Eine zweite
   * Liste wäre endlos, und das System rechnet nie mit der Einheit: es zeigt sie an.
   */
  unit?: string;
}

/**
 * Ein Modul im Entwurf — dieselbe Form am Artikel wie im Auftrag.
 *
 * **Keinen Namen** (Testnotiz #682): wie ein Modul heisst, sagt sein Typ. Ein Feld
 * daneben hatte genau eine richtige Antwort und war trotzdem Pflicht – und war damit
 * die Quelle der Meldung «String should have at least 1 character» (#686).
 *
 * Die **Identität** vergibt der Server beim Anlegen (#687); `id` hier ist nur eine
 * lokale Nummer, denn den Datensatz gibt es noch nicht.
 */
export interface ModuleDraft {
  id: number;
  moduleType: string;
  points: PointDraft[];
  /** **Wie viele der wartenden Stücke erfasst werden** – je Instanz. Pflichtfeld der
   *  Entwurfsform, damit jede Anlagestelle sie aussprechen muss; ihr Vorgabewert ist
   *  `SAMPLE_ALL`, nicht ein stillschweigend fehlendes Feld. */
  sample: SampleDraft;
  /** Nur «Aussondern»: verschrotten (endgültig) oder sperren (aufhebbar). */
  mode: DisposalMode;
  /**
   * Nur «Aussondern»: **warum** hier ausgesondert wird. Pflicht – aber beim
   * **Modellieren**, nicht am Band: der Anlass gehört zum Ablauf und lautet bei jedem
   * Stück gleich. Ohne ihn ist das Modul nicht anlegbar (`Aussondern.clean_config`).
   */
  reason: string;
  /**
   * Nur «Verbrauch»: die **Objektnummern der Artikel**, deren Stücke hier verbaut werden.
   *
   * Artikel und nicht Definitionszeilen – dasselbe Modul wird auch in der
   * **Artikel-Vorlage** definiert (der Erzeugungsprozess IST der Montageplan), und dort
   * gibt es noch gar keine Zeilen. Eine Vorlage kann «Rahmen, Motor» meinen, aber nicht
   * «Zeile 2».
   */
  articles: number[];
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
 * **Was ein Modultyp im Entwurf ausmacht — je Typ ein Eintrag, nicht je Stelle ein `if`.**
 *
 * Zwei Fragen hängen am Typ und sonst an nichts: *was schickt er als Konfiguration* und
 * *wann ist er vollständig*. Beide stehen hier zusammen; verteilt über `toModulePayload`
 * und `moduleIncomplete` wären es zwei Ketten, die beim dritten Modultyp auseinanderlaufen.
 *
 * Es ist bewusst **kein** Spiegel des Backends: die Regel gilt dort (`Module.clean_config`),
 * hier steht nur die Form der Eingabe. `test_frontend_mirrors` hält die Schlüssel deckungsgleich.
 */
export const MODULE_FORM: Record<string, {
  config: (m: ModuleDraft) => Record<string, unknown>;
  incomplete: (m: ModuleDraft) => string | null;
}> = {
  datenerfassung: {
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
    incomplete: (m) => {
      if (m.points.length === 0) return 'kein Erfassungspunkt';
      if (m.points.some((p) => !p.label.trim())) return 'Erfassungspunkt ohne Bezeichnung';
      if (m.points.some((p) => p.type === NEEDS_TARGET && !String(p.target ?? '').trim())) {
        return 'Soll-Ist-Vergleich ohne Sollwert';
      }
      if (m.sample.mode === 'free' && !m.sample.value.trim()) return 'Stichprobe ohne Zahl';
      return null;
    },
  },
  aussondern: {
    // Zwei Angaben, beide Pflicht: **was** passiert (verschrotten ↔ sperren) und
    // **warum**. Erfassungspunkte gibt es keine – was ankommt, wird ausgesondert, und
    // der Grund steht bereits hier statt bei jedem Stück noch einmal.
    config: (m) => ({ mode: m.mode, reason: m.reason }),
    incomplete: (m) => (m.reason.trim() ? null : 'Grund fehlt'),
  },
  verbrauch: {
    // Eine Angabe, und sie ist Pflicht: **welche Artikel** werden hier verbaut. Ohne sie
    // wäre das Modul ein Durchgang, der aussieht wie eine Montage.
    config: (m) => ({ articles: m.articles }),
    incomplete: (m) => (m.articles.length ? null : 'kein Artikel gewählt'),
  },
};

/** Ein frischer Entwurf dieses Modultyps – mit den Vorgaben, die das Backend kennt. */
export function blankModule(id: number, moduleType: string): ModuleDraft {
  return {
    id, moduleType, points: [], sample: { ...SAMPLE_ALL }, mode: 'scrap', reason: '',
    articles: [],
  };
}

/** Entwurfsform → API-Form (`schemas/process.ModuleInput`). */
export function toModulePayload(m: ModuleDraft) {
  return { module_type: m.moduleType, config: MODULE_FORM[m.moduleType]?.config(m) ?? {} };
}

/**
 * Ist dieses Modul vollständig? **Erst dann ist es angelegt** – vorher steht es zwar im
 * Fluss, aber die Freigabe verlangt es vollständig (der Server prüft dasselbe).
 *
 * Einen Typ, den diese Oberfläche nicht kennt, meldet sie – statt ihn durchzulassen: er
 * käme aus einem neueren Backend, und was er braucht, weiss sie nicht.
 */
export function moduleIncomplete(m: ModuleDraft): string | null {
  const form = MODULE_FORM[m.moduleType];
  return form ? form.incomplete(m) : `Modultyp «${m.moduleType}» ist hier unbekannt`;
}
