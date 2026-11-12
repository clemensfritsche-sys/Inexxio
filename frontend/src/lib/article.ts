import type { ArticleSerialization, ArticleUnit } from '@/types';

// Der **Status** eines Artikels steht nicht hier: er kommt aus der EINEN Statusliste
// (`lib/process-status`, Testnotiz #669). Eine eigene Karte je Achse war genau der
// Grund, warum derselbe Zustand an drei Orten drei Beschriftungen trug.

// ─── Anzeige-Konfiguration ──────────────────────────────────────────────────

const ARTICLE_UNITS: { value: ArticleUnit; label: string }[] = [
  { value: 'Stk', label: 'Stk.' },
  { value: 'mm',  label: 'mm' },
  { value: 'm2',  label: 'm²' },
  { value: 'm3',  label: 'm³' },
  { value: 'kg',  label: 'kg' },
  { value: 'l',   label: 'l' },
];

const SERIALIZATION_OPTIONS: { value: ArticleSerialization; label: string }[] = [
  { value: 'unit',  label: 'Einzelteil' },
  { value: 'batch', label: 'Charge' },
];

export function unitLabel(value: string): string {
  return ARTICLE_UNITS.find((u) => u.value === value)?.label ?? value;
}

export function serializationLabel(value: string): string {
  return SERIALIZATION_OPTIONS.find((s) => s.value === value)?.label ?? value;
}
