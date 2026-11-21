/**
 * Typen der Content-Dateien. Seitentexte stehen in src/content/*.ts (strukturiert) bzw.
 * src/content/**\/*.md (lange Texte) – getrennt von den Layout-Komponenten. Werte aus der
 * Konfiguration werden mit {{schlüssel}} eingesetzt.
 */
import type { IconName } from '../components/Icon.astro';
import { t } from '../i18n/t.mjs';
export type AreaId = 'krantechnik' | 'fahrzeugtechnik' | 'spezialloesungen';
/** OG-Bild: Standard oder das des Bereichs (public/og/, scripts/make-assets.mjs). */
export type OgImage = 'default' | AreaId;
export interface Faq { q: string; a: string }
export interface LinkItem { href: string; label: string; text?: string; kind?: 'leistung' | 'ratgeber' }
export interface Action { label: string; href: string }
export interface Step { title: string; text: string }
/**
 * Eine Station auf dem Weg (components/spezial/SolutionPath.astro). Jede Station eines Ablaufs endet
 * gleich: `result` = was der Kunde danach in der Hand hat (eine Zeile mit Haken). Keine Etiketten –
 * was dazugehört, steht im Satz. `who` nennt eine Partei (Sie · Gemeinsam · Wir), keinen Ort.
 * Eine Zeitleiste (Über uns) hat statt `result` ein `no` (das Jahr) – ein Weg hat entweder bei
 * jeder Station ein Ergebnis oder bei keiner.
 */
export interface Station { icon: IconName; who: string; title: string; text: string; result?: string; no?: string }

/** Bereichsseite (Krantechnik, Fahrzeugtechnik, Speziallösungen). */
export interface AreaPage {
  id: AreaId;
  path: string;
  title: string;
  description: string;
  hero: { eyebrow: string; h1: string; lead: string; photo: string; primary: Action };
  /** «Auf einen Blick»: 2–3 sachliche Sätze – was, für wen, wo. */
  summary: string;
  /** Der Ablauf als Schritte. */
  steps: Step[];
  faq: Faq[];
  service: { name: string; serviceType: string };
}

/** Unterseite. */
export interface SubPage {
  area: AreaId;
  path: string;
  /** Kurzname für Breadcrumbs und Karten. */
  crumb: string;
  /** Titel ohne Zusatz (der Zusatz «| INEXXIO» kommt von selbst). */
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
}

export interface Entry { title: string; text: string; href: string; icon: IconName }

/** «Auf einen Blick» – die drei Zeilen in fester Reihenfolge (Seite und llms-full.txt). */
const GLANCE = t('ui', { forWhom: 'Für wen', what: 'Was wir tun', deliverables: 'Was Sie erhalten' });
export const glanceRows = (g: SubPage['glance']): { label: string; text: string }[] => [
  { label: GLANCE.forWhom, text: g.forWhom },
  { label: GLANCE.what, text: g.what },
  { label: GLANCE.deliverables, text: g.deliverables },
];
