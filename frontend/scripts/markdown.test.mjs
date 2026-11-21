/**
 * ►►► **Die Antwort der KI als Markdown** (`src/components/erp/capture/markdown.tsx`). ◄◄◄
 *
 * Geprüft am echten Bauteil (transpiliert, mit React auf dem Server gezeichnet). Die Bug-Formen:
 * HTML aus der Antwort wird zu HTML (ein `<script>`, ein `onerror`) · ein Link ausser http(s)
 * (`javascript:`) wird klickbar · Listen, Überschriften, fett, Code fallen als Sternchen und Rauten
 * in den Text · ein Absatz verliert seine Zeilenumbrüche.
 *
 *     node --test scripts/markdown.test.mjs
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
// In node_modules, damit `react` sich von dort auflöst wie im Bauteil.
const out = resolve(here, '../node_modules/.cache/markdown-test');
mkdirSync(out, { recursive: true });
const js = ts.transpileModule(readFileSync(resolve(here, '../src/components/erp/capture/markdown.tsx'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
writeFileSync(resolve(out, 'markdown.mjs'), js);
const { Markdown } = await import(pathToFileURL(resolve(out, 'markdown.mjs')).href);
const React = (await import('react')).default;
const { renderToStaticMarkup } = (await import('react-dom/server')).default;

const html = (text) => renderToStaticMarkup(React.createElement(Markdown, { text }));

test('Absätze, Überschrift, Listen, fett, kursiv, Code – als Form, nicht als Zeichen', () => {
  const h = html('## Offen\n\nZwei **wichtige** Punkte, *kurz*:\n- Telefon `079`\n- Adresse\n\n1. eins\n2. zwei\n\nZeile a\nZeile b');
  assert.match(h, /<p class="erp-md-h">Offen<\/p>/);
  assert.match(h, /<strong>wichtige<\/strong>/);
  assert.match(h, /<em>kurz<\/em>/);
  assert.match(h, /<ul><li>Telefon <code>079<\/code><\/li><li>Adresse<\/li><\/ul>/);
  assert.match(h, /<ol><li>eins<\/li><li>zwei<\/li><\/ol>/);
  assert.match(h, /<p>Zeile a<br\/>Zeile b<\/p>/);
  assert.doesNotMatch(h, /\*\*|##/);
});

test('Code-Block bleibt, wie er ist', () => {
  assert.match(html('```\na **b**\n```'), /<pre><code>a \*\*b\*\*<\/code><\/pre>/);
});

test('HTML in der Antwort bleibt Text, nur http(s) wird ein Link', () => {
  const h = html('<script>alert(1)</script> <img src=x onerror=alert(1)> [x](javascript:alert(1)) [ok](https://inexxio.ch)');
  assert.doesNotMatch(h, /<script|<img|href="javascript/);
  assert.match(h, /&lt;script&gt;/);
  assert.match(h, /<a href="https:\/\/inexxio.ch" target="_blank" rel="noreferrer noopener">ok<\/a>/);
});
