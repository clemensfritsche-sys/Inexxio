// @ts-check
/**
 * Text-Werkzeuge der Website – die EINE Stelle, an der aus einem geschriebenen Text
 * HTML (oder reiner Text) wird.
 *
 * Drei Dinge passieren hier, und nur hier:
 *  1. **Werte aus der Konfiguration** – `{{phone.display}}` wird zu «052 378 22 47».
 *     So steht eine Telefonnummer auch im Fliesstext genau einmal (in `site.mjs`).
 *     Ein unbekannter Schlüssel bricht den Build ab.
 *  2. **Markierungen** – `[[PLATZHALTER: …]]` / `[[PRÜFEN: …]]` werden im Modus
 *     «preview» sichtbar (gelb gestrichelt, mit Label). Im Modus «live» ist eine
 *     Markierung ein Fehler: der Build bricht ab.
 *  3. **Minimales Inline-Markup** in Content-Dateien: `**fett**` und `[Text](/pfad)`.
 *
 * `rich()` liefert HTML (für `set:html`), `plain()` liefert Text (für Meta-Tags,
 * Alt-Texte, JSON-LD, llms.txt). Beide lesen dieselben Werte.
 */
import { site, contactEmail } from '../config/site.mjs';

export const MARKER_RE = /\[\[(PLATZHALTER|PRÜFEN):\s*([^\]]*?)\s*\]\]/g;
const TOKEN_RE = /\{\{\s*([\w.]+)\s*\}\}/g;

/** @returns {'preview' | 'live'} */
export function siteMode() {
  // @ts-ignore – von Vite (astro.config.mjs → define) eingesetzt; in Node-Skripten fehlt es.
  const defined = typeof __SITE_MODE__ !== 'undefined' ? __SITE_MODE__ : undefined;
  const raw = defined ?? process.env.SITE_MODE ?? 'preview';
  if (raw !== 'preview' && raw !== 'live') {
    throw new Error(`SITE_MODE muss «preview» oder «live» sein, nicht «${raw}».`);
  }
  return raw;
}

export const isLive = () => siteMode() === 'live';

/** @param {string} s */
export function escapeHtml(s) {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

/**
 * Flacht die Konfiguration zu `a.b.c → Wert` ab (nur Text, Zahlen, Text-Listen).
 * @param {Record<string, unknown>} obj
 * @param {string} [prefix]
 * @param {Record<string, string>} [out]
 * @returns {Record<string, string>}
 */
function flatten(obj, prefix = '', out = {}) {
  for (const [k, v] of Object.entries(obj)) {
    const key = prefix ? `${prefix}.${k}` : k;
    if (typeof v === 'string' || typeof v === 'number') out[key] = String(v);
    else if (Array.isArray(v) && v.every((x) => typeof x === 'string')) out[key] = v.join(', ');
    else if (v && typeof v === 'object' && !Array.isArray(v)) flatten(/** @type {Record<string, unknown>} */ (v), key, out);
  }
  return out;
}

const a = site.address;
/**
 * Alle einsetzbaren Werte. Abgeleitete stehen ausdrücklich hier, nicht in den Texten.
 * @type {Record<string, string>}
 */
export const TOKENS = {
  ...flatten(site),
  email: contactEmail(),
  'address.line': `${a.street}, ${a.zip} ${a.city}`,
  'address.place': `${a.zip} ${a.city} (${a.municipality} ${a.canton})`,
  'marks.mixerList': site.marks.mixers.join(', '),
  year: String(new Date().getFullYear()),
};

/** Tokens, die im HTML zu einem Link werden (im Text: nur die Anzeige). */
const LINK_TOKENS = {
  'phone.link': () => ({ href: `tel:${site.phone.e164}`, label: site.phone.display, track: 'tel_click' }),
  'pikett.link': () => ({ href: `tel:${site.pikett.e164}`, label: site.pikett.display, track: 'pikett_click' }),
  'email.link': () => ({ href: `mailto:${contactEmail()}`, label: contactEmail(), track: 'mailto_click' }),
};

/**
 * Setzt `{{…}}`-Werte ein – rekursiv, weil ein Konfigurationswert selbst einen Namen
 * enthalten darf (`brand.full` = «{{brand.name}} ({{brand.formerly}})»).
 * @param {string} text
 * @param {{ links?: 'keep' | 'label' }} [opts]
 */
export function resolve(text, opts = {}) {
  let out = String(text);
  for (let depth = 0; depth < 4; depth++) {
    let changed = false;
    out = out.replace(TOKEN_RE, (m, key) => {
      if (key in LINK_TOKENS) {
        if (opts.links === 'keep') return m;
        changed = true;
        return LINK_TOKENS[/** @type {keyof typeof LINK_TOKENS} */ (key)]().label;
      }
      if (!(key in TOKENS)) {
        throw new Error(`Unbekannter Wert «{{${key}}}» – er steht nicht in src/config/site.mjs.`);
      }
      changed = true;
      return TOKENS[key];
    });
    if (!changed) return out;
  }
  if (TOKEN_RE.test(out)) throw new Error(`Werte verweisen im Kreis: «${text}»`);
  return out;
}

/** @param {string} kind @param {string} note */
function markerHtml(kind, note) {
  if (isLive()) {
    throw new Error(`Offene Markierung im Modus «live»: [[${kind}: ${note}]]`);
  }
  const label = kind === 'PRÜFEN' ? 'Prüfen' : 'Platzhalter';
  const cls = kind === 'PRÜFEN' ? 'mk mk--check' : 'mk mk--ph';
  return `<span class="${cls}"><span class="mk__label">${label}</span> ${note}</span>`;
}

/** @param {string} label @param {string} href */
function linkHtml(label, href) {
  const external = /^https?:\/\//.test(href);
  const track = href.startsWith('tel:') ? ' data-track="tel_click"'
    : href.startsWith('mailto:') ? ' data-track="mailto_click"' : '';
  const tap = /^(tel|mailto):/.test(href) ? ' class="tap"' : '';
  return `<a href="${href}"${tap}${external ? ' rel="noopener"' : ''}${track}>${label}</a>`;
}

/**
 * Text → HTML (für `set:html`).
 * @param {string | undefined | null} text
 */
export function rich(text) {
  if (text == null || text === '') return '';
  let html = escapeHtml(resolve(text, { links: 'keep' }));
  html = html.replace(/\{\{\s*([\w.]+)\s*\}\}/g, (_, key) => {
    const link = LINK_TOKENS[/** @type {keyof typeof LINK_TOKENS} */ (key)]();
    return `<a href="${escapeHtml(link.href)}" class="tap" data-track="${link.track}">${escapeHtml(link.label)}</a>`;
  });
  html = html.replace(MARKER_RE, (_, kind, note) => markerHtml(kind, note));
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
  html = html.replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, (_, label, href) => linkHtml(label, href));
  return html;
}

