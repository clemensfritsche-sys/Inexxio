import { Users, Package, ClipboardList, Warehouse, Boxes, Building2 } from 'lucide-react';
import type { ElementType } from 'react';
import type { ErpRecordType } from '@/types';

/**
 * EINE Quelle der Wahrheit für die visuelle Identität jedes ERP-Datensatztyps:
 * Symbol + getönte Symbolfarbe (Design-System: «Symbole statt Text, Farbe =
 * Bedeutung»). Jeder Typ hat eine eigene warme Farbfamilie → sofortige optische
 * Unterscheidung im Feed, im Typ-Filter und in Detail-Köpfen.
 * Werte aus dem Inexxio-Design-Mockup (Instanz-Detail Redesign).
 */
export interface TypeMeta {
  label: string;
  icon: ElementType;
  /** getönte Füllung des Symbol-Quadrats */
  bg: string;
  /** Symbol-/Textfarbe */
  fg: string;
}

export const TYPE_META: Record<ErpRecordType, TypeMeta> = {
  user:             { label: 'Benutzer',    icon: Users,         bg: '#E8F1EC', fg: '#2E7D5B' },
  article:          { label: 'Artikel',     icon: Package,       bg: '#F4EBDD', fg: '#9A7238' },
  order:            { label: 'Auftrag',     icon: ClipboardList, bg: '#E7F0F4', fg: '#1C6487' },
  instance:         { label: 'Instanzen',   icon: Boxes,         bg: '#E9EDEC', fg: '#5E6B66' },
  storage_location: { label: 'Lagerplatz',  icon: Warehouse,     bg: '#F0E7F1', fg: '#7E5586' },
  organization:     { label: 'Unternehmen', icon: Building2,     bg: '#F3E5DD', fg: '#A65A3C' },
};

// 'organization' erscheint nur für Admins als Chip (displayCount blendet 0-Zähler aus).
export const FILTER_TYPES: ErpRecordType[] = [
  'user', 'article', 'order', 'instance', 'storage_location', 'organization',
];
