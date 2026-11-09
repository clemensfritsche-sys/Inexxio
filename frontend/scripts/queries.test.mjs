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

import test from 'node:test';
import assert from 'node:assert/strict';
import { calls, files, parse, ts, walk } from './lib/source.mjs';

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

/** Jeder `api.<methode>(…)`-Aufruf im Körper eines `useEffect`. */
function effectCalls(sf) {
  const found = [];
  walk(sf, (n) => {
    if (ts.isCallExpression(n) && n.expression.getText() === 'useEffect' && n.arguments[0]) {
      for (const c of calls(n.arguments[0], (name) => name.startsWith('api.'))) {
        found.push(c.expression.name.text);
      }
    }
  });
  return found;
}

test('kein Lesen vom Server in einem useEffect – ausser mit Grund', () => {
  const seen = new Set();
  const bad = [];
  for (const rel of files()) {
    for (const method of effectCalls(parse(rel))) {
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
  const sf = parse('useEffect(() => { api.timeView(1).then(setView); }, []);', { text: true });
  assert.deepEqual(effectCalls(sf), ['timeView']);
  assert.deepEqual(effectCalls(parse('const run = () => api.timeView(1);', { text: true })), []);
});
