// @ts-check
/**
 * ►►► Der Build aller Sprachen – und der Wächter, dass keine zurückbleibt. ◄◄◄
 * (WEBSITE_PLAN Entscheid 136, src/config/languages.mjs, src/i18n/t.mjs)
 *
 *   node scripts/languages.mjs            Build: Deutsch → Prüfung → jede weitere Sprache → zusammenführen
 *   node scripts/languages.mjs --status   nur die Prüfung (gegen den letzten deutschen Build)
 *   node scripts/languages.mjs --prepare  fehlende Texte leer eintragen, verwaiste entfernen
 *
 * Die Prüfung je gebauter Sprache – jede Abweichung bricht den Build:
 *   fehlt     ein deutscher Text hat keine Übersetzung (auch: er wurde geändert – dann ist der alte «verwaist»)
 *   leer      die Übersetzung ist leer
 *   Werte     die Übersetzung trägt andere {{Werte}}, Links oder Hervorhebungen als das Deutsch
 *   verwaist  eine Übersetzung, deren deutscher Text es nicht mehr gibt
 *   Pfad      eine Seite ohne Adresse in der Sprache (pfade.json), oder eine Adresse ohne Seite
 *   Ratgeber  ein Artikel ohne Übersetzung, oder sein deutscher Text hat sich seit der Übersetzung geändert
 */
import { execFileSync } from 'node:child_process';
import { createHash } from 'node:crypto';
import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { SOURCE, builtLanguages, languages } from '../src/config/languages.mjs';
import { siteMode } from '../src/lib/text.mjs';

const ROOT = process.cwd();
const DIST = resolve(ROOT, 'dist');
const BUILD = resolve(ROOT, '.build');
const TEXTS = join(BUILD, 'texte.jsonl');
const ARTICLES = resolve(ROOT, 'src/content/ratgeber');
const SITE_URL = (process.env.SITE_URL ?? 'http://localhost:4321').replace(/\/+$/, '');
const others = builtLanguages(siteMode()).filter((l) => l.code !== SOURCE);

/** @param {string} dir @returns {string[]} */
const walk = (dir) => readdirSync(dir).flatMap((n) => {
  const p = join(dir, n);
  return statSync(p).isDirectory() ? walk(p) : [p];
});
/** Pfad einer Seite aus ihrer Datei: krantechnik/kranservice.html → /krantechnik/kranservice */
const pathOf = (/** @type {string} */ rel) => {
  const p = `/${rel.replace(/\\/g, '/').replace(/\.html$/, '').replace(/(^|\/)index$/, '')}`.replace(/\/$/, '');
  return p || '/';
};
const sha = (/** @type {string} */ s) => createHash('sha256').update(s).digest('hex').slice(0, 16);
const astro = (/** @type {Record<string, string>} */ env) =>
  execFileSync('npx', ['astro', 'build'], { stdio: 'inherit', env: { ...process.env, ...env } });

// ---------------------------------------------------------------- was es zu übersetzen gibt
/** Alle deutschen Texte des letzten Builds: Text → Dateien, in denen er steht. */
function sourceTexts() {
  if (!existsSync(TEXTS)) throw new Error('Keine Texte des deutschen Builds – zuerst «npm run build».');
  /** @type {Map<string, Set<string>>} */
  const out = new Map();
  for (const line of readFileSync(TEXTS, 'utf8').split('\n').filter(Boolean)) {
    const { file, texts } = JSON.parse(line);
    for (const de of texts) (out.get(de) ?? out.set(de, new Set()).get(de))?.add(file);
  }
  return out;
}

/** Die deutschen Seiten (ohne 404 – die eine Fehlerseite der Hosting-Site, und ohne die schon
    zusammengeführten Seiten der anderen Sprachen, wenn `--status` nach einem ganzen Build läuft). */
const otherRoots = languages.filter((l) => l.code !== SOURCE).map((l) => `/${l.code}`);
const sourcePages = () => walk(DIST).filter((f) => f.endsWith('.html')).map((f) => pathOf(relative(DIST, f)))
  .filter((p) => p !== '/404' && !otherRoots.some((r) => p === r || p.startsWith(`${r}/`)));

