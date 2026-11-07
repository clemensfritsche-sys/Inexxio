'use client';

import { useState } from 'react';
import { CheckCircle2, Info, Plus, X } from 'lucide-react';
import { api } from '@/lib/api';
import { tell } from '@/lib/notice';
import { useDecide } from '@/lib/proposals';
import { inputCls } from '@/components/erp/controls';
import { MICRO_LABEL } from '@/components/erp/fields';
import { ErrorText } from '@/components/erp/hints';
import { useErpNav } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import { findTargets, type TargetOption } from '@/components/erp/document-detail';
import { formatObjectId } from '@/lib/utils';
import { TextArea } from '@/components/form/field';
import { SheetHead } from '@/components/erp/capture/sheet-head';
import { useCapture } from '@/components/erp/capture/capture-context';
import { ProposalCard, type ProposalAction } from '@/components/erp/capture/proposal-card';
import type { Intake, IntakePart, Proposal } from '@/types';

/** Ein Teil im Entwurf – `key` hält React-Schlüssel stabil, auch wenn zwei Teile an denselben
 *  Datensatz gehen. */
type Draft = IntakePart & { key: number };

/**
 * ►►► **«Abgelegt»** – schlicht: je Teil der Datensatz und der Text, darunter die Vorschläge,
 * dann «Stimmt so». ◄◄◄ (Akte §4.4, Bauplan «Oberfläche»)
 *
 * Den Datensatz antippen = einen anderen wählen (`ObjectSelect`, Nummer oder Name); der Text
 * ist bearbeitbar. «Stimmt so» legt je Teil eine Notiz an (`POST /erp/intake/{id}/file`) und
 * schliesst. Wer es später tun will, schliesst einfach – die Erfassung bleibt offen und steht
 * im «+» unter «Nicht abgelegt». Konnte die KI nicht ablegen, sagt `problem` warum (leise); der
 * ganze Text steht dann am Hinweis bzw. an der Person – «Stimmt so» geht trotzdem.
 */
export function Filed({ intake, onClose }: { intake: Intake; onClose: () => void }) {
  const [parts, setParts] = useState<Draft[]>(() => intake.parts.map((p, key) => ({ ...p, key })));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const missing = !parts.length || parts.some((p) => !p.object_id || !p.text.trim());
  const set = (key: number, patch: Partial<Draft>) =>
    setParts((ps) => ps.map((p) => (p.key === key ? { ...p, ...patch } : p)));

  async function file() {
    setBusy(true);
    setError('');
    try {
      await api.fileIntake(intake.id, parts.map(({ object_id, text, subject }) =>
        ({ object_id, text: text.trim(), ...(subject ? { subject } : {}) })));
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Nicht abgelegt.');
      tell('Erfassung', 'Nicht abgelegt')(e);
      setBusy(false);
    }
  }

  const title = <><CheckCircle2 size={18} style={{ color: 'var(--success)' }} aria-hidden />Abgelegt</>;
  return (
    <>
      <SheetHead title={title} onClose={onClose} />
      <div style={{ padding: '14px 16px 16px', display: 'flex', flexDirection: 'column', gap: 14, overflowY: 'auto' }}>
        {intake.problem && (
          <p style={{ margin: 0, display: 'flex', gap: 8, fontSize: 12.5, lineHeight: 1.45, color: 'var(--fg-3)' }}>
            <Info size={14} style={{ flex: 'none', marginTop: 2 }} aria-hidden />{intake.problem}
          </p>
        )}
        {parts.map((p) => (
          <PartRow key={p.key} part={p} onChange={(patch) => set(p.key, patch)}
            onRemove={parts.length > 1 ? () => setParts((ps) => ps.filter((x) => x.key !== p.key)) : undefined} />
        ))}
        {!intake.filed && (
          <button type="button" className="erp-actbtn erp-actbtn-neutral" style={{ alignSelf: 'flex-start', height: 32 }}
            onClick={() => setParts((ps) => [...ps, { object_id: 0, label: '', text: '', subject: '',
              key: Math.max(-1, ...ps.map((x) => x.key)) + 1 }])}>
            <Plus size={14} />Weiterer Teil
          </button>
        )}
        <IntakeProposals intake={intake} onClose={onClose} />
        {error && <ErrorText msg={error} />}
        {/* Unten festgehalten: «Stimmt so» ist immer mit dem Daumen erreichbar. */}
        <div style={{ position: 'sticky', bottom: -16, margin: '0 -16px -16px', padding: '10px 16px 16px',
          background: 'var(--bg-1)', borderTop: '1px solid var(--border-1)', display: 'flex' }}>
          {intake.filed ? (
            <button type="button" onClick={onClose} className="erp-actbtn erp-actbtn-neutral" style={{ height: 48, flex: 1 }}>
              Schliessen
            </button>
          ) : (
            <button type="button" onClick={() => void file()} disabled={busy || missing}
              data-tip={missing ? 'Jeder Teil braucht einen Datensatz und Text.' : undefined}
              className="erp-actbtn erp-actbtn-primary" style={{ height: 48, fontSize: 15, flex: 1 }}>
              {busy ? 'legt ab …' : 'Stimmt so'}
            </button>
          )}
        </div>
      </div>
    </>
  );
}

