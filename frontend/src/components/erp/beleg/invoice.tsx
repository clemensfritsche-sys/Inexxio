'use client';

import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { AlertTriangle, Loader2, RotateCcw, X } from 'lucide-react';
import { api, attachmentUrl } from '@/lib/api';
import { TONE } from '@/lib/status-tone';
import { day, when } from '@/lib/when';
import { VOUCHER_STAGE } from '@/lib/modules';
import { PayOnline } from '@/components/erp/pay-online';
import { PhotoShot } from '@/components/erp/photo-capture';
import { FileUpload } from '@/components/erp/file-upload';
import { Segmented, inputCls, Label, numericInputProps, numericOnly } from '@/components/erp/fields';
import { ACT_H, ActionButton, Amount, FIELD_GAP, LedgerRow, Steady } from '@/components/erp/module-ui';
import type { TransferInfo } from '@/types';
import { CASH, TRANSFER, needsIban, startForm, taxed } from './forms';
import type { Form } from './forms';
import { FieldBox, LABEL, Section, Stacked, may, unsigned } from './shared';
import type { Filled, Send } from './shared';

type Entry = Filled['entries'][number];
type Way = NonNullable<Filled['ways']>[number];

/**
 * ►►► **Der Abschnitt «Rechnung» – Rechnung, Geld, Saldo in EINEM Abschnitt.** ◄◄◄
 *
 * Die Rechnung (eine je Modul, sie IST der Beleg), die Gutschrift aus dem Storno, die
 * Abweichung einer Lieferantenrechnung, jede Geld-Zeile (leise «falsch erfasst?»), der
 * Saldo – und die Entscheidungen, die er verlangt (ausbuchen · erstatten · als Trinkgeld
 * behalten · so annehmen · Ausfuhrnachweis). Erfasst wird im grauen Kasten, abgeschickt
 * in der Leiste.
 */
export function Invoice({ d, busy, form, setForm, way, card, setCard, orderObjectId, stepId,
                          onPaid, onAction }: {
  d: Filled; busy: boolean; form: Form | null; setForm: (f: Form | null) => void;
  way: Way | null; card: boolean; setCard: (open: boolean) => void;
  orderObjectId: number; stepId: number; onPaid: () => void; onAction: Send;
}) {
  const invoice = d.invoice ?? null;
  if (!invoice && form?.kind !== 'bill') return null;
  const quiet = !form && !card;
  return (
    <Section title={d.invoice_title}>
      <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
        {!invoice && <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>Nichts berechnet</span>}
        {invoice && <InvoiceRow d={d} invoice={invoice} />}
        {invoice && d.credit_number && <CreditRow d={d} invoice={invoice} />}
        <Deviation d={d} busy={busy} form={form} setForm={setForm} />
        {d.entries.map((e) => (
          <EntryRow key={e.id} d={d} e={e} busy={busy} onAction={onAction} />
        ))}
        <ExportProof d={d} busy={busy} form={form} setForm={setForm} />
        {invoice && <Balance d={d} busy={busy} form={form} setForm={setForm} onAction={onAction} />}
        {form && ['pay', 'refund', 'bill'].includes(form.kind) && (
          <EntryForm d={d} form={form} setForm={setForm} />
        )}
        {/* Die Auskunft zur Überweisung nur, solange Geld zu uns kommen soll. */}
        {quiet && way?.info && (may(d, 'pay') || may(d, 'pay_online')) && (
          <Transfer orderObjectId={orderObjectId} stepId={stepId} />
        )}
        {card && (
          <PayOnline orderObjectId={orderObjectId} stepId={stepId}
            prepare={api.prepareVoucherPayment} label={d.pay_online_word}
            onDone={() => { setCard(false); onPaid(); }} onClose={() => setCard(false)} />
        )}
      </div>
    </Section>
  );
}

/** Die Farbe eines Zustands – aus dem Ton des Servers. */
function toneOf(tone?: string | null): string | undefined {
  return TONE[tone as keyof typeof TONE]?.color;
}

/**
 * **DIE Rechnung** – eine Zeile in der Grammatik jeder Geld-Zeile: Nummer · was auf dem
 * Papier steht · Fälligkeit · Betrag (in der Farbe ihres Zustands, das Wort im Hover).
 */
