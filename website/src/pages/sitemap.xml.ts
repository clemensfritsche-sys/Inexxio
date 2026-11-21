/**
 * /sitemap.xml – nur indexierbare Seiten (src/lib/pages.ts), mit lastmod.
 * Im Modus «preview» gibt es sie ebenfalls (prüfbar); robots.txt nennt sie dort nicht.
 *
 * Sprachen: jede freigegebene Sprache (src/config/languages.mjs, `live`) steht mit ihren Adressen
 * darin, jede Seite nennt ihre Fassungen in den anderen Sprachen (xhtml:link hreflang) – so, wie
 * Google es für mehrsprachige Seiten empfiehlt. Eine Sprache in Prüfung steht nicht darin.
 */
import type { APIRoute } from 'astro';
import { pages } from '../lib/pages';
import { publishedLanguages, SOURCE } from '../config/languages.mjs';
import { localPath } from '../i18n/paths.mjs';

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

export const GET: APIRoute = ({ site }) => {
  const base = site!.href.replace(/\/$/, '');
  const url = (path: string) => esc(path === '/' ? `${base}/` : `${base}${path}`);
  const langs = publishedLanguages();
  const urls = pages().flatMap((p) => {
    const versions = langs.map((l) => ({ l, path: localPath(p.path, l.code) })).filter((v) => v.path);
    const alt = versions.length > 1
      ? versions.map((v) => `\n    <xhtml:link rel="alternate" hreflang="${v.l.locale}" href="${url(v.path!)}"/>`).join('') +
        `\n    <xhtml:link rel="alternate" hreflang="x-default" href="${url(p.path)}"/>`
      : '';
    return versions.map((v) => `  <url><loc>${url(v.path!)}</loc><lastmod>${p.updated}</lastmod>${alt}${alt ? '\n  ' : ''}</url>`);
  });
  const ns = langs.some((l) => l.code !== SOURCE) ? ' xmlns:xhtml="http://www.w3.org/1999/xhtml"' : '';
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"${ns}>\n${urls.join('\n')}\n</urlset>\n`;
  return new Response(xml, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
};
