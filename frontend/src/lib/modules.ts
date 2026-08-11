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
  Camera, ClipboardCheck, PenLine, Ruler, ThumbsUp, Type, type LucideIcon,
} from 'lucide-react';

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

/** Die Farbe eines Modultyps. Unbekannt → der neutrale Grundton, nie eine leere Fläche. */
export function moduleTone(tone: string | undefined): { bg: string; fg: string; border: string } {
  return MODULE_TONE[tone ?? ''] ?? MODULE_TONE.slate;
}

/** Typen, die in der Definition einen **Sollwert** brauchen (`Measure.clean`). */
export const NEEDS_TARGET = 'measure';

/**
 * Die Stichprobenregel im Entwurf (`domain/sampling.py`) — drei Formen, eine Zahl.
 *
 * `value` ist bewusst ein **String**: es ist ein Eingabefeld, und ein halb getipptes
 * Feld hat keine Zahl. Geprüft wird sie serverseitig (`sampling.clean`), die Antwort
 * kommt als Satz durch `validate` zurück – hier steht keine zweite Regel.
 */
export interface SampleDraft {
  mode: 'all' | 'count' | 'percent';
  value: string;
}

/** Was ohne Angabe gilt – **alle**, wie im Backend (`sampling.DEFAULT`). */
export const SAMPLE_ALL: SampleDraft = { mode: 'all', value: '' };

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
}

/** Entwurfsform → API-Form (`schemas/process.ModuleInput`). */
export function toModulePayload(m: ModuleDraft) {
  return {
    module_type: m.moduleType,
    config: {
      points: m.points.map((p) => ({
        label: p.label,
        type: p.type,
        target: p.type === NEEDS_TARGET && p.target !== '' ? Number(p.target) : null,
        tolerance: p.type === NEEDS_TARGET && p.tolerance !== '' ? Number(p.tolerance) : null,
      })),
      // **Unverändert weiterreichen, auch halb getippt.** Ein leeres Feld hier in «alle»
      // umzudeuten wäre eine stille Änderung der Konfiguration – der Server sagt statt-
      // dessen, dass die Zahl fehlt, und die Freigabe verweigert bis dahin.
      sample: { mode: m.sample.mode, value: m.sample.value },
    },
  };
}

/**
 * Ist dieses Modul vollständig? **Erst dann ist es angelegt** – vorher steht es zwar im
 * Fluss, aber die Freigabe verlangt es vollständig (der Server prüft dasselbe).
 */
export function moduleIncomplete(m: ModuleDraft): string | null {
  if (m.points.length === 0) return 'kein Erfassungspunkt';
  if (m.points.some((p) => !p.label.trim())) return 'Erfassungspunkt ohne Bezeichnung';
  if (m.points.some((p) => p.type === NEEDS_TARGET && !String(p.target ?? '').trim())) {
    return 'Soll-Ist-Vergleich ohne Sollwert';
  }
  if (m.sample.mode !== 'all' && !m.sample.value.trim()) return 'Stichprobe ohne Zahl';
  return null;
}
