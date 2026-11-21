'use client';

import { useQuery } from '@tanstack/react-query';
import { Fingerprint, Package } from 'lucide-react';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import { instanceName } from '@/lib/record-name';
import { kindLabel } from '@/lib/record-status';
import { DetailBody, DetailHeader, ReadField, SectionSep, SPEC, SpecHead } from '@/components/erp/detail-frame';
import { History } from '@/components/erp/history';
import { DocumentTiles } from '@/components/erp/documents';
import { ObjId } from '@/components/erp/obj-id';
import { StockView } from '@/components/erp/stock-view';
import { LabelButton } from '@/components/scan/object-label';
import { DetailSkeleton } from './skeleton';
import { NOTHING } from '@/lib/when';

/**
 * Instanz-Detail – eine **Gruppe** und ihre Einzelinstanzen.
 *
 * Hier gibt es nichts zu tun – gearbeitet wird am Prozess; übrig bleibt die Auskunft: woher die
 * Gruppe stammt und was in ihr liegt. Dieselbe Anatomie wie der Artikel (`DetailHeader`, dann
 * Herkunft und Bestand aus `stock-view.tsx`). Die Gruppe trägt keinen Zustand – er steht an
 * den Stücken.
 */
export function InstanceDetail({ objectId, onBack }: { objectId: number; onBack?: () => void }) {
  const query = useQuery({
    queryKey: qk.instance(objectId),
    queryFn: ({ signal }) => api.getInstance(objectId, { signal }),
    meta: { what: 'Instanz' },
  });
  const rec = query.data ?? null;
  const error = !rec && query.error ? query.error.message : null;

  if (error) return <div className="p-6 text-sm" style={{ color: 'var(--danger)' }}>{error}</div>;
  if (!rec) return <DetailSkeleton />;

  return (
    <div className="flex flex-col h-full bg-bg-1">
      <DetailHeader
        type="instance"
        title={instanceName(rec)}
        objectId={rec.object_id}
        actions={<LabelButton objectId={rec.object_id} title={rec.article_name} kind="Instanz" />}
        onBack={onBack}
      />

      <div style={{ flex: 1, overflowY: 'auto', padding: '24px clamp(14px, 4vw, 28px) 88px', background: 'var(--bg-2)' }}>
        <DetailBody gap={22}>
          {/* Woher stammt diese Gruppe? Der Artikel als verlinkte Objektnummer – die
              Spezifikation liegt einen Klick entfernt. */}
          <div style={SPEC.card}>
            <SpecHead icon={Package} title="Herkunft" />
            <div style={SPEC.grid}>
              <ReadField
                icon={Package}
                label="Artikel"
                full
                value={
                  <span className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
                    {rec.article_object_id != null
                      ? <ObjId value={rec.article_object_id} />
                      : <span className="text-fg-4">{NOTHING}</span>}
                    <span>{rec.article_name ?? 'Unbekannter Artikel'}</span>
                  </span>
                }
              />
              <ReadField icon={Fingerprint} label="Serialisierung" value={kindLabel(rec.kind)} />
            </div>
          </div>

          {/* Dasselbe Bestandsmodul wie am Artikel, im kleineren Umfang. */}
          <StockView scope={{ kind: 'instance', record: rec }} />
          <DocumentTiles objectId={rec.object_id} />
          <SectionSep label="Verlauf" />
          <History objectId={rec.object_id} />
        </DetailBody>
      </div>
    </div>
  );
}

export { ObjId };
