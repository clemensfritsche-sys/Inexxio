'use client';

import { useState } from 'react';
import { Check, CircleSlash, Minus, Undo2 } from 'lucide-react';
import type { PurchaseEmbed, PurchaseQuote } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { Label, inputCls, numericInputProps, numericOnly } from '@/components/erp/fields';
import { formatAmount } from '@/lib/utils';

/**
 * **Der Beschaffungs-Beleg an der Ausführungsstelle — drei Stufen, eine Kette.**
 *
 * `Anfrage → Bestellung → Wareneingang`, immer dieselben, egal ob im Shop gekauft oder
 * beim Lieferanten bestellt wird. Der Unterschied ist nur, **wer den Preis einträgt** –
 * du oder der Lieferant. Ein zweiter Ablauf für dieselben drei Stufen wäre dieselbe
 * Angabe ein zweites Mal.
 *
 * **Die Stufen gehören dem Beleg, nicht dem Stück.** Die Einzelinstanzen stehen von der
 * Anfrage bis zum Wareneingang durchgehend auf `Im Prozess`; sie warten, sie ändern sich
 * nicht. Wer den Bestellzustand an den Zustand des Stücks hängte, hätte Zustände
 * erfunden, die keine Aussage über das Material sind.
 *
 * **Zeilen, keine Modul-Karten.** Eine Stufe ist kein Modul – sähe sie aus wie eines,
 * stünden im selben Bild zwei Massstäbe. Was sie mit der Hauptachse teilt, ist die
 * **Regel**, nicht die Form: kräftige Linie bis zur offenen Stelle, Haarlinie danach.
 *
 * **Ein Modul räumt selbst auf.** Jede Zusage nach aussen hat ihre Gegenhandlung an
 * derselben Stelle – und es ist **eine**: was `revoke` bewirkt, sagt die Stufe (vor der
 * Bestellung zurückziehen, danach stornieren). Was **Stücke** betrifft, entscheidet
 * dagegen ein Mensch; dieses Modul legt keinen Auftrag an.
 */
/** Derselbe Beleg, nur mit gefüllten Listen – siehe `PurchaseWork`. */
type Filled = Omit<PurchaseEmbed, 'stages' | 'quotes' | 'allowed'> & {
  stages: NonNullable<PurchaseEmbed['stages']>;
  quotes: NonNullable<PurchaseEmbed['quotes']>;
  allowed: NonNullable<PurchaseEmbed['allowed']>;
};

export function PurchaseWork({ purchase, busy, onAction, children }: {
  purchase: PurchaseEmbed;
  busy?: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
  /** Der Wareneingang selbst – der Scan, der jedes Modul abschliesst. */
  children?: React.ReactNode;
}) {
  // Die Listen sind serverseitig immer gesetzt; der generierte Typ lässt sie optional,
  // weil Pydantic-Defaults dort so ankommen. Einmal hier vereinheitlicht statt an jeder
  // Lesestelle ein `?? []`.
  const p = { ...purchase, stages: purchase.stages ?? [], quotes: purchase.quotes ?? [],
              allowed: purchase.allowed ?? [] };
  const cancelled = p.stage === 'storniert';

  return (
    <div className="flex flex-col">
      {p.stages.map((stage, i) => {
        const last = i === p.stages.length - 1;
        // **Die Regel der Hauptachse, eine Ebene tiefer**: kräftig bis zur offenen
        // Stelle, Haarlinie danach. Storniert heisst: keine Stufe ist mehr aktiv.
        const walked = stage.done;
        return (
          <div key={stage.key} className="flex gap-2.5">
            <div className="flex flex-col items-center" style={{ width: 14, flex: 'none' }}>
              <Dot done={stage.done} active={stage.active && !cancelled} />
              {!last && (
                <div style={{
                  flex: 1, width: walked ? 2 : 1, minHeight: 14,
                  background: walked ? 'var(--fg-2)' : 'var(--border-2)',
                }} />
              )}
            </div>
            <div className="flex-1 min-w-0" style={{ paddingBottom: last ? 0 : 12 }}>
              <div className="flex items-baseline gap-2">
                <span style={{
                  font: `${stage.active && !cancelled ? 700 : 600} 12.5px var(--font-body)`,
                  color: stage.active && !cancelled ? 'var(--fg-1)'
                    : stage.done ? 'var(--fg-2)' : 'var(--fg-4)',
                }}>{stage.label}</span>
                {i === 0 && <Summary p={p} />}
              </div>
              {stage.key === 'anfrage' && stage.active && !cancelled && (
                <Ask p={p} busy={busy} onAction={onAction} />
              )}
              {stage.key === 'bestellung' && stage.active && !cancelled && (
                <Ordered p={p} busy={busy} onAction={onAction} />
              )}
              {stage.key === 'wareneingang' && p.stage === 'bestellung' && !cancelled && (
                <div className="mt-1.5">{children}</div>
              )}
            </div>
          </div>
        );
      })}
      {cancelled && (
        <div className="flex items-center gap-1.5 mt-1 text-[12.5px]"
          style={{ color: 'var(--danger)' }}>
          <CircleSlash size={13} /> Storniert – hier kommt nichts mehr an.
        </div>
      )}
    </div>
  );
}

