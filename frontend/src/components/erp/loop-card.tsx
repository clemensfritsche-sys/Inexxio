'use client';

import { useState } from 'react';
import { Repeat, X } from 'lucide-react';
import type { LoopView } from '@/types';
import { Input } from '@/components/form/field';
import { Segmented, inputClass } from '@/components/erp/controls';
import { StatusDot } from '@/components/erp/fields';
import { ActionButton } from '@/components/erp/module-ui';
import { ObjId } from '@/components/erp/obj-id';
import { TONE } from '@/lib/status-tone';
import { day } from '@/lib/when';
import { LOOP_EVERY, LOOP_TAKES, type LoopEvery } from '@/lib/vocab';
import { LAGER, type DefinitionLine } from '@/components/erp/definition-lines';

/**
 * ►►► **Die Wiederholung — eine Karte unter dem Ende** (Projektakte `docs/konzept/wiederkehr.md`). ◄◄◄
 *
 * Im Entwurf wird sie eingeschaltet und eingestellt (Wiederholen · Ab · Bis · Nimmt), mit der
 * Freigabe ist sie eingefroren. Am laufenden Auftrag sagt sie nur, wie es steht (Punkt + Satz),
 * und bietet am neuesten Auftrag der Kette «Beenden» an. **Geprüft wird nichts hier**: was
 * fehlt, sagt der Server beim Freigeben (`domain/loop.problems`), was geht, sagt `may_end`.
 * Ihre Linie (links zurück zum Start) zeichnet `process-columns.LoopLine`.
 */

/** Die Takte – Schlüssel und Wort generiert aus `domain/loop.EVERY`. */
const EVERY = (Object.keys(LOOP_EVERY) as LoopEvery[]).map((value) => ({ value, label: LOOP_EVERY[value] }));
/** Die Wahl je Lager-Zeile (`domain/loop.TAKES`) – `new` wählt niemand, es folgt aus einer Zeile «Neu». */
const TAKES = (['same', 'fifo'] as const).map((value) => ({ value, label: LOOP_TAKES[value] }));
const ENDS = [
  { value: 'never', label: 'unbefristet' },
  { value: 'until', label: 'bis Datum' },
  { value: 'count', label: 'Anzahl' },
];

/** Die Einstellung im Entwurf – lebt nur im Browser, wie der ganze Entwurf. */
export interface LoopDraft {
  every: string;
  first: string;
  end: 'never' | 'until' | 'count';
  until: string;
  count: string;
  /** Was die Wiederholung je Zeile nimmt, nach dem Schlüssel der Zeile; ohne Vorbelegung. */
  takes: Record<number, string>;
}

const NEW_LOOP: LoopDraft = {
  every: 'month', first: '', end: 'never', until: '', count: '', takes: {},
};

/** **Die Nutzlast** (`LoopIn`): `takes` in der Reihenfolge der Zeilen, die freigegeben werden. */
export function loopPayload(loop: LoopDraft | null, lines: DefinitionLine[]) {
  if (!loop) return null;
  return {
    every: loop.every,
    first: loop.first || null,
    until: loop.end === 'until' ? loop.until || null : null,
    count: loop.end === 'count' && loop.count ? Number(loop.count) : null,
    takes: lines.filter((l) => l.articleObjectId !== null)
      .map((l) => (l.origin === LAGER ? loop.takes[l.key] ?? null : null)),
  };
}

