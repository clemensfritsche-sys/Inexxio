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
import { Boxes, CheckCircle2, ClipboardList, Clock3, PackageMinus, PackagePlus, PauseCircle, TriangleAlert } from 'lucide-react';
import { Dialog, PaletteButton, PrimaryButton } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { unitLabel } from '@/lib/article';
import { formatQty } from '@/lib/process';
import { formatObjectId } from '@/lib/utils';
import type { AffectedOrder, ShortfallAnswer } from '@/types';

/** Frei verfügbare Instanz, mit der sich die Fehlmenge ohne Nachschub decken liesse. */
export type ShortfallCandidate = { object_id: number; quantity: number };

const ROW: React.CSSProperties = {
  display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center',
};

/**
 * **Wen trifft die Entscheidung?** – eine Zeile je betroffenem Auftrag (Notiz #387).
 *
 * Ohne sie stand über den drei Symbolen nur «Es fehlt»: man entschied über Aufträge, die
 * man nicht sah. Die Zeile beantwortet drei Dinge, sonst beantwortet sie keines
 * (Notiz #393):
 *
 *   **wer**   – ein Auftrag. Sein Name IST der Artikelname («Schraubendreher»), darum steht
 *               die Datensatzart als Eyebrow davor: ohne sie las sich die Zeile wie ein
 *               Artikel und man wusste nicht, welchen Auftrag es trifft.
 *   **wie viel** – in der **Einheit** des Artikels («1 Stk»), nicht in seinem Namen: das
 *               frühere «verliert 1 Schraubendreher» wiederholte nur den Namen von links.
 *   **woher**  – aus welcher Instanz. Bei mehreren Anteilen ist genau das die Information,
 *               die man zum Entscheiden braucht.
 *
 * **Jeder Betroffene steht hier** (Notiz #397) – auch eine Abweichung. Früher galt ein
 * festes Subjekt als «schrumpft lautlos mit»; das war eine zweite Logik für dieselbe Lage,
 * und in der Praxis wurde eine Abweichung ohne Rückfrage abgebrochen.
 */
function AffectedList({ affected }: { affected: AffectedOrder[] }) {
  if (affected.length === 0) return null;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {affected.map((a) => {
        const dev = a.reason === 'deviation';
        const sources = a.sources ?? [];
        return (
          <div key={a.object_id} style={{
            display: 'flex', flexDirection: 'column', gap: 3,
            padding: '8px 11px', borderRadius: 'var(--r-md)',
            border: '1px solid var(--border-1)', background: 'var(--bg-2)',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
              <span style={{ color: 'var(--fg-3)', display: 'inline-flex', flexShrink: 0 }}>
                {dev ? <TriangleAlert size={14} /> : <ClipboardList size={14} />}
              </span>
              <span style={{
                font: '700 10.5px var(--font-body)', letterSpacing: '.06em',
                textTransform: 'uppercase', color: 'var(--fg-4)',
              }}>{dev ? 'Abweichung' : 'Auftrag'}</span>
              <span style={{ font: '600 13px var(--font-body)', color: 'var(--fg-1)' }}>{a.name ?? '—'}</span>
              <ObjId value={a.object_id} />
            </div>
            <span style={{ font: '500 12.5px var(--font-body)', color: 'var(--fg-3)' }}>
              verliert <b style={{ color: 'var(--fg-1)', fontVariantNumeric: 'tabular-nums' }}>
                {formatQty(a.quantity)}{a.unit ? ` ${unitLabel(a.unit)}` : ''}</b>
              {/* EINE Herkunft steht einfach dahinter; bei mehreren je Instanz die Teilmenge. */}
              {sources.length === 1
                ? <> von <ObjId value={sources[0].instance_object_id} /></>
                : sources.map((s) => (
                    <span key={s.instance_object_id}>
                      {' · '}{formatQty(s.quantity)} von <ObjId value={s.instance_object_id} />
                    </span>
                  ))}
            </span>
          </div>
        );
      })}
    </div>
  );
}

export function ShortfallDialog({
  affected = [], candidates = [], canReduce = true, busy = false, error, onAnswer, onClose,
}: {
  /** Die betroffenen laufenden Aufträge – worüber hier entschieden wird (#387). */
  affected?: AffectedOrder[];
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
    <Dialog icon={PackageMinus} title="Es fehlt" onClose={onClose} width={480}>
      <AffectedList affected={affected} />
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
