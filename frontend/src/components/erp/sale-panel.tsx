'use client';

import { useEffect, useState } from 'react';
import { Receipt, CheckCircle2, FileText, Banknote, Ban, Calculator, User as UserIcon } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { saleStatusConfig, saleNodes } from '@/lib/sale';
import { PrimaryButton, SearchSelect, TextField, ErrorText, StatusBadge, PanelHeader } from '@/components/erp/fields';
import { PurchaseProgress } from '@/components/erp/purchase-progress';
import { fmtObjId } from '@/components/erp/user-detail';

/** Verkaufsschritt (kaufmännisch, Spiegel der Beschaffung): Kunde + Betrag erfassen,
 *  dann Bestätigung → Rechnung → Zahlung. Die Unter-Schritte werden – wie bei der
 *  Beschaffung – als Fortschritt visualisiert. Der Versand läuft über die Bewegung.
 *  Der Kunde ist NIE optional (zur Bestätigung Pflicht). */
export function SalePanel({ order, stepState, stepId, onOrderUpdated }: {
  order: Order;
  stepState: string;
  stepId: number;
  onOrderUpdated: (o: Order) => void;
}) {
  const sale = order.sale;
  const [customers, setCustomers] = useState<UserProfile[]>([]);
  const [customerId, setCustomerId] = useState(sale?.customer_id ? String(sale.customer_id) : '');
  const [total, setTotal] = useState(sale?.order_total != null ? String(sale.order_total) : '');
  const [vat, setVat] = useState(sale?.vat_rate != null ? String(sale.vat_rate) : '8.1');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Als Kunde sind ALLE Benutzer wählbar – auch Mitarbeiter können selbst bestellen.
    api.getUsers().then(setCustomers).catch(() => {});
  }, []);

  if (!sale || order.object_id == null) return null;
  const status = sale.status;
  const editable = stepState === 'active' && status === 'requested';
  const qty = sale.quantity ?? order.quantity ?? 0;
  const unit = total && qty ? (Number(total) / qty) : null;
  const cfg = saleStatusConfig(status);
  const nodes = saleNodes(sale);
  const selectedCustomer = customers.find((c) => String(c.id) === customerId);
  const customerName = sale.customer_name ?? (selectedCustomer ? userDisplayName(selectedCustomer) : undefined);
  // Pflichtfeld Kunde: ohne Kunde keine Bestätigung möglich.
  const canConfirm = !!customerId && !!total;

  async function send(next: string) {
    if (next === 'confirmed' && !customerId) { setError('Bitte einen Kunden auswählen'); return; }
    setBusy(true); setError(null);
    try {
      const updated = await api.updateOrderSale(order.object_id!, {
        status: next as 'confirmed' | 'invoiced' | 'paid' | 'cancelled',
        order_total: total ? Number(total) : null,
        vat_rate: vat ? Number(vat) : null,
        customer_id: customerId ? Number(customerId) : null,
        step_id: stepId,
      });
      onOrderUpdated(updated);
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler'); }
    finally { setBusy(false); }
  }

  return (
    <Card>
      {/* Kopf */}
      <PanelHeader icon={Receipt} title="Verkauf" tone="#0d9488"
        info="Kaufmännischer Ablauf: Bestätigung → Rechnung → Zahlung."
        right={<StatusBadge cfg={cfg} size={11} />} />

      {/* Fortschritt der Unter-Schritte (analog Beschaffung) */}
      <div style={{ padding: '8px 2px 2px' }}>
        <PurchaseProgress nodes={nodes} />
      </div>

      {editable ? (
        <>
          {/* Kunde ist Pflicht – keine «kein Kunde»-Option */}
          <SearchSelect label="Kunde" value={customerId} onChange={setCustomerId} required
            placeholder="Kunde auswählen …"
            options={customers.map((c) => ({ value: String(c.id), label: `${fmtObjId(c.object_id)} · ${userDisplayName(c)}` }))} />
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ flex: 1 }}><TextField label="Verkaufsbetrag netto (CHF)" value={total} onChange={setTotal} required placeholder="z. B. 1250.00" /></div>
            <div style={{ width: 120 }}><TextField label="MWST %" value={vat} onChange={setVat} /></div>
          </div>
          <UnitBox unit={unit} qty={qty} />
          {error && <ErrorText msg={error} />}
          <PrimaryButton icon={CheckCircle2} onClick={() => send('confirmed')} disabled={busy || !canConfirm}>
            Bestätigen (Auftragsbestätigung)
          </PrimaryButton>
          <button onClick={() => send('cancelled')} disabled={busy} style={ghost}><Ban size={13} /> Verkauf stornieren</button>
        </>
      ) : (
        <>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            <Row k="Kunde" v={customerName ?? '—'} icon={UserIcon} />
            {sale.order_total != null && (
              <Row k="Betrag netto" v={`${Number(sale.order_total).toFixed(2)} ${sale.currency}${sale.vat_rate != null ? ` + ${sale.vat_rate}% MWST` : ''}`} />
            )}
            {sale.invoice_number && <Row k="Rechnungs-Nr." v={sale.invoice_number} />}
          </div>
          {unit != null && <UnitBox unit={unit} qty={qty} />}
          {error && <ErrorText msg={error} />}
          {stepState === 'active' && status === 'confirmed' && (
            <PrimaryButton icon={FileText} onClick={() => send('invoiced')} disabled={busy}>Rechnung erstellen</PrimaryButton>
          )}
          {stepState === 'active' && status === 'invoiced' && (
            <PrimaryButton icon={Banknote} onClick={() => send('paid')} disabled={busy}>Zahlung erfassen</PrimaryButton>
          )}
          {status === 'paid' && (
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#16a34a', fontWeight: 600, fontSize: 13 }}>
              <CheckCircle2 size={15} /> Bezahlt
            </div>
          )}
        </>
      )}
    </Card>
  );
}

function UnitBox({ unit, qty }: { unit: number | null; qty: number }) {
  if (unit == null) return null;
  return (
    <div style={{ background: '#f0fdfa', border: '1px solid #99f6e4', borderRadius: 8, padding: '10px 12px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <Calculator size={13} style={{ color: '#0f766e' }} />
        <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#0f766e' }}>Stückpreis netto</span>
      </div>
      <div style={{ fontSize: 18, fontWeight: 800, color: '#0f766e' }}>CHF {unit.toFixed(2)}</div>
      <div style={{ fontSize: 11, color: '#94a3b8' }}>Verkaufsbetrag ÷ Menge ({qty || '—'})</div>
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

function Row({ k, v, icon: Icon }: { k: string; v: string; icon?: React.ElementType }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span style={{ color: '#94a3b8', flexShrink: 0, display: 'inline-flex', alignItems: 'center', gap: 5 }}>
        {Icon && <Icon size={12} />}{k}
      </span>
      <span style={{ color: '#0F172A', fontWeight: 600, textAlign: 'right' }}>{v}</span>
    </div>
  );
}

const ghost: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5, alignSelf: 'flex-start',
  border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0,
};
