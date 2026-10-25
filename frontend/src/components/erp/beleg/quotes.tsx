'use client';

import { useCallback, useEffect, useState } from 'react';
import { Check, CircleSlash, ClipboardList, ExternalLink, Send as SendIcon, X } from 'lucide-react';
import { api } from '@/lib/api';
import { happened } from '@/lib/when';
import { QUOTE_STATE, VOUCHER_STAGE } from '@/lib/modules';
import { ObjId } from '@/components/erp/obj-id';
import { numericInputProps, numericOnly } from '@/components/erp/fields';
import { ACT_H, ActionButton, Amount } from '@/components/erp/module-ui';
import type { VoucherParty, VoucherQuoteOut, VoucherSide } from '@/types';
import { Term } from './terms';
import {
  DOC_FIELD, DocRef, Editable, FieldBox, LABEL, Note, Section, Stacked, may,
} from './shared';
import type { Filled, Send } from './shared';

/** Das Wort der Schwelle an einer Angebotszeile – in beiden Richtungen dasselbe. */
export const AGREE_WORD = 'Offerte annehmen';
/** Was man an einer Angebotszeile tut, wenn die Gegenpartei den Preis nennt. */
const QUOTE_WORD = 'Offerte erfassen';
/** «Absage» – richtungsneutral. */
const DECLINE_WORD = 'Absage';

/**
 * **Der Angebotsspiegel** – je Kandidat eine Zeile: wer, wie viel, in welchem Zustand, und
 * was man damit tun kann (annehmen · Absage; beim Einkauf die Offerte erfassen). Die Zeile,
 * die im Kopf steht, trägt «Im Kopf»; ein Klick auf einen Namen stellt ihn in den Kopf.
 * Nach der Zusage bleibt jede Zeile stehen und nennt ihren Ausgang.
 */
export function Quotes({ d, busy, head, picking, onShow, onPicking, onAction }: {
  d: Filled; busy: boolean;
  /** Wer im Kopf steht (`parties.headOf`). */
  head: VoucherSide | null;
  /** «Partner wählen» ist offen – auch aus der Leiste heraus. */
  picking: boolean;
  onShow: (objectId: number) => void;
  onPicking: (open: boolean) => void;
  onAction: Send;
}) {
  const open = d.stage === VOUCHER_STAGE.offer;
  const asked = new Set(d.quotes.map((q) => q.party_object_id));
  const candidates = open
    ? (d.recipients ?? []).filter((r) => r.object_id != null && !asked.has(r.object_id))
    : [];
  const free = open && may(d, 'party') && d.allowed.length === 0;
  if (!d.quotes.length && !candidates.length && !free) return null;
  const first = d.quotes.map((q) => q.sent_at).filter((x): x is string => !!x).sort()[0];
  const sent = first ? happened(first, d.sent_word) : null;
  return (
    <Section title={d.quotes_title}
      aside={sent && (
        <span data-tip={sent.title}>{sent.text}{open && d.expired ? ' · abgelaufen' : ''}</span>
      )}>
      <div className="flex flex-col" style={{ minWidth: 0 }}>
        {d.quotes.map((q) => (
          <QuoteRow key={q.id} q={q} d={d} busy={busy} onAction={onAction} />
        ))}
        {candidates.map((r) => (
          <Candidate key={r.object_id} d={d} side={r} busy={busy}
            inHead={head?.object_id === r.object_id}
            onShow={() => onShow(r.object_id as number)} onAction={onAction} />
        ))}
        {free && <PickParty d={d} open={picking} onOpen={onPicking} onAction={onAction} />}
      </div>
    </Section>
  );
}

/** Die Haarlinie, die eine Zeile schliesst. */
const ROW = { padding: '12px 0 14px', borderBottom: '1px solid var(--border-1)' } as const;

/** «Im Kopf» – die Zeile, deren Anschrift der Belegkopf gerade zeigt. */
function InHead() {
  return <span style={{ ...LABEL, color: 'var(--accent-ink)', flex: 'none' }}>Im Kopf</span>;
}

/**
 * **Ein Kandidat, dem noch nichts hinausging** – Name mit Nummer, «Noch nicht angeboten»;
 * eine frei gewählte Partei lässt sich wieder wegnehmen (`unask`), eine aus der Definition
 * nicht – die Definition ist die Vorlage.
 */
