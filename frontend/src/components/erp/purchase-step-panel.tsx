'use client';

import { useState } from 'react';
import { Truck, Link2, Calculator, User as UserIcon } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, OrderPurchase, PurchaseOrderStatus, PurchaseOrderUpdateInput } from '@/types';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { TextField, StatusBadge } from '@/components/erp/fields';

type ViewerRole = 'staff' | 'supplier';

type Form = {
  unit_price: string; transport_cost: string; transport_included: boolean;
  other_costs: string; lead_time_days: string; payment_terms_days: string;
  tracking_number: string; rejection_reason: string;
};

function seed(p: OrderPurchase): Form {
  const s = (v: unknown) => (v == null ? '' : String(v));
  return {
    unit_price: s(p.unit_price), transport_cost: s(p.transport_cost),
    transport_included: !!p.transport_included, other_costs: s(p.other_costs),
    lead_time_days: s(p.lead_time_days), payment_terms_days: s(p.payment_terms_days),
    tracking_number: s(p.tracking_number), rejection_reason: s(p.rejection_reason),
  };
}

function moneyOrNull(v: string): string | null {
  const t = v.trim().replace(',', '.');
  return t === '' ? null : t;
}
function intOrNull(v: string): number | null {
  const t = v.trim();
  return t === '' ? null : Math.trunc(Number(t));
}
function fmtMoney(v: string | number | null | undefined): string {
  if (v == null || v === '') return '—';
  return Number(v).toLocaleString('de-CH', { minimumFractionDigits: 2 });
}

interface Action { label: string; target: PurchaseOrderStatus; variant: 'primary' | 'danger'; needsPrice?: boolean }

