// @ts-check
/**
 * ►►► Übersetzen – die EINE Stelle (WEBSITE_PLAN Entscheid 136). ◄◄◄
 *
 * Jeder Text der Website wird deutsch geschrieben und geht durch `t()`:
 *
 *   export const cranePath = t('krantechnik', { title: 'So läuft es ab.', … });
 *
 * Im deutschen Build kommt der Wert unverändert zurück. In jedem anderen Build ersetzt `t()`
 * jeden Text durch seine Übersetzung – Zahlen, Symbole, Pfade und Bilder bleiben, wie sie im
 * Deutschen stehen (EINE Quelle für alles ausser Wörtern).
 *
 * ►►► Der deutsche Text IST der Schlüssel (wie bei gettext). ◄◄◄ `src/i18n/<sprache>/<datei>.json`
 * ist ein Wörterbuch «Deutsch → Übersetzung», je Datei die Texte eines Bereichs. Derselbe deutsche
 * Text wird einmal übersetzt und gilt überall. Ändert sich ein deutscher Text, ist er ein neuer
 * Schlüssel ohne Übersetzung – der Build bricht ab, bis er übersetzt ist (scripts/languages.mjs).
 * So kann keine Sprache still hinter dem Deutschen zurückbleiben.
 *
 * Was ein Text ist: jeder String mit Buchstaben – ausser unter einem Daten-Schlüssel (`DATA`,
 * z. B. `icon`, `href`, `photo`) oder einem Pfad aus `opts.keep`. Ein String nur aus Werten
 * (`{{history.founded}}`) ist kein Text.
 */
import { appendFileSync, existsSync, mkdirSync, readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { SOURCE, currentLang } from '../config/languages.mjs';

/** Schlüssel, deren Wert nie übersetzt wird (Daten, keine Wörter). */
export const DATA = new Set([
  'icon', 'href', 'illo', 'photo', 'id', 'ratio', 'path', 'file', 'area', 'from', 'to', 'slug', 'kind',
  'video', 'timeZone', 'query', 'import', 'tone', 'src', 'e164', 'intl', 'accept', 'pages', 'anchor', 'section',
  'photos', 'order', 'sight',
]);

/** Werte, Zahlen und Satzzeichen sind kein Text. */
export const isText = (/** @type {string} */ s) => /\p{L}{2,}/u.test(s.replace(/\{\{[^}]*\}\}/g, ''));

/** Wohin der deutsche Build alle Texte schreibt (für scripts/languages.mjs). */
export const TEXTS_FILE = resolve(process.cwd(), '.build/texte.jsonl');

/**
 * Geht jeden Text eines Werts durch (`swap` gibt den Ersatz) – tief kopiert, Getter bleiben Getter.
 * @template T
 * @param {T} value
 * @param {string[]} keep
 * @param {(de: string) => string} swap
 * @returns {T}
 */
export function mapTexts(value, keep, swap) {
  const kept = (/** @type {string} */ p) =>
    keep.some((k) => new RegExp(`^${k.replace(/\./g, '\\.').replace(/\*/g, '[^.]+')}(\\.|$)`).test(p));
  /** @type {(v: any, p: string, key: string) => any} */
  const walk = (v, p, key) => {
    if (p && kept(p)) return v;
    // Ein Daten-Schlüssel schützt nur Strings (`href: '/x'`), nicht ein ganzes Objekt darunter.
    if (typeof v === 'string') return !DATA.has(key) && isText(v) ? swap(v) : v;
    if (Array.isArray(v)) return v.map((x, i) => walk(x, p ? `${p}.${i}` : String(i), key));
    if (v && typeof v === 'object' && Object.getPrototypeOf(v) === Object.prototype) {
      /** @type {Record<string, any>} */
      const out = {};
      for (const [k, d] of Object.entries(Object.getOwnPropertyDescriptors(v))) {
        if ('get' in d && d.get) Object.defineProperty(out, k, { ...d });
        else out[k] = walk(d.value, p ? `${p}.${k}` : k, k);
      }
      return out;
    }
    return v;
  };
  return walk(value, '', '');
}

