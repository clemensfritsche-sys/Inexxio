// ►►► Prüft die fertige Website (dist/) – läuft nach jedem Build (postbuild). ◄◄◄
//
//   node scripts/check-site.mjs
//
// Bricht ab (Exit 1) bei: kaputten internen Links und Ankern, ungültigem oder
// unvollständigem JSON-LD, Titel > 60 Zeichen, nicht genau einer H1, übersprungenen
// Überschriften-Ebenen, Bildern ohne Alt-Text, mehr als drei Kranbahn-Linien, verbotenen
// Wörtern (Kapitel 8.2), Sitemap/robots.txt/llms.txt im falschen Zustand, Weiterleitungen
// ins Leere (../firebase.json), Dateien auf ERP-Pfaden und überschrittenem Leistungsbudget.
// «ehemals HS Steiner» in Titel oder Beschreibung. Dazu für Suchmaschinen und KI-Dienste:
// Open Graph und Twitter-Karte vollständig; hreflang (Kopf und Sitemap) nur für freigegebene
// Sprachen, gegenseitig, mit x-default; jede indexierte Seite mit genau einem WebPage-Knoten, der
// Titel, Beschreibung, canonical, Sprache und lastmod des Kopfs bzw. der Sitemap wiederholt, und
// Brotkrumen; jeder JSON-LD-Verweis (@id) findet seinen Knoten; das Bild im Seitenkopf lädt
// zuerst (kein lazy, fetchpriority="high"); jede indexierte Seite steht in llms.txt und
// llms-full.txt. Warnt bei Meta-Descriptions ausserhalb 140–155 Zeichen.
//
// Bewusst ohne HTML-Parser-Abhängigkeit: geprüft wird die eigene, generierte Ausgabe.
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs';
import { dirname, join, relative, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { gzipSync } from 'node:zlib';
import { site, onErpPath } from '../src/config/site.mjs';
import { newsletter } from '../src/config/newsletter.mjs';
import { isLive } from '../src/lib/text.mjs';
import { languages, SOURCE } from '../src/config/languages.mjs';

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const DIST = join(ROOT, 'dist');
const LIVE = isLive();
const SITE_URL = (process.env.SITE_URL ?? 'http://localhost:4321').replace(/\/+$/, '');
/** Seiten, die das ERP auf derselben Domain ausliefert – Links dorthin sind gültig. */
const ERP_PAGES = site.erpPaths.filter((p) => p.page).map((p) => p.path);
/**
 * Leistungsbudget, in Bytes. **Eine Messart:** Text (HTML, JS, CSS) so, wie er über die Leitung
 * geht – gzip; was schon komprimiert ist (Bilder, Video, Schriften), roh. Die Startseite zählt
 * alles, was ein Desktop-Browser beim ersten Aufruf lädt, das Bühnenvideo eingeschlossen.
 */
const BUDGET = { jsGzip: 30 * 1024, cssGzip: 40 * 1024, fonts: 120 * 1024, home: 7000 * 1024 };
/** Kapitel 8.2 – im sichtbaren Text verboten (klein geschrieben verglichen). */
const FORBIDDEN = [
  'innovativ', 'ganzheitlich', 'massgeschneidert', 'maßgeschneidert', 'ihr zuverlässiger partner',
  'lösungen aus einer hand', 'höchste qualität', 'leidenschaft', 'mehrwert', 'state of the art',
  'synergie', 'exzellenz', 'revolutionär', 'nahtlos', 'im herzen von', 'herzlich willkommen',
  'pikett',
  // Rückmeldung 07.10.2026: keine Jahrespakete mehr – INEXXIO 365 ersetzt sie.
  'jahrespreis', 'jahrespaket',
  // Rückmeldung 09.10.2026: keine Markenaufzählung «für alle Marken» – offen lassen.
  'aller marken', 'alle marken', 'jeder marke', 'fremder marke',
  // Design System v4 (Oktober 2026): kein «Fixpreis» in keiner Form, keine «Werkstatt».
  'fixpreis', 'werkstatt', 'werkstätte',
];
/** Ganze Wörter, die nirgends stehen dürfen («Abo» – INEXXIO 365 ist kein Abo). */
const FORBIDDEN_WORDS = [/\babos?\b/i];
/**
 * Alte hs-steiner.ch-Pfade (WEBSITE_PLAN Entscheid 12/40) → das Ziel, das die Tabelle verlangt. Jeder muss
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
  '/heuentnahmekran/Kran-dem-Gebäude-Angepasst': '/krantechnik/krane-nach-mass',
  '/heuentnahmekran/Kran-dem-Geb%C3%A4ude-Angepasst': '/krantechnik/krane-nach-mass',
  '/heuentnahmekran/matagematerial': '/krantechnik/kranservice',
  '/betonfordertechnik': '/fahrzeugtechnik/trommeltausch',
  '/betonfordertechnik/Betonfahrmischer': '/fahrzeugtechnik/trommeltausch',
  '/betonfordertechnik/fahrmischerpumpen': '/fahrzeugtechnik/trommeltausch',
  '/betonfordertechnik/service-und-reparaturen': '/fahrzeugtechnik/trommeltausch',
  '/betonfordertechnik/bilder': '/fahrzeugtechnik/trommeltausch',
  '/betonfordertechnik/Euro-Kpper': '/fahrzeugtechnik#reparatur',
  '/betonfordertechnik/verschleissteile': '/fahrzeugtechnik/verschleissteile',
  '/antrieb-und-steuerung': '/krantechnik/kranservice',
  '/antrieb-und-steuerung/elektrosteuerung': '/krantechnik/kranservice',
  '/baumaschinen': '/spezialloesungen',
  '/baumaschinen/reparaturen': '/spezialloesungen',
  '/wahrschaftes': '/spezialloesungen',
  '/wahrschaftes/stahlbau': '/spezialloesungen',
  '/wahrschaftes/Gelaender-und-Verglasung': '/ueber-uns',
  '/sachtransporter-anhanger/Reparaturen': '/fahrzeugtechnik#reparatur',
  '/sachtransporter-anhanger': '/ueber-uns',
  '/sachtransporter-anhanger/aufbau': '/ueber-uns',
  '/forst-und-landwirtschaft': '/krantechnik/heukrananlagen',
  '/forst-und-landwirtschaft/heukrane': '/krantechnik/heukrananlagen',
  '/haus-und-garten': '/ueber-uns',
  '/haus-und-garten/rasenmaeher': '/ueber-uns',
  '/kleintransporter-pw': '/ueber-uns',
  '/kleintransporter-pw/reifenservice': '/ueber-uns',
  '/hebebuhnen': '/ueber-uns',
  '/Camping': '/ueber-uns',
  '/unsere-einsatzorte': '/ueber-uns',
  '/unsere-einsatzorte/ch-schweiz': '/ueber-uns',
  '/application/files/7615/1234/prospekt.pdf': '/krantechnik/heukrananlagen',
  '/kontakt': '/kontakt',
};
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

/** Die Sprache einer Seite – an ihrer Adresse (/fr/…), sonst Deutsch (src/config/languages.mjs). */
const langOf = (path) => languages.find((l) => l.code !== SOURCE && (path === `/${l.code}` || path.startsWith(`/${l.code}/`)))
  ?? languages.find((l) => l.code === SOURCE);

/**
 * ►►► Kein Deutsch auf einer Seite einer anderen Sprache (WEBSITE_PLAN Entscheid 136). ◄◄◄
 * Ein Text, der an `t()` vorbei im Code steht, bliebe in jeder Sprache deutsch – diese Prüfung
 * findet ihn am gebauten HTML: sichtbarer Text und was vorgelesen wird (alt, aria-label, title,
 * placeholder, Beschreibung). Namen (Firma, Personen, Orte, Marken) zählen nicht.
 */
const GERMAN = new Set(['und', 'der', 'die', 'das', 'dem', 'den', 'mit', 'für', 'nicht', 'ist', 'sind', 'wir', 'sie', 'ihr',
  'ihre', 'ihren', 'ihnen', 'unser', 'unsere', 'oder', 'auch', 'bei', 'nach', 'zum', 'zur', 'ein', 'eine', 'einen', 'wird',
  'werden', 'über', 'ohne', 'noch', 'jede', 'jeder', 'alle', 'wie', 'wenn', 'hier', 'uns', 'von', 'zu', 'auf', 'aus', 'im']);
/** Wörter, die auch in der Sprache selbst Wörter sind (it «alle» = «an den», en «die»). */
const OWN = { it: new Set(['alle']), en: new Set(['die']) };
const NAMES = [...site.brand.alternateNames, site.brand.formerLegalName, site.people.founder.name, site.people.owner.name,
  site.address.street, site.address.city, site.address.municipality, ...site.marks.mixers].sort((a, b) => b.length - a.length);
function checkLanguage(p) {
  const lang = langOf(p.path);
  if (lang.code === SOURCE) return;
  const said = [...p.html.matchAll(/\s(?:alt|aria-label|title|placeholder|content)="([^"]*)"/g)].map((m) => decode(m[1]));
  // Die Sprachwahl nennt jede Sprache in ihren eigenen Worten (Element mit `lang`) – das gehört so.
  const own = p.html.replace(/<li\b[^>]*>(?:(?!<\/li>)[\s\S])*?\slang="[^"]*"[\s\S]*?<\/li>/g, ' ');
  let text = `${visibleText(own)} ${said.join(' ')}`;
  for (const n of NAMES) text = text.split(n).join(' ');
  text = text.replace(/\S+@\S+/g, ' ');
  const found = new Map();
  for (const m of text.matchAll(/[\p{L}]+/gu)) {
    const w = m[0];
    if (OWN[lang.code]?.has(w.toLowerCase())) continue;
    if (!GERMAN.has(w.toLowerCase()) && !/[äöüß]/i.test(w)) continue;
    if (!found.has(w)) found.set(w, text.slice(Math.max(0, m.index - 40), m.index + w.length + 40).trim());
  }
  for (const [w, ctx] of found) fail(p.path, `deutsches Wort «${w}» auf einer Seite in «${lang.code}»: «…${ctx}…»`);
}

/** Die Startseite einer Sprache: «/» bzw. «/fr». */
const homeOf = (lang) => (lang.code === SOURCE ? '/' : `/${lang.code}`);

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
  const lang = langOf(p.path);
  if (!new RegExp(`<html lang="${lang.locale}"`).test(p.html)) fail(p.path, `lang="${lang.locale}" fehlt`);
  const desc = attr(/<meta name="description"[^>]*>/.exec(p.html)?.[0] ?? '', 'content');
  if (!desc) fail(p.path, 'Meta-Description fehlt');
  else if (INDEXED.has(p.path) && (desc.length < 140 || desc.length > 155)) {
    warn(p.path, `Meta-Description hat ${desc.length} Zeichen (Ziel 140–155)`);
  }
  // Der frühere Name steht im Fliesstext und im JSON-LD (alternateName), nie in Titel und
  // Beschreibung – dort trägt INEXXIO allein (Weisung 24.10.2026).
  const head = { Titel: title[0] ?? '', 'Meta-Description': desc ?? '', 'og:title': attr(/<meta property="og:title"[^>]*>/.exec(p.html)?.[0] ?? '', 'content') };
  for (const [what, text] of Object.entries(head)) {
    if (text.includes(site.brand.formerly)) fail(p.path, `${what} nennt «${site.brand.formerly}»: «${text}»`);
  }
  const canonical = attr(/<link rel="canonical"[^>]*>/.exec(p.html)?.[0] ?? '', 'href');
  if (canonical !== urlOf(p.path) && p.path !== '/404') fail(p.path, `canonical «${canonical}» ≠ «${urlOf(p.path)}»`);
  for (const prop of ['og:title', 'og:description', 'og:image', 'og:url']) {
    if (!new RegExp(`<meta property="${prop}" content="[^"]+"`).test(p.html)) fail(p.path, `${prop} fehlt`);
  }
  if (attr(/<meta property="og:url"[^>]*>/.exec(p.html)?.[0] ?? '', 'content') !== canonical) fail(p.path, 'og:url ≠ canonical');
  for (const name of ['twitter:card', 'twitter:title', 'twitter:description', 'twitter:image']) {
    if (!new RegExp(`<meta name="${name}" content="[^"]+"`).test(p.html)) fail(p.path, `${name} fehlt`);
  }
  // Sprachfassungen im Kopf: nur auf indexierten Seiten einer freigegebenen Sprache – und dann
  // nach denselben Regeln wie in der Sitemap (sich selbst, x-default, nur indexierte Adressen).
  const alt = [...p.html.matchAll(/<link rel="alternate" hreflang="([^"]+)" href="([^"]+)"[^>]*>/g)].map((m) => [m[1], decode(m[2])]);
  if (alt.length) {
    if (p.noindex || lang.status !== 'live') fail(p.path, `hreflang auf einer Seite, die nicht indexiert wird (${p.noindex ? 'noindex' : `Sprache ${lang.status}`})`);
    hreflangProblems(p.path, urlOf(p.path), alt);
    for (const [, href] of alt) if (!INDEXED.has(href.slice(SITE_URL.length) || '/')) fail(p.path, `hreflang «${href}» steht nicht in der Sitemap`);
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
  if (heroes.length === 1) checkHeroImages(p, heroes[0]);
  if (heroes.length !== 1) fail(p.path, `${heroes.length} Seitenköpfe (data-hero) statt genau einem`);
  else if (['article', 'main', 'body'].includes(heroes[0][1])) {
    fail(p.path, `data-hero an <${heroes[0][1]}> – gemeint ist der Seitenkopf (H1 und erste Handlung), nicht der ganze Inhalt`);
  } else if (p.html.indexOf('<h1', heroes[0].index) < 0) {
    fail(p.path, 'die H1 steht vor dem Seitenkopf (data-hero)');
  }
}

/**
 * Das Element vom öffnenden Tag `m` bis zu seinem Abschluss (gleichnamige Tags gezählt).
 * @param {string} html @param {RegExpMatchArray} m Treffer auf das öffnende Tag, Gruppe 1 = Name
 */
function elementAt(html, m) {
  const re = new RegExp(`<(/?)${m[1]}\\b[^>]*>`, 'g');
  re.lastIndex = m.index;
  let depth = 0;
  for (let t; (t = re.exec(html));) {
    depth += t[1] ? -1 : 1;
    if (depth === 0) return html.slice(m.index, re.lastIndex);
  }
  return html.slice(m.index);
}

/**
 * ►►► Das Bild im Seitenkopf ist das grösste im ersten Bild (LCP): es lädt sofort und zuerst. ◄◄◄
 * Seitenkopf = alles in <main> bis zum Ende des Elements mit `data-hero` (das Titelbild steht oft
 * daneben, nicht darin). Kein Bild dort mit `loading="lazy"`, das erste mit `fetchpriority="high"`. Ein Video
 * davor trägt sein Standbild selbst (`poster`) – dann gilt die Regel für das Video. Kleine Bilder
 * (jede Grösse in `sizes` höchstens 320px, z. B. ein Porträt neben der Telefonnummer) sind nie
 * das LCP-Element und zählen nicht.
 */
const small = (img) => {
  const sizes = attr(img, 'sizes');
  const lengths = sizes.split(',').map((part) => part.trim().split(/\s+/).at(-1));
  return Boolean(sizes) && lengths.every((l) => /^\d+px$/.test(l) && parseInt(l, 10) <= 320);
};
function checkHeroImages(p, hero) {
  const main = p.html.search(/<main\b/);
  const el = p.html.slice(main >= 0 && main < hero.index ? main : hero.index, hero.index + elementAt(p.html, hero).length);
  const video = el.indexOf('<video');
  const imgs = [...el.matchAll(/<img\b[^>]*>/g)].filter((m) => (video < 0 || m.index < video) && !small(m[0]));
  for (const m of imgs) if (/\sloading="lazy"/.test(m[0])) fail(p.path, `Bild im Seitenkopf lädt verzögert (loading="lazy"): ${m[0].slice(0, 90)}`);
  if (imgs.length && !/\sfetchpriority="high"/.test(imgs[0][0])) fail(p.path, `erstes Bild im Seitenkopf ohne fetchpriority="high": ${imgs[0][0].slice(0, 90)}`);
  if (video >= 0 && !imgs.length && !/<video\b[^>]*\sposter="/.test(el.slice(video))) fail(p.path, 'Video im Seitenkopf ohne Standbild (poster)');
}

/** Kapitel 8.1/8.2: verbotene Wörter, Ausrufezeichen, Emojis, ß. */
function checkWords(where, text) {
  const lower = text.toLowerCase();
  for (const w of FORBIDDEN) if (lower.includes(w)) fail(where, `verbotenes Wort «${w}»`);
  for (const rx of FORBIDDEN_WORDS) { const m = rx.exec(text); if (m) fail(where, `verbotenes Wort «${m[0]}»`); }
  const bang = /[^\s]![^=]|!$/.exec(text);
  if (bang) fail(where, `Ausrufezeichen: «…${text.slice(Math.max(0, bang.index - 30), bang.index + 2)}»`);
  // Emoji-Darstellung, nicht «Pictographic»: ©, ® und ™ sind Satzzeichen, keine Emojis.
  const emoji = /\p{Emoji_Presentation}|\uFE0F/u.exec(text);
  if (emoji) fail(where, `Emoji im Text: «${emoji[0]}»`);
  if (text.includes('ß')) fail(where, '«ß» statt «ss» (Schweizer Rechtschreibung)');
}

/**
 * Jedes `<use href="#…">` (das Logo steht EINMAL als Symbol, Lockup.astro) findet sein Ziel auf
 * derselben Seite – genau einmal. Sonst fehlte das Zeichen still.
 */
function checkUseRefs(p) {
  for (const id of new Set([...p.html.matchAll(/<use\b[^>]*\shref="#([^"]+)"/g)].map((m) => m[1]))) {
    const n = p.html.split(` id="${id}"`).length - 1;
    if (n !== 1) fail(p.path, `<use href="#${id}"> – das Ziel steht ${n}-mal auf der Seite (erwartet: einmal)`);
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
  if (ERP_PAGES.some((e) => bare === e || bare.startsWith(`${e}/`))) return;
  const clean = bare.replace(/\/$/, '') || '/';
  const file = fileFor(clean);
  if (!file) return fail(p.path, `${kind} ins Leere: «${href}»`);
  if (hash && file.endsWith('.html')) {
    const tp = byPath.get(pathOf(file));
    if (tp && !tp.ids.has(decodeURIComponent(hash))) fail(p.path, `Anker «${href}» fehlt auf ${tp.path}`);
  }
}

/** Wohin ein Formular der Website schicken darf: die Anfrage und die Newsletter-Anmeldung. */
const FORM_TARGETS = new Set(['/api/v1/contact', '/api/v1/newsletter']);

function checkLinks(p) {
  for (const m of p.html.matchAll(/<a\b[^>]*\shref="([^"]*)"/g)) checkTarget(p, decode(m[1]), 'Link');
  for (const m of p.html.matchAll(/<(?:img|script|source)\b[^>]*\ssrc="([^"]*)"/g)) checkTarget(p, decode(m[1]), 'Datei');
  for (const m of p.html.matchAll(/<link\b[^>]*\shref="([^"]*)"/g)) {
    if (!/rel="canonical"/.test(m[0])) checkTarget(p, decode(m[1]), 'Datei');
  }
  for (const m of p.html.matchAll(/<form\b[^>]*\saction="([^"]*)"/g)) {
    // Die Sprache der Seite reist als `?lang=` mit (der Server antwortet in ihr) – nur eine bekannte.
    const [target, query] = decode(m[1]).split('?');
    const lang = query ? /^lang=([a-z]{2})$/.exec(query)?.[1] : undefined;
    if (!FORM_TARGETS.has(target) || (query && !languages.some((l) => l.code === lang))) fail(p.path, `Formular schickt an «${m[1]}»`);
  }
}

// ---------------------------------------------------------------- JSON-LD
const has = (o, path) => path.split('.').reduce((v, k) => (v == null ? undefined : v[k]), o) != null;
/** Die Arten der Seite selbst (src/lib/seo.mjs `webPage`, src/lib/pages.ts `type`). */
const PAGE_TYPES = ['WebPage', 'AboutPage', 'ContactPage', 'CollectionPage'];
const PAGE_FIELDS = ['@id', 'url', 'name', 'description', 'inLanguage', 'isPartOf', 'publisher'];
const REQUIRED = {
  Organization: ['name', 'url', 'logo', 'telephone', 'address.streetAddress', 'address.postalCode', 'address.addressLocality', 'address.addressCountry', 'geo.latitude', 'areaServed', 'foundingDate', 'founder.name'],
  ...Object.fromEntries(PAGE_TYPES.map((t) => [t, PAGE_FIELDS])),
  WebSite: ['name', 'url'],
  BreadcrumbList: ['itemListElement'],
  FAQPage: ['mainEntity'],
  Service: ['name', 'serviceType', 'provider'],
  Article: ['headline', 'description', 'datePublished', 'dateModified', 'author.name', 'image', 'inLanguage', 'mainEntityOfPage'],
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
    if (/\{\{/.test(raw)) fail(p.path, 'JSON-LD enthält einen offenen Wert');
    const orgs = (data['@graph'] ?? []).filter((n) => [n['@type']].flat().includes('Organization'));
    if (orgs.length !== 1) fail(p.path, `${orgs.length} Organization-Knoten statt einem`);
    for (const node of data['@graph'] ?? []) checkNode(p, node);
    checkRefs(p, data['@graph'] ?? []);
    checkPageNode(p, data['@graph'] ?? []);
  }
}

/**
 * Jeder Verweis `{ "@id": … }` (ein Objekt, das nur die @id trägt) zeigt auf einen Knoten im
 * selben Graphen – sonst verbindet er nichts. Und keine @id ist zweimal vergeben.
 */
function checkRefs(p, nodes) {
  const ids = new Map();
  for (const n of nodes) if (n['@id']) ids.set(n['@id'], (ids.get(n['@id']) ?? 0) + 1);
  for (const [id, n] of ids) if (n > 1) fail(p.path, `JSON-LD: @id «${id}» ${n}-mal vergeben`);
  const walkRefs = (v) => {
    if (Array.isArray(v)) return v.forEach(walkRefs);
    if (!v || typeof v !== 'object') return;
    const keys = Object.keys(v);
    if (keys.length === 1 && keys[0] === '@id' && !ids.has(v['@id'])) fail(p.path, `JSON-LD: Verweis auf «${v['@id']}» ohne Knoten`);
    for (const k of keys) if (k !== '@id') walkRefs(v[k]);
  };
  nodes.forEach((n) => Object.entries(n).forEach(([k, v]) => k !== '@id' && walkRefs(v)));
}

/**
 * ►►► Jede indexierte Seite beschreibt sich selbst (WebPage) – mit dem, was im Kopf steht. ◄◄◄
 * Genau ein Seiten-Knoten: Adresse = canonical, Name = <title>, Beschreibung = Meta-Description,
 * Sprache = lang, Stand = lastmod der Sitemap; Brotkrumen auf jeder Seite ausser der Startseite.
 * So können Titel, Beschreibung und strukturierte Daten nicht auseinanderlaufen.
 */
function checkPageNode(p, nodes) {
  if (!INDEXED.has(p.path)) return;
  const own = nodes.filter((n) => PAGE_TYPES.includes(n['@type']));
  if (own.length !== 1) return fail(p.path, `${own.length} Seiten-Knoten (WebPage …) statt einem`);
  const n = own[0];
  const url = urlOf(p.path);
  const head = {
    url, '@id': `${url}#webpage`,
    name: decode(/<title>([\s\S]*?)<\/title>/.exec(p.html)?.[1] ?? '').trim(),
    description: attr(/<meta name="description"[^>]*>/.exec(p.html)?.[0] ?? '', 'content'),
    inLanguage: langOf(p.path).locale,
    dateModified: LASTMOD.get(p.path),
  };
  for (const [k, want] of Object.entries(head)) if (n[k] !== want) fail(p.path, `JSON-LD ${n['@type']}: ${k} «${n[k]}» ≠ «${want}»`);
  const crumbs = nodes.filter((x) => x['@type'] === 'BreadcrumbList');
  if (p.path !== homeOf(langOf(p.path)) && crumbs.length !== 1) fail(p.path, `${crumbs.length} BreadcrumbList statt einer`);
  if (crumbs.length && n.breadcrumb?.['@id'] !== crumbs[0]['@id']) fail(p.path, 'JSON-LD: Seite verweist nicht auf ihre Brotkrumen');
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

/** `lastmod` je Pfad der Sitemap – dasselbe Datum steht als `dateModified` im JSON-LD der Seite. */
const LASTMOD = new Map();

/**
 * Die Sitemap: je `<url>` genau ein `loc` und ein `lastmod` (JJJJ-MM-TT), nur Seiten, die es gibt
 * und die indexiert werden – nie eine Sprache, die noch gegengelesen wird (`preview`). Nennt ein
 * Eintrag seine Fassungen in anderen Sprachen (xhtml:link hreflang), dann sich selbst, x-default
 * und nur Adressen, die selbst in der Sitemap stehen und dieselbe Gruppe nennen (gegenseitig).
 */
function checkSitemap() {
  const xml = read('sitemap.xml');
  const blocks = [...xml.matchAll(/<url>([\s\S]*?)<\/url>/g)].map((m) => m[1]);
  if (blocks.length !== (xml.match(/<url>/g) ?? []).length) fail('sitemap.xml', '<url> ohne Abschluss');
  const listed = new Set();
  /** @type {Map<string, string>} loc → die Gruppe seiner Sprachfassungen */
  const groups = new Map();
  for (const b of blocks) {
    const loc = [...b.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => decode(m[1]));
    const lastmod = [...b.matchAll(/<lastmod>([^<]*)<\/lastmod>/g)].map((m) => m[1]);
    if (loc.length !== 1 || lastmod.length !== 1 || !/^\d{4}-\d{2}-\d{2}$/.test(lastmod[0])) {
      fail('sitemap.xml', `Eintrag ohne genau ein loc und ein lastmod (JJJJ-MM-TT): ${b.trim().slice(0, 100)}`);
      continue;
    }
    if (!loc[0].startsWith(SITE_URL)) fail('sitemap.xml', `«${loc[0]}» liegt nicht unter ${SITE_URL}`);
    const path = loc[0].slice(SITE_URL.length) || '/';
    listed.add(path);
    LASTMOD.set(path, lastmod[0]);
    const p = byPath.get(path);
    if (!p) fail('sitemap.xml', `«${loc[0]}» gibt es nicht`);
    else if (LIVE && p.noindex) fail('sitemap.xml', `«${loc[0]}» ist noindex`);
    if (langOf(path).status !== 'live') fail('sitemap.xml', `«${loc[0]}» gehört zur Sprache «${langOf(path).code}» (${langOf(path).status}) – nur freigegebene Sprachen`);
    const alt = [...b.matchAll(/<xhtml:link rel="alternate" hreflang="([^"]+)" href="([^"]+)"\/>/g)].map((m) => [m[1], decode(m[2])]);
    if (alt.length) {
      if (!/xmlns:xhtml="http:\/\/www\.w3\.org\/1999\/xhtml"/.test(xml)) fail('sitemap.xml', 'hreflang ohne xmlns:xhtml');
      groups.set(loc[0], hreflangProblems('sitemap.xml', loc[0], alt));
    }
  }
  for (const [loc, group] of groups) {
    for (const href of group.split(' ')) {
      if (!listed.has(href.slice(SITE_URL.length) || '/')) fail('sitemap.xml', `${loc}: hreflang «${href}» steht nicht in der Sitemap`);
      else if (groups.get(href) !== group) fail('sitemap.xml', `${loc}: hreflang nicht gegenseitig mit «${href}»`);
    }
  }
  for (const p of pages) if (!listed.has(p.path) && !p.noindex) fail(p.path, 'indexierbar, aber nicht in der Sitemap');
  return listed;
}

/**
 * Eine Gruppe von Sprachfassungen (Sitemap oder <link rel="alternate">): jede Sprache einmal und
 * freigegeben, die Seite selbst darin, dazu x-default. Gibt die Gruppe als sortierte Adressen zurück.
 * @param {string} where @param {string} self volle Adresse @param {string[][]} alt [hreflang, href]
 */
function hreflangProblems(where, self, alt) {
  const live = new Map(languages.filter((l) => l.status === 'live').map((l) => [l.locale, l]));
  const seen = new Set();
  for (const [code, href] of alt) {
    if (seen.has(code)) fail(where, `${self}: hreflang «${code}» doppelt`);
    seen.add(code);
    if (code !== 'x-default' && !live.has(code)) fail(where, `${self}: hreflang «${code}» ist keine freigegebene Sprache`);
    else if (code !== 'x-default' && langOf(href.slice(SITE_URL.length) || '/').locale !== code) fail(where, `${self}: hreflang «${code}» zeigt auf «${href}» (andere Sprache)`);
  }
  if (!seen.has('x-default')) fail(where, `${self}: hreflang ohne x-default`);
  if (!alt.some(([code, href]) => code !== 'x-default' && href === self)) fail(where, `${self}: hreflang nennt die Seite selbst nicht`);
  return alt.filter(([code]) => code !== 'x-default').map(([, href]) => href).sort().join(' ');
}

/**
 * ►►► Jede Seite ist über das Menü im Kopf erreichbar (Testnotiz #1154). ◄◄◄
 * Ausgenommen sind nur die Startseite (das Logo), Impressum und Datenschutz (Fuss, Pflicht-
 * angaben) und die einzelnen Ratgeber-Artikel (sie stehen auf /ratgeber, das im Menü ist).
 * Eine neue Seite ohne Menüpunkt bricht den Build ab, statt unauffindbar zu werden.
 */
function checkMenu(listed) {
  // Je Sprache ihr eigenes Menü (das der Startseite dieser Sprache, /fr …).
  const menus = new Map();
  const menuOf = (lang) => {
    if (!menus.has(lang.code)) {
      const header = byPath.get(homeOf(lang))?.html.match(/<header class="site-header[\s\S]*?<\/header>/)?.[0] ?? '';
      menus.set(lang.code, new Set([...header.matchAll(/href="([^"#?]+)/g)].map((m) => m[1].replace(/\/$/, '') || '/')));
    }
    return menus.get(lang.code);
  };
  // Ein Ratgeber-Artikel steht auf der Übersicht, nicht im Menü – erkannt an seinem JSON-LD.
  const exempt = (path) => path === homeOf(langOf(path)) || /"@type":"Article"/.test(byPath.get(path)?.html ?? '');
  for (const path of listed) if (!exempt(path) && !menuOf(langOf(path)).has(path)) fail(path, 'nicht über das Menü im Kopf erreichbar');
}

/**
 * ►►► Der Fuss nennt genau die Punkte des Kopfs – in derselben Reihenfolge (Testnotiz #1209). ◄◄◄
 * Beide lesen `site.navigation`; diese Prüfung hält es am gebauten HTML fest, damit niemand
 * den Fuss wieder von Hand erweitert. Kontakt (eigene Spalte bzw. eigener Punkt) und ERP
 * (nur für Personal) gehören nicht zur Liste.
 */
function checkFooterMatchesHeader() {
  const home = pages.find((p) => p.path === '/');
  const order = (html) => [...new Set([...html.matchAll(/href="([^"]+)"/g)].map((m) => decode(m[1])))]
    .filter((h) => h.startsWith('/') && h !== '/kontakt' && !h.startsWith('/erp'));
  const nav = home?.html.match(/<nav class="nav[ "][\s\S]*?<\/nav>/)?.[0] ?? '';
  const grid = home?.html.match(/<div class="site-footer__grid[ "][\s\S]*?<\/address>/)?.[0] ?? '';
  const foot = [...grid.matchAll(/<nav class="site-footer__col[ "][\s\S]*?<\/nav>/g)].map((m) => m[0]).join('');
  const a = order(nav).join(' ');
  const b = order(foot).join(' ');
  if (!a) fail('/', 'Hauptnavigation im Kopf nicht gefunden');
  else if (a !== b) fail('/', `Fuss und Kopf nennen andere Punkte:\n    Kopf: ${a}\n    Fuss: ${b}`);
}

function checkRobots() {
  const txt = read('robots.txt');
  if (!LIVE) {
    // Nicht öffentlich ist die Vorschau durch noindex auf jeder Seite (oben), nicht durch robots.txt.
    if (/^Disallow: \/$/m.test(txt) || /Sitemap:/.test(txt)) fail('robots.txt', 'Vorschau: keine Sitemap, kein «Disallow: /» (sonst sähe Google das noindex nicht)');
    return;
  }
  for (const bot of site.seo.bots) if (!txt.includes(`User-agent: ${bot}\n`)) fail('robots.txt', `${bot} nicht zugelassen`);
  for (const p of site.privatePaths) if (!txt.includes(`Disallow: ${p}\n`)) fail('robots.txt', `${p} nicht gesperrt`);
  for (const p of site.noindexPages) if (txt.includes(`Disallow: ${p}`)) fail('robots.txt', `${p} gesperrt – Google sähe das noindex nicht`);
  if (!txt.includes(`Sitemap: ${SITE_URL}/sitemap.xml`)) fail('robots.txt', 'Sitemap fehlt');
  if (/^Disallow: \/$/m.test(txt)) fail('robots.txt', 'Modus live, aber alles gesperrt');
}

function checkLlms(listed) {
  const short = read('llms.txt');
  const full = read('llms-full.txt');
  for (const [name, txt] of [['llms.txt', short], ['llms-full.txt', full]]) {
    if (!txt.startsWith(`# ${site.brand.name}\n`)) fail(name, 'beginnt nicht mit dem Namen');
    if (!txt.includes(site.brand.notToConfuse)) fail(name, 'Abgrenzung zu «inexio» fehlt');
    if (!txt.includes(site.phone.display)) fail(name, 'Telefon fehlt');
    if (/\{\{/.test(txt)) fail(name, 'enthält einen offenen Wert');
    checkWords(name, txt.replace(/https?:\/\/\S+/g, ''));
  }
  for (const m of short.matchAll(/\]\((https?:\/\/[^)]+)\)/g)) {
    const path = m[1].startsWith(SITE_URL) ? m[1].slice(SITE_URL.length) || '/' : null;
    if (path === null) fail('llms.txt', `Link «${m[1]}» zeigt nicht auf diese Website`);
    else if (!listed.has(path) && path !== '/llms-full.txt') fail('llms.txt', `Link «${m[1]}» steht nicht in der Sitemap`);
  }
  // Umgekehrt: jede indexierte Seite der Quellsprache steht in llms.txt (verlinkt) und in
  // llms-full.txt (im Wortlaut) – eine neue Seite kann nicht still fehlen.
  for (const path of listed) {
    if (langOf(path).code !== SOURCE) continue;
    if (!short.includes(`](${urlOf(path)})`)) fail('llms.txt', `Seite ${path} fehlt (kein Link)`);
    if (!full.includes(`URL: ${urlOf(path)}\n`)) fail('llms-full.txt', `Seite ${path} fehlt`);
  }
  if (!short.includes(`](${urlOf('/llms-full.txt')})`)) fail('llms.txt', 'Link auf llms-full.txt fehlt');
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
  return rules.length;
}

// ---------------------------------------------------------------- ERP-Pfade, Budget, E-Mail-Texte
function checkErpPaths() {
  for (const f of files) {
    const rel = relative(DIST, f).replace(/\\/g, '/');
    if (onErpPath(rel)) fail(rel, 'liegt auf einem Pfad des ERP');
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
  // Bilder der Menü-Kacheln laden erst beim Öffnen des Kopf-Menüs (Header.astro: Kachelreihe vorher nicht im Layout).
  html = html.replace(/<img\b[^>]*\sdata-menu-img\b[^>]*>/g, '');
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

/**
 * Videogewicht wie im Browser: das Standbild (`poster`) und die Quelle, die das Gerät wählt – das
 * Bühnenvideo spielt von selbst und lädt darum ganz (Media.astro). Je Gerät passt EINE Quelle
 * (breit oder hochkant); gezählt wird die grösste.
 */
function videoWeight(html) {
  let sum = 0;
  for (const [video] of html.matchAll(/<video\b[\s\S]*?<\/video>/g)) {
    const size = (url) => {
      const file = url.startsWith('/') ? fileFor(decode(url).split('?')[0]) : null;
      if (!file) fail('Budget', `Video-Datei «${url}» fehlt in dist/`);
      return file ? statSync(file).size : 0;
    };
    const poster = video.match(/\sposter="([^"]+)"/)?.[1];
    // Je Gerät lädt nur EINE Quelle (breit oder hochkant): gezählt wird die grösste.
    const sources = [...video.matchAll(/<source\b[^>]*\ssrc="([^"]+)"/g)].map((m) => size(m[1]));
    sum += (poster ? size(poster) : 0) + Math.max(0, ...sources);
  }
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
      const video = videoWeight(p.html);
      report.home = gzipSync(p.html).length + js + css + fonts + imgs + video;
      report.homeParts = { html: gzipSync(p.html).length, js, css, fonts, imgs, video };
      if (report.home > BUDGET.home) fail('/', `Startseite ${kb(report.home)} (höchstens ${kb(BUDGET.home)})`);
    }
  }
  return { ...report, fonts };
}

function checkMailTexts() {
  const f = join(ROOT, '..', 'backend', 'app', 'assets', 'website_contact.json');
  if (!existsSync(f)) return fail('website_contact.json', 'fehlt – «npm run export:erp»');
  const texts = [];
  const collect = (v) => (typeof v === 'string' ? texts.push(v) : v && typeof v === 'object' && Object.values(v).forEach(collect));
  collect(JSON.parse(readFileSync(f, 'utf8')));
  checkWords('E-Mail-Texte', texts.join(' \n '));
}

// ---------------------------------------------------------------- Ablauf
/** Was im Modus «live» indexiert wird = was in der Sitemap steht (im Modus preview ist alles noindex). */
const INDEXED = checkSitemap();
checkMenu(INDEXED);
checkFooterMatchesHeader();
const titles = new Map();
for (const p of pages) {
  const title = checkHead(p);
  if (title && INDEXED.has(p.path)) {
    if (titles.has(title)) fail(p.path, `Titel doppelt (auch ${titles.get(title)})`);
    titles.set(title, p.path);
  }
  checkHeadings(p);
  checkLinks(p);
  checkUseRefs(p);
  checkJsonLd(p);
  checkWords(p.path, visibleText(p.html));
  checkLanguage(p);
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
    ` (JS max ${kb(budget.js)} · CSS max ${kb(budget.css)} gzip · Schriften ${kb(budget.fonts)} · Startseite ${kb(budget.home)}` +
    (budget.homeParts ? ` = HTML ${kb(budget.homeParts.html)} + JS + CSS + Schriften + Bilder ${kb(budget.homeParts.imgs)} + Video ${kb(budget.homeParts.video)}` : '') + ')' +
    (warnings.length ? `, ${warnings.length} Hinweise` : ''),
);
