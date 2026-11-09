/**
 * ►►► **Regeln des Prozesses, die jede Oberfläche erbt** – auf dem Syntaxbaum geprüft. ◄◄◄
 *
 * Was ein Typ nicht sagen kann und keine Funktion zum Fahren hat. Früher standen diese Regeln
 * als Textsuchen in `backend/tests/test_source_process.py` / `test_source_capture.py` – an
 * einzelne Dateien und Schreibweisen gebunden. Hier gilt jede für das ganze Frontend:
 *
 * 1. **Anlegen = Freigeben, an EINER Stelle**: ein Auftrag entsteht nur in
 *    `order-detail.tsx`, ein Artikel nur in `article-detail.tsx` – nie in einem Effekt oder
 *    Auto-Save (im Vorbeitippen). Kein Shortcut, kein Modul, kein «Holen lassen» legt selbst an:
 *    sie öffnen denselben Entwurf (#678, #690, Testnotiz #386).
 * 2. **Bestand und Instanz werden gelesen, nie bearbeitet**: dort steht keine schreibende
 *    Anfrage (Material entsteht über einen Auftrag #678, gelöscht wird nie #679, erfasst am
 *    Modul #677).
 * 3. **Jede Datei eines Moduls ist ein Dokument, ein Bild entsteht in der Kamera**: lose in den
 *    Korb lädt nur die gezeichnete Unterschrift; die Aufnahme hat keinen Dateidialog (#718/#720).
 * 4. **Ein Halt verdrängt nichts**: «nicht bestanden» ist eine Auskunft neben dem Weg nach vorn,
 *    nie die eine Seite einer Weiche (`held ? <Entscheidung/> : <Scan/>` war die Sackgasse).
 * 5. **«Beim Ausführen definieren» ist ein Satz an einer Stelle** (`scan.RUNTIME_CHOICE`, #786).
 *
 * Dass die Oberfläche eine Eigenschaft des Moduls fragt, nie seinen Typ (`'bewegen'`), prüft
 * `house.test.mjs`.
 *
 *     node --test scripts/process-ui.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { calleeName, calls, files, find, jsx, line, parse, ts } from './lib/source.mjs';

const ALL = files();
const at = (rel) => (n) => `${rel}:${line(n)}`;

// ─── 1. Anlegen = Freigeben, an einer Stelle ─────────────────────────────────

const CREATES = { 'api.createOrder': 'components/erp/order-detail.tsx',
  'api.createArticle': 'components/erp/article-detail.tsx' };
/** Wo nie angelegt werden darf: was von selbst läuft, statt auf «Freigeben». */
const BY_ITSELF = /^(useEffect|useLayoutEffect|useAutosave\w*)$/;

function creations(sf, rel) {
  const bad = [];
  for (const call of calls(sf, (name) => name in CREATES)) {
    const name = calleeName(call);
    if (CREATES[name] !== rel) bad.push(`${rel}:${line(call)} ${name} – angelegt wird nur in ${CREATES[name]}`);
    for (let p = call.parent; p; p = p.parent) {
      if (ts.isCallExpression(p) && BY_ITSELF.test(calleeName(p))) {
        bad.push(`${rel}:${line(call)} ${name} in ${calleeName(p)} – angelegt wird mit «Freigeben»`);
      }
    }
  }
  return bad;
}

test('ein Auftrag und ein Artikel entstehen an je einer Stelle, mit «Freigeben»', () => {
  const bad = ALL.flatMap((rel) => creations(parse(rel), rel));
  assert.deepEqual(bad, [], bad.join('\n'));
  for (const [name, rel] of Object.entries(CREATES)) {
    assert.ok(calls(parse(rel), name).length > 0, `${name} fehlt in ${rel} – der Wächter wäre blind`);
  }
});

// ─── 2. Bestand und Instanz: nur lesen ──────────────────────────────────────

const READ_ONLY = ['components/erp/stock-view.tsx', 'components/erp/stock-bar.tsx',
  'components/erp/unit-numbers.tsx', 'components/erp/instance-detail.tsx'];

/** Die Methoden von `lib/api.ts`, die nur lesen: jede `this.call('get', …)`, keine andere Art. */
function readingMethods(sf = parse('lib/api.ts')) {
  const reads = new Set();
  for (const m of find(sf, ts.isMethodDeclaration)) {
    const verbs = calls(m, 'this.call').map((c) => c.arguments[0]?.text);
    const methods = find(m, (n) => ts.isPropertyAssignment(n) && n.name.getText() === 'method')
      .map((n) => n.initializer.getText());
    if (verbs.length && verbs.every((v) => v === 'get') && !methods.length) reads.add(m.name.getText());
  }
  return reads;
}

function writes(sf, rel, reads) {
  return calls(sf, (name) => name.startsWith('api.'))
    .filter((c) => !reads.has(c.expression.name.text))
    .map((c) => `${rel}:${line(c)} ${calleeName(c)}`);
}

