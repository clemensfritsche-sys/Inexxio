/**
 * ►►► **Die Datums-Ausgabe hat einen Wächter je Stufe** (Testnotiz #1014). ◄◄◄
 *
 * *«Dies ist bereits die dritte Meldung zu dieser Regel. Sichere die Funktion mit Unit-
 * Tests für alle Stufen ab.»*
 *
 * **Der gemeldete Fehler lag nicht in dieser Funktion**, und das ist der Grund, warum es
 * ihn dreimal gab: `when()` bekam einen **reinen Tag** (`booked_on`, «2026-09-16») und
 * antwortete korrekt «Heute» – aus einem Datum ohne Uhrzeit lässt sich «vor 5 Minuten»
 * nicht ableiten, und es zu erfinden wäre schlimmer. Gefehlt hat der **Zeitpunkt**; er
 * reist jetzt als `booked_at` mit. Diese Prüfungen halten beides fest: jede Stufe **und**
 * die Regel, dass ein reiner Tag die Stunden-Kaskade überspringt.
 *
 * Gefahren mit dem Node-eigenen Testläufer gegen die **echte** Quelle – `src/lib/when.ts`
 * wird mit dem TypeScript des Hauses transpiliert, nicht nachgebaut: eine zweite Fassung
 * wäre genau die Stelle, an der ein Wächter grün bleibt, während die Oberfläche etwas
 * anderes tut.
 *
 *     node --test scripts/when.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const source = readFileSync(resolve(here, '../src/lib/when.ts'), 'utf8');
const js = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const { when, day, whenTitle, formatWhen, NOTHING } =
  await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

/** Der feste Bezugspunkt aller Prüfungen – ein Zeitpunkt, keine Uhr. */
const NOW = new Date(2026, 8, 16, 17, 58, 30);
const at = (...a) => new Date(...a);

test('gerade eben – darunter ist jede Zahl eine erfundene Genauigkeit', () => {
  assert.equal(when(at(2026, 8, 16, 17, 58, 0), NOW), 'gerade eben');
  assert.equal(when(at(2026, 8, 16, 17, 58, 29), NOW), 'gerade eben');
});

test('Minuten – die Stufe, die dreimal gemeldet wurde', () => {
  assert.equal(when(at(2026, 8, 16, 17, 53, 30), NOW), 'vor 5 Minuten');
  assert.equal(when(at(2026, 8, 16, 17, 57, 20), NOW), 'vor 1 Minute');
  assert.equal(when(at(2026, 8, 16, 17, 0, 0), NOW), 'vor 58 Minuten');
});

test('Stunden – und der Singular ist eine Angabe, keine Rechnung', () => {
  assert.equal(when(at(2026, 8, 16, 14, 58, 30), NOW), 'vor 3 Stunden');
  assert.equal(when(at(2026, 8, 16, 16, 58, 30), NOW), 'vor 1 Stunde');
});

test('Gestern beginnt, wo Stunden zu zählen aufhört', () => {
  // 20 Stunden her war gestern *und* ist «vor 20 Stunden» – die genauere Aussage gewinnt.
  assert.equal(when(at(2026, 8, 15, 21, 58, 30), NOW), 'vor 20 Stunden');
  assert.equal(when(at(2026, 8, 15, 10, 0, 0), NOW), 'Gestern');
});

test('Tage – vorwärts wie rückwärts', () => {
  assert.equal(when(at(2026, 8, 13, 10, 0, 0), NOW), 'vor 3 Tagen');
  // Morgen früh ist noch keine 24 Stunden hin – dort gewinnt weiterhin die Stunde.
  assert.equal(when(at(2026, 8, 17, 10, 0, 0), NOW), 'in 16 Stunden');
  assert.equal(when(at(2026, 8, 17, 23, 0, 0), NOW), 'Morgen');
  assert.equal(when(at(2026, 8, 21, 10, 0, 0), NOW), 'in 5 Tagen');
});

test('älter als eine Woche: das Datum – die Jahreszahl nur, wenn sie etwas sagt', () => {
  assert.equal(when(at(2026, 6, 13, 10, 0, 0), NOW), '13. Juli');
  assert.equal(when(at(2025, 8, 13, 10, 0, 0), NOW), '13. Sep. 2025');
  assert.equal(when(at(2026, 10, 1, 10, 0, 0), NOW), '1. Nov.');
});

test('ein reiner Tag überspringt die Stunden-Kaskade', () => {
  // Genau das war #1014: aus «2026-09-16» lässt sich «vor 5 Minuten» nicht ableiten.
  assert.equal(when('2026-09-16', NOW), 'Heute');
  assert.equal(when('2026-09-15', NOW), 'Gestern');
  assert.equal(when('2026-09-13', NOW), 'vor 3 Tagen');
});

test('ein reiner Tag ist ein Kalendertag, keine UTC-Mitternacht', () => {
  // Als UTC gelesen wäre «2026-09-16» in der Schweiz der Vortag um 02:00.
  assert.equal(day('2026-09-16'), '16.09.2026');
});

test('day() sagt den Tag auf dem Papier, nie eine Aussage', () => {
  assert.equal(day(at(2026, 8, 16, 17, 58)), '16.09.2026');
  assert.equal(day(at(2026, 0, 3)), '03.01.2026');
});

test('ohne Wert steht «—» da, und es gibt keinen leeren Hover', () => {
  assert.equal(when(null, NOW), NOTHING);
  assert.equal(when(undefined, NOW), NOTHING);
  assert.equal(when('', NOW), NOTHING);
  assert.equal(day(null), NOTHING);
  assert.equal(whenTitle(null), undefined);
  assert.equal(whenTitle('quatsch'), undefined);
});

test('die Tatsache steht immer im Hover – formatWhen gibt beides', () => {
  const w = formatWhen(at(2026, 8, 16, 17, 53, 30), NOW);
  assert.equal(w.text, 'vor 5 Minuten');
  assert.equal(w.title, '16.09.2026, 17:53');
});

test('die Wörter stehen im Modul, nicht im ICU', () => {
  // «Sep.» ↔ «Sept.» je nach ICU-Fassung wäre derselbe Fehler wie beim Tausender-Trenner:
  // server- und clientseitig verschieden gerendert wirft React die Seite weg.
  assert.equal(when(at(2025, 8, 13), NOW), '13. Sep. 2025');
  assert.equal(when(at(2025, 2, 13), NOW), '13. März 2025');
});
