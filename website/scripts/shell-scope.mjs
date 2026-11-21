// Auswahl-Regeln für das Stylesheet von Kopf und Fuss im Konto/ERP (scripts/export-shell.mjs).
// Eigene Datei, damit scripts/shell.test.mjs die Regel prüfen kann, ohne zu exportieren.

export const SCOPE = '.ix-shell';
/** Klassen, die die Website am <html> setzt (early.js, header.ts). */
const HTML_CLASSES = ['.js', '.menu-open'];

/** Eine Auswahl auf `.ix-shell` beschränken. */
export function scope(selector) {
  const s = selector.trim();
  if (s === ':root' || s === 'html' || s === 'body') return SCOPE;
  const m = s.match(/^(html|:root)((?:\[[^\]]*\]|[.:#][\w-]+(?:\([^)]*\))?)*)(\s+[\s\S]*)?$/);
  if (m) {
    const [, , rest = '', tail] = m;
    if (!tail) return s; // Regel allein am <html> – gilt der ganzen Seite (z. B. Scroll-Sperre)
    return `html${rest} ${SCOPE}${tail.replace(/^\s+body\b/, '')}`;
  }
  const cls = HTML_CLASSES.find((c) => s === c || s.startsWith(`${c} `) || s.startsWith(`${c}:`));
  if (cls) {
    const head = s.match(/^\S+/)[0];
    const tail = s.slice(head.length);
    return tail ? `html${head} ${SCOPE}${tail}` : `html${head}`;
  }
  if (s.startsWith('body ')) return `${SCOPE} ${s.slice(5)}`;
  return `${SCOPE} ${s}`;
}

