/**
 * /sitemap.xml – nur indexierbare Seiten (src/lib/pages.ts), mit lastmod.
 * Im Modus «preview» gibt es sie ebenfalls (prüfbar); robots.txt nennt sie dort nicht.
 */
import type { APIRoute } from 'astro';
import { pages } from '../lib/pages';

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;');

export const GET: APIRoute = ({ site }) => {
  const base = site!.href.replace(/\/$/, '');
  const urls = pages().map((p) => `  <url><loc>${esc(p.path === '/' ? `${base}/` : `${base}${p.path}`)}</loc><lastmod>${p.updated}</lastmod></url>`);
  const xml = `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.join('\n')}\n</urlset>\n`;
  return new Response(xml, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
};
