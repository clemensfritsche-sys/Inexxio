/**
 * Typen der Content-Dateien. Seitentexte stehen in src/content/*.ts (strukturiert) bzw.
 * src/content/**\/*.md (lange Texte) – getrennt von den Layout-Komponenten. Werte aus der
 * Konfiguration werden mit {{schlüssel}} eingesetzt, offene Punkte mit [[PLATZHALTER: …]]
 * bzw. [[PRÜFEN: …]] markiert.
 */
import type { IconName } from '../components/Icon.astro';

export type InquiryKind = 'kran' | 'fahrmischer' | 'teile' | 'abo' | 'anderes';
export interface Faq { q: string; a: string }
export interface LinkItem { href: string; label: string; text?: string; kind?: 'leistung' | 'ratgeber' }
export interface Action { label: string; href: string; track?: string }

/** Vorlage für alle Leistungsseiten (Kapitel 7.3 des Auftrags). */
export interface ServicePage {
  path: string;
  /** Kurzname für Breadcrumbs und Navigation. */
  crumb: string;
  /** Titel ohne Zusatz (der Zusatz «| INEXXIO (ehemals HS Steiner)» kommt von selbst). */
  title: string;
  description: string;
  og: 'default' | 'krane' | 'fahrmischer';
  parent?: { name: string; path: string };
  hero: { eyebrow: string; h1: string; lead: string; photo: string; primary: Action; note?: string };
  /** 2–3 sachliche Sätze: wer, was, wo – zitierfähig für Suchmaschinen und KI. */
  summary: string;
  glance: { forWhom: string; what: string; speed: string; deliverables: string };
  scope: { title: string; lead?: string; items: { title: string; text: string }[] };
  steps: { title: string; text: string }[];
  faq: Faq[];
  cta: { title: string; lead?: string; kind: InquiryKind; need?: string; urgency?: 'dringend' | 'wochen' | 'planung'; messageLabel?: string; pikettFirst?: boolean };
  related: LinkItem[];
  service: { name: string; serviceType: string };
  keywords?: string[];
}

export interface Entry { title: string; text: string; href: string; icon: IconName }

/** «Auf einen Blick» – die vier Zeilen in fester Reihenfolge (Seite und llms-full.txt). */
export const glanceRows = (g: ServicePage['glance']): { label: string; text: string }[] => [
  { label: 'Für wen', text: g.forWhom },
  { label: 'Was wir tun', text: g.what },
  { label: 'Wie schnell', text: g.speed },
  { label: 'Was Sie erhalten', text: g.deliverables },
];
