/**
 * ►►► **Was das Design-System still verschluckt, fällt hier auf.** ◄◄◄
 *
 * Eine unbekannte CSS-Variable, eine Klasse ohne Stil, ein Farbwert der Alt-Palette – nichts
 * davon bricht den Build; es sieht nur *fast* richtig aus. Früher als Textsuche in
 * `backend/tests/test_source_ui.py`. Je Regel ein Wächter, je Wächter die Gegenprobe:
 *
 * 1. **Jede `var(--x)` ohne Rückfall ist definiert** – im Token-Blatt, in `globals.css`, als
 *    Angabe am Element oder im Stylesheet des gemeinsamen Kopfs (`--site-header-h`). Gefunden:
 *    `var(--ok)`/`var(--warn)` färbten nichts, eine Box verlor ihren Rahmen (#1032).
 * 2. **Jede `ix-`-Klasse im Markup hat einen Stil** (Frontend oder Website) – die Rückkehrseite
 *    der Anmeldung trug `.ix-login-bg` und sah darum nicht aus wie der Dialog.
 * 3. **Die Alt-Palette ist weg, auch als Hex** (Tailwinds slate/gray/amber/green/red/sky), das
 *    Markenrot steht nur als Token, die Warnfarbe nie als Rohtoken (F-20/F-50/F-51). Die
 *    Gebietskarte trägt bewusst eine eigene kategoriale Palette.
 * 4. **Ein Zustand ist Punkt + Wort über `fields.StatusDot`** – kein selbst gebauter Punkt.
 * 5. **Das Mikro-Label steht einmal** (`fields.MICRO_LABEL`) – keine Versalien daneben (F-43).
 * 6. **Ein Dialog hat einen Namen, ein Reiter sagt, ob er gewählt ist** (Bildschirmleser).
 *
 *     node --test scripts/design.test.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import { SRC, files, find, jsx, line, parse, read, stripComments, ts } from './lib/source.mjs';

const ROOT = resolve(SRC, '../..');

/** Alle Dateien mit einer Endung unter einem Verzeichnis (absolut). */
function under(dir, ...ext) {
  const walk = (abs) => readdirSync(abs).flatMap((name) => {
    const p = join(abs, name);
    if (statSync(p).isDirectory()) return walk(p);
    return ext.some((e) => name.endsWith(e)) ? [p] : [];
  });
  return walk(dir);
}

const CSS = under(SRC, '.css');
const code = (rel) => stripComments(read(rel));

// ─── 1. CSS-Variablen ────────────────────────────────────────────────────────

