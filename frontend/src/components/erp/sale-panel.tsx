'use client';

import { useEffect, useState } from 'react';
import { Receipt, CheckCircle2, FileText, Banknote, Ban, Calculator, User as UserIcon, Store, Building2, AlertTriangle, RotateCcw } from 'lucide-react';
import { api } from '@/lib/api';
import type { Order, OrderSale, PaymentMethod, UserProfile } from '@/types';
import { userDisplayName } from '@/lib/utils';
import { saleStatusConfig, saleNodes } from '@/lib/sale';
import { ErrorText, PanelHeader, PrimaryButton, Row, SearchSelect, Segmented, StatusBadge, TextField } from '@/components/erp/fields';
import { PurchaseProgress } from '@/components/erp/purchase-progress';
import { fmtObjId } from '@/components/erp/user-detail';
import { ObjId } from '@/components/erp/obj-id';

// Zahlungsart des manuellen Zahlungseingangs – kein Kartenterminal nötig, der übliche
// B2B-Weg ist die Rechnung (QR-Rechnung). 'stripe' setzt das System selbst (Shop-Zahlung).
const PAYMENT_METHOD_LABEL: Record<string, string> = {
  invoice: 'Rechnung', cash: 'Bar', twint: 'Twint', other: 'Sonstige', stripe: 'Online (Stripe)',
};

/** Verkaufsschritt (kaufmännisch, Spiegel der Beschaffung): Kunde + Betrag erfassen,
 *  dann Bestätigung → Rechnung → Zahlung. Die Unter-Schritte werden – wie bei der
 *  Beschaffung – als Fortschritt visualisiert. Der Versand läuft über die Bewegung.
 *
 *  EIN Schritt, ABER ggf. mehrere Belege (ein Verkauf-Fact je Artikel eines Mehr-
 *  positionen-Auftrags) – ``sales`` ist immer die vollständige Liste (mind. 1 Eintrag).
 *  Bei genau einer Position bleibt der Betrag frei editierbar (z. B. Artikel ohne
 *  hinterlegten Verkaufspreis); bei mehreren kommt der Betrag PRO POSITION vom Artikel
 *  (Single Source of Truth, Preis-Pipeline des Shops) – keine freie Eingabe mehr, damit
 *  nicht ein einzelner Betrag über unterschiedliche Artikel/Preismodelle gestülpt wird. */
