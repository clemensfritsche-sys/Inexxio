/**
 * Typen der Content-Dateien. Seitentexte stehen in src/content/*.ts (strukturiert) bzw.
 * src/content/**\/*.md (lange Texte) – getrennt von den Layout-Komponenten. Werte aus der
 * Konfiguration werden mit {{schlüssel}} eingesetzt, offene Punkte mit [[PLATZHALTER: …]]
 * bzw. [[PRÜFEN: …]] markiert.
 */
import type { IconName } from '../components/Icon.astro';
export type AreaId = 'krantechnik' | 'fahrzeugtechnik' | 'sonderloesungen';
/** OG-Bild: Standard oder das des Bereichs (public/og/, scripts/make-assets.mjs). */
export type OgImage = 'default' | AreaId;
export interface Faq { q: string; a: string }
export interface LinkItem { href: string; label: string; text?: string; kind?: 'leistung' | 'ratgeber' }
export interface Action { label: string; href: string; track?: string }
export interface Step { title: string; text: string }


/** Bereichsseite (Auftrag Kap. 7.4) – alle drei mit derselben Struktur. */
export interface AreaPage {
  id: AreaId;
  path: string;
  title: string;
  description: string;
  hero: { eyebrow: string; h1: string; lead: string; photo: string; primary: Action };
  /** «Auf einen Blick»: 2–3 sachliche Sätze – was, für wen, wo. */
  summary: string;
  /** Die drei Ebenen: Lösungen · Service & Reparatur · Ersatz- und Verschleissteile. */
  levels: { title: string; text: string; links: LinkItem[] }[];
  /** Ablauf in vier Schritten: Anfrage → Abklärung → Umsetzung → Bericht. */
  steps: Step[];
  faq: Faq[];
  service: { name: string; serviceType: string };
  keywords?: string[];
}

/** Unterseite (Auftrag Kap. 7.5). */
export interface SubPage {
  area: AreaId;
  path: string;
  /** Kurzname für Breadcrumbs und Karten. */
  crumb: string;
  /** Titel ohne Zusatz (der Zusatz «| INEXXIO (ehemals HS Steiner)» kommt von selbst). */
  title: string;
  description: string;
  hero: { eyebrow: string; h1: string; lead: string; photo: string; primary: Action };
  /** 2–3 sachliche Sätze: wer, was, wo – zitierfähig für Suchmaschinen und KI. */
  summary: string;
  /** «Auf einen Blick»: Für wen · Was wir tun · Was Sie erhalten. */
  glance: { forWhom: string; what: string; deliverables: string };
  scope: { title: string; lead?: string; items: { title: string; text: string }[] };
  faq: Faq[];
  /** 2–3 verwandte Leistungen, mindestens ein Ratgeber-Artikel. */
  related: LinkItem[];
  service: { name: string; serviceType: string };
  keywords?: string[];
}

export interface Entry { title: string; text: string; href: string; icon: IconName }

/** «Auf einen Blick» – die drei Zeilen in fester Reihenfolge (Seite und llms-full.txt). */
export const glanceRows = (g: SubPage['glance']): { label: string; text: string }[] => [
  { label: 'Für wen', text: g.forWhom },
  { label: 'Was wir tun', text: g.what },
  { label: 'Was Sie erhalten', text: g.deliverables },
];
