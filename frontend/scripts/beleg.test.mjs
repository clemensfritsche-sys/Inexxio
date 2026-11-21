/**
 * ►►► **Die Karte des Belegs zeigt, was der Dienst sagt** (Modul «Zahlung»). ◄◄◄
 *
 * Früher in `backend/tests/test_source_beleg.py` als Textsuche. Geprüft wird hier:
 *
 * 1. **Das Formular sperrt, was der Dienst abweisen würde** (`beleg/forms.ts`, Verhalten):
 *    eine Lieferantenrechnung geht nicht ohne Nummer, Datum, Dokument – und ohne MWST-Nr.,
 *    sobald Steuer darauf steht; eine Zahlung verlangt keine Referenz (#1058).
 * 2. **Kein `if` auf die Richtung, kein Wort des Dienstes in der Karte** (#802/#804/#848):
 *    Wörter, Verben und Titel reisen fertig mit (`label`, `ask_verb`, `charge_word`,
 *    `pay_online_word`, `attn`). Ein Vergleich auf `.direction` oder ein Rollen-Wort als Text
 *    wäre die zweite Fassung neben dem Dienst.
 * 3. **Bezahlt wird bei uns**: weder Karte noch Bezahlkarte schicken den Zahlenden weg
 *    (`window.open`, `location = …`) – der Rückweg ist der Webhook, nicht dieser Browser.
 *
 *     node --test scripts/beleg.test.mjs
 */

import test from 'node:test';
import assert from 'node:assert/strict';
import { files, find, line, load, parse, strings, ts } from './lib/source.mjs';

/** Die ganze Karte: der Einstieg, jeder Abschnitt, die Bezahlkarte. */
const CARD = ['components/erp/beleg-work.tsx', ...files('components/erp/beleg'),
  'components/erp/pay-online.tsx'];

// ─── 1. Das Formular (Verhalten) ─────────────────────────────────────────────

// `./shared` trägt die Bauteile der Karte (React) – gebraucht wird nur `unsigned`.
const forms = await load('components/erp/beleg/forms.ts', {
  './shared': "export const unsigned = (a) => String(a).replace(/^-/, '');",
});

const D = { ref_label: 'Rechnungsnummer', vat_rate: 'normal', minus: false, currency: 'CHF',
  vat_rates: [{ key: 'normal', rate: '8.1' }, { key: 'zero', rate: '0' }] };
const bill = (f) => ({ kind: 'bill', f: { amount: '100', vat: 'normal', reference: 'R-1',
  billed_on: '01.10.2026', party_uid: 'CHE-123.456.789', original: '100000123', ...f } });

test('die Lieferantenrechnung: Nummer, Datum, Dokument – und die MWST-Nr. nur mit Steuer', () => {
  assert.equal(forms.formProblem(bill({}), D), null, 'eine vollständige Rechnung ist bereit');
  for (const missing of ['reference', 'billed_on', 'original', 'amount']) {
    assert.ok(forms.formProblem(bill({ [missing]: '' }), D), `ohne «${missing}» geht sie durch`);
  }
  assert.match(forms.formProblem(bill({ reference: ' ' }), D), /Rechnungsnummer/, 'der Grund nennt die Angabe');
  assert.ok(forms.formProblem(bill({ party_uid: '' }), D), 'mit Steuer geht sie ohne MWST-Nr. durch');
  assert.equal(forms.formProblem(bill({ party_uid: '', vat: 'zero' }), D), null,
    'ohne Steuer verlangt sie eine MWST-Nr.');
});

test('eine Zahlung verlangt keine Referenz – und der Befehl trägt keine', () => {
  const pay = forms.startForm('pay', { ...D, next_payment: '50.00' });
  assert.equal(forms.formProblem(pay, D), null);
  assert.ok(!('reference' in forms.formBody(pay, D)));
  assert.ok(forms.formProblem({ kind: 'pay', f: { amount: '0', method: 'cash' } }, D), 'ein Betrag 0 geht durch');
  const back = { kind: 'refund', f: { amount: '10', method: forms.TRANSFER, iban: '' } };
  assert.match(forms.formProblem(back, D), /IBAN/, 'Geld per Überweisung zurück ohne IBAN');
});

