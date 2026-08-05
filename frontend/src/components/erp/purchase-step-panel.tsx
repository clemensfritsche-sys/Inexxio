'use client';

import { useState } from 'react';
import { AlertTriangle, Link2, Calculator, Building2, ExternalLink, FileText, MapPin } from 'lucide-react';
import { api } from '@/lib/api';
import { actorHint } from '@/lib/utils';
import type { CompanySettings, Order, OrderPurchase, PurchaseOrderStatus, PurchaseOrderUpdateInput } from '@/types';
import { unitLabel, serializationLabel } from '@/lib/article';
import { fieldLabel } from '@/lib/article-fields';
import { Row, TextField, numericOnly } from '@/components/erp/fields';
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
      ? { label: 'Bestellt', target: 'ordered', variant: 'primary', needsTotal: true }
      : { label: 'Offeriert', target: 'quoted', variant: 'primary', needsTotal: true });
  }
  if (s === 'quoted' && isBuyer) {
    actions.push({ label: 'Bestellt', target: 'ordered', variant: 'primary' });
    actions.push({ label: 'Ablehnen', target: 'rejected', variant: 'danger' });
  }
  if (s === 'ordered' && isBuyer) {
    actions.push({ label: 'Geliefert', target: 'received', variant: 'primary' });
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
    // Die Lieferzeit ist Pflicht (#195): ohne sie gibt es keinen Termin, an dem die
    // Lieferung fällig wäre – und damit auch keine Überfälligkeit.
    if (needsTotal && !form.lead_time_days.trim()) { setError('Bitte die Lieferzeit erfassen'); return; }
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

  async function clarify() {
    setSaving(true); setError(null);
    try {
      onOrderUpdated(await api.clarifyOrderPurchase(
        order.object_id as number, po.article_id ?? null, stepId ?? null));
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


  return (
    <>
      <Card>
        {/* Kein eigener Kopf und keine Status-Badge hier (#201/#247): die Modul-Karte
            des Flusses heisst «Beschaffung» und trägt den Zustand; welche Stufe gerade
            dran ist, zeigt der Ablauf darunter. */}
        {/* Bei mehreren Positionen: welcher Artikel diese Bestellung betrifft */}
        {showArticle && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 12, fontWeight: 700, color: '#0F172A' }}>
            {po.article_object_id != null && <ObjId value={po.article_object_id} />}
            {po.article_name ?? 'Artikel'}
          </div>
        )}

        {/* Der Beschaffungs-Ablauf als Prozess IM Prozess – gleiche Bildsprache wie der
            Auftrags-Fluss, nur eine Nummer kleiner (#194). */}
        <PurchaseProgress nodes={nodes} delivery={delivery} renderActive={() => (
          <>
            {/* **Was mit dem Lieferanten zu klären ist** (Testnotizen #587/#588).
                Bis zur Zusage zieht das System den Beleg selbst nach; ab «Bestellt» ist der
                Lieferant gebunden und die Ware in aller Regel unterwegs – dann fasst es ihn
                nicht an, sondern sagt, worüber zu reden ist. Wer angerufen hat, quittiert
                hier das Ergebnis; erst das löst dieselbe Änderung aus. */}
            {po.clarify_needed != null && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap',
                padding: '10px 12px', borderRadius: 'var(--r-md)',
                background: 'color-mix(in srgb, var(--warning) 10%, #fff)',
                border: '1px solid color-mix(in srgb, var(--warning) 35%, #fff)' }}>
                <AlertTriangle size={15} style={{ color: 'var(--warning)', flexShrink: 0 }} />
                <span style={{ flex: 1, minWidth: 160, font: '500 12.5px var(--font-body)', color: 'var(--fg-2)' }}>
                  Bestellt {qty} {unit ? unitLabel(unit) : ''} · gebraucht{' '}
                  {po.clarify_needed > 0 ? `${po.clarify_needed} ${unit ? unitLabel(unit) : ''}` : 'nichts mehr'}
                  {' – '}mit Lieferant klären
                </span>
                {isStaff && (
                  <button onClick={clarify} disabled={saving} className="erp-actbtn erp-actbtn-primary">
                    {saving ? '…' : 'Lieferant hat zugestimmt'}
                  </button>
                )}
              </div>
            )}

            {/* Offerte / Bestellsumme */}
            {canEditOffer ? (
              <>
                {/* Beschriftung nennt die Sache, der Platzhalter erklärt sie (#183–#186). */}
                <TextField label="Bestellsumme" value={form.order_total} onChange={(v) => set('order_total', v)} required
                  placeholder="ganze Menge, netto in CHF – z. B. 1250" />
                {isWebshop ? (
                  <TextField label="Lieferzeit" value={form.lead_time_days} onChange={(v) => set('lead_time_days', numericOnly(v, { decimals: false }))} required placeholder="z. B. 14 Tage" />
                ) : (
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))', gap: 14 }}>
                    <TextField label="Lieferzeit" value={form.lead_time_days} onChange={(v) => set('lead_time_days', numericOnly(v, { decimals: false }))} required placeholder="z. B. 14 Tage" />
                    <TextField label="Zahlungsziel" value={form.payment_terms_days} onChange={(v) => set('payment_terms_days', numericOnly(v, { decimals: false }))} placeholder="z. B. 30 Tage" />
                  </div>
                )}
              </>
            ) : (po.order_total != null || s !== 'requested') && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {/* **Der Stückpreis ist eine Ableitung dieser Zahl** (Summe ÷ Menge) – also
                    steht er im Hover an ihr, nicht als eigener hervorgehobener Kasten
                    darunter (Testnotiz #383). Weniger Fläche, dieselbe Auskunft. */}
                <Row k="Bestellsumme netto" v={`CHF ${fmtMoney(po.order_total)}`}
                  hint={perUnit != null ? `CHF ${fmtMoney(perUnit)} pro Stück (netto) – Summe ÷ Menge` : undefined} />
                <Row k="Lieferzeit" v={po.lead_time_days != null ? `${po.lead_time_days} Tage` : '—'} />
                {!isWebshop && <Row k="Zahlungsziel" v={po.payment_terms_days != null ? `${po.payment_terms_days} Tage` : 'sofort'} />}
              </div>
            )}

            {/* Tracking (optionales Detail von «Bestellt») */}
            {canEditTracking ? (
              <div onBlur={saveTracking}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); saveTracking(); } }}>
                {/* Auto-Save wie überall: gespeichert wird beim Verlassen des Felds bzw. mit
                    Enter – ein «Tracking speichern»-Knopf wäre ein zweiter Weg (#198–#200). */}
                <TextField label="Tracking-Nummer" value={form.tracking_number} onChange={(v) => set('tracking_number', v)}
                  placeholder="Tracking-Nummer" />
                {trackingSaved && <div style={{ marginTop: 4, font: '600 11px var(--font-body)', color: 'var(--success)' }}>✓ gespeichert</div>}
              </div>
            ) : (
              po.tracking_number && <Row k="Tracking-Nummer" v={po.tracking_number} />
            )}

            {/* Aktionen – Primäraktion speichert Eingaben + Übergang in einem Klick.
                Kein Statuswort mehr in der Zeile (#188): der Zustand steht oben rechts als
                Badge. Die Knöpfe sprechen die Design-Sprache des ERP (#187): schwarz für die
                Routine-Hauptaktion, rot nur fürs Ablehnen. */}
            {(actions.length > 0 || error) && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', justifyContent: 'flex-end', borderTop: '1px solid var(--border-1)', paddingTop: 12 }}>
                {error && <span style={{ flex: 1, font: '500 12px var(--font-body)', color: 'var(--danger)', minWidth: 120 }}>{error}</span>}
                {actions.map((a) => (
                  <button key={a.target} onClick={() => run(a.target, a.needsTotal)} disabled={saving}
                    className={`erp-actbtn ${a.variant === 'danger' ? 'erp-actbtn-danger' : 'erp-actbtn-primary'}`}>
                    {saving ? '…' : a.label}
                  </button>
                ))}
              </div>
            )}
          </>
        )} />

        {/* Bezugsquelle + Lieferadresse – zwei Tatsachen, eine Zeile je Angabe. */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap', font: '500 12px var(--font-body)', color: 'var(--fg-3)' }}>
          {po.mode === 'supplier' ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <Building2 size={13} /> {po.supplier_name ?? (po.supplier_id ? `#${po.supplier_id}` : 'Selbst-Beschaffung')}
            </span>
          ) : po.webshop_url ? (
            // Ein Link, der wie ein Link aussehen soll, ist ein Knopf mit Symbol – nicht
            // blauer Fliesstext mitten in einer Angabenzeile (Notiz #193).
            <a href={po.webshop_url} target="_blank" rel="noreferrer" className="erp-actbtn erp-actbtn-neutral"
              style={{ height: 30, padding: '0 11px', fontSize: 12.5, textDecoration: 'none' }}>
              <ExternalLink size={13} /> Webshop
            </a>
          ) : (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}><Link2 size={13} /> Webshop</span>
          )}
          {/* Lieferadresse = Adresse des Standorts, an den geliefert wird (heute: die eine
              Firmenadresse aus der Systemkonfiguration). */}
          {company?.street && (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
              <MapPin size={13} /> {[company.street, company.street_number].filter(Boolean).join(' ')}, {company.zip} {company.city}
            </span>
          )}
        </div>

      </Card>

      {/* Für den Lieferanten freigegebene Stammdaten */}
      {sharedRows.length > 0 && (
        <Card>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <FileText size={13} style={{ color: '#94a3b8' }} />
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#64748b' }}>
              Spezifikation
            </span>
          </div>
          {sharedRows.map((r) => <Row key={r.key} k={r.label} v={r.value} />)}
        </Card>
      )}
    </>
  );
}

