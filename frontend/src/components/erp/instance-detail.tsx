'use client';

import { useEffect, useState } from 'react';
import { Boxes, Package, Hash, Plus, Trash2, Layers } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance, InstanceUnit } from '@/types';
import { TYPE_META } from '@/lib/erp-record';
import { instanceName } from '@/lib/record-name';
import { instanceStatus, kindLabel } from '@/lib/record-status';
import { formatObjectId } from '@/lib/utils';
import { Card, DetailHeader, ReadField, SPEC, StatusBadge } from '@/components/erp/fields';
import { ObjId } from '@/components/erp/obj-id';
import { CapturePanel } from '@/components/erp/capture-panel';

/**
 * Instanz-Detail – eine **Gruppe** und ihre Einzelinstanzen.
 *
 * Die Menge steht als Zahl da, ist aber nirgends gespeichert: sie ist die Anzahl der
 * Einzelinstanzen darunter. Das ist der ganze Punkt des neuen Modells – wer die Menge
 * ändern will, legt Einzelinstanzen an oder deaktiviert welche.
 *
 * Gearbeitet wird an der Einzelinstanz: die Datenerfassung hängt an genau einem Stück,
 * darum wählt man es hier aus.
 */
export function InstanceDetail({ objectId, onBack }: { objectId: number; onBack?: () => void }) {
  const [rec, setRec] = useState<Instance | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<InstanceUnit | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let dead = false;
    setSelected(null);
    api.getInstance(objectId)
      .then((r) => { if (!dead) { setRec(r); setError(null); } })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [objectId]);

  if (error) return <div className="p-6 text-sm" style={{ color: 'var(--danger)' }}>{error}</div>;
  if (!rec) return null;

  const meta = TYPE_META.instance;

  async function addUnits() {
    setBusy(true);
    try { setRec(await api.addInstanceUnits(objectId, 1)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  async function removeUnit(suffix: number) {
    setBusy(true);
    try {
      const next = await api.deactivateInstanceUnit(objectId, suffix);
      setRec(next);
      if (selected?.suffix === suffix) setSelected(null);
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <div className="flex flex-col h-full overflow-auto">
      <DetailHeader
        icon={meta.icon}
        iconBg={meta.bg}
        iconFg={meta.fg}
        eyebrow={meta.label}
        title={instanceName(rec)}
        objectId={rec.object_id}
        status={instanceStatus(rec)}
        onBack={onBack}
      />

      <div className="w-full max-w-[880px] mx-auto px-5 py-5 flex flex-col gap-4">
        <Card icon={Layers} title="Merkmale">
          <div style={SPEC.grid}>
            <ReadField icon={Package} label="Artikel" value={rec.article_name ?? '—'} />
            <ReadField
              icon={Hash}
              label="Artikelnummer"
              value={rec.article_object_id ? formatObjectId(rec.article_object_id) : '—'}
              mono
            />
            <ReadField icon={Boxes} label="Typ" value={kindLabel(rec.kind)} />
            <ReadField
              icon={Hash}
              label="Menge"
              value={String(rec.quantity)}
              autoHint="Gezählt, nicht gespeichert: die Anzahl der Einzelinstanzen unten."
            />
          </div>
        </Card>

        <Card
          icon={Boxes}
          title="Einzelinstanzen"
          right={
            <button
              onClick={addUnits}
              disabled={busy}
              className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-ds-sm border border-border-1 hover:bg-bg-2 disabled:opacity-50"
              title="Eine weitere Einzelinstanz anlegen. Die Nummer ist kumulierend – eine einmal vergebene kommt nie zurück."
            >
              <Plus size={13} /> Einzelinstanz
            </button>
          }
        >
          {rec.units.length === 0 ? (
            <p className="text-sm text-fg-3">Keine Einzelinstanzen.</p>
          ) : (
            <div className="flex flex-col">
              {rec.units.map((u) => (
                <div
                  key={u.id}
                  onClick={() => setSelected(u)}
                  className="flex items-center gap-3 py-2 border-t border-border-1 cursor-pointer hover:bg-bg-2"
                  style={selected?.id === u.id ? { background: 'var(--bg-2)' } : undefined}
                >
                  <span className="font-mono text-[12.5px] font-semibold tabular-nums">{u.number}</span>
                  <span className="text-sm text-fg-3">1 {'×'}</span>
                  <div className="ml-auto flex items-center gap-2">
                    <StatusBadge cfg={instanceStatus({ status: u.status })} />
                    <button
                      onClick={(e) => { e.stopPropagation(); void removeUnit(u.suffix); }}
                      disabled={busy}
                      title="Einzelinstanz deaktivieren. Ihre Nummer bleibt vergeben."
                      className="p-1 rounded-ds-sm hover:bg-bg-3 disabled:opacity-40"
                    >
                      <Trash2 size={13} style={{ color: 'var(--danger)' }} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Card>

        {selected ? (
          <CapturePanel number={selected.number} />
        ) : (
          <Card icon={Boxes} title="Datenerfassung">
            <p className="text-sm text-fg-3">
              Erfasst wird an einer Einzelinstanz – bitte oben eine auswählen.
            </p>
          </Card>
        )}
      </div>
    </div>
  );
}

export { ObjId };
