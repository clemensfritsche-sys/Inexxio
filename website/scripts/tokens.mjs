// Liest die Design-Tokens aus der EINEN Quelle des Hauses und schreibt die Werte, die die
// Website braucht, nach src/styles/tokens.css.
//
// Warum generiert statt kopiert: `frontend/src/styles/design-system/colors_and_type.css`
// ist laut CLAUDE.md die einzige Stelle, an der ein Token-Wert definiert wird. Eine
// abgeschriebene Kopie würde beim nächsten Re-Sync aus Claude Design still veralten.
// Die Datei selbst wird nicht importiert: sie lädt Inter über Google Fonts (Fremdanfrage),
// und die Website hostet ihre Schrift selbst.
//
// Fehlt ein Token, bricht das Skript ab – lieber ein roter Build als eine Farbe, die
// stillschweigend auf den Browser-Standard zurückfällt.

import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const SOURCE = resolve(here, '../../frontend/src/styles/design-system/colors_and_type.css');
const TARGET = resolve(here, '../src/styles/tokens.css');

/** DS-Token → Name auf der Website. Nur, was die Website wirklich liest. */
const MAP = {
  '--inexxio-red': '--red',
  '--inexxio-red-deep': '--red-deep',
  '--inexxio-red-bright': '--red-bright',
  '--color-primary-hover': '--red-hover',
  '--color-border-focus': '--line-focus',
  '--danger': '--danger',
  '--inexxio-black': '--black',
  '--fg-1': '--ink',
  '--fg-2': '--ink-2',
  '--fg-3': '--ink-3',
  '--fg-4': '--ink-4',
  '--fg-on-dark': '--on-dark',
  '--bg-1': '--white',
  '--bg-2': '--paper',
  '--bg-3': '--paper-2',
  '--bg-dark': '--dark',
  '--bg-dark-2': '--dark-2',
  '--border-1': '--line',
  '--border-2': '--line-2',
  '--border-on-dark': '--line-dark',
  '--border-strong': '--line-strong',
  '--accent': '--slate',
  '--accent-soft': '--slate-soft',
  '--success': '--ok',
  '--warning': '--amber',
  '--warning-bg': '--amber-bg',
  '--danger-bg': '--red-bg',
  '--font-mono': '--font-mono',
  '--r-sm': '--r-sm',
  '--r-md': '--r-md',
  '--r-lg': '--r-lg',
  '--shadow-sm': '--shadow-sm',
  '--shadow-md': '--shadow-md',
  '--shadow-lg': '--shadow-lg',
  '--shadow-red': '--shadow-red',
  '--dur-fast': '--t-fast',
  '--dur-base': '--t-base',
  '--ease-out': '--ease',
  '--tracking-tight': '--tracking-tight',
  '--tracking-snug': '--tracking-snug',
  '--tracking-overline': '--tracking-overline',
};

const css = readFileSync(SOURCE, 'utf8');
const root = css.match(/:root\s*\{([\s\S]*?)\n\}/);
if (!root) throw new Error(`Kein :root-Block in ${SOURCE}`);

const values = new Map();
for (const m of root[1].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) values.set(m[1], m[2].trim());

const missing = Object.keys(MAP).filter((k) => !values.has(k));
if (missing.length) {
  throw new Error(`Design-System-Token fehlen in ${SOURCE}: ${missing.join(', ')}`);
}

const lines = Object.entries(MAP).map(([from, to]) => {
  let value = values.get(from);
  // `var(--x)` verweist innerhalb des DS – hier gibt es nur die übernommenen Namen.
  // Seit v3 sind die Verweise mehrstufig (--fg-1 → --color-text → --gray-950): auflösen,
  // bis kein var() mehr übrig ist. Eine Schleife (Verweis auf sich selbst) bricht ab.
  for (let depth = 0; value.includes('var('); depth++) {
    if (depth > 8) throw new Error(`${from}: Verweiskette zu tief oder zyklisch`);
    value = value.replace(/var\((--[\w-]+)\)/g, (_, ref) => {
      if (!values.has(ref)) throw new Error(`${from} verweist auf unbekanntes ${ref}`);
      return values.get(ref);
    });
  }
  return `  ${to}: ${value}; /* ${from} */`;
});

const out = `/* GENERIERT von scripts/tokens.mjs – NICHT von Hand ändern.
   Quelle: frontend/src/styles/design-system/colors_and_type.css (Design-System des Hauses). */
:root {
${lines.join('\n')}
}
`;

mkdirSync(dirname(TARGET), { recursive: true });
let previous = '';
try { previous = readFileSync(TARGET, 'utf8'); } catch { /* erste Generierung */ }
if (previous !== out) writeFileSync(TARGET, out);
console.log(`tokens: ${Object.keys(MAP).length} Werte aus dem Design-System übernommen`);