function InvoiceRow({ d, invoice }: { d: Filled; invoice: NonNullable<Filled['invoice']> }) {
  const cancelled = d.stage === VOUCHER_STAGE.cancelled;
  const meta: ReactNode[] = [];
  if (d.minus) meta.push('Gutschrift');
  if (!d.we_quote && invoice.billed_on) meta.push(`vom ${day(invoice.billed_on)}`);
  if (d.party_uid) meta.push(d.party_uid);
  if (cancelled) meta.push(d.cancelled_word);
  const stamp = invoice.due_on
    ? `${d.minus ? 'zu erstatten bis' : 'fällig'} ${when(invoice.due_on)}`
    : when(invoice.billed_on);
  return (
    <LedgerRow ident={invoice.number || d.invoice_title}
      meta={(
        <>
          {meta.join(' · ')}
          {d.original && (
            <>{meta.length ? ' · ' : ''}<a href={attachmentUrl(d.original)} target="_blank" rel="noopener noreferrer"
              style={{ color: 'var(--accent-ink)' }}>Beleg</a></>
          )}
        </>
      )}
      date={stamp}
      tip={[invoice.state_label, `${d.invoice_title} ${day(invoice.billed_on)}`,
            invoice.due_on ? `fällig ${day(invoice.due_on)}` : '',
            invoice.service_date ? `${d.service_date_label} ${day(invoice.service_date)}` : '']
        .filter(Boolean).join(' · ')}
      amount={(
        <Amount value={invoice.amount} currency={d.currency} decimals={d.currency_decimals}
          size={15} weight={400}
          color={cancelled ? 'var(--fg-3)' : toneOf(invoice.state_tone)} />
      )} />
  );
}

/** **Die Gutschrift aus dem Storno** – eigene Nummer, Bezug auf die Rechnung, von selbst. */
function CreditRow({ d, invoice }: { d: Filled; invoice: NonNullable<Filled['invoice']> }) {
  return (
    <LedgerRow ident={d.credit_number}
      meta={invoice.number ? `Storno zu ${invoice.number}` : 'Storno'}
      date={d.cancelled_on ? when(d.cancelled_on) : undefined}
      tip={d.cancel_note ? `Grund: ${d.cancel_note}` : undefined}
      amount={(
        <Amount value={d.credited ?? invoice.amount} currency={d.currency}
          decimals={d.currency_decimals} size={15} weight={400} color="var(--fg-3)" />
      )} />
  );
}

/**
 * **Die Lieferantenrechnung weicht ab** – die Differenz als Zeile; bezahlt wird erst nach
 * dem Entscheid: so annehmen (mit Grund) oder stornieren. Entschieden bleibt die Zeile als
 * Nachweis stehen.
 */
function Deviation({ d, busy, form, setForm }: {
  d: Filled; busy: boolean; form: Form | null; setForm: (f: Form | null) => void;
}) {
  if (d.deviation_note) {
    return (
      <LedgerRow ident="Abweichung angenommen" meta={`Grund: ${d.deviation_note}`}
        amount={<span />} />
    );
  }
  if (!d.deviation || !d.invoice?.amount) return null;
  const gap = Number(d.deviation);
  const agreed = (Number(d.invoice.amount) - gap).toFixed(d.currency_decimals);
  const sign = gap > 0 ? '+' : '−';
  const open = form?.kind === 'accept';
  return (
    <>
      <LedgerRow ident="Abweichung zur Zusage"
        meta={`zugesagt ${agreed} · in Rechnung ${d.invoice.amount}`}
        amount={(
          <span style={{ color: 'var(--warning)' }}>
            {sign}
            <Amount value={unsigned(d.deviation)} currency={d.currency}
              decimals={d.currency_decimals} size={15} weight={400} color="var(--warning)" />
          </span>
        )} />
      <FieldBox tone="warning">
        <span style={{ fontSize: 12.5, color: 'var(--fg-1)' }}>
          Die Rechnung liegt {unsigned(d.deviation)} {gap > 0 ? 'über' : 'unter'} der
          Zusage. Annehmen (mit Grund) – oder stornieren und eine korrigierte Rechnung verlangen.
        </span>
        {open ? (
          <div className="flex items-end" style={{ gap: FIELD_GAP }}>
            <FormField label="Grund" required grow>
              <input className={inputCls} value={form.f.note ?? ''} autoFocus aria-label="Grund"
                placeholder="z. B. Materialzuschlag"
                onChange={(e) => setForm({ ...form, f: { ...form.f, note: e.target.value } })} />
            </FormField>
            <Cancel onClick={() => setForm(null)} />
          </div>
        ) : may(d, 'accept') && (
          <span>
            <button type="button" className="erp-actbtn erp-actbtn-neutral" disabled={busy}
              style={{ height: ACT_H.main, fontSize: 12.5 }}
              onClick={() => setForm(startForm('accept', d))}>So annehmen …</button>
          </span>
        )}
      </FieldBox>
    </>
  );
}

