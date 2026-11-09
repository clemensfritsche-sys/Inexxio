'use client';

import { useEffect, useRef, useState } from 'react';
import { api, ApiError } from '@/lib/api';
import { notify, tell } from '@/lib/notice';
import {
  BITRATE, RecordingSession, UploadQueue, pickMime, silence, type QueueState, type RecorderLike,
} from '@/lib/recorder';
import type { Recording } from '@/types';

/**
 * ►►► **Aufnehmen im Browser** (Phase 4, `docs/konzept/phase4-bauplan.md` «Aufnahme im
 * Browser»). ◄◄◄ Schliesst die reine Logik (`lib/recorder.ts`: Abschnitte, Stücke,
 * Warteschlange) an Mikrofon, `MediaRecorder`, Pegel und Wake Lock an.
 *
 * Ablauf: Mikrofon (Mono) → `POST /erp/recordings` → Stücke der Reihe nach hoch → Stopp:
 * letztes Stück abwarten, Mikrofon zu, Warteschlange leeren → `POST …/stop {segments}` →
 * `onStopped(recording)`. Wird das Bauteil vorher entfernt (Seite gewechselt), hält die Aufnahme
 * genauso an – im Hintergrund, ohne `onStopped`; abgeschrieben wird sie dann im Takt.
 *
 * **Freigegeben wird immer**: Spuren des Mikrofons gestoppt, `AudioContext` geschlossen, Wake
 * Lock gelöst, Zeitgeber weg – beim Stopp, beim Fehler und beim Entfernen. **30 s Stille**
 * halten an wie «Stopp» (`lib/recorder.silence`).
 *
 * **Nichts geht verloren, nichts läuft still weiter:** fällt das Mikrofon aus (Fehler des
 * Recorders, Spur beendet, länger stumm), endet die Aufnahme sauber mit einer Meldung; wird die
 * Seite verlassen oder unsichtbar, geht das Letzte sofort hoch (`requestData`); weist der Server
 * ein Stück ab, weil die Aufnahme schon abgeschlossen ist (409), endet sie sofort mit klarem Satz.
 */

/** Kann dieser Browser aufnehmen? Sonst steht kein Knopf da. */
export function canRecord(): boolean {
  return typeof window !== 'undefined' && typeof window.MediaRecorder === 'function'
    && typeof navigator.mediaDevices?.getUserMedia === 'function';
}

type RecorderPhase = 'starting' | 'recording' | 'stopping' | 'failed';

/** Wie viele Balken der Pegel zeigt und wie oft er sich bewegt (ruhig: 10 je Sekunde). */
const LEVEL_BARS = 44;
const LEVEL_MS = 100;

const IDLE_QUEUE: QueueState = { pending: 0, failed: 0, uploadedSeconds: 0, waiting: false };
/** So lange darf das Mikrofon stumm sein (`mute`), bevor die Aufnahme als getrennt gilt. */
const MUTE_MS = 5_000;
const MIC_LOST = 'Mikrofon getrennt – Aufnahme beendet.';
const CLOSED = 'Diese Aufnahme ist schon abgeschlossen – bitte neu starten.';

/** Ein `MediaRecorder` in der Form, die die Sitzung braucht; ein Stopp am schon stillen
 *  Recorder meldet sich trotzdem als gestoppt. */
function wrap(r: MediaRecorder, onError: (e: unknown) => void): RecorderLike<Blob> {
  const like: RecorderLike<Blob> = {
    start: (ms) => r.start(ms),
    stop: () => { if (r.state !== 'inactive') r.stop(); else like.onstop?.(null); },
    requestData: () => { if (r.state === 'recording') r.requestData(); },
    ondataavailable: null,
    onstop: null,
  };
  r.ondataavailable = (e) => like.ondataavailable?.(e);
  r.onstop = (e) => like.onstop?.(e);
  r.onerror = onError;
  return like;
}

/** Ist die Aufnahme am Server schon abgeschlossen? (Ein Stück kam zu spät: 409.) */
function closedOnServer(e: unknown): boolean {
  return e instanceof ApiError && e.status === 409;
}

/** Lohnt ein neuer Versuch? Nicht bei einer Abweisung des Servers (4xx ausser 408/429). */
function retryable(e: unknown): boolean {
  return !(e instanceof ApiError && e.status >= 400 && e.status < 500 && e.status !== 408 && e.status !== 429);
}

/** Der Grund in einem Satz – das Mikrofon sagt es nur als Fehlername. */
function micProblem(e: unknown): string {
  const name = e instanceof DOMException ? e.name : '';
  if (name === 'NotAllowedError' || name === 'SecurityError') return 'Kein Zugriff auf das Mikrofon – im Browser erlauben.';
  if (name === 'NotFoundError' || name === 'OverconstrainedError') return 'Kein Mikrofon gefunden.';
  if (name === 'NotReadableError') return 'Das Mikrofon ist gerade belegt.';
  return e instanceof Error && e.message ? e.message : 'Die Aufnahme liess sich nicht starten.';
}

