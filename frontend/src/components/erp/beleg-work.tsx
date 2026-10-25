'use client';

import { useCallback, useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import type { VoucherEmbed } from '@/types';
import { Documents } from '@/components/erp/beleg/documents';
import { Footer } from '@/components/erp/beleg/footer';
import { startForm } from '@/components/erp/beleg/forms';
import type { Form } from '@/components/erp/beleg/forms';
import { Goods } from '@/components/erp/beleg/goods';
import { Invoice } from '@/components/erp/beleg/invoice';
import { Parties, headOf } from '@/components/erp/beleg/parties';
import { Quotes } from '@/components/erp/beleg/quotes';
import { Stages } from '@/components/erp/beleg/stages';
import { Terms } from '@/components/erp/beleg/terms';
import { filled } from '@/components/erp/beleg/shared';
import type { Send } from '@/components/erp/beleg/shared';

/**
 * ►►► **Der Beleg an der Ausführungsstelle – drei Zonen** (PROCESS_CORE §9.15). ◄◄◄
 *
 *     Stationen (Offerte · Zusage · Rechnung · Erledigt)
 *     Parteien → Positionen → Konditionen → Angebote → Rechnung → Dokumente
 *     DIE Leiste: Stand, wer dran ist, die eine Handlung (+ Stornieren)
 *
 * * **Kein `if` auf die Richtung**: Wörter, Verben, Titel und die Leiste (`state`) reisen
 *   fertig mit; diese Datei fragt `may(...)` (`can` ist Auskunft UND Tor) und zeichnet.
 * * **Jeder änderbare Wert wird sofort geschrieben** (eigenes Verb); wählen ist nicht
 *   anbieten (`party` ↔ `ask`).
 * * **Eingefroren heisst nicht zugeklappt**: jeder Abschnitt bleibt sichtbar.
 *
 * Die Teile stehen in `components/erp/beleg/` – je Abschnitt eine Datei.
 */
export function BelegWork({
  voucher, busy, active, orderObjectId, stepId, onAction, onPaid, children,
}: {
  voucher: VoucherEmbed;
  busy: boolean;
  /** Ist dieses Modul an der Reihe? Der Beleg fragt `can`, nicht die Reihe. */
  active: boolean;
  orderObjectId: number;
  stepId: number;
  onAction: Send;
  /** Der Auftrag soll neu geladen werden – eine Karten-Zahlung kommt über den Webhook. */
  onPaid: () => void;
  /** Der Inhalt des Moduls selbst – am Ende der Karte, über der Leiste. */
  children?: ReactNode;
}) {
  const d = filled(voucher);
  const [shown, setShown] = useState<number | null>(null);
  const [picking, setPicking] = useState(false);
  const [form, setForm] = useState<Form | null>(null);
  const [card, setCard] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const ways = d.ways ?? [];
  // **Die gewählte Antwort ist eine Ableitung** – fällt der Weg weg, steht sie auf dem ersten.
  const way = ways.find((w) => w.key === picked) ?? ways[0] ?? null;
  const wait = useWaitForMoney(d.paid ?? '', onPaid);
  const [failed, setFailed] = useState<string | null>(null);

  // Ein Formular gilt der Lage, in der es geöffnet wurde – ändert sie sich, ist es weg.
  const situation = `${d.stage}:${d.state?.key ?? ''}`;
  useEffect(() => { setForm(null); setCard(false); }, [situation]);

  const chooseWay = useCallback((key: string) => {
    setPicked(key);
    setCard(false);
    const next = ways.find((w) => w.key === key);
    setForm((f) => (f?.kind !== 'pay' ? f
      : (next?.action === 'pay' ? startForm('pay', d, key) : null)));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ways]);

  const refundCard = useCallback(async () => {
    const entry = d.entries.find((e) => e.refundable);
    if (!entry) return;
    setFailed(null);
    try {
      await api.refundVoucherPayment(orderObjectId, stepId, entry.id);
      wait();
    } catch (e) {
      setFailed(e instanceof Error ? e.message : String(e));
    }
  }, [d.entries, orderObjectId, stepId, wait]);

  const asked = new Set(d.quotes.map((q) => q.party_object_id));
  const fresh = (d.recipients ?? []).filter((r) => r.object_id != null
    && !asked.has(r.object_id)).length;
  const head = headOf(d, shown);

  return (
    <div className="flex flex-col" style={{ minWidth: 0 }} data-active={active || undefined}>
      <Stages d={d} />
      <div style={{ minWidth: 0, ...(d.locked ? { opacity: 0.6 } : {}) }}>
        <Parties d={d} shown={shown} orderObjectId={orderObjectId} stepId={stepId}
          onAction={onAction} />
        <Goods d={d} busy={busy} onAction={onAction} />
        <Terms d={d} busy={busy} onAction={onAction} />
        <Quotes d={d} busy={busy} head={head} picking={picking} onShow={setShown}
          onPicking={setPicking} onAction={onAction} />
        <Invoice d={d} busy={busy} form={form} setForm={setForm} way={way} card={card}
          setCard={setCard} orderObjectId={orderObjectId} stepId={stepId} onPaid={wait}
          onAction={onAction} />
        <Documents d={d} />
      </div>
      {children}
      {failed && (
        <span className="flex items-center" style={{ gap: 6, marginTop: 14, fontSize: 12,
                                                    color: 'var(--danger)' }}>
          <AlertTriangle size={12} style={{ flex: 'none' }} /> {failed}
        </span>
      )}
      <Footer d={d} busy={busy} form={form} setForm={setForm} ways={ways} way={way}
        setWay={chooseWay} setCard={setCard} onPicking={() => setPicking(true)}
        onRefundCard={() => void refundCard()} fresh={fresh} onAction={onAction} />
    </div>
  );
}

const WAIT_TRIES = 10;
const WAIT_STEP = 1500;

/**
 * **Angezeigt wird sofort, gebucht vom Webhook**: nach einer Karten-Zahlung bzw. -Erstattung
 * wird nachgefragt, bis sich die Summe der Zahlungen ändert – höchstens zehnmal.
 */
function useWaitForMoney(paid: string, onPaid: () => void): () => void {
  const [left, setLeft] = useState(0);
  useEffect(() => {
    if (left === 0) return;
    const t = setTimeout(() => { onPaid(); setLeft((n) => n - 1); }, WAIT_STEP);
    return () => clearTimeout(t);
  }, [left, onPaid]);
  useEffect(() => { setLeft(0); }, [paid]);
  return useCallback(() => { setLeft(WAIT_TRIES); onPaid(); }, [onPaid]);
}
