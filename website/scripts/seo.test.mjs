// Wächter für das, was ein Build im Modus «preview» nicht zeigt: den Zweig «live» der
// robots.txt (ein echter live-Build bricht ab, solange Markierungen offen sind).
//   npm test
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { robotsTxt } from '../src/lib/robots.mjs';
import { site } from '../src/config/site.mjs';

const BASE = 'https://www.example.ch';

test('Vorschau: alles gesperrt, keine Sitemap', () => {
  const txt = robotsTxt('preview', BASE);
  assert.match(txt, /^User-agent: \*\nDisallow: \/$/m);
  assert.doesNotMatch(txt, /Sitemap:/);
  assert.doesNotMatch(txt, /Allow: \//);
});

test('live: jeder Crawler der Liste ausdrücklich zugelassen', () => {
  const txt = robotsTxt('live', BASE);
  for (const bot of site.seo.bots) assert.ok(txt.includes(`User-agent: ${bot}\n`), bot);
  for (const bot of ['GPTBot', 'ClaudeBot', 'PerplexityBot', 'Google-Extended', 'CCBot']) {
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
