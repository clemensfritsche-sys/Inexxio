// ►►► Prüft die fertige Website (dist/) – läuft nach jedem Build (postbuild). ◄◄◄
//
//   node scripts/check-site.mjs
//
// Bricht ab (Exit 1) bei: kaputten internen Links und Ankern, ungültigem oder
// unvollständigem JSON-LD, Titel > 60 Zeichen, nicht genau einer H1, übersprungenen
// Überschriften-Ebenen, Bildern ohne Alt-Text, mehr als drei Kranbahn-Linien, verbotenen
// Wörtern (Kapitel 8.2), Sitemap/robots.txt/llms.txt im falschen Zustand, Weiterleitungen
// ins Leere (../firebase.json), Dateien auf ERP-Pfaden und überschrittenem Leistungsbudget.
// Warnt bei Meta-Descriptions ausserhalb 140–155 Zeichen.
//
// Bewusst ohne HTML-Parser-Abhängigkeit: geprüft wird die eigene, generierte Ausgabe.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { site } from '../src/config/site.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(ROOT, 'dist');
const LIVE = (process.env.SITE_MODE ?? 'preview') === 'live';
const SITE_URL = (process.env.SITE_URL ?? 'http://localhost:4321').replace(/\/+$/, '');
/** Pfade, die das ERP auf derselben Domain ausliefert – Links dorthin sind gültig. */
const ERP_PATHS = ['/login', '/agb', '/konto', '/erp', '/abmelden'];
/** Leistungsbudget (Kapitel 15), in Bytes gzip bzw. roh. */
const BUDGET = { jsGzip: 30 * 1024, cssGzip: 40 * 1024, fonts: 120 * 1024, home: 1024 * 1024 };
/** Kapitel 8.2 – im sichtbaren Text verboten (klein geschrieben verglichen). */
const FORBIDDEN = [
  'innovativ', 'ganzheitlich', 'massgeschneidert', 'maßgeschneidert', 'ihr zuverlässiger partner',
  'lösungen aus einer hand', 'höchste qualität', 'leidenschaft', 'mehrwert', 'state of the art',
  'synergie', 'exzellenz', 'revolutionär', 'nahtlos', 'im herzen von', 'herzlich willkommen',
  'pikett',
];
/**
 * Alte hs-steiner.ch-Pfade (Auftrag Kap. 14) → das Ziel, das die Tabelle verlangt. Jeder muss
 * die ERSTE passende Regel in ../firebase.json treffen (Firebase nimmt die erste) – oder es
 * gibt die Seite unter demselben Pfad (/kontakt).
 */