/** Benutzt ohne Rückfall · definiert (Deklaration `--x:` oder Name als Text `'--x'`). */
function variables(text) {
  return {
    used: [...text.matchAll(/var\((--[a-z0-9-]+)\s*\)/g)].map((m) => m[1]),
    defined: [...text.matchAll(/(--[a-z0-9-]+)\s*:/g), ...text.matchAll(/['"](--[a-z0-9-]+)['"]/g)].map((m) => m[1]),
  };
}

test('jede CSS-Variable ohne Rückfall ist irgendwo definiert', () => {
  const sources = [...CSS.map((p) => readFileSync(p, 'utf8')), ...files().map(code),
    readFileSync(resolve(ROOT, 'website/scripts/export-shell.mjs'), 'utf8')];
  const defined = new Set(sources.flatMap((t) => variables(t).defined));
  const where = [...CSS.map((p) => [relative(SRC, p), readFileSync(p, 'utf8')]), ...files().map((r) => [r, code(r)])];
  const bad = where.flatMap(([rel, t]) => variables(t).used.filter((v) => !defined.has(v)).map((v) => `${rel}: ${v}`));
  assert.ok(defined.has('--fg-1') && defined.size > 50, 'Die Tokens nicht gelesen – der Wächter wäre blind.');
  assert.deepEqual([...new Set(bad)], [], `Benutzt, aber nirgends definiert – erzeugt still nichts:\n${bad.join('\n')}`);
});

// ─── 2. ix-Klassen ───────────────────────────────────────────────────────────

/** Die `ix-`-Klassen in `className` (Text, Vorlage, Ausdruck) – ohne `ix-shell` (Website-Build). */
function ixClasses(sf) {
  const out = new Set();
  for (const attr of find(sf, (n) => ts.isJsxAttribute(n) && n.name.getText() === 'className' && n.initializer)) {
    const texts = find(attr, (n) => ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n)
      || ts.isTemplateHead(n) || ts.isTemplateMiddle(n) || ts.isTemplateTail(n));
    if (ts.isStringLiteral(attr.initializer)) texts.push(attr.initializer);
    for (const t of texts) for (const m of t.text.matchAll(/(?<![\w-])(ix-[\w-]*\w)/g)) out.add(m[1]);
  }
  out.delete('ix-shell');
  return out;
}

test('jede ix-Klasse im Markup hat einen Stil', () => {
  const styles = [...CSS, ...under(resolve(ROOT, 'website/src'), '.css', '.astro')]
    .map((p) => readFileSync(p, 'utf8')).join('\n');
  const styled = (c) => new RegExp(`\\.${c.replace(/[-]/g, '\\-')}(?![\\w-])`).test(styles);
  const bad = files().filter((r) => r.endsWith('.tsx'))
    .flatMap((rel) => [...ixClasses(parse(rel))].filter((c) => !styled(c)).map((c) => `${rel}: ${c}`));
  assert.deepEqual(bad, [], `Klassen ohne Stil – sie erzeugen still nichts:\n${bad.join('\n')}`);
});

// ─── 3. Alt-Palette ──────────────────────────────────────────────────────────

const OLD_HEX = new RegExp('#(0F172A|1E293B|334155|475569|64748B|94A3B8|CBD5E1|E2E8F0|F1F5F9|F8FAFC|'
  + '111827|1F2937|374151|4B5563|6B7280|9CA3AF|D1D5DB|E5E7EB|F3F4F6|F9FAFB|'
  + 'F59E0B|D97706|B45309|FFFBEB|16A34A|15803D|F0FDF4|BBF7D0|DC2626|FEF2F2|FCA5A5|'
  + '0284C7|F0F9FF|BAE6FD|2563EB|E51A14)\\b|--ix-red\\b|var\\(--color-warning', 'i');
/** Die Gebietskarte malt Gesellschaften, keine Zustände; das Token-Blatt ist die Quelle. */
const OWN_PALETTE = new Set(['components/erp/territory-map.tsx']);

function oldColours(text) {
  return [...text.matchAll(new RegExp(OLD_HEX.source, 'gi'))].map((m) => m[0]);
}

test('die Alt-Palette ist weg – auch als Hex, das Rot nur als Token', () => {
  const css = CSS.map((p) => relative(SRC, p)).filter((r) => !r.startsWith('styles/design-system/'))
    .map((r) => [r, read(r)]);
  const bad = [...files().filter((r) => !OWN_PALETTE.has(r)).map((r) => [r, code(r)]), ...css]
    .flatMap(([rel, t]) => oldColours(t).map((c) => `${rel}: ${c}`));
  assert.deepEqual(bad, [], `Farbe über die Tokens (colors_and_type.css):\n${bad.join('\n')}`);
});

// ─── 4. Zustandspunkt · 5. Mikro-Label ───────────────────────────────────────

/** Punkte, die kein Zustand sind – mit Grund. */
const NOT_A_STATE = new Map([
  ['components/erp/territory-map.tsx', 'die Farbe einer Gesellschaft auf der Karte'],
  ['components/erp/time/time-calendar.tsx', 'eine Markierung in der Ecke eines Kalendertags'],
  ['components/erp/fields.tsx', 'StatusDot selbst'],
  ['components/erp/controls.tsx', 'die Empfehlung am Schieber (IconSwitch.mark)'],
]);

const prop = (obj, name) => obj.properties.find((p) => ts.isPropertyAssignment(p) && p.name.getText() === name)?.initializer;
const small = (e) => e && ts.isNumericLiteral(e) && Number(e.text) >= 5 && Number(e.text) <= 8;

/** Ein Stil 5–8 px im Quadrat, rund oder gefüllt – ein selbst gebauter Punkt. */
function handDots(sf) {
  return find(sf, (n) => ts.isObjectLiteralExpression(n) && small(prop(n, 'width')) && small(prop(n, 'height'))
    && (prop(n, 'background') || prop(n, 'backgroundColor') || /rounded-full/.test(n.parent?.parent?.parent?.getText() ?? '')
      || (ts.isNumericLiteral(prop(n, 'borderRadius') ?? n) && Number(prop(n, 'borderRadius').text) >= 999)))
    .map((n) => `${line(n)}: ${n.getText().slice(0, 50)}`);
}

test('ein Zustandspunkt ist fields.StatusDot – kein Eigenbau', () => {
  const stale = [...NOT_A_STATE.keys()].filter((r) => !files().includes(r));
  assert.deepEqual(stale, [], 'Ausnahmen ohne Datei – bitte streichen');
  const bad = files().filter((r) => r.endsWith('.tsx') && !NOT_A_STATE.has(r))
    .flatMap((rel) => handDots(parse(rel)).map((f) => `${rel}:${f}`));
  assert.deepEqual(bad, [], `Status = Punkt + Wort über StatusDot:\n${bad.join('\n')}`);
});

/** Wo Versalien bewusst stehen: das Mikro-Label selbst, der Abschnittskopf, das Zahlungsformular des Dienstes. */
const UPPERCASE_HOME = new Set(['components/erp/fields.tsx', 'components/erp/detail-frame.tsx',
  'components/erp/module-ui.tsx', 'components/erp/pay-online.tsx']);

function uppercase(sf) {
  return find(sf, (n) => ts.isPropertyAssignment(n) && n.name.getText() === 'textTransform'
    && ts.isStringLiteral(n.initializer) && n.initializer.text === 'uppercase').map((n) => `${line(n)}`);
}

test('das Mikro-Label steht einmal – keine Versalien daneben', () => {
  const bad = files().filter((r) => !UPPERCASE_HOME.has(r))
    .flatMap((rel) => uppercase(parse(rel)).map((f) => `${rel}:${f}`));
  assert.deepEqual(bad, [], `Beschriftung über fields.MICRO_LABEL / Label:\n${bad.join('\n')}`);
});

// ─── 6. Bildschirmleser ──────────────────────────────────────────────────────

const attrOf = (el, name) => el.attributes.properties.find((a) => ts.isJsxAttribute(a) && a.name.getText() === name);
const roleIs = (el, role) => attrOf(el, 'role')?.initializer?.text === role;

function unnamed(sf) {
  return jsx(sf).filter((el) => (roleIs(el, 'dialog') && !attrOf(el, 'aria-label') && !attrOf(el, 'aria-labelledby'))
    || (roleIs(el, 'tab') && !attrOf(el, 'aria-selected'))).map((el) => `${line(el)}: role=${attrOf(el, 'role').initializer.text}`);
}

test('ein Dialog hat einen Namen, ein Reiter sagt, ob er gewählt ist', () => {
  const bad = files().filter((r) => r.endsWith('.tsx')).flatMap((rel) => unnamed(parse(rel)).map((f) => `${rel}:${f}`));
  assert.deepEqual(bad, [], `aria-label/aria-labelledby am Dialog, aria-selected am Reiter:\n${bad.join('\n')}`);
});

test('die Wächter erkennen ihre Bug-Form', () => {
  const sample = (t) => parse(t, { text: true });
  assert.deepEqual(variables("a { color: var(--warn); } b { --ok: 1; }"), { used: ['--warn'], defined: ['--ok'] });
  assert.deepEqual(variables('a { color: var(--warn, red); }').used, []);
  assert.deepEqual([...ixClasses(sample('const a = <div className="ix-login-bg x" />;'))], ['ix-login-bg']);
  assert.deepEqual([...ixClasses(sample('const a = <div className={`ix-row ${on ? "ix-on" : ""}`} />;'))].sort(), ['ix-on', 'ix-row']);
  assert.deepEqual(oldColours("const c = '#64748b'; const r = 'var(--ix-red)';"), ['#64748b', '--ix-red']);
  assert.deepEqual(oldColours("const c = 'var(--inexxio)';"), []);
  assert.equal(handDots(sample("const a = <span style={{ width: 7, height: 7, borderRadius: 999 }} />;")).length, 1);
  assert.equal(handDots(sample("const a = <span style={{ width: 6, height: 6, background: c }} />;")).length, 1);
  assert.equal(handDots(sample("const a = <span style={{ width: 16, height: 16, borderRadius: 999 }} />;")).length, 0);
  assert.equal(uppercase(sample("const s = { textTransform: 'uppercase' };")).length, 1);
  assert.equal(unnamed(sample('const a = <div role="dialog" aria-modal="true" />;')).length, 1);
  assert.equal(unnamed(sample('const a = <button role="tab" />;')).length, 1);
  assert.equal(unnamed(sample('const a = <div role="dialog" aria-label="Scannen" />;')).length, 0);
});