function Candidate({ d, side, busy, inHead, onShow, onAction }: {
  d: Filled; side: VoucherSide; busy: boolean; inHead: boolean;
  onShow: () => void; onAction: Send;
}) {
  const number = side.object_id as number;
  const removable = may(d, 'unask') && !d.allowed.some((p) => p.object_id === number);
  return (
    <div className="flex flex-wrap items-baseline" style={{ ...ROW, gap: '4px 10px', minWidth: 0 }}>
      <span className="flex items-baseline" style={{ gap: 8, flex: '1 1 190px', minWidth: 0 }}>
        <button type="button" onClick={onShow} className="truncate"
          data-tip="Im Kopf zeigen" style={{ ...DOC_FIELD, fontSize: 13, cursor: 'pointer',
                                             minWidth: 0, textAlign: 'left' }}>
          {side.name || number}
        </button>
        <span style={{ flex: 'none' }}><ObjId value={number} /></span>
      </span>
      {inHead && <InHead />}
      <span style={{ ...LABEL, flex: 'none' }}>
        {d.we_quote ? 'Noch nicht angeboten' : 'Noch nicht angefragt'}
      </span>
      {removable && (
        <ActionButton icon={X} label="Wieder wegnehmen" tone="danger" height={ACT_H.row} square
          disabled={busy} onClick={() => void onAction({ action: 'unask', party: number })} />
      )}
    </div>
  );
}

/**
 * **«+ Partner wählen»** – nur wo die Definition niemanden nennt. Wählen ist nicht
 * anbieten: `party` hält fest, wen der Beleg betrifft; hinaus geht er mit der Leiste.
 */
function PickParty({ d, open, onOpen, onAction }: {
  d: Filled; open: boolean; onOpen: (open: boolean) => void; onAction: Send;
}) {
  const find = useCallback((q: string) => api.searchPeople(q).catch(() => []), []);
  return (
    <div style={{ paddingTop: 12 }}>
      <DocRef<VoucherParty> on text={`+ ${d.party_word} wählen`}
        placeholder={`${d.party_word} suchen`} tip={`${d.party_word} wählen – wählen ist nicht anbieten`}
        face={{ fontSize: 13, color: 'var(--accent-ink)' }}
        value={null} selected={null} find={find} open={open} onOpen={onOpen}
        onChange={(_n, option) => {
          if (option) void onAction({ action: 'party', party: option.object_id });
        }} />
    </div>
  );
}

/**
 * **Der Zustand einer Angebotszeile als Wort** – vor und nach der Entscheidung bedeutet
 * dasselbe Wort Verschiedenes, darum nimmt sie die Entscheidung als zweite Angabe.
 */
function quoteLook(state: string, decided: boolean): { label: string; color: string } {
  if (state === QUOTE_STATE.chosen) return { label: 'Zugesagt', color: 'var(--success)' };
  if (state === QUOTE_STATE.declined) return { label: 'Abgesagt', color: 'var(--danger)' };
  if (state === QUOTE_STATE.quoted) {
    return decided ? { label: 'Unterlegen', color: 'var(--fg-4)' }
      : { label: 'Offeriert', color: 'var(--warning)' };
  }
  return { label: decided ? 'Unbeantwortet' : 'Angefragt', color: 'var(--fg-4)' };
}

/**
 * **Eine Angebotszeile** – Name mit Nummer, ihr Ausgang in einem Wort (oder der Moment
 * der Annahme), der Betrag zuletzt. Abgesagt ist abgesagt: kein Preis mehr an der Zeile.
 */
