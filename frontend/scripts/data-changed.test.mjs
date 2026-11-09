/**
 * ►►► **«Ich habe Daten geändert» wird an EINER Stelle gesagt und an EINER gehört.** ◄◄◄
 *
 * Gesagt in `lib/api.ts` – nach jeder erfolgreichen Anfrage, die kein GET ist, mit ihrem Pfad;
 * gehört in `lib/use-feed.ts`, das über `lib/feed.touchedBy` invalidiert (Wächter
 * `feed.test.mjs`). Ein Aufrufer kann das Melden darum nicht vergessen, und ein zweiter
 * Hörer (ein Detailfenster, das selbst nachlädt) wäre die zweite Datenquelle neben React Query
 * – Feed und Detail liefen auseinander (#685, #688).
 *
 *     node --test scripts/data-changed.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { files, find, line, load, parse, ts } from './lib/source.mjs';

const { api } = await load('lib/api.ts', { '@/lib/feed': "export const DATA_CHANGED = 'data-changed';" });

const heard = [];
globalThis.window = { dispatchEvent: (e) => heard.push([e.type, e.detail]) };
globalThis.CustomEvent ??= class { constructor(type, init) { this.type = type; this.detail = init?.detail; } };

function answer(status, body = {}) {
  globalThis.fetch = async () => ({
    ok: status < 400, status,
    json: async () => body, blob: async () => body,
    clone() { return this; },
  });
}

test('eine erfolgreiche schreibende Anfrage meldet ihren Pfad – ein GET nie', async () => {
  heard.length = 0;
  answer(200, { object_id: 1 });
  await api.getOrder(100000123);
  assert.deepEqual(heard, [], 'ein Lesen meldet eine Änderung');
  const talk = 7;
  await api.stopTalk(talk);
  assert.deepEqual(heard, [['data-changed', { path: `/api/v1/erp/assistant/talks/${talk}/stop` }]]);
});

test('eine abgewiesene Anfrage hat nichts geändert und meldet nichts', async () => {
  heard.length = 0;
  answer(409, { detail: 'schon angehalten', code: 'conflict' });
  await assert.rejects(api.stopTalk(7), /schon angehalten/);
  assert.deepEqual(heard, []);
});

// ─── Gehört wird an EINER Stelle ─────────────────────────────────────────────

/** Wer das Signal kennen darf: wo es steht, wer es sagt, wer es hört. */
const OWNERS = new Set(['lib/feed.ts', 'lib/api.ts', 'lib/use-feed.ts']);

function mentions(sf) {
  return find(sf, (n) => ts.isIdentifier(n) && n.text === 'DATA_CHANGED')
    .concat(find(sf, (n) => ts.isStringLiteral(n) && n.text === 'inexxio:data-changed'))
    .map((n) => line(n));
}

test('niemand ausser lib/use-feed hört auf Schreibvorgänge', () => {
  const bad = files().filter((rel) => !OWNERS.has(rel))
    .flatMap((rel) => mentions(parse(rel)).map((l) => `${rel}:${l}`));
  assert.deepEqual(bad, [], `Ein zweiter Hörer – nachgeladen wird über lib/feed.TOUCHES:\n${bad.join('\n')}`);
  assert.ok(mentions(parse('lib/use-feed.ts')).length > 0, 'lib/use-feed hört nicht mehr – der Wächter wäre blind');
});

test('der Wächter erkennt die Bug-Form', () => {
  const sample = (t) => mentions(parse(t, { text: true }));
  assert.equal(sample("window.addEventListener(DATA_CHANGED, reload);").length, 1);
  assert.equal(sample("window.addEventListener('inexxio:data-changed', reload);").length, 1);
  assert.equal(sample('// DATA_CHANGED im Kommentar\nconst x = 1;').length, 0);
});
