'use client';

import { useEffect, useRef } from 'react';
import { Square } from 'lucide-react';
import { runtime } from '@/lib/recorder';
import { useRecorder } from '@/lib/use-recorder';
import { StatusDot } from '@/components/erp/fields';
import type { Recording } from '@/types';

/**
 * ►►► **Die Aufnahme – im Eingabefeld selbst** (Erfassen neu): Punkt, Zeit, Pegel; der
 * Absende-Knopf ist der Stopp. ◄◄◄ Sonst nichts. Nur wenn etwas klemmt (kein Netz, ein Stück
 * abgewiesen), steht darunter ein Satz – nie still. Während sie läuft, lässt sich das «+» nicht
 * schliessen (`CaptureSheet`); der Weg hinaus ist Stopp. Die Logik steht in `lib/use-recorder.ts`.
 * Startet das Mikrofon nicht (verweigert, keines da), geht der Grund an `onFailed` – das Feld
 * ist dann wieder die Eingabe, der Grund steht darunter.
 */
export function RecordingStrip({ hint, context, onStopped, onFailed }: {
  hint: number | null;
  /** Die Stecknadel («Stelle: …») – steht später vor dem abgeschriebenen Text. */
  context: string | null;
  onStopped: (r: Recording) => void;
  onFailed: (why: string) => void;
}) {
  const rec = useRecorder(hint, onStopped, context);
  const live = rec.phase === 'recording';
  const failedRef = useRef(onFailed);
  failedRef.current = onFailed;
  useEffect(() => {
    if (rec.phase === 'failed') failedRef.current(rec.problem || 'Die Aufnahme liess sich nicht starten.');
  }, [rec.phase, rec.problem]);
  // Ein Stück wartet auf den nächsten Versuch, oder der Server wies eines ab.
  const trouble = rec.queue.failed
    ? `${rec.queue.failed} Stück nicht hochgeladen`
    : rec.queue.waiting ? `wartet auf Netz · ${rec.queue.pending} ${rec.queue.pending === 1 ? 'Stück' : 'Stücke'}` : '';
  return (
    <div className="erp-composer erp-composer-rec" aria-live="off">
      <div className="erp-rec-line">
        <span className="erp-rec-dot" aria-hidden data-live={live || undefined} />
        <span className="erp-rec-time">{rec.phase === 'starting' ? 'Mikrofon …' : runtime(rec.elapsed)}</span>
        <Level levels={rec.levels} live={live} />
        <button type="button" onClick={rec.stop} disabled={!live} className="erp-send erp-send-stop"
          aria-label={live ? 'Stopp' : 'Lädt die letzten Stücke hoch'} data-tip={live ? 'Stopp' : undefined}>
          <Square size={14} fill="currentColor" />
        </button>
      </div>
      {(trouble || rec.phase === 'stopping') && (
        <p aria-live="polite" className="erp-rec-trouble">
          {trouble && <StatusDot color="var(--warning)" />}
          {trouble || 'lädt die letzten Stücke hoch …'}
        </p>
      )}
    </div>
  );
}

/** Der Pegel: die letzten Sekunden als ruhige Balken, das Neueste rechts. */
function Level({ levels, live }: { levels: number[]; live: boolean }) {
  return (
    <div className="erp-rec-level" aria-hidden>
      {levels.map((v, i) => (
        // Feste Stellen, keine Datensätze: die Stelle ist der Schlüssel.
        <span key={i} style={{ height: 3 + Math.round(v * 22), opacity: live ? 1 : 0.35 }} />
      ))}
    </div>
  );
}

/** Ein Wort für den Stand einer Aufnahme – in «Nicht abgelegt». */
export function recordingWord(r: Recording): string {
  switch (r.state) {
    case 'recording': return 'Aufnahme unterbrochen – wird bald abgeschrieben';
    case 'transcribing': return r.segments > 1
      ? `Aufnahme · schreibt ab … ${Math.min(r.transcribed, r.segments)} von ${r.segments}` : 'Aufnahme · schreibt ab …';
    case 'filing': return 'Aufnahme · legt ab …';
    case 'done': return 'Aufnahme abgeschrieben';
    case 'failed': return r.problem ? `Aufnahme fehlgeschlagen – ${r.problem}` : 'Aufnahme fehlgeschlagen';
  }
}
