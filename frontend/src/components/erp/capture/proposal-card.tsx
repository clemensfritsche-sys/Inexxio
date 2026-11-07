'use client';

import { Sparkles, X } from 'lucide-react';
import { when, whenTitle } from '@/lib/when';
import { ObjId } from '@/components/erp/obj-id';
import type { Proposal } from '@/types';

/** Was ein Vorschlag als Handlung anbietet – je Art genau eine (`change` «Zum Feld», `create`
 *  «Entwurf öffnen», `file` «Abgelegt»). */
export interface ProposalAction { label: string; run: () => void }

/**
 * ►►► **Ein Vorschlag als Zeile – dieselbe Karte in «Abgelegt» und im Angehefteten.** ◄◄◄
 *
 * Wort (was), Wert (wohin), Quelle (woher, wann), eine Handlung und ✕. Die Handlung kommt vom
 * Aufrufer: er weiss, was hier geht (ein Knopf, der nichts kann, steht nicht da). Steht das
 * Feld nicht auf der Seite, ist die Karte selbst das Fenster: Wert, Quelle, ✕.
 */
export function ProposalCard({ p, action, onReject, withRecord }: {
  p: Proposal;
  action?: ProposalAction | null;
  onReject: () => void;
  /** Den Datensatz nennen (in «Abgelegt» stehen Vorschläge an mehreren). */
  withRecord?: boolean;
}) {
  return (
    // Schmal rutschen die Handlungen unter den Text – der Text behält die Breite.
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, padding: '10px 10px 10px 12px', background: 'var(--bg-1)',
      border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', minWidth: 0 }}>
      <div style={{ flex: '1 1 240px', minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, font: '600 13px var(--font-body)',
          color: 'var(--fg-1)', overflowWrap: 'anywhere' }}>
          <Sparkles size={15} aria-hidden style={{ color: 'var(--warning)', flex: 'none', marginTop: 1 }} />
          {p.label}
        </div>
        {p.kind === 'change' && (
          <div style={{ paddingLeft: 23, fontSize: 13, color: 'var(--fg-2)', overflowWrap: 'anywhere' }}>
            {p.current ? <><span style={{ color: 'var(--fg-4)' }}>{p.current}</span> → </> : null}
            <b style={{ fontWeight: 600, color: 'var(--fg-1)' }}>{p.value || '–'}</b>
          </div>
        )}
        <div style={{ paddingLeft: 23, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: '2px 6px', fontSize: 12,
          color: 'var(--fg-3)' }}>
          {withRecord && <><ObjId value={p.object_id} /><span>{p.object_label}</span><span aria-hidden>·</span></>}
          <span>{p.source.text}</span>
          <span aria-hidden>·</span>
          <span className="tabular-nums" data-tip={whenTitle(p.source.at)}>{when(p.source.at)}</span>
        </div>
      </div>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 6, flex: 'none', marginLeft: 'auto' }}>
        {action && (
          <button type="button" onClick={action.run} className="erp-actbtn erp-actbtn-neutral"
            style={{ height: 32, padding: '0 10px', fontSize: 12.5 }}>
            {action.label}
          </button>
        )}
        <button type="button" onClick={onReject} aria-label={`Vorschlag «${p.label}» verwerfen`} data-tip="Verwerfen"
          className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon"
          style={{ height: 32, ['--actbtn-w' as string]: '32px' }}>
          <X size={14} />
        </button>
      </div>
    </div>
  );
}
