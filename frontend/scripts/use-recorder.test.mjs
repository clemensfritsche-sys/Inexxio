/**
 * ►►► **Aufnehmen im Browser-Anschluss: nichts geht verloren, nichts läuft still weiter**
 * (Phase 4, `src/lib/use-recorder.ts`). ◄◄◄
 *
 * Der echte Hook in echtem React (ein Wurzelknoten ohne DOM), gegen die echten Quellen
 * (`use-recorder.ts`, `recorder.ts`, `notice.ts`, transpiliert). Nachgebildet sind nur die
 * Ränder: Mikrofon (`getUserMedia`, eine Spur), `MediaRecorder`, `AudioContext` und die API.
 * Die Bug-Formen: ein Netzloch kostet Stücke · die Spur endet und die Aufnahme läuft still
 * weiter (oder verliert ihr letztes Stück) · ein Fehler des Recorders bleibt stumm · ein Stück
 * zu einer schon fertigen Aufnahme (409) läuft still weiter · beim Verlassen der Seite bleibt
 * das zuletzt Gesprochene im Recorder.
 *
 *     node --test scripts/use-recorder.test.mjs
 */

import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { dirname, resolve } from 'node:path';
import test from 'node:test';
import assert from 'node:assert/strict';
import ts from 'typescript';

const here = dirname(fileURLToPath(import.meta.url));
const out = resolve(here, '../node_modules/.cache/use-recorder-test');
mkdirSync(out, { recursive: true });
for (const name of ['recorder', 'notice', 'use-recorder']) {
  const js = ts.transpileModule(readFileSync(resolve(here, `../src/lib/${name}.ts`), 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.ESNext, target: ts.ScriptTarget.ES2022 },
  }).outputText
    .replace(/from '@\/lib\/api'/g, "from './api-stub.mjs'")
    .replace(/from '@\/lib\/([\w-]+)'/g, "from './$1.mjs'");
  writeFileSync(resolve(out, `${name}.mjs`), js);
}
// Die API: was der Test je Fall vorgibt (`server`), mitgeschrieben, was ankam.
writeFileSync(resolve(out, 'api-stub.mjs'), `
export class ApiError extends Error {
  constructor(message, status) { super(message); this.name = 'ApiError'; this.status = status; }
}
export const api = {
  startRecording: async (mime) => globalThis.server.start(mime),
  recordingChunk: async (id, segment, seq, blob, req) => globalThis.server.chunk(id, segment, seq, blob, req),
  stopRecording: async (id, segments) => globalThis.server.stop(id, segments),
};`);

const { useRecorder } = await import(pathToFileURL(resolve(out, 'use-recorder.mjs')).href);
const { ApiError } = await import(pathToFileURL(resolve(out, 'api-stub.mjs')).href);
const notice = await import(pathToFileURL(resolve(out, 'notice.mjs')).href);
const React = (await import('react')).default;
const { createRoot } = (await import('react-dom/client')).default;

// ─── Der nachgebildete Browser ───────────────────────────────────────────────────────

function bus() {
  const on = {};
  return {
    addEventListener(t, f) { (on[t] ??= new Set()).add(f); },
    removeEventListener(t, f) { on[t]?.delete(f); },
    dispatch(t, e = {}) { for (const f of [...(on[t] ?? [])]) f(e); },
  };
}
const win = bus();
const doc = { ...bus(), visibilityState: 'visible', createElement: () => ({}), activeElement: null };
globalThis.window = Object.assign(globalThis, { addEventListener: win.addEventListener, removeEventListener: win.removeEventListener });
globalThis.document = doc;
globalThis.IS_REACT_ACT_ENVIRONMENT = false;
globalThis.HTMLIFrameElement ??= class {};

let mic;
function newMic() {
  const track = { stopped: false, onended: null, onmute: null, onunmute: null, stop() { track.stopped = true; } };
  return { track, getAudioTracks: () => [track], getTracks: () => [track] };
}
Object.defineProperty(globalThis, 'navigator', {
  configurable: true,
  value: { mediaDevices: { getUserMedia: async () => { mic = newMic(); return mic; } } },
});

const recorders = [];
let piece = 0;
globalThis.MediaRecorder = class {
  static isTypeSupported() { return true; }
  constructor() { this.state = 'inactive'; this.mimeType = 'audio/webm;codecs=opus'; recorders.push(this); }
  start() { this.state = 'recording'; }
  emit() { this.ondataavailable?.({ data: { size: 10, name: `p${piece++}` } }); }
  requestData() { this.emit(); }
  stop() {
    this.state = 'inactive';
    setImmediate(() => { this.emit(); this.onstop?.({}); });   // erst das letzte Stück, dann stop
  }
};
globalThis.AudioContext = class {
  state = 'running';
  createAnalyser() { return { fftSize: 0, getFloatTimeDomainData() {} }; }
  createMediaStreamSource() { return { connect() {} }; }
  resume() { return Promise.resolve(); }
  close() { this.state = 'closed'; return Promise.resolve(); }
};

