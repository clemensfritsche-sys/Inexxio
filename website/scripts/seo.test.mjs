// Wächter für das, was ein Build im Modus «preview» nicht zeigt: den Zweig «live» der
// robots.txt (ein echter live-Build bricht ab, solange ein Foto fehlt).
//   npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { robotsTxt } from '../src/lib/robots.mjs';
import { site } from '../src/config/site.mjs';
import { article, breadcrumbs, organization, webPage } from '../src/lib/seo.mjs';

const BASE = 'https://www.example.ch';

test('Vorschau: alles gesperrt, keine Sitemap', () => {
  const txt = robotsTxt('preview', BASE);
  assert.match(txt, /^User-agent: \*\nDisallow: \/$/m);
  assert.doesNotMatch(txt, /Sitemap:/);
  assert.doesNotMatch(txt, /Allow: \//);
});

test('Vorschau: Konto- und ERP-Pfade trotzdem ausdrücklich gesperrt (immer, auch im Modus preview)', () => {
  const txt = robotsTxt('preview', BASE);
  for (const p of site.privatePaths) assert.ok(txt.includes(`Disallow: ${p}\n`), p);
  for (const p of ['/erp', '/konto', '/login', '/abmelden', '/dokument']) assert.ok(site.privatePaths.includes(p), `${p} fehlt in site.privatePaths`);
});

test('live: jeder Crawler der Liste ausdrücklich zugelassen', () => {
  const txt = robotsTxt('live', BASE);
  for (const bot of site.seo.bots) assert.ok(txt.includes(`User-agent: ${bot}\n`), bot);
  for (const bot of ['Googlebot', 'Bingbot', 'GPTBot', 'OAI-SearchBot', 'ChatGPT-User', 'ClaudeBot', 'Claude-SearchBot', 'Claude-User',
    'PerplexityBot', 'Google-Extended', 'Applebot-Extended', 'CCBot']) {
    assert.ok(site.seo.bots.includes(bot), `${bot} fehlt in site.seo.bots`);
  }
});

test('live: Kundenbereich gesperrt – für jede Gruppe', () => {
  const txt = robotsTxt('live', BASE);
  const groups = txt.split(/\n\n/).filter((g) => g.includes('User-agent:'));
  assert.equal(groups.length, 2);
  for (const g of groups) for (const p of site.privatePaths) assert.ok(`${g}\n`.includes(`Disallow: ${p}\n`), `${p} in «${g.split("\n")[0]}»`);
  assert.doesNotMatch(txt, /^Disallow: \/$/m);
});

test('live: Sitemap unter der eigenen Adresse', () => {
  assert.ok(robotsTxt('live', BASE).includes(`Sitemap: ${BASE}/sitemap.xml\n`));
});

// ---------------------------------------------------------------- JSON-LD (src/lib/seo.mjs)

test('Organization: Einsatzgebiet als Ländercodes, dieselben wie im Kontakt', () => {
  const org = organization(BASE);
  assert.ok(site.seo.areaServed.length > 0);
  for (const c of site.seo.areaServed) assert.match(c, /^[A-Z]{2}$/, `${c} ist kein ISO-Ländercode`);
  assert.deepEqual(org.areaServed.map((a) => a.name), site.seo.areaServed);
  assert.deepEqual(org.contactPoint[0].areaServed, site.seo.areaServed);
});

test('WebPage: verknüpft Website, Firma und Brotkrumen über @id – Brotkrumen nur, wenn es sie gibt', () => {
  const p = webPage(BASE, { path: '/service', name: 'Service | INEXXIO', description: 'Text', updated: '2026-10-08', breadcrumb: true, image: `${BASE}/og/default.png` });
  assert.equal(p['@type'], 'WebPage');
  assert.equal(p['@id'], `${BASE}/service#webpage`);
  assert.equal(p.isPartOf['@id'], `${BASE}/#website`);
  assert.equal(p.publisher['@id'], organization(BASE)['@id']);
  assert.equal(p.breadcrumb['@id'], breadcrumbs(BASE, [{ name: 'Service', path: '/service' }])['@id']);
  assert.equal(p.dateModified, '2026-10-08');
  const bare = webPage(BASE, { path: '/', name: 'INEXXIO', description: 'Text', breadcrumb: false, image: `${BASE}/og/default.png`, type: 'AboutPage' });
  assert.equal(bare.breadcrumb, undefined);
  assert.equal(bare.dateModified, undefined, 'ohne Datum kein leeres dateModified');
  assert.equal(bare['@type'], 'AboutPage');
});

test('Article: gehört zu seiner Seite, mit Bild und Sprache', () => {
  const a = article(BASE, { title: 'T', description: 'D', path: '/ratgeber/x', published: '2026-10-01', updated: '2026-10-02', image: `${BASE}/_astro/x.webp` });
  assert.equal(a.mainEntityOfPage['@id'], `${BASE}/ratgeber/x#webpage`);
  assert.deepEqual(a.image, [`${BASE}/_astro/x.webp`, `${BASE}/og/default.png`]);
  assert.equal(a.inLanguage, 'de-CH');
});
