'use client';

import { useEffect, useState } from 'react';
import { Fingerprint, Package } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance } from '@/types';
import { instanceName } from '@/lib/record-name';
import { kindLabel } from '@/lib/record-status';
import { DetailHeader, ReadField, SPEC, SpecHead } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { StockView } from '@/components/erp/stock-view';
import { LabelButton } from '@/components/scan/object-label';

/**
 * Instanz-Detail – eine **Gruppe** und ihre Einzelinstanzen.
 *
 * **Es gibt hier nichts zu tun.** Eine Einzelinstanz entsteht mit ihrer Instanz und die
 * mit einem Auftrag (Testnotiz #678); gelöscht wird sie nie (#679). Gearbeitet wird am
 * Prozess, und dort steht auch, was erfasst wurde. Übrig bleibt die Auskunft: **woher**
 * die Gruppe stammt und **was** in ihr liegt.
 *
 * **Dieselbe Anatomie wie der Artikel**: der Kopf ist der eine `DetailHeader`, darunter
 * Spezifikations-Karten – erst die Herkunft, dann der Bestand. Und der Bestand ist
 * wörtlich dasselbe Modul wie im Artikel-Reiter «Bestand» (`stock-view.tsx`), nur mit dem
 * kleineren Umfang: hier sind die Zeilen direkt die Einzelinstanzen.
 *
 * **Die Gruppe trägt keinen Zustand** (#675). Bei genau einem Stück liesse er sich
 * spiegeln – bei einer Charge mit gemischten Zuständen gibt es keine richtige Antwort,
 * und jede gewählte wäre eine Behauptung. Der Zustand steht an den Stücken, wo er
 * hingehört; die Leiste im Bestand zählt auf, statt zu behaupten.
 */
export function InstanceDetail({ objectId, onBack }: { objectId: number; onBack?: () => void }) {
  const [rec, setRec] = useState<Instance | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let dead = false;
    api.getInstance(objectId)
      .then((r) => { if (!dead) { setRec(r); setError(null); } })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [objectId]);

  if (error) return <div className="p-6 text-sm" style={{ color: 'var(--danger)' }}>{error}</div>;
  if (!rec) return null;

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
        <div style={{ maxWidth: 880, marginInline: 'auto', width: '100%', display: 'flex', flexDirection: 'column', gap: 22 }}>
          {/* **Woher stammt diese Gruppe?** Der Artikel, dessen Erzeugungsprozess sie
              durchlaufen hat – als **verlinkte Objektnummer**, nicht als abgeschriebener
              Name: die Spezifikation liegt einen Klick entfernt und ist dort immer
              aktuell (#676). Die Merkmale daneben (Menge, Zustände) stehen im Bestand
              darunter; sie hier zu wiederholen wäre dieselbe Aussage an zwei Stellen. */}
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
                      : <span className="text-fg-4">—</span>}
                    <span>{rec.article_name ?? 'Unbekannter Artikel'}</span>
                  </span>
                }
              />
              <ReadField icon={Fingerprint} label="Serialisierung" value={kindLabel(rec.kind)} />
            </div>
          </div>

          {/* **Dasselbe Bestandsmodul wie am Artikel** – kein Nachbau, nur der kleinere
              Umfang: die Aufstellung dieser Gruppe und darunter ihre Nummern. */}
          <StockView scope={{ kind: 'instance', record: rec }} />
        </div>
      </div>
    </div>
  );
}

export { ObjId };
