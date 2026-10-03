// ►►► Führt die Website in die Hosting-Ausgabe des ERP zusammen. ◄◄◄
//
//   node scripts/merge-hosting.mjs [ziel]      Standard-Ziel: ../frontend/out
//
// Firebase Hosting hat EINE Site je Umgebung (firebase.json: public = frontend/out). Die
// Website besitzt «/» und ihre Seiten, das ERP behält /erp, /konto, /login, /agb, /_next.
// Kollidiert eine Datei, bricht das Skript ab – mit zwei bewusst erlaubten Ausnahmen:
//   404.html   die Fehlerseite der Website gilt für die ganze Domain
//   robots.txt die EINE robots.txt (das ERP liefert keine mehr)
// Eine Website-Datei auf einem ERP-Pfad bricht immer ab.
import { cpSync, existsSync, readdirSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(ROOT, 'dist');
const TARGET = resolve(process.argv[2] ?? join(ROOT, '..', 'frontend', 'out'));
const OVERRIDES = new Set(['404.html', 'robots.txt']);
const ERP = /^(erp|konto|login|agb|api|_next)(\/|\.html$|$)/;

function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

if (!existsSync(DIST)) {
  console.error('merge-hosting: website/dist fehlt – zuerst «npm run build».');
  process.exit(1);
}
if (!existsSync(TARGET)) {
  console.error(`merge-hosting: ${TARGET} fehlt – zuerst das ERP bauen (frontend: npm run build).`);
  process.exit(1);
}
if (!existsSync(join(TARGET, 'erp.html')) && !existsSync(join(TARGET, 'erp', 'index.html'))) {
  console.error(`merge-hosting: ${TARGET} sieht nicht nach der ERP-Ausgabe aus (keine erp.html).`);
  process.exit(1);
}

const problems = [];
let overridden = 0;
const files = walk(DIST).map((f) => relative(DIST, f).replace(/\\/g, '/'));
for (const rel of files) {
  if (ERP.test(rel)) problems.push(`${rel} läge auf einem Pfad des ERP`);
  else if (existsSync(join(TARGET, rel))) {
    if (OVERRIDES.has(rel)) overridden += 1;
    else problems.push(`${rel} gibt es schon in der ERP-Ausgabe`);
  }
}
if (problems.length) {
  console.error('merge-hosting: abgebrochen – nichts kopiert.');
  for (const p of problems) console.error(`  ${p}`);
  process.exit(1);
}
cpSync(DIST, TARGET, { recursive: true });
console.log(`merge-hosting: ${files.length} Dateien nach ${relative(process.cwd(), TARGET) || TARGET} (${overridden} bewusst ersetzt: ${[...OVERRIDES].join(', ')})`);
