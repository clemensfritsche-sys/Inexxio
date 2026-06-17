'use client';

import { useEffect, useState } from 'react';
import { Boxes } from 'lucide-react';
import { api } from '@/lib/api';
import type { Instance } from '@/types';
import { qcStatusConfig, instanceKindLabel } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';
import { StatusBadge, Placeholder } from '@/components/erp/fields';

export function InstanceList({ articleObjectId, unit }: { articleObjectId: number | null; unit?: string }) {
  const [items, setItems] = useState<Instance[]>([]);
  const [loading, setLoading] = useState(false);

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
    return <div style={{ fontSize: 13, color: '#94a3b8', padding: 12 }}>Laden…</div>;
  }
  if (items.length === 0) {
    return <Placeholder icon={Boxes} title="Kein Bestand" text="Instanzen entstehen bei der Serialisierung eines freigegebenen Auftrags." />;
  }

  const totalQty = items.reduce((sum, i) => sum + (i.quantity || 0), 0);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#64748b' }}>
        <Boxes size={14} /> {items.length} Instanz{items.length === 1 ? '' : 'en'} · {totalQty} {unit ?? 'Stk'} gesamt
      </div>
      {items.map((i) => (
        <div key={i.id} style={{ display: 'flex', alignItems: 'center', gap: 10, background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '10px 12px' }}>
          <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(i.object_id ?? null)}</span>
          <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>
            {i.kind === 'batch' ? `Charge · ${i.quantity} ${unit ?? ''}`.trim() : instanceKindLabel(i.kind)}
            {i.order_object_id ? ` · Auftrag ${fmtObjId(i.order_object_id)}` : ''}
          </span>
          <StatusBadge cfg={qcStatusConfig(i.qc_status)} />
        </div>
      ))}
    </div>
  );
}
