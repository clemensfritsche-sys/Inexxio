'use client';

import { useState } from 'react';
import { ClipboardList, ArrowLeft, Info } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, OrderStatus, OrderUpdateInput } from '@/types';
import { ORDER_STATUS_ORDER, orderStatusConfig } from '@/lib/order';
import { fmtObjId } from '@/components/erp/user-detail';
import { TextField, StatusBadge } from '@/components/erp/fields';

type Form = { title: string; status: string };

function seedFrom(record: Order | null): Form {
  if (!record) return { title: '', status: 'draft' };
  return { title: record.title ?? '', status: record.status };
}

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

export function OrderDetail({ record, onSaved, onCancel, onBack }: {
  record: Order | null;            // null ⇒ Anlage-Modus
  onSaved: (o: Order) => void;
  onCancel: () => void;
  onBack: () => void;
}) {
  const isCreate = record === null;
  const [form, setForm] = useState<Form>(() => seedFrom(record));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  const dirty = isCreate || (record !== null && (
    form.title !== (record.title ?? '') || form.status !== record.status
  ));

  async function save() {
    setSaving(true);
    setError(null);
    try {
      if (isCreate) {
        const created = await api.createOrder({ title: form.title.trim() || null });
        onSaved(created);
      } else {
        const payload: OrderUpdateInput = {};
        if (form.title !== (record.title ?? '')) payload.title = form.title.trim() || null;
        if (form.status !== record.status) payload.status = form.status as OrderStatus;
        const updated = await api.updateOrder(record.object_id as number, payload);
        onSaved(updated);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const heading = form.title || (isCreate ? 'Neuer Auftrag' : 'Auftrag');

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#F1F5F9', color: '#64748b', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ClipboardList size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: form.title ? '#0F172A' : '#94a3b8', fontStyle: form.title ? 'normal' : 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {heading}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 4 }}>
              {isCreate ? (
                <StatusBadge cfg={orderStatusConfig('draft')} />
              ) : (
                <select
                  value={form.status}
                  onChange={(e) => set('status', e.target.value)}
                  style={{ fontSize: 12, fontWeight: 600, padding: '2px 6px', borderRadius: 6, border: '1px solid #E2E8F0', background: '#fff', color: '#475569', cursor: 'pointer' }}
                >
                  {ORDER_STATUS_ORDER.map((s) => <option key={s} value={s}>{orderStatusConfig(s).label}</option>)}
                </select>
              )}
            </div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>
              {isCreate ? 'wird vergeben' : fmtObjId(record.object_id)}
            </div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
        <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '16px 18px', display: 'flex', flexDirection: 'column', gap: 14 }}>
          <TextField label="Bezeichnung" value={form.title} onChange={(v) => set('title', v)} placeholder="Kurzbeschreibung des Auftrags" />
        </div>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 12, padding: '12px 14px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, fontSize: 13, color: '#1e40af' }}>
          <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Weitere Auftragsfelder folgen — der Inhalt dieses Datensatztyps wird noch definiert.</span>
        </div>
      </div>

      {/* Meta footer (edit only) */}
      {!isCreate && (
        <div style={{ padding: '8px 20px', borderTop: '1px solid #E2E8F0', background: '#fff', flexShrink: 0, fontSize: 11, color: '#94a3b8', display: 'flex', gap: 16 }}>
          <span>Erstellt: {localDate(record.created_at)}</span>
          <span>Zuletzt geändert: {localDate(record.updated_at)}</span>
        </div>
      )}

      {/* Save bar */}
      {(isCreate || dirty || error) && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 13, color: error ? '#dc2626' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (isCreate ? 'Neuen Auftrag erfassen' : 'Ungespeicherte Änderungen')}
          </span>
          <button
            onClick={isCreate ? onCancel : () => { setForm(seedFrom(record)); setError(null); }}
            style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}
          >
            {isCreate ? 'Abbrechen' : 'Verwerfen'}
          </button>
          <button
            onClick={save}
            disabled={saving}
            style={{ padding: '6px 14px', borderRadius: 7, border: 'none', background: saving ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer', flexShrink: 0 }}
          >
            {saving ? 'Speichern…' : isCreate ? 'Anlegen' : 'Speichern'}
          </button>
        </div>
      )}
    </div>
  );
}
