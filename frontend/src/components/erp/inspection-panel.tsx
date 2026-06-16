'use client';

import { useState } from 'react';
import { ClipboardCheck, Lock, CheckCircle2, XCircle } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order } from '@/types';
import { TextField } from '@/components/erp/fields';

export function InspectionPanel({ order, stepState, onOrderUpdated }: {
  order: Order;
  stepState: string;
  onOrderUpdated: (o: Order) => void;
}) {
  const insp = order.inspection;
  const required = insp?.required_count ?? 0;
  const pct = insp?.sample_percent ?? 100;
  const result = insp?.result ?? 'pending';
  const done = result === 'passed' || result === 'failed';

  const [checked, setChecked] = useState(insp?.checked_count != null ? String(insp.checked_count) : '');
  const [note, setNote] = useState(insp?.note ?? '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const qty = order.quantity || 0;

  async function submit(res: 'passed' | 'failed') {
    const checkedNum = checked.trim() === '' ? 0 : Math.trunc(Number(checked));
    if (res === 'passed' && checkedNum < required) {
      setError(`Für die Freigabe müssen mindestens ${required} Stück geprüft sein`);
      return;
    }
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.updateOrderInspection(order.object_id as number, {
        result: res,
        checked_count: checked.trim() === '' ? null : checkedNum,
        note: note.trim() || null,
      }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  if (stepState === 'locked') {
    return (
      <div style={cardStyle}>
        <Header />
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#94a3b8' }}>
          <Lock size={14} /> Wird aktiv, sobald die Serialisierung erledigt ist.
        </div>
      </div>
    );
  }

  return (
    <div style={cardStyle}>
      <Header />

      <div style={{ background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '8px 12px', fontSize: 13, color: '#374151' }}>
        Prüfumfang: <b>{required}</b> von {qty} Stück <span style={{ color: '#94a3b8' }}>({pct}% Stichprobe)</span>
      </div>

      {done ? (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 12px', borderRadius: 8,
          background: result === 'passed' ? '#f0fdf4' : '#fef2f2', color: result === 'passed' ? '#16a34a' : '#dc2626' }}>
          {result === 'passed' ? <CheckCircle2 size={16} /> : <XCircle size={16} />}
          <span style={{ fontSize: 13, fontWeight: 700 }}>{result === 'passed' ? 'Bestanden' : 'Durchgefallen'}</span>
          {insp?.checked_count != null && <span style={{ fontSize: 12, color: '#64748b' }}>· {insp.checked_count} geprüft</span>}
          {insp?.inspector_name && <span style={{ fontSize: 12, color: '#94a3b8', marginLeft: 'auto' }}>{insp.inspector_name}</span>}
        </div>
      ) : null}
      {done && insp?.note && (
        <div style={{ fontSize: 13, color: '#374151' }}><span style={{ color: '#94a3b8' }}>Notiz:</span> {insp.note}</div>
      )}

      {/* Erfassung (auch nachträglich korrigierbar) */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 14 }}>
        <TextField label="Geprüft (Stück)" value={checked} onChange={setChecked} placeholder={String(required)} />
        <TextField label="Notiz (optional)" value={note} onChange={setNote} placeholder="Bemerkung zur Prüfung" />
      </div>
      {error && <div style={{ fontSize: 12, color: '#dc2626' }}>{error}</div>}
      <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
        <button onClick={() => submit('failed')} disabled={saving}
          style={{ padding: '7px 14px', borderRadius: 7, border: '1px solid #fecaca', background: '#fff', color: '#dc2626', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}>
          Durchgefallen
        </button>
        <button onClick={() => submit('passed')} disabled={saving}
          style={{ padding: '7px 14px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#16a34a', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer' }}>
          {saving ? '…' : 'Bestanden'}
        </button>
      </div>
    </div>
  );
}

function Header() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <ClipboardCheck size={15} style={{ color: '#2563eb' }} />
      <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Eingangskontrolle</span>
    </div>
  );
}

const cardStyle: React.CSSProperties = {
  background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px',
  display: 'flex', flexDirection: 'column', gap: 12,
};
