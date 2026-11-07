'use client';

import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Check, Loader2, Pin, RefreshCw } from 'lucide-react';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import { tell } from '@/lib/notice';
import { when, whenTitle } from '@/lib/when';
import { openAtField, pinnedOpen, useDecide, useFieldsOnPage, usePinned } from '@/lib/proposals';
import { MICRO_LABEL } from '@/components/erp/fields';
import { useCapture } from '@/components/erp/capture/capture-context';
import { ProposalCard, type ProposalAction } from '@/components/erp/capture/proposal-card';
import type { Pinned as PinnedData, Proposal } from '@/types';

/**
 * ►►► **Das Angeheftete – unten beim Neuesten im Verlauf** (Akte §4.2, Bauplan «Oberfläche»). ◄◄◄
 *
 * Zuerst **alle offenen Vorschläge** des Datensatzes (immer; sie verschwinden nur durch einen
 * Entscheid), dann die **Hinweise** der KI – gewählt **auf Abruf** («neu ansehen», nie von
 * selbst), jeder lässt sich lösen. «neu ansehen» ersetzt nur die Hinweise: die Vorschläge kommen
 * in jeder Antwort mit, und was lokal entschieden ist, bleibt weg (`lib/proposals`).
 *
 * Je Art eine Handlung: `change` «Zum Feld» (nur, wenn das Feld auf der Seite steht – sonst
 * zeigt die Karte Wert und Quelle, ✕ geht immer) · `create` «Entwurf öffnen». Eine Erfassung,
 * die auf «Stimmt so» wartet, steht nicht hier, sondern im «+» (die Zahl am Knopf). Sprungziel
 * von «zu tun» (Abschnitt `vorschlaege`).
 */
export function Pinned({ objectId }: { objectId: number }) {
  const { data } = usePinned(objectId);
  const client = useQueryClient();
  const [busy, setBusy] = useState(false);
  const proposals = data?.proposals ?? [];
  const hints = data?.hints ?? [];

  /** Die Antwort des Servers ist das Angeheftete – lokal Entschiedenes bleibt draussen. */
  const keep = (next: PinnedData) => { client.setQueryData(qk.pins(objectId), pinnedOpen(next)); };
  async function refresh() {
    setBusy(true);
    try { keep(await api.refreshPins(objectId)); } catch (e) { tell('Hinweise', 'Nicht neu angesehen')(e); }
    finally { setBusy(false); }
  }
  const solve = (key: string) => api.solvePin(objectId, key).then(keep, tell('Hinweis', 'Nicht gelöst'));

  return (
    <section aria-label="Angeheftet" data-todo="vorschlaege"
      style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6, paddingTop: 8,
        borderTop: '1px solid var(--border-1)', scrollMarginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 32 }}>
        <Pin size={13} aria-hidden style={{ color: 'var(--fg-3)' }} />
        <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)', flex: 1 }}>
          {proposals.length || hints.length ? 'Angeheftet' : 'Nichts angeheftet'}
        </span>
        {data?.refreshed_at && (
          <span className="tabular-nums" style={{ fontSize: 11.5, color: 'var(--fg-4)' }}
            data-tip={whenTitle(data.refreshed_at)}>{when(data.refreshed_at)}</span>
        )}
        <button type="button" onClick={() => void refresh()} disabled={busy}
          data-tip="Die KI sieht nach, was hier jetzt wichtig ist"
          className="erp-actbtn erp-actbtn-neutral" style={{ height: 28, padding: '0 10px', fontSize: 12 }}>
          {busy ? <Loader2 size={13} className="animate-spin" /> : <RefreshCw size={13} />}
          {busy ? 'sieht nach …' : 'neu ansehen'}
        </button>
      </div>
      <PinnedProposals proposals={proposals} />
      {hints.map((h) => (
        <div key={h.key} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 2px 6px 10px',
          borderLeft: '1px solid var(--border-1)', fontSize: 13, color: 'var(--fg-2)' }}>
          <button type="button" disabled={!h.entry_key} onClick={() => toEntry(h.entry_key ?? null)}
            data-tip={h.entry_key ? 'Im Verlauf zeigen' : undefined}
            style={{ flex: 1, minWidth: 0, textAlign: 'left', background: 'none', border: 'none', padding: 0,
              font: 'inherit', color: 'inherit', cursor: h.entry_key ? 'pointer' : 'default', overflowWrap: 'anywhere' }}>
            {h.text}
          </button>
          <button type="button" onClick={() => void solve(h.key)} className="erp-actbtn erp-actbtn-neutral"
            style={{ height: 28, padding: '0 10px', fontSize: 12, flex: 'none' }}>
            <Check size={13} />lösen
          </button>
        </div>
      ))}
      {data?.problem && <p style={{ margin: 0, fontSize: 12, color: 'var(--fg-3)' }}>{data.problem}</p>}
    </section>
  );
}

/** Ein Hinweis zeigt auf einen Eintrag des Verlaufs – ist er geladen, dorthin rollen. */
function toEntry(key: string | null) {
  if (!key) return;
  // Der Eintrag selbst hat keine Box (`display: contents`) – gerollt wird zu seinem Inhalt.
  document.querySelector(`[data-entry="${CSS.escape(key)}"]`)?.firstElementChild
    ?.scrollIntoView({ behavior: 'smooth', block: 'center' });
}

/** Die offenen Vorschläge – je Art die eine Handlung, die hier geht. */
function PinnedProposals({ proposals }: { proposals: Proposal[] }) {
  const decide = useDecide();
  const capture = useCapture();
  const onPage = useFieldsOnPage(proposals.filter((p) => p.kind === 'change').map((p) => p.id));
  const actionOf = (p: Proposal): ProposalAction | null => {
    if (p.kind === 'change') return onPage.has(p.id) ? { label: 'Zum Feld', run: () => openAtField(p.id) } : null;
    if (p.kind === 'create' && p.draft && capture) {
      const draft = p.draft;
      return { label: 'Entwurf öffnen', run: () => capture.createDraft(draft.type, draft.values) };
    }
    return null;
  };
  return (
    <>
      {proposals.map((p) => (
        <ProposalCard key={p.id} p={p} action={actionOf(p)} onReject={() => void decide.reject(p)} />
      ))}
    </>
  );
}
