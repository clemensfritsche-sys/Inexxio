'use client';

import { AlertCircle, ArrowRight, Check, Clock, Loader2, Sparkles, SquareArrowOutUpRight, X } from 'lucide-react';
import { api } from '@/lib/api';
import { useAction } from '@/lib/use-action';
import { NOTHING, when, whenTitle } from '@/lib/when';
import { ObjId, useErpNav } from '@/components/erp/obj-id';
import { useCapture, type CaptureActions, type DraftFromHandgriff } from '@/components/erp/capture/capture-context';
import type { Handgriff } from '@/types';

/**
 * ►►► **Ein Vorschlag als Karte** – im Gespräch und am Datensatz («Auf einen Blick»). ◄◄◄
 *
 * Die KI führt nie aus; sie schlägt vor, der Mensch entscheidet – **dort, wo die Sache steht**:
 *
 * - **Im Gespräch** nur **Öffnen** und **✕**. Öffnen führt hin: zum Entwurf (überall, wo es «Neu
 *   anlegen» gibt: ausgefüllt, angelegt erst mit «Freigeben») oder zum Datensatz, den er betrifft.
 * - **Am Datensatz** steht, was sich ändert (`feld: alt → neu`, wie es jetzt ist) und
 *   **Übernehmen** – genau einmal, durch die echte Route, mit meinen Rechten; was nicht geht, sagt
 *   der Satz der Route an der Karte. Was einen Entwurf hat, öffnet ihn.
 */
export function HandgriffCard({ h, at = 'talk', onChanged, onLeave }: {
  h: Handgriff;
  /** Wo die Karte steht: im Gespräch (`talk`) oder am Datensatz (`record`). */
  at?: 'talk' | 'record';
  /** Nach einer Handlung – das Gespräch bzw. «Auf einen Blick» lädt nach (`lib/feed`). */
  onChanged?: () => void;
  /** Öffnen führt woandershin – das «+» tritt zur Seite. */
  onLeave?: () => void;
}) {
  const { busy, error: problem, run } = useAction('Ging nicht.');
  const capture = useCapture();
  const nav = useErpNav();
  const draft = capture ? draftOf(h, capture) : null;
  const live = h.state === 'open' || (at === 'talk' && h.state === 'waiting');
  const act = (call: () => Promise<unknown>) => run(async () => { await call(); onChanged?.(); });
  const go = draft ?? (nav && h.object_id ? () => nav(h.object_id) : null);

  return (
    <div className="erp-hg" data-state={h.state}>
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, minWidth: 0 }}>
        <StateIcon h={h} />
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 3 }}>
          <span className="erp-hg-line">{h.line || h.summary}</span>
          <span className="erp-hg-meta">
            <ObjId value={h.object_id} />
            <span className="truncate" style={{ minWidth: 0 }}>{h.label}</span>
            <span aria-hidden>·</span>
            <span>{h.source}</span>
            <span aria-hidden>·</span>
            <span className="tabular-nums" data-tip={whenTitle(h.at)}>{when(h.at)}</span>
          </span>
          {at === 'record' && h.state === 'open' && (h.changes?.length ? <Changes h={h} /> : <Values body={h.body} />)}
          <StateLine h={h} />
        </div>
      </div>
      {problem && <p role="alert" className="erp-capture-problem"><AlertCircle size={15} aria-hidden />{problem}</p>}
      {live && (
        <div className="erp-hg-actions">
          {at === 'talk' || draft ? (
            go && (
              <button type="button" disabled={busy} onClick={() => { go(); onLeave?.(); }}
                className="erp-actbtn erp-actbtn-primary erp-hg-btn">
                <SquareArrowOutUpRight size={14} />{draft && at === 'record' ? 'Entwurf öffnen' : 'Öffnen'}
              </button>
            )
          ) : (
            <button type="button" disabled={busy} onClick={() => void act(() => api.runHandgriff(h.id))}
              className="erp-actbtn erp-actbtn-primary erp-hg-btn">
              {busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />}{isNoteBody(h.body) ? 'Ablegen' : 'Übernehmen'}
            </button>
          )}
          <span style={{ flex: 1 }} />
          <button type="button" disabled={busy} onClick={() => void act(() => api.dropHandgriff(h.id))}
            aria-label="Weg" data-tip="Weg – geschieht nicht" className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon erp-hg-x">
            <X size={14} />
          </button>
        </div>
      )}
    </div>
  );
}