/**
 * Text → reiner Text (Meta, Alt, JSON-LD, llms.txt): Werte eingesetzt, Markierungen weg.
 * @param {string | undefined | null} text
 */
export function plain(text) {
  if (text == null) return '';
  return resolve(text)
    .replace(MARKER_RE, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/\[([^\]]+)\]\(([^)\s]+)\)/g, '$1')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+([.,;:])/g, '$1')
    .trim();
}

/**
 * Enthält der Text (nach dem Einsetzen) eine Markierung?
 * @param {string | undefined | null} text
 */
export function hasMarker(text) {
  if (text == null) return false;
  MARKER_RE.lastIndex = 0;
  const found = MARKER_RE.test(resolve(String(text)));
  MARKER_RE.lastIndex = 0;
  return found;
}

/**
 * Fertig gerendertes HTML (z. B. aus Markdown) nachbearbeiten: Werte einsetzen und
 * Markierungen sichtbar machen – aber nur im TEXT, nie innerhalb eines Tags.
 * @param {string} html
 */
export function processHtml(html) {
  let tables = 0;
  return html
    .split(/(<[^>]+>)/g)
    .map((part) => {
      if (part.startsWith('<')) {
        // In Attributen nur Werte einsetzen (z. B. href="tel:{{phone.e164}}").
        return part.replace(TOKEN_RE, (_, key) => escapeHtml(resolve(`{{${key}}}`)));
      }
      const withValues = part.replace(TOKEN_RE, (m, key) => {
        if (key in LINK_TOKENS) return m;
        return escapeHtml(resolve(m));
      });
      return withValues
        .replace(/\{\{\s*([\w.]+)\s*\}\}/g, (_, key) => {
          const link = LINK_TOKENS[/** @type {keyof typeof LINK_TOKENS} */ (key)]();
          return `<a href="${escapeHtml(link.href)}" class="tap" data-track="${link.track}">${escapeHtml(link.label)}</a>`;
        })
        .replace(MARKER_RE, (_, kind, note) => markerHtml(kind, note));
    })
    .join('')
    .replace(/<table>/g, () => `<div class="table-scroll" tabindex="0" role="region" aria-label="Tabelle ${++tables}"><table>`)
    .replace(/<\/table>/g, '</table></div>');
}
