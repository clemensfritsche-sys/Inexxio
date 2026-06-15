'use client';

import { useState } from 'react';
import { ShoppingCart, ArrowLeft, Package, Truck, MapPin, Link2, Calculator } from 'lucide-react';
import { api } from '@/lib/api';
import type { CompanySettings, PurchaseOrder, PurchaseOrderStatus, PurchaseOrderUpdateInput } from '@/types';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { fmtObjId } from '@/components/erp/user-detail';
import { TextField, StatusBadge } from '@/components/erp/fields';

type ViewerRole = 'staff' | 'supplier';

type Form = {
  unit_price: string; transport_cost: string; transport_included: boolean;
  other_costs: string; lead_time_days: string; payment_terms_days: string;
  tracking_number: string; rejection_reason: string;
};

function seed(r: PurchaseOrder): Form {
  const s = (v: unknown) => (v == null ? '' : String(v));
  return {
    unit_price: s(r.unit_price), transport_cost: s(r.transport_cost),
    transport_included: !!r.transport_included, other_costs: s(r.other_costs),
    lead_time_days: s(r.lead_time_days), payment_terms_days: s(r.payment_terms_days),
    tracking_number: s(r.tracking_number), rejection_reason: s(r.rejection_reason),
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
function localDate(iso: string | null | undefined): string {
  return iso ? new Date(iso).toLocaleDateString('de-CH') : '—';
}

interface Action { label: string; target: PurchaseOrderStatus; variant: 'primary' | 'danger'; needsPrice?: boolean }

export function PurchaseOrderDetail({ record, viewerRole, company, onSaved, onBack }: {
  record: PurchaseOrder;
  viewerRole: ViewerRole;
  company: Partial<CompanySettings> | null;
  onSaved: (po: PurchaseOrder) => void;
  onBack: () => void;
}) {
  const [form, setForm] = useState<Form>(() => seed(record));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  const s = record.status;
  const isStaff = viewerRole === 'staff';
  const supplierCanAct = viewerRole === 'supplier' && record.mode === 'supplier';
  const canEditOffer = (isStaff || supplierCanAct) && (s === 'requested' || s === 'quoted');
  const canEditTracking = (isStaff || supplierCanAct) && (s === 'approved' || s === 'confirmed');

  // Live-Vorschau Einstandspreis (nur Mitarbeiter)
  const qty = record.quantity || 0;
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
      const updated = await api.updatePurchaseOrder(record.object_id as number, payload);
      onSaved(updated);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const companyAddr = company
    ? [company.street, company.street_number].filter(Boolean).join(' ')
    : '';
  const cfg = purchaseStatusConfig(s);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div style={{ padding: '12px 20px', borderBottom: '1px solid #E2E8F0', background: '#fff', flexShrink: 0 }}>
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-blue-600 mb-2 md:hidden">
          <ArrowLeft size={14} /> Zurück
        </button>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ width: 44, height: 44, borderRadius: 10, flexShrink: 0, background: '#eff6ff', color: '#2563eb', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <ShoppingCart size={20} />
          </div>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div style={{ fontSize: 15, fontWeight: 700, color: '#0F172A' }}>Bestellung</div>
            <div style={{ marginTop: 4 }}><StatusBadge cfg={cfg} size={11} /></div>
          </div>
          <div style={{ flexShrink: 0, textAlign: 'right' }}>
            <div style={{ fontSize: 10, color: '#CBD5E1', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em' }}>Obj.-Nr.</div>
            <div style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700, color: '#475569' }}>{fmtObjId(record.object_id)}</div>
          </div>
        </div>
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px 20px', background: '#F8FAFC' }}>
        {/* Artikel */}
        <SectionTitle icon={Package}>Artikel</SectionTitle>
        <Card>
          <Row k="Bezeichnung" v={record.article_name ?? '—'} />
          <Row k="Artikel-Nr." v={fmtObjId(record.article_object_id)} mono />
          <Row k="Spezifikation" v={`${record.article_size ?? '—'} mm · ${record.article_weight_kg ?? '—'} kg · ${record.article_unit ?? ''}`} />
          <Row k="Menge" v={`${record.quantity} ${record.article_unit ?? ''}`} />
        </Card>

        {/* Lieferadresse / Besteller (v.a. für Lieferant) */}
        <SectionTitle icon={MapPin}>Lieferung an</SectionTitle>
        <Card>
          <Row k="Besteller" v={company?.company_name ?? 'Inexxio AG'} />
          {companyAddr && <Row k="Adresse" v={`${companyAddr}, ${company?.zip ?? ''} ${company?.city ?? ''}`} />}
          <Row k="Wunsch-Liefertermin" v={localDate(record.desired_delivery_date)} />
          {record.mode === 'webshop' && record.webshop_url && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13 }}>
              <Link2 size={13} style={{ color: '#2563eb' }} />
              <a href={record.webshop_url} target="_blank" rel="noreferrer" style={{ color: '#2563eb', wordBreak: 'break-all' }}>Zum Webshop</a>
            </div>
          )}
        </Card>

        {/* Offerte */}
        <SectionTitle icon={Truck}>Offerte</SectionTitle>
        <Card>
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
            <>
              <Row k="Stückpreis netto" v={`CHF ${fmtMoney(record.unit_price)}`} />
              <Row k="Transport" v={record.transport_included ? 'inbegriffen' : `CHF ${fmtMoney(record.transport_cost)}`} />
              {record.other_costs != null && <Row k="Sonstige Kosten" v={`CHF ${fmtMoney(record.other_costs)}`} />}
              <Row k="Lieferzeit" v={record.lead_time_days != null ? `${record.lead_time_days} Tage` : '—'} />
              <Row k="Zahlungsziel" v={record.payment_terms_days != null ? `${record.payment_terms_days} Tage` : '—'} />
            </>
          )}
        </Card>

        {/* Einstandspreis – nur intern (Mitarbeiter) */}
        {isStaff && (livePreview != null || record.landed_unit_cost != null) && (
          <Card accent>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <Calculator size={15} style={{ color: '#0f766e' }} />
              <span style={{ fontSize: 12, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#0f766e' }}>Einstandspreis netto / Stück</span>
            </div>
            <div style={{ fontSize: 20, fontWeight: 800, color: '#0f766e' }}>
              CHF {fmtMoney(record.status === 'requested' || record.status === 'quoted' ? livePreview : (record.landed_unit_cost ?? livePreview))}
            </div>
            <div style={{ fontSize: 11, color: '#94a3b8' }}>(Stückpreis × Menge + Transport + Sonstiges) ÷ Menge · ohne MWST</div>
          </Card>
        )}

        {/* Tracking */}
        <SectionTitle icon={Truck}>Versand</SectionTitle>
        <Card>
          {canEditTracking ? (
            <TextField label="Tracking-Nummer" value={form.tracking_number} onChange={(v) => set('tracking_number', v)} placeholder="optional, kann nachgetragen werden" />
          ) : (
            <Row k="Tracking-Nummer" v={record.tracking_number ?? '—'} />
          )}
        </Card>

        {/* Ablehnungsgrund (Mitarbeiter, beim Status quoted) */}
        {isStaff && s === 'quoted' && (
          <Card>
            <TextField label="Ablehnungsgrund (optional)" value={form.rejection_reason} onChange={(v) => set('rejection_reason', v)} placeholder="nur nötig bei Ablehnung" />
          </Card>
        )}
        {record.status === 'rejected' && record.rejection_reason && (
          <Card><Row k="Ablehnungsgrund" v={record.rejection_reason} /></Card>
        )}

        <div style={{ fontSize: 11, color: '#94a3b8', padding: '4px 2px' }}>
          Auftrag {fmtObjId(record.order_object_id)} · Erstellt: {localDate(record.created_at)}
        </div>
      </div>

      {/* Action bar */}
      {(actions.length > 0 || canEditOffer || canEditTracking || error) && (
        <div style={{ padding: '10px 20px', background: '#fff', borderTop: '1px solid #E2E8F0', display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          <span style={{ flex: 1, fontSize: 13, color: error ? '#dc2626' : '#64748b', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {error ?? cfg.label}
          </span>
          {(canEditOffer || canEditTracking) && (
            <button onClick={() => run()} disabled={saving}
              style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer', flexShrink: 0 }}>
              Speichern
            </button>
          )}
          {actions.map((a) => (
            <button key={a.target} onClick={() => run(a.target, a.needsPrice)} disabled={saving}
              style={{ padding: '6px 14px', borderRadius: 7, border: 'none', fontSize: 13, fontWeight: 600, cursor: saving ? 'wait' : 'pointer', flexShrink: 0,
                background: a.variant === 'danger' ? '#dc2626' : '#2563eb', color: '#fff' }}>
              {saving ? '…' : a.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function Card({ children, accent }: { children: React.ReactNode; accent?: boolean }) {
  return (
    <div style={{ background: accent ? '#f0fdfa' : '#fff', border: `1px solid ${accent ? '#99f6e4' : '#E2E8F0'}`, borderRadius: 10, padding: '14px 16px', marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 10 }}>
      {children}
    </div>
  );
}

function SectionTitle({ icon: Icon, children }: { icon: React.ElementType; children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 2px 8px' }}>
      <Icon size={13} style={{ color: '#94a3b8' }} />
      <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#64748b' }}>{children}</span>
    </div>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span style={{ color: '#94a3b8', flexShrink: 0 }}>{k}</span>
      <span style={{ color: '#0F172A', fontWeight: 600, textAlign: 'right', fontFamily: mono ? 'monospace' : undefined }}>{v}</span>
    </div>
  );
}
