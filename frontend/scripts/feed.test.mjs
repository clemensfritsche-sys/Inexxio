/**
 * ►►► **Ein Schreibvorgang lädt nur nach, was er ändert – und nie zu wenig.** ◄◄◄
 *
 * Der ERP-Feed lud nach JEDER schreibenden Anfrage alle Listen neu (auch nach einer Prüfung
 * oder dem Abgleich der Postfächer, jede Minute). Jetzt invalidiert `lib/use-feed.ts` nur die
 * Listen, die `feedsTouchedBy(path)` aus `src/lib/feed.ts` nennt. Geprüft gegen die echte
 * Quelle (transpiliert): die Bug-Formen «zu wenig» (ein Auftrag lädt die Stücke nicht nach),
 * «unbekannt = nichts» (ein neuer Endpunkt liesse den Feed stehen) und «Präfix trifft
 * Fremdes» (`/orders` trifft `/ordersX`).
 *
 *     node --test scripts/feed.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const js = ts.transpileModule(readFileSync(resolve(here, '../src/lib/feed.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { feedsTouchedBy, touchedBy, areaKey, FEED_LISTS, DETAILS, feedKey, DATA_CHANGED } = await import(
  `data:text/javascript;base64,${Buffer.from(js).toString('base64')}`
);
const touched = (p) => [...feedsTouchedBy(p)].sort();
// Beispielwerte für die Pfad-Teile – die Pfade selbst sind echte Routen (test_api_routes).
const oid = 100000123, step = 4, token = 'abc';
const API = '/api/v1';

test('ein Auftrag lädt Aufträge, Stücke, Artikel, Dokumente und «zu tun» nach', () => {
  for (const p of ['/api/v1/erp/orders', `/api/v1/erp/orders/${oid}/steps/${step}/confirm`,
    `/api/v1/erp/orders/${oid}/steps/${step}/voucher`]) {
    assert.deepEqual(touched(p), ['articles', 'documents', 'instances', 'orders', 'todo'], p);
  }
});

test('Personen, Firmen, Dokumente, Zeit – je ihre Listen', () => {
  assert.deepEqual(touched(`/api/v1/erp/records/${oid}`), ['companies', 'people', 'todo']);
  assert.deepEqual(touched(`/api/v1/auth/me/addresses/${step}`), ['companies', 'people', 'todo']);
  assert.deepEqual(touched('/api/v1/erp/articles'), ['articles']);
  assert.deepEqual(touched(`/api/v1/erp/documents/${oid}/refs`), ['documents', 'todo']);
  assert.deepEqual(touched(`/api/v1/erp/time/${oid}/swipe`), ['todo']);
  assert.deepEqual(touched(`/api/v1/admin/companies/${oid}`), ['companies', 'todo']);
  assert.deepEqual(touched('/api/v1/erp/messages'), ['people', 'todo']);
});

test('Prüfen, Vorschau-Lesen und ein leerer Abgleich ändern keine Liste', () => {
  for (const p of ['/api/v1/erp/orders/validate', '/api/v1/erp/articles/validate',
    '/api/v1/erp/documents/read', '/api/v1/erp/documents/compose', '/api/v1/erp/messages/sync',
    '/api/v1/auth/passkeys/register/verify', `/api/v1/public/beleg/${token}/accept`]) {
    assert.deepEqual(touched(p), [], p);
  }
  // Genau DIESER Pfad – ein Dokument neu lesen lassen ist eine Änderung am Dokument.
  assert.deepEqual(touched(`/api/v1/erp/documents/${oid}/read`), ['documents', 'todo']);
});

test('unbekannt heisst alle Listen – und ein Präfix trifft nur ganze Pfadteile', () => {
  assert.deepEqual(touched(`${API}/erp/neu`), [...FEED_LISTS].sort());
  assert.deepEqual(touched(''), [...FEED_LISTS].sort());
  assert.deepEqual(touched(`${API}/erp/ordersx`), [...FEED_LISTS].sort());
  assert.deepEqual(touched('/api/v1/erp/records?x=1'), ['companies', 'people', 'todo']);
});

test('der Schlüssel einer Liste ist das Präfix, über das sie invalidiert wird', () => {
  assert.deepEqual([...feedKey('instances')], ['feed', 'instances']);
  assert.equal(DATA_CHANGED, 'inexxio:data-changed');
});

test('die Detailansichten hängen an derselben Tabelle', () => {
  const areas = (p) => new Set(touchedBy(p));
  const order = areas(`${API}/erp/orders/${oid}/steps/${step}/voucher`);
  for (const d of ['order', 'instance', 'article', 'stock', 'units', 'documentsOf', 'payments']) {
    assert.ok(order.has(d), `Handlung am Auftrag lädt «${d}» nicht nach`);
  }
  assert.ok(areas(`${API}/erp/documents/${oid}/refs`).has('documentsOf'), 'Kacheln am Datensatz');
  assert.ok(areas(`${API}/erp/documents`).has('document'));
  assert.ok(areas(`${API}/erp/messages`).has('messages'));
  assert.ok(areas(`${API}/erp/newsletter/${oid}/invite`).has('newsletter'));
  assert.ok(areas(`${API}/erp/messages/mailboxes/c${oid}/connect`).has('mailboxes'));
  assert.deepEqual([...areas(`${API}/erp/orders/validate`)], []);
  // Unbekannt heisst alles – auch jede Detailansicht.
  const all = areas(`${API}/erp/neu`);
  for (const d of DETAILS) assert.ok(all.has(d), d);
  assert.deepEqual([...areaKey('order')], ['order']);
  assert.deepEqual([...areaKey('orders')], ['feed', 'orders']);
});
