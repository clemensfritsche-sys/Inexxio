// ►►► Fotoliste: welche Bildstellen haben noch kein echtes Foto? ◄◄◄
//
//   node scripts/check-content.mjs --dist      Build-Ausgabe prüfen und OFFENE_PUNKTE.md schreiben
//
// Bildstellen ohne echtes Foto tragen `data-photo-missing` (Photo.astro). Die Liste ist die
// Vorlage für den Fototag.
//
// Modus «preview» (Standard): Bericht, Exit 0.
// Modus «live»:               ein fehlendes Foto ist ein Fehler, Exit 1 – der Build bricht ab.
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { site } from '../src/config/site.mjs';
import { photos } from '../src/config/photos.mjs';
import { samples } from '../src/config/photo-samples.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const LIVE = (process.env.SITE_MODE ?? 'preview') === 'live';

function walk(dir, exts) {
  if (!existsSync(dir)) return [];
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p, exts));
    else if (exts.includes(extname(name))) out.push(p);
  }
  return out;
}

function pageOf(file, dist) {
  const rel = relative(dist, file).replace(/\\/g, '/');
  if (rel === 'index.html') return '/';
  return rel.endsWith('.html') ? `/${rel.slice(0, -5)}` : `/${rel}`;
}

function scanDist() {
  const dist = join(ROOT, 'dist');
  if (!existsSync(dist)) throw new Error('dist/ fehlt – zuerst bauen (npm run build).');
  const missing = new Map();
  for (const file of walk(dist, ['.html'])) {
    const page = pageOf(file, dist);
    for (const m of readFileSync(file, 'utf8').matchAll(/data-photo-missing="([^"]+)"/g)) {
      if (!missing.has(m[1])) missing.set(m[1], new Set());
      missing.get(m[1]).add(page);
    }
  }
  return missing;
}

const esc = (s) => String(s).replace(/\|/g, '\\|');

function writeReport(missing) {
  const rows = Object.entries(photos)
    .filter(([, p]) => !p.file)
    .map(([id, p]) => ({ id, p, pages: [...(missing.get(id) ?? [])] }));
  const disabled = Object.entries(site.features).filter(([, on]) => on === false);
  const lines = [
    '# Offene Punkte – Website INEXXIO (ehemals HS Steiner)',
    '',
    '> Generiert nach jedem `npm run build`. Nicht von Hand ändern – sobald ein Foto in',
    '> `src/config/photos.mjs` eine Datei hat, verschwindet seine Zeile von selbst.',
    '> Solange hier ein Foto steht, bricht ein Build im Modus `live` ab.',
    '',
    `**Stand:** ${rows.length} Fotos · ${disabled.length} abgeschaltete Sektionen`,
    '',
    '## Fotos',
    '',
    'Empfehlung: ein professioneller Fototag – der grösste Hebel für die Qualität der Seite.',
    '',
    '| Foto | Beschreibung für den Fototag | Format | Verwendet auf |',
    '|---|---|---|---|',
  ];
  for (const { id, p, pages } of rows) {
    const used = pages.length ? pages.map((x) => `\`${x}\``).join(', ')
      : p.feature ? `abgeschaltete Sektion \`${p.feature}\`` : 'noch nicht verwendet';
    lines.push(`| \`${id}\`${samples[id] ? ' (zurzeit Beispielbild)' : ''} | ${esc(p.brief)} | ${p.ratio.replace('/', ':')} | ${used} |`);
  }
  lines.push('', '## Abgeschaltete Sektionen (`features` in `src/config/site.mjs`)', '');
  for (const [key] of disabled) lines.push(`- \`${key}\` – ohne echte Fotos abgeschaltet.`);
  lines.push('');
  const out = join(ROOT, 'OFFENE_PUNKTE.md');
  const text = lines.join('\n');
  if (!existsSync(out) || readFileSync(out, 'utf8') !== text) writeFileSync(out, text);
  return rows.length;
}

const missing = scanDist();
const count = writeReport(missing);
console.log(`check-content: ${count} fehlende Fotos → OFFENE_PUNKTE.md`);
if (LIVE && missing.size) {
  console.error('\nModus «live» – die Ausgabe enthält noch Foto-Platzhalter.');
  process.exit(1);
}
