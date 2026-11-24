// Erzeugt die statischen Bild-Dateien der Website: Favicons (PNG), Logo-PNG für JSON-LD und
// die vier Open-Graph-Bilder (1200 × 630: Startseite + je Bereich, `og` in Base.astro). Einmalig bzw. nach einem Namens- oder
// Logowechsel laufen lassen; die Ergebnisse liegen versioniert in public/.
//
//   node scripts/make-assets.mjs            alles
//   node scripts/make-assets.mjs --icons    nur die Favicons
//
// Braucht Playwright mit Chromium (nicht als Abhängigkeit der Website – der Build braucht
// es nie). Gesucht wird in PLAYWRIGHT_MODULE oder im globalen npm-Verzeichnis; ein eigenes
// Chromium nennt CHROMIUM_PATH.
import { createRequire } from 'node:module';
import { readFileSync, mkdirSync, writeFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { execSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { site } from '../src/config/site.mjs';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const pub = (p) => resolve(root, 'public', p);

function loadPlaywright() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, execSync('npm root -g').toString().trim()].filter(Boolean);
  for (const base of candidates) {
    try {
      return createRequire(`${base}/`)('playwright');
    } catch { /* nächster Kandidat */ }
  }
  throw new Error('Playwright nicht gefunden – PLAYWRIGHT_MODULE auf das node_modules mit «playwright» setzen.');
}

const fontUrl = pathToFileURL(resolve(root, 'src/assets/fonts/inter-latin-wght-normal.woff2')).href;
const favicon = readFileSync(pub('favicon.svg'), 'utf8');
// Das gestapelte Logo trägt «ehemals HS Steiner» selbst – eine Unterzeile daneben wäre doppelt.
const lockup = readFileSync(pub('logo/inexxio-ehemals-hs-steiner.svg'), 'utf8')
  .replace(/\s(width|height)="[^"]*"/g, '')
  .replace(/<title>[\s\S]*?<\/title>/, '');

const base = `
  @font-face { font-family: Inter; src: url('${fontUrl}') format('woff2'); font-weight: 100 900; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Inter, sans-serif; -webkit-font-smoothing: antialiased; }
`;

/** Je Bereich ein Bild – der Dateiname ist die Bereichs-ID (`OgImage` in content/types.ts). */
const OG = [
  { file: 'og/default.png', eyebrow: 'Tuttwil-Wängi TG · seit 1982', title: 'Krane, Fahrmischer und Spezialmaschinen mit Handschlagqualität' },
  ...site.areas.map((a) => ({ file: `og/${a.id}.png`, eyebrow: a.label, title: a.ogTitle })),
];

