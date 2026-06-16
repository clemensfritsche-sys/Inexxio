'use client';

import { useState } from 'react';
import { Hash, Lock } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order } from '@/types';
import { qcStatusConfig } from '@/lib/process';
import { fmtObjId } from '@/components/erp/user-detail';
import { StatusBadge } from '@/components/erp/fields';

export function SerializationPanel({ order, stepState, onOrderUpdated }: {
  order: Order;
  stepState: string;
  onOrderUpdated: (o: Order) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const instances = order.instances ?? [];
  const isBatch = order.article_serialization === 'batch';
  const qty = order.quantity || 0;
  const preview = isBatch ? `1 Charge à ${qty} ${order.article_unit ?? ''}`.trim() : `${qty} Einzel-Instanzen`;

  async function run() {
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.serializeOrder(order.object_id as number));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Serialisieren');
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={cardStyle}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Hash size={15} style={{ color: '#2563eb' }} />
        <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A', flex: 1 }}>Serialisierung</span>
      </div>

      {instances.length > 0 ? (
        <>
          <div style={{ fontSize: 12, color: '#64748b' }}>
            {instances.length === 1 && isBatch
              ? `1 Charge mit ${instances[0].quantity} ${order.article_unit ?? ''}`.trim()
              : `${instances.length} Instanz${instances.length === 1 ? '' : 'en'} angelegt`}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 260, overflowY: 'auto' }}>
            {instances.map((i) => (
              <div key={i.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', border: '1px solid #f1f5f9', borderRadius: 8 }}>
                <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(i.object_id ?? null)}</span>
                <span style={{ fontSize: 12, color: '#64748b', flex: 1 }}>
                  {i.kind === 'batch' ? `Charge · ${i.quantity} ${order.article_unit ?? ''}`.trim() : 'Einzelteil'}
                </span>
                <StatusBadge cfg={qcStatusConfig(i.qc_status)} />
              </div>
            ))}
          </div>
        </>
      ) : stepState === 'active' ? (
        <>
          <div style={{ fontSize: 13, color: '#374151' }}>
            Es werden <b>{preview}</b> mit eigener Nummer angelegt
            {isBatch ? '' : ' (Einzelteil-Serialisierung)'}.
          </div>
          {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button onClick={run} disabled={saving}
              style={{ padding: '7px 16px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}>
              {saving ? 'Serialisiere…' : 'Serialisieren'}
            </button>
          </div>
        </>
      ) : (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Lock size={14} /> Wird aktiv, sobald der vorherige Schritt erledigt ist.
        </div>
      )}
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
