// ►►► EIN Kopf und EIN Fuss für Website UND Konto/ERP (WEBSITE_PLAN Entscheid 60). ◄◄◄
//
// Rückmeldung 04.10.2026: «Der Header muss genau gleich sein … ein Header für beides, eine
// globale Funktion, Logik, Design.» Vorher gab es zwei: Header.astro hier und einen
// React-Nachbau im Frontend – zwei Fassungen, die auseinanderliefen (Profilbild, Dropdown-
// Bilder, Masse). Jetzt ist Header.astro/Footer.astro die einzige Quelle, und das Frontend
// übernimmt beim Bauen, was dieser Build daraus gemacht hat:
//
//   dist/_shell/shell.json        Kopf- und Fuss-HTML, Skripte, Stylesheet, Kontakt-Vorgabe
//   dist/_shell/shell.<hash>.css  das Stylesheet der Website, auf `.ix-shell` beschränkt
//
// Gelesen wird `dist/404.html` – eine fertige Seite, auf der kein Menüpunkt als «aktuell»
// markiert ist. Dieselben Skripte wie auf jeder Website-Seite (Kopf, Profil, Kontaktdaten
// aus dem ERP); das Frontend lädt sie unverändert.
//
// Warum beschränkt: das Stylesheet der Website setzt auch Grundregeln (body, a, h1 …). Im
// ERP dürfen sie nur Kopf und Fuss treffen. Jede Regel bekommt darum `.ix-shell` davor;
// `:root`/`body` werden zu `.ix-shell` (Tokens, Schrift), Regeln am <html> (z. B.
// `html[data-account]`, Scroll-Sperre des Mobil-Menüs) behalten ihr `html` vorne.
import { createHash } from 'node:crypto';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import postcss from 'postcss';
import { SCOPE, scope } from './shell-scope.mjs';

const DIST = resolve(process.cwd(), 'dist');
const OUT = resolve(DIST, '_shell');

const page = readFileSync(resolve(DIST, '404.html'), 'utf8');
const pick = (re, what) => {
  const m = page.match(re);
  if (!m) throw new Error(`export-shell: ${what} nicht in dist/404.html gefunden.`);
  return m[1] ?? m[0];
};

const header = pick(/<header class="site-header[\s\S]*?<\/header>/, 'Kopf');
const footer = pick(/<footer class="site-footer[\s\S]*?<\/footer>/, 'Fuss');
const cssHref = pick(/<link rel="stylesheet" href="(\/_astro\/[^"]+\.css)"/, 'Stylesheet');
const early = pick(/<script src="(\/_astro\/early\.[^"]+\.js)"/, 'early.js');
const module = pick(/<script type="module" src="(\/_astro\/Base[^"]+\.js)"/, 'Seiten-Skript');
const contact = pick(/<body[^>]*\sdata-contact="([^"]*)"/, 'Kontakt-Vorgabe').replaceAll('&quot;', '"');

const raw = readFileSync(resolve(DIST, cssHref.slice(1)), 'utf8');
const root = postcss.parse(raw);
// Die Kopfhöhe braucht auch das ERP (es zieht sie von der Fensterhöhe ab) – sie kommt von
// hier als `--site-header-h` am :root, statt dort ein zweites Mal als Zahl zu stehen.
const heights = [];
root.walkDecls('--header-h', (d) => {
  const rule = d.parent;
  if (rule?.type !== 'rule' || rule.selector.trim() !== ':root') return;
  const media = rule.parent?.type === 'atrule' && rule.parent.name === 'media' ? rule.parent.params : null;
  heights.push(media ? `@media ${media}{:root{--site-header-h:${d.value}}}` : `:root{--site-header-h:${d.value}}`);
});
if (!heights.length) throw new Error('export-shell: --header-h nicht im Stylesheet der Website gefunden.');
root.walkRules((rule) => {
  if (rule.parent?.type === 'atrule' && /keyframes$/i.test(rule.parent.name)) return;
  rule.selectors = rule.selectors.map(scope);
});
// Die Hülle selbst hat keine Box – sonst klebte der Kopf (position: sticky) an ihr fest.
const css = `${heights.join('\n')}\n${SCOPE}{display:contents}\n${root.toString()}`;
const hash = createHash('sha256').update(css).digest('hex').slice(0, 10);
const cssFile = `shell.${hash}.css`;

mkdirSync(OUT, { recursive: true });
writeFileSync(resolve(OUT, cssFile), css);
const shell = {
  _comment: 'Generiert von website/scripts/export-shell.mjs beim Website-Build – nicht von Hand ändern.',
  header,
  footer,
  css: `/_shell/${cssFile}`,
  early,
  module,
  contact,
};
writeFileSync(resolve(OUT, 'shell.json'), `${JSON.stringify(shell, null, 2)}\n`);
console.log(`export-shell: Kopf ${(header.length / 1024).toFixed(1)} KB · Fuss ${(footer.length / 1024).toFixed(1)} KB · ${cssFile}`);