test('Bestand und Instanz lesen nur – dort wird nichts angelegt, geändert oder gelöscht', () => {
  const reads = readingMethods();
  assert.ok(reads.has('getArticleStock') && !reads.has('createOrder'), 'die Lesemethoden nicht erkannt – der Wächter wäre blind');
  const bad = READ_ONLY.flatMap((rel) => writes(parse(rel), rel, reads));
  assert.deepEqual(bad, [], `Schreibende Anfrage, wo nur gelesen wird:\n${bad.join('\n')}`);
});

// ─── 3. Datei = Dokument, Bild = Kamera ─────────────────────────────────────

const LOOSE_UPLOAD = 'components/erp/signature-pad.tsx';
const CAMERA_ONLY = 'components/erp/photo-capture.tsx';

function looseUploads(sf, rel) {
  return rel === LOOSE_UPLOAD ? [] : calls(sf, 'api.uploadAttachment').map((c) => `${at(rel)(c)}`);
}

function fileInputs(sf) {
  return jsx(sf, 'input').map((n) => line(n));
}

test('lose in den Korb lädt nur die Unterschrift; die Aufnahme hat keinen Dateidialog', () => {
  const bad = ALL.flatMap((rel) => looseUploads(parse(rel), rel));
  assert.deepEqual(bad, [], `Eine Datei eines Moduls wird ein Dokument (document-draft), keine lose Datei:\n${bad.join('\n')}`);
  assert.deepEqual(fileInputs(parse(CAMERA_ONLY)), [], 'die Aufnahme hat wieder ein <input> – ein zweiter Weg zu einem Nachweis');
  assert.ok(calls(parse(CAMERA_ONLY), 'useCamera').length, 'die Aufnahme nutzt die Kamera nicht mehr – der Wächter wäre blind');
});

// ─── 4. Ein Halt verdrängt nichts ───────────────────────────────────────────

const isHeld = (n) => ts.isPropertyAccessExpression(n) && n.name.text === 'held';

function heldSwitches(sf) {
  return find(sf, (n) => ts.isConditionalExpression(n)
    && (isHeld(n.condition) || find(n.condition, isHeld).length > 0))
    .map((n) => line(n));
}

test('ein Halt steht neben dem Weg nach vorn, nie an seiner Stelle', () => {
  const bad = ALL.flatMap((rel) => heldSwitches(parse(rel)).map((l) => `${rel}:${l}`));
  assert.deepEqual(bad, [], `«held ? A : B» verdrängt den Scan – den Halt als «held && …» daneben zeigen:\n${bad.join('\n')}`);
});

// ─── 5. Ein Satz, eine Stelle ───────────────────────────────────────────────

function runtimeSentences(sf) {
  return find(sf, (n) => (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isJsxText(n))
    && /Beim Ausführen/i.test(n.text)).map((n) => line(n));
}

test('«Beim Ausführen definieren» steht nur in lib/scan', () => {
  const bad = ALL.filter((rel) => rel !== 'lib/scan.ts')
    .flatMap((rel) => runtimeSentences(parse(rel)).map((l) => `${rel}:${l}`));
  assert.deepEqual(bad, [], `scan.RUNTIME_CHOICE lesen, nicht neu schreiben:\n${bad.join('\n')}`);
  assert.equal(runtimeSentences(parse('lib/scan.ts')).length, 1, 'der eine Satz fehlt – der Wächter wäre blind');
});

// ─── Gegenprobe ─────────────────────────────────────────────────────────────

test('die Wächter erkennen ihre Bug-Form', () => {
  const s = (t) => parse(t, { text: true });
  // 1
  assert.equal(creations(s('useAutosaveValue(v, () => api.createArticle(p));'), 'components/erp/article-detail.tsx').length, 1);
  assert.equal(creations(s('const go = () => api.createOrder(d);'), 'components/erp/capture-work.tsx').length, 1);
  assert.equal(creations(s('async function release() { await api.createOrder(d); }'), 'components/erp/order-detail.tsx').length, 0);
  // 2
  const reads = readingMethods(s(`class A {
    getX(id) { return this.call('get', '/x', {}); }
    addX(b) { return this.call('post', '/x', { body: b }); }
    upload(f) { return this.request('/y', { method: 'POST', body: f }); }
  }`));
  assert.deepEqual([...reads], ['getX']);
  assert.deepEqual(writes(s('api.getX(1); api.addX(2); api.upload(3);'), 'x', reads).length, 2);
  // 3
  assert.equal(looseUploads(s('await api.uploadAttachment(file);'), 'components/erp/beleg/invoice.tsx').length, 1);
  assert.equal(fileInputs(s('const x = <input type="file" accept="image/*" />;')).length, 1);
  // 4
  assert.equal(heldSwitches(s('const x = work.held ? <Hold /> : <Scan />;')).length, 1);
  assert.equal(heldSwitches(s('const x = <>{work.held && <Hold />}<Scan /></>;')).length, 0);
  // 5
  assert.equal(runtimeSentences(s('const x = <span>Beim Ausführen scannen</span>;')).length, 1);
  assert.equal(runtimeSentences(s("const p = 'Leer: freie Wahl beim Ausführen';")).length, 1);
  assert.equal(runtimeSentences(s('const p = RUNTIME_CHOICE;')).length, 0);
});
