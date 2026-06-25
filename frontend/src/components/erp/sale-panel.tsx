'use client';

import { useEffect, useState } from 'react';
import { Receipt, CheckCircle2, FileText, Banknote, Ban } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { PrimaryButton, SearchSelect, TextField, ErrorText } from '@/components/erp/fields';
import { fmtObjId } from '@/components/erp/user-detail';

const STATUS_LABEL: Record<string, string> = {
  requested: 'Angefragt', confirmed: 'Bestätigt', invoiced: 'Verrechnet', paid: 'Bezahlt', cancelled: 'Storniert',
};

/** Verkaufsschritt (kaufmännisch, Spiegel der Beschaffung): Kunde + Betrag erfassen,
 *  dann Bestätigung → Rechnung → Zahlung. Der Versand läuft über die Bewegung. */
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

  async function send(next: string) {
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <Receipt size={16} style={{ color: '#0d9488' }} />
        <span style={{ fontSize: 14, fontWeight: 700, color: '#0f172a' }}>Verkauf</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: '#0d9488', background: '#f0fdfa', padding: '2px 8px', borderRadius: 999 }}>{STATUS_LABEL[status] ?? status}</span>
      </div>

      {editable ? (
        <>
          <SearchSelect label="Kunde (optional)" value={customerId} onChange={setCustomerId}
            options={[{ value: '', label: '— kein Kunde —' }, ...customers.map((c) => ({ value: String(c.id), label: `${fmtObjId(c.object_id)} · ${userDisplayName(c)}` }))]} />
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ flex: 1 }}><TextField label="Verkaufsbetrag netto (CHF)" value={total} onChange={setTotal} required placeholder="z. B. 1250.00" /></div>
            <div style={{ width: 120 }}><TextField label="MWST %" value={vat} onChange={setVat} /></div>
          </div>
          {unit != null && <div style={{ fontSize: 12, color: '#64748b' }}>Stückpreis netto: {unit.toFixed(2)} CHF · Menge {qty}</div>}
          {error && <ErrorText msg={error} />}
          <PrimaryButton icon={CheckCircle2} onClick={() => send('confirmed')} disabled={busy || !total}>Bestätigen (Auftragsbestätigung)</PrimaryButton>
          <button onClick={() => send('cancelled')} disabled={busy} style={ghost}><Ban size={13} /> Verkauf stornieren</button>
        </>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6, fontSize: 13, color: '#475569' }}>
          {sale.customer_name && <div>Kunde: <b>{sale.customer_name}</b></div>}
          {sale.order_total != null && <div>Betrag netto: <b>{Number(sale.order_total).toFixed(2)} {sale.currency}</b>{sale.vat_rate != null ? ` + ${sale.vat_rate}% MWST` : ''}</div>}
          {unit != null && <div>Stückpreis netto: {unit.toFixed(2)} {sale.currency} · Menge {qty}</div>}
          {error && <ErrorText msg={error} />}
          {stepState === 'active' && status === 'confirmed' && (
            <PrimaryButton icon={FileText} onClick={() => send('invoiced')} disabled={busy}>Rechnung erstellen</PrimaryButton>
          )}
          {stepState === 'active' && status === 'invoiced' && (
            <PrimaryButton icon={Banknote} onClick={() => send('paid')} disabled={busy}>Zahlung erfassen</PrimaryButton>
          )}
          {status === 'paid' && <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#16a34a', fontWeight: 600 }}><CheckCircle2 size={15} /> Bezahlt</div>}
        </div>
      )}
    </div>
  );
}

const ghost: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5, alignSelf: 'flex-start',
  border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0,
};