test('was das ERP weiss, steht vorbelegt im Formular', () => {
  const f = forms.startForm('bill', { ...D, amount: '80.00', original: 100000999 });
  assert.equal(f.f.amount, '80.00');
  assert.equal(f.f.original, '100000999');
  assert.equal(forms.formBody(bill({}), D).billed_on, '2026-10-01', 'das Datum reist als Tag mit');
});

// ─── 2./3. Die Karte (Regel über den Quelltext) ─────────────────────────────

/** Wörter der Richtung und der Rolle – und die, die der Dienst fertig schickt. */
const SERVER_WORDS = [/\b(Kunden?|Lieferanten?|Einnahme|Ausgabe)\b/, /Rechnung (stellen|erfassen)/,
  /Gutschrift stellen/, /Jetzt bezahlen/, /Vorgang abschliessen|Auftrag erledigt/, /z\. ?H\./];

/** Ein Vergleich, an dem `.direction` hängt. */
function directionBranches(sf) {
  const isDir = (e) => ts.isPropertyAccessExpression(e) && e.name.text === 'direction';
  return find(sf, (n) => ts.isBinaryExpression(n)
    && [ts.SyntaxKind.EqualsEqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsEqualsToken,
      ts.SyntaxKind.EqualsEqualsToken, ts.SyntaxKind.ExclamationEqualsToken].includes(n.operatorToken.kind)
    && (isDir(n.left) || isDir(n.right)))
    .map((n) => `${line(n)}: ${n.getText()}`);
}

/** Feste Texte im Code, die ein Wort des Dienstes tragen. */
function serverWords(sf) {
  return strings(sf).filter((s) => SERVER_WORDS.some((w) => w.test(s.text)))
    .map((s) => `${line(s)}: '${s.text}'`);
}

/** Wege, den Zahlenden wegzuschicken. */
function leaves(sf) {
  const away = find(sf, (n) => {
    if (ts.isCallExpression(n)) {
      const t = n.expression.getText();
      return /(^|\.)open$/.test(t) && t.includes('window') || /location\.(assign|replace)$/.test(t);
    }
    return ts.isBinaryExpression(n) && n.operatorToken.kind === ts.SyntaxKind.EqualsToken
      && /(^|\.)location(\.href)?$/.test(n.left.getText());
  });
  return away.map((n) => `${line(n)}: ${n.getText()}`);
}

function each(check) {
  return CARD.flatMap((rel) => check(parse(rel)).map((f) => `${rel}:${f}`));
}

test('die Karte verzweigt nie auf die Richtung', () => {
  assert.ok(CARD.length > 5, 'Die Abschnitte des Belegs nicht gefunden – der Wächter wäre blind.');
  const bad = each(directionBranches);
  assert.deepEqual(bad, [], `Was Einnahme von Ausgabe unterscheidet, reist mit:\n${bad.join('\n')}`);
});

test('kein Wort der Richtung, der Rolle oder des Dienstes als Text in der Karte', () => {
  const bad = each(serverWords);
  assert.deepEqual(bad, [], `Das Wort kommt vom Server (domain/voucher):\n${bad.join('\n')}`);
});

test('die Karte schickt den Zahlenden nirgendwohin', () => {
  const bad = each(leaves);
  assert.deepEqual(bad, [], `Bezahlt wird bei uns – kein Zahllink, keine fremde Seite:\n${bad.join('\n')}`);
});

test('die Wächter erkennen ihre Bug-Form', () => {
  const sample = (t) => parse(t, { text: true });
  assert.equal(directionBranches(sample("if (d.direction === 'in') x();")).length, 1);
  assert.equal(directionBranches(sample("if ('out' !== row.direction) x();")).length, 1);
  assert.equal(directionBranches(sample('const w = d.ask_verb;')).length, 0);
  assert.equal(serverWords(sample("const t = 'Kunde';")).length, 1);
  assert.equal(serverWords(sample('const t = `Rechnung stellen`;')).length, 1);
  assert.equal(serverWords(sample("const t = 'z. H. ' + n;")).length, 1);
  assert.equal(serverWords(sample('// Kunde im Kommentar\nconst t = d.label;')).length, 0);
  assert.equal(leaves(sample('window.open(url);')).length, 1);
  assert.equal(leaves(sample('window.location.href = url;')).length, 1);
  assert.equal(leaves(sample('location.assign(url);')).length, 1);
  assert.equal(leaves(sample('const back = window.location.href;')).length, 0);
});