/**
 * **Die Stufe, auf der man steht, sagt was zu TUN ist; die dahinter, was GESCHEHEN ist**
 * (Notizen #271/#272/#275). Vorher hiess auch die aktive Stufe wie ein Status («Bestellt»),
 * obwohl dort noch nichts bestellt war. Die Knöpfe tragen den erreichten Zustand – man
 * hakt die Stufe ab.
 */
const FLOW = [
  { key: 'requested', verb: 'Anfragen', label: 'Angefragt' },
  { key: 'quoted', verb: 'Offerieren', label: 'Offeriert' },
  { key: 'ordered', verb: 'Bestellen', label: 'Bestellt' },
  { key: 'received', verb: 'Wareneingang', label: 'Geliefert' },
] as const;

function hint(h: Hist | undefined): string | undefined {
  return h ? actorHint(h.by ?? 'System', h.at) : undefined;
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
  if (status === 'cancelled') {
    // **Storniert kann jede Stufe treffen** – anders als «Abgelehnt», das nur aus «Offeriert»
    // erreichbar ist. Gezeigt wird darum der Weg, der tatsächlich gegangen wurde (aus dem
    // Verlauf), und am Ende die Stufe, an der es endete.
    return [
      ...flow.filter((f) => hist[f.key]).map((f) => (
        { key: f.key, label: f.label, state: 'done' as const, hint: hint(hist[f.key]) })),
      { key: 'cancelled', label: 'Storniert', state: 'rejected', hint: hint(hist.cancelled) },
    ];
  }
  const ci = flow.findIndex((f) => f.key === status);
  // Im Webshop ist „requested" der Zustand vor „Bestellt" → erster Knoten aktiv
  const current = isWebshop && status === 'requested' ? 0 : ci;
  return flow.map((f, i) => {
    const state: PNode['state'] = i < current ? 'done'
      : i === current ? (status === 'received' ? 'done' : 'active') : 'pending';
    return { key: f.key, label: state === 'active' ? f.verb : f.label, state, hint: hint(hist[f.key]) };
  });
}

function Card({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {children}
    </div>
  );
}

