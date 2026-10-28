/**
 * ►►► **Als Link nur, was ins Web führt** (`src/lib/web-link.ts`). ◄◄◄
 *
 * Der CAD-Link eines Artikels stand ungeprüft in `<a href>` – `javascript:…` lief beim Klick.
 *
 *     node --test scripts/web-link.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const js = ts.transpileModule(readFileSync(resolve(here, '../src/lib/web-link.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { webHref } = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

test('http und https sind Links', () => {
  for (const ok of ['https://cad.onshape.com/documents/1', 'http://example.ch', 'HTTPS://X.CH/a']) {
    assert.equal(webHref(ok), ok);
  }
});

test('alles andere ist Text', () => {
  for (const bad of ['javascript:alert(1)', ' javascript:alert(1)', 'JaVaScRiPt:alert(1)',
    'data:text/html,<script>1</script>', 'vbscript:x', '//evil.example', 'cad.onshape.com',
    'https://', 'https:///x', 'ftp://x.ch', '', null, undefined]) {
    assert.equal(webHref(bad), null, String(bad));
  }
});

test('der Baustein fragt die Regel, bevor er ein <a> setzt', () => {
  const fields = readFileSync(resolve(here, '../src/components/erp/detail-frame.tsx'), 'utf8');
  const read = fields.match(/export function ReadField[\s\S]*?\n}\n/);
  assert.ok(read, 'ReadField nicht gefunden');
  assert.match(read[0], /webHref\(link\)/);
  assert.doesNotMatch(read[0], /href=\{link\}/);
});