/** @param {string} lang */
const langDir = (lang) => resolve(ROOT, 'src/i18n', lang);
/** @param {string} lang @param {string} file @returns {Record<string, string>} */
const readJson = (lang, file) => {
  const f = join(langDir(lang), `${file}.json`);
  return existsSync(f) ? JSON.parse(readFileSync(f, 'utf8')) : {};
};
/** Die Werte eines Textes (`{{phone.link}}` …) – eine Übersetzung trägt genau dieselben. */
const tokens = (/** @type {string} */ s) => [...s.matchAll(/\{\{\s*[\w.]+\s*\}\}|\[[^\]]+\]\([^)]+\)|\*\*|==/g)]
  .map((m) => m[0].replace(/^\[[^\]]+\]/, '[…]')).sort().join(' ');

/**
 * Was in einer Sprache nicht stimmt – je Befund ein Satz.
 * @param {string} lang
 * @param {boolean} [prepare] fehlende als "" eintragen (in die Datei, in der der Text steht), verwaiste entfernen
 */
function audit(lang, prepare = false) {
  const src = sourceTexts();
  /** @type {string[]} */
  const issues = [];
  const names = (existsSync(langDir(lang)) ? readdirSync(langDir(lang)) : [])
    .filter((n) => n.endsWith('.json') && n !== 'pfade.json').map((n) => n.slice(0, -5));
  /** @type {Record<string, Record<string, string>>} */
  const files = Object.fromEntries(names.map((n) => [n, readJson(lang, n)]));
  const have = new Map(Object.entries(files).flatMap(([n, d]) => Object.entries(d).map(([de, tr]) => [de, { file: n, tr }])));
  for (const [de, where] of src) {
    const h = have.get(de);
    const file = [...where][0];
    if (!h) {
      issues.push(`fehlt      ${lang}/${file}.json: «${de}»`);
      if (prepare) (files[file] ??= {})[de] = '';
    } else if (!h.tr.trim()) issues.push(`leer       ${lang}/${h.file}.json: «${de}»`);
    else if (tokens(de) !== tokens(h.tr)) issues.push(`Werte      ${lang}/${h.file}.json: «${de}» → «${h.tr}» – Werte, Links und Hervorhebungen ({{…}}, [..](..), **, ==) müssen gleich bleiben`);
  }
  for (const [n, d] of Object.entries(files)) {
    for (const de of Object.keys(d)) {
      if (src.has(de)) continue;
      issues.push(`verwaist   ${lang}/${n}.json: «${de}» – den deutschen Text gibt es nicht mehr`);
      if (prepare) delete d[de];
    }
  }
  if (prepare) {
    mkdirSync(langDir(lang), { recursive: true });
    for (const [n, d] of Object.entries(files)) writeFileSync(join(langDir(lang), `${n}.json`), `${JSON.stringify(d, null, 2)}\n`);
  }
  // Adressen: jede deutsche Seite hat genau eine in der Sprache, unter /<sprache>.
  const table = readJson(lang, 'pfade');
  const pagesDe = sourcePages();
  const seen = new Set();
  for (const p of pagesDe) {
    const to = table[p];
    if (!to) {
      issues.push(`Pfad       ${lang}/pfade.json: «${p}» hat keine Adresse`);
      if (prepare) table[p] = '';
    } else if (to !== `/${lang}` && !to.startsWith(`/${lang}/`)) issues.push(`Pfad       ${lang}/pfade.json: «${to}» liegt nicht unter /${lang}`);
    else if (seen.has(to)) issues.push(`Pfad       ${lang}/pfade.json: «${to}» steht zweimal`);
    seen.add(to);
  }
  for (const p of Object.keys(table)) if (!pagesDe.includes(p)) issues.push(`Pfad       ${lang}/pfade.json: «${p}» gibt es nicht (mehr)`);
  if (prepare) writeFileSync(join(langDir(lang), 'pfade.json'), `${JSON.stringify(table, null, 2)}\n`);
  // Ratgeber: je Artikel eine Übersetzung, die den Fingerabdruck ihres deutschen Originals trägt.
  for (const name of readdirSync(ARTICLES).filter((n) => n.endsWith('.md'))) {
    const tr = join(ARTICLES, lang, name);
    const want = sha(readFileSync(join(ARTICLES, name), 'utf8'));
    if (!existsSync(tr)) { issues.push(`Ratgeber   ${relative(ROOT, tr)} fehlt (Fingerabdruck des Originals: ${want})`); continue; }
    const got = /^quelle:\s*"?([0-9a-f]{16})"?\s*$/m.exec(readFileSync(tr, 'utf8'))?.[1];
    if (got !== want) issues.push(`Ratgeber   ${relative(ROOT, tr)}: das Deutsch hat sich geändert (quelle ${got ?? '–'} → ${want}) – nachziehen, dann «quelle: ${want}»`);
  }
  return issues;
}

