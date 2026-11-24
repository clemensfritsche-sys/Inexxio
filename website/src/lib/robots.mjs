// @ts-check
/**
 * Inhalt der robots.txt – je nach Modus (Kapitel 5.5 und 13 des Auftrags). Eine reine
 * Funktion, damit auch der Zweig «live» geprüft werden kann, solange noch Fotos fehlen und
 * ein echter live-Build abbricht (scripts/seo.test.mjs).
 *
 *  preview  nur `/api/` gesperrt, keine Sitemap – nicht öffentlich ist die Vorschau durch
 *           `noindex` auf jeder Seite (check-site), nicht durch robots.txt
 *  live     die Crawler aus `site.seo.bots` ausdrücklich zugelassen, `/api/` gesperrt
 *           (`site.privatePaths`), Sitemap genannt. Die Seiten des Kundenbereichs sind NICHT
 *           gesperrt: sie tragen `noindex` (`site.noindexPages`), und das sieht nur, wer lesen darf.
 *
 * Die Domain gehört auch dem ERP – diese Datei ist die EINE robots.txt für beide.
 */
import { site } from '../config/site.mjs';

/**
 * @param {'preview' | 'live'} mode
 * @param {string} base  SITE_URL ohne Schrägstrich am Ende
 */
export function robotsTxt(mode, base) {
  if (mode !== 'live') {
    // Nicht «Disallow: /»: jede Seite der Vorschau trägt noindex (Meta, auf Staging dazu der
    // Kopf) – gesperrt sähe Google das nie und könnte die blosse Adresse zeigen.
    return ['# Vorschau – nicht öffentlich, jede Seite noindex (SITE_MODE=preview)', 'User-agent: *', ...site.privatePaths.map((p) => `Disallow: ${p}`), ''].join('\n');
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
