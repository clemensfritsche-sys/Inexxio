'use client';

import { useState } from 'react';
import { Link2, Calculator, User as UserIcon, FileText } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, OrderPurchase, PurchaseOrderStatus, PurchaseOrderUpdateInput } from '@/types';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { unitLabel, serializationLabel } from '@/lib/article';
import { fieldLabel } from '@/lib/article-fields';
import { TextField, StatusBadge } from '@/components/erp/fields';

type ViewerRole = 'staff' | 'supplier';

type Form = { order_total: string; lead_time_days: string; payment_terms_days: string; tracking_number: string };

function seed(p: OrderPurchase): Form {
  const s = (v: unknown) => (v == null ? '' : String(v));
  return {
    order_total: s(p.order_total), lead_time_days: s(p.lead_time_days),
    payment_terms_days: s(p.payment_terms_days), tracking_number: s(p.tracking_number),
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

interface Action { label: string; target: PurchaseOrderStatus; variant: 'primary' | 'danger'; needsTotal?: boolean }

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
  // Verantwortung für die Offerte: im Webshop-Modus der Mitarbeiter, sonst der Lieferant.
  const isOfferEditor = (po.mode === 'webshop' && isStaff) || (po.mode === 'supplier' && viewerRole === 'supplier');
  const isBuyer = isStaff;  // Freigabe/Ablehnung/Wareneingang
  const canEditOffer = isOfferEditor && (s === 'requested' || s === 'quoted');
  const canEditTracking = isOfferEditor && (s === 'approved' || s === 'confirmed');

  const qty = order.quantity || 0;
  const perUnit = (() => {
    if (canEditOffer) {
      const tot = Number(form.order_total.replace(',', '.'));
      if (!qty || form.order_total.trim() === '' || !Number.isFinite(tot)) return null;
      return tot / qty;
    }
    if (po.unit_price != null) return Number(po.unit_price);
    if (po.order_total != null && qty) return Number(po.order_total) / qty;
    return null;
  })();

  const actions: Action[] = [];
  if (s === 'requested' && isOfferEditor)
    actions.push({ label: po.mode === 'webshop' ? 'Offerte erfassen' : 'Offerte senden', target: 'quoted', variant: 'primary', needsTotal: true });
  if (s === 'quoted' && isBuyer) {
    actions.push({ label: 'Freigeben', target: 'approved', variant: 'primary' });
    actions.push({ label: 'Ablehnen', target: 'rejected', variant: 'danger' });
  }
  if (s === 'approved' && isOfferEditor)
    actions.push({ label: 'Bestätigen', target: 'confirmed', variant: 'primary' });
  if (s === 'confirmed' && isBuyer)
    actions.push({ label: 'Wareneingang bestätigen', target: 'received', variant: 'primary' });

  function buildEditable(): PurchaseOrderUpdateInput {
    const p: PurchaseOrderUpdateInput = {};
    if (canEditOffer) {
      p.order_total = moneyOrNull(form.order_total);
      p.lead_time_days = intOrNull(form.lead_time_days);
      p.payment_terms_days = intOrNull(form.payment_terms_days);
    }
    if (canEditTracking) {
      p.tracking_number = form.tracking_number.trim() || null;
      p.lead_time_days = intOrNull(form.lead_time_days);
    }
    return p;
  }

  async function run(target?: PurchaseOrderStatus, needsTotal?: boolean) {
    if (needsTotal && !form.order_total.trim()) { setError('Bitte eine Bestellsumme erfassen'); return; }
    setSaving(true); setError(null);
    try {
      const payload: PurchaseOrderUpdateInput = buildEditable();
      if (target) payload.status = target;
      onOrderUpdated(await api.updateOrderPurchase(order.object_id as number, payload));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  // Für den Lieferanten freigegebene Stammdaten
  const sharedRows = (po.shared_fields ?? []).map((key) => {
    let value = '—';
    if (key === 'name') value = order.article_name ?? '—';
    else if (key === 'unit') value = order.article_unit ? unitLabel(order.article_unit) : '—';
    else if (key === 'serialization') value = order.article_serialization ? serializationLabel(order.article_serialization) : '—';
    else if (key === 'size') value = order.article_size ?? '—';
    else if (key === 'weight_kg') value = order.article_weight_kg != null ? `${order.article_weight_kg} kg` : '—';
    return { key, label: fieldLabel(key), value };
  });

  const cfg = purchaseStatusConfig(s);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
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
            <TextField label="Bestellsumme netto, exkl. MWST (CHF)" value={form.order_total} onChange={(v) => set('order_total', v)} required placeholder="z. B. 1250" hint="Gesamtsumme für die ganze Bestellmenge" />
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <TextField label="Lieferzeit (Tage)" value={form.lead_time_days} onChange={(v) => set('lead_time_days', v)} placeholder="z. B. 14" />
              <TextField label="Zahlungsziel (Tage)" value={form.payment_terms_days} onChange={(v) => set('payment_terms_days', v)} placeholder="z. B. 30" />
            </div>
          </>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Row k="Bestellsumme netto" v={`CHF ${fmtMoney(po.order_total)}`} />
            <Row k="Lieferzeit" v={po.lead_time_days != null ? `${po.lead_time_days} Tage` : '—'} />
            <Row k="Zahlungsziel" v={po.payment_terms_days != null ? `${po.payment_terms_days} Tage` : '—'} />
          </div>
        )}

        {/* Preis pro Stück (berechnet, read-only) */}
        {perUnit != null && (
          <div style={{ background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 8, padding: '10px 12px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <Calculator size={13} style={{ color: '#0f766e' }} />
              <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#0f766e' }}>Preis pro Stück (netto)</span>
            </div>
            <div style={{ fontSize: 18, fontWeight: 800, color: '#0f766e' }}>CHF {fmtMoney(perUnit)}</div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>
              Bestellsumme ÷ Menge ({qty || '—'}){isStaff ? ' · wird als Einstandspreis übernommen' : ''}
            </div>
          </div>
        )}

        {/* Tracking */}
        {canEditTracking ? (
          <TextField label="Tracking-Nummer" value={form.tracking_number} onChange={(v) => set('tracking_number', v)} placeholder="optional, kann nachgetragen werden" />
        ) : (
          po.tracking_number && <Row k="Tracking-Nummer" v={po.tracking_number} />
        )}

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
              <button key={a.target} onClick={() => run(a.target, a.needsTotal)} disabled={saving}
                style={{ padding: '6px 14px', borderRadius: 7, border: 'none', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer',
                  background: a.variant === 'danger' ? '#dc2626' : '#2563eb', color: '#fff' }}>
                {saving ? '…' : a.label}
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* Für den Lieferanten freigegebene Stammdaten */}
      {sharedRows.length > 0 && (
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <FileText size={13} style={{ color: '#94a3b8' }} />
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>
              Artikel-Stammdaten{isStaff ? ' (für Lieferant sichtbar)' : ''}
            </span>
          </div>
          {sharedRows.map((r) => <Row key={r.key} k={r.label} v={r.value} />)}
        </Card>
      )}
    </div>
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
