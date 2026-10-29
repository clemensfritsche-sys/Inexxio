'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import { afterPaint, holdPlace } from '@/lib/hold-place';
import type { PaperOut, VoucherEmbed } from '@/types';
import { PaperSheet } from '@/components/erp/beleg/paper-sheet';
import { Documents } from '@/components/erp/beleg/documents';
import { Footer } from '@/components/erp/beleg/footer';
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
  // **Der Abschnitt, in dem zuletzt gearbeitet wurde** – er bleibt nach jeder Handlung, wo er
  // war (`holdPlace`). Gemerkt beim Zeigen und Fokussieren; ein Klick in eine Liste, die an
  // `body` hängt (Portal), hat keinen Abschnitt und lässt den letzten stehen.
  const lastSection = useRef<Element | null>(null);
  const remember = (e: { target: EventTarget }) => {
    const at = (e.target as Element).closest?.('section');
    if (at) lastSection.current = at;
  };
  const run: Send = useCallback(async (body) => {
    const keep = holdPlace(lastSection.current);
    await onAction(body);
    await afterPaint();
    keep();
  }, [onAction]);
  // ►►► **Vorschau → Freigeben**: was ein Papier hinausgibt (Offerte, Rechnung, Storno,
  // Mahnung, Auftragsbestätigung, Quittung), zeigt die Karte vorher – gerechnet von derselben
  // Handlung auf dem Server. Erst «Freigeben» führt sie aus. Welche Verben das sind, sagt der
  // Server (`paper_verbs`). ◄◄◄
  const [papers, setPapers] = useState<{ body: Parameters<Send>[0]; list: PaperOut[] } | null>(null);
  const paperVerbs = voucher.paper_verbs;
  const send: Send = useCallback(async (body) => {
    if (!(paperVerbs ?? []).includes(body.action)) return run(body);
    const shown = await api.previewVoucher(orderObjectId, stepId, body);
    if (!shown.papers?.length) return run(body);
    setPapers({ body, list: shown.papers });
  }, [paperVerbs, run, orderObjectId, stepId]);
  const [shown, setShown] = useState<number | null>(null);
  const [picking, setPicking] = useState(false);
  const [form, setForm] = useState<Form | null>(null);
  const [card, setCard] = useState(false);
  const [picked, setPicked] = useState<string | null>(null);
  const ways = useMemo(() => voucher.ways ?? [], [voucher.ways]);
  // **Die gewählte Antwort ist eine Ableitung** – fällt der Weg weg, steht sie auf dem ersten.
  const way = ways.find((w) => w.key === picked) ?? ways[0] ?? null;
  const wait = useWaitForMoney(d.paid ?? '', onPaid);
  const [failed, setFailed] = useState<string | null>(null);

  // Ein Formular gilt der Lage, in der es geöffnet wurde – ändert sie sich, ist es weg.
  const situation = `${d.stage}:${d.state?.key ?? ''}`;
  useEffect(() => { setForm(null); setCard(false); setRefunding(false); }, [situation]);

  const chooseWay = useCallback((key: string) => {
    setPicked(key);
    setCard(false);
    const next = ways.find((w) => w.key === key);
    // Eine offene Zahlung behält ihren Betrag – nur der Weg ändert sich; führt der neue Weg
    // nicht zu einer Buchung (Karte), ist sie weg.
    setForm((f) => (f?.kind !== 'pay' ? f
      : (next?.action === 'pay' ? { ...f, f: { ...f.f, method: key } } : null)));
  }, [ways]);

  // **«Zurück auf die Karte» sagt, was daraus wurde** (#1013/#1018): ab dem Klick zu,
  // nachgefragt wie bei einer Zahlung (gebucht wird vom Webhook), ein Fehler steht da und
  // gibt den Knopf wieder frei – sonst wäre ein Netzwerkfehler eine Sackgasse.
  const [refunding, setRefunding] = useState(false);
  const refundCard = useCallback(async () => {
    const entry = d.entries.find((e) => e.refundable);
    if (!entry) return;
    setFailed(null);
    setRefunding(true);
    try {
      await api.refundVoucherPayment(orderObjectId, stepId, entry.id);
      wait();
    } catch (e) {
      setRefunding(false);
      setFailed(e instanceof Error ? e.message : String(e));
    }
  }, [d.entries, orderObjectId, stepId, wait]);

  const asked = new Set(d.quotes.map((q) => q.party_object_id));
  const fresh = (d.recipients ?? []).filter((r) => r.object_id != null
    && !asked.has(r.object_id)).length;
  const head = headOf(d, shown);

  return (
    <div className="flex flex-col" style={{ minWidth: 0 }} data-active={active || undefined}
      onPointerDownCapture={remember} onFocusCapture={remember}>
      <Stages d={d} />
      <div style={{ minWidth: 0, ...(d.locked ? { opacity: 0.6 } : {}) }}>
        <Parties d={d} shown={shown} orderObjectId={orderObjectId} stepId={stepId}
          onAction={send} />
        <Goods d={d} busy={busy} onAction={send} />
        <Terms d={d} busy={busy} onAction={send} />
        <Quotes d={d} busy={busy} head={head} picking={picking} onShow={setShown}
          onPicking={setPicking} onAction={send} />
        <Invoice d={d} busy={busy} form={form} setForm={setForm} way={way} card={card}
          setCard={setCard} orderObjectId={orderObjectId} stepId={stepId} onPaid={wait}
          onAction={send} />
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
        onRefundCard={() => void refundCard()} refunding={refunding} fresh={fresh}
        onAction={send} />
      {papers && (
        <PaperSheet papers={papers.list} onCancel={() => setPapers(null)}
          onRelease={async () => { await run(papers.body); setPapers(null); }} />
      )}
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