/** Was eine Geld-Zeile ist – ihr Name kommt aus ihrer Art, nie aus einem Vergleich der Richtung. */
function entryName(e: Entry): string {
  if (e.reverses_id != null) return 'Gegenbuchung';
  if (e.kind === 'writeoff') return 'Ausbuchung';
  if (e.kind === 'tip') return 'Trinkgeld';
  if (Number(e.amount) < 0) return 'Erstattung';
  return e.method_label || e.reference || 'Zahlung';
}

/**
 * **Eine Geld-Zeile** – Art · Vermerk · Zeitpunkt · Betrag. Ein Ereignis der Aussenwelt
 * macht man nicht ungeschehen; ein Tippfehler wird leise als «falsch erfasst?»
 * gegengebucht (`reverse`), genau diese Zeile.
 */
function EntryRow({ d, e, busy, onAction }: { d: Filled; e: Entry; busy: boolean; onAction: Send }) {
  const neg = Number(e.amount) < 0;
  const meta = [
    e.kind === 'writeoff' ? e.reason_label : null,
    neg && e.method_label ? `per ${e.method_label}` : null,
    e.iban ? `an ${e.iban}` : null,
    e.reference && e.reference !== e.method_label ? e.reference : null,
    e.note,
  ].filter(Boolean).join(' · ');
  return (
    <LedgerRow ident={entryName(e)} meta={meta}
      date={when(e.booked_at ?? e.booked_on)}
      tip={e.booked_on ? `Gebucht ${day(e.booked_on)}` : undefined}
      actions={e.reversible ? (
        <ActionButton icon={RotateCcw} label={d.reverse_word} disabled={busy}
          tip="Bucht genau diese Zeile gegen – für einen Tippfehler"
          onClick={() => void onAction({ action: 'reverse', entry: e.id })} />
      ) : undefined}
      amount={(
        <Amount value={neg ? unsigned(e.amount) : e.amount} currency={d.currency}
          decimals={d.currency_decimals} size={15} weight={400}
          color={neg || e.kind !== 'payment' || e.reverses_id != null ? 'var(--fg-3)' : undefined} />
      )} />
  );
}

/**
 * **Der Ausfuhrnachweis** – nur beim Export, nach der Rechnung: ohne ihn gilt 0 % nicht,
 * erledigt ist der Beleg erst damit. Erfasst: die Nummer der Veranlagungsverfügung und das
 * Dokument selbst – **hochgeladen** (PDF oder Bild), denn es kommt vom Zoll per Mail.
 */
function ExportProof({ d, busy, form, setForm }: {
  d: Filled; busy: boolean; form: Form | null; setForm: (f: Form | null) => void;
}) {
  if (!d.export || !d.invoice) return null;
  if (d.export_number) {
    return (
      <LedgerRow ident="Ausfuhrnachweis"
        meta={(
          <>Veranlagungsverfügung {d.export_number}
            {d.export_photo && (
              <> · <a href={attachmentUrl(d.export_photo)} target="_blank" rel="noopener noreferrer"
                style={{ color: 'var(--accent-ink)' }}>Dokument</a></>
            )}
          </>
        )}
        amount={<span style={{ ...LABEL, color: 'var(--success)' }}>erfasst</span>} />
    );
  }
  if (d.stage === VOUCHER_STAGE.cancelled) return null;
  const open = form?.kind === 'export';
  const set = (patch: Record<string, string>) => form && setForm({ ...form, f: { ...form.f, ...patch } });
  return (
    <FieldBox tone="warning">
      <span style={{ fontSize: 12.5, color: 'var(--fg-1)' }}>
        <strong style={{ fontWeight: 600 }}>Ausfuhrnachweis fehlt.</strong> Ohne die
        Veranlagungsverfügung des Zolls gilt 0 % nicht – der Beleg ist erst damit erledigt.
      </span>
      {open ? (
        <div className="flex flex-wrap items-start" style={{ gap: FIELD_GAP }}>
          <FormField label="Nr. der Veranlagungsverfügung" required>
            <input className={inputCls} value={form.f.reference ?? ''} autoFocus
              aria-label="Nr. der Veranlagungsverfügung"
              onChange={(e) => set({ reference: e.target.value })} />
          </FormField>
          <FormField label="Veranlagungsverfügung" required>
            <FileUpload value={form.f.photo ? { url: form.f.photo, name: form.f.name ?? '' } : null}
              onChange={(file) => set(file
                ? { photo: file.url, original: String(file.id), name: file.name }
                : { photo: '', original: '', name: '' })} />
          </FormField>
          <Cancel onClick={() => setForm(null)} />
        </div>
      ) : may(d, 'export') && (
        <span>
          <button type="button" className="erp-actbtn erp-actbtn-neutral" disabled={busy}
            style={{ height: ACT_H.main, fontSize: 12.5 }}
            onClick={() => setForm(startForm('export', d))}>Ausfuhrnachweis erfassen</button>
        </span>
      )}
    </FieldBox>
  );
}