export function PurchaseStepPanel({ order, viewerRole, onOrderUpdated }: {
  order: Order;
  viewerRole: ViewerRole;
  onOrderUpdated: (o: Order) => void;
}) {
  const po = order.purchase;
  const [form, setForm] = useState<Form>(() => (po ? seed(po) : seed({} as OrderPurchase)));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!po) return null;

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  const s = po.status;
  const isStaff = viewerRole === 'staff';
  const supplierCanAct = viewerRole === 'supplier' && po.mode === 'supplier';
  const canEditOffer = (isStaff || supplierCanAct) && (s === 'requested' || s === 'quoted');
  const canEditTracking = (isStaff || supplierCanAct) && (s === 'approved' || s === 'confirmed');

  const qty = order.quantity || 0;
  const livePreview = (() => {
    const up = Number(form.unit_price.replace(',', '.'));
    if (!qty || !Number.isFinite(up) || form.unit_price.trim() === '') return null;
    const tr = form.transport_included ? 0 : Number(form.transport_cost.replace(',', '.')) || 0;
    const ot = Number(form.other_costs.replace(',', '.')) || 0;
    return (up * qty + tr + ot) / qty;
  })();

  const actions: Action[] = [];
  if (s === 'requested' && canEditOffer)
    actions.push({ label: isStaff ? 'Offerte erfassen' : 'Offerte senden', target: 'quoted', variant: 'primary', needsPrice: true });
  if (s === 'quoted' && isStaff) {
    actions.push({ label: 'Freigeben', target: 'approved', variant: 'primary' });
    actions.push({ label: 'Ablehnen', target: 'rejected', variant: 'danger' });
  }
  if (s === 'approved' && (isStaff || supplierCanAct))
    actions.push({ label: 'Bestätigen', target: 'confirmed', variant: 'primary' });
  if (s === 'confirmed' && isStaff)
    actions.push({ label: 'Wareneingang bestätigen', target: 'received', variant: 'primary' });

  function buildEditable(): PurchaseOrderUpdateInput {
    const p: PurchaseOrderUpdateInput = {};
    if (canEditOffer) {
      p.unit_price = moneyOrNull(form.unit_price);
      p.transport_included = form.transport_included;
      p.transport_cost = form.transport_included ? null : moneyOrNull(form.transport_cost);
      p.other_costs = moneyOrNull(form.other_costs);
      p.lead_time_days = intOrNull(form.lead_time_days);
      p.payment_terms_days = intOrNull(form.payment_terms_days);
    }
    if (canEditTracking) {
      p.tracking_number = form.tracking_number.trim() || null;
      p.lead_time_days = intOrNull(form.lead_time_days);
    }
    if (isStaff && s === 'quoted') p.rejection_reason = form.rejection_reason.trim() || null;
    return p;
  }

  async function run(target?: PurchaseOrderStatus, needsPrice?: boolean) {
    if (needsPrice && !form.unit_price.trim()) { setError('Bitte einen Stückpreis erfassen'); return; }
    setSaving(true); setError(null);
    try {
      const payload: PurchaseOrderUpdateInput = buildEditable();
      if (target) payload.status = target;
      const updated = await api.updateOrderPurchase(order.object_id as number, payload);
      onOrderUpdated(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const cfg = purchaseStatusConfig(s);

  return (
    <Card>
      {/* Schritt-Kopf */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <div style={{ width: 30, height: 30, borderRadius: 8, flexShrink: 0, background: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 13, fontWeight: 700 }}>1</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>Bestellung (Beschaffung)</div>
        </div>
        <StatusBadge cfg={cfg} size={11} />
      </div>

      {/* Bezugsquelle */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#64748b' }}>
        {po.mode === 'supplier'
          ? <><UserIcon size={12} /> Lieferant: {po.supplier_name ?? `#${po.supplier_id}`}</>
          : <><Link2 size={12} /> {po.webshop_url
              ? <a href={po.webshop_url} target="_blank" rel="noreferrer" style={{ color: '#2563eb', wordBreak: 'break-all' }}>Webshop öffnen</a>
              : 'Webshop'}</>}
      </div>

      {/* Offerte */}
      {canEditOffer ? (
        <>
          <TextField label="Stückpreis netto (CHF)" value={form.unit_price} onChange={(v) => set('unit_price', v)} required placeholder="z. B. 12.50" />
          <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: '#374151', cursor: 'pointer' }}>
            <input type="checkbox" checked={form.transport_included} onChange={(e) => set('transport_included', e.target.checked)} />
            Transport im Stückpreis inbegriffen (frei Haus)
          </label>
          {!form.transport_included && (
            <TextField label="Transportkosten (CHF)" value={form.transport_cost} onChange={(v) => set('transport_cost', v)} placeholder="z. B. 25" />
          )}
          <TextField label="Sonstige Kosten (CHF)" value={form.other_costs} onChange={(v) => set('other_costs', v)} placeholder="optional" />
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
            <TextField label="Lieferzeit (Tage)" value={form.lead_time_days} onChange={(v) => set('lead_time_days', v)} placeholder="z. B. 14" />
            <TextField label="Zahlungsziel (Tage)" value={form.payment_terms_days} onChange={(v) => set('payment_terms_days', v)} placeholder="z. B. 30" />
          </div>
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Row k="Stückpreis netto" v={`CHF ${fmtMoney(po.unit_price)}`} />
          <Row k="Transport" v={po.transport_included ? 'inbegriffen' : `CHF ${fmtMoney(po.transport_cost)}`} />
          {po.other_costs != null && <Row k="Sonstige Kosten" v={`CHF ${fmtMoney(po.other_costs)}`} />}
          <Row k="Lieferzeit" v={po.lead_time_days != null ? `${po.lead_time_days} Tage` : '—'} />
          <Row k="Zahlungsziel" v={po.payment_terms_days != null ? `${po.payment_terms_days} Tage` : '—'} />
        </div>
      )}

      {/* Einstandspreis – nur intern (Mitarbeiter) */}
      {isStaff && (livePreview != null || po.landed_unit_cost != null) && (
        <div style={{ background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 8, padding: '10px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <Calculator size={13} style={{ color: '#0f766e' }} />
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#0f766e' }}>Einstandspreis netto / Stück</span>
          </div>
          <div style={{ fontSize: 18, fontWeight: 800, color: '#0f766e' }}>
            CHF {fmtMoney(s === 'requested' || s === 'quoted' ? livePreview : (po.landed_unit_cost ?? livePreview))}
          </div>
          <div style={{ fontSize: 11, color: '#94a3b8' }}>(Stückpreis × Menge + Transport + Sonstiges) ÷ Menge · ohne MWST</div>
        </div>
      )}

      {/* Tracking */}
      {canEditTracking ? (
        <TextField label="Tracking-Nummer" value={form.tracking_number} onChange={(v) => set('tracking_number', v)} placeholder="optional, kann nachgetragen werden" />
      ) : (
        po.tracking_number && <Row k="Tracking-Nummer" v={po.tracking_number} />
      )}

      {/* Ablehnungsgrund */}
      {isStaff && s === 'quoted' && (
        <TextField label="Ablehnungsgrund (optional)" value={form.rejection_reason} onChange={(v) => set('rejection_reason', v)} placeholder="nur nötig bei Ablehnung" />
      )}
      {s === 'rejected' && po.rejection_reason && <Row k="Ablehnungsgrund" v={po.rejection_reason} />}

      {/* Aktionen */}
      {(actions.length > 0 || canEditOffer || canEditTracking || error) && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', borderTop: '1px solid #f1f5f9', paddingTop: 12 }}>
          <span style={{ flex: 1, fontSize: 12, color: error ? '#dc2626' : '#94a3b8', minWidth: 120 }}>{error ?? cfg.label}</span>
          {(canEditOffer || canEditTracking) && (
            <button onClick={() => run()} disabled={saving}
              style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer' }}>
              Speichern
            </button>
          )}
          {actions.map((a) => (
            <button key={a.target} onClick={() => run(a.target, a.needsPrice)} disabled={saving}
              style={{ padding: '6px 14px', borderRadius: 7, border: 'none', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer',
                background: a.variant === 'danger' ? '#dc2626' : '#2563eb', color: '#fff' }}>
              {saving ? '…' : a.label}
            </button>
          ))}
        </div>
      )}
    </Card>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 10, padding: '14px 16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {children}
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span style={{ color: '#94a3b8', flexShrink: 0 }}>{k}</span>
      <span style={{ color: '#0F172A', fontWeight: 600, textAlign: 'right' }}>{v}</span>
    </div>
  );
}
