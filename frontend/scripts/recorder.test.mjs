/**
 * ►►► **Aufnehmen: Abschnitte, Stücke, Warteschlange** (Phase 4, `src/lib/recorder.ts`). ◄◄◄
 *
 * Geprüft gegen die echte Quelle (transpiliert), ohne Browser: Recorder und Zeitgeber sind
 * Attrappen. Die Bug-Formen: die Stück-Zählung läuft über den Abschnitt hinaus weiter · das
 * letzte Stück eines Abschnitts trägt die Nummer des nächsten · Stücke überholen einander ·
 * ein gescheitertes Stück hält die übrigen auf oder verschwindet stumm · der Stopp wartet
 * nicht auf das letzte Stück.
 *
 *     node --test scripts/recorder.test.mjs
 */

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const js = ts.transpileModule(readFileSync(resolve(here, '../src/lib/recorder.ts'), 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
}).outputText;
const R = await import(`data:text/javascript;base64,${Buffer.from(js).toString('base64')}`);

const tick = () => new Promise((r) => setImmediate(r));

/** Ein Recorder zum Anfassen: `emit` liefert ein Stück, `stop` liefert das letzte und meldet sich. */
function fakeRecorder(log) {
  const rec = {
    ondataavailable: null, onstop: null, slice: null, stopped: false,
    start(ms) { rec.slice = ms; log.push('start'); },
    stop() { rec.stopped = true; setImmediate(() => { rec.emit('last'); rec.onstop?.({}); }); },
    emit(data) { rec.ondataavailable?.({ data }); },
  };
  return rec;
}

/** Zeitgeber, die der Test von Hand auslöst. */
function fakeTimers() {
  const timers = [];
  const add = (fn, ms, repeat) => { const t = { fn, ms, repeat, on: true }; timers.push(t); return () => { t.on = false; }; };
  return {
    every: (fn, ms) => add(fn, ms, true),
    after: (fn, ms) => add(fn, ms, false),
    fire(ms) { for (const t of timers.filter((x) => x.on && x.ms === ms)) { if (!t.repeat) t.on = false; t.fn(); } },
  };
}

function setup({ send } = {}) {
  const sent = [];
  const log = [];
  const recorders = [];
  const timers = fakeTimers();
  const queue = new R.UploadQueue({
    send: send ?? (async (c) => { sent.push(`${c.segment}.${c.seq}:${c.blob}`); }),
    wait: async () => {},
  });
  const session = new R.RecordingSession({
    createRecorder: () => { const r = fakeRecorder(log); recorders.push(r); return r; },
    sizeOf: (b) => (b === '' ? 0 : 1),
    queue, ...timers,
  });
  return { session, queue, sent, recorders, timers, log };
}

test('Stücke alle 30 s, ein neuer Abschnitt alle 10 Minuten – die Zählung beginnt bei 0', async () => {
  const { session, sent, recorders, timers } = setup();
  session.start();
  assert.equal(recorders[0].slice, R.CHUNK_MS);
  assert.equal(R.CHUNK_MS, 30_000);
  assert.equal(R.SEGMENT_MS, 600_000);
  recorders[0].emit('a'); recorders[0].emit('b');
  timers.fire(R.SEGMENT_MS);            // Abschnitt 1 beginnt sofort, Abschnitt 0 liefert noch sein letztes Stück
  assert.equal(recorders.length, 2);
  assert.ok(recorders[0].stopped);
  await tick();
  recorders[1].emit('c');
  recorders[1].emit('');                // ein leeres Stück zählt nicht
  recorders[1].emit('d');
  assert.equal(await session.stop(), 2);
  assert.deepEqual(sent, ['0.0:a', '0.1:b', '0.2:last', '1.0:c', '1.1:d', '1.2:last']);
});

test('der Stopp wartet auf das letzte Stück und leert die Warteschlange', async () => {
  let release;
  const gate = new Promise((r) => { release = r; });
  const sent = [];
  const { session, recorders } = setup({ send: async (c) => { await gate; sent.push(c.blob); } });
  session.start();
  recorders[0].emit('x');
  const stopped = session.stop();
  assert.equal(session.stop(), stopped, 'zweimal Stopp – derselbe Lauf');
  await tick(); await tick();
  assert.deepEqual(sent, []);
  release();
  assert.equal(await stopped, 1);
  assert.deepEqual(sent, ['x', 'last']);
});

