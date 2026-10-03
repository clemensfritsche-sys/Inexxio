/**
 * /llms.txt und /llms-full.txt – generiert aus der Konfiguration und den Seitentexten.
 *
 * llms.txt folgt dem Vorschlag llmstxt.org: Titel, Kurzbeschreibung als Zitat, Fakten,
 * dann Abschnitte mit Links. llms-full.txt bringt dieselben Seiten im Wortlaut – dieselben
 * Texte, die auf der Website stehen, nur ohne Gestaltung.
 *
 * Werte werden eingesetzt, Markierungen fallen weg (wie bei Meta-Tags und JSON-LD); im
 * Modus «live» gibt es keine mehr – der Build bricht vorher ab.
 */
import { site, contactEmail } from '../config/site.mjs';
import { MARKER_RE, plain, resolve } from './text.mjs';
import { pages, type PageEntry, type Section } from './pages';
import { article } from './ratgeber';
import { glanceRows } from '../content/types';

const raw = import.meta.glob<string>('../content/ratgeber/*.md', { query: '?raw', import: 'default', eager: true });

/** Text mit Zeilenumbrüchen: Werte eingesetzt, Markierungen weg, Links absolut. */
function md(text: string, base: string): string {
  return resolve(text)
    .replace(MARKER_RE, '')
    .replace(/\[([^\]]+)\]\((\/[^)\s]*)\)/g, (_, label: string, href: string) => `[${label}](${base}${href})`)
    .replace(/[ \t]{2,}/g, ' ')
    .replace(/[ \t]+([.,;:])/g, '$1')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
}

const url = (base: string, path: string) => (path === '/' ? `${base}/` : `${base}${path}`);

function facts(base: string): string[] {
  const a = site.address;
  const o = site.people.owner;
  const lines = [
    `- Früher: ${site.brand.alternateNames.join(' · ')}`,
    `- Gegründet ${site.history.founded} von ${site.people.founder.name} in Tuttwil-Wängi TG; heute geführt von ${o.name} (${o.role}).`,
    `- Telefon: ${site.phone.display} (${site.phone.intl})`,
    ...(site.features.pikett ? [`- Pikett: ${site.pikett.display} (${site.pikett.intl})`] : []),
    `- E-Mail: ${contactEmail()}`,
    `- Adresse: ${a.street}, ${a.zip} ${a.city} (${a.municipality} ${a.canton}), ${a.countryName}`,
    `- Öffnungszeiten: ${plain(site.hours.text)}`,
    `- Einsatzgebiet: ${plain(site.area.summary)}. ${plain(site.area.abroad)}`,
    `- Anfrage: ${url(base, site.cta.href)}`,
  ];
  return lines.map((l) => plain(l));
}

function header(base: string): string[] {
  return [
    `# ${plain(site.brand.full)}`,
    '',
    `> ${plain(site.brand.full)}, ${site.brand.descriptor}: ${plain(site.brand.summary)}`,
    '',
    plain(site.brand.notToConfuse),
    '',
    ...facts(base),
  ];
}

const SECTIONS: Section[] = ['Leistungen', 'Unternehmen', 'Ratgeber'];

/** /llms.txt – wer wir sind und die wichtigsten Seiten mit Links. */
export function llmsTxt(base: string): string {
  const all = pages();
  const link = (p: PageEntry) => `- [${plain(p.name)}](${url(base, p.path)}): ${plain(p.description)}`;
  const out = [...header(base), ''];
  for (const section of SECTIONS) {
    out.push(`## ${section}`, '', ...all.filter((p) => p.section === section).map(link), '');
  }
  out.push(
    '## Optional',
    '',
    `- [Alle Seiten im Wortlaut](${url(base, '/llms-full.txt')}): Leistungen, häufige Fragen und Ratgeber-Artikel als Text.`,
    ...all.filter((p) => p.section === 'Start' || p.section === 'Rechtliches').map(link),
    '',
  );
  return out.join('\n');
}

function pageText(p: PageEntry, base: string): string[] {
  const out = [`## ${plain(p.name)}`, '', `URL: ${url(base, p.path)}`, `Stand: ${p.updated}`, ''];
  if (p.article) return [...out, ...articleText(p.article, base)];
  out.push(p.summary ? md(p.summary, base) : plain(p.description), '');
  const s = p.service;
  if (s) {
    out.push('### Auf einen Blick', '', ...glanceRows(s.glance).map((r) => `- ${r.label}: ${md(r.text, base)}`), '');
    out.push(`### ${plain(s.scope.title)}`, '', ...s.scope.items.map((i) => `- **${plain(i.title)}**: ${md(i.text, base)}`), '');
    out.push('### So läuft es ab', '', ...s.steps.map((st, i) => `${i + 1}. **${plain(st.title)}**: ${md(st.text, base)}`), '');
  }
  if (p.faq?.length) {
    out.push('### Häufige Fragen', '');
    for (const f of p.faq) out.push(`**${plain(f.q)}**`, md(f.a, base), '');
  }
  return out;
}

function articleText(slug: string, base: string): string[] {
  const a = article(slug);
  const source = raw[`../content/ratgeber/${slug}.md`];
  if (source === undefined) throw new Error(`Ratgeber «${slug}»: Quelltext nicht gefunden.`);
  // Ohne Kopfangaben; Überschriften eine Stufe tiefer – der Artikel ist hier ein Abschnitt (##).
  const body = source.replace(/^---\n[\s\S]*?\n---\n/, '').replace(/^(#{2,5}) /gm, '#$1 ');
  return [
    `Autor: ${site.people.owner.name}, ${plain(site.brand.full)} · veröffentlicht ${a.published} · aktualisiert ${a.updated}`,
    '',
    '### Kurz gesagt',
    '',
    ...a.kurz.map((k) => `- ${md(k, base)}`),
    '',
    md(body, base),
    '',
    '### Quellen',
    '',
    ...a.sources.map((s) => `- [${s.label}](${s.href})`),
    '',
  ];
}

/** /llms-full.txt – dieselben Seiten im Wortlaut. */
export function llmsFullTxt(base: string): string {
  const out = [...header(base), ''];
  for (const p of pages()) out.push('---', '', ...pageText(p, base));
  return `${out.join('\n').replace(/\n{3,}/g, '\n\n').trim()}\n`;
}
