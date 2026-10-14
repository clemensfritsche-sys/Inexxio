import type { ArticleSerialization, ArticleUnit } from '@/types';

// Der **Status** eines Artikels steht nicht hier: er kommt aus der EINEN Statusliste
// (`lib/process-status`, Testnotiz #669). Eine eigene Karte je Achse war genau der
// Grund, warum derselbe Zustand an drei Orten drei Beschriftungen trug.

// ─── Anzeige-Konfiguration ──────────────────────────────────────────────────

export const ARTICLE_UNITS: { value: ArticleUnit; label: string }[] = [
  { value: 'Stk', label: 'Stk.' },
  { value: 'mm',  label: 'mm' },
  { value: 'm2',  label: 'm²' },
  { value: 'm3',  label: 'm³' },
  { value: 'kg',  label: 'kg' },
  { value: 'l',   label: 'l' },
];

export const SERIALIZATION_OPTIONS: { value: ArticleSerialization; label: string }[] = [
  { value: 'unit',  label: 'Einzelteil' },
  { value: 'batch', label: 'Charge' },
];

export function unitLabel(value: string): string {
  return ARTICLE_UNITS.find((u) => u.value === value)?.label ?? value;
}

export function serializationLabel(value: string): string {
  return SERIALIZATION_OPTIONS.find((s) => s.value === value)?.label ?? value;
}

// ─── Validierung (Spiegel von backend/app/schemas/article.py) ────────────────

const SIZE_RE = /^\d+(\.\d+)?(x\d+(\.\d+)?)+$/;

/** Normalisiert eine Grössenangabe: Kleinschreibung, ohne Leerzeichen, × → x. */
export function normalizeSize(raw: string): string {
  return raw.trim().toLowerCase().replace(/×/g, 'x').replace(/\s+/g, '');
}

/** Gibt eine Fehlermeldung zurück oder null, wenn die Grösse gültig ist. */
export function validateSize(raw: string): string | null {
  if (!raw.trim()) return 'Grösse ist ein Pflichtfeld';
  const s = normalizeSize(raw);
  if (!SIZE_RE.test(s)) {
    return "Format: Zahlen getrennt durch 'x', z. B. 3x40x600";
  }
  const parts = s.split('x').map(Number);
  if (parts.some((p) => !(p > 0))) return 'Alle Masse müssen grösser als 0 sein';
  for (let i = 0; i < parts.length - 1; i++) {
    if (parts[i] > parts[i + 1]) return 'Masse müssen aufsteigend sein (klein → gross)';
  }
  return null;
}

/** Normalisiert ein Gewicht: Komma → Punkt, getrimmt. */
export function normalizeWeight(raw: string): string {
  return raw.trim().replace(',', '.');
}

/** Gibt eine Fehlermeldung zurück oder null, wenn das Gewicht gültig ist. */
export function validateWeight(raw: string): string | null {
  const s = normalizeWeight(raw);
  if (s === '') return 'Gewicht ist ein Pflichtfeld';
  if (!/^\d+(\.\d+)?$/.test(s)) return 'Gewicht muss eine Zahl sein';
  if (!(Number(s) > 0)) return 'Gewicht darf nicht 0 sein';
  const decimals = s.split('.')[1];
  if (decimals && decimals.length > 3) return 'Höchstens 3 Nachkommastellen';
  return null;
}

export function validateName(raw: string): string | null {
  return raw.trim() ? null : 'Name ist ein Pflichtfeld';
}