const CARD: React.CSSProperties = {
  width: '100%', background: 'var(--bg-1)', border: '1px solid var(--border-1)',
  borderRadius: 12, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12,
};
const ROW: React.CSSProperties = { display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' };
const KEY: React.CSSProperties = { width: 64, flex: 'none', fontSize: 12, color: 'var(--fg-3)' };

function Head({ right }: { right?: React.ReactNode }) {
  return (
    <div style={{ ...ROW, justifyContent: 'space-between' }}>
      <span className="flex items-center gap-2 text-sm font-semibold" style={{ color: 'var(--fg-1)' }}>
        <Repeat size={15} style={{ color: 'var(--fg-3)' }} /> Wiederholen
      </span>
      {right}
    </div>
  );
}

/** ►► **Im Entwurf**: aus → ein leiser Knopf; an → die vier Zeilen. ◄◄ */
export function LoopDraftCard({ loop, onChange, lines }: {
  loop: LoopDraft | null; onChange: (l: LoopDraft | null) => void; lines: DefinitionLine[];
}) {
  if (!loop) {
    return (
      <div className="flex justify-center">
        <button type="button" className="erp-actbtn" onClick={() => onChange(NEW_LOOP)}
          data-tip="Der Auftrag wiederholt sich im Takt – jedes Mal als Kopie mit denselben Modulen">
          <Repeat size={15} /> Wiederholen
        </button>
      </div>
    );
  }
  const set = (patch: Partial<LoopDraft>) => onChange({ ...loop, ...patch });
  const stock = lines.filter((l) => l.articleObjectId !== null && l.origin === LAGER);
  return (
    <div style={CARD}>
      <Head right={<ActionButton icon={X} label="Nicht wiederholen" square
        onClick={() => onChange(null)} />} />
      <div style={ROW}>
        <span style={KEY}>Takt</span>
        <Segmented value={loop.every} onChange={(v) => set({ every: v })} options={EVERY} />
      </div>
      <div style={ROW}>
        <span style={KEY}>Ab</span>
        <div style={{ width: 170 }}>
          <Input name="loop.first" type="date" value={loop.first} required
            className={inputClass('normal')} onChange={(v) => set({ first: v })} />
        </div>
      </div>
      <div style={ROW}>
        <span style={KEY}>Bis</span>
        <Segmented value={loop.end} onChange={(v) => set({ end: v as LoopDraft['end'] })}
          options={ENDS} />
        {loop.end !== 'never' && (
          <div style={{ width: loop.end === 'until' ? 170 : 96 }}>
            <Input name={`loop.${loop.end}`} required className={inputClass('normal')}
              type={loop.end === 'until' ? 'date' : 'number'}
              value={loop.end === 'until' ? loop.until : loop.count}
              onChange={(v) => set(loop.end === 'until' ? { until: v } : { count: v })} />
          </div>
        )}
      </div>
      {stock.map((l, i) => (
        <div key={l.key} style={ROW}>
          <span style={KEY}>{stock.length > 1 ? `Nimmt ${i + 1}` : 'Nimmt'}</span>
          <Segmented value={loop.takes[l.key] ?? ''} options={TAKES}
            tip="Aus dem Lager: jedes Mal dieselben Stücke – oder die ältesten freien (FIFO)"
            onChange={(v) => set({ takes: { ...loop.takes, [l.key]: v } })} />
        </div>
      ))}
    </div>
  );
}

/** ►► **Am laufenden Auftrag**: Zustand, Satz, Zeilen – und «Beenden», wo es geht. ◄◄ */
export function LoopRunCard({ loop, busy, onEnd }: {
  loop: LoopView; busy: boolean; onEnd: () => void;
}) {
  const [asking, setAsking] = useState(false);
  const tone = TONE[(loop.tone as keyof typeof TONE)] ?? TONE.pending;
  const end = loop.may_end && (asking ? (
    <span className="flex items-center gap-2 text-xs" style={{ color: 'var(--fg-3)' }}>
      Endgültig beenden?
      <button type="button" className="erp-actbtn" disabled={busy}
        onClick={() => { setAsking(false); onEnd(); }}>Beenden</button>
      <button type="button" className="erp-actbtn" onClick={() => setAsking(false)}>Abbrechen</button>
    </span>
  ) : (
    <button type="button" className="erp-actbtn" disabled={busy} onClick={() => setAsking(true)}
      data-tip="Es entsteht kein weiterer Auftrag mehr. Dieser hier läuft zu Ende.">
      Beenden
    </button>
  ));
  return (
    <div style={CARD}>
      <Head right={end || undefined} />
      <div className="flex items-center gap-2 text-sm" style={{ color: 'var(--fg-1)' }}>
        <StatusDot color={tone.color} />
        <span style={{ fontWeight: 600 }}>{loop.state_label}</span>
        <span style={{ color: 'var(--fg-3)' }}>· {loop.sentence}</span>
      </div>
      {loop.reason && <p className="text-xs" style={{ color: tone.color, margin: 0 }}>{loop.reason}</p>}
      {(loop.lines ?? []).map((ln) => (
        <div key={ln.position} className="text-xs" style={ROW}>
          <span style={KEY}>Nimmt</span>
          <span style={{ color: 'var(--fg-2)' }}>{ln.article_name} – {ln.take_label}</span>
        </div>
      ))}
      <Links loop={loop} />
    </div>
  );
}

/** Woher, wohin, und woher die Zusage stammt – je eine Nummer, nie ein Satz ohne sie. */
function Links({ loop }: { loop: LoopView }) {
  const rows: Array<[string, number, string?]> = [];
  if (loop.predecessor) rows.push(['Vorher', loop.predecessor]);
  if (loop.successor) rows.push(['Weiter in', loop.successor]);
  if (loop.agreed_from) {
    rows.push(['Zusage aus', loop.agreed_from,
      loop.agreed_on ? `vom ${day(loop.agreed_on)}, ohne neue Offerte` : undefined]);
  }
  if (!rows.length) return null;
  return (
    <div className="flex flex-col gap-1.5 text-xs">
      {rows.map(([word, nr, note]) => (
        <div key={word} style={ROW}>
          <span style={KEY}>{word}</span>
          <span className="flex items-center gap-1.5" style={{ color: 'var(--fg-3)' }}>
            Auftrag <ObjId value={nr} /> {note}
          </span>
        </div>
      ))}
    </div>
  );
}