/** Ein Pegel 0…1 aus dem Signal – in dB, damit leises Sprechen sichtbar bleibt. */
function levelOf(buf: Float32Array): number {
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
  const db = 20 * Math.log10(Math.sqrt(sum / buf.length) || 1e-8);
  return Math.min(1, Math.max(0, (db + 60) / 50));
}

const sleep = (ms: number) => new Promise<void>((r) => { setTimeout(r, ms); });

export function useRecorder(hint: number | null, onStopped: (r: Recording) => void,
  context?: string | null) {
  const [phase, setPhase] = useState<RecorderPhase>('starting');
  const [problem, setProblem] = useState('');
  const [span, setSpan] = useState<{ from: number; to: number | null } | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [levels, setLevels] = useState<number[]>(() => Array<number>(LEVEL_BARS).fill(0));
  const [queue, setQueue] = useState<QueueState>(IDLE_QUEUE);
  const stopRef = useRef<() => void>(() => undefined);
  const doneRef = useRef(onStopped);
  doneRef.current = onStopped;
  // Hinweis und Stecknadel gelten, wie sie beim Start waren.
  const hintRef = useRef(hint);
  const contextRef = useRef(context ?? null);

  useEffect(() => {
    let dead = false;
    let stream: MediaStream | null = null;
    let audio: AudioContext | null = null;
    let lock: WakeLockSentinel | null = null;
    let session: RecordingSession<Blob> | null = null;
    let id: number | null = null;
    let finishing: Promise<void> | null = null;
    let busy = false;   // Mikrofon offen oder Stücke unterwegs → «Seite verlassen?»
    const timers: (() => void)[] = [];

    const freeMic = () => {
      timers.forEach((t) => t());
      timers.length = 0;
      stream?.getTracks().forEach((t) => t.stop());
      stream = null;
      if (audio && audio.state !== 'closed') void audio.close().catch(tell('Pegel', 'Nicht geschlossen'));
      audio = null;
      void lock?.release().catch(tell('Bildschirm', 'Nicht freigegeben'));
      lock = null;
    };

    const wake = () => {
      if (!('wakeLock' in navigator) || document.visibilityState !== 'visible' || lock) return;
      navigator.wakeLock.request('screen').then((l) => {
        if (dead || !session?.active) { void l.release().catch(tell('Bildschirm', 'Nicht freigegeben')); return; }
        lock = l;
        l.addEventListener('release', () => { if (lock === l) lock = null; });
      }, (e: unknown) => {
        // Verweigert (Stromsparen, Rechte) ist wie «gibt es nicht»: die Aufnahme läuft trotzdem,
        // und eine Meldung läge über dem Stopp-Knopf. Alles andere meldet sich.
        if (e instanceof DOMException && e.name === 'NotAllowedError') return;
        tell('Bildschirm bleibt an', 'Nicht möglich')(e);
      });
    };
    const onVisible = () => { if (session?.active) wake(); };
    const onLeave = (e: BeforeUnloadEvent) => { if (busy) { e.preventDefault(); e.returnValue = ''; } };

    /** Anhalten – vom Knopf, von der Höchstdauer, beim Entfernen, wenn das Mikrofon ausfällt
     *  oder der Server die Aufnahme schon abgeschlossen hat (`closed`: dann kein Stopp, ein
     *  klarer Satz). Einmal. */
    let closed = false;
    const finish = (): Promise<void> => {
      if (finishing) return finishing;
      if (!session || id === null) { freeMic(); busy = false; return Promise.resolve(); }
      const s = session;
      const rid = id;
      if (!dead) { setPhase('stopping'); setSpan((x) => x && { ...x, to: Date.now() }); }
      void s.recorded().then(freeMic);
      finishing = s.stop()
        .then((segments) => (closed ? null : api.stopRecording(rid, segments)))
        .then((rec) => {
          busy = false;
          if (!rec) {
            if (dead) notify(CLOSED);
            else { setProblem(CLOSED); setPhase('failed'); }
          } else if (!dead) doneRef.current(rec);
        })
        .catch((e: unknown) => {
          busy = false;
          tell('Aufnahme', 'Nicht angehalten')(e);
          if (!dead) { setProblem(e instanceof Error ? e.message : 'Nicht angehalten.'); setPhase('failed'); }
        });
      return finishing;
    };
    stopRef.current = () => { void finish(); };
    /** Das Mikrofon ist weg – einmal sagen, dann sauber beenden (was da ist, geht hoch). */
    const micLost = () => {
      if (finishing || !session) return;
      notify(MIC_LOST, Date.now(), { tone: 'info' });
      void finish();
    };
    /** Seite wird verlassen oder unsichtbar: das bisher Aufgenommene sofort hoch. */
    const flush = () => { session?.flush(); };
    const onHidden = () => { if (document.visibilityState === 'hidden') flush(); };
    const watchTracks = (src: MediaStream) => {
      for (const track of src.getAudioTracks()) {
        let muted: ReturnType<typeof setTimeout> | null = null;
        track.onended = micLost;
        track.onmute = () => { if (!muted) muted = setTimeout(micLost, MUTE_MS); };
        track.onunmute = () => { if (muted) clearTimeout(muted); muted = null; };
        timers.push(() => { if (muted) clearTimeout(muted); track.onended = null; track.onmute = null; track.onunmute = null; });
      }
    };

    const meter = (src: MediaStream) => {
      audio = new AudioContext();
      if (audio.state === 'suspended') void audio.resume().catch(tell('Pegel', 'Nicht gestartet'));
      const analyser = audio.createAnalyser();
      analyser.fftSize = 1024;
      audio.createMediaStreamSource(src).connect(analyser);
      const buf = new Float32Array(analyser.fftSize);
      // 30 s Stille → von selbst anhalten, wie mit «Stopp» (`lib/recorder.silence`).
      const quiet = silence(Date.now());
      const t = setInterval(() => {
        analyser.getFloatTimeDomainData(buf);
        const v = levelOf(buf);
        const at = Date.now();
        setLevels((l) => [...l.slice(1), v]);
        setNow(at);
        if (quiet.hear(v, at)) void finish();
      }, LEVEL_MS);
      timers.push(() => clearInterval(t));
    };

    async function begin() {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
        });
        if (dead) { freeMic(); return; }
        busy = true;
        const mimeType = pickMime((m) => MediaRecorder.isTypeSupported(m));
        const opts: MediaRecorderOptions = { audioBitsPerSecond: BITRATE, ...(mimeType ? { mimeType } : {}) };
        let spare: MediaRecorder | null = new MediaRecorder(stream, opts);
        const rec = await api.startRecording(spare.mimeType || mimeType || 'audio/webm', hintRef.current,
          contextRef.current);
        if (dead) {
          freeMic();
          busy = false;
          void api.stopRecording(rec.id, 0).catch(tell('Aufnahme', 'Nicht angehalten'));
          return;
        }
        const rid = rec.id;
        id = rid;
        const mic = stream;
        const uploads = new UploadQueue<Blob>({
          send: (c, signal) => api.recordingChunk(rid, c.segment, c.seq, c.blob, { signal }),
          wait: sleep,
          retryable,
          onFail: (c, e) => {
            if (closedOnServer(e)) { if (!closed) { closed = true; void finish(); } return; }
            tell(`Aufnahme, Stück ${c.segment + 1}.${c.seq + 1}`, 'Nicht hochgeladen')(e);
          },
          // Einmal beim ersten Hängen – danach sagt es die Anzeige ruhig («wartet auf Netz»).
          onStall: () => notify('Aufnahme: kein Netz – die Stücke warten und gehen hoch, sobald es zurück ist.',
            Date.now(), { tone: 'info' }),
          onChange: (q) => { if (!dead) setQueue(q); },
        });
        session = new RecordingSession<Blob>({
          createRecorder: () => {
            const r = spare ?? new MediaRecorder(mic, opts);
            spare = null;
            return wrap(r, micLost);
          },
          sizeOf: (b) => b.size,
          queue: uploads,
          every: (fn, ms) => { const t = setInterval(fn, ms); return () => clearInterval(t); },
          after: (fn, ms) => { const t = setTimeout(fn, ms); return () => clearTimeout(t); },
          onLimit: () => {
            notify('Die Aufnahme hat nach 3 Stunden von selbst angehalten.', Date.now(), { tone: 'info' });
            void finish();
          },
        });
        session.start();
        watchTracks(mic);
        setSpan({ from: Date.now(), to: null });
        setPhase('recording');
        // Ohne Pegel nimmt sie trotzdem auf – er ist nur Anzeige.
        try { meter(mic); } catch (e) { tell('Pegel')(e); }
        wake();
      } catch (e) {
        freeMic();
        busy = false;
        if (dead) return;
        const why = e instanceof ApiError ? e.message : micProblem(e);
        // Der Grund steht im Blatt, wo die Aufnahme hätte laufen sollen – keine zweite Meldung.
        setProblem(why);
        setPhase('failed');
      }
    }

    document.addEventListener('visibilitychange', onVisible);
    document.addEventListener('visibilitychange', onHidden);
    window.addEventListener('pagehide', flush);
    window.addEventListener('beforeunload', onLeave);
    void begin();
    return () => {
      dead = true;
      document.removeEventListener('visibilitychange', onVisible);
      document.removeEventListener('visibilitychange', onHidden);
      window.removeEventListener('pagehide', flush);
      // Entfernt mitten in der Aufnahme: nichts geht verloren – anhalten wie mit dem Knopf; bis
      // die letzten Stücke oben sind, fragt das Verlassen der Seite weiter nach.
      void finish().finally(() => window.removeEventListener('beforeunload', onLeave));
    };
  }, []);

  const elapsed = span ? (span.to ?? Math.max(now, span.from)) - span.from : 0;
  return { phase, problem, elapsed, levels, queue, stop: () => stopRef.current() };
}
