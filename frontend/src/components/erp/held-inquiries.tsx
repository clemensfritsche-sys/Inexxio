'use client';

/**
 * ►►► **Aussortiert – Spam aus dem Formular der Website** (`services/spam`). ◄◄◄
 *
 * Die KI hat diese Anfragen für Spam gehalten: es gibt keine Person, keine Nachricht, keine
 * Bestätigung. Sie stehen hier, in der Kommunikation der Gesellschaft, die sie bekommen hätte –
 * getrennt vom Verlauf und als Aufgabe («zu tun»), bis jemand entscheidet: **Kein Spam** legt die
 * Anfrage an wie eben gekommen (samt Bestätigung), **Spam** schliesst sie. Ohne Aussortiertes
 * steht hier nichts.
 */
import { useQuery } from '@tanstack/react-query';
import { Check, ShieldAlert, Trash2 } from 'lucide-react';
import { Card, TodoAt } from '@/components/erp/detail-frame';
import { ErrorText } from '@/components/erp/hints';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import { useAction } from '@/lib/use-action';
import { formatWhen, when } from '@/lib/when';
import type { HeldInquiry } from '@/types';

export function HeldInquiries({ company }: { company: number }) {
  const q = useQuery({
    queryKey: qk.held(company),
    queryFn: ({ signal }) => api.heldInquiries(company, { signal }),
    meta: { what: 'Aussortierte Anfragen' },
  });
  const rows = q.data ?? [];
  if (!rows.length) return null;
  return (
    <TodoAt part="aussortiert" objectId={company}>
      <Card title="Aussortiert" info={'Die KI hält diese Anfragen der Website für Spam: es gibt '
        + 'keine Person, keine Nachricht und keine Bestätigung. «Kein Spam» legt die Anfrage an wie '
        + 'eben gekommen – mit Bestätigung an die Person.'}>
        <div style={{ display: 'grid', gap: 16 }}>
          {rows.map((h, i) => <Held key={h.id} h={h} last={i === rows.length - 1} />)}
        </div>
      </Card>
    </TodoAt>
  );
}

function Held({ h, last }: { h: HeldInquiry; last: boolean }) {
  const { busy, error, run } = useAction('Nicht gespeichert');
  const facts = [h.firm, h.phone, h.source].filter(Boolean).join(' · ');
  return (
    <div style={{ display: 'grid', gap: 6, ...(last ? {} : { paddingBottom: 16, borderBottom: '1px solid var(--border-1)' }) }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <strong style={{ fontSize: 14, color: 'var(--fg-1)' }}>{h.name}</strong>
        <span style={{ fontSize: 13, color: 'var(--fg-3)', overflowWrap: 'anywhere' }}>{h.email}</span>
        <span style={{ flex: 1 }} />
        <span data-tip={formatWhen(h.at)} style={{ fontSize: 12, color: 'var(--fg-3)' }}>{when(h.at)}</span>
      </div>
      {facts && <div style={{ fontSize: 12, color: 'var(--fg-3)' }}>{facts}</div>}
      <p style={{ margin: 0, fontSize: 14, color: 'var(--fg-1)', whiteSpace: 'pre-wrap',
        overflowWrap: 'anywhere' }}>{h.message}</p>
      {h.files.length > 0 && (
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', fontSize: 13 }}>
          {h.files.map((f) => (
            <a key={f.url} href={f.url} target="_blank" rel="noreferrer">{f.name}</a>
          ))}
        </div>
      )}
      {h.reason && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--fg-3)' }}>
          <ShieldAlert size={13} aria-hidden />KI: {h.reason}
        </div>
      )}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 4 }}>
        <button type="button" className="kt-add" disabled={busy}
          data-tip="Die Anfrage anlegen wie eben gekommen – mit Bestätigung an die Person."
          onClick={() => void run(() => api.releaseHeld(h.id))}>
          <Check size={16} aria-hidden />Kein Spam
        </button>
        <button type="button" className="kt-add" disabled={busy}
          data-tip="Entschieden: es entsteht nichts. Die Anfrage bleibt im Log."
          onClick={() => void run(() => api.discardHeld(h.id))}>
          <Trash2 size={16} aria-hidden />Spam
        </button>
      </div>
      {error && <ErrorText msg={error} />}
    </div>
  );
}
