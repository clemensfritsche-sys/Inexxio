/**
 * Prozessschrittmodule und Erfassungspunkt-Typen — **Symbole**, sonst nichts.
 *
 * Die Listen selbst stehen im Backend (`domain/modules.py`, `domain/capture_types/`) und
 * kommen über `GET /erp/orders/module-catalog`. Hier liegt nur, was eine Antwort nicht
 * transportieren kann: das Icon. Eine zweite Aufzählung mit Beschriftungen liefe beim
 * ersten neuen Typ auseinander — und der Fehler zeigte sich erst, wenn jemand ihn wählt.
 *
 * `backend/tests/test_frontend_mirrors.py` prüft, dass diese Zuordnungen **genau** die
 * Schlüssel des Backends abdecken: ein Typ ohne Symbol wäre eine leere Fläche, ein Symbol
 * ohne Typ eine tote Zeile.
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

/** Typen, die in der Definition einen **Sollwert** brauchen (`Measure.clean`). */
export const NEEDS_TARGET = 'measure';

/**
 * Ein Erfassungspunkt im Entwurf. `key` fehlt: er wird serverseitig aus der Bezeichnung
 * abgeleitet — ihn hier zu vergeben hiesse, zwei Stellen für dieselbe Regel zu haben.
 */
export interface PointDraft {
  label: string;
  type: string;
  required: boolean;
  target?: string;
  tolerance?: string;
}

/** Ein Modul im Entwurf — dieselbe Form am Artikel wie im Auftrag. */
export interface ModuleDraft {
  /** Lokale Nummer; der Datensatz existiert ja noch nicht. */
  id: number;
  moduleType: string;
  name: string;
  points: PointDraft[];
}

/** Entwurfsform → API-Form (`schemas/process.ModuleInput`). */
export function toModulePayload(m: ModuleDraft) {
  return {
    module_type: m.moduleType,
    name: m.name,
    config: {
      points: m.points.map((p) => ({
        label: p.label,
        type: p.type,
        required: p.required,
        target: p.type === NEEDS_TARGET && p.target !== '' ? Number(p.target) : null,
        tolerance: p.type === NEEDS_TARGET && p.tolerance !== '' ? Number(p.tolerance) : null,
      })),
    },
  };
}