function StateIcon({ h }: { h: Handgriff }) {
  const style = { flex: 'none', marginTop: 1 } as const;
  if (h.state === 'done') return <Check size={15} aria-hidden style={{ ...style, color: 'var(--success)' }} />;
  if (h.state === 'dropped') return <X size={15} aria-hidden style={{ ...style, color: 'var(--fg-4)' }} />;
  if (h.state === 'waiting') return <Clock size={15} aria-hidden style={{ ...style, color: 'var(--fg-3)' }} />;
  return <Sparkles size={15} aria-hidden style={{ ...style, color: 'var(--warning)' }} />;
}

function StateLine({ h }: { h: Handgriff }) {
  if (h.state === 'done') {
    return <span className="erp-hg-state">Übernommen{h.result ? <> · <ObjId value={h.result} /></> : null}</span>;
  }
  if (h.state === 'dropped') return <span className="erp-hg-state">Weggelegt</span>;
  if (h.state === 'waiting') return <span className="erp-hg-state">Wartet auf Vorschlag {(h.waits_for ?? []).join(', ')}</span>;
  return null;
}

/** Was sich ändert – je Feld, wie es jetzt ist, und wie es würde. */
function Changes({ h }: { h: Handgriff }) {
  return (
    <dl className="erp-hg-values">
      {(h.changes ?? []).map((c) => (
        <div key={c.field} style={{ display: 'contents' }}>
          <dt>{c.field}</dt>
          <dd className="erp-hg-change">
            <span className="erp-hg-before">{c.before || NOTHING}</span>
            <ArrowRight size={12} aria-hidden style={{ flex: 'none', color: 'var(--fg-4)' }} />
            <span>{c.after || NOTHING}</span>
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** Die Werte eines neuen Eintrags – Schlüssel und Wert, knapp; was verschachtelt ist, als Text. */
function Values({ body }: { body: unknown }) {
  if (!body || typeof body !== 'object' || Array.isArray(body)) return null;
  // Was die Karte oben schon nennt (die Datensätze, an denen er hängt), steht hier nicht noch einmal.
  const rows = Object.entries(body as Record<string, unknown>).filter(([k, v]) => v !== null && v !== '' && v !== undefined
    && !Array.isArray(v) && k !== 'channel');
  if (!rows.length) return null;
  return (
    <dl className="erp-hg-values">
      {rows.slice(0, 8).map(([k, v]) => (
        <div key={k} style={{ display: 'contents' }}>
          <dt>{k}</dt>
          <dd>{show(v)}</dd>
        </div>
      ))}
    </dl>
  );
}

function show(v: unknown): string {
  if (typeof v === 'string') return v;
  if (typeof v === 'number' || typeof v === 'boolean') return String(v);
  if (v && typeof v === 'object' && '$handgriff' in (v as object)) return `aus Vorschlag ${(v as { $handgriff: number }).$handgriff}`;
  return JSON.stringify(v);
}

const isNoteBody = (b: unknown) => !!b && typeof b === 'object' && (b as { channel?: string }).channel === 'note';

/**
 * **Wo das ERP einen Entwurf hat** – überall, wo es «Neu anlegen» gibt (Person, Firma, Artikel,
 * Auftrag, Dokument): die Anlage-Route der Handlung ist der Schlüssel (`DRAFTS`). Der Entwurf
 * öffnet ausgefüllt; mit «Freigeben» ist der Vorschlag erledigt.
 */
const DRAFTS: Record<string, DraftFromHandgriff['kind']> = {
  '/api/v1/erp/records': 'user',
  '/api/v1/admin/companies': 'organization',
  '/api/v1/erp/articles': 'article',
  '/api/v1/erp/orders': 'order',
  '/api/v1/erp/documents': 'document',
};

function draftOf(h: Handgriff, capture: CaptureActions): (() => void) | null {
  const kind = h.method === 'POST' ? DRAFTS[h.path] : undefined;
  if (!kind) return null;
  const body = (h.body && typeof h.body === 'object' ? h.body : {}) as Record<string, unknown>;
  const values = Object.fromEntries(Object.entries(body).filter(([, v]) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')
    .map(([k, v]) => [k, String(v)]));
  return () => capture.openDraft({ kind, values, body, handgriff: h.id });
}