/** Ein Teil: der Datensatz als Chip (antippen = anderer), darunter der Text. */
function PartRow({ part, onChange, onRemove }: {
  part: Draft; onChange: (patch: Partial<Draft>) => void; onRemove?: () => void;
}) {
  const [choosing, setChoosing] = useState(!part.object_id);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, minWidth: 0 }}>
        {choosing ? (
          <div style={{ flex: 1, minWidth: 0 }}>
            <ObjectSelect<TargetOption> value={part.object_id || null} find={findTargets}
              selected={part.object_id ? { object_id: part.object_id, name: part.label } : null}
              placeholder="Datensatz – Nummer oder Name"
              onChange={(id, opt) => {
                if (!id) return;
                onChange({ object_id: id, label: opt?.name ?? String(id) });
                setChoosing(false);
              }} />
          </div>
        ) : (
          <button type="button" onClick={() => setChoosing(true)} data-tip="Anderer Datensatz"
            className="erp-capture-chip">
            <span className="erp-objid" style={{ font: '500 13px var(--font-mono)', fontVariantNumeric: 'tabular-nums' }}>
              {formatObjectId(part.object_id)}
            </span>
            <span className="truncate">{part.label}</span>
          </button>
        )}
        {onRemove && (
          <button type="button" onClick={onRemove} aria-label="Teil entfernen" data-tip="Teil entfernen"
            className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon" style={{ height: 32, flex: 'none' }}>
            <X size={14} />
          </button>
        )}
      </div>
      <TextArea name="text" value={part.text} onChange={(text) => onChange({ text })} rows={3}
        aria-label={`Text zu ${part.label || 'diesem Teil'}`} className={inputCls}
        style={{ fontSize: 15, lineHeight: 1.45, resize: 'vertical' }} />
    </div>
  );
}

/** Die Vorschläge, die aus der Erfassung folgen – dieselbe Karte wie im Angehefteten. */
function IntakeProposals({ intake, onClose }: { intake: Intake; onClose: () => void }) {
  const decide = useDecide();
  const capture = useCapture();
  const nav = useErpNav();
  const [gone, setGone] = useState<number[]>([]);
  const list = intake.proposals.filter((p) => p.kind !== 'file' && !gone.includes(p.id));
  if (!list.length) return null;
  const actionOf = (p: Proposal): ProposalAction | null => {
    if (p.kind === 'create' && p.draft && capture) {
      const d = p.draft;
      return { label: 'Entwurf öffnen', run: () => { onClose(); capture.createDraft(d.type, d.values); } };
    }
    // Das Feld steht am Datensatz – dort trägt es das Zeichen, und das Angeheftete nennt es.
    return nav ? { label: 'Öffnen', run: () => { onClose(); nav(p.object_id); } } : null;
  };
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)' }}>Vorschläge</span>
      {list.map((p) => (
        <ProposalCard key={p.id} p={p} withRecord action={actionOf(p)}
          onReject={() => { setGone((g) => [...g, p.id]); void decide.reject(p); }} />
      ))}
    </div>
  );
}
