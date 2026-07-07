'use client';

import { useState } from 'react';
import { Link2, Calculator, User as UserIcon, FileText, MapPin, ShoppingCart } from 'lucide-react';
import { api } from '@/lib/api';
import type { CompanySettings, Order, OrderPurchase, PurchaseOrderStatus, PurchaseOrderUpdateInput } from '@/types';
import { purchaseStatusConfig } from '@/lib/purchase-order';
import { unitLabel, serializationLabel } from '@/lib/article';
import { fieldLabel } from '@/lib/article-fields';
import { TextField, StatusBadge, PanelHeader } from '@/components/erp/fields';
import { PurchaseProgress, type PNode, type Delivery } from '@/components/erp/purchase-progress';
import { ObjId } from '@/components/erp/obj-id';
import { formatAmount as fmtMoney } from '@/lib/utils';

type ViewerRole = 'staff' | 'supplier';
type Hist = NonNullable<OrderPurchase['history']>[number];

type Form = { order_total: string; lead_time_days: string; payment_terms_days: string; tracking_number: string };

function seed(p: OrderPurchase): Form {
  const s = (v: unknown) => (v == null ? '' : String(v));
  return {
    order_total: s(p.order_total), lead_time_days: s(p.lead_time_days),
    payment_terms_days: s(p.payment_terms_days), tracking_number: s(p.tracking_number),
  };
}

const moneyOrNull = (v: string): string | null => (v.trim().replace(',', '.') === '' ? null : v.trim().replace(',', '.'));
const intOrNull = (v: string): number | null => (v.trim() === '' ? null : Math.trunc(Number(v)));
const fmtDateTime = (iso: string): string => new Date(iso).toLocaleString('de-CH', { dateStyle: 'short', timeStyle: 'short' });

// Letzten Audit-Eintrag je Status (für Hover-Tooltip)
function historyByStatus(history: Hist[] | undefined): Record<string, Hist> {
  const map: Record<string, Hist> = {};
  (history ?? []).forEach((h) => { map[h.status] = h; });
  return map;
}

interface Action { label: string; target: PurchaseOrderStatus; variant: 'primary' | 'danger'; needsTotal?: boolean }

// Bei einem Mehrpositionen-Auftrag kann der Beschaffungs-Schritt MEHRERE Bestellungen
// tragen (eine je Artikel/Position). Anders als beim Verkauf ist jede Bestellung eine
// EIGENE, unabhängig fortschreitende Beschaffung (eigene Offerte/Lieferzeit, ggf.
// separat geliefert) – deshalb EIN vollständiges Panel je Position statt einer
// gemeinsamen Aktion; bei mehreren Positionen zeigt jedes zusätzlich seinen Artikel.
export function PurchaseStepPanel({ order, purchases, stepId, viewerRole, company, onOrderUpdated }: {
  order: Order;
  purchases: OrderPurchase[];
  stepId?: number;
  viewerRole: ViewerRole;
  company?: Partial<CompanySettings> | null;
  onOrderUpdated: (o: Order) => void;
}) {
  if (purchases.length === 0) return null;
  const showArticle = purchases.length > 1;
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {purchases.map((po) => (
        <PurchaseLine key={po.id} order={order} po={po} stepId={stepId} viewerRole={viewerRole}
          company={company} onOrderUpdated={onOrderUpdated} showArticle={showArticle} />
      ))}
    </div>
  );
}

