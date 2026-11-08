import { api, ApiError } from '@/lib/api';
import { notify, tell } from '@/lib/notice';
import type { Recording } from '@/types';

/**
 * ►►► **Eine Aufnahme zu Ende abschreiben lassen – auch wenn das «+» zu ist.** ◄◄◄
 *
 * Nach dem Stopp fragt die Oberfläche `POST …/advance`, bis die Aufnahme `done` (der Text steht
 * im Gespräch) oder `failed` ist; jeder Aufruf arbeitet höchstens ~60 s. Die Schleife gehört
 * **nicht** dem Fenster: schliesst man das «+», läuft sie weiter, solange die Seite lebt – und
 * meldet sich, wenn es fertig ist («Aufnahme abgeschrieben …»). Je Aufnahme läuft **eine**
 * Schleife (`runs`): öffnet man sie wieder, hängt sich das Fenster an dieselbe. Ist die Seite
 * zu, macht es der Takt (`recordings.advance` im Takt `voice`).
 */

type Listener = (r: Recording) => void;

interface Run { promise: Promise<Recording>; listeners: Set<Listener>; last: Recording }

const runs = new Map<number, Run>();

/** Wie lange «weiter abschreiben» mindestens auseinanderliegt, wenn sich nichts bewegt – bei
 *  einer noch laufenden (unterbrochenen) Aufnahme länger; nach einem Fehler wartet sie. */
const IDLE_MS = 3_000;
const WAITING_MS = 15_000;
const RETRY_MS = 5_000;

const pause = (ms: number) => new Promise<void>((r) => { setTimeout(r, ms); });

/** Fertig im Sinn der Schleife: der Text steht im Gespräch, oder es ist gescheitert. */
const finished = (r: Recording) => (r.state === 'done' && !!r.talk) || r.state === 'failed';

async function loop(id: number, run: Run): Promise<Recording> {
  let r = run.last;
  while (!finished(r)) {
    const t0 = Date.now();
    const was = r.transcribed;
    try {
      r = await api.advanceRecording(id);
    } catch (e) {
      tell('Aufnahme', 'Nicht abgeschrieben')(e);
      // Weist der Server ab (abgemeldet, die Aufnahme gibt es nicht), hilft kein neuer Versuch:
      // hier aufhören – der Takt schreibt sie zu Ende, sie steht im «+». Sonst (Netz, Zeit)
      // wieder versuchen.
      if (e instanceof ApiError && e.status >= 400 && e.status < 500 && e.status !== 408 && e.status !== 429) {
        return { ...r, state: 'failed', problem: `${e.message} – sie wird im Hintergrund weiter abgeschrieben.` };
      }
      await pause(RETRY_MS);
      continue;
    }
    run.last = r;
    run.listeners.forEach((l) => l(r));
    // Bewegt sich nichts und kam die Antwort sofort, nicht im Kreis fragen.
    if (Date.now() - t0 < 2_000 && r.transcribed === was && !finished(r)) {
      await pause(r.state === 'recording' ? WAITING_MS : IDLE_MS);
    }
  }
  return r;
}

/**
 * Der Aufnahme folgen – startet die Schleife oder hängt sich an die laufende. `onUpdate` hört
 * jeden Zwischenstand; `leave()` hört auf zuzuhören (die Schleife läuft weiter). Wer am Ende
 * niemand mehr zuhört, bekommt die Meldung.
 */
export function follow(rec: Recording, onUpdate: Listener): { promise: Promise<Recording>; leave: () => void } {
  let run = runs.get(rec.id);
  if (!run) {
    const fresh: Run = { promise: Promise.resolve(rec), listeners: new Set(), last: rec };
    fresh.promise = loop(rec.id, fresh).then((done) => {
      runs.delete(rec.id);
      if (!fresh.listeners.size) {
        notify(done.state === 'failed'
          ? `Aufnahme nicht abgeschrieben – ${done.problem ?? 'Grund unbekannt'}. Sie steht im «+».`
          : 'Aufnahme abgeschrieben – das Gespräch steht im «+».', Date.now(),
        { tone: done.state === 'failed' ? 'warning' : 'info' });
      }
      return done;
    });
    runs.set(rec.id, fresh);
    run = fresh;
  }
  run.listeners.add(onUpdate);
  const mine = run;
  return { promise: run.promise, leave: () => { mine.listeners.delete(onUpdate); } };
}
