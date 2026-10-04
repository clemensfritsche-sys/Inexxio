/**
 * Ratgeber – die Artikel liegen als Markdown in src/content/ratgeber/ (ein Artikel = eine
 * Datei, der Dateiname ist die Adresse). Hier werden sie eingelesen, die Kopfangaben
 * geprüft und als fertige Daten geliefert: neueste zuerst.
 *
 * Fehlt eine Pflichtangabe oder zeigt ein Link ins Leere, bricht der Build ab – lieber
 * kein Artikel als ein halber.
 */
import { kindOf } from '../config/inquiry.mjs';
import { processHtml } from './text.mjs';
import type { LinkItem } from '../content/types';

export interface Source { label: string; href: string }
export interface Heading { depth: number; slug: string; text: string }

export interface Article {
  slug: string;
  path: string;
  title: string;
  /** Kurzer Titel für <title> (mit Zusatz höchstens 60 Zeichen). */
  seoTitle: string;
  description: string;
  /** JJJJ-MM-TT */
  published: string;
  updated: string;
  kurz: string[];
  sources: Source[];
  related: LinkItem[];
  /** Vorgewähltes Anliegen im Kontaktbereich am Ende des Artikels. */
  cta: { need?: string };
  html: string;
  headings: Heading[];
}

interface MdModule {
  frontmatter: Record<string, unknown>;
  compiledContent: () => Promise<string>;
  getHeadings: () => Heading[];
}

const modules = import.meta.glob<MdModule>('../content/ratgeber/*.md', { eager: true });

const fail = (file: string, msg: string): never => {
  throw new Error(`Ratgeber «${file}»: ${msg}`);
};

const text = (file: string, fm: Record<string, unknown>, key: string): string => {
  const v = fm[key];
  if (typeof v !== 'string' || v.trim() === '') fail(file, `«${key}» fehlt.`);
  return (v as string).trim();
};

/** YAML liest 2026-10-03 als Datum; Astro reicht es als ISO-Text weiter. */
const day = (file: string, fm: Record<string, unknown>, key: string): string => {
  const v = fm[key];
  const s = v instanceof Date ? v.toISOString() : typeof v === 'string' ? v : '';
  const m = /^(\d{4}-\d{2}-\d{2})/.exec(s);
  if (!m) fail(file, `«${key}» muss ein Datum JJJJ-MM-TT sein.`);
  return m![1];
};

const list = <T>(file: string, fm: Record<string, unknown>, key: string, check: (x: unknown) => x is T): T[] => {
  const v = fm[key];
  if (!Array.isArray(v) || v.length === 0 || !v.every(check)) fail(file, `«${key}» fehlt oder ist unvollständig.`);
  return v as T[];
};

const isText = (x: unknown): x is string => typeof x === 'string' && x.trim() !== '';
const isSource = (x: unknown): x is Source =>
  !!x && typeof x === 'object' && isText((x as Source).label) && /^https:\/\//.test(String((x as Source).href));
const isRelated = (x: unknown): x is LinkItem =>
  !!x && typeof x === 'object' && isText((x as LinkItem).label) && /^\/[a-z0-9/#-]*$/.test(String((x as LinkItem).href));

function load(): Article[] {
  const out: Article[] = [];
  for (const [path, mod] of Object.entries(modules)) {
    const file = path.split('/').pop()!;
    const slug = file.replace(/\.md$/, '');
    if (!/^[a-z0-9-]+$/.test(slug)) fail(file, 'Dateiname nur aus a–z, 0–9 und Bindestrich.');
    const fm = mod.frontmatter;
    const cta = (fm.cta ?? {}) as { need?: string };
    if (cta.need && !(cta.need in kindOf)) fail(file, `«cta.need» ist kein Anliegen des Anfrage-Formulars.`);
    const published = day(file, fm, 'published');
    const updated = day(file, fm, 'updated');
    if (updated < published) fail(file, '«updated» liegt vor «published».');
    out.push({
      slug,
      path: `/ratgeber/${slug}`,
      title: text(file, fm, 'title'),
      seoTitle: text(file, fm, 'seoTitle'),
      description: text(file, fm, 'description'),
      published,
      updated,
      kurz: list(file, fm, 'kurz', isText),
      sources: list(file, fm, 'sources', isSource),
      related: list(file, fm, 'related', isRelated),
      cta: { need: cta.need },
      html: '',
      headings: mod.getHeadings(),
    });
  }
  return out.sort((a, b) => (a.updated === b.updated ? a.title.localeCompare(b.title, 'de') : b.updated.localeCompare(a.updated)));
}

const ARTICLES = load();

/** Alle Artikel, neueste zuerst – ohne den Text (der kommt mit `withBody`). */
export const articles = (): Article[] => ARTICLES;

export function article(slug: string): Article {
  const a = ARTICLES.find((x) => x.slug === slug);
  if (!a) throw new Error(`Ratgeber-Artikel «${slug}» gibt es nicht (src/content/ratgeber/${slug}.md).`);
  return a;
}

/** Der Artikel mit fertigem HTML (Werte eingesetzt, Markierungen sichtbar). */
export async function withBody(slug: string): Promise<Article> {
  const a = article(slug);
  const mod = modules[`../content/ratgeber/${slug}.md`];
  return { ...a, html: processHtml(await mod.compiledContent()) };
}

const DATE = new Intl.DateTimeFormat('de-CH', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
/** «3. Oktober 2026» */
export const formatDay = (iso: string): string => DATE.format(new Date(`${iso}T00:00:00Z`));
