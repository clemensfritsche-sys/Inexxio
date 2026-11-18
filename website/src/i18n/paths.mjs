// @ts-check
/**
 * Die Adressen je Sprache: Deutsch ohne Vorsilbe, jede andere Sprache unter /<code>/… mit
 * übersetzten Pfaden – EINE Tabelle je Sprache, `src/i18n/<code>/pfade.json`
 * (deutscher Pfad → Pfad der Sprache). Gelesen beim Bauen (Sprachwahl, hreflang, Sitemap) und
 * beim Zusammenführen (scripts/languages.mjs schreibt jede Seite an ihre Adresse und jeden
 * Link auf die Adresse der Sprache um).
 */
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { SOURCE } from '../config/languages.mjs';

/** @type {Map<string, Record<string, string>>} */
const cache = new Map();

/** @param {string} lang @returns {Record<string, string>} */
export function pathTable(lang) {
  if (lang === SOURCE) return {};
  if (!cache.has(lang)) {
    const f = resolve(process.cwd(), `src/i18n/${lang}/pfade.json`);
    cache.set(lang, existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : {});
  }
  return /** @type {Record<string, string>} */ (cache.get(lang));
}

/**
 * Der Pfad einer deutschen Seite in einer Sprache (ohne Übersetzung: undefined).
 * @param {string} dePath  z. B. «/krantechnik/kranservice» oder «/»
 * @param {string} lang
 */
export function localPath(dePath, lang) {
  if (lang === SOURCE) return dePath;
  return pathTable(lang)[dePath];
}
