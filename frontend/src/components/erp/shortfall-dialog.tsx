'use client';

/**
 * **Die Unterdeckungs-Frage – EINE Stelle, drei Antworten.**
 *
 * Einem Auftrag fehlt etwas. Das kann an zwei Stellen auffallen – beim **Auswählen**
 * gebundener Instanzen (man nimmt einem laufenden Auftrag sein Stück weg) und am
 * **laufenden Auftrag** selbst (Ausschuss, Aussteuerung, offene Abweichung). Es ist
 * aber dieselbe Frage, also gibt es sie nur einmal: dieses Fenster.
 *
 * **Symbole statt Sätze** (Notiz #376): dieselbe Geste wie bei den Prozessschritt-Modulen –
 * eine offene Palette, der Name klappt beim Hover auf, die Erklärung steht im Tooltip
 * (`PaletteButton`). Der frühere Erklärabsatz darüber ist entfallen (#375): der Titel sagt,
 * worum es geht, und WAS fehlt steht bereits im Ablauf – beim Unter-Auftrag, der die Menge
 * bindet, bzw. in der Notiz unter dem Fluss.
 *
 * Die drei Antworten heissen so, wie sie sich auswirken – nicht wie das System sie
 * intern nennt (Notiz #352):
 *
 *   Pausieren       (wait)    – der Auftrag ruht, bis die Menge wieder da ist
 *   Ersetzen        (replace) – freier Bestand (FIFO **oder** gezielt), Rest per Nachschub
 *   Menge reduzieren(accept)  – der Auftrag wird mit weniger fertig
 *
 * «Ersetzen» führt dabei auf die gewohnten zwei Wege der Instanz-Herkunft: **älteste
 * zuerst** oder **bestimmte Instanzen**. Das ist keine zweite Entscheidung, nur die
 * Ausführung der ersten – darum steht sie IM selben Fenster, eine Ebene tiefer.
 */

import { useState } from 'react';
import { Boxes, CheckCircle2, Clock3, PackageMinus, PackagePlus, PauseCircle } from 'lucide-react';
import { Dialog, PaletteButton, PrimaryButton } from '@/components/erp/fields';
import { formatObjectId } from '@/lib/utils';

export type ShortfallAnswer = 'wait' | 'replace' | 'accept';

/** Frei verfügbare Instanz, mit der sich die Fehlmenge ohne Nachschub decken liesse. */
export type ShortfallCandidate = { object_id: number; quantity: number };

const ROW: React.CSSProperties = {
  display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center',
};

export function ShortfallDialog({
  candidates = [], canReduce = true, busy = false, error, onAnswer, onClose,
}: {
  /** Frei verfügbare Instanzen (nur dann gibt es «bestimmte Instanzen»). */
  candidates?: ShortfallCandidate[];
  /** «Menge reduzieren» gibt es nur für die Fertigware – Material nicht. */
  canReduce?: boolean;
  busy?: boolean;
  error?: string | null;
  onAnswer: (answer: ShortfallAnswer, instanceObjectIds?: number[]) => void;
  onClose: () => void;
}) {
  const [picking, setPicking] = useState(false);
  const [picked, setPicked] = useState<number[]>([]);

  function toggle(oid: number) {
    setPicked((p) => (p.includes(oid) ? p.filter((x) => x !== oid) : [...p, oid]));
  }

  return (
    <Dialog icon={PackageMinus} title="Es fehlt" onClose={onClose} width={440}>
      {!picking ? (
        <div style={ROW}>
          <PaletteButton
            icon={PauseCircle} label="Pausieren" disabled={busy}
            tone="var(--warning)" bg="var(--warning-bg)" border="var(--warning)"
            hint="Auftrag pausieren – der Prozess ruht, bis die Menge wieder da ist."
            onClick={() => onAnswer('wait')} />
          <PaletteButton
            icon={PackagePlus} label="Ersetzen" disabled={busy}
            tone="var(--success)" bg="var(--success-bg)" border="var(--success)"
            hint={candidates.length > 0
              ? 'Aus dem freien Bestand – älteste zuerst oder gezielt gewählt.'
              : 'Freier Bestand zuerst, für den Rest ein Nachschub.'}
            onClick={() => (candidates.length > 0 ? setPicking(true) : onAnswer('replace'))} />
          {canReduce && (
            <PaletteButton
              icon={PackageMinus} label="Menge reduzieren" disabled={busy}
              hint="Auftragsmenge reduzieren – der Auftrag wird mit dem fertig, was da ist."
              onClick={() => onAnswer('accept')} />
          )}
        </div>
      ) : (
        // Woher der Ersatz kommt – die gewohnten zwei Wege, wie bei der Auftragsanlage.
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={ROW}>
            <PaletteButton icon={Clock3} label="Älteste zuerst" disabled={busy}
              hint="Automatisch aus dem freien Bestand (FIFO)."
              onClick={() => onAnswer('replace')} />
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: 7, font: '700 11.5px var(--font-body)', letterSpacing: '.04em', textTransform: 'uppercase', color: 'var(--fg-3)' }}>
              <Boxes size={13} /> Bestimmte Instanzen
            </span>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {candidates.map((c) => {
                const sel = picked.includes(c.object_id);
                return (
                  <button key={c.object_id} type="button" onClick={() => toggle(c.object_id)}
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12,
                      fontFamily: 'var(--font-mono)', padding: '4px 10px', borderRadius: 999, cursor: 'pointer',
                      border: `1px solid ${sel ? 'var(--success)' : 'var(--border-1)'}`,
                      background: sel ? 'var(--success-bg)' : '#fff', color: sel ? 'var(--success)' : 'var(--fg-2)',
                    }}>
                    {sel && <CheckCircle2 size={12} />}
                    {formatObjectId(c.object_id)}{c.quantity > 1 ? ` ·${c.quantity}` : ''}
                  </button>
                );
              })}
            </div>
            <PrimaryButton icon={CheckCircle2} disabled={busy || picked.length === 0}
              onClick={() => onAnswer('replace', picked)}>
              {busy ? 'Wird übernommen…' : 'Gewählte übernehmen'}
            </PrimaryButton>
          </div>
        </div>
      )}

      {error && <span style={{ fontSize: 12, color: 'var(--danger)' }}>{error}</span>}
    </Dialog>
  );
}
