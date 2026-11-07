'use client';

import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Loader2, Mic, Square } from 'lucide-react';
import { api } from '@/lib/api';
import { tell } from '@/lib/notice';
import { runtime } from '@/lib/recorder';
import { useRecorder } from '@/lib/use-recorder';
import { StatusDot } from '@/components/erp/fields';
import { SheetHead } from '@/components/erp/capture/sheet-head';
import type { Intake, Recording } from '@/types';

/**
 * ►►► **Die Aufnahme** (Phase 4, Mockup «Aufnahme»): nur das Nötigste – Zeit, Pegel, Stopp. ◄◄◄
 *
 * Während sie läuft, lässt sich das Blatt nicht wegtippen und nicht mit Escape schliessen
 * (`CaptureSheet` sperrt es); der Weg hinaus ist «Stopp». Dezent darunter, wie weit die Stücke
 * oben sind – hängen welche, ein Warnpunkt. Die Logik steht in `lib/use-recorder.ts`.
 */
export function RecorderView({ hint, onStopped, onClose }: {
  hint: number | null;
  onStopped: (r: Recording) => void;
  onClose: () => void;
}) {
  const rec = useRecorder(hint, onStopped);
  const live = rec.phase === 'recording';
  // Ein Stück wartet auf den nächsten Versuch, oder der Server wies eines ab.
  const behind = rec.queue.waiting || rec.queue.failed > 0;
  return (
    <>
      <SheetHead title="Aufnahme" onClose={rec.phase === 'failed' ? onClose : undefined} />
      <div style={{ padding: '22px 16px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
        {rec.phase !== 'failed' && <>
          <div className="erp-rec-time" aria-live="off">{runtime(rec.elapsed)}</div>
          <Level levels={rec.levels} live={live} />
        </>}
        {rec.phase === 'failed' ? (
          <p role="alert" style={{ margin: 0, display: 'flex', gap: 8, fontSize: 13.5, lineHeight: 1.45,
            color: 'var(--danger)', textAlign: 'left' }}>
            <AlertCircle size={16} style={{ flex: 'none', marginTop: 2 }} aria-hidden />{rec.problem}
          </p>
        ) : (
          <button type="button" onClick={rec.stop} disabled={!live} className="erp-rec-stop"
            aria-label={live ? 'Stopp' : rec.phase === 'stopping' ? 'Lädt die letzten Stücke hoch' : 'Startet'}>
            {live ? <Square size={26} fill="currentColor" /> : <Loader2 size={26} className="animate-spin" />}
          </button>
        )}
        {/* Der Platz steht von Anfang an – nichts springt, wenn sich die Zeile füllt. */}
        <p aria-live="polite" style={{ margin: '14px 0 0', minHeight: 20, fontSize: 12.5, color: 'var(--fg-3)',
          display: 'flex', alignItems: 'center', gap: 6 }}>
          {rec.phase === 'starting' && 'Mikrofon …'}
          {live && !behind && (rec.queue.uploadedSeconds
            ? <span>Hochgeladen bis <span className="tabular-nums">{runtime(Math.min(rec.queue.uploadedSeconds * 1000, rec.elapsed))}</span></span>
            : 'Stopp, wenn fertig · auch ein ganzes Meeting')}
          {live && behind && (
            <><StatusDot color="var(--warning)" />
              {rec.queue.failed ? `${rec.queue.failed} Stück nicht hochgeladen`
                : `wartet auf Netz · ${rec.queue.pending} ${rec.queue.pending === 1 ? 'Stück' : 'Stücke'}`}</>
          )}
          {rec.phase === 'stopping' && (rec.queue.waiting ? 'wartet auf Netz – die letzten Stücke gehen hoch, sobald es zurück ist …' : 'lädt die letzten Stücke hoch …')}
        </p>
      </div>
    </>
  );
}

/** Der Pegel: die letzten Sekunden als ruhige Balken, das Neueste rechts. */
function Level({ levels, live }: { levels: number[]; live: boolean }) {
  return (
    <div className="erp-rec-level" aria-hidden>
      {levels.map((v, i) => (
        // Feste Stellen, keine Datensätze: die Stelle ist der Schlüssel.
        <span key={i} style={{ height: 4 + Math.round(v * 30), opacity: live ? 1 : 0.35 }} />
      ))}
    </div>
  );
}

/** Wie lange «weiter abschreiben» mindestens auseinanderliegt, wenn sich nichts bewegt –
 *  bei einer noch laufenden (unterbrochenen) Aufnahme länger. */
const IDLE_MS = 3_000;
const WAITING_MS = 15_000;
const RETRY_MS = 5_000;

/**
 * ►►► **«schreibt ab …»** – fragt `POST …/advance`, bis die Aufnahme abgelegt bereit ist. ◄◄◄
 *
 * Jeder Aufruf arbeitet höchstens ~60 s, dann kommt sofort der nächste. Bei `done` öffnet sich
 * «Abgelegt» (wie nach «Schreiben»); bei `failed` steht der Grund da. Schliesst man das Blatt,
 * läuft es im Takt weiter – die Aufnahme steht dann im «+» unter «Nicht abgelegt».
 */
export function Transcribe({ recording, onFiled, onClose }: {
  recording: Recording;
  onFiled: (i: Intake) => void;
  onClose: () => void;
}) {
  const [rec, setRec] = useState(recording);
  const [offline, setOffline] = useState('');
  const filedRef = useRef(onFiled);
  filedRef.current = onFiled;

  useEffect(() => {
    const ctl = new AbortController();
    const pause = (ms: number) => new Promise<void>((r) => { setTimeout(r, ms); });
    (async () => {
      let r = recording;
      while (!ctl.signal.aborted) {
        if (r.state === 'done' && r.intake) { filedRef.current(r.intake); return; }
        if (r.state === 'failed') return;
        const t0 = Date.now();
        const was = r.transcribed;
        try {
          r = await api.advanceRecording(r.id, { signal: ctl.signal });
        } catch (e) {
          if (ctl.signal.aborted) return;
          tell('Aufnahme', 'Nicht abgeschrieben')(e);
          setOffline(e instanceof Error ? e.message : 'Keine Antwort vom Server.');
          await pause(RETRY_MS);
          continue;
        }
        if (ctl.signal.aborted) return;
        setOffline('');
        setRec(r);
        // Bewegt sich nichts und kam die Antwort sofort, nicht im Kreis fragen.
        const quick = Date.now() - t0 < 2_000 && r.transcribed === was && r.state !== 'done';
        if (quick) await pause(r.state === 'recording' ? WAITING_MS : IDLE_MS);
      }
    })();
    return () => ctl.abort();
  }, [recording]);

  const failed = rec.state === 'failed';
  const total = Math.max(rec.segments, 1);
  return (
    <>
      <SheetHead title={failed ? 'Aufnahme' : 'Abschreiben'} onClose={onClose} />
      <div style={{ padding: '22px 16px 24px', display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="erp-capture-round-dot" style={{ width: 44, height: 44, flex: 'none' }}><Mic size={20} /></span>
          <div style={{ display: 'flex', flexDirection: 'column', minWidth: 0 }}>
            <span style={{ font: '600 15px var(--font-body)', color: 'var(--fg-1)' }}>{recordingWord(rec)}</span>
            <span className="tabular-nums" style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>
              {runtime(rec.seconds * 1000)}{rec.segments > 1 ? ` · ${rec.segments} Abschnitte` : ''}
            </span>
          </div>
        </div>
        {failed ? (
          <p role="alert" style={{ margin: 0, display: 'flex', gap: 8, fontSize: 13.5, lineHeight: 1.45, color: 'var(--danger)' }}>
            <AlertCircle size={16} style={{ flex: 'none', marginTop: 2 }} aria-hidden />{rec.problem || 'Die Aufnahme liess sich nicht abschreiben.'}
          </p>
        ) : (
          <>
            <div className="erp-rec-progress" role="progressbar" aria-valuemin={0} aria-valuemax={total}
              aria-valuenow={rec.transcribed} aria-label="Abgeschrieben">
              <span style={{ width: `${Math.round((Math.min(rec.transcribed, total) / total) * 100)}%` }} />
            </div>
            <p style={{ margin: 0, fontSize: 12.5, lineHeight: 1.45, color: 'var(--fg-3)' }}>
              {offline
                ? <><StatusDot color="var(--warning)" style={{ marginRight: 6, verticalAlign: 'middle' }} />{offline} – es wird weiter versucht.</>
                : 'Das Blatt kann zu – es wird weiter abgeschrieben und steht danach im «+» unter «Nicht abgelegt».'}
            </p>
          </>
        )}
        {failed && (
          <button type="button" onClick={onClose} className="erp-actbtn erp-actbtn-neutral" style={{ height: 48 }}>
            Schliessen
          </button>
        )}
      </div>
    </>
  );
}

/** Ein Wort für den Stand einer Aufnahme – im Blatt und unter «Nicht abgelegt». */
export function recordingWord(r: Recording): string {
  switch (r.state) {
    case 'recording': return 'Unterbrochen – wird bald abgeschrieben';
    case 'transcribing': return r.segments > 1
      ? `schreibt ab … ${Math.min(r.transcribed, r.segments)} von ${r.segments}` : 'schreibt ab …';
    case 'filing': return 'legt ab …';
    case 'done': return 'Abgeschrieben';
    case 'failed': return 'Aufnahme fehlgeschlagen';
  }
}
