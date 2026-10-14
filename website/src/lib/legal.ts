/**
 * Rechtliche Seiten (Impressum, Datenschutz) – Markdown in src/content/legal/. Wie beim
 * Ratgeber: Werte aus der Konfiguration eingesetzt, Markierungen sichtbar (lib/text.processHtml).
 */
import { processHtml } from './text.mjs';

interface MdModule {
  frontmatter: Record<string, unknown>;
  compiledContent: () => Promise<string>;
}

const modules = import.meta.glob<MdModule>('../content/legal/*.md', { eager: true });

export type LegalName = 'impressum' | 'datenschutz';
export interface LegalMeta { title: string; description: string; updated: string }
export interface LegalDoc extends LegalMeta { html: string }

const mod = (name: LegalName): MdModule => {
  const m = modules[`../content/legal/${name}.md`];
  if (!m) throw new Error(`Rechtstext «${name}» fehlt (src/content/legal/${name}.md).`);
  return m;
};

/** Kopfangaben ohne Text – für Sitemap und llms.txt. */
export function legalMeta(name: LegalName): LegalMeta {
  const fm = mod(name).frontmatter;
  const updatedRaw = fm.updated instanceof Date ? fm.updated.toISOString() : String(fm.updated ?? '');
  const updated = /^(\d{4}-\d{2}-\d{2})/.exec(updatedRaw)?.[1];
  if (typeof fm.title !== 'string' || typeof fm.description !== 'string' || !updated) {
    throw new Error(`Rechtstext «${name}»: title, description und updated (JJJJ-MM-TT) sind Pflicht.`);
  }
  return { title: fm.title, description: fm.description, updated };
}

export async function legalDoc(name: LegalName): Promise<LegalDoc> {
  return { ...legalMeta(name), html: processHtml(await mod(name).compiledContent()) };
}
