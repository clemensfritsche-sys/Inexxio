// @ts-check
/**
 * ►►► Die Sprachen der Website – EINE Liste. ◄◄◄
 *
 * Deutsch ist die Quelle: jeder Text wird deutsch geschrieben, jede andere Sprache übersetzt
 * ihn (src/i18n/<code>/, WEBSITE_PLAN Entscheid 136). Jede Sprache bekommt ihre eigenen
 * Adressen unter /<code>/… mit übersetzten Pfaden (src/i18n/<code>/pfade.json).
 *
 * `status`:
 *  - `live`     gebaut, indexierbar (Modus live), mit hreflang und in der Sitemap.
 *  - `preview`  gebaut und in der Sprachwahl, aber noindex, ohne hreflang, nicht in der Sitemap –
 *               bis eine Fachperson der Sprache gegengelesen hat. Im Modus «live» nicht gebaut.
 *  - `planned`  nur in der Sprachwahl als «bald» – nichts gebaut, nichts zu übersetzen.
 *
 * Eine gebaute Sprache ist IMMER vollständig und aktuell: fehlt ein Text oder hat sich das
 * Deutsch seit der Übersetzung geändert, bricht der Build ab (scripts/languages.mjs).
 */

/**
 * @typedef {{ code: string, locale: string, og: string, name: string, hello: string, read: string, soon: string, status: 'live' | 'preview' | 'planned' }} Language
 * `hello`, `read` und `soon` stehen in der Sprache selbst – so liest sie jeder in der Sprachwahl.
 * @type {Language[]}
 */
export const languages = [
  { code: 'de', locale: 'de-CH', og: 'de_CH', name: 'Deutsch', hello: 'Hallo', read: 'Auf Deutsch lesen', soon: 'Demnächst', status: 'live' },
  { code: 'fr', locale: 'fr-CH', og: 'fr_CH', name: 'Français', hello: 'Bonjour', read: 'Lire en français', soon: 'Bientôt disponible', status: 'live' },
  { code: 'en', locale: 'en', og: 'en_GB', name: 'English', hello: 'Hello', read: 'Read in English', soon: 'Coming soon', status: 'live' },
  { code: 'it', locale: 'it-CH', og: 'it_CH', name: 'Italiano', hello: 'Ciao', read: 'Leggi in italiano', soon: 'Presto disponibile', status: 'live' },
];

/** Die Quellsprache. */
export const SOURCE = 'de';

/** Die Sprache DIESES Builds (`SITE_LANG`, sonst Deutsch). */
export function currentLang() {
  const code = process.env.SITE_LANG || SOURCE;
  const l = languages.find((x) => x.code === code);
  if (!l) throw new Error(`SITE_LANG «${code}» steht nicht in src/config/languages.mjs.`);
  if (l.status === 'planned') throw new Error(`Sprache «${code}» ist erst geplant – zuerst auf «preview» stellen und übersetzen.`);
  return l;
}

/**
 * Welche Sprachen dieser Modus baut: im Modus «live» nur die freigegebenen, sonst auch die,
 * die gegengelesen werden.
 * @param {'preview' | 'live'} mode
 */
export function builtLanguages(mode) {
  return languages.filter((l) => l.status === 'live' || (l.status === 'preview' && mode !== 'live'));
}

/** Die indexierbaren Sprachen (hreflang, Sitemap). */
export function publishedLanguages() {
  return languages.filter((l) => l.status === 'live');
}
