// ►►► Prüfskript für offene Punkte. ◄◄◄
//
//   node scripts/check-content.mjs --sources   Quellen (src/) und Konfiguration prüfen
//   node scripts/check-content.mjs --dist      Build-Ausgabe prüfen und OFFENE_PUNKTE.md schreiben
//
// Findet alle Markierungen [[PLATZHALTER: …]] und [[PRÜFEN: …]] – in den Quellen mit
// Datei und Zeile, in der Ausgabe mit Seite und Stelle (nächste Überschrift davor) – und
// alle Bildstellen ohne echtes Foto.
//
// Modus «preview» (Standard): Bericht, Exit 0.
// Modus «live":               jede Markierung ist ein Fehler, Exit 1 – der Build bricht ab.
import { existsSync, readdirSync, readFileSync, statSync, writeFileSync } from 'node:fs';
import { dirname, extname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { site } from '../src/config/site.mjs';
import { photos } from '../src/config/photos.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const args = new Set(process.argv.slice(2));
const LIVE = (process.env.SITE_MODE ?? 'preview') === 'live';
const MARKER = /\[\[(PLATZHALTER|PRÜFEN):\s*([^\]]*?)\s*\]\]/g;
/** Erklärende Beispiele der Syntax («[[PLATZHALTER: …]]») sind keine offenen Punkte. */
const isExample = (note) => /^(…|\.\.\.)$/.test(note.trim());

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

const clean = (html) => html.replace(/<[^>]+>/g, '').replace(/&amp;/g, '&').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/\s+/g, ' ').trim();

// ---------------------------------------------------------------- Quellen
function scanSources() {
  const files = walk(join(ROOT, 'src'), ['.astro', '.ts', '.mjs', '.md'])
    .filter((f) => !f.endsWith(join('lib', 'text.mjs')));
  const found = [];
  for (const file of files) {
    readFileSync(file, 'utf8').split('\n').forEach((line, i) => {
      for (const m of line.matchAll(MARKER)) {
        if (isExample(m[2])) continue;
        found.push({ kind: m[1], note: m[2], where: `${relative(ROOT, file)}:${i + 1}` });
      }
    });
  }
  return found;
}

// ---------------------------------------------------------------- Ausgabe
function pageOf(file, dist) {
  const rel = relative(dist, file).replace(/\\/g, '/');
  if (rel === 'index.html') return '/';
  if (rel.endsWith('.html')) return `/${rel.slice(0, -5)}`;
  return `/${rel}`;
}

function scanDist() {
  const dist = join(ROOT, 'dist');
  if (!existsSync(dist)) throw new Error('dist/ fehlt – zuerst bauen (npm run build).');
  const markers = [];
  const missingPhotos = new Map();
  for (const file of walk(dist, ['.html', '.txt', '.xml', '.json'])) {
    const text = readFileSync(file, 'utf8');
    const page = pageOf(file, dist);
    const headings = [...text.matchAll(/<h([1-3])[^>]*>([\s\S]*?)<\/h\1>/g)].map((h) => ({ at: h.index, text: clean(h[2]) }));
    const spotOf = (at) => headings.filter((h) => h.at <= at).pop()?.text ?? '(Kopf/Seitenanfang)';
    // Sichtbar gemachte Markierungen (Modus preview)
    for (const m of text.matchAll(/<span class="mk mk--(ph|check)"><span class="mk__label">[^<]*<\/span>\s*([\s\S]*?)<\/span>/g)) {
      markers.push({ kind: m[1] === 'ph' ? 'PLATZHALTER' : 'PRÜFEN', note: clean(m[2]), page, spot: spotOf(m.index) });
    }
    // Rohe Markierungen (Attribute, Meta, JSON-LD, Textdateien)
    for (const m of text.matchAll(MARKER)) {
      if (isExample(m[2])) continue;
      markers.push({ kind: m[1], note: m[2], page, spot: extname(file) === '.html' ? `${spotOf(m.index)} (Attribut/Meta)` : extname(file) });
    }
    for (const m of text.matchAll(/data-photo-missing="([^"]+)"/g)) {
      if (!missingPhotos.has(m[1])) missingPhotos.set(m[1], new Set());
      missingPhotos.get(m[1]).add(page);
    }
  }
  return { markers, missingPhotos };
}

// ---------------------------------------------------------------- Einordnung
const DECISION = /zusatz zum markennamen|logo|domain|e-mail-adresse|adresse für bewerbungen|pikett|antwortzeit|reaktionszeit|zusagen|abo-stufen|stufennamen|preis|teileliste|analytics|whatsapp|handelsregister|uid\b/i;
const EXPERT = /fachlich|rechtlich/i;

function category(note) {
  if (EXPERT.test(note)) return 'Fachlich/Rechtlich';
  if (DECISION.test(note)) return 'Entscheidungen';
  return 'Inhalte und Freigaben';
}

function merge(sourceMarkers, distMarkers) {
  const byKey = new Map();
  const key = (m) => `${m.kind}|${m.note}`;
  for (const m of distMarkers) {
    const k = key(m);
    if (!byKey.has(k)) byKey.set(k, { kind: m.kind, note: m.note, pages: new Map(), sources: new Set() });
    const e = byKey.get(k);
    if (!e.pages.has(m.page)) e.pages.set(m.page, m.spot);
  }
  for (const m of sourceMarkers) {
    const k = key(m);
    if (!byKey.has(k)) byKey.set(k, { kind: m.kind, note: m.note, pages: new Map(), sources: new Set() });
    byKey.get(k).sources.add(m.where);
  }
  return [...byKey.values()];
}