function QuoteRow({ q, d, busy, onAction }: {
  q: VoucherQuoteOut; d: Filled; busy: boolean; onAction: Send;
}) {
  const decided = d.stage !== VOUCHER_STAGE.offer;
  const look = quoteLook(q.state, decided);
  const declined = q.state === QUOTE_STATE.declined;
  const chosen = q.state === QUOTE_STATE.chosen;
  const taken = chosen && q.agreed_at ? happened(q.agreed_at, d.taken_word) : null;
  const word = !taken && (decided || declined || q.amount == null) ? look.label : null;
  return (
    <div className="flex flex-col" style={{
      ...ROW, gap: 10, minWidth: 0, opacity: decided && !chosen ? 0.6 : 1,
    }}>
      <div className="flex flex-wrap items-baseline" style={{ gap: '4px 10px', minWidth: 0 }}>
        <span className="flex items-baseline" style={{ gap: 8, flex: '1 1 190px', minWidth: 0 }}>
          <span className="truncate" style={{ fontSize: 13, minWidth: 0 }}>
            {q.party_name || q.party_object_id}
          </span>
          <span style={{ flex: 'none' }}><ObjId value={q.party_object_id} /></span>
        </span>
        {taken && <Note tip={taken.title} color="var(--success)">{taken.text}</Note>}
        {word && <span style={{ ...LABEL, color: look.color, flex: 'none' }}>{word}</span>}
        {q.amount != null && !declined && (
          <Amount value={q.amount} currency={d.currency} decimals={d.currency_decimals}
            size={15} weight={400} />
        )}
      </div>
      <Reference q={q} />
      {!decided && !declined && !chosen && (
        <QuoteWork q={q} d={d} busy={busy} onAction={onAction} />
      )}
    </div>
  );
}

/**
 * **Wie man bei ihm bestellt und was er uns nannte** – die Bestellangabe aus der Definition
 * (`ref`), seine Referenz bzw. Bestellnummer und der Link zur Bestellung.
 */
function Reference({ q }: { q: VoucherQuoteOut }) {
  if (!q.ref && !q.reference && !q.link) return null;
  return (
    <div className="flex flex-wrap items-baseline" style={{ gap: '2px 12px', minWidth: 0 }}>
      {q.ref && (
        <Note tip="Wie man bei ihm bestellt – aus der Definition">
          <ClipboardList size={11} style={{ flex: 'none' }} /> {q.ref}
        </Note>
      )}
      {q.reference && <Note tip="Seine Referenz bzw. Bestellnummer">Ihre Referenz {q.reference}</Note>}
      {q.link && (
        <a href={q.link} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center" style={{
            gap: 4, fontSize: 11.5, color: 'var(--accent-ink)', textDecoration: 'none',
            borderBottom: '1px solid var(--accent)',
          }}>
          {hostOf(q.link)} · Bestelldetails <ExternalLink size={10} />
        </a>
      )}
    </div>
  );
}

function hostOf(link: string): string {
  try { return new URL(link).host.replace(/^www\./, ''); } catch { return 'Link'; }
}

/**
 * **Was man an einer offenen Zeile tut** – wo die Gegenpartei den Preis nennt, wird ihre
 * Offerte im grauen Kasten erfasst (Betrag, Fristen, ihre Referenz, Link); annehmen geht,
 * sobald ein Preis dasteht. Ob es geht, sagt `can`; was noch nicht geht, nennt den Grund.
 */
function QuoteWork({ q, d, busy, onAction }: {
  q: VoucherQuoteOut; d: Filled; busy: boolean; onAction: Send;
}) {
  const [f, setF] = useState(() => quoteDraft(q));
  const key = JSON.stringify(quoteDraft(q));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { setF(quoteDraft(q)); }, [key]);
  const canQuote = may(d, 'quote') && !d.we_quote;
  const canDecline = may(d, 'decline');
  const priced = q.amount != null;
  // **Annehmen geht nur, solange die Offerte gilt** – sonst gesperrt, mit dem Grund.
  const agreeWhy = may(d, 'agree') ? null : agreeProblem(d);
  const showAgree = priced && (may(d, 'agree') || agreeWhy !== null);
  const sendQuote = () => void onAction({
    action: 'quote', party: q.party_object_id, amount: f.amount,
    payment_days: f.pay === '' ? null : Number(f.pay),
    lead_days: f.lead === '' ? null : Number(f.lead),
    reference: f.reference.trim() || null, link: f.link.trim() || null,
  });
  if (!canQuote && !showAgree && !canDecline) return null;
  return (
    <>
      {canQuote && <QuoteForm d={d} f={f} setF={setF} />}
      <div className="flex items-center justify-end" style={{ gap: 8, minWidth: 0 }}>
        {showAgree && (
          <button type="button" className="erp-actbtn erp-actbtn-primary"
            disabled={busy || !!agreeWhy} style={{ height: ACT_H.main, fontSize: 12.5 }}
            {...(agreeWhy ? { 'data-tip': agreeWhy } : {})}
            onClick={() => void onAction({ action: 'agree', party: q.party_object_id })}>
            <Check size={14} /> {AGREE_WORD}
          </button>
        )}
        {canQuote && (priced ? (
          <ActionButton icon={SendIcon} label={QUOTE_WORD} tone="primary" height={ACT_H.main}
            square disabled={busy || f.amount.trim() === ''} onClick={sendQuote} />
        ) : (
          <button type="button" className="erp-actbtn erp-actbtn-primary"
            disabled={busy || f.amount.trim() === ''} style={{ height: ACT_H.main, fontSize: 12.5 }}
            {...(f.amount.trim() === '' ? { 'data-tip': 'Erst den Betrag seiner Offerte eintragen' } : {})}
            onClick={sendQuote}>
            <SendIcon size={14} /> {QUOTE_WORD}
          </button>
        ))}
        {canDecline && (
          <ActionButton icon={CircleSlash} label={DECLINE_WORD} tone="danger" height={ACT_H.main}
            square disabled={busy}
            onClick={() => void onAction({ action: 'decline', party: q.party_object_id })} />
        )}
      </div>
    </>
  );
}

