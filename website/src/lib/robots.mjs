// @ts-check
/**
 * Inhalt der robots.txt – je nach Modus (Kapitel 5.5 und 13 des Auftrags). Eine reine
 * Funktion, damit auch der Zweig «live» geprüft werden kann, solange noch Markierungen
 * offen sind und ein echter live-Build abbricht (scripts/seo.test.mjs).
 *
 *  preview  alles gesperrt (die Vorschau ist nicht öffentlich)
 *  live     die Crawler aus `site.seo.bots` ausdrücklich zugelassen, die Bereiche des
 *           Kundenbereichs (`site.privatePaths`) gesperrt, Sitemap genannt
 *
 * Die Domain gehört auch dem ERP – diese Datei ist die EINE robots.txt für beide.
 */
import { site } from '../config/site.mjs';

/**
 * @param {'preview' | 'live'} mode
 * @param {string} base  SITE_URL ohne Schrägstrich am Ende
 */
export function robotsTxt(mode, base) {
  // Auch in der Vorschau stehen die Konto- und ERP-Pfade ausdrücklich da (Auftrag 12.5:
  // «immer Disallow») – sonst fiele ihre Sperre beim Umschalten auf «live» als Erstes weg.
  if (mode !== 'live') {
    return ['# Vorschau – nicht öffentlich (SITE_MODE=preview)', 'User-agent: *', 'Disallow: /', ...site.privatePaths.map((p) => `Disallow: ${p}`), ''].join('\n');
  }
  const rules = ['Allow: /', ...site.privatePaths.map((p) => `Disallow: ${p}`)];
  return [
    `# ${site.brand.name} – Website und Kundenbereich`,
    '',
    ...site.seo.bots.map((b) => `User-agent: ${b}`),
    ...rules,
    '',
    'User-agent: *',
    ...rules,
    '',
    `Sitemap: ${base}/sitemap.xml`,
    '',
  ].join('\n');
}