/** @type {Map<string, Map<string, string>>} */
const memory = new Map();
/** Das Wörterbuch einer Sprache: alle Dateien in src/i18n/<sprache>/ (ausser pfade.json). */
export function dictionary(/** @type {string} */ lang) {
  if (!memory.has(lang)) {
    const dir = resolve(process.cwd(), 'src/i18n', lang);
    /** @type {Map<string, string>} */
    const m = new Map();
    for (const n of existsSync(dir) ? readdirSync(dir) : []) {
      if (!n.endsWith('.json') || n === 'pfade.json') continue;
      for (const [de, tr] of Object.entries(JSON.parse(readFileSync(resolve(dir, n), 'utf8')))) if (tr) m.set(de, String(tr));
    }
    memory.set(lang, m);
  }
  return /** @type {Map<string, string>} */ (memory.get(lang));
}

/**
 * Den deutschen Wert in der Sprache dieses Builds.
 * @template T
 * @param {string} file  wohin die Texte im Wörterbuch gehören (src/i18n/<sprache>/<file>.json)
 * @param {T} value      der deutsche Wert (Text, Liste oder Objekt)
 * @param {{ keep?: string[] }} [opts] Pfade, die Daten sind (`seasons.*.from` – `*` = ein Index)
 * @returns {T}
 */
export function t(file, value, opts = {}) {
  const keep = opts.keep ?? [];
  const lang = currentLang().code;
  if (process.env.SITE_RECORD === '1' && lang === SOURCE) {
    /** @type {string[]} */
    const texts = [];
    mapTexts(value, keep, (de) => { texts.push(de); return de; });
    mkdirSync(resolve(process.cwd(), '.build'), { recursive: true });
    appendFileSync(TEXTS_FILE, `${JSON.stringify({ file, texts })}\n`);
  }
  return tFor(lang, value, opts);
}

/**
 * Den deutschen Wert in einer bestimmten Sprache – unabhängig vom Build. Für das, was eine Seite
 * oder ein Abdruck in mehreren Sprachen zugleich braucht (die eine 404-Seite, die Wörter des ERP,
 * `scripts/export-erp.mjs`). Der Wert muss schon durch `t()` gegangen sein – nur dort wird er gezählt.
 * @template T
 * @param {string} lang
 * @param {T} value
 * @param {{ keep?: string[] }} [opts]
 * @returns {T}
 */
export function tFor(lang, value, opts = {}) {
  if (lang === SOURCE) return value;
  const dict = dictionary(lang);
  // Fehlt eine Übersetzung, bleibt das Deutsch stehen – der Build hat vorher schon abgebrochen
  // (scripts/languages.mjs), ausser beim Ausprobieren mit «SITE_LANG=… astro dev».
  return mapTexts(value, opts.keep ?? [], (de) => dict.get(de) ?? de);
}

/**
 * Texte in fertigem Markup übersetzen – z. B. ein Schema als SVG (`…svg?raw`): jeder Textknoten und
 * jedes `aria-label`/`alt`/`title`. Dieselbe Regel wie `t()`, nur für Markup.
 * @param {string} file
 * @param {string} markup
 */
export function tMarkup(file, markup) {
  /** @type {string[]} */
  const found = [];
  markup.replace(/>([^<>]+)</g, (_, s) => { if (isText(s.trim())) found.push(s.trim()); return _; });
  markup.replace(/\s(?:aria-label|alt|title)="([^"]+)"/g, (_, s) => { if (isText(s)) found.push(s); return _; });
  const tr = t(file, found);
  const map = new Map(found.map((de, i) => [de, tr[i]]));
  return markup
    .replace(/>([^<>]+)</g, (m, s) => (map.has(s.trim()) ? `>${s.replace(s.trim(), /** @type {string} */ (map.get(s.trim())))}<` : m))
    .replace(/(\s(?:aria-label|alt|title)=")([^"]+)"/g, (m, a, s) => (map.has(s) ? `${a}${map.get(s)}"` : m));
}

/** @type {Map<string, Map<string, string>>} */
const reverse = new Map();
/**
 * Das deutsche Original eines übersetzten Texts – für Logik, die am Wortlaut hängt (z. B. welches
 * Bild zu einer Frage gehört). So entscheidet in jeder Sprache dasselbe deutsche Wort.
 * @param {string} text
 */
export function original(text) {
  const lang = currentLang().code;
  if (lang === SOURCE) return text;
  if (!reverse.has(lang)) reverse.set(lang, new Map([...dictionary(lang)].map(([de, tr]) => [tr, de])));
  return /** @type {Map<string, string>} */ (reverse.get(lang)).get(text) ?? text;
}
