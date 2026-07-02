'use client';

import { useState } from 'react';
import { RotateCcw, CheckCircle2, FileText, Ban, User as UserIcon } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, OrderSale } from '@/types';
import { saleStatusConfig } from '@/lib/sale';
import { PrimaryButton, TextField, ErrorText, StatusBadge, PanelHeader } from '@/components/erp/fields';

/**
 * Prozessschritt «Rückerstattung» – die **Geld-Seite** einer Retoure (Kredit-Modus des
 * Verkaufs). Betrag/Kunde stammen aus dem **Original-Verkauf** (abgeleitet), können bei genau
 * einer Position aber **abweichend** erfasst werden (z. B. Restocking-Fee, Teil-Erstattung).
 * Ablauf Bestätigen → Ausstellen → **Erstatten**: die «Zahlung» (paid) löst die Stripe-
 * Rückerstattung (bzw. die manuelle Gutschrift) aus. Der **physische** Rückfluss der Ware
 * läuft getrennt über die **Bewegung** (Ware zurück ins Lager) – nicht über diesen Schritt.
 */
export function RefundPanel({ order, sales, stepState, stepId, onOrderUpdated }: {
  order: Order;
  sales: OrderSale[];
  stepState: string;
  stepId: number;
  onOrderUpdated: (o: Order) => void;
}) {
  const first = sales[0] as OrderSale | undefined;
  const isSingle = sales.length === 1;
  const [total, setTotal] = useState(first?.order_total != null ? String(first.order_total) : '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!first || order.object_id == null) return null;
  const status = first.status;
  const cfg = saleStatusConfig(status);
  const editableAmount = isSingle && stepState === 'active' && status === 'requested';
  const grandTotal = sales.every((s) => s.order_total != null)
    ? sales.reduce((sum, s) => sum + Number(s.order_total), 0) : null;
  const displayTotal = isSingle && total ? Number(total) : grandTotal;

  async function send(next: 'confirmed' | 'invoiced' | 'paid' | 'cancelled') {
    setBusy(true); setError(null);
    try {
      onOrderUpdated(await api.updateOrderRefund(order.object_id!, {
        status: next,
        // Betrag nur bei genau EINER Position frei erfassbar (abweichend vom Original);
        // bei mehreren kommt er je Position aus dem Original-Verkauf.
        ...(isSingle && next === 'confirmed' ? { order_total: total ? Number(total) : null } : {}),
        step_id: stepId,
      }));
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler'); }
    finally { setBusy(false); }
  }

  return (
    <Card>
      <PanelHeader icon={RotateCcw} title="Rückerstattung" tone="#e11d48"
        info="Geld zurück (Kredit-Modus des Verkaufs). Betrag aus dem Original-Verkauf abgeleitet, bei einer Position abweichend erfassbar; «Erstattung auslösen» erstattet real (Stripe) bzw. dokumentiert die Gutschrift. Die Ware kommt getrennt über die Bewegung zurück."
        right={<StatusBadge cfg={cfg} size={11} />} />

      {/* Positionen (ein Gutschrift-Beleg je Artikel) */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {sales.map((s) => (
          <div key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, padding: '7px 0', borderBottom: '1px solid #f1f5f9' }}>
            <span style={{ flex: 1, minWidth: 0, color: '#0F172A', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {s.quantity ?? 1}× {s.article_name ?? 'Artikel'}
            </span>
            {s.order_total != null
              ? <span style={{ color: '#be123c', fontWeight: 700, flexShrink: 0 }}>− {Number(s.order_total).toFixed(2)} {s.currency}</span>
              : <span style={{ color: '#dc2626', fontSize: 11, fontWeight: 700, flexShrink: 0 }}>Kein Betrag</span>}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        <Row k="Kunde" v={first.customer_name ?? '—'} icon={UserIcon} />
        {first.original_sale_id != null && <Row k="Original-Beleg" v={`#${first.original_sale_id}`} />}
        {first.credit_note_number && <Row k="Gutschrift-Nr." v={first.credit_note_number} />}
      </div>

      {editableAmount ? (
        <div>
          <TextField label="Erstattungsbetrag netto (CHF)" value={total} onChange={setTotal}
            placeholder="aus Original abgeleitet – abweichend möglich" />
          <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
            Vorbelegt aus dem Original-Verkauf. Für eine Teil-Erstattung / Restocking-Fee anpassen.
          </div>
        </div>
      ) : displayTotal != null && (
        <div style={{ background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 8, padding: '10px 12px' }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#be123c' }}>Erstattungsbetrag netto</div>
          <div style={{ fontSize: 18, fontWeight: 800, color: '#be123c' }}>− {displayTotal.toFixed(2)} {first.currency}</div>
          {first.vat_rate != null && <div style={{ fontSize: 11, color: '#fb7185' }}>inkl. MWST-Korrektur {Number(first.vat_rate)}%</div>}
        </div>
      )}

      {error && <ErrorText msg={error} />}

      {stepState === 'active' && status === 'requested' && (
        <>
          <PrimaryButton icon={CheckCircle2} onClick={() => send('confirmed')} disabled={busy}>Gutschrift bestätigen</PrimaryButton>
          <button onClick={() => send('cancelled')} disabled={busy} style={ghost}><Ban size={13} /> Erstattung verwerfen</button>
        </>
      )}
      {stepState === 'active' && status === 'confirmed' && (
        <PrimaryButton icon={FileText} onClick={() => send('invoiced')} disabled={busy}>Gutschrift ausstellen</PrimaryButton>
      )}
      {stepState === 'active' && status === 'invoiced' && (
        <PrimaryButton icon={RotateCcw} onClick={() => send('paid')} disabled={busy}>Erstattung auslösen</PrimaryButton>
      )}
      {status === 'paid' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#e11d48', fontWeight: 700, fontSize: 13 }}>
            <RotateCcw size={15} /> Erstattet{first.credit_note_number ? ` · ${first.credit_note_number}` : ''}
          </div>
          {first.stripe_refund_id && <div style={{ fontSize: 11, color: '#94a3b8' }}>Stripe-Refund: {first.stripe_refund_id}</div>}
        </div>
      )}
      {status === 'cancelled' && (
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, color: '#94a3b8', fontWeight: 600, fontSize: 13 }}>
          <Ban size={15} /> Erstattung verworfen
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
