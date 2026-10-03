// Beispielbilder aus Wikimedia Commons holen – ein Werkzeug für die Zeit, bis echte Fotos da sind.
//
// Läuft in GitHub Actions (.github/workflows/sample-photos.yml), weil die Arbeitsumgebung
// keinen Zugang zu Bildquellen hat. Zwei Schritte, gesteuert über
// scripts/sample-photos.request.json:
//
//   search  Je Bildstelle bis zu 8 Kandidaten suchen (nur freie Lizenzen: CC0, gemeinfrei,
//           CC BY, CC BY-SA) und je Stelle einen Kontaktbogen schreiben
//           (scripts/.sample-review/<id>.jpg + candidates.json). Ein Mensch – oder Claude –
//           schaut sie an und wählt.
//   fetch   Die gewählten Dateien in voller Grösse (lange Seite 2400 px) nach
//           src/assets/photos/samples/<id>.jpg holen und den Bildnachweis nach
//           scripts/.sample-review/credits.json schreiben.
//
// Commons statt Openverse: eine Anfrage je Stelle liefert Vorschaubild, Masse und Lizenz
// zugleich, und es gibt keine enge Anfragegrenze für anonyme Nutzer.

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';

const here = dirname(fileURLToPath(import.meta.url));
const REQUEST = resolve(here, 'sample-photos.request.json');
const REVIEW = resolve(here, '.sample-review');
const OUT = resolve(here, '../src/assets/photos/samples');
const API = 'https://commons.wikimedia.org/w/api.php';
const UA = 'InexxioWebsite-SamplePhotos/1.0 (https://inexxio-dev.web.app; build tool)';
const FREE = /^(CC0|Public domain|PD|CC BY(?:-SA)? \d)/i;

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const strip = (html = '') => html.replace(/<[^>]*>/g, ' ').replace(/\s+/g, ' ').trim();

async function api(params) {
  const url = `${API}?${new URLSearchParams({ format: 'json', formatversion: '2', ...params })}`;
  for (let i = 0; i < 4; i++) {
    const res = await fetch(url, { headers: { 'User-Agent': UA } });
    if (res.ok) return res.json();
    await sleep(2000 * (i + 1));
  }
  throw new Error(`Commons antwortet nicht: ${url}`);
}

async function download(url) {
  for (let i = 0; i < 4; i++) {
    const res = await fetch(url, { headers: { 'User-Agent': UA } });
    if (res.ok) return Buffer.from(await res.arrayBuffer());
    await sleep(2000 * (i + 1));
  }
  throw new Error(`Download fehlgeschlagen: ${url}`);
}

function info(page) {
  const ii = page.imageinfo?.[0];
  if (!ii) return null;
  const m = ii.extmetadata ?? {};
  return {
    file: page.title,
    width: ii.width,
    height: ii.height,
    mime: ii.mime,
    thumb: ii.thumburl,
    page: ii.descriptionurl,
    license: m.LicenseShortName?.value ?? '',
    licenseUrl: m.LicenseUrl?.value ?? '',
    author: strip(m.Artist?.value) || 'unbekannt',
    description: strip(m.ImageDescription?.value).slice(0, 200),
  };
}

async function candidates(query, portrait) {
  const data = await api({
    action: 'query', generator: 'search', gsrnamespace: '6', gsrlimit: '30',
    gsrsearch: `filetype:bitmap ${query}`,
    prop: 'imageinfo', iiprop: 'url|size|mime|extmetadata', iiurlwidth: '480',
    iiextmetadatafilter: 'LicenseShortName|LicenseUrl|Artist|ImageDescription',
  });
  return (data.query?.pages ?? [])
    .map(info)
    .filter((c) => c && c.mime === 'image/jpeg' && FREE.test(c.license))
    .filter((c) => Math.max(c.width, c.height) >= 1400)
    .filter((c) => (portrait ? c.height > c.width : c.width >= c.height));
}

/** Ein Kontaktbogen je Stelle: 4 × 2 Felder, nummeriert. */
async function sheet(id, list) {
  const W = 360, H = 270, LABEL = 26, cols = 4;
  const rows = Math.ceil(list.length / cols) || 1;
  const tiles = await Promise.all(list.map(async (c, i) => {
    const img = await sharp(await download(c.thumb)).resize(W, H, { fit: 'cover' }).jpeg().toBuffer();
    const label = Buffer.from(`<svg width="${W}" height="${LABEL}"><rect width="100%" height="100%" fill="#0A0A0B"/>` +
      `<text x="8" y="18" font-family="DejaVu Sans, sans-serif" font-size="14" fill="#fff">${i + 1} · ${c.license.replace(/&/g, '&amp;')}</text></svg>`);
    return [
      { input: img, left: (i % cols) * W, top: Math.floor(i / cols) * (H + LABEL) },
      { input: label, left: (i % cols) * W, top: Math.floor(i / cols) * (H + LABEL) + H },
    ];
  }));
  await sharp({ create: { width: cols * W, height: rows * (H + LABEL), channels: 3, background: '#ffffff' } })
    .composite(tiles.flat()).jpeg({ quality: 78 }).toFile(resolve(REVIEW, `${id}.jpg`));
}

async function search(slots) {
  mkdirSync(REVIEW, { recursive: true });
  const all = {};
  for (const [id, { q, portrait = false }] of Object.entries(slots)) {
    const seen = new Set();
    const list = [];
    for (const query of q) {
      for (const c of await candidates(query, portrait)) {
        if (!seen.has(c.file) && list.length < 8) { seen.add(c.file); list.push(c); }
      }
      await sleep(400);
      if (list.length >= 8) break;
    }
    all[id] = list;
    if (list.length) await sheet(id, list);
    console.log(`${id}: ${list.length} Kandidaten`);
  }
  writeFileSync(resolve(REVIEW, 'candidates.json'), `${JSON.stringify(all, null, 2)}\n`);
}

async function fetchChosen(choose) {
  mkdirSync(OUT, { recursive: true });
  mkdirSync(REVIEW, { recursive: true });
  const credits = {};
  for (const [id, file] of Object.entries(choose)) {
    const data = await api({
      action: 'query', titles: file, prop: 'imageinfo', iiprop: 'url|size|mime|extmetadata',
      iiurlwidth: '2400', iiextmetadatafilter: 'LicenseShortName|LicenseUrl|Artist|ImageDescription',
    });
    const c = info(data.query.pages[0]);
    if (!c || !FREE.test(c.license)) throw new Error(`${id}: ${file} – keine freie Lizenz (${c?.license})`);
    const src = c.width > 2400 || c.height > 2400 ? c.thumb : (await api({
      action: 'query', titles: file, prop: 'imageinfo', iiprop: 'url',
    })).query.pages[0].imageinfo[0].url;
    await sharp(await download(src)).rotate().resize(2400, 2400, { fit: 'inside', withoutEnlargement: true })
      .jpeg({ quality: 82, mozjpeg: true }).toFile(resolve(OUT, `${id}.jpg`));
    credits[id] = { file: c.file, author: c.author, license: c.license, licenseUrl: c.licenseUrl, page: c.page, description: c.description };
    console.log(`${id}: ${c.file} (${c.license})`);
    await sleep(400);
  }
  writeFileSync(resolve(REVIEW, 'credits.json'), `${JSON.stringify(credits, null, 2)}\n`);
}

const req = JSON.parse(readFileSync(REQUEST, 'utf8'));
if (req.mode === 'search') await search(req.slots);
else if (req.mode === 'fetch') await fetchChosen(req.choose);
else throw new Error(`Unbekannter Modus «${req.mode}» in ${REQUEST}`);
