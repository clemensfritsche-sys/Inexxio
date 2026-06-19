// Spiegel von backend/app/services/article_fields.py – Katalog der Stammdaten,
// die einem Lieferanten freigegeben werden können. Pflichtfelder sind immer dabei.

export interface SupplierField { key: string; label: string; mandatory: boolean }

export const SUPPLIER_FIELD_CATALOG: SupplierField[] = [
  { key: 'name',                    label: 'Bezeichnung',        mandatory: true },
  { key: 'unit',                    label: 'Einheit',            mandatory: true },
  { key: 'serialization',           label: 'Serialisierung',     mandatory: true },
  { key: 'size',                    label: 'Grösse (mm)',        mandatory: true },
  { key: 'weight_kg',               label: 'Gewicht (kg)',       mandatory: true },
  { key: 'supplier_article_number', label: 'Lief.-Artikelnummer', mandatory: false },
];

export const MANDATORY_FIELD_KEYS = SUPPLIER_FIELD_CATALOG.filter((f) => f.mandatory).map((f) => f.key);

export function fieldLabel(key: string): string {
  return SUPPLIER_FIELD_CATALOG.find((f) => f.key === key)?.label ?? key;
}

export function normalizeSharedFields(values: string[] | null | undefined): string[] {
  const sel = new Set(values ?? []);
  MANDATORY_FIELD_KEYS.forEach((k) => sel.add(k));
  return SUPPLIER_FIELD_CATALOG.filter((f) => sel.has(f.key)).map((f) => f.key);
}
