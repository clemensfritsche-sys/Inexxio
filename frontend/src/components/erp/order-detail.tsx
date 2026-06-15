'use client';

import { useState } from 'react';
import { ClipboardList, ArrowLeft, Info, Rocket } from 'lucide-react';
import { api } from '@/lib/api';
import type { Article, Order, OrderStatus, OrderUpdateInput } from '@/types';
import { ORDER_STATUS_ORDER, orderStatusConfig } from '@/lib/order';
import { fmtObjId } from '@/components/erp/user-detail';
import { TextField, SelectField, StatusBadge, Label, ErrorText } from '@/components/erp/fields';

type Form = {
  title: string; status: string;
  article_id: string; quantity: string; desired_delivery_date: string;
};

function seedFrom(record: Order | null): Form {
  if (!record) return { title: '', status: 'draft', article_id: '', quantity: '', desired_delivery_date: '' };
  return {
    title: record.title ?? '',
    status: record.status,
    article_id: record.article_id != null ? String(record.article_id) : '',
    quantity: record.quantity != null ? String(record.quantity) : '',
    desired_delivery_date: record.desired_delivery_date ?? '',
  };
}

function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

export function OrderDetail({ record, articles, onSaved, onCancel, onBack }: {
  record: Order | null;            // null ⇒ Anlage-Modus
  articles: Article[];
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

  const seed = seedFrom(record);
  const dirty = isCreate || (Object.keys(form) as (keyof Form)[]).some((k) => form[k] !== seed[k]);

  const qtyNum = form.quantity.trim() ? Number(form.quantity) : null;
  const hasArticleQty = !!form.article_id && qtyNum != null && qtyNum > 0;
  const releaseBlocked = form.status === 'released' && !hasArticleQty;

  async function save() {
    if (releaseBlocked) { setError('Zur Freigabe sind Artikel und Menge (> 0) erforderlich'); return; }
    setSaving(true);
    setError(null);
    try {
      const article_id = form.article_id ? Number(form.article_id) : null;
      const quantity = qtyNum;
      const desired_delivery_date = form.desired_delivery_date || null;
      if (isCreate) {
        const created = await api.createOrder({
          title: form.title.trim() || null, article_id, quantity, desired_delivery_date,
        });
        onSaved(created);
      } else {
        const payload: OrderUpdateInput = {};
        if (form.title !== (record.title ?? '')) payload.title = form.title.trim() || null;
        if (article_id !== (record.article_id ?? null)) payload.article_id = article_id;
        if (quantity !== (record.quantity ?? null)) payload.quantity = quantity;
        if (desired_delivery_date !== (record.desired_delivery_date ?? null)) payload.desired_delivery_date = desired_delivery_date;
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
  const articleOptions = [
    { value: '', label: '— Artikel wählen —' },
    ...articles.map((a) => ({ value: String(a.id), label: `${a.name} · ${fmtObjId(a.object_id)}` })),
  ];

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
          <TextField label="Bezeichnung" value={form.title} onChange={(v) => set('title', v)} placeholder="Kurzbeschreibung (optional)" />
          <SelectField label="Artikel" value={form.article_id} onChange={(v) => set('article_id', v)} options={articleOptions} required />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <TextField label="Menge" value={form.quantity} onChange={(v) => set('quantity', v)} required placeholder="z. B. 5" />
            <div>
              <Label>Wunsch-Liefertermin</Label>
              <input type="date" value={form.desired_delivery_date} onChange={(e) => set('desired_delivery_date', e.target.value)}
                className="w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent" style={{ borderColor: '#e2e8f0' }} />
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 12, padding: '12px 14px', background: '#eff6ff', border: '1px solid #bfdbfe', borderRadius: 10, fontSize: 13, color: '#1e40af' }}>
          <Rocket size={15} style={{ flexShrink: 0, marginTop: 1 }} />
          <span>Sobald der Auftrag auf <b>Freigegeben</b> gesetzt wird, startet der hinterlegte Prozess des
            Artikels. Hat der Artikel einen Bestell-Schritt, entsteht automatisch eine Bestellung im Feed.</span>
        </div>

        {!isCreate && record.status === 'released' && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, marginTop: 10, padding: '12px 14px', background: '#f0fdf4', border: '1px solid #bbf7d0', borderRadius: 10, fontSize: 13, color: '#166534' }}>
            <Info size={15} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>Auftrag freigegeben – der Prozess wurde angestossen.</span>
          </div>
        )}
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
          <span style={{ flex: 1, fontSize: 13, color: error || releaseBlocked ? '#dc2626' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? (releaseBlocked ? 'Freigabe braucht Artikel + Menge' : isCreate ? 'Neuen Auftrag erfassen' : 'Ungespeicherte Änderungen')}
          </span>
          <button
            onClick={isCreate ? onCancel : () => { setForm(seedFrom(record)); setError(null); }}
            style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}
          >
            {isCreate ? 'Abbrechen' : 'Verwerfen'}
          </button>
          <button
            onClick={save}
            disabled={saving || releaseBlocked}
            style={{ padding: '6px 14px', borderRadius: 7, border: 'none', background: saving || releaseBlocked ? '#93c5fd' : '#2563eb', color: '#fff', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer', flexShrink: 0 }}
          >
            {saving ? 'Speichern…' : isCreate ? 'Anlegen' : 'Speichern'}
          </button>
        </div>
      )}
    </div>
  );
}