/** Warum «Offerte annehmen» gerade nicht geht – derselbe Grund, aus dem `can` es weglässt. */
function agreeProblem(d: Filled): string | null {
  if (d.locked) return d.locked;
  if (d.expired) return 'Die Offerte ist abgelaufen – erst erneut anbieten, dann annehmen.';
  if (d.changed) return 'Die gesendete Offerte ist überholt – erst erneut anbieten.';
  return null;
}

type QuoteDraft = { amount: string; pay: string; lead: string; reference: string; link: string };

function quoteDraft(q: VoucherQuoteOut): QuoteDraft {
  return {
    amount: q.amount ?? '', pay: q.payment_days == null ? '' : String(q.payment_days),
    lead: q.lead_days == null ? '' : String(q.lead_days),
    reference: q.reference ?? '', link: q.link ?? '',
  };
}

/** Der graue Kasten: Betrag · Zahlungsfrist · Lieferfrist, darunter Referenz und Link. */
function QuoteForm({ d, f, setF }: {
  d: Filled; f: QuoteDraft; setF: (fn: (x: QuoteDraft) => QuoteDraft) => void;
}) {
  const set = (patch: Partial<QuoteDraft>) => setF((x) => ({ ...x, ...patch }));
  return (
    <FieldBox>
      <div className="flex flex-wrap items-end" style={{ gap: '8px 18px', minWidth: 0 }}>
        <Stacked label="Betrag">
          <Editable missing={f.amount.trim() === ''} title="Betrag seiner Offerte">
            <Amount currency={d.currency} size={13}>
              <input {...numericInputProps} value={f.amount} aria-label="Betrag"
                onChange={(e) => set({ amount: numericOnly(e.target.value,
                                                           { decimals: d.currency_decimals }) })}
                style={{ ...DOC_FIELD, width: 92, textAlign: 'right', fontSize: 13,
                         fontVariantNumeric: 'tabular-nums' }} />
            </Amount>
          </Editable>
        </Stacked>
        <Term label={d.payment_term_label} on value={f.pay} terms={d.payment_terms ?? []}
          freeMin={d.term_free_min} freeLabel={d.term_free_label}
          onChange={(pay) => set({ pay })} />
        <Term label={d.lead_term_label} on value={f.lead} terms={d.lead_terms ?? []}
          freeMin={d.term_free_min} freeLabel={d.term_free_label}
          onChange={(lead) => set({ lead })} />
      </div>
      <div className="flex flex-wrap items-end" style={{ gap: '8px 18px', minWidth: 0 }}>
        <Stacked label="Ihre Referenz">
          <Editable title="Seine Referenz bzw. Bestellnummer">
            <input value={f.reference} aria-label="Ihre Referenz" placeholder="—"
              onChange={(e) => set({ reference: e.target.value })}
              style={{ ...DOC_FIELD, width: 150, fontSize: 13 }} />
          </Editable>
        </Stacked>
        <Stacked label="Link zur Bestellung">
          <Editable title="Bei einem Online-Kauf: der Link zur Bestellung">
            <input value={f.link} aria-label="Link zur Bestellung" placeholder="—"
              onChange={(e) => set({ link: e.target.value })}
              style={{ ...DOC_FIELD, width: 190, fontSize: 13 }} />
          </Editable>
        </Stacked>
      </div>
    </FieldBox>
  );
}