function PurchaseLine({ order, po, stepId, viewerRole, company, onOrderUpdated, showArticle }: {
  order: Order;
  po: OrderPurchase;
  stepId?: number;
  viewerRole: ViewerRole;
  company?: Partial<CompanySettings> | null;
  onOrderUpdated: (o: Order) => void;
  showArticle: boolean;
}) {
  const [form, setForm] = useState<Form>(() => seed(po));
  const [saving, setSaving] = useState(false);
  const [trackingSaved, setTrackingSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function set<K extends keyof Form>(key: K, value: Form[K]) {
    setForm((p) => ({ ...p, [key]: value }));
  }

  const s = po.status;
  const isStaff = viewerRole === 'staff';
  const isWebshop = po.mode === 'webshop';
  // Offerte/Bestellsumme erfassen darf der **Besteller (Mitarbeiter) immer** (Selbst-
  // Beschaffung – nie blockiert, auch ohne zugewiesenen Lieferanten) sowie – im Lieferanten-
  // Modus – der Lieferant über sein Portal.
  const isOfferEditor = isStaff || (!isWebshop && viewerRole === 'supplier');
  const isBuyer = isStaff;
  const canEditOffer = isOfferEditor && s === 'requested';     // nach Absenden gesperrt
  const canEditTracking = isOfferEditor && s === 'ordered';

  // Menge DIESER Position (bei einem Mehrpositionen-Auftrag pro Artikel, sonst der Anker).
  const qty = po.quantity ?? order.quantity ?? 0;
  const perUnit = (() => {
    if (canEditOffer) {
      const tot = Number(form.order_total.replace(',', '.'));
      if (!qty || form.order_total.trim() === '' || !Number.isFinite(tot)) return null;
      return tot / qty;
    }
    if (po.order_total != null && qty) return Number(po.order_total) / qty;
    return null;
  })();

  const actions: Action[] = [];
  if (s === 'requested' && isOfferEditor) {
    // Mitarbeiter (Besteller) & Webshop → direkt bestellen (Summe selbst erfassen);
    // nur der externe Lieferant offeriert (→ quoted), woraufhin der Besteller bestellt.
    actions.push(isStaff || isWebshop
      ? { label: 'Bestellen', target: 'ordered', variant: 'primary', needsTotal: true }
      : { label: 'Offerte senden', target: 'quoted', variant: 'primary', needsTotal: true });
  }
  if (s === 'quoted' && isBuyer) {
    actions.push({ label: 'Bestellen', target: 'ordered', variant: 'primary' });
    actions.push({ label: 'Ablehnen', target: 'rejected', variant: 'danger' });
  }
  if (s === 'ordered' && isBuyer) {
    actions.push({ label: 'Lieferung bestätigen', target: 'received', variant: 'primary' });
  }

  // Mehrpositionen: jede Aktion muss die betroffene Position (Artikel) benennen –
  // beim Einzel-Artikel-Auftrag genügt die eindeutige Bestellung des Schritts.
  const disambiguator: Partial<PurchaseOrderUpdateInput> = showArticle
    ? { article_id: po.article_id ?? undefined }
    : {};

  function buildEditable(): PurchaseOrderUpdateInput {
    const p: PurchaseOrderUpdateInput = { step_id: stepId, ...disambiguator };
    if (canEditOffer) {
      p.order_total = moneyOrNull(form.order_total);
      p.lead_time_days = intOrNull(form.lead_time_days);
      // Webshop wird sofort bezahlt → kein Zahlungsziel
      p.payment_terms_days = isWebshop ? null : intOrNull(form.payment_terms_days);
    }
    if (canEditTracking) p.tracking_number = form.tracking_number.trim() || null;
    return p;
  }

  async function run(target: PurchaseOrderStatus, needsTotal?: boolean) {
    if (needsTotal && !form.order_total.trim()) { setError('Bitte eine Bestellsumme erfassen'); return; }
    setSaving(true); setError(null);
    try {
      const payload: PurchaseOrderUpdateInput = { ...buildEditable(), status: target };
      onOrderUpdated(await api.updateOrderPurchase(order.object_id as number, payload));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  // Tracking wird ohne separaten Button gespeichert (Autosave beim Verlassen des Felds)
  async function saveTracking() {
    if (!canEditTracking) return;
    const next = form.tracking_number.trim() || null;
    if (next === (po.tracking_number ?? null)) return;
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.updateOrderPurchase(order.object_id as number,
        { tracking_number: next, step_id: stepId, ...disambiguator }));
      setTrackingSaved(true);
      setTimeout(() => setTrackingSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Fehler beim Speichern');
    } finally {
      setSaving(false);
    }
  }

  const hist = historyByStatus(po.history);
  const nodes = buildNodes(s, isWebshop, hist);
  const delivery: Delivery | undefined = (() => {
    if (s !== 'ordered' || !po.ordered_at || !po.lead_time_days || po.lead_time_days <= 0) return undefined;
    const start = new Date(po.ordered_at).getTime();
    const total = po.lead_time_days * 86400000;
    const now = Date.now();
    const pct = Math.max(0, Math.min(100, ((now - start) / total) * 100));
    const remaining = Math.ceil((start + total - now) / 86400000);
    const overdue = remaining < 0;
    const label = remaining > 0 ? `noch ${remaining} Tag${remaining === 1 ? '' : 'e'}`
      : remaining === 0 ? 'heute fällig'
      : `überfällig ${-remaining} Tag${-remaining === 1 ? '' : 'e'}`;
    const oi = Math.max(0, nodes.findIndex((n) => n.key === 'ordered'));
    return { pct, label, overdue, oi };
  })();

  // FIX: Die Spezifikation kam vom AUFTRAG – bei einem Mehrpositionen-Auftrag ist
  // order.article_* NULL und der Lieferant sah nur «—». Massgeblich ist die POSITION
  // (jede Bestellung trägt ihren eigenen Artikel); Auftrag bleibt Fallback (Einzel-Artikel).
  const name = po.article_name ?? order.article_name;
  const unit = po.article_unit ?? order.article_unit;
  const serialization = po.article_serialization ?? order.article_serialization;
  const size = po.article_size ?? order.article_size;
  const weightKg = po.article_weight_kg ?? order.article_weight_kg;
  const supplierArtNr = po.article_supplier_article_number ?? order.article_supplier_article_number;
  const sharedRows = (po.shared_fields ?? []).map((key) => {
    let value = '—';
    if (key === 'name') value = name ?? '—';
    else if (key === 'unit') value = unit ? unitLabel(unit) : '—';
    else if (key === 'serialization') value = serialization ? serializationLabel(serialization) : '—';
    else if (key === 'size') value = size ?? '—';
    else if (key === 'weight_kg') value = weightKg != null ? `${weightKg} kg` : '—';
    else if (key === 'supplier_article_number') value = supplierArtNr ?? '—';
    return { key, label: fieldLabel(key), value };
  });

  const cfg = purchaseStatusConfig(s);

  return (
    <>
      <Card>
        {/* Kopf */}
        <PanelHeader icon={ShoppingCart} title="Bestellung (Beschaffung)"
          info="Beschaffung beim Lieferanten unter dieser Auftragsnummer: Anfrage → Offerte → Bestellung → Wareneingang."
          right={<StatusBadge cfg={cfg} size={11} />} />

        {/* Bei mehreren Positionen: welcher Artikel diese Bestellung betrifft */}
        {showArticle && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: '#0F172A' }}>
            {po.article_object_id != null && <ObjId value={po.article_object_id} />}
            {po.article_name ?? 'Artikel'}
          </div>
        )}

        {/* Fortschritt inkl. Lieferungs-Animation + Audit-Hover */}
        <div style={{ padding: '8px 2px 2px' }}>
          <PurchaseProgress nodes={nodes} delivery={delivery} />
        </div>

        {/* Bezugsquelle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#64748b' }}>
          {po.mode === 'supplier'
            ? <><UserIcon size={12} /> Lieferant: {po.supplier_name ?? (po.supplier_id ? `#${po.supplier_id}` : 'nicht zugewiesen (Selbst-Beschaffung)')}</>
            : <><Link2 size={12} /> {po.webshop_url
                ? <a href={po.webshop_url} target="_blank" rel="noreferrer" style={{ color: '#2563eb', wordBreak: 'break-all' }}>Webshop öffnen</a>
                : 'Webshop'}</>}
        </div>

        {/* Lieferadresse: Firmenadresse aus der Systemkonfiguration */}
        {company?.street && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, color: '#64748b' }}>
            <MapPin size={12} />
            <span>
              Lieferadresse: {[company.street, company.street_number].filter(Boolean).join(' ')}, {company.zip} {company.city}
            </span>
          </div>
        )}

        {/* Offerte / Bestellsumme */}
        {canEditOffer ? (
          <>
            <TextField label="Bestellsumme netto, exkl. MWST (CHF)" value={form.order_total} onChange={(v) => set('order_total', v)} required placeholder="z. B. 1250" hint="Gesamtsumme für die ganze Bestellmenge" />
            {isWebshop ? (
              <TextField label="Lieferzeit (Tage)" value={form.lead_time_days} onChange={(v) => set('lead_time_days', v)} placeholder="z. B. 14" hint="Webshop wird sofort bezahlt – kein Zahlungsziel" />
            ) : (
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
                <TextField label="Lieferzeit (Tage)" value={form.lead_time_days} onChange={(v) => set('lead_time_days', v)} placeholder="z. B. 14" />
                <TextField label="Zahlungsziel (Tage)" value={form.payment_terms_days} onChange={(v) => set('payment_terms_days', v)} placeholder="z. B. 30" />
              </div>
            )}
          </>
        ) : (po.order_total != null || s !== 'requested') && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Row k="Bestellsumme netto" v={`CHF ${fmtMoney(po.order_total)}`} />
            <Row k="Lieferzeit" v={po.lead_time_days != null ? `${po.lead_time_days} Tage` : '—'} />
            {!isWebshop && <Row k="Zahlungsziel" v={po.payment_terms_days != null ? `${po.payment_terms_days} Tage` : 'sofort'} />}
          </div>
        )}

        {/* Preis pro Stück (berechnet) */}
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

        {/* Tracking (optionales Detail von «Bestellt») */}
        {canEditTracking ? (
          <div>
            <TextField label="Tracking-Nummer (optional)" value={form.tracking_number} onChange={(v) => set('tracking_number', v)} placeholder="wird automatisch gespeichert" />
            {trackingSaved && <div style={{ marginTop: 4, fontSize: 11, color: '#16a34a' }}>✓ gespeichert</div>}
          </div>
        ) : (
          po.tracking_number && <Row k="Tracking-Nummer" v={po.tracking_number} />
        )}

        {/* Wareneingang/Transport läuft über den Pflicht-Bewegungsschritt – hier nur kaufmännisch */}
        {s === 'ordered' && isBuyer && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, fontSize: 12, color: '#64748b' }}>
            <MapPin size={14} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>«Lieferung bestätigen» ist rein kaufmännisch. Das Einlagern (Lagerplatz) erfolgt anschliessend im Bewegungs-Schritt.</span>
          </div>
        )}

        {/* Aktionen – Primäraktion speichert Eingaben + Übergang in einem Klick */}
        {(actions.length > 0 || canEditTracking || error) && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', borderTop: '1px solid #f1f5f9', paddingTop: 12 }}>
            <span style={{ flex: 1, fontSize: 12, color: error ? '#dc2626' : '#94a3b8', minWidth: 120 }}>{error ?? cfg.label}</span>
            {canEditTracking && (
              <button onClick={saveTracking} disabled={saving}
                style={{ padding: '6px 14px', borderRadius: 7, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer' }}>
                Tracking speichern
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
              Artikel-Spezifikation{isStaff ? ' (für Lieferant sichtbar)' : ''}
            </span>
          </div>
          {sharedRows.map((r) => <Row key={r.key} k={r.label} v={r.value} />)}
        </Card>
      )}
    </>
  );
}

const FLOW = [
  { key: 'requested', label: 'Angefragt' },
  { key: 'quoted', label: 'Offeriert' },
  { key: 'ordered', label: 'Bestellt' },
  { key: 'received', label: 'Geliefert' },
] as const;

function hint(h: Hist | undefined): string | undefined {
  if (!h) return undefined;
  return `${h.by ?? 'System'} · ${fmtDateTime(h.at)}`;
}

function buildNodes(status: string, isWebshop: boolean, hist: Record<string, Hist>): PNode[] {
  if (status === 'rejected') {
    return [
      { key: 'requested', label: 'Angefragt', state: 'done', hint: hint(hist.requested) },
      { key: 'quoted', label: 'Offeriert', state: 'done', hint: hint(hist.quoted) },
      { key: 'rejected', label: 'Abgelehnt', state: 'rejected', hint: hint(hist.rejected) },
    ];
  }
  // Webshop: nur Bestellt → Wareneingang
  const flow = isWebshop ? FLOW.filter((f) => f.key === 'ordered' || f.key === 'received') : FLOW;
  const ci = flow.findIndex((f) => f.key === status);
  // Im Webshop ist „requested" der Zustand vor „Bestellt" → erster Knoten aktiv
  const current = isWebshop && status === 'requested' ? 0 : ci;
  return flow.map((f, i) => ({
    key: f.key,
    label: f.label,
    state: i < current ? 'done' : i === current ? (status === 'received' ? 'done' : 'active') : 'pending',
    hint: hint(hist[f.key]),
  }));
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