test('nach 3 Stunden hält die Aufnahme von selbst an', async () => {
  let limited = false;
  const timers = fakeTimers();
  const recorders = [];
  const session = new R.RecordingSession({
    createRecorder: () => { const r = fakeRecorder([]); recorders.push(r); return r; },
    sizeOf: () => 1,
    queue: new R.UploadQueue({ send: async () => {}, wait: async () => {} }),
    ...timers, onLimit: () => { limited = true; },
  });
  session.start();
  assert.equal(R.MAX_MS, 3 * 3600_000);
  timers.fire(R.MAX_MS);
  assert.ok(limited);
  assert.ok(recorders[0].stopped);
  assert.equal(session.active, false);
});

test('die Warteschlange: der Reihe nach, mit Pausen 1-2-4-8 s, dann gescheitert – die übrigen gehen weiter', async () => {
  const tries = {};
  const waits = [];
  const sent = [];
  const failed = [];
  const queue = new R.UploadQueue({
    send: async (c) => {
      tries[c.blob] = (tries[c.blob] ?? 0) + 1;
      if (c.blob === 'kaputt') throw new Error('HTTP 500');
      if (c.blob === 'wackelt' && tries[c.blob] < 3) throw new Error('kein Netz');
      sent.push(c.blob);
    },
    wait: async (ms) => { waits.push(ms); },
    onFail: (c, e) => failed.push(`${c.blob}: ${e.message}`),
  });
  for (const [seq, blob] of ['a', 'wackelt', 'kaputt', 'b'].entries()) queue.push({ segment: 0, seq, blob });
  await queue.drain();
  assert.deepEqual(sent, ['a', 'wackelt', 'b']);
  assert.equal(tries.kaputt, 1 + R.RETRY_MS.length);
  assert.deepEqual(waits, [1000, 2000, 1000, 2000, 4000, 8000]);
  assert.deepEqual(failed, ['kaputt: HTTP 500']);
  assert.deepEqual(queue.state, { pending: 0, failed: 1, uploadedSeconds: 120 });
});

test('eine Abweisung, die kein neuer Versuch ändert, wird nicht wiederholt', async () => {
  let n = 0;
  const failed = [];
  const queue = new R.UploadQueue({
    send: async () => { n += 1; throw Object.assign(new Error('fertig'), { status: 409 }); },
    wait: async () => {},
    retryable: (e) => e.status !== 409,
    onFail: (c) => failed.push(c.seq),
  });
  queue.push({ segment: 0, seq: 0, blob: 'x' });
  await queue.drain();
  assert.equal(n, 1);
  assert.deepEqual(failed, [0]);
});

test('«hochgeladen bis» zählt nie über das Ende eines Abschnitts hinaus', async () => {
  const queue = new R.UploadQueue({ send: async () => {}, wait: async () => {} });
  queue.push({ segment: 0, seq: 20, blob: 'letztes, kurzes Stück' });   // 21 × 30 s wäre 10:30
  await queue.drain();
  assert.equal(queue.state.uploadedSeconds, 600);
  queue.push({ segment: 1, seq: 0, blob: 'x' });
  await queue.drain();
  assert.equal(queue.state.uploadedSeconds, 630);
});

test('Laufzeit mm:ss, ab einer Stunde h:mm:ss', () => {
  assert.equal(R.runtime(0), '00:00');
  assert.equal(R.runtime(247_900), '04:07');
  assert.equal(R.runtime(3_847_000), '1:04:07');
  assert.equal(R.runtime(-5), '00:00');
});

test('das Format: Opus in WebM, sonst MP4, sonst die Vorgabe des Browsers', () => {
  assert.equal(R.pickMime(() => true), 'audio/webm;codecs=opus');
  assert.equal(R.pickMime((m) => m === 'audio/mp4'), 'audio/mp4');
  assert.equal(R.pickMime(() => false), '');
});