/**
 * **Der Saldo – eine Zahl, und ihre Farbe ist die Aussage**; darunter, was er verlangt:
 * zu wenig → offen lassen oder ausbuchen, zu viel → erstatten oder als Trinkgeld behalten.
 */
function Balance({ d, busy, form, setForm, onAction }: {
  d: Filled; busy: boolean; form: Form | null; setForm: (f: Form | null) => void;
  onAction: Send;
}) {
  if (d.open == null) return null;
  const color = toneOf(d.open_state_tone);
  const settled = d.open_state === 'settled';
  const credit = d.open_state === 'overpaid';
  const word = settled || credit
    ? d.open_state_label
    : (d.minus ? 'Wir erstatten' : 'Offen');
  const short = d.state?.key === 'short' && may(d, 'writeoff');
  const back = may(d, 'refund') && form?.kind !== 'refund';
  return (
    <div className="flex flex-col" style={{ gap: 8, paddingTop: 8, borderTop: '1px solid var(--border-1)' }}>
      <div className="flex items-baseline" style={{ gap: 10 }}>
        <span style={settled || credit || d.minus
          ? { ...LABEL, flex: 1, color: color ?? 'var(--accent-ink)' }
          : { font: '700 13px var(--font-body)', flex: 1 }}>{word}</span>
        <Amount value={unsigned(d.open)} currency={d.currency} decimals={d.currency_decimals}
          size={15} weight={600} color={color} tip={d.open_state_label ?? undefined} />
      </div>
      {short && form?.kind !== 'writeoff' && (
        <Decision text={`Es fehlen ${unsigned(d.open)} ${d.currency}. Der Rest bleibt offen und `
          + 'kommt in den Mahnlauf – oder Sie buchen ihn aus (Grund Pflicht).'}>
          <DecisionButton primary busy={busy} label={d.write_off_word}
            onClick={() => setForm(startForm('writeoff', d))} />
        </Decision>
      )}
      {(back || may(d, 'tip')) && (
        <Decision text={d.stage === VOUCHER_STAGE.cancelled
          ? `${unsigned(d.open)} ${d.currency} gehen zurück – dorthin, woher das Geld kam.`
          : `${unsigned(d.open)} ${d.currency} zu viel bezahlt – erstatten, dorthin, woher das `
            + `Geld kam${may(d, 'tip') ? ', oder als Trinkgeld behalten' : ''}.`}>
          {back && (
            <DecisionButton primary busy={busy} label={d.refund_word}
              onClick={() => setForm(startForm('refund', d))} />
          )}
          {may(d, 'tip') && (
            <DecisionButton busy={busy} label={d.tip_word}
              onClick={() => void onAction({ action: 'tip' })} />
          )}
        </Decision>
      )}
    </div>
  );
}

function Decision({ text, children }: { text: string; children: ReactNode }) {
  return (
    <div className="flex flex-col" style={{ gap: 8 }}>
      <span style={{ fontSize: 12.5, color: 'var(--fg-2)' }}>{text}</span>
      <div className="flex flex-wrap" style={{ gap: 8 }}>{children}</div>
    </div>
  );
}

