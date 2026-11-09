/**
 * ►►► **Was die Oberfläche vom Server liest, ist eine Query** (Änderungsakte U7). ◄◄◄
 *
 * Ein `useEffect`, der `api.…` aufruft und das Ergebnis in einen eigenen Zustand legt, ist ein
 * zweiter Lade-Weg: kein Cache, kein Nachladen nach einer Änderung (`lib/feed.TOUCHES`), keine
 * Meldung bei einem Fehler. Gelesen wird über `useQuery` (Schlüssel aus `lib/queries.qk`).
 * Erlaubt ist ein Aufruf in einem Effekt nur, wo er **keine** Lesestelle ist (eine Handlung,
 * ein Abgleich) oder wo es keinen Query-Client gibt – und dann steht er hier mit Grund.
 *
 *     node --test scripts/queries.test.mjs
 */

import { readFileSync, readdirSync, statSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join, relative, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../src');

/** Datei · Methode → warum es hier ein Effekt sein darf. */
const ALLOWED = new Map([
  ['app/(auth)/login/page.tsx · getMe', 'die Anmeldung selbst – vor jedem Query-Client'],
  ['components/layout/account-sync.tsx · getMe', 'der Anzeige-Cache der Website-Shell, ausserhalb des ERP'],
  ['components/auth/passkey-nudge.tsx · listPasskeys', 'öffentliche Seiten – dort gibt es keinen Query-Client'],
  ['components/beleg/document-page.tsx · publicDocument', 'öffentliche Seite, über einen Link, ohne Anmeldung'],
  ['components/beleg/legal-page.tsx · publicLegal', 'öffentliche Seite (AGB, Datenschutz, Impressum)'],
  ['app/(erp)/erp/verbinden/page.tsx · mcpRequest', 'einmal je Aufruf – der signierte Auftrag läuft nach zehn Minuten ab'],
  ['lib/use-maps-key.ts · getMapsKey', 'auch ausserhalb eines Query-Clients (Konto, Website-Rahmen); ein Merker je Seite'],
  ['components/erp/address-book.tsx · addAddress', 'eine Handlung (speichern), kein Lesen'],
  ['components/erp/capture/handgriff-card.tsx · probeHandgriff', 'ein Probelauf (Handlung), kein Lesen'],
  ['components/erp/document-detail.tsx · readDocumentLater', 'eine Handlung: die KI liest nach'],
  ['components/erp/document-draft.tsx · readDraft', 'eine Handlung: die KI liest den Entwurf'],
  ['lib/assistant.ts · refreshPins', 'eine Handlung: das Wissen neu wählen'],
  ['lib/use-mail-sync.ts · syncMail', 'der Abgleich der Postfächer (Handlung im Takt der Seite)'],
  ['components/erp/communication/composer.tsx · createMessage', 'eine Handlung: die Nachricht senden'],
  ['lib/use-recorder.ts · startRecording', 'eine Handlung: die Aufnahme beginnen'],
  ['lib/use-recorder.ts · stopRecording', 'eine Handlung: die Aufnahme beenden (auch beim Verlassen)'],
  ['lib/use-recorder.ts · recordingChunk', 'eine Handlung: ein Stück der Aufnahme hochladen'],
  ['lib/use-url-params.ts · resolveObject', 'einmal je Seitenaufruf: eine Nummer aus der Adresse öffnen'],
]);

function files(dir) {
  return readdirSync(dir).flatMap((n) => {
    const p = join(dir, n);
    if (statSync(p).isDirectory()) return files(p);
    return /\.tsx?$/.test(n) && !p.endsWith('types/api.ts') ? [p] : [];
  });
}

/** Jeder `api.<methode>(…)`-Aufruf im Körper eines `useEffect`. */
function effectCalls(path) {
  const text = readFileSync(path, 'utf8');
  const sf = ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const found = [];
  const inside = (node) => {
    if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
        && ts.isIdentifier(node.expression.expression) && node.expression.expression.text === 'api') {
      found.push(node.expression.name.text);
    }
    ts.forEachChild(node, inside);
  };
  const visit = (node) => {
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression) && node.expression.text === 'useEffect'
        && node.arguments[0]) {
      inside(node.arguments[0]);
    }
    ts.forEachChild(node, visit);
  };
  visit(sf);
  return found;
}

test('kein Lesen vom Server in einem useEffect – ausser mit Grund', () => {
  const seen = new Set();
  const bad = [];
  for (const path of files(src)) {
    const rel = relative(src, path);
    for (const method of effectCalls(path)) {
      const key = `${rel} · ${method}`;
      seen.add(key);
      if (!ALLOWED.has(key)) bad.push(key);
    }
  }
  assert.deepEqual(bad, [], `Lesen über useQuery (lib/queries.qk), nicht im Effekt:\n${bad.join('\n')}`);
  const stale = [...ALLOWED.keys()].filter((k) => !seen.has(k));
  assert.deepEqual(stale, [], `Ausnahmen ohne Fundstelle – bitte streichen:\n${stale.join('\n')}`);
});

test('der Wächter erkennt die Bug-Form', () => {
  const sample = join(here, 'queries.sample.tmp.tsx');
  const text = "useEffect(() => { api.timeView(1).then(setView); }, []);";
  const sf = ts.createSourceFile(sample, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const calls = [];
  const inside = (n) => {
    if (ts.isCallExpression(n) && ts.isPropertyAccessExpression(n.expression)) calls.push(n.expression.name.text);
    ts.forEachChild(n, inside);
  };
  ts.forEachChild(sf, function walk(n) {
    if (ts.isCallExpression(n) && ts.isIdentifier(n.expression) && n.expression.text === 'useEffect') inside(n.arguments[0]);
    ts.forEachChild(n, walk);
  });
  assert.ok(calls.includes('timeView'));
});