const OLD_URLS = {
  '/heuentnahmekran': '/krantechnik/heukrananlagen',
  '/heuentnahmekran/Einschienen-Kran': '/krantechnik/heukrananlagen',
  '/heuentnahmekran/drehkran-hydraulisch': '/krantechnik/heukrananlagen',
  '/heuentnahmekran/bruecken-kran': '/krantechnik/heukrananlagen',
  '/heuentnahmekran/bilder-gallerie': '/krantechnik/heukrananlagen',
  '/heuentnahmekran/pdf-prospekte': '/krantechnik/heukrananlagen',
  '/heuentnahmekran/Kran-dem-Gebäude-Angepasst': '/krantechnik/industriekrane',
  '/heuentnahmekran/Kran-dem-Geb%C3%A4ude-Angepasst': '/krantechnik/industriekrane',
  '/heuentnahmekran/matagematerial': '/krantechnik/pruefung-wartung',
  '/betonfordertechnik': '/fahrzeugtechnik/fahrmischer',
  '/betonfordertechnik/Betonfahrmischer': '/fahrzeugtechnik/fahrmischer',
  '/betonfordertechnik/fahrmischerpumpen': '/fahrzeugtechnik/fahrmischer',
  '/betonfordertechnik/service-und-reparaturen': '/fahrzeugtechnik/fahrmischer',
  '/betonfordertechnik/bilder': '/fahrzeugtechnik/fahrmischer',
  '/betonfordertechnik/Euro-Kpper': '/fahrzeugtechnik/aufbauten-reparatur',
  '/betonfordertechnik/verschleissteile': '/fahrzeugtechnik/verschleiss-ersatzteile',
  '/antrieb-und-steuerung': '/krantechnik/modernisierung',
  '/antrieb-und-steuerung/elektrosteuerung': '/krantechnik/modernisierung',
  '/baumaschinen': '/sonderloesungen/baumaschinen',
  '/baumaschinen/reparaturen': '/sonderloesungen/baumaschinen',
  '/wahrschaftes': '/sonderloesungen/schweiss-stahlbau',
  '/wahrschaftes/stahlbau': '/sonderloesungen/schweiss-stahlbau',
  '/wahrschaftes/Gelaender-und-Verglasung': '/uebergabe',
  '/sachtransporter-anhanger/Reparaturen': '/fahrzeugtechnik/aufbauten-reparatur',
  '/sachtransporter-anhanger': '/uebergabe',
  '/sachtransporter-anhanger/aufbau': '/uebergabe',
  '/forst-und-landwirtschaft': '/krantechnik/heukrananlagen',
  '/forst-und-landwirtschaft/heukrane': '/krantechnik/heukrananlagen',
  '/haus-und-garten': '/uebergabe',
  '/haus-und-garten/rasenmaeher': '/uebergabe',
  '/kleintransporter-pw': '/uebergabe',
  '/kleintransporter-pw/reifenservice': '/uebergabe',
  '/hebebuhnen': '/uebergabe',
  '/Camping': '/uebergabe',
  '/unsere-einsatzorte': '/ueber-uns',
  '/unsere-einsatzorte/ch-schweiz': '/ueber-uns',
  '/application/files/7615/1234/prospekt.pdf': '/krantechnik/heukrananlagen',
  '/kontakt': '/kontakt',
};
/** Seiten der ersten Fassung (03.10.2026), die es nicht mehr gibt – nirgends ein Link, keine Datei. */
const REMOVED = [
  '/krane', '/krane/pruefung-wartung', '/krane/reparatur', '/krane/modernisierung', '/krane/hs-krananlagen',
  '/fahrmischer', '/fahrmischer/service-reparatur', '/fahrmischer/verschleissteile', '/service-abo',
  '/einsatzgebiet', '/ratgeber/kranfachmann-kranexperte', '/ratgeber/heukran-saison-check',
];

const errors = [];
const warnings = [];
const fail = (where, msg) => errors.push(`${where}: ${msg}`);
const warn = (where, msg) => warnings.push(`${where}: ${msg}`);

// ---------------------------------------------------------------- Hilfen
function walk(dir) {
  const out = [];
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else out.push(p);
  }
  return out;
}

