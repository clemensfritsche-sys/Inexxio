'use client';

import { Eye, Loader2, Lightbulb } from 'lucide-react';
import { usePinned } from '@/lib/assistant';
import { when, whenTitle } from '@/lib/when';
import { MICRO_LABEL } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { HandgriffCard } from '@/components/erp/capture/handgriff-card';

/**
 * ►►► **Auf einen Blick – unten beim Neuesten im Verlauf** (Projektakte, Phase 5 §8.3). ◄◄◄
 *
 * Zuerst **die offenen Vorschläge** zu diesem Datensatz (aus Mails für jedes Personal, aus meinen
 * Gesprächen nur meine) – hier mit dem, was sich ändert (alt → neu), und «Übernehmen». Dann **das
 * Wissen, das jetzt zählt**: höchstens drei Aussagen mit Datum und Quelle. Meist hat der Takt es
 * schon vorbereitet; hat sich im Umfeld seither etwas geändert, wählt die KI still neu
 * (`lib/assistant.usePinned`) – sonst nicht.
 * Sprungziel von «zu tun» (Abschnitt `handgriffe`).
 */
export function Pinned({ objectId }: { objectId: number }) {
  const { data, choosing } = usePinned(objectId);
  const handgriffe = data?.handgriffe ?? [];
  const knowledge = data?.knowledge ?? [];
  if (!data || (!handgriffe.length && !knowledge.length && !data.stale && !data.problem)) return null;
  return (
    <section aria-label="Auf einen Blick" data-todo="handgriffe"
      style={{ display: 'flex', flexDirection: 'column', gap: 6, marginTop: 6, paddingTop: 8,
        borderTop: '1px solid var(--border-1)', scrollMarginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, minHeight: 28 }}>
        <Eye size={13} aria-hidden style={{ color: 'var(--fg-3)' }} />
        <span style={{ ...MICRO_LABEL, color: 'var(--fg-3)', flex: 1 }}>Auf einen Blick</span>
        {choosing ? (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11.5, color: 'var(--fg-4)' }}>
            <Loader2 size={12} className="animate-spin" aria-hidden />sieht nach …
          </span>
        ) : data.chosen_at && (
          <span className="tabular-nums" style={{ fontSize: 11.5, color: 'var(--fg-4)' }}
            data-tip={whenTitle(data.chosen_at)}>{when(data.chosen_at)}</span>
        )}
      </div>
      {handgriffe.map((h) => <HandgriffCard key={h.id} h={h} at="record" />)}
      {knowledge.map((k, i) => (
        <div key={i} className="erp-knowledge">
          <Lightbulb size={14} aria-hidden style={{ flex: 'none', marginTop: 2, color: 'var(--fg-3)' }} />
          <span style={{ flex: 1, minWidth: 0, overflowWrap: 'anywhere' }}>{k.text}</span>
          {k.source_object_id ? <ObjId value={k.source_object_id} /> : null}
          {k.at && <span className="tabular-nums erp-capture-when" data-tip={whenTitle(k.at)}>{when(k.at)}</span>}
        </div>
      ))}
      {data.problem && <p style={{ margin: 0, fontSize: 12, color: 'var(--fg-3)' }}>{data.problem}</p>}
    </section>
  );
}