// ---------------------------------------------------------------- zusammenführen
const esc = (/** @type {string} */ s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

/**
 * Jeden Link einer Seite auf die Adresse der Sprache: `href="/krantechnik#x"` und volle
 * Adressen (canonical, og:url, JSON-LD). Ein Tag mit `hreflang` zeigt bewusst auf eine andere
 * Sprache (Sprachwahl, alternate) – er bleibt, wie er ist.
 * @param {string} html @param {Record<string, string>} table
 */
function relink(html, table) {
  const map = (/** @type {string} */ p) => table[p.replace(/\/$/, '') || '/'];
  const fix = (/** @type {string} */ part) => part
    .replace(/(href=")(\/[^"#?]*)/g, (m, a, p) => (map(p) ? a + map(p) : m))
    .replace(new RegExp(`${esc(SITE_URL)}(/[^"#?\\s<\\\\]*)`, 'g'), (m, p) => (map(p) ? SITE_URL + map(p) : m));
  return html.split(/(<(?:a|link)\b[^>]*\shreflang="[^"]*"[^>]*>)/g).map((part, i) => (i % 2 ? part : fix(part))).join('');
}

/** @param {string} lang */
function merge(lang) {
  const out = resolve(BUILD, `site-${lang}`);
  const table = readJson(lang, 'pfade');
  for (const file of walk(out)) {
    const rel = relative(out, file).replace(/\\/g, '/');
    if (rel.startsWith('_astro/')) {
      const to = join(DIST, rel);
      if (existsSync(to)) {
        if (!readFileSync(to).equals(readFileSync(file))) throw new Error(`${rel}: gleicher Name, anderer Inhalt in Deutsch und «${lang}».`);
        continue;
      }
      mkdirSync(dirname(to), { recursive: true });
      copyFileSync(file, to);
      continue;
    }
    if (!rel.endsWith('.html') || rel === '404.html') continue;
    const target = table[pathOf(rel)];
    if (!target) throw new Error(`«${pathOf(rel)}» hat keine Adresse in ${lang}/pfade.json.`);
    const to = join(DIST, `${target.slice(1)}.html`);
    if (existsSync(to)) throw new Error(`${relative(ROOT, to)} gibt es schon – zwei Seiten auf derselben Adresse.`);
    mkdirSync(dirname(to), { recursive: true });
    writeFileSync(to, relink(readFileSync(file, 'utf8'), table));
  }
}

// ---------------------------------------------------------------- Ablauf
const arg = process.argv[2];
const report = (/** @type {string} */ lang, /** @type {string[]} */ issues) => {
  if (!issues.length) { console.log(`Sprachen: ${lang} vollständig und aktuell.`); return true; }
  console.error(`\nSprachen: «${lang}» – ${issues.length} Befunde (WEBSITE_PLAN Entscheid 136):`);
  for (const i of issues) console.error(`  ${i}`);
  return false;
};

if (arg === '--status' || arg === '--prepare') {
  let ok = true;
  for (const l of others) ok = report(l.code, audit(l.code, arg === '--prepare')) && ok;
  process.exit(ok ? 0 : 1);
}

rmSync(BUILD, { recursive: true, force: true });
astro({ SITE_LANG: SOURCE, SITE_RECORD: '1' });
let ok = true;
for (const l of others) ok = report(l.code, audit(l.code)) && ok;
if (!ok) {
  console.error('\nJede gebaute Sprache ist vollständig und aktuell – sonst kein Build. Übersetzung nachziehen');
  console.error('(src/i18n/<sprache>/), «node scripts/languages.mjs --prepare» trägt Fehlendes als leer ein.');
  process.exit(1);
}
for (const l of others) {
  astro({ SITE_LANG: l.code });
  merge(l.code);
}
