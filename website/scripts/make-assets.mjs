// Erzeugt die statischen Bild-Dateien der Website: Favicons (PNG), Logo-PNG für JSON-LD und
// die drei Open-Graph-Bilder (1200 × 630). Einmalig bzw. nach einem Namens- oder
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
import { plain } from '../src/lib/text.mjs';

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
const wordmark = readFileSync(pub('logo/inexxio-wortmarke.svg'), 'utf8');

const base = `
  @font-face { font-family: Inter; src: url('${fontUrl}') format('woff2'); font-weight: 100 900; }
  * { margin: 0; box-sizing: border-box; }
  body { font-family: Inter, sans-serif; -webkit-font-smoothing: antialiased; }
`;

const OG = [
  {
    file: 'og/default.png',
    eyebrow: 'Tuttwil-Wängi TG · seit 1982',
    title: 'Kranservice und Fahrmischer-Reparatur für die Ostschweiz',
  },
  {
    file: 'og/krane.png',
    eyebrow: 'Krane · alle Marken',
    title: 'Prüfung, Wartung, Reparatur und Modernisierung von Krananlagen',
  },
  {
    file: 'og/fahrmischer.png',
    eyebrow: 'Fahrmischer · alle gängigen Marken',
    title: 'Service, Reparatur und Trommel-Revision für Fahrmischer',
  },
];

function ogHtml({ eyebrow, title }) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>${base}
    body { width: 1200px; height: 630px; background: #F4F3F0; color: #0A0A0B; position: relative; overflow: hidden; }
    .pad { position: absolute; inset: 64px 72px; display: flex; flex-direction: column; }
    .eyebrow { font-family: ui-monospace, Menlo, monospace; font-size: 22px; letter-spacing: .08em; text-transform: uppercase; color: #6E6E73; }
    h1 { margin-top: 28px; font-size: 68px; line-height: 1.04; letter-spacing: -0.03em; font-weight: 700; max-width: 960px; }
    .rail { position: absolute; left: 72px; right: 72px; bottom: 170px; height: 1px; background: #0A0A0B; }
    .cat { position: absolute; left: 300px; bottom: 164px; width: 13px; height: 13px; background: #E51A14; }
    .foot { position: absolute; left: 72px; right: 72px; bottom: 64px; display: flex; align-items: center; justify-content: space-between; }
    .lock { display: flex; align-items: center; gap: 22px; }
    .lock svg { height: 40px; width: auto; }
    .lock .t { border-left: 1px solid #D7D4CC; padding-left: 22px; display: grid; gap: 6px; }
    .lock .d { font-size: 17px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; }
    .lock .f { font-size: 19px; color: #6E6E73; }
    .tel { font-size: 30px; font-weight: 650; font-variant-numeric: tabular-nums; }
  </style></head><body>
    <div class="pad"><p class="eyebrow">${eyebrow}</p><h1>${title}</h1></div>
    <div class="rail"></div><div class="cat"></div>
    <div class="foot">
      <div class="lock">${wordmark}<div class="t"><span class="d">${plain(site.brand.descriptor)}</span><span class="f">${plain(site.brand.formerly)}</span></div></div>
      <span class="tel">${site.phone.display}</span>
    </div>
  </body></html>`;
}

const iconHtml = (size, pad, bg) => `<!doctype html><html><head><style>${base}
  body { width: ${size}px; height: ${size}px; background: ${bg}; display: grid; place-items: center; }
  svg { width: ${size - 2 * pad}px; height: ${size - 2 * pad}px; }
</style></head><body>${favicon}</body></html>`;

const logoHtml = `<!doctype html><html><head><style>${base}
  body { width: 1200px; height: 240px; background: #FFFFFF; display: grid; place-items: center; }
  svg { width: 1040px; height: auto; }
</style></head><body>${wordmark}</body></html>`;

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
await shot(logoHtml, 1200, 240, 'logo/inexxio-wortmarke.png');
await browser.close();
