/**
 * ►►► **Ein Baustein je Muster** (Änderungsakte C3). ◄◄◄
 *
 * - **Eine Hover-Blase**: `data-tip` (gezeigt von `components/erp/hints.TipHost`, am `body`).
 *   Kein natives `title=` an einem Element – der Browser zeigt es nach einer Sekunde in seiner
 *   eigenen Form –, kein `role="tooltip"` und kein `content: attr(…)`-Blase daneben.
 * - **Ein Klick daneben** schliesst über `lib/use-outside.ts` – kein eigener Lauscher am Dokument.
 * - **Leer ist `NOTHING`** (`lib/when.ts`) – kein Strich als Literal.
 *
 *     node --test scripts/hints.test.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const src = resolve(dirname(fileURLToPath(import.meta.url)), '../src');

/** Elemente, an denen `title` kein Hover ist, sondern der Name (Barrierefreiheit). */
const TITLE_OK = new Map([
  ['iframe', 'der zugängliche Name eines Rahmens – ein Bildschirmleser braucht ihn'],
]);

/** Wer selbst am Dokument lauscht – und warum. */
const LISTENER_OK = new Map([
  ['lib/use-outside.ts', 'der eine Baustein'],
  ['lib/pin-point.ts', 'die Stecknadel fängt den Klick ab, bevor die Seite ihn bekommt – kein Menü'],
]);

function files(dir, ext) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return files(p, ext);
    return ext.test(n) && !p.endsWith('types/api.ts') ? [p] : [];
  });
}

/** Native `title=` an einem HTML-/SVG-Element (kleiner Anfangsbuchstabe) und `<title>`-Kinder. */
export function nativeTitles(text, name = 'x.tsx') {
  const sf = ts.createSourceFile(name, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const found = [];
  const visit = (n) => {
    if (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) {
      const tag = n.tagName.getText(sf);
      if (tag === 'title') found.push('<title>');
      if (/^[a-z]/.test(tag) && !TITLE_OK.has(tag)) {
        for (const a of n.attributes.properties) {
          if (ts.isJsxAttribute(a) && a.name.getText(sf) === 'title') found.push(`<${tag} title>`);
          if (ts.isJsxSpreadAttribute(a) && /\btitle\s*:/.test(a.getText(sf))) found.push(`<${tag} {...title}>`);
        }
      }
    }
    ts.forEachChild(n, visit);
  };
  visit(sf);
  return found;
}

/** Eine zweite Blase: `role="tooltip"` in einer Komponente, `content: attr(…)` in einem Blatt. */
export function secondTooltip(text, path) {
  if (path.endsWith('.css')) return /content\s*:\s*attr\(/.test(text) ? ['content: attr(…)'] : [];
  return /role=["']tooltip["']/.test(text) && !path.endsWith('components/erp/hints.tsx') ? ['role="tooltip"'] : [];
}

/** Ein eigener Klick-daneben-Lauscher am Dokument. */
export function ownListener(text) {
  return /document\.addEventListener\(\s*['"](mousedown|pointerdown)['"]/.test(text) ? ['Klick daneben'] : [];
}

/** Ein Strich als «nichts» – als String oder als Text im JSX. */
export function dashLiteral(text) {
  return /['"][—–]['"]|>[—–]</.test(text) ? ['Strich statt NOTHING'] : [];
}

test('keine native Hover-Blase (title=) – die eine heisst data-tip', () => {
  const bad = files(src, /\.tsx$/).flatMap((p) => nativeTitles(readFileSync(p, 'utf8'), p)
    .map((w) => `${relative(src, p)}: ${w}`));
  assert.deepEqual(bad, [], `Statt title= bitte data-tip (components/erp/hints):\n${bad.join('\n')}`);
});

test('keine zweite Blase neben hints.TipHost', () => {
  const bad = files(src, /\.(tsx|css)$/).flatMap((p) => secondTooltip(readFileSync(p, 'utf8'), p)
    .map((w) => `${relative(src, p)}: ${w}`));
  assert.deepEqual(bad, []);
});

test('ein Klick daneben über lib/use-outside – ausser mit Grund', () => {
  const bad = files(src, /\.tsx?$/).filter((p) => !LISTENER_OK.has(relative(src, p)))
    .flatMap((p) => ownListener(readFileSync(p, 'utf8')).map((w) => `${relative(src, p)}: ${w}`));
  assert.deepEqual(bad, []);
});

test('leer ist NOTHING (lib/when) – kein Strich als Literal', () => {
  const bad = files(src, /\.tsx?$/).filter((p) => !p.endsWith('lib/when.ts'))
    .flatMap((p) => dashLiteral(readFileSync(p, 'utf8')).map((w) => `${relative(src, p)}: ${w}`));
  assert.deepEqual(bad, []);
});

test('der Wächter erkennt die Bug-Form', () => {
  assert.deepEqual(nativeTitles('<button title="Löschen" />'), ['<button title>']);
  assert.deepEqual(nativeTitles("<span {...(x ? { title: 'a' } : {})} />"), ['<span {...title}>']);
  assert.deepEqual(nativeTitles('<svg><g><title>Europa</title></g></svg>'), ['<title>']);
  assert.deepEqual(nativeTitles('<Card title="Person" /><iframe title="Dokument" />'), []);
  assert.deepEqual(secondTooltip('.x::after { content: attr(data-label); }', 'a.css'), ['content: attr(…)']);
  assert.deepEqual(secondTooltip('<span role="tooltip">x</span>', 'components/erp/x.tsx'), ['role="tooltip"']);
  assert.deepEqual(ownListener("document.addEventListener('mousedown', onDoc);"), ['Klick daneben']);
  assert.deepEqual(dashLiteral("return v ?? '—';"), ['Strich statt NOTHING']);
  assert.deepEqual(dashLiteral('<span>–</span>'), ['Strich statt NOTHING']);
  assert.deepEqual(dashLiteral("`${a} – ${b}`"), []);
});