/** Punkt statt Nummer: erledigt · dran · kommt noch (Design-System «Punkt + Wort»). */
function Dot({ done, active }: { done: boolean; active: boolean }) {
  const size = 10;
  return (
    <span style={{
      width: size, height: size, borderRadius: 999, flex: 'none', marginTop: 4,
      background: done ? 'var(--fg-2)' : active ? 'var(--accent)' : 'transparent',
      border: done || active ? 'none' : '1px solid var(--border-2)',
    }} />
  );
}

/** Was gekauft wird – einmal, an der ersten Stufe. Nicht in jeder Zeile wiederholt. */
function Summary({ p }: { p: Filled }) {
  return (
    <span className="truncate text-[12.5px]" style={{ color: 'var(--fg-3)' }}>
      <span style={{ fontVariantNumeric: 'tabular-nums' }}>{p.quantity}</span>
      {p.unit ? ` ${p.unit}` : ''} · {p.article_name}
    </span>
  );
}


/**
 * **Die Anfrage — bei wem, und was kostet es.**
 *
 * Solange nichts angefragt ist, stehen die **zugelassenen** Lieferanten da (die
 * Lieferantenfreigabe aus der Definition) und man wählt, bei wem man fragt. Danach ist
 * jede Zeile ein Angebot: der Preis kommt entweder vom Lieferanten selbst (Portal) oder
 * wird hier eingetragen – bei einem Shop-Kauf ist das der Katalogpreis.
 */
function Ask({ p, busy, onAction }: {
  p: Filled; busy?: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
}) {
  const asked = p.quotes.length > 0;
  const [picked, setPicked] = useState<number[]>(p.allowed.map((a) => a.supplier_object_id));
  const [qty, setQty] = useState(String(p.quantity));
  const [prices, setPrices] = useState<Record<number, string>>({});
  const [days, setDays] = useState<Record<number, string>>({});

  return (
    <div className="flex flex-col gap-2 mt-1.5">
      {!asked && (
        <>
          <div style={{ maxWidth: 150 }}>
            <Label>Menge</Label>
            <input className={inputCls} {...numericInputProps} value={qty}
              onChange={(e) => setQty(numericOnly(e.target.value))} />
          </div>
          {p.allowed.map((a) => (
            <label key={a.supplier_object_id} className="flex items-center gap-2 text-[13px]">
              <input type="checkbox" checked={picked.includes(a.supplier_object_id)}
                onChange={(e) => setPicked((cur) => (e.target.checked
                  ? [...cur, a.supplier_object_id]
                  : cur.filter((n) => n !== a.supplier_object_id)))} />
              <ObjId value={a.supplier_object_id} />
              <span className="truncate" style={{ color: 'var(--fg-3)' }}>{a.supplier_name}</span>
            </label>
          ))}
          <button type="button" className="erp-actbtn erp-actbtn-primary self-start"
            style={{ height: 32 }} disabled={busy || picked.length === 0}
            onClick={() => onAction({
              action: 'ask', suppliers: picked, quantity: Number(qty) || undefined,
            })}>
            Anfragen
          </button>
        </>
      )}

      {asked && p.quotes.map((q) => (
        <QuoteRow key={q.supplier_object_id} q={q} p={p} busy={busy} onAction={onAction}
          price={prices[q.supplier_object_id] ?? ''}
          onPrice={(v) => setPrices((c) => ({ ...c, [q.supplier_object_id]: v }))}
          lead={days[q.supplier_object_id] ?? ''}
          onLead={(v) => setDays((c) => ({ ...c, [q.supplier_object_id]: v }))} />
      ))}

      {asked && (
        <button type="button" className="erp-actbtn erp-actbtn-neutral self-start"
          style={{ height: 28 }} disabled={busy}
          onClick={() => onAction({ action: 'revoke' })}>
          <Undo2 size={13} /> Anfrage zurückziehen
        </button>
      )}
    </div>
  );
}

