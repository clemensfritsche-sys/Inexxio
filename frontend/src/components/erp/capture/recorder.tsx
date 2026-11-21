'use client';

import { useEffect, useRef } from 'react';
import { Square } from 'lucide-react';
import { runtime } from '@/lib/recorder';
import { useRecorder } from '@/lib/use-recorder';
import { StatusDot } from '@/components/erp/fields';
import type { Recording } from '@/types';

/**
 * ►►► **Die Aufnahme – dezent in der Leiste der Eingabe** (wie bei Claude). ◄◄◄ Das Feld bleibt
 * stehen; unten laufen roter Punkt, Zeit und der Pegel von rechts nach links, das Mikrofon ist der
 * Stopp. 30 s Stille halten von selbst an (`lib/recorder.silence`). Nur wenn etwas klemmt (kein
 * Netz, ein Stück abgewiesen), steht ein kurzer Satz daneben – nie still. Startet das Mikrofon
 * nicht, geht der Grund an `onFailed`. Die Logik steht in `lib/use-recorder.ts`.
 */
export function RecordingBar({ hint, context, onStopped, onFailed }: {
  hint: number | null;
  /** Die Stecknadel («Stelle: …») – kommt mit dem Text zurück. */
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
    : rec.queue.waiting ? 'wartet auf Netz' : '';
  return (
    <div className="erp-rec-line" aria-live="off">
      <span className="erp-rec-dot" aria-hidden data-live={live || undefined} />
      <span className="erp-rec-time">{rec.phase === 'starting' ? 'Mikrofon …' : runtime(rec.elapsed)}</span>
      <Level levels={rec.levels} live={live} />
      {(trouble || rec.phase === 'stopping') && (
        <span aria-live="polite" className="erp-rec-trouble">
          {trouble && <StatusDot color="var(--warning)" />}{trouble || 'lädt hoch …'}
        </span>
      )}
      <button type="button" onClick={rec.stop} disabled={!live} className="erp-send erp-send-stop"
        aria-label={live ? 'Stopp' : 'Lädt die letzten Stücke hoch'} data-tip={live ? 'Stopp (nach 30 s Stille von selbst)' : undefined}>
        <Square size={13} fill="currentColor" />
      </button>
    </div>
  );
}

/** Der Pegel: die letzten Sekunden als ruhige Balken, das Neueste rechts – er wandert nach links. */
function Level({ levels, live }: { levels: number[]; live: boolean }) {
  return (
    <div className="erp-rec-level" aria-hidden>
      {levels.map((v, i) => (
        // Feste Stellen, keine Datensätze: die Stelle ist der Schlüssel.
        <span key={i} style={{ height: 3 + Math.round(v * 18), opacity: live ? 1 : 0.35 }} />
      ))}
    </div>
  );
}

/** Ein Wort für eine Aufnahme, die nicht abgeschrieben werden konnte – in «Offene Gespräche». */
export function recordingWord(r: Recording): string {
  return r.problem ? `Aufnahme fehlgeschlagen – ${r.problem}` : 'Aufnahme fehlgeschlagen';
}