function DecisionButton({ primary, busy, label, onClick }: {
  primary?: boolean; busy: boolean; label: string; onClick: () => void;
}) {
  return (
    <button type="button" disabled={busy} onClick={onClick}
      className={`erp-actbtn ${primary ? 'erp-actbtn-primary' : 'erp-actbtn-neutral'}`}
      style={{ height: ACT_H.main, fontSize: 12.5 }}>{label}</button>
  );
}

/** **Abbrechen** – leise, als Quadrat; abgeschickt wird in der Leiste. */
function Cancel({ onClick }: { onClick: () => void }) {
  return (
    <span className="inline-flex" style={{ alignSelf: 'flex-start' }}>
      <Steady>
        <ActionButton icon={X} label="Abbrechen" height={ACT_H.main} square onClick={onClick} />
      </Steady>
    </span>
  );
}

/** **Eine Frage im Formular** – Beschriftung über dem Feld, Pflicht wie im Dienst. */
function FormField({ label, required, grow, children }: {
  label: string; required?: boolean; grow?: boolean; children: ReactNode;
}) {
  return (
    <div className="flex flex-col" style={{ minWidth: 0, ...(grow ? { flex: '1 1 180px' } : {}) }}>
      <Label required={required}>{label}</Label>
      {children}
    </div>
  );
}

/**
 * **Eine Geld-Zeile bzw. die Lieferantenrechnung erfassen** – im grauen Kasten, der
 * Betrag vorbelegt; abgeschickt wird in der Leiste («Buchen»), abgebrochen hier.
 */
function EntryForm({ d, form, setForm }: {
  d: Filled; form: Form; setForm: (f: Form | null) => void;
}) {
  const set = (patch: Record<string, string>) => setForm({ ...form, f: { ...form.f, ...patch } });
  const title = form.kind === 'bill' ? d.charge_word
    : (form.kind === 'refund' ? d.refund_word : d.payment_word);
  return (
    <FieldBox>
      <div className="flex flex-wrap items-end" style={{ gap: FIELD_GAP, minWidth: 0 }}>
        <FormField label={title}>
          <input {...numericInputProps} className={inputCls} value={form.f.amount ?? ''} autoFocus
            aria-label="Betrag" style={{ width: 130, textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}
            onChange={(e) => set({ amount: numericOnly(e.target.value, { decimals: d.currency_decimals }) })} />
        </FormField>
        {form.kind === 'refund' && (
          <Segmented value={form.f.method} onChange={(method) => set({ method })}
            options={[{ value: CASH, label: 'Bar' }, { value: TRANSFER, label: 'Überweisung' }]} />
        )}
        {form.kind === 'bill' && <BillFields d={d} form={form} set={set} />}
        {/* **Abbrechen steht in der Zeile des Betrags** (Chrome-Test) – allein darunter
            war es ein «×» in einem leeren Kasten. */}
        <span className="inline-flex" style={{ marginLeft: 'auto' }}>
          <Cancel onClick={() => setForm(null)} />
        </span>
      </div>
      {form.kind === 'bill' && <BillPaper d={d} form={form} set={set} />}
      {needsIban(form, d) && (
        <FormField label="IBAN" required grow>
          <input className={inputCls} value={form.f.iban ?? ''} aria-label="IBAN"
            placeholder="CH00 0000 0000 0000 0000 0" onChange={(e) => set({ iban: e.target.value })} />
          <span style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 4 }}>
            Das Geld geht dorthin zurück, woher es kam – kennt das System kein Konto, wird die
            IBAN von Hand eingetragen.
          </span>
        </FormField>
      )}
    </FieldBox>
  );
}

/** Die Lieferantenrechnung, wie sie auf dem Papier steht: Satz und Rechnungsnummer. */
function BillFields({ d, form, set }: {
  d: Filled; form: Form; set: (patch: Record<string, string>) => void;
}) {
  return (
    <>
      <FormField label={d.vat_label}>
        <select className={inputCls} value={form.f.vat} aria-label={d.vat_label}
          onChange={(e) => set({ vat: e.target.value })}>
          {(d.vat_rates ?? []).map((v) => (
            <option key={v.key} value={v.key}>{v.label} ({v.rate} %)</option>
          ))}
        </select>
      </FormField>
      <FormField label={d.ref_label ?? 'Rechnungsnummer'} required grow>
        <input className={inputCls} value={form.f.reference ?? ''} aria-label={d.ref_label ?? 'Rechnungsnummer'}
          onChange={(e) => set({ reference: e.target.value })} />
      </FormField>
    </>
  );
}

