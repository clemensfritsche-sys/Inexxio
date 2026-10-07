/**
 * ►►► Die indexierbaren Seiten der Website – EINE Liste. ◄◄◄
 *
 * Sitemap, llms.txt und llms-full.txt lesen sie; `Base.astro` prüft beim Bauen, dass jede
 * Seite entweder hier steht oder ausdrücklich `noindex` trägt (Danke-Seite, 404). Eine neue
 * Seite, die hier fehlt, bricht damit den Build – sie kann nicht still aus der Sitemap
 * fallen.
 *
 * Titel, Beschreibung und Text kommen aus den Content-Dateien, die auch die Seite selbst
 * liest – hier wird nichts zweimal geschrieben, nur zusammengestellt.
 */
import { site } from '../config/site.mjs';
import type { AreaPage, Faq, SubPage } from '../content/types';
import { start } from '../content/start';
import { krantechnik, krantechnikPages } from '../content/krantechnik';
import { fahrzeugtechnik, fahrzeugtechnikPages } from '../content/fahrzeugtechnik';
import { sonderloesungen } from '../content/sonderloesungen';
import { service } from '../content/service';
import { handover } from '../content/uebergabe';
import { ueberUns } from '../content/ueber-uns';
import { kontakt } from '../content/kontakt';
import { karriere } from '../content/karriere';
import { ratgeberUebersicht } from '../content/ratgeber-uebersicht';
import { articles } from './ratgeber';
import { legalMeta } from './legal';

export type Section =
  | 'Start' | 'Krantechnik' | 'Fahrzeugtechnik' | 'Sonderlösungen' | 'Service' | 'Unternehmen' | 'Ratgeber' | 'Rechtliches';

export interface PageEntry {
  path: string;
  /** Name in Listen – ohne Markenzusatz. */
  name: string;
  description: string;
  /** JJJJ-MM-TT – `lastmod` der Sitemap. */
  updated: string;
  section: Section;
  /** Was llms-full.txt über die Seite schreibt (dieselben Texte, die auf ihr stehen). */
  summary?: string;
  faq?: Faq[];
  /** Bereichsseite: die drei Ebenen und der Ablauf (llms-full.txt). */
  area?: AreaPage;
  /** Unterseite: «Auf einen Blick» und Leistungsumfang (llms-full.txt). */
  subpage?: SubPage;
  /** Slug eines Ratgeber-Artikels: llms-full.txt bringt ihn im Wortlaut. */
  article?: string;
}

const day = site.seo.contentUpdated;

const areaEntry = (p: AreaPage, section: Section): PageEntry => ({
  path: p.path, name: p.title, description: p.description, updated: day, section, summary: p.summary, faq: p.faq, area: p,
});
const subEntry = (p: SubPage, section: Section): PageEntry => ({
  path: p.path, name: p.title, description: p.description, updated: day, section, summary: p.summary, faq: p.faq, subpage: p,
});

function build(): PageEntry[] {
  const list: PageEntry[] = [
    { path: '/', name: 'Startseite', description: start.description, updated: day, section: 'Start', summary: start.summary, faq: start.faq },
    areaEntry(krantechnik, 'Krantechnik'),
    ...krantechnikPages.map((p) => subEntry(p, 'Krantechnik')),
    areaEntry(fahrzeugtechnik, 'Fahrzeugtechnik'),
    ...fahrzeugtechnikPages.map((p) => subEntry(p, 'Fahrzeugtechnik')),
    subEntry(sonderloesungen, 'Sonderlösungen'),
    { path: service.path, name: service.title, description: service.description, updated: day, section: 'Service', summary: service.summary, faq: service.faq },
    { path: '/ueber-uns', name: ueberUns.title, description: ueberUns.description, updated: day, section: 'Unternehmen', summary: ueberUns.summary, faq: [...handover.faq, ...ueberUns.areaFaq] },
    { path: '/kontakt', name: kontakt.title, description: kontakt.description, updated: day, section: 'Unternehmen', summary: kontakt.summary },
    { path: '/karriere', name: karriere.title, description: karriere.description, updated: day, section: 'Unternehmen' },
    { path: '/ratgeber', name: ratgeberUebersicht.title, description: ratgeberUebersicht.description, updated: day, section: 'Ratgeber', summary: ratgeberUebersicht.summary },
    ...articles().map((a): PageEntry => ({
      path: a.path, name: a.title, description: a.description, updated: a.updated, section: 'Ratgeber', article: a.slug,
    })),
    ...(['impressum', 'datenschutz'] as const).map((name): PageEntry => {
      const m = legalMeta(name);
      return { path: `/${name}`, name: m.title, description: m.description, updated: m.updated, section: 'Rechtliches' };
    }),
  ];
  const seen = new Set<string>();
  for (const p of list) {
    if (seen.has(p.path)) throw new Error(`Seite «${p.path}» steht zweimal in src/lib/pages.ts.`);
    seen.add(p.path);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(p.updated)) throw new Error(`Seite «${p.path}»: Datum «${p.updated}» ist nicht JJJJ-MM-TT.`);
  }
  return list;
}

const PAGES = build();

/** Alle indexierbaren Seiten, in der Reihenfolge der Navigation. */
export const pages = (): PageEntry[] => PAGES;

/** Steht diese Seite in der Liste? (Pfad ohne .html und ohne Schrägstrich am Ende) */
export const isListed = (path: string): boolean => PAGES.some((p) => p.path === path);