export function SalePanel({ order, sales, stepState, stepId, onOrderUpdated }: {
  order: Order;
  sales: OrderSale[];
  stepState: string;
  stepId: number;
  onOrderUpdated: (o: Order) => void;
}) {
  const first = sales[0] as OrderSale | undefined;
  const isSingle = sales.length === 1;
  const [customers, setCustomers] = useState<UserProfile[]>([]);
  const [customerId, setCustomerId] = useState(first?.customer_id ? String(first.customer_id) : '');
  const [total, setTotal] = useState(first?.order_total != null ? String(first.order_total) : '');
  const [vat, setVat] = useState(first?.vat_rate != null ? String(first.vat_rate) : '8.1');
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>('invoice');
  const [paymentRef, setPaymentRef] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    // Als Kunde sind ALLE Benutzer wählbar – auch Mitarbeiter können selbst bestellen.
    api.getUsers().then(setCustomers).catch(() => {});
  }, []);

  if (!first || order.object_id == null) return null;
  const status = first.status;
  // Kredit-Modus (Gutschrift/Erstattung): DERSELBE Schritt, wenn der Auftrag auf verkaufte Ware
  // wirkt (Retoure). Betrag/Kunde aus dem Original abgeleitet; die «Zahlung» löst den Stripe-Refund
  // (bzw. die manuelle Gutschrift) aus. Wurde der Verkauf via Stripe abgewickelt → automatisch zurück.
  const isCredit = first.kind === 'credit';
  const editable = stepState === 'active' && status === 'requested';
  const allPriced = sales.every((s) => s.order_total != null);
  const grandTotal = allPriced ? sales.reduce((sum, s) => sum + Number(s.order_total), 0) : null;
  const qty = first.quantity ?? order.quantity ?? 0;
  const unit = isSingle && total && qty ? (Number(total) / qty) : null;
  const cfg = saleStatusConfig(status);
  const nodes = saleNodes(first);
  const selectedCustomer = customers.find((c) => String(c.id) === customerId);
  const customerName = first.customer_name ?? (selectedCustomer ? userDisplayName(selectedCustomer) : undefined);
  // Pflichtfeld Kunde: ohne Kunde keine Bestätigung möglich. Bei mehreren Positionen
  // muss zusätzlich JEDE Position bereits einen (vom Artikel abgeleiteten) Preis tragen.
  const canConfirm = !!customerId && (isSingle ? !!total : allPriced);

  async function send(next: string) {
    if (next === 'confirmed' && !isCredit && !customerId) { setError('Bitte einen Kunden auswählen'); return; }
    setBusy(true); setError(null);
    try {
      const updated = await api.updateOrderSale(order.object_id!, {
        status: next as 'confirmed' | 'invoiced' | 'paid' | 'cancelled',
        // Betrag bei genau EINER Position frei erfassbar (Gutschrift: Teilbetrag/Kulanz).
        ...(isSingle ? {
          order_total: total ? Number(total) : null,
          ...(isCredit ? {} : { vat_rate: vat ? Number(vat) : null }),
        } : {}),
        // Gutschrift: Kunde + Zahlungsart sind abgeleitet – nicht senden.
        ...(isCredit ? {} : {
          customer_id: customerId ? Number(customerId) : null,
          ...(next === 'paid' ? {
            payment_method: paymentMethod,
            payment_reference: paymentRef.trim() || null,
          } : {}),
        }),
        step_id: stepId,
      });
      onOrderUpdated(updated);
    } catch (e) { setError(e instanceof Error ? e.message : 'Fehler'); }
    finally { setBusy(false); }
  }

  // Herkunft: 'shop' (Kunde selbst über die Kasse) | 'direct' (Personal im ERP erfasst,
  // z. B. Telefon/Messe/B2B-Rechnung) – rein informativ, keine unterschiedliche Logik.
  const originBadge = first.mode ? (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, fontWeight: 700,
      padding: '2px 8px', borderRadius: 999, color: first.mode === 'shop' ? '#2563eb' : '#64748b',
      background: first.mode === 'shop' ? '#eff6ff' : '#f1f5f9',
    }}>
      {first.mode === 'shop' ? <Store size={11} /> : <Building2 size={11} />}
      {first.mode === 'shop' ? 'Via Shop' : 'Direkt erfasst'}
    </span>
  ) : null;

  // ── Gutschrift / Erstattung (Kredit-Modus) – eigener, klarer Ablauf ─────────────────────
  if (isCredit) {
    const amount = isSingle && total ? Number(total) : (allPriced ? sales.reduce((s, x) => s + Number(x.order_total), 0) : null);
    return (
      <Card>
        <PanelHeader icon={RotateCcw} title="Gutschrift / Erstattung" tone="#e11d48"
          info="Geld zurück zum Original-Verkauf. Betrag abgeleitet, bei einer Position abweichend erfassbar (Teilbetrag/Kulanz). «Erstattung auslösen» erstattet real (Stripe, falls der Verkauf via Stripe lief) bzw. dokumentiert die Gutschrift. Die Ware kommt getrennt über die Bewegung zurück."
          right={<StatusBadge cfg={cfg} size={11} />} />
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          {sales.map((s) => <SaleLineRow key={s.id} sale={s} credit />)}
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <Row k="Kunde" v={customerName ?? '—'} icon={UserIcon} />
          {first.original_sale_id != null && <Row k="Original-Beleg" v={`#${first.original_sale_id}`} />}
          {first.credit_note_number && <Row k="Gutschrift-Nr." v={first.credit_note_number} />}
        </div>
        {editable && isSingle ? (
          <>
            <TextField label="Erstattungsbetrag netto (CHF)" value={total} onChange={setTotal}
              placeholder="aus Original abgeleitet – abweichend möglich" />
            <div style={{ fontSize: 11, color: '#94a3b8', marginTop: -6 }}>Für Teil-Erstattung / Kulanz anpassen.</div>
          </>
        ) : amount != null && (
          <div style={{ background: '#fff1f2', border: '1px solid #fecdd3', borderRadius: 8, padding: '10px 12px' }}>
            <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#be123c' }}>Erstattungsbetrag netto</div>
            <div style={{ fontSize: 18, fontWeight: 800, color: '#be123c' }}>− {amount.toFixed(2)} {first.currency}</div>
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

  return (
    <Card>
      {/* Kopf */}
      <PanelHeader icon={Receipt} title="Verkauf" tone="#0d9488"
        info="Kaufmännischer Ablauf: Bestätigung → Rechnung → Zahlung."
        right={<div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>{originBadge}<StatusBadge cfg={cfg} size={11} /></div>} />

      {/* Positionen – bei einem Mehrpositionen-Auftrag trägt jede Position ihren eigenen
          Beleg (eigener Artikel, eigener vom Artikel abgeleiteter Preis). */}
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {sales.map((s) => <SaleLineRow key={s.id} sale={s} />)}
      </div>
      {!isSingle && (
        grandTotal != null ? (
          <TotalBox total={grandTotal} currency={first.currency} />
        ) : (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 12px', background: '#fffbeb', border: '1px solid #fde68a', borderRadius: 8, fontSize: 12, color: '#92400e' }}>
            <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 1 }} />
            <span>Für mindestens eine Position ist kein Verkaufspreis hinterlegt – bitte am
              Artikel (Reiter «Verkauf») einen Preis anlegen, bevor der Verkauf bestätigt wird.</span>
          </div>
        )
      )}

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
          {isSingle && (
            <>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{ flex: 1 }}><TextField label="Verkaufsbetrag netto (CHF)" value={total} onChange={setTotal} required placeholder="z. B. 1250.00" /></div>
                <div style={{ width: 120 }}><TextField label="MWST %" value={vat} onChange={setVat} /></div>
              </div>
              <UnitBox unit={unit} qty={qty} />
            </>
          )}
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
            {first.invoice_number && <Row k="Rechnungs-Nr." v={first.invoice_number} />}
            {first.payment_method && (
              <Row k="Zahlungsart" v={PAYMENT_METHOD_LABEL[first.payment_method] ?? first.payment_method} />
            )}
            {first.payment_reference && <Row k="Zahlungsreferenz" v={first.payment_reference} />}
          </div>
          {isSingle && unit != null && <UnitBox unit={unit} qty={qty} />}
          {error && <ErrorText msg={error} />}
          {stepState === 'active' && status === 'confirmed' && (
            <PrimaryButton icon={FileText} onClick={() => send('invoiced')} disabled={busy}>Rechnung erstellen</PrimaryButton>
          )}
          {stepState === 'active' && status === 'invoiced' && (
            <>
              {/* Kein Kartenterminal nötig – Rechnung (QR-Rechnung) ist der übliche B2B-Weg;
                  bar/Twint für Vor-Ort-Verkäufe. */}
              <Segmented label="Zahlungsart" value={paymentMethod} onChange={(v) => setPaymentMethod(v as PaymentMethod)}
                options={[
                  { value: 'invoice', label: 'Rechnung' },
                  { value: 'cash', label: 'Bar' },
                  { value: 'twint', label: 'Twint' },
                  { value: 'other', label: 'Sonstige' },
                ]} />
              <TextField label="Zahlungsreferenz (optional)" value={paymentRef} onChange={setPaymentRef}
                placeholder="z. B. QR-Referenz, Beleg-Nr." />
              <PrimaryButton icon={Banknote} onClick={() => send('paid')} disabled={busy}>Zahlung erfassen</PrimaryButton>
            </>
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

// Eine Position (ein Beleg): Artikel + Menge links, der vom Artikel abgeleitete Betrag
// rechts – fehlt ein Preis, ein klarer Hinweis statt einer leeren/falschen Zahl.
function SaleLineRow({ sale, credit }: { sale: OrderSale; credit?: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, padding: '7px 0', borderBottom: '1px solid #f1f5f9' }}>
      {sale.article_object_id != null && <ObjId value={sale.article_object_id} />}
      <span style={{ flex: 1, minWidth: 0, color: '#0F172A', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
        {sale.quantity ?? 1}× {sale.article_name ?? 'Artikel'}
      </span>
      {sale.order_total != null ? (
        <span style={{ color: credit ? '#be123c' : '#0f766e', fontWeight: 700, flexShrink: 0 }}>
          {credit ? '− ' : ''}{Number(sale.order_total).toFixed(2)} {sale.currency}
        </span>
      ) : (
        <span style={{ color: '#dc2626', fontSize: 11, fontWeight: 700, flexShrink: 0 }}>Kein {credit ? 'Betrag' : 'Preis'}</span>
      )}
    </div>
  );
}

function TotalBox({ total, currency }: { total: number; currency: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '8px 2px 0' }}>
      <span style={{ fontSize: 12, fontWeight: 700, color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Summe netto</span>
      <span style={{ fontSize: 16, fontWeight: 800, color: '#0f766e' }}>{total.toFixed(2)} {currency}</span>
    </div>
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {children}
    </div>
  );
}


const ghost: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 5, alignSelf: 'flex-start',
  border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0,
};