/**
 * **Was es für den Vorsteuerabzug braucht** – Rechnungsdatum, MWST-Nr. des Lieferanten
 * (sobald Steuer darauf steht) und das Original als Foto (Pflicht, zehn Jahre aufbewahrt).
 */
function BillPaper({ d, form, set }: {
  d: Filled; form: Form; set: (patch: Record<string, string>) => void;
}) {
  return (
    <>
      <div className="flex flex-wrap items-end" style={{ gap: FIELD_GAP, minWidth: 0 }}>
        <FormField label="Rechnungsdatum" required grow>
          <input className={inputCls} value={form.f.billed_on ?? ''} placeholder="TT.MM.JJJJ"
            aria-label="Rechnungsdatum" onChange={(e) => set({ billed_on: e.target.value })} />
        </FormField>
        <FormField label="MWST-Nr. auf der Rechnung" required={taxed(form, d)} grow>
          <input className={inputCls} value={form.f.party_uid ?? ''} placeholder="CHE-123.456.789 MWST"
            aria-label="MWST-Nr. auf der Rechnung" onChange={(e) => set({ party_uid: e.target.value })} />
        </FormField>
      </div>
      <FormField label="Originalbeleg" required>
        <PhotoShot value={form.f.photo || null}
          onChange={(url, id) => set({ photo: url ?? '', original: url && id != null ? String(id) : '' })} />
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)', marginTop: 4 }}>
          Die Rechnung, wie sie gekommen ist – Pflicht für den Vorsteuerabzug
          und 10 Jahre aufbewahrt.
        </span>
      </FormField>
    </>
  );
}

/** Ein feststehender Wert – Beschriftung darüber, der Grund im Hover. */
function Fixed({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Stacked label={label}>
      <span style={{ fontSize: 13, color: 'var(--fg-1)', width: 'fit-content' }}
        {...(hint ? { 'data-tip': hint } : {})}>{value}</span>
    </Stacked>
  );
}

/**
 * **Wie man diese Rechnung überweist** – Empfänger, IBAN, Referenz und, wo er gilt, die
 * Swiss QR-Rechnung. Eine Auskunft, keine Buchung.
 */
function Transfer({ orderObjectId, stepId }: { orderObjectId: number; stepId: number }) {
  const [info, setInfo] = useState<TransferInfo | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let stale = false;
    void api.voucherTransfer(orderObjectId, stepId)
      .then((r) => { if (!stale) setInfo(r); })
      .catch(() => { if (!stale) setFailed(true); });
    return () => { stale = true; };
  }, [orderObjectId, stepId]);

  if (failed) {
    return (
      <span className="flex items-center" style={{ gap: 6, fontSize: 12, color: 'var(--danger)' }}>
        <AlertTriangle size={12} /> Die Angaben zur Überweisung sind gerade nicht abrufbar.
      </span>
    );
  }
  if (!info) {
    return (
      <span className="flex items-center" style={{ gap: 6, fontSize: 12, color: 'var(--fg-3)' }}>
        <Loader2 size={12} className="animate-spin" /> Einen Moment …
      </span>
    );
  }
  return (
    <div className="flex flex-wrap" style={{
      gap: 14, padding: 11, borderRadius: 'var(--r-md)', border: '1px solid var(--border-1)',
      minWidth: 0,
    }}>
      <div className="flex flex-col" style={{ gap: 4, flex: '1 1 200px', minWidth: 0 }}>
        <Fixed label="Empfänger" value={info.creditor} />
        <Fixed label="IBAN" value={info.iban ?? '—'} />
        <Fixed label="Referenz" value={info.reference || '—'}
          hint={`Aus der Rechnungsnummer ${info.invoice} abgeleitet (ISO 11649)`} />
        <Fixed label="Betrag" value={`${info.amount} ${info.currency}`} />
      </div>
      {info.qr ? (
        <div style={{ flex: '0 0 168px', width: 168 }} dangerouslySetInnerHTML={{ __html: info.qr }} />
      ) : (
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)', flex: '1 1 160px' }}>{info.problem}</span>
      )}
    </div>
  );
}
