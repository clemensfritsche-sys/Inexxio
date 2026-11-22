import { Users, Package, ClipboardList, Boxes, Building2, FileText } from 'lucide-react';
import type { ElementType } from 'react';
import type { ErpRecordType } from '@/types';

/**
 * EINE Quelle der Wahrheit für die visuelle Identität jedes ERP-Datensatztyps: Symbol und
 * **Art-Farbe** (Tokens `--type-*` im Design System, `colors_and_type.css`). Die Farbe steht im
 * Symbol, in der Überschrift des Kopfs und als heller Ton der gewählten Zeile im Feed – so gehören
 * Zeile und Datensatz sichtbar zusammen. Rot bleibt für «zu tun».
 */
interface TypeMeta {
  label: string;
  icon: ElementType;
  /** Heller Ton: Füllung des Symbols, gewählte Zeile im Feed, aktiver Filter. */
  bg: string;
  /** Die Farbe: Symbol, Überschrift im Kopf. */
  fg: string;
}

export const TYPE_META: Record<ErpRecordType, TypeMeta> = {
  user:             { label: 'Benutzer',    icon: Users,         bg: 'var(--type-user-bg)',     fg: 'var(--type-user)' },
  article:          { label: 'Artikel',     icon: Package,       bg: 'var(--type-article-bg)',  fg: 'var(--type-article)' },
  order:            { label: 'Auftrag',     icon: ClipboardList, bg: 'var(--type-order-bg)',    fg: 'var(--type-order)' },
  // **Singular, wie jeder andere Typ.** Das Wort steht im Detail-Kopf über EINEM
  // Datensatz («INSTANZEN · Schraube M4» las sich, als wären es mehrere) und im Feed
  // neben seiner Anzahl – beides will die Einzahl.
  instance:         { label: 'Instanz',     icon: Boxes,         bg: 'var(--type-instance-bg)', fg: 'var(--type-instance)' },
  organization:     { label: 'Unternehmen', icon: Building2,     bg: 'var(--type-company-bg)',  fg: 'var(--type-company)' },
  // Jede freigegebene Datei (`services/documents`).
  document:         { label: 'Dokument',    icon: FileText,      bg: 'var(--type-document-bg)', fg: 'var(--type-document)' },
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

// 'organization' sieht jedes Personal (displayCount blendet 0-Zähler aus).
export const FILTER_TYPES: ErpRecordType[] = [
  'user', 'article', 'order', 'instance', 'organization', 'document',
];
