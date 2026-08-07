'use client';

import { useEffect, useState } from 'react';
import { Boxes } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance } from '@/types';
import { TYPE_META } from '@/lib/erp-record';
import { instanceName } from '@/lib/record-name';
import { kindLabel } from '@/lib/record-status';
import { statusCfg } from '@/lib/process-status';
import { Card, DetailHeader, StatusBadge } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { UnitNumber } from '@/components/erp/unit-number';

/**
 * Instanz-Detail – eine **Gruppe** und ihre Einzelinstanzen.
 *
 * **Es gibt hier nichts zu tun.** Eine Einzelinstanz entsteht mit ihrer Instanz und die
 * mit einem Auftrag (Testnotiz #678); gelöscht wird sie nie (#679). Gearbeitet wird am
 * Prozess, und dort steht auch, was erfasst wurde – die frühere Erfassungs-Historie hier
 * war eine zweite Ansicht auf dieselbe Sache, an einem Ort, an dem man nicht arbeitet
 * (#677). Übrig bleibt die Auskunft: **woher** die Gruppe stammt und **welche** Stücke
 * sie enthält.
 *
 * **Die Gruppe trägt keinen Zustand** (#675). Solange genau ein Stück darunter liegt,
 * liesse er sich spiegeln – bei einer Charge mit gemischten Zuständen gibt es keine
 * richtige Antwort, und jede gewählte wäre eine Behauptung. Der Zustand steht an den
 * Stücken, wo er hingehört.
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

  const meta = TYPE_META.instance;

  return (
    <div className="flex flex-col h-full overflow-auto">
      <DetailHeader
        icon={meta.icon}
        iconBg={meta.bg}
        iconFg={meta.fg}
        eyebrow={meta.label}
        title={instanceName(rec)}
        objectId={rec.object_id}
        onBack={onBack}
      />

      <div className="w-full max-w-[880px] mx-auto px-5 py-5 flex flex-col gap-4">
        {/* **Woher stammt diese Gruppe?** Ein Verweis auf den Artikel, dessen
            Erzeugungsprozess sie durchlaufen hat – mehr braucht es nicht (#676). Die
            Merkmale daneben (Name, Nummer, Typ, Menge) standen entweder schon im Kopf
            oder eine Zeile weiter unten; sie am Artikel zu lesen ist ein Klick und
            immer aktuell, statt hier eine Kopie zu pflegen. */}
        <Card icon={meta.icon} title="Herkunft">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-sm">
            {rec.article_object_id ? (
              <ObjId value={rec.article_object_id} />
            ) : (
              <span className="text-fg-4">—</span>
            )}
            <span>{rec.article_name ?? 'Unbekannter Artikel'}</span>
            <span className="text-fg-4">·</span>
            <span className="text-fg-3">{kindLabel(rec.kind)}</span>
          </div>
        </Card>

        {/* Eine Zeile je Stück: Nummer, Zustand. Die Menge steht nicht dabei – eine
            Einzelinstanz IST genau ein Stück, das ist ihre Definition und keine
            Angabe, die man wiederholen müsste (#680). */}
        <Card icon={Boxes} title={`Einzelinstanzen · ${rec.quantity}`}>
          {rec.units.length === 0 ? (
            <p className="text-sm text-fg-3">Keine Einzelinstanzen.</p>
          ) : (
            <div className="flex flex-col">
              {rec.units.map((u) => (
                <div key={u.id}
                  className="flex items-center gap-3 py-1.5 border-t border-border-1">
                  <UnitNumber value={u.number} />
                  <span className="ml-auto">
                    <StatusBadge cfg={statusCfg(u.status)} />
                  </span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export { ObjId };
