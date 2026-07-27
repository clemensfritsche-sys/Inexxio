'use client';

import { useEffect, useState } from 'react';
import { Boxes, ChevronRight } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance } from '@/types';
import { instanceStatusConfig, instanceLabel } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';
import { useErpNav } from '@/components/erp/obj-id';
import { StatusBadge, Placeholder } from '@/components/erp/fields';
import { TYPE_META } from '@/lib/erp-record';

// Farbidentität des Datensatztyps aus der EINEN Quelle (statt hier hart kodiert).
const INST = TYPE_META.instance;

export function InstanceList({ articleObjectId, unit }: { articleObjectId: number | null; unit?: string }) {
  const [items, setItems] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(false);
  const nav = useErpNav();

  useEffect(() => {
    if (articleObjectId == null) return;
    setLoading(true);
    api.getArticleInstances(articleObjectId)
      .then(setItems)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [articleObjectId]);

  if (articleObjectId == null) {
    return <Placeholder icon={Boxes} title="Bestand" text="Artikel zuerst speichern – danach erscheinen hier die Instanzen." />;
  }
  if (loading) {
    return <div style={{ fontSize: 13, color: 'var(--fg-4)', padding: 12 }}>Laden…</div>;
  }
  if (items.length === 0) {
    return <Placeholder icon={Boxes} title="Kein Bestand" text="Instanzen entstehen bei der Serialisierung eines freigegebenen Auftrags." />;
  }

  return (
    // Zentriert und breiter: auf einem 3440er-Schirm klebte die Liste sonst links
    // in einer 720-px-Spalte.
    <div style={{ maxWidth: 980, marginInline: 'auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
        <div style={{ width: 36, height: 36, borderRadius: 'var(--r-sm)', background: INST.bg, color: INST.fg, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
          <Boxes size={18} />
        </div>
        {/* Keine Summenzeile: jede Instanz nennt ihre Menge in der Zeile darunter. */}
        <h3 style={{ font: '800 19px var(--font-display)', letterSpacing: '-.02em', margin: 0, color: 'var(--fg-1)' }}>Bestand</h3>
      </div>
      <div style={{ border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', overflow: 'hidden', background: '#fff' }}>
        {items.map((i, idx) => (
          <button
            key={i.id}
            className="erp-orow"
            onClick={() => i.object_id != null && nav?.(i.object_id)}
            style={{
              display: 'flex', alignItems: 'center', gap: 12, width: '100%', padding: '13px 16px',
              background: '#fff', border: 'none', borderBottom: idx === items.length - 1 ? 'none' : '1px solid var(--border-1)',
              cursor: 'pointer', font: 'inherit', textAlign: 'left',
            }}
          >
            <div style={{ width: 34, height: 34, borderRadius: 'var(--r-sm)', background: INST.bg, color: INST.fg, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
              <Boxes size={16} />
            </div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ font: '700 13.5px var(--font-body)', color: 'var(--fg-1)' }}>
                {instanceLabel(i.kind, i.quantity, unit)}
              </div>
              <div style={{ font: 'var(--mono-sm)', color: 'var(--fg-3)', fontVariantNumeric: 'tabular-nums', marginTop: 2 }}>
                {fmtObjId(i.object_id)}{i.order_object_id ? ` · Auftrag ${fmtObjId(i.order_object_id)}` : ''}
              </div>
            </div>
            <StatusBadge cfg={instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0)} size={11} />
            <span style={{ color: 'var(--fg-4)', display: 'flex', flex: 'none' }}><ChevronRight size={18} /></span>
          </button>
        ))}
      </div>
    </div>
  );
}