/** Eine Angebotszeile: Lieferant · Preis · Frist – und was man damit tun kann. */
function QuoteRow({ q, p, busy, price, lead, onPrice, onLead, onAction }: {
  q: PurchaseQuote; p: Filled; busy?: boolean;
  price: string; lead: string;
  onPrice: (v: string) => void; onLead: (v: string) => void;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
}) {
  const declined = q.state === 'abgelehnt';
  return (
    <div className="flex flex-wrap items-center gap-2 text-[13px]"
      style={{ borderTop: '1px solid var(--border-1)', paddingTop: 6 }}>
      <ObjId value={q.supplier_object_id} />
      <span className="truncate" style={{ color: 'var(--fg-3)', minWidth: 60 }}>{q.supplier_name}</span>
      {declined ? (
        <span className="flex items-center gap-1" style={{ color: 'var(--danger)' }}>
          <Minus size={12} /> abgelehnt
        </span>
      ) : q.amount != null ? (
        <>
          <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
            {formatAmount(q.amount)} {p.currency}
          </span>
          {q.lead_days != null && (
            <span style={{ color: 'var(--fg-4)' }}>{q.lead_days} Tage</span>
          )}
          <button type="button" className="erp-actbtn erp-actbtn-primary ml-auto"
            style={{ height: 28 }} disabled={busy}
            onClick={() => onAction({
              action: 'order', supplier: q.supplier_object_id, amount: q.amount,
            })}>
            Bestellen
          </button>
        </>
      ) : (
        <>
          <input className={inputCls} {...numericInputProps} placeholder="Betrag netto"
            style={{ width: 120 }} value={price}
            onChange={(e) => onPrice(numericOnly(e.target.value, { decimals: true }))} />
          <input className={inputCls} {...numericInputProps} placeholder="Tage"
            style={{ width: 74 }} value={lead}
            onChange={(e) => onLead(numericOnly(e.target.value))} />
          <button type="button" className="erp-actbtn erp-actbtn-neutral"
            style={{ height: 28 }} disabled={busy || !price.trim()}
            onClick={() => onAction({
              action: 'quote', supplier: q.supplier_object_id,
              amount: Number(price), lead_days: lead ? Number(lead) : undefined,
            })}>
            <Check size={13} /> Offerte
          </button>
          <button type="button" className="erp-actbtn erp-actbtn-neutral"
            style={{ height: 28 }} disabled={busy}
            onClick={() => onAction({ action: 'decline', supplier: q.supplier_object_id })}>
            Absage
          </button>
        </>
      )}
    </div>
  );
}

/**
 * **Bestellt — und was der Lieferant zurückgibt.**
 *
 * Die Referenz (Bestellnummer, Link, Sendungsnummer) kommt **nach** der Bestellung; sie
 * am Bestellen mitzugeben hiesse, sie zu erfinden oder das Bestellen zu verzögern.
 *
 * **Verliert der Beleg seine Grundlage, ändert das System hier nichts.** Ab dieser Stufe
 * ist eine zweite Partei gebunden – es steht eine Bestellung beim Lieferanten. Also wird
 * **gemeldet** und auf die Bestätigung gewartet, statt still eine andere Menge zu
 * behaupten.
 */
function Ordered({ p, busy, onAction }: {
  p: Filled; busy?: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
}) {
  const [ref, setRef] = useState(p.reference ?? '');
  const [due, setDue] = useState(p.due_date ?? '');
  const dirty = ref !== (p.reference ?? '') || due !== (p.due_date ?? '');

  return (
    <div className="flex flex-col gap-2 mt-1.5">
      <div className="flex flex-wrap items-center gap-2 text-[13px]">
        {p.supplier_object_id != null && <ObjId value={p.supplier_object_id} />}
        <span className="truncate" style={{ color: 'var(--fg-3)' }}>{p.supplier_name}</span>
        {p.amount != null && (
          <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
            {formatAmount(p.amount)} {p.currency}
          </span>
        )}
      </div>

      {p.clarify_quantity != null && (
        <div className="flex flex-wrap items-center gap-2 text-[12.5px]"
          style={{ color: 'var(--warning)' }}>
          <span>
            Bestellt für <b style={{ fontVariantNumeric: 'tabular-nums' }}>{p.quantity}</b>,
            gebraucht <b style={{ fontVariantNumeric: 'tabular-nums' }}>{p.clarify_quantity}</b>
            {' '}– mit Lieferant klären.
          </span>
          <button type="button" className="erp-actbtn erp-actbtn-neutral"
            style={{ height: 28 }} disabled={busy}
            onClick={() => onAction({ action: 'clarified' })}>
            Lieferant hat zugestimmt
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <div style={{ flex: 1, minWidth: 160 }}>
          <Label>Referenz</Label>
          <input className={inputCls} value={ref} placeholder="Bestellnummer, Link, Sendungsnummer"
            onChange={(e) => setRef(e.target.value)} />
        </div>
        <div style={{ width: 150 }}>
          <Label>Termin</Label>
          <input className={inputCls} type="date" value={due}
            onChange={(e) => setDue(e.target.value)} />
        </div>
        <button type="button" className="erp-actbtn erp-actbtn-neutral" style={{ height: 34 }}
          disabled={busy || !dirty}
          onClick={() => onAction({ action: 'note', reference: ref, due_date: due || null })}>
          Übernehmen
        </button>
      </div>

      <button type="button" className="erp-actbtn erp-actbtn-danger self-start"
        style={{ height: 28 }} disabled={busy}
        onClick={() => onAction({ action: 'revoke' })}>
        <Undo2 size={13} /> Bestellung stornieren
      </button>
    </div>
  );
}
