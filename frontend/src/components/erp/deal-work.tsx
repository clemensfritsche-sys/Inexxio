'use client';

import { useCallback, useState } from 'react';
import {
  Check, ChevronDown, CircleSlash, FileText, Lock, Send, Trash2, Undo2, Wallet,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { DealEmbed, DealParty, DealQuote } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import {
  Label, ReadField, inputCls, numericInputProps, numericOnly,
} from '@/components/erp/fields';
import { DEAL_STAGE, QUOTE_STATE, dealDirection } from '@/lib/modules';
import { formatAmount, localDate } from '@/lib/utils';

/**
 * ►►► **Der Geldvorgang an der Ausführungsstelle — drei Zeilen.** ◄◄◄
 *
 * `Angebot → Auftrag → Rechnung & Zahlung`, in **beide** Richtungen dieselben. Was
 * Einnahme von Ausgabe unterscheidet, **reist fertig mit** (`label`, `stages[].label/verb`,
 * `party_word`, `ask_verb`, `charge_word`) – die Karte braucht dafür **kein einziges `if`
 * auf die Richtung**; ein Wächter zählt sie.
 *
 * ## Zwei Stufen, und die dritte Zeile ist KEINE
 *
 * Unumkehrbar sind zwei Dinge: nichts zugesagt · zugesagt. «Abgeschlossen» stand einmal
 * als dritte Stufe da und war genau das Missverständnis – ein **Zustand** in einer Reihe
 * von **Schritten**.
 *
 * Die dritte Zeile ist das **Geld**, und es ist bewusst keine Stufe: eine Zahlung macht
 * aus einem Angebot keine Zusage, sie ist reversibel, und sie darf **vor** der Erfüllung
 * stehen (Vorauszahlung) wie danach (Zahlungsziel). Wer sie als dritte Stufe führte,
 * hätte für die Vorauszahlung ein `if`.
 *
 * ## Ein Vorgang hat zwei Parteien
 *
 * Der **Angebotsspiegel** (`quotes`) ist der Kern der ersten Zeile: wir fragen an bzw.
 * bieten an, die Gegenpartei nennt ihren Preis oder sagt ab, wir geben den Zuschlag.
 * Dieselbe Karte sieht die Gegenpartei – nur ihre eigene Zeile, keine Zahl über Forderung
 * und Geld, und was sie **tun** darf, sagt `can`. Diese Komponente weiss darum nicht, was
 * eine Gegenpartei ist; sie fragt `may(...)`.
 *
 * ## Eine primäre Handlung statt drei gleichwertiger Knöpfe
 *
 * Gemeldet war: «kann Zahlungen erfassen, obwohl noch keine Rechnung erstellt worden ist
 * – ich check die Logik nicht». Die Freiheit bleibt (jede Reihenfolge muss abbildbar
 * sein), aber der **nächste** Schritt steht vorn: der Server sagt ihn (`next_charge` ↔
 * `next_payment`), alles Übrige liegt unter «Weitere».
 */
type Filled = Omit<DealEmbed, 'stages' | 'entries' | 'allowed' | 'can' | 'quotes' | 'lines'> & {
  stages: NonNullable<DealEmbed['stages']>;
  entries: NonNullable<DealEmbed['entries']>;
  allowed: NonNullable<DealEmbed['allowed']>;
  can: NonNullable<DealEmbed['can']>;
  quotes: NonNullable<DealEmbed['quotes']>;
  lines: NonNullable<DealEmbed['lines']>;
};

type Action = { action: string } & Record<string, unknown>;

/** **Darf man das hier?** – die einzige Frage über Rechte, die diese Komponente stellt. */
function may(d: Filled, active: boolean, action: string): boolean {
  return active && d.can.includes(action);
}

export function DealWork({ deal, busy, active = true, onAction, children }: {
  deal: DealEmbed;
  busy?: boolean;
  /**
   * **Ist dieses Modul an der Reihe?**
   *
   * Der Vorgang steht in **jedem** Zustand da – was in ihm passiert ist, gehört zum
   * Modul und nicht zu dem Moment, in dem man es bedienen darf. Abhängig ist allein, ob
   * **gehandelt** werden kann.
   */
  active?: boolean;
  onAction: (body: Action) => void;
  /** Die Bestätigung, die das Modul abschliesst – **kein Scan** (es tut nichts am Stück). */
  children?: React.ReactNode;
}) {
  // Die Listen sind serverseitig immer gesetzt; der generierte Typ lässt sie optional,
  // weil Pydantic-Defaults dort so ankommen. Einmal hier vereinheitlicht statt an jeder
  // Lesestelle ein `?? []`.
  const d: Filled = {
    ...deal, stages: deal.stages ?? [], entries: deal.entries ?? [],
    allowed: deal.allowed ?? [], can: deal.can ?? [],
    quotes: deal.quotes ?? [], lines: deal.lines ?? [],
  };
  const cancelled = d.stage === DEAL_STAGE.cancelled;
  const agreed = d.stage !== DEAL_STAGE.offer;

  return (
    <div className="flex flex-col">
      <Head d={d} />
      <Goods d={d} />

      <Row first label={d.stages[0]?.label ?? ''} done={!!d.stages[0]?.done}
        active={!!d.stages[0]?.active && !cancelled}>
        <Offer d={d} busy={busy} active={active && !!d.stages[0]?.active}
          onAction={onAction} />
      </Row>

      <Row label={d.stages[1]?.label ?? ''} done={agreed && !cancelled}
        active={!!d.stages[1]?.active && !cancelled}>
        {agreed && <Agreed d={d} busy={busy} active={active} onAction={onAction}>
          {children}
        </Agreed>}
      </Row>

      {/* **Das Geld – eine Zeile, keine Stufe.** Sie steht dort, wo man sie erwartet
          (dritte Position), und ist ab der Zusage bedienbar; die Kette darüber sagt
          weiterhin nur, was **zugesagt** ist. */}
      <Row last label={d.money_label} done={!!d.settled && !!Number(d.charged ?? 0)}
        active={agreed && !cancelled}>
        {agreed && <Money d={d} busy={busy} active={active} onAction={onAction} />}
      </Row>

      {cancelled && (
        <div className="flex items-center gap-1.5 mt-1 text-[12.5px]"
          style={{ color: 'var(--danger)' }}>
          <CircleSlash size={13} /> {d.stage_label}
        </div>
      )}
    </div>
  );
}

/**
 * **Eine Zeile der Kette** – Punkt, Linie, Beschriftung, Inhalt.
 *
 * Dieselbe Regel wie die Hauptachse, eine Ebene tiefer: kräftige Linie bis zur offenen
 * Stelle, Haarlinie danach. Ein Bauteil statt dreimal derselbe Aufbau – sonst laufen die
 * drei Zeilen beim ersten Eingriff auseinander.
 */
function Row({ label, done, active, first, last, children }: {
  label: string; done?: boolean; active?: boolean;
  first?: boolean; last?: boolean; children?: React.ReactNode;
}) {
  return (
    <div className="flex gap-2.5">
      <div className="flex flex-col items-center" style={{ width: 14, flex: 'none' }}>
        <span style={{
          width: 10, height: 10, borderRadius: 999, flex: 'none', marginTop: 3,
          background: done ? 'var(--fg-2)' : 'var(--bg-1)',
          border: `${active ? 2 : 1}px solid ${
            done || active ? 'var(--fg-2)' : 'var(--border-2)'}`,
        }} />
        {!last && (
          <div style={{
            flex: 1, width: done ? 2 : 1, minHeight: 14,
            background: done ? 'var(--fg-2)' : 'var(--border-2)',
          }} />
        )}
      </div>
      <div className="flex-1 min-w-0" style={{ paddingBottom: last ? 0 : 12, paddingTop: first ? 0 : 0 }}>
        <span style={{
          font: `${active ? 700 : 600} 12.5px var(--font-body)`,
          color: active ? 'var(--fg-1)' : done ? 'var(--fg-2)' : 'var(--fg-4)',
        }}>{label}</span>
        {children}
      </div>
    </div>
  );
}

/**
 * **In welche Richtung — als SYMBOL, nicht als Dauertext** (#797).
 *
 * Plus und Minus sind die Buchhaltungssprache selbst; ein Wort daneben sagt dieselbe
 * Sache ein zweites Mal und ist bei jeder Karte im Weg. Die Bedeutung steht im Hover –
 * dieselbe Regel wie bei jedem Symbol-Knopf im Haus.
 */
function Head({ d }: { d: Filled }) {
  const dir = dealDirection(d.direction);
  const Icon = dir.icon;
  return (
    <div className="flex items-center gap-2 flex-wrap"
      style={{ marginBottom: 10, paddingBottom: 8, borderBottom: '1px solid var(--border-1)' }}>
      <span data-tip={dir.hint} style={{ color: 'var(--fg-2)', display: 'flex' }}>
        <Icon size={15} />
      </span>
      {d.subject && (
        <span className="text-[12.5px] min-w-0 flex-1" style={{ color: 'var(--fg-2)' }}>
          {d.subject}
        </span>
      )}
      {/* **Die Sperre ist eine Auskunft, keine Warnung.** Sie steht als Eigenschaft
          dieses Moduls da, nicht als Fehler. */}
      {d.prepaid && (
        <span className="flex items-center gap-1 text-[12px]"
          data-tip="Dieses Modul schliesst erst ab, wenn der zugesagte Betrag bezahlt ist."
          style={{ color: 'var(--fg-3)', flex: 'none' }}>
          <Lock size={11} /> Erst zahlen
        </span>
      )}
    </div>
  );
}

/**
 * ►►► **Worum es geht — ABGELEITET, nie getippt.** ◄◄◄
 *
 * Je Artikel, dessen Einzelinstanzen im Auftrag stehen, eine Zeile; mehrere sind der
 * Normalfall. Die **Spezifikation reist mit** – sie beschreibt die Sache, damit die
 * Gegenpartei weiss, worum es geht, und sie wird nicht ausgewählt: eine Spezifikation,
 * die je nach Empfänger anders lautet, ist keine.
 *
 * Sie steht **erst auf Klick**: im Normalfall interessiert die Zeile, nicht das
 * Datenblatt – und bei zwei Artikeln stünden sonst zwölf Werte über dem Angebot.
 */
function Goods({ d }: { d: Filled }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!d.lines.length) return null;
  return (
    <div className="flex flex-col" style={{ marginBottom: 10 }}>
      {d.lines.map((line) => {
        const spec = line.spec ?? [];
        const shown = open === line.article_id;
        return (
          <div key={line.article_id} className="flex flex-col">
            <button type="button" className="flex items-center gap-2 py-1 text-left"
              style={{ background: 'none', border: 0, padding: '4px 0' }}
              aria-expanded={shown}
              onClick={() => setOpen(shown ? null : line.article_id)}>
              <span className="ix-tnum text-[12.5px] font-semibold"
                style={{ color: 'var(--fg-1)', flex: 'none' }}>{line.quantity}×</span>
              <span className="text-[12.5px] truncate" style={{ color: 'var(--fg-1)' }}>
                {line.article_name}
              </span>
              <ObjId value={line.article_object_id} />
              {spec.length > 0 && (
                <ChevronDown size={13} style={{
                  color: 'var(--fg-4)', flex: 'none',
                  transform: shown ? 'rotate(180deg)' : undefined,
                }} />
              )}
            </button>
            {shown && spec.length > 0 && (
              <div className="grid gap-x-4 gap-y-1" style={{
                gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))',
                padding: '2px 0 6px 22px',
              }}>
                {spec.map((f) => (
                  <div key={f.label} className="flex gap-2 text-[12px]">
                    <span style={{ color: 'var(--fg-4)' }}>{f.label}</span>
                    <span style={{ color: 'var(--fg-2)' }}>{f.value}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * ►►► **Der Angebotsspiegel — der Vorgang hat zwei Parteien.** ◄◄◄
 *
 * Wir fragen an bzw. bieten an, die Gegenpartei nennt ihren Preis oder sagt ab, wir geben
 * den Zuschlag. **Eine Liste, auch wenn fast immer einer drinsteht**: n statt 1 – wer
 * vergleichen will, fragt drei, und der Vergleich ist damit kein zweiter Mechanismus.
 *
 * **Steht in der Definition genau eine Gegenpartei, gibt es nichts zu wählen** (#793):
 * dann heisst der Knopf schlicht «Anbieten» bzw. «Anfragen» und fragt nicht nach dem
 * Kunden. Nur wo die Definition **niemanden** nennt, ist die Wahl eine echte Frage.
 */
function Offer({ d, busy, active, onAction }: {
  d: Filled; busy?: boolean; active: boolean; onAction: (body: Action) => void;
}) {
  const [picked, setPicked] = useState<DealParty | null>(null);
  const find = useCallback(
    (q: string) => api.searchDealParties(q).catch(() => []), []);

  const open = d.allowed.filter((a) => !d.quotes.some(
    (q) => q.party_object_id === a.object_id));
  const free = d.allowed.length === 0;

  return (
    <div className="flex flex-col gap-2 mt-1.5">
      {d.quotes.map((q) => (
        <QuoteRow key={q.party_object_id} d={d} quote={q} busy={busy} active={active}
          onAction={onAction} />
      ))}

      {may(d, active, 'ask') && (free ? (
        // **Wo niemand zugelassen ist, wird gesucht** – dieselbe Bauart wie überall.
        <ObjectSelect<DealParty>
          label={d.party_word}
          value={picked?.object_id ?? null}
          selected={picked}
          find={find}
          scanLabel={d.party_word}
          placeholder="Nummer oder Name"
          onChange={(nr, opt) => {
            // **Die frisch gewählte Option wird gehalten** (#794): sonst zeigt das Feld
            // nach dem Klick nichts, weil die Wahl noch nicht gespeichert ist.
            setPicked(nr === null ? null : (opt ?? { object_id: nr, name: '' }));
            if (nr !== null) onAction({ action: 'ask', parties: [nr] });
          }}
        />
      ) : open.length > 0 && (
        <div>
          <button type="button" className="erp-actbtn" disabled={busy}
            data-tip={open.map((o) => `${o.object_id} ${o.name}`).join(' · ')}
            onClick={() => onAction({ action: 'ask' })}>
            <Send size={13} /> {d.ask_verb}
            {open.length > 1 ? ` (${open.length})` : ''}
          </button>
        </div>
      ))}
    </div>
  );
}

/**
 * **Eine Angebotszeile** – wer, wie viel, wie lange, und was man damit tun darf.
 *
 * Zwei Zeilen statt einer Flexzeile: bei ~460 px Spurbreite drängten sich sonst Nummer,
 * Name, zwei Eingaben und zwei Symbol-Knöpfe nebeneinander. Oben **wer und wie viel**,
 * darunter – nur wo etwas zu tun ist – die Handlungen.
 */
function QuoteRow({ d, quote, busy, active, onAction }: {
  d: Filled; quote: DealQuote; busy?: boolean; active: boolean;
  onAction: (body: Action) => void;
}) {
  const [amount, setAmount] = useState(quote.amount ?? '');
  const [lead, setLead] = useState(quote.lead_days == null ? '' : String(quote.lead_days));
  const [days, setDays] = useState(
    quote.payment_days == null ? '' : String(quote.payment_days));
  const party = quote.party_object_id;
  const declined = quote.state === QUOTE_STATE.declined;
  const chosen = quote.state === QUOTE_STATE.chosen;

  return (
    <div className="flex flex-col" style={{ borderTop: '1px solid var(--border-1)' }}>
      <div className="flex items-center gap-2 py-1 flex-wrap">
        {chosen && <Check size={13} style={{ color: 'var(--success)', flex: 'none' }}
          data-tip="Diese Zeile hat den Zuschlag" />}
        <ObjId value={party} />
        <span className="text-[12.5px] truncate flex-1" style={{
          minWidth: 0, color: declined ? 'var(--fg-4)' : 'var(--fg-2)',
          textDecoration: declined ? 'line-through' : undefined,
        }}>{quote.party_name}</span>
        {quote.amount && (
          <span className="ix-tnum text-[12.5px] font-semibold"
            style={{ color: 'var(--fg-1)', flex: 'none' }}>
            {formatAmount(quote.amount)}
          </span>
        )}
        {quote.lead_days != null && (
          <span className="text-[12px]" style={{ color: 'var(--fg-4)', flex: 'none' }}>
            {quote.lead_days} Tage
          </span>
        )}
        {declined && (
          <span className="text-[12px]" style={{ color: 'var(--fg-4)', flex: 'none' }}>
            abgesagt
          </span>
        )}
      </div>
      {active && !chosen && (may(d, active, 'quote') || may(d, active, 'agree')) && (
        <div className="flex items-end gap-2 flex-wrap" style={{ paddingBottom: 8 }}>
          {may(d, active, 'quote') && (
            <>
              <div style={{ width: 110 }}>
                <Label>Betrag</Label>
                <input className={`${inputCls} ix-tnum`} {...numericInputProps}
                  value={amount} aria-label="Betrag" placeholder="0.00"
                  onChange={(e) => setAmount(numericOnly(e.target.value))} />
              </div>
              <div style={{ width: 92 }}>
                <Label>Lieferfrist</Label>
                <input className={`${inputCls} ix-tnum`} {...numericInputProps}
                  value={lead} aria-label="Lieferfrist in Tagen" placeholder="Tage"
                  onChange={(e) => setLead(numericOnly(e.target.value, { decimals: false }))} />
              </div>
              <div style={{ width: 100 }}>
                <Label>Zahlungsfrist</Label>
                <input className={`${inputCls} ix-tnum`} {...numericInputProps}
                  value={days} aria-label="Zahlungsfrist in Tagen" placeholder="Tage"
                  onChange={(e) => setDays(numericOnly(e.target.value, { decimals: false }))} />
              </div>
              <button type="button" className="erp-actbtn" disabled={busy}
                data-tip="Den genannten Preis festhalten"
                onClick={() => onAction({
                  action: 'quote', party, amount,
                  lead_days: lead === '' ? null : Number(lead),
                  payment_days: days === '' ? null : Number(days),
                })}>
                Offerte
              </button>
            </>
          )}
          {may(d, active, 'decline') && !declined && (
            <button type="button" className="erp-actbtn erp-actbtn-icon" disabled={busy}
              aria-label="Absage" data-tip="Absage · kommt nicht in Frage"
              onClick={() => onAction({ action: 'decline', party })}>
              <CircleSlash size={13} />
            </button>
          )}
          {/* **Der Zuschlag** – das eine Verb, das in beiden Richtungen gleich heisst. */}
          {may(d, active, 'agree') && !declined && (
            <button type="button" className="erp-actbtn" disabled={busy || !quote.amount}
              data-tip={quote.amount ? undefined : 'Ohne Preis gibt es keine Zusage'}
              onClick={() => onAction({ action: 'agree', party })}>
              <Check size={13} /> {d.stages[0]?.verb}
            </button>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * **Der bestätigte Auftrag** – was feststeht, steht als **Wert** da, nicht in einem
 * gesperrten Feld. Und darin die Bestätigung, die das Modul abschliesst.
 */
function Agreed({ d, busy, active, onAction, children }: {
  d: Filled; busy?: boolean; active: boolean; onAction: (body: Action) => void;
  children?: React.ReactNode;
}) {
  const [ref, setRef] = useState(d.reference ?? '');
  const waiting = d.prepaid && !d.settled;
  return (
    <div className="flex flex-col gap-2 mt-1.5">
      <div className="grid gap-2"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))' }}>
        <ReadField label={d.party_word}
          value={d.party_object_id
            ? <span className="flex items-center gap-1.5 flex-wrap">
                <ObjId value={d.party_object_id} /> {d.party_name}
              </span>
            : '—'} />
        <ReadField label="Betrag" mono value={formatAmount(d.amount)} />
        {d.due_days != null && (
          <ReadField label="Zahlungsfrist" value={`${d.due_days} Tage`} />
        )}
        {d.agreed_on && <ReadField label="Bestätigt" value={localDate(d.agreed_on)} />}
      </div>
      {may(d, active, 'note') && (
        <div style={{ maxWidth: 260 }}>
          <Label>Referenz</Label>
          <input className={inputCls} value={ref} aria-label="Referenz"
            placeholder="ihre Nummer"
            onChange={(e) => setRef(e.target.value)}
            onBlur={() => ref !== (d.reference ?? '')
              && onAction({ action: 'note', reference: ref })} />
        </div>
      )}
      {/* **Warum es nicht weitergeht, steht da, wo man weiterklicken würde.** Der Server
          weist ebenso ab (`deal.assert_completable`) – dies ist die freundliche Hälfte. */}
      {active && waiting && (
        <p className="text-[12.5px]" style={{ color: 'var(--warning)' }}>
          Erst nach Zahlungseingang: {formatAmount(d.paid)} von {formatAmount(d.amount)}
          {' '}bezahlt.
        </p>
      )}
      {active && !waiting && children}
    </div>
  );
}

/**
 * ►►► **Rechnung & Zahlung — zwei Achsen, EINE naheliegende Handlung.** ◄◄◄
 *
 * Forderung und Geld sind getrennt, und genau deshalb braucht keines der Szenarien einen
 * Modus: Vorauszahlung ist «erst fordern, dann zahlen», eine Anzahlung ist eine Forderung
 * über einen Teil, eine Gutschrift eine **negative** Forderung, eine Erstattung eine
 * **negative** Zahlung.
 *
 * **Welche Handlung jetzt dran ist, sagt der Server** (`next_charge` ↔ `next_payment`) –
 * die Oberfläche rechnet nichts nach. Alles Übrige liegt unter «Weitere»: die Freiheit
 * bleibt, aber sie steht nicht mehr als drei gleichwertige Knöpfe da.
 */
function Money({ d, busy, active, onAction }: {
  d: Filled; busy?: boolean; active: boolean; onAction: (body: Action) => void;
}) {
  const [form, setForm] = useState<'' | 'charge' | 'payment'>('');
  const [more, setMore] = useState(false);
  // Ohne Zahlen gibt es nichts zu zeigen – so sieht es eine Gegenpartei.
  if (d.open == null) return null;

  const openAmount = Number(d.open);
  const nothingYet = !Number(d.charged ?? 0) && !Number(d.paid ?? 0);
  const overdue = d.entries.some((e) => e.overdue);
  // **Die naheliegende Handlung**: erst fordern, dann kassieren. Beides bleibt möglich –
  // nur steht das eine vorn und das andere unter «Weitere».
  const primary = d.next_charge != null ? 'charge'
    : d.next_payment != null ? 'payment' : '';

  const chargeBtn = (main: boolean) => may(d, active, 'charge') && (
    <button type="button" className="erp-actbtn" disabled={busy} key="charge"
      style={main ? { fontWeight: 600 } : undefined}
      onClick={() => setForm(form === 'charge' ? '' : 'charge')}>
      <FileText size={13} /> {d.charge_word}
    </button>
  );
  const payBtn = (main: boolean) => may(d, active, 'pay') && (
    <button type="button" className="erp-actbtn" disabled={busy} key="pay"
      style={main ? { fontWeight: 600 } : undefined}
      onClick={() => setForm(form === 'payment' ? '' : 'payment')}>
      <Wallet size={13} /> {d.payment_word}
    </button>
  );

  return (
    <div className="flex flex-col gap-2 mt-1.5">
      <div className="flex items-center gap-2 flex-wrap">
        {/* **Punkt + Wort**, wie jeder Zustand im Haus – nicht als gefüllte Plakette. */}
        <span style={{
          width: 6, height: 6, borderRadius: 999, flex: 'none',
          background: nothingYet ? 'var(--border-2)'
            : openAmount === 0 ? 'var(--success)'
            : overdue ? 'var(--danger)' : 'var(--warning)',
        }} />
        <span className="text-[12.5px]" style={{ color: 'var(--fg-2)' }}>
          {/* **«Bezahlt» heisst «gefordert UND beglichen».** Ohne die Unterscheidung
              stünde direkt nach der Zusage «Bezahlt» da – offen ist dort null, weil noch
              nichts gefordert wurde. Dieselbe Zahl, eine ganz andere Aussage. */}
          {nothingYet ? 'Nichts berechnet'
            : openAmount === 0 ? 'Bezahlt'
            : openAmount < 0 ? 'Wir schulden' : d.open_word}
        </span>
        {!nothingYet && openAmount !== 0 && (
          <span className="ix-tnum text-[12.5px] font-semibold"
            style={{ color: overdue ? 'var(--danger)' : 'var(--fg-1)' }}>
            {formatAmount(Math.abs(openAmount))}
          </span>
        )}
        <span className="text-[12px] ix-tnum" style={{ color: 'var(--fg-4)' }}>
          {formatAmount(d.charged)} berechnet · {formatAmount(d.paid)} bezahlt · von{' '}
          {formatAmount(d.amount)}
        </span>
      </div>

      {d.entries.length > 0 && (
        <div className="flex flex-col">
          {d.entries.map((e) => (
            <div key={e.id} className="flex items-center gap-2 py-1 text-[12.5px] flex-wrap"
              style={{ borderTop: '1px solid var(--border-1)' }}>
              <span style={{ color: 'var(--fg-4)', display: 'flex', flex: 'none' }}
                data-tip={e.kind === 'charge' ? d.charge_word : d.payment_word}>
                {e.kind === 'charge' ? <FileText size={13} /> : <Wallet size={13} />}
              </span>
              <span className="ix-tnum font-semibold" style={{
                color: e.overdue ? 'var(--danger)' : 'var(--fg-1)', flex: 'none',
              }}>{formatAmount(e.amount)}</span>
              {/* **Die Referenz nimmt den Rest und wird gekappt, das Datum nicht.**
                  Umgekehrt lief der Datumstext über seine eigene Box hinaus – gemessen
                  380,1 px bei 375 px Fenster, und kein Element-Rahmen zeigte es. */}
              {e.reference && (
                <span className="ix-tnum truncate flex-1" data-tip={e.reference}
                  style={{ color: 'var(--fg-3)', minWidth: 0 }}>{e.reference}</span>
              )}
              <span style={{ color: 'var(--fg-4)', flex: 'none' }}>
                {localDate(e.booked_on)}
                {e.due_on && ` · ${e.overdue ? 'überfällig seit' : 'fällig'} `}
                {e.due_on && localDate(e.due_on)}
              </span>
              {may(d, active, 'void') && (
                <button type="button" className="erp-actbtn erp-actbtn-icon"
                  disabled={busy} aria-label="Zeile zurücknehmen"
                  data-tip="Zeile zurücknehmen – sie bleibt im Nachweis lesbar."
                  onClick={() => onAction({ action: 'void', entry: e.id })}>
                  <Trash2 size={13} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        {primary === 'charge' && chargeBtn(true)}
        {primary === 'payment' && payBtn(true)}
        {!more && (may(d, active, 'charge') || may(d, active, 'pay')
          || may(d, active, 'revoke')) && (
          <button type="button" className="erp-actbtn" onClick={() => setMore(true)}
            data-tip="Gutschrift, Erstattung, Storno – jede Reihenfolge bleibt möglich">
            Weitere <ChevronDown size={13} />
          </button>
        )}
        {more && primary !== 'charge' && chargeBtn(false)}
        {more && primary !== 'payment' && payBtn(false)}
        {/* **Die eine Gegenhandlung** – und ihr Wort kommt vom Server (`undo`). */}
        {more && may(d, active, 'revoke') && d.undo && (
          <button type="button" className="erp-actbtn" disabled={busy}
            onClick={() => onAction({ action: 'revoke' })}>
            <Undo2 size={13} /> {d.undo}
          </button>
        )}
      </div>

      {form !== '' && (
        <Entry kind={form} d={d} busy={busy}
          onCancel={() => setForm('')}
          onSubmit={(body) => { setForm(''); onAction(body); }} />
      )}
    </div>
  );
}

/**
 * **Eine Zeile Geld erfassen** – dasselbe Formular für beide Achsen.
 *
 * Der Unterschied ist eine Vorgabe: eine Forderung schlägt *zugesagt − berechnet* vor,
 * eine Zahlung den *offenen* Betrag. **Und keine Vorgabe ist je negativ** (#795): dass
 * mehr berechnet als zugesagt wurde, ist eine gültige Aussage – als Vorschlag in einem
 * Eingabefeld ist sie es nicht. Negative Beträge bleiben **eingebbar**: das ist die
 * Gutschrift bzw. die Erstattung.
 */
function Entry({ kind, d, busy, onCancel, onSubmit }: {
  kind: 'charge' | 'payment'; d: Filled; busy?: boolean;
  onCancel: () => void; onSubmit: (body: Action) => void;
}) {
  const [amount, setAmount] = useState(
    (kind === 'charge' ? d.next_charge : d.next_payment) ?? '');
  const [ref, setRef] = useState('');
  return (
    <div className="flex flex-col gap-2" style={{
      padding: 10, borderRadius: 8, border: '1px solid var(--border-1)',
    }}>
      <div className="grid gap-2"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))' }}>
        <div>
          <Label required>Betrag</Label>
          <input className={`${inputCls} ix-tnum`} {...numericInputProps} autoFocus
            value={amount} aria-label="Betrag"
            onChange={(e) => setAmount(numericOnly(e.target.value, { signed: true }))} />
        </div>
        <div>
          <Label>{kind === 'charge' ? 'Rechnungsnummer' : 'Zahlungszweck'}</Label>
          <input className={inputCls} value={ref}
            aria-label={kind === 'charge' ? 'Rechnungsnummer' : 'Zahlungszweck'}
            placeholder={kind === 'charge' && d.direction === 'in'
              ? 'automatisch' : 'optional'}
            onChange={(e) => setRef(e.target.value)} />
        </div>
      </div>
      <div className="flex items-center gap-2">
        <button type="button" className="erp-actbtn" disabled={busy}
          onClick={() => onSubmit({
            action: kind === 'charge' ? 'charge' : 'pay', amount, reference: ref,
          })}>
          {kind === 'charge' ? d.charge_word : d.payment_word}
        </button>
        <button type="button" className="erp-actbtn" onClick={onCancel}>Abbrechen</button>
      </div>
    </div>
  );
}