const esc = (s) => String(s).replace(/\|/g, '\\|');

function where(entry) {
  const pages = [...entry.pages.entries()];
  if (pages.length > 6) return `alle Seiten (${pages.length}) – Kopf, Fuss oder Ankündigung`;
  if (pages.length) return pages.map(([p, spot]) => `\`${p}\` – ${spot}`).join('<br>');
  return [...entry.sources].map((s) => `Konfiguration \`${s}\``).join('<br>');
}

function writeReport(entries, missingPhotos) {
  const groups = { Entscheidungen: [], 'Inhalte und Freigaben': [], 'Fachlich/Rechtlich': [] };
  for (const e of entries) groups[category(e.note)].push(e);
  const photoRows = Object.entries(photos)
    .filter(([, p]) => !p.file)
    .map(([id, p]) => ({ id, p, pages: [...(missingPhotos.get(id) ?? [])] }));
  const disabled = Object.entries(site.features).filter(([, on]) => on === false);
  const DISABLED_TEXT = {
    references: 'Referenzkunden – nur mit schriftlicher Freigabe der Kunden.',
    beforeAfter: 'Vorher/Nachher-Regler (Modernisierung) – braucht echte Fotopaare.',
    team: 'Team auf «Über uns» – Namen und Fotos nur mit Einverständnis.',
    jobPosting: 'Stelleninserat «Servicetechniker/in Krane und Fahrmischer» – Text und Konditionen fehlen.',
    whatsapp: 'WhatsApp-Kontakt – Entscheidung offen.',
  };

  const lines = [
    '# Offene Punkte – Website INEXXIO (ehemals HS Steiner)',
    '',
    '> Generiert von `npm run check:content` (bzw. nach jedem `npm run build`). Nicht von Hand ändern –',
    '> die Markierung an der Fundstelle erledigen, dann verschwindet die Zeile von selbst.',
    '> Solange hier etwas steht, bricht ein Build im Modus `live` ab.',
    '',
    `**Stand:** ${groups.Entscheidungen.length} Entscheidungen · ${groups['Inhalte und Freigaben'].length} Inhalte und Freigaben · ` +
      `${photoRows.length} Fotos · ${groups['Fachlich/Rechtlich'].length} fachlich/rechtlich · ${disabled.length} abgeschaltete Sektionen`,
    '',
  ];
  for (const [title, list] of Object.entries(groups)) {
    lines.push(`## ${title}`, '', '| Was gebraucht wird | Art | Wo |', '|---|---|---|');
    for (const e of list.sort((a, b) => a.note.localeCompare(b.note, 'de'))) {
      lines.push(`| ${esc(e.note)} | ${e.kind === 'PRÜFEN' ? 'Prüfen' : 'Platzhalter'} | ${where(e)} |`);
    }
    lines.push('');
  }
  lines.push('## Fotos', '', 'Empfehlung: ein professioneller Fototag – der grösste Hebel für die Qualität der Seite.', '');
  lines.push('| Foto | Beschreibung für den Fototag | Format | Verwendet auf |', '|---|---|---|---|');
  for (const { id, p, pages } of photoRows) {
    lines.push(`| \`${id}\` | ${esc(p.brief)} | ${p.ratio.replace('/', ':')} | ${pages.length ? pages.map((x) => `\`${x}\``).join(', ') : p.feature ? `abgeschaltete Sektion \`${p.feature}\`` : 'noch nicht verwendet'} |`);
  }
  lines.push('', '## Abgeschaltete Sektionen (`enabled: false` in `src/config/site.mjs`)', '');
  for (const [key] of disabled) lines.push(`- \`${key}\` – ${DISABLED_TEXT[key] ?? 'ohne echten Inhalt abgeschaltet.'}`);
  lines.push('');

  const out = join(ROOT, 'OFFENE_PUNKTE.md');
  const text = lines.join('\n');
  if (!existsSync(out) || readFileSync(out, 'utf8') !== text) writeFileSync(out, text);
  return { groups, photoRows };
}

// ---------------------------------------------------------------- Ablauf
const doSources = args.has('--sources') || args.size === 0;
const doDist = args.has('--dist');
const sourceMarkers = doSources || doDist ? scanSources() : [];
let failed = false;

if (doSources) {
  console.log(`check-content: ${sourceMarkers.length} Markierungen in den Quellen`);
  if (LIVE && sourceMarkers.length) {
    console.error('\nModus «live» – offene Markierungen:');
    for (const m of sourceMarkers) console.error(`  ${m.where}  [[${m.kind}: ${m.note}]]`);
    failed = true;
  }
}

if (doDist) {
  const { markers, missingPhotos } = scanDist();
  const entries = merge(sourceMarkers, markers);
  const { photoRows } = writeReport(entries, missingPhotos);
  console.log(`check-content: ${entries.length} offene Punkte, ${photoRows.length} fehlende Fotos → OFFENE_PUNKTE.md`);
  if (LIVE && (markers.length || missingPhotos.size)) {
    console.error('\nModus «live» – die Ausgabe enthält noch Markierungen oder Foto-Platzhalter.');
    failed = true;
  }
}

if (failed) process.exit(1);