function ogHtml({ eyebrow, title }) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${base}
    body { width: 1200px; height: 630px; background: #F5F6F7; color: #0A0A0B; position: relative; overflow: hidden; }
    .pad { position: absolute; inset: 64px 72px; display: flex; flex-direction: column; }
    .eyebrow { font-size: 20px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #C8140F; }
    h1 { margin-top: 28px; font-size: 68px; line-height: 1.04; letter-spacing: -0.03em; font-weight: 700; max-width: 960px; }
    /* Signatur des Design-Systems v3: Punktraster, zum Rand hin ausgeblendet; Haarlinie über dem Fuss. */
    .dots { position: absolute; inset: 0; background-image: radial-gradient(circle at 1px 1px, #D0D2D6 1.5px, transparent 0); background-size: 28px 28px;
      -webkit-mask-image: radial-gradient(ellipse at 85% 30%, #000 0%, transparent 65%); }
    .rail { position: absolute; left: 72px; right: 72px; bottom: 170px; height: 1px; background: #D0D2D6; }
    .foot { position: absolute; left: 72px; right: 72px; bottom: 64px; display: flex; align-items: center; justify-content: space-between; }
    .lock svg { display: block; height: 86px; width: auto; }
    .tel { font-size: 30px; font-weight: 600; font-variant-numeric: tabular-nums; }
  </style></head><body>
    <div class="dots"></div>
    <div class="pad"><p class="eyebrow">${eyebrow}</p><h1>${title}</h1></div>
    <div class="rail"></div>
    <div class="foot">
      <div class="lock">${lockup}</div>
      <span class="tel">${site.phone.display}</span>
    </div>
  </body></html>`;
}

const iconHtml = (size, pad, bg) => `<!doctype html><html><head><style>${base}
  body { width: ${size}px; height: ${size}px; background: ${bg}; display: grid; place-items: center; }
  svg { width: ${size - 2 * pad}px; height: ${size - 2 * pad}px; }
</style></head><body>${favicon}</body></html>`;

const logoHtml = `<!doctype html><html><head><style>${base}
  body { width: 1200px; height: 600px; background: #FFFFFF; display: grid; place-items: center; }
  svg { width: 1040px; height: auto; }
</style></head><body>${lockup}</body></html>`;

const { chromium } = loadPlaywright();
const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_PATH || undefined });
const tmp = mkdtempSync(resolve(tmpdir(), 'ix-assets-'));
async function shot(html, w, h, out, needsFont = false) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  // Über eine Datei statt setContent: nur so darf die Seite die lokale Schrift laden.
  const file = resolve(tmp, `${out.replace(/[/.]/g, '_')}.html`);
  writeFileSync(file, html);
  await page.goto(pathToFileURL(file).href, { waitUntil: 'load' });
  await page.evaluate(() => document.fonts.ready);
  const inter = await page.evaluate(() => document.fonts.check('700 40px Inter'));
  if (needsFont && !inter) throw new Error(`Inter wurde für ${out} nicht geladen`);
  mkdirSync(dirname(pub(out)), { recursive: true });
  await page.screenshot({ path: pub(out), omitBackground: false });
  await page.close();
  console.log(`  ${out}`);
}

/** ►► **favicon.ico** – 16, 32 und 48 px in einer Datei (je ein PNG im ICO-Rahmen). Ältere
 *  Browser und Crawler fragen ohne Link nach /favicon.ico; fehlt sie, zeigt Google ein altes. ◄◄ */
function ico(pngs) {
  const head = Buffer.alloc(6 + 16 * pngs.length);
  head.writeUInt16LE(0, 0); head.writeUInt16LE(1, 2); head.writeUInt16LE(pngs.length, 4);
  let offset = head.length;
  pngs.forEach(({ size, data }, i) => {
    const e = 6 + 16 * i;
    head.writeUInt8(size % 256, e); head.writeUInt8(size % 256, e + 1);
    head.writeUInt16LE(1, e + 4); head.writeUInt16LE(32, e + 6);
    head.writeUInt32LE(data.length, e + 8); head.writeUInt32LE(offset, e + 12);
    offset += data.length;
  });
  return Buffer.concat([head, ...pngs.map((p) => p.data)]);
}

if (!process.argv.includes('--icons')) {
  for (const og of OG) await shot(ogHtml(og), 1200, 630, og.file, true);
  await shot(logoHtml, 1200, 600, 'logo/inexxio-ehemals-hs-steiner.png');
}
await shot(iconHtml(32, 0, 'transparent'), 32, 32, 'favicon-32.png');
await shot(iconHtml(180, 30, '#FFFFFF'), 180, 180, 'apple-touch-icon.png');
// Google zeigt in den Treffern ein Icon von mindestens 48 px (ein Vielfaches von 48) – rund
// zugeschnitten, darum mit weissem Grund und Rand wie das Apple-Icon. Dazu favicon.ico. Dasselbe
// für die Testumgebung aus ihrem Zeichen (dev-icons/, der Deploy kopiert es nur auf Staging).
async function forGoogle(svg, dir, pad192, bg192) {
  const html = (size, pad, bg) => iconHtml(size, pad, bg).replace(favicon, svg);
  const at = (f) => (dir ? `../${dir}/${f}` : f);
  await shot(html(192, pad192, bg192), 192, 192, at('favicon-192.png'));
  const sizes = [16, 32, 48];
  for (const s of sizes) await shot(html(s, 0, 'transparent'), s, s, at(`ico-${s}.png`));
  writeFileSync(pub(at('favicon.ico')), ico(sizes.map((size) => ({ size, data: readFileSync(pub(at(`ico-${size}.png`))) }))));
  for (const s of sizes) rmSync(pub(at(`ico-${s}.png`)));
  console.log(`  ${at('favicon.ico')} (16, 32, 48)`);
}
await forGoogle(favicon, '', 28, '#FFFFFF');
await forGoogle(readFileSync(resolve(root, 'dev-icons/favicon.svg'), 'utf8'), 'dev-icons', 0, 'transparent');
await browser.close();
