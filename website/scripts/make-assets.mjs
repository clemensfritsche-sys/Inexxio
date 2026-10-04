// Erzeugt die statischen Bild-Dateien der Website: Favicons (PNG), Logo-PNG für JSON-LD und
// die vier Open-Graph-Bilder (1200 × 630: Startseite + je Bereich, `og` in Base.astro). Einmalig bzw. nach einem Namens- oder
// Logowechsel laufen lassen; die Ergebnisse liegen versioniert in public/.
//
//   node scripts/make-assets.mjs
//
// Braucht Playwright mit Chromium (nicht als Abhängigkeit der Website – der Build braucht
// es nie). Gesucht wird in PLAYWRIGHT_MODULE oder im globalen npm-Verzeichnis.
import { createRequire } from 'node:module';
import { readFileSync, mkdirSync, writeFileSync, mkdtempSync } from 'node:fs';
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
  { file: 'og/default.png', eyebrow: 'Tuttwil-Wängi TG · seit 1982', title: 'Krantechnik, Fahrzeugtechnik und Sonderlösungen' },
  ...site.areas.map((a) => ({ file: `og/${a.id}.png`, eyebrow: a.label, title: a.ogTitle })),
];

function ogHtml({ eyebrow, title }) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${base}
    body { width: 1200px; height: 630px; background: #F7F6F4; color: #0A0A0B; position: relative; overflow: hidden; }
    .pad { position: absolute; inset: 64px 72px; display: flex; flex-direction: column; }
    .eyebrow { font-size: 20px; font-weight: 600; letter-spacing: .08em; text-transform: uppercase; color: #C8140F; }
    h1 { margin-top: 28px; font-size: 68px; line-height: 1.04; letter-spacing: -0.03em; font-weight: 700; max-width: 960px; }
    /* Signatur des Design-Systems v3: Punktraster, zum Rand hin ausgeblendet; Haarlinie über dem Fuss. */
    .dots { position: absolute; inset: 0; background-image: radial-gradient(circle at 1px 1px, #D1CEC8 1.5px, transparent 0); background-size: 28px 28px;
      -webkit-mask-image: radial-gradient(ellipse at 85% 30%, #000 0%, transparent 65%); }
    .rail { position: absolute; left: 72px; right: 72px; bottom: 170px; height: 1px; background: #D1CEC8; }
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
const browser = await chromium.launch();
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

for (const og of OG) await shot(ogHtml(og), 1200, 630, og.file, true);
await shot(iconHtml(32, 2, 'transparent'), 32, 32, 'favicon-32.png');
await shot(iconHtml(180, 30, '#FFFFFF'), 180, 180, 'apple-touch-icon.png');
await shot(logoHtml, 1200, 600, 'logo/inexxio-ehemals-hs-steiner.png');
await browser.close();
