'use client';

import { useEffect, useState } from 'react';
import { Boxes, ChevronRight, Search } from 'lucide-react';
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
  const [q, setQ] = useState('');
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

  // **Neueste zuerst** (wie im Feed: Objektnummern werden aufsteigend vergeben, gemeint ist
  // fast immer die zuletzt entstandene Instanz) + Suche über Objektnummer/Auftrag/Status.
  const shown = [...items]
    .sort((a, b) => (b.object_id ?? 0) - (a.object_id ?? 0))
    .filter((i) => {
      const needle = q.trim().toLowerCase();
      if (!needle) return true;
      const cfg = instanceStatusConfig(i.quality, i.disposition, (i.reserved_quantity ?? 0) > 0);
      return `${fmtObjId(i.object_id)} ${fmtObjId(i.order_object_id ?? null)} ${cfg.label}`.toLowerCase().includes(needle);
    });

  return (
    // Zentriert und breiter: auf einem 3440er-Schirm klebte die Liste sonst links
    // in einer 720-px-Spalte. Die Überschrift «Bestand» steht bereits im Reiter darüber.
    <div style={{ maxWidth: 980, marginInline: 'auto' }}>
      <div style={{ position: 'relative', marginBottom: 12 }}>
        <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--fg-4)', pointerEvents: 'none' }} />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Instanz, Auftrag oder Status suchen"
          style={{ width: '100%', padding: '9px 12px 9px 34px', fontSize: 13.5, borderRadius: 'var(--r-md)', border: '1px solid var(--border-1)', background: '#fff', outline: 'none', boxSizing: 'border-box' }} />
      </div>
      <div style={{ border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)', overflow: 'hidden', background: '#fff' }}>
        {shown.map((i, idx) => (
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
                {fmtObjId(i.object_id)}
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