function container() {
  const d = { nodeType: 9, addEventListener() {}, removeEventListener() {} };
  d.ownerDocument = d;
  d.defaultView = globalThis;
  return { nodeType: 1, nodeName: 'DIV', tagName: 'DIV', ownerDocument: d, addEventListener() {}, removeEventListener() {} };
}

/** Den Hook einhängen: `view` hält, was er gerade zeigt, `stopped` die gestoppten Aufnahmen. */
function mount() {
  const view = { current: null, stopped: [] };
  function Probe() {
    view.current = useRecorder(null, (r) => view.stopped.push(r));
    return null;
  }
  const root = createRoot(container());
  React.act(() => root.render(React.createElement(Probe)));
  return { view, unmount: () => React.act(() => root.unmount()) };
}

/** Eine API, die mitschreibt; `chunk` darf je Aufruf etwas anderes tun. */
function serve(chunk = async () => ({})) {
  const s = { uploaded: [], stops: [], chunk: null };
  s.start = async () => ({ id: 7, state: 'recording' });
  s.chunk = async (id, segment, seq, blob, req) => {
    assert.ok(req?.signal, 'jeder Versuch trägt eine Zeitgrenze');
    await chunk(segment, seq);
    s.uploaded.push(`${segment}.${seq}`);
    return {};
  };
  s.stop = async (id, segments) => { s.stops.push(segments); return { id, state: 'transcribing', segments }; };
  globalThis.server = s;
  return s;
}

const wait = (ms) => new Promise((r) => { setTimeout(r, ms); });
async function until(cond, ms = 10_000) {
  const end = Date.now() + ms;
  while (!cond()) {
    if (Date.now() > end) throw new Error('Zeit abgelaufen');
    await wait(20);
  }
}
function notices() {
  let list = [];
  const off = notice.subscribe((l) => { list = l; });
  return { texts: () => list.map((n) => n.text), off };
}

// ─── Die Fälle ───────────────────────────────────────────────────────────────────────

test('Netz weg: die Stücke warten («wartet auf Netz», eine Meldung) und kommen alle an', async () => {
  let down = 2;
  const s = serve(async () => { if (down > 0) { down -= 1; throw new Error('Keine Verbindung zum Server'); } });
  const n = notices();
  const { view, unmount } = mount();
  await until(() => view.current.phase === 'recording');
  win.dispatch('pagehide');                         // das Gesprochene sofort hoch …
  await until(() => view.current.queue.waiting);    // … aber das Netz ist weg
  doc.visibilityState = 'hidden';
  doc.dispatch('visibilitychange');                 // noch ein Stück, während es wartet
  doc.visibilityState = 'visible';
  view.current.stop();
  await until(() => view.stopped.length === 1);
  assert.deepEqual(s.uploaded, ['0.0', '0.1', '0.2']);
  assert.deepEqual(s.stops, [1]);
  assert.equal(n.texts().filter((t) => t.includes('kein Netz')).length, 1, 'einmal, nicht je Versuch');
  assert.equal(view.current.queue.waiting, false);
  assert.ok(mic.track.stopped, 'Mikrofon zu');
  n.off();
  unmount();
});

test('Spur beendet: einmal «Mikrofon getrennt», sauberer Stopp mit dem letzten Stück', async () => {
  const s = serve();
  const n = notices();
  const { view, unmount } = mount();
  await until(() => view.current.phase === 'recording');
  mic.track.onended();
  await until(() => view.stopped.length === 1);
  assert.deepEqual(s.uploaded, ['0.0']);            // das letzte Stück des Recorders ist oben
  assert.deepEqual(s.stops, [1]);
  assert.ok(n.texts().some((t) => t.startsWith('Mikrofon getrennt')));
  assert.ok(mic.track.stopped);
  n.off();
  unmount();
});

test('Fehler des Recorders: ebenso – nie still weiter', async () => {
  const s = serve();
  const { view, unmount } = mount();
  await until(() => view.current.phase === 'recording');
  recorders.at(-1).onerror?.({ error: new Error('kaputt') });
  await until(() => view.stopped.length === 1);
  assert.deepEqual(s.stops, [1]);
  unmount();
});

test('409 – die Aufnahme ist am Server schon fertig: sofort beendet, klarer Satz, kein Stopp', async () => {
  const s = serve(async () => { throw new ApiError('Aufnahme «7» ist schon fertig.', 409); });
  const { view, unmount } = mount();
  await until(() => view.current.phase === 'recording');
  win.dispatch('pagehide');
  await until(() => view.current.phase === 'failed');
  assert.equal(view.current.problem, 'Diese Aufnahme ist schon abgeschlossen – bitte neu starten.');
  assert.deepEqual(s.stops, []);
  assert.equal(view.stopped.length, 0);
  assert.ok(mic.track.stopped, 'Mikrofon zu');
  unmount();
});