const decode = (s) =>
  s.replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n))
    .replace(/&#x([0-9a-f]+);/gi, (_, n) => String.fromCodePoint(parseInt(n, 16)))
    .replace(/&nbsp;/g, ' ').replace(/&lt;/g, '<').replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');

/** Sichtbarer Text: ohne Skripte, Styles, Kommentare und Tags. */
const visibleText = (html) =>
  decode(html.replace(/<script[\s\S]*?<\/script>/g, ' ').replace(/<style[\s\S]*?<\/style>/g, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ').replace(/<[^>]+>/g, ' ')).replace(/\s+/g, ' ').trim();

const attr = (tag, name) => decode(new RegExp(`\\s${name}="([^"]*)"`).exec(tag)?.[1] ?? '');
const pathOf = (file) => {
  const rel = relative(DIST, file).replace(/\\/g, '/').replace(/\.html$/, '');
  return rel === 'index' ? '/' : `/${rel.replace(/\/index$/, '')}`;
};
const urlOf = (path) => (path === '/' ? `${SITE_URL}/` : `${SITE_URL}${path}`);

/** Datei in dist/ zu einem Pfad – so, wie Firebase Hosting mit cleanUrls ausliefert. */
function fileFor(path) {
  if (path === '/') return join(DIST, 'index.html');
  const p = join(DIST, decodeURI(path));
  for (const c of [p, `${p}.html`, join(p, 'index.html')]) if (existsSync(c) && statSync(c).isFile()) return c;
  return null;
}

// ---------------------------------------------------------------- Einlesen
if (!existsSync(DIST)) {
  console.error('check-site: dist/ fehlt – zuerst bauen (npm run build).');
  process.exit(1);
}
const files = walk(DIST);
const pages = files.filter((f) => f.endsWith('.html')).map((file) => {
  const html = readFileSync(file, 'utf8');
  const main = /<main[\s\S]*?<\/main>/.exec(html)?.[0] ?? '';
  return {
    file, html, path: pathOf(file), main,
    ids: new Set([...html.matchAll(/\sid="([^"]+)"/g)].map((m) => decode(m[1]))),
    noindex: /<meta name="robots" content="noindex/.test(html),
  };
});
const byPath = new Map(pages.map((p) => [p.path, p]));

// ---------------------------------------------------------------- Kopf, Überschriften, Bilder
function checkHead(p) {
  const title = [...p.html.matchAll(/<title>([\s\S]*?)<\/title>/g)].map((m) => decode(m[1]).trim());
  if (title.length !== 1) fail(p.path, `${title.length} <title> statt genau einem`);
  else if (title[0].length > 60) fail(p.path, `Titel hat ${title[0].length} Zeichen (höchstens 60): «${title[0]}»`);
  if (!/<html lang="de-CH"/.test(p.html)) fail(p.path, 'lang="de-CH" fehlt');
  const desc = attr(/<meta name="description"[^>]*>/.exec(p.html)?.[0] ?? '', 'content');
  if (!desc) fail(p.path, 'Meta-Description fehlt');
  else if (INDEXED.has(p.path) && (desc.length < 140 || desc.length > 155)) {
    warn(p.path, `Meta-Description hat ${desc.length} Zeichen (Ziel 140–155)`);
  }
  const canonical = attr(/<link rel="canonical"[^>]*>/.exec(p.html)?.[0] ?? '', 'href');
  if (canonical !== urlOf(p.path) && p.path !== '/404') fail(p.path, `canonical «${canonical}» ≠ «${urlOf(p.path)}»`);
  for (const prop of ['og:title', 'og:description', 'og:image', 'og:url']) {
    if (!new RegExp(`<meta property="${prop}" content="[^"]+"`).test(p.html)) fail(p.path, `${prop} fehlt`);
  }
  // Ein Bild, auf das Meta-Angaben oder JSON-LD mit voller Adresse zeigen (og:image, Logo),
  // muss es geben – ein fehlendes fällt sonst erst auf, wenn jemand die Seite teilt.
  const own = new RegExp(`${SITE_URL.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(/[^"\\s]+\\.(?:png|jpe?g|webp|avif|svg))`, 'g');
  for (const m of p.html.matchAll(own)) {
    if (!existsSync(join(DIST, m[1]))) fail(p.path, `Bild fehlt in dist: ${m[1]}`);
  }
  const robots = attr(/<meta name="robots"[^>]*>/.exec(p.html)?.[0] ?? '', 'content');
  if (!LIVE && robots !== 'noindex, nofollow') fail(p.path, `Modus preview, aber robots «${robots}»`);
  return title[0] ?? '';
}

function checkHeadings(p) {
  const h1 = (p.html.match(/<h1[\s>]/g) ?? []).length;
  if (h1 !== 1) fail(p.path, `${h1} H1 statt genau einer`);
  let last = 0;
  for (const m of p.html.matchAll(/<h([1-6])[\s>]/g)) {
    const level = Number(m[1]);
    if (last && level > last + 1) fail(p.path, `Überschrift springt von H${last} auf H${level}`);
    last = level;
  }
  for (const m of p.html.matchAll(/<img\b[^>]*>/g)) if (!/\salt="/.test(m[0])) fail(p.path, `Bild ohne alt: ${m[0].slice(0, 80)}`);
  for (const m of p.html.matchAll(/<svg\b[^>]*role="img"[^>]*>/g)) {
    if (!/aria-label(ledby)?="/.test(m[0])) fail(p.path, 'SVG mit role="img" ohne Beschriftung');
  }
  const kranbahn = (p.html.match(/data-kranbahn/g) ?? []).length;
  if (kranbahn > 3) fail(p.path, `${kranbahn} Kranbahn-Linien (höchstens 3)`);
  // Die mobile Aktionsleiste erscheint, sobald der Seitenkopf aus dem Bild ist (mobilebar.ts).
  // Markiert war einmal der ganze Artikel – dann kam sie erst am Seitenende.
  const heroes = [...p.html.matchAll(/<([a-z0-9]+)\b[^>]*\sdata-hero(?=[\s>=])/g)];
  if (heroes.length !== 1) fail(p.path, `${heroes.length} Seitenköpfe (data-hero) statt genau einem`);
  else if (['article', 'main', 'body'].includes(heroes[0][1])) {
    fail(p.path, `data-hero an <${heroes[0][1]}> – gemeint ist der Seitenkopf (H1 und erste Handlung), nicht der ganze Inhalt`);
  } else if (p.html.indexOf('<h1', heroes[0].index) < 0) {
    fail(p.path, 'die H1 steht vor dem Seitenkopf (data-hero)');
  }
}

/** Kapitel 8.1/8.2: verbotene Wörter, Ausrufezeichen, Emojis, ß – und die erste Nennung. */
function checkWords(where, text) {
  const lower = text.toLowerCase();
  for (const w of FORBIDDEN) if (lower.includes(w)) fail(where, `verbotenes Wort «${w}»`);
  const bang = /[^\s]![^=]|!$/.exec(text);
  if (bang) fail(where, `Ausrufezeichen: «…${text.slice(Math.max(0, bang.index - 30), bang.index + 2)}»`);
  // Emoji-Darstellung, nicht «Pictographic»: ©, ® und ™ sind Satzzeichen, keine Emojis.
  const emoji = /\p{Emoji_Presentation}|\uFE0F/u.exec(text);
  if (emoji) fail(where, `Emoji im Text: «${emoji[0]}»`);
  if (text.includes('ß')) fail(where, '«ß» statt «ss» (Schweizer Rechtschreibung)');
}

/** Rechtstexte nennen zuerst die Rechtsperson – dort gilt die Regel nicht. */
const LEGAL = new Set(['/impressum', '/datenschutz']);

function checkFirstMention(p) {
  if (LEGAL.has(p.path)) return;
  const text = visibleText(p.main);
  const first = text.indexOf(site.brand.name);
  if (first === -1) return;
  const full = `${site.brand.name} (${site.brand.formerly})`;
  const legal = `${site.brand.legalName} (${site.brand.formerly})`;
  // «Aus HS Steiner wird INEXXIO» sagt dasselbe – die alte Firma steht unmittelbar davor.
  const before = text.slice(Math.max(0, first - 30), first);
  const at = (s) => text.slice(first, first + s.length) === s;
  if (!at(full) && !at(legal) && !before.includes('HS Steiner')) {
    warn(p.path, `erste Nennung im Inhalt ist «${text.slice(first, first + full.length + 5)}…» statt «${full}»`);
  }
}

// ---------------------------------------------------------------- Links und Anker
function checkTarget(p, href, kind) {
  if (/^(https?:)?\/\//.test(href)) return;
  if (href.startsWith('tel:')) {
    if (!/^tel:\+41\d{9}$/.test(href)) fail(p.path, `Telefon-Link «${href}» nicht im Format +41…`);
    return;
  }
  if (href.startsWith('mailto:')) {
    if (!/^mailto:[^@\s?]+@[^@\s?]+\.[a-z]{2,}/i.test(href)) fail(p.path, `mailto-Link «${href.slice(0, 60)}» ohne gültige Adresse`);
    return;
  }
  if (href.startsWith('data:')) return;
  const [path, hash] = href.split('#');
  const target = path === '' ? p : null;
  if (target && hash) {
    if (!p.ids.has(decodeURIComponent(hash))) fail(p.path, `Anker «#${hash}» fehlt auf der Seite`);
    return;
  }
  if (!path.startsWith('/')) return fail(p.path, `relativer ${kind} «${href}» – bitte absolut (/…)`);
  if (path.startsWith('/api/')) return;
  const bare = path.split('?')[0];
  if (ERP_PATHS.some((e) => bare === e || bare.startsWith(`${e}/`))) return;
  const clean = bare.replace(/\/$/, '') || '/';
  const file = fileFor(clean);
  if (!file) return fail(p.path, `${kind} ins Leere: «${href}»`);
  if (hash && file.endsWith('.html')) {
    const tp = byPath.get(pathOf(file));
    if (tp && !tp.ids.has(decodeURIComponent(hash))) fail(p.path, `Anker «${href}» fehlt auf ${tp.path}`);
  }
}

function checkLinks(p) {
  for (const m of p.html.matchAll(/<a\b[^>]*\shref="([^"]*)"/g)) checkTarget(p, decode(m[1]), 'Link');
  for (const m of p.html.matchAll(/<(?:img|script|source)\b[^>]*\ssrc="([^"]*)"/g)) checkTarget(p, decode(m[1]), 'Datei');
  for (const m of p.html.matchAll(/<link\b[^>]*\shref="([^"]*)"/g)) {
    if (!/rel="canonical"/.test(m[0])) checkTarget(p, decode(m[1]), 'Datei');
  }
  for (const m of p.html.matchAll(/<form\b[^>]*\saction="([^"]*)"/g)) {
    if (decode(m[1]) !== '/api/v1/contact') fail(p.path, `Formular schickt an «${m[1]}»`);
  }
}

// ---------------------------------------------------------------- JSON-LD
const has = (o, path) => path.split('.').reduce((v, k) => (v == null ? undefined : v[k]), o) != null;
const REQUIRED = {
  Organization: ['name', 'url', 'telephone', 'address.streetAddress', 'address.postalCode', 'address.addressLocality', 'address.addressCountry', 'geo.latitude', 'foundingDate', 'founder.name'],
  WebSite: ['name', 'url'],
  BreadcrumbList: ['itemListElement'],
  FAQPage: ['mainEntity'],
  Service: ['name', 'serviceType', 'provider'],
  Article: ['headline', 'datePublished', 'dateModified', 'author.name'],
  Person: ['name'],
  JobPosting: ['title', 'description', 'datePosted', 'hiringOrganization', 'jobLocation'],
};

function checkNode(p, node) {
  const types = [node['@type']].flat();
  for (const t of types) for (const field of REQUIRED[t] ?? []) if (!has(node, field)) fail(p.path, `JSON-LD ${t}: «${field}» fehlt`);
  if (types.includes('Organization') && !node.alternateName?.some?.((n) => n.includes('HS Steiner'))) {
    fail(p.path, 'JSON-LD Organization: alternateName ohne «HS Steiner»');
  }
  if (types.includes('BreadcrumbList')) {
    const items = node.itemListElement ?? [];
    items.forEach((it, i) => {
      if (it.position !== i + 1 || !it.name || !/^https?:\/\//.test(it.item ?? '')) fail(p.path, `JSON-LD Breadcrumb ${i + 1} unvollständig`);
    });
    if (items.length && items.at(-1).item !== urlOf(p.path)) fail(p.path, 'JSON-LD Breadcrumb endet nicht auf dieser Seite');
  }
  if (types.includes('FAQPage')) {
    const text = visibleText(p.html);
    for (const q of node.mainEntity ?? []) {
      if (!q.name || !q.acceptedAnswer?.text) fail(p.path, 'JSON-LD FAQ: Frage oder Antwort fehlt');
      else if (!text.includes(q.name)) fail(p.path, `JSON-LD FAQ «${q.name}» steht nicht sichtbar auf der Seite`);
    }
  }
}

function checkJsonLd(p) {
  const blocks = [...p.html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)];
  if (blocks.length !== 1) fail(p.path, `${blocks.length} JSON-LD-Blöcke statt einem`);
  for (const b of blocks) {
    let data;
    try {
      data = JSON.parse(b[1]);
    } catch (e) {
      fail(p.path, `JSON-LD nicht lesbar: ${e.message}`);
      continue;
    }
    if (data['@context'] !== 'https://schema.org' || !Array.isArray(data['@graph'])) fail(p.path, 'JSON-LD ohne @context/@graph');
    const raw = JSON.stringify(data);
    if (/"(Review|AggregateRating)"|"aggregateRating"|"review"/.test(raw)) fail(p.path, 'JSON-LD enthält Bewertungen');
    if (/\[\[|\{\{/.test(raw)) fail(p.path, 'JSON-LD enthält eine Markierung oder einen offenen Wert');
    const orgs = (data['@graph'] ?? []).filter((n) => [n['@type']].flat().includes('Organization'));
    if (orgs.length !== 1) fail(p.path, `${orgs.length} Organization-Knoten statt einem`);
    for (const node of data['@graph'] ?? []) checkNode(p, node);
  }
}

// ---------------------------------------------------------------- Sitemap, robots.txt, llms.txt
function read(name) {
  const f = join(DIST, name);
  if (!existsSync(f)) {
    fail(name, 'fehlt');
    return '';
  }
  return readFileSync(f, 'utf8');
}

function checkSitemap() {
  const xml = read('sitemap.xml');
  const locs = [...xml.matchAll(/<url><loc>([^<]+)<\/loc><lastmod>(\d{4}-\d{2}-\d{2})<\/lastmod><\/url>/g)];
  const all = (xml.match(/<url>/g) ?? []).length;
  if (locs.length !== all) fail('sitemap.xml', 'Eintrag ohne loc oder lastmod (JJJJ-MM-TT)');
  const listed = new Set();
  for (const [, loc] of locs) {
    if (!loc.startsWith(SITE_URL)) fail('sitemap.xml', `«${loc}» liegt nicht unter ${SITE_URL}`);
    const path = loc.slice(SITE_URL.length) || '/';
    listed.add(path);
    const p = byPath.get(path);
    if (!p) fail('sitemap.xml', `«${loc}» gibt es nicht`);
    else if (LIVE && p.noindex) fail('sitemap.xml', `«${loc}» ist noindex`);
  }
  for (const p of pages) if (!listed.has(p.path) && !p.noindex) fail(p.path, 'indexierbar, aber nicht in der Sitemap');
  return listed;
}

function checkRobots() {
  const txt = read('robots.txt');
  if (!LIVE) {
    if (!/User-agent: \*\nDisallow: \/\n/.test(txt) || /Sitemap:/.test(txt)) fail('robots.txt', 'Vorschau muss alles sperren');
    return;
  }
  for (const bot of site.seo.bots) if (!txt.includes(`User-agent: ${bot}\n`)) fail('robots.txt', `${bot} nicht zugelassen`);
  for (const p of site.privatePaths) if (!txt.includes(`Disallow: ${p}\n`)) fail('robots.txt', `${p} nicht gesperrt`);
  if (!txt.includes(`Sitemap: ${SITE_URL}/sitemap.xml`)) fail('robots.txt', 'Sitemap fehlt');
  if (/^Disallow: \/$/m.test(txt)) fail('robots.txt', 'Modus live, aber alles gesperrt');
}

function checkLlms(listed) {
  const short = read('llms.txt');
  const full = read('llms-full.txt');
  for (const [name, txt] of [['llms.txt', short], ['llms-full.txt', full]]) {
    if (!txt.startsWith(`# ${site.brand.name} (${site.brand.formerly})`)) fail(name, 'beginnt nicht mit dem Namen');
    if (!txt.includes(site.brand.notToConfuse)) fail(name, 'Abgrenzung zu «inexio» fehlt');
    if (!txt.includes(site.phone.display)) fail(name, 'Telefon fehlt');
    if (/\[\[|\{\{/.test(txt)) fail(name, 'enthält eine Markierung oder einen offenen Wert');
    checkWords(name, txt.replace(/https?:\/\/\S+/g, ''));
  }
  for (const m of short.matchAll(/\]\((https?:\/\/[^)]+)\)/g)) {
    const path = m[1].startsWith(SITE_URL) ? m[1].slice(SITE_URL.length) || '/' : null;
    if (path === null) fail('llms.txt', `Link «${m[1]}» zeigt nicht auf diese Website`);
    else if (!listed.has(path) && path !== '/llms-full.txt') fail('llms.txt', `Link «${m[1]}» steht nicht in der Sitemap`);
  }
}

// ---------------------------------------------------------------- Weiterleitungen (../firebase.json)
function checkRedirects(listed) {
  const config = JSON.parse(readFileSync(join(ROOT, '..', 'firebase.json'), 'utf8'));
  const rules = (config.hosting?.redirects ?? []).map((r, i) => {
    if (!r.regex || !r.destination || r.type !== 301) fail('firebase.json', `Weiterleitung ${i + 1}: regex, destination und type 301 sind Pflicht`);
    const ci = r.regex.startsWith('(?i)');
    let re = null;
    try {
      re = new RegExp(ci ? r.regex.slice(4) : r.regex, ci ? 'i' : '');
    } catch (e) {
      fail('firebase.json', `Weiterleitung ${i + 1}: Regex «${r.regex}» ungültig (${e.message})`);
    }
    const [destPath, destHash] = r.destination.split('#');
    if (!listed.has(destPath)) fail('firebase.json', `Weiterleitung ${i + 1} zeigt auf «${r.destination}» – keine Seite der Sitemap`);
    else if (destHash && !byPath.get(destPath)?.ids.has(destHash)) fail('firebase.json', `Weiterleitung ${i + 1}: Anker «#${destHash}» fehlt auf ${destPath}`);
    return { re, r };
  });
  for (const p of pages) {
    const hit = rules.find(({ re }) => re?.test(p.path));
    if (hit) fail('firebase.json', `«${hit.r.regex}» überdeckt die Seite ${p.path}`);
  }
  for (const [old, expected] of Object.entries(OLD_URLS)) {
    if (byPath.has(old)) {
      if (old !== expected) fail('firebase.json', `alter Pfad «${old}» ist eine Seite, verlangt ist die Weiterleitung auf «${expected}»`);
      continue;
    }
    const first = rules.find(({ re }) => re?.test(old));
    if (!first) fail('firebase.json', `alter Pfad «${old}» ohne Weiterleitung`);
    else if (first.r.destination !== expected) fail('firebase.json', `alter Pfad «${old}» führt auf «${first.r.destination}» statt «${expected}»`);
  }
  for (const gone of REMOVED) {
    if (byPath.has(gone)) fail(gone, 'Seite der ersten Fassung gibt es noch – sie ist entfallen');
  }
  return rules.length;
}

// ---------------------------------------------------------------- ERP-Pfade, Budget, E-Mail-Texte
function checkErpPaths() {
  for (const f of files) {
    const rel = relative(DIST, f).replace(/\\/g, '/');
    if (/^(erp|konto|api|_next)\//.test(rel) || /^(login|agb|erp|konto)(\.html|\/)/.test(rel)) fail(rel, 'liegt auf einem Pfad des ERP');
  }
}

const gz = (file) => gzipSync(readFileSync(file)).length;
const kb = (n) => `${(n / 1024).toFixed(1)} KB`;

/**
 * Bildgewicht wie im Browser: je <picture> genau EINE Datei – die AVIF-Fassung, die ein
 * Desktop-Bildschirm (1440 px, halbe Breite, doppelte Dichte ≈ 1200 px) lädt. Die JPEG-Rückfall-
 * datei im <img src> lädt ein Browser mit AVIF nie; sie zu zählen hiesse, jedes Bild doppelt
 * und in voller Grösse zu rechnen. Ein <img> ohne <picture> zählt mit seiner Datei.
 *
 * Die Bilder der Mega-Dropdowns (`.dd__img`, #1111) zählen nicht: das Panel ist geschlossen
 * `display: none`, die Bilder sind `loading="lazy"` – geladen werden sie erst beim Öffnen, und
 * dann in Dropdown-Grösse (sizes="240px"), nicht in halber Bildschirmbreite.
 */
function imageWeight(html, local) {
  html = html.replace(/<span class="dd__img[^>]*>\s*<picture\b[\s\S]*?<\/picture>\s*<\/span>/g, '');
  let sum = 0;
  const pictures = [...html.matchAll(/<picture\b[\s\S]*?<\/picture>/g)].map((m) => m[0]);
  for (const pic of pictures) {
    const srcset = pic.match(/<source\b[^>]*type="image\/avif"[^>]*srcset="([^"]+)"/)?.[1]
      ?? pic.match(/<source\b[^>]*srcset="([^"]+)"[^>]*type="image\/avif"/)?.[1];
    if (!srcset) continue;
    const cands = decode(srcset).split(',').map((c) => c.trim().split(/\s+/)).map(([url, w]) => ({ url, w: parseInt(w, 10) || 0 }));
    const fit = cands.filter((c) => c.w <= 1200).sort((a, b) => b.w - a.w)[0] ?? cands.sort((a, b) => a.w - b.w)[0];
    const file = fit && fit.url.startsWith('/') ? fileFor(fit.url) : null;
    if (file) sum += statSync(file).size;
  }
  const bare = html.replace(/<picture\b[\s\S]*?<\/picture>/g, '');
  sum += local(/<img\b[^>]*\ssrc="([^"]+)"/g, bare).reduce((s, f) => s + statSync(f).size, 0);
  return sum;
}

function checkBudget() {
  const fonts = files.filter((f) => f.endsWith('.woff2')).reduce((s, f) => s + statSync(f).size, 0);
  if (fonts > BUDGET.fonts) fail('Budget', `Schriften ${kb(fonts)} (höchstens ${kb(BUDGET.fonts)})`);
  let report = { js: 0, css: 0, home: 0 };
  for (const p of pages) {
    const local = (re, html = p.html) => [...new Set([...html.matchAll(re)].map((m) => decode(m[1])))].filter((h) => h.startsWith('/')).map(fileFor).filter(Boolean);
    const js = local(/<script\b[^>]*\ssrc="([^"]+)"/g).concat(local(/<link rel="modulepreload" href="([^"]+)"/g)).reduce((s, f) => s + gz(f), 0);
    const css = local(/<link rel="stylesheet" href="([^"]+)"/g).reduce((s, f) => s + gz(f), 0);
    if (js > BUDGET.jsGzip) fail(p.path, `JavaScript ${kb(js)} gzip (höchstens ${kb(BUDGET.jsGzip)})`);
    if (css > BUDGET.cssGzip) fail(p.path, `CSS ${kb(css)} gzip (höchstens ${kb(BUDGET.cssGzip)})`);
    report.js = Math.max(report.js, js);
    report.css = Math.max(report.css, css);
    if (p.path === '/') {
      const imgs = imageWeight(p.html, local);
      report.home = Buffer.byteLength(p.html) + js + css + fonts + imgs;
      if (report.home > BUDGET.home) fail('/', `Startseite ${kb(report.home)} (höchstens ${kb(BUDGET.home)})`);
    }
  }
  return { ...report, fonts };
}

function checkMailTexts() {
  const f = join(ROOT, '..', 'backend', 'app', 'assets', 'website_contact.json');
  if (!existsSync(f)) return fail('website_contact.json', 'fehlt – «npm run export:contact»');
  const texts = [];
  const collect = (v) => (typeof v === 'string' ? texts.push(v) : v && typeof v === 'object' && Object.values(v).forEach(collect));
  collect(JSON.parse(readFileSync(f, 'utf8')));
  checkWords('E-Mail-Texte', texts.join(' \n '));
}

// ---------------------------------------------------------------- Ablauf
/** Was im Modus «live» indexiert wird = was in der Sitemap steht (im Modus preview ist alles noindex). */
const INDEXED = checkSitemap();
const titles = new Map();
for (const p of pages) {
  const title = checkHead(p);
  if (title && INDEXED.has(p.path)) {
    if (titles.has(title)) fail(p.path, `Titel doppelt (auch ${titles.get(title)})`);
    titles.set(title, p.path);
  }
  checkHeadings(p);
  checkLinks(p);
  checkJsonLd(p);
  checkWords(p.path, visibleText(p.html));
  checkFirstMention(p);
}
const listed = INDEXED;
checkRobots();
checkLlms(listed);
const redirects = checkRedirects(listed);
checkErpPaths();
checkMailTexts();
const budget = checkBudget();

for (const w of warnings) console.warn(`  Hinweis  ${w}`);
if (errors.length) {
  console.error(`\ncheck-site: ${errors.length} Fehler`);
  for (const e of errors) console.error(`  ${e}`);
  process.exit(1);
}
console.log(
  `check-site: ${pages.length} Seiten, ${listed.size} in der Sitemap, ${redirects} Weiterleitungen – in Ordnung` +
    ` (JS max ${kb(budget.js)} · CSS max ${kb(budget.css)} gzip · Schriften ${kb(budget.fonts)} · Startseite ${kb(budget.home)})` +
    (warnings.length ? `, ${warnings.length} Hinweise` : ''),
);
