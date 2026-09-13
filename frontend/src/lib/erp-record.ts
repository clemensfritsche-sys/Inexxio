import { Users, Package, ClipboardList, Boxes, Building2 } from 'lucide-react';
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
  // **Singular, wie jeder andere Typ.** Das Wort steht im Detail-Kopf über EINEM
  // Datensatz («INSTANZEN · Schraube M4» las sich, als wären es mehrere) und im Feed
  // neben seiner Anzahl – beides will die Einzahl.
  instance:         { label: 'Instanz',     icon: Boxes,         bg: '#E9EDEC', fg: '#5E6B66' },
  organization:     { label: 'Unternehmen', icon: Building2,     bg: '#F3E5DD', fg: '#A65A3C' },
};

/**
 * **Ein Scan sucht einen Datensatz – also trägt er dessen Symbol** (#754).
 *
 * `ScanKind` ist die Sicht des Scanners auf einen Typ, `ErpRecordType` die des ERP; wo
 * beide dasselbe meinen, steht es hier – an EINER Stelle, neben der Zuordnung selbst.
 * `process`/`object` bleiben ohne Eintrag: sie sind kein Datensatztyp, und ein
 * ausgeliehenes Symbol wäre eine Behauptung (dieselbe Lehre wie `moduleIcon`, wo ein
 * Rückfall drei fremde Module vortäuschte).
 */
export const SCAN_RECORD_TYPE: Record<string, ErpRecordType> = {
  user: 'user',
  instance: 'instance',
  article: 'article',
  company: 'organization',
};

// 'organization' erscheint nur für Admins als Chip (displayCount blendet 0-Zähler aus).
export const FILTER_TYPES: ErpRecordType[] = [
  'user', 'article', 'order', 'instance', 'organization',
];
