'use client';

import { useCallback, useState } from 'react';
import { useAutosave } from '@/lib/use-autosave';
import { ArrowUpRight, Check, CircleSlash, Coins, CreditCard, FileText, Undo2 } from 'lucide-react';
import { api } from '@/lib/api';
import type { PurchaseEmbed, PurchaseQuote, SupplierOption } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import { IconSwitch, Label, ReadField, inputCls, numericInputProps, numericOnly } from '@/components/erp/fields';
import { MANUAL_METHODS, STAGE, type Method } from '@/lib/modules';
import { formatAmount, localDate } from '@/lib/utils';

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
 *
 * ## Eine Ansicht, zwei Rollen — und keine Rollenabfrage (#751)
 *
 * Personal und Lieferant sehen **dieselbe** Karte: dieselben Stufen, dieselbe Sache,
 * dieselben Wörter. Was sie unterscheidet, ist einzig, **was man hier tun darf** – und
 * das sagt der Beleg selbst (`purchase.can`, abgeleitet aus Stufe × Rolle an der einen
 * Stelle, an der die Regel wohnt). Diese Komponente weiss darum nicht, was ein Lieferant
 * ist; sie fragt `may(...)`.
 *
 * Vorher rendete sie jede Aktion, sobald die Stufe aktiv war: ein Lieferant sah
 * «Anfrage zurückziehen», «Bestellen», «Stornieren» und den Wareneingangs-Scan – vier
 * Knöpfe, die der Server mit 403 abweist. Ein Knopf, der nie etwas tun kann, ist kein
 * Angebot; und eine Rollenabfrage hier wäre die zweite Stelle für dieselbe Regel.
 *
 * **Die Wörter sind darum allgemein gehalten**, nicht je Rolle formuliert: «Offerte
 * erfassen» stimmt für beide (er gibt seine ab, wir schreiben seine auf), «Absage ·
 * liefert nicht» ebenso. Eine Beschriftung je Rolle wäre ein `if` in Textform.
 */
/** Derselbe Beleg, nur mit gefüllten Listen – siehe `PurchaseWork`. */
type Filled = Omit<PurchaseEmbed, 'stages' | 'quotes' | 'allowed' | 'lines' | 'can'> & {
  stages: NonNullable<PurchaseEmbed['stages']>;
  quotes: NonNullable<PurchaseEmbed['quotes']>;
  allowed: NonNullable<PurchaseEmbed['allowed']>;
  lines: NonNullable<PurchaseEmbed['lines']>;
  can: NonNullable<PurchaseEmbed['can']>;
};

/**
 * **Darf man das hier?** – die einzige Frage, die diese Komponente über Rechte stellt.
 *
 * `can` kommt vom Server (`purchase._can`); `active` sagt, ob das **Modul** an der Reihe
 * ist. Beides muss stimmen: ein Lieferant darf offerieren, aber nicht an einem Modul,
 * das noch gar nicht dran ist.
 */
function may(p: Filled, active: boolean, action: string): boolean {
  return active && p.can.includes(action);
}

/** Das Verb der aktiven Stufe – aus dem Beleg, nicht aus einem Literal daneben. */
function verbOf(p: Filled): string {
  return p.stages.find((s) => s.active)?.verb ?? '';
}

/** Die Gesamtmenge des Belegs – die Summe seiner Zeilen, an EINER Stelle gerechnet. */
function total(p: Filled): number {
  return p.lines.reduce((sum, l) => sum + (l.quantity ?? 0), 0);
}

export function PurchaseWork({ purchase, busy, active = true, onAction, onLink,
  children }: {
  purchase: PurchaseEmbed;
  busy?: boolean;
  /**
   * **Ist dieses Modul an der Reihe?**
   *
   * Der Beleg steht in **jedem** Zustand da – was in ihm passiert ist, gehört zum Modul
   * und nicht zum Moment, in dem man es bedienen darf (dieselbe Regel wie «ein
   * abgeschlossenes Modul zeigt lückenlos, was in ihm geschah»). Abhängig ist allein,
   * ob **gehandelt** werden kann: ohne `active` bleiben die Knöpfe aus und die Felder
   * gesperrt.
   */
  active?: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
  /**
   * **Eine Zahlungsaufforderung erzeugen** – der Aufrufer weiss, an welchem Auftrag und
   * Modul er steht; diese Komponente kennt keine Routen. Fehlt der Rückruf, gibt es den
   * Knopf nicht: derselbe Massstab wie `can`.
   */
  onLink?: () => Promise<string>;
  /** Der Wareneingang selbst – der Scan, der jedes Modul abschliesst. */
  children?: React.ReactNode;
}) {
  // Die Listen sind serverseitig immer gesetzt; der generierte Typ lässt sie optional,
  // weil Pydantic-Defaults dort so ankommen. Einmal hier vereinheitlicht statt an jeder
  // Lesestelle ein `?? []`.
  const p = { ...purchase, stages: purchase.stages ?? [], quotes: purchase.quotes ?? [],
              allowed: purchase.allowed ?? [], lines: purchase.lines ?? [],
              can: purchase.can ?? [] };
  const cancelled = p.stage === STAGE.cancelled;

  return (
    <div className="flex flex-col">
      <Subject p={p} />
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

              </div>
              {/* **Eine Stufe zeigt, was sie trägt – auch wenn sie vorbei ist.**
                  Gehandelt wird nur an der Stufe, die dran ist UND deren Modul dran ist. */}
              {stage.key === STAGE.offer && (stage.active || stage.done) && (
                <Ask p={p} busy={busy} active={active && stage.active} onAction={onAction} />
              )}
              {stage.key === STAGE.commitment && (stage.active || stage.done) && (
                <Ordered p={p} busy={busy} active={active && stage.active} onAction={onAction} />
              )}
              {/* **Auch der Wareneingang ist ein Verb dieses Belegs** – er läuft über
                  `confirm_step`, aber wer ihn buchen darf, steht in derselben Liste.
                  Zwei Listen wären zwei Massstäbe. */}
              {stage.key === STAGE.fulfilment && may(p, active, 'receive') && (
                <div className="mt-1.5">{children}</div>
              )}
            </div>
          </div>
        );
      })}
      {cancelled && (
        <div className="flex items-center gap-1.5 mt-1 text-[12.5px]"
          style={{ color: 'var(--danger)' }}>
          <CircleSlash size={13} /> Storniert
        </div>
      )}
      {/* **Das Geld steht NEBEN den Stufen, nicht in ihnen** – es ist keine vierte.
          Eine Zahlung macht aus einem Angebot keine Zusage, und eine ausbleibende macht
          aus einer Lieferung keine Nicht-Lieferung; und **nach** einem Storno ist eine
          Erstattung der Normalfall, nicht die Ausnahme. Ob es überhaupt etwas zu zeigen
          gibt, sagt der Beleg (`open` ist `null`, solange nichts zugesagt ist). */}
      <Money p={p} busy={busy} active={active} onAction={onAction} onLink={onLink} />
    </div>
  );
}

/**
 * ►►► **Das Geld an diesem Beleg — offen, fällig, und was geflossen ist.** ◄◄◄
 *
 * **Drei Ableitungen, keine Spalte** (`services/payments`): *offen* ist Belegsumme minus
 * Gutschriften minus Zahlungen, *fällig* ist Zusagedatum plus Zahlungsfrist, *überfällig*
 * ist beides zusammen. Die Oberfläche rechnet nichts nach – sie zeigt, was der Beleg sagt.
 *
 * **Ein negativer offener Betrag ist kein Fehler**, sondern eine Aussage: dann schulden
 * **wir**. Das Wort wechselt, die Zahl bleibt dieselbe – eine zweite Anzeige daneben wäre
 * dieselbe Information ein zweites Mal.
 *
 * **Überweisung und Karte sind dieselbe Zeile.** Der Unterschied ist, wer sie schreibt:
 * ein Mensch hier oder der Webhook des Zahlungsdienstes. Darum gibt es hier auch kein
 * «Stripe» – nur einen Zahllink, und ob es ihn gibt, sagt `can`.
 */
function Money({ p, busy, active, onAction, onLink }: {
  p: Filled; busy?: boolean; active: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
  onLink?: () => Promise<string>;
}) {
  const [shown, setShown] = useState<'' | 'invoices' | 'payments'>('');
  const entries = p.entries ?? [];
  const bills = p.invoices ?? [];
  // Solange nichts zugesagt ist, gibt es keine Summe – und damit nichts zu zeigen.
  if (p.open == null) return null;

  const owed = p.open < 0;
  const settled = p.open === 0;
  // ►►► **«Bezahlt» heisst «gefordert UND beglichen».** ◄◄◄
  //
  // Ohne die Unterscheidung stand direkt nach der Zusage «Bezahlt» da – offen ist dort
  // null, weil noch **nichts gefordert** wurde. Das ist dieselbe Zahl und eine ganz
  // andere Aussage; wer sie liest, hält den Beleg für erledigt. Gemessen an der echten
  // Karte, nicht am Code.
  const nothingYet = !p.charged && !p.paid;
  return (
    <div className="flex flex-col gap-2" style={{
      marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border-1)',
    }}>
      <div className="flex items-center gap-2 flex-wrap">
        {/* **Punkt + Wort**, wie jeder Zustand im Haus – nicht als gefüllte Plakette. */}
        <span style={{
          width: 6, height: 6, borderRadius: 999, flex: 'none',
          background: nothingYet ? 'var(--border-2)'
            : settled ? 'var(--success)'
            : p.overdue ? 'var(--danger)' : 'var(--warning)',
        }} />
        <span className="text-[12.5px]" style={{ color: 'var(--fg-2)' }}>
          {nothingYet ? 'Nichts berechnet'
            : settled ? 'Bezahlt' : owed ? 'Wir schulden' : 'Offen'}
        </span>
        {!settled && !nothingYet && (
          <span className="ix-tnum text-[12.5px] font-semibold"
            style={{ color: p.overdue ? 'var(--danger)' : 'var(--fg-1)' }}>
            {formatAmount(Math.abs(p.open))} {p.currency}
          </span>
        )}
        {p.due_on && !settled && (
          <span className="text-[12px]" style={{
            color: p.overdue ? 'var(--danger)' : 'var(--fg-3)',
          }}>
            {p.overdue ? 'überfällig seit' : 'fällig'} {localDate(p.due_on)}
          </span>
        )}
        {/* **Zugesagt, noch nicht berechnet** – die Zahl, die es vor der dritten Achse
            gar nicht geben konnte, und zugleich die Vorgabe für die nächste Rechnung.
            Sie steht nur da, wenn sie etwas sagt: bei null ist alles berechnet. */}
        {!!p.uncharged && (
          <span className="text-[12px]" style={{ color: 'var(--fg-3)' }}>
            · {formatAmount(p.uncharged)} noch nicht berechnet
          </span>
        )}
        {bills.length > 0 && (
          <button type="button" className="text-[12px] underline"
            style={{ color: 'var(--accent)' }}
            onClick={() => setShown((v) => (v === 'invoices' ? '' : 'invoices'))}>
            {bills.length} {bills.length === 1 ? 'Rechnung' : 'Rechnungen'}
          </button>
        )}
        {entries.length > 0 && (
          <button type="button" className="text-[12px] underline"
            style={{ color: 'var(--accent)' }}
            onClick={() => setShown((v) => (v === 'payments' ? '' : 'payments'))}>
            {entries.length} {entries.length === 1 ? 'Buchung' : 'Buchungen'}
          </button>
        )}
      </div>

      {/* **Die Rechnungen – die dritte Achse.** Ein negativer Betrag ist eine
          Gutschrift; eine eigene Art dafür gibt es nicht. */}
      {shown === 'invoices' && bills.map((b) => (
        <div key={b.id} className="flex items-baseline gap-2 text-[12px]"
          style={{ color: 'var(--fg-3)', paddingLeft: 14 }}>
          <span className="ix-tnum" style={{
            color: b.amount < 0 ? 'var(--success)' : 'var(--fg-2)', minWidth: 78,
          }}>
            {formatAmount(b.amount)}
          </span>
          {b.number_label && (
            <span className="font-mono truncate" style={{ maxWidth: 180 }}>
              {b.number_label}
            </span>
          )}
          {b.issued_on && <span>· {localDate(b.issued_on)}</span>}
          {b.due_on && <span>· fällig {localDate(b.due_on)}</span>}
          {b.note && <span className="truncate" style={{ maxWidth: 220 }}>· {b.note}</span>}
        </div>
      ))}

      {/* **Erst auf Klick** – dieselbe Regel wie beim Modul-Protokoll: eine Liste, die
          bei jeder Anzeige mitläuft, ist bei zwanzig Teilzahlungen eine Wand. */}
      {shown === 'payments' && entries.map((e) => (
        <div key={e.id} className="flex items-baseline gap-2 text-[12px]"
          style={{ color: 'var(--fg-3)', paddingLeft: 14 }}>
          <span className="ix-tnum" style={{ color: 'var(--fg-2)', minWidth: 78 }}>
            {formatAmount(e.amount)}
          </span>
          {e.method_label && <span>{e.method_label}</span>}
          {e.paid_at && <span>· {localDate(e.paid_at)}</span>}
          {e.reference && (
            <span className="font-mono truncate" style={{ maxWidth: 180 }}>
              · {e.reference}
            </span>
          )}
        </div>
      ))}

      <div className="flex items-center gap-2 flex-wrap">
        {/* **Die Forderung steht VOR dem Geld** – nicht als Reihenfolge-Regel, sondern
            weil man nicht kassiert, was niemand gefordert hat. Wann sie entsteht,
            entscheidet der Mensch: vorher (Vorauszahlung) oder nachher (Zahlungsziel). */}
        {may(p, active, 'invoice') && (
          <InvoiceForm p={p} busy={busy} onAction={onAction} />
        )}
        {may(p, active, 'pay') && (
          <PayForm p={p} busy={busy} onAction={onAction} />
        )}
        {/* **Der Zahllink erscheint nur, wo es einen Dienst gibt UND etwas offen ist.**
            Beides entscheidet der Server (`can`); ein Knopf, der nie etwas tun kann, ist
            kein Angebot – und ein ausgegrauter wäre eine Bitte. */}
        {may(p, active, 'link') && onLink && <PayLink onLink={onLink} busy={busy} />}
      </div>
    </div>
  );
}

/**
 * **Eine Zeile Geld erfassen** – Betrag, Weg, Referenz.
 *
 * Kein eigener Endpunkt: `pay` ist eine Handlung am Beleg wie jede andere (`onAction`).
 * Sie hat nur keine **Stufe** – Geld fliesst, sobald zugesagt ist, und auch noch nach
 * einem Storno.
 *
 * **Keine «Art» mehr.** Eine Gutschrift ist eine negative **Rechnung**: dabei fliesst
 * kein Geld, also gehört sie auf die andere Achse. Als Zahlungs-Art brauchte sie eine
 * eigene Regel («hat keinen Zahlweg») – jetzt braucht sie keine.
 *
 * **Und keine Karte** (#782): eine Kartenzahlung entsteht beim Zahlungsdienst und kommt
 * über den Webhook. Sie hier abzutippen wäre eine zweite Quelle für dieselbe Buchung –
 * die eine aus der Wirklichkeit, die andere aus einer Erinnerung. Die Regel steht im
 * Dienst (`money.MANUAL_METHODS`, durchgesetzt in `purchase._pay`); hier folgt ihr das
 * Formular, damit man gar nicht erst etwas eingibt, das abgewiesen würde.
 *
 * **Zwei Werte sind ein Schieber, keine Liste** – dieselbe Form wie überall im Haus
 * (`IconSwitch`): man sieht, was gilt, und wechselt mit einem Klick statt mit dreien.
 */
function PayForm({ p, busy, onAction }: {
  p: Filled; busy?: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
}) {
  const [show, setShow] = useState(false);
  const [amount, setAmount] = useState('');
  const [method, setMethod] = useState<Method>('transfer');
  const [reference, setReference] = useState('');

  if (!show) {
    return (
      <button type="button" className="erp-actbtn self-start" style={{ height: 28 }}
        disabled={busy} onClick={() => {
          // **Vorbelegt mit dem, was offen ist** – der Normalfall ist «voll bezahlt».
          setAmount(p.open != null && p.open > 0 ? String(p.open) : '');
          setShow(true);
        }}>
        <Coins size={13} /> Zahlung erfassen
      </button>
    );
  }
  return (
    <div className="flex items-end gap-2 flex-wrap">
      <div style={{ width: 108 }}>
        <Label>Betrag</Label>
        <input className={inputCls} {...numericInputProps} value={amount}
          onChange={(e) => setAmount(numericOnly(e.target.value))} />
      </div>
      <div>
        <Label>Weg</Label>
        <IconSwitch<Method>
          value={method} onChange={setMethod}
          options={MANUAL_METHODS.map((m) => ({
            value: m.value, icon: m.icon, label: m.label, hint: m.hint,
          }))}
        />
      </div>
      <div style={{ width: 180 }}>
        <Label>Referenz</Label>
        <input className={inputCls} value={reference} placeholder="Zahlungszweck"
          onChange={(e) => setReference(e.target.value)} />
      </div>
      <button type="button" className="erp-actbtn erp-actbtn-primary"
        style={{ height: 30 }} disabled={busy || amount.trim() === ''}
        onClick={() => {
          onAction({ action: 'pay', amount: Number(amount), method, reference });
          setShow(false); setAmount(''); setReference('');
        }}>
        <Check size={13} /> Buchen
      </button>
      <button type="button" className="erp-actbtn" style={{ height: 30 }}
        onClick={() => setShow(false)}>Abbrechen</button>
    </div>
  );
}


/**
 * ►►► **Eine Forderung stellen — die dritte Achse neben Ware und Geld.** ◄◄◄
 *
 * **Alles ist vorbelegt**, und das ist die ganze Automatik: der Betrag mit *zugesagt −
 * bereits berechnet*, die Fälligkeit mit *heute + vereinbarte Frist*, die Nummer mit
 * `<Auftragsnummer>-<laufend>`. Der Normalfall ist damit ein Klick – und jede Abweichung
 * eine Eingabe statt eines zweiten Wegs.
 *
 * **Es gibt keinen Modus.** Ob die Rechnung vor der Lieferung steht (Vorauszahlung) oder
 * danach (Zahlungsziel), ist die Reihenfolge, in der ein Mensch handelt – kein Schalter,
 * keine Einstellung. Eine negative Zahl ist eine **Gutschrift**; auch dafür braucht es
 * keine zweite Handlung.
 *
 * **Die Nummer kommt vom Server** (`next_invoice_number`) – beim Einkauf leer, denn dort
 * nummeriert die Gegenpartei. Eine im Browser gebaute Nummer wäre die zweite Fassung
 * desselben Formats.
 *
 * **Und kein Fälligkeits-Feld** (dieselbe Regel wie beim Liefertermin, #745): sie ist
 * *Rechnungsdatum + vereinbarte Zahlungsfrist*, und die Frist ist die Vereinbarung. Ein
 * abweichendes Datum wäre eine Neuverhandlung – die ändert die Frist, nicht diese eine
 * Zeile. Der Dienst nimmt `due_on` trotzdem entgegen: dort ist es die Naht, über die die
 * Migration bestehende Belege setzt.
 */
function InvoiceForm({ p, busy, onAction }: {
  p: Filled; busy?: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
}) {
  const [show, setShow] = useState(false);
  const [amount, setAmount] = useState('');
  const [number, setNumber] = useState('');
  const [note, setNote] = useState('');

  if (!show) {
    return (
      <button type="button" className="erp-actbtn self-start" style={{ height: 28 }}
        disabled={busy} onClick={() => {
          setAmount(p.uncharged ? String(p.uncharged) : '');
          setNumber(p.next_invoice_number ?? '');
          setShow(true);
        }}>
        <FileText size={13} /> {p.invoice_verb}
      </button>
    );
  }
  return (
    <div className="flex items-end gap-2 flex-wrap">
      <div style={{ width: 108 }}>
        <Label>Betrag</Label>
        <input className={inputCls} {...numericInputProps} value={amount}
          onChange={(e) => setAmount(numericOnly(e.target.value, { signed: true }))} />
      </div>
      <div style={{ width: 150 }}>
        <Label>Nummer</Label>
        <input className={inputCls} value={number} maxLength={60}
          placeholder="Nummer der Gegenpartei"
          onChange={(e) => setNumber(e.target.value)} />
      </div>
      <div style={{ width: 180 }}>
        <Label>Notiz</Label>
        <input className={inputCls} value={note} maxLength={400}
          placeholder="z. B. Anzahlung 30 %"
          onChange={(e) => setNote(e.target.value)} />
      </div>
      <button type="button" className="erp-actbtn erp-actbtn-primary"
        style={{ height: 30 }} disabled={busy || amount.trim() === ''}
        onClick={() => {
          onAction({ action: 'invoice', amount: Number(amount), number,
                     note_text: note });
          setShow(false); setAmount(''); setNumber(''); setNote('');
        }}>
        <Check size={13} /> {p.invoice_verb}
      </button>
      <button type="button" className="erp-actbtn" style={{ height: 30 }}
        onClick={() => setShow(false)}>Abbrechen</button>
    </div>
  );
}


/**
 * **Eine Zahlungsaufforderung erzeugen** – und die Adresse zeigen.
 *
 * Sie ändert am Beleg **nichts**: gebucht wird erst, wenn das Geld wirklich da ist, und
 * das meldet der Webhook. Ein Browser, der nach der Zahlung geschlossen wird, darf keine
 * Buchung verschlucken.
 */
function PayLink({ onLink, busy }: { onLink: () => Promise<string>; busy?: boolean }) {
  const [url, setUrl] = useState('');
  const [failed, setFailed] = useState('');
  if (url) {
    return (
      <a className="erp-actbtn self-start" style={{ height: 28 }} href={url}
        target="_blank" rel="noreferrer">
        <ArrowUpRight size={13} /> Zahlungsseite öffnen
      </a>
    );
  }
  return (
    <div className="flex items-center gap-2">
      <button type="button" className="erp-actbtn self-start" style={{ height: 28 }}
        disabled={busy}
        onClick={() => {
          setFailed('');
          onLink().then(setUrl).catch((e) => setFailed(
            e instanceof Error ? e.message : 'Der Zahllink liess sich nicht erzeugen.'));
        }}>
        <CreditCard size={13} /> Zahllink erzeugen
      </button>
      {failed && (
        <span className="text-[12px]" style={{ color: 'var(--danger)' }}>{failed}</span>
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

/**
 * **Was beschafft wird — und was damit zu tun ist.** Der Gegenstand des Belegs, über der
 * Kette und in **jedem** Zustand: er gehört dem ganzen Vorgang, nicht seiner ersten Stufe.
 *
 * **Die Zeilen sind abgeleitet, nicht getippt**: es sind die Artikel der Einzelinstanzen,
 * die vor dem Modul stehen. Mehrere sind der Normalfall und kein Sonderfall – eine
 * Bestellung mit zwei Positionen ist im echten Leben eine Bestellung.
 *
 * **Drei Schichten, jede an ihrem Ort**: die *Spezifikation* beschreibt die Sache (sie
 * reist mit, sie wird nicht ausgewählt), der *Auftrag* sagt, was damit geschehen soll
 * («Härten auf 58 HRC»), und die *Nummer* des Lieferanten steht an seiner Zeile. Ohne die
 * mittlere Schicht wüsste ein Lieferant, **was** das Teil ist, aber nicht, was er tun soll.
 */
function Subject({ p }: { p: Filled }) {
  if (p.lines.length === 0 && !p.instruction) return null;
  return (
    <div className="flex flex-col gap-1.5"
      style={{ paddingBottom: 10, marginBottom: 10, borderBottom: '1px solid var(--border-1)' }}>
      {p.lines.map((l) => (
        <div key={l.article_object_id} className="flex flex-col gap-0.5">
          <div className="flex flex-wrap items-baseline gap-2 text-[13px]">
            <ObjId value={l.article_object_id} />
            <span className="truncate" style={{ fontWeight: 600 }}>{l.article_name}</span>
            <span style={{ fontVariantNumeric: 'tabular-nums', color: 'var(--fg-3)' }}>
              {l.quantity}{l.unit ? ` ${l.unit}` : ''}
            </span>
          </div>
          {(l.spec ?? []).length > 0 && (
            <div className="flex flex-wrap gap-x-2.5 gap-y-0.5 text-[12px]"
              style={{ color: 'var(--fg-3)' }}>
              {(l.spec ?? []).map((f) => (
                <span key={f.label}>
                  <span style={{ color: 'var(--fg-4)' }}>{f.label}</span> {f.value}
                </span>
              ))}
            </div>
          )}
        </div>
      ))}
      {p.instruction && (
        <div className="text-[12.5px]" style={{ color: 'var(--fg-2)' }}>
          <span style={{ color: 'var(--fg-4)' }}>Auftrag</span> {p.instruction}
        </div>
      )}
    </div>
  );
}


/**
 * **Die Anfrage — bei wem, und was kostet es.**
 *
 * Solange nichts angefragt ist, wird gewählt, bei wem man fragt. **Woher die Kandidaten
 * kommen, ist der einzige Unterschied zwischen zwei Fällen** – nicht der Ablauf:
 *
 * - Die Definition nennt **zugelassene** Lieferanten (Beschaffen: Lieferantenfreigabe) →
 *   sie stehen als Liste da, und die Zeile IST der Schalter.
 * - Sie nennt **keinen** (ein Transport: den Spediteur wählt man, wenn man weiss, wohin) →
 *   dann wird **gesucht** (`/orders/supplier-options`, dieselbe Bedingung wie überall:
 *   Nummer oder Name).
 *
 * Genau dieser zweite Fall fehlte: die Liste war leer, also stand nichts zum Anklicken da
 * und der Knopf blieb für immer gesperrt – man konnte «Beschaffen» wählen und danach
 * **nichts** tun (Testnotiz #775). Dieselbe Auflösung wie bei `SearchSelect` (#730):
 * derselbe Knopf, dieselbe Aktion, nur eine andere Quelle. Und die Regel dahinter steht
 * im **Dienst** (`purchase._assert_allowed`) – frei heisst nicht «irgendwer», gefragt
 * werden kann nur, wer als Lieferant geführt ist.
 *
 * Danach ist jede Zeile ein Angebot: der Preis kommt entweder vom Lieferanten selbst
 * (Portal) oder wird hier eingetragen – bei einem Shop-Kauf ist das der Katalogpreis.
 */
function Ask({ p, busy, active, onAction }: {
  p: Filled; busy?: boolean; active: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
}) {
  const asked = p.quotes.length > 0;
  const free = p.allowed.length === 0;
  const [picked, setPicked] = useState<number[]>(p.allowed.map((a) => a.supplier_object_id));
  // Die frei gesuchten tragen ihren Namen mit: die Antwort der Suche ist die einzige
  // Stelle, an der er hier bekannt ist.
  const [found, setFound] = useState<SupplierOption[]>([]);
  const [prices, setPrices] = useState<Record<number, string>>({});
  const [days, setDays] = useState<Record<number, string>>({});
  const mayAsk = may(p, active, 'ask');

  const findSuppliers = useCallback(
    (q: string) => api.searchParties(p.party_role, q).catch(() => []), [p.party_role]);

  const rows = free
    ? found.map((f) => ({ supplier_object_id: f.object_id, supplier_name: f.name }))
    : p.allowed;

  return (
    <div className="flex flex-col gap-2 mt-1.5">
      {!asked && rows.map((a) => {
        // **Die Zeile IST der Schalter** – kein Häkchen daneben. Gewählt heisst getönt
        // mit Haken, abgewählt heisst blass; dieselbe Geste wie überall im Haus, wo ein
        // Klick die Entscheidung ist.
        const on = picked.includes(a.supplier_object_id);
        return (
          <button key={a.supplier_object_id} type="button"
            disabled={!mayAsk}
            className="flex items-center gap-2 text-[13px] rounded-ds-sm w-full"
            style={{
              padding: '5px 8px', textAlign: 'left',
              border: `1px solid ${on ? 'var(--border-2)' : 'transparent'}`,
              background: on ? 'var(--bg-1)' : 'transparent',
              opacity: on ? 1 : 0.5,
              cursor: mayAsk ? 'pointer' : 'default',
            }}
            onClick={() => setPicked((cur) => (on
              ? cur.filter((n) => n !== a.supplier_object_id)
              : [...cur, a.supplier_object_id]))}>
            <Check size={13} style={{ flex: 'none', color: on ? 'var(--success)' : 'var(--fg-4)',
                                      opacity: on ? 1 : 0.35 }} />
            <ObjId value={a.supplier_object_id} />
            <span className="truncate" style={{ color: 'var(--fg-3)' }}>{a.supplier_name}</span>
          </button>
        );
      })}

      {/* **Dasselbe Referenzfeld wie überall** (`ObjectSelect`, #738): tippen sucht auf
          dem Server, die Kamera sitzt im Feld. Es steht nur da, wo die Definition
          niemanden nennt – wo sie es tut, ist die Liste die Wahl. */}
      {!asked && free && mayAsk && (
        <ObjectSelect<SupplierOption>
          value={null}
          find={findSuppliers}
          kind="user"
          scanLabel="Lieferant"
          placeholder="Lieferant suchen"
          onChange={(nr, opt) => {
            if (nr == null) return;
            if (opt) setFound((cur) => (cur.some((f) => f.object_id === nr) ? cur : [...cur, opt]));
            setPicked((cur) => (cur.includes(nr) ? cur : [...cur, nr]));
          }}
        />
      )}

      {/* **Ein Wort, immer dasselbe** (#750). «Anfragen» ↔ «Bei 2 anfragen» waren zwei
          Beschriftungen für denselben Knopf – und die Zahl fiel ausgerechnet dann weg,
          wenn sie am grössten ist. */}
      {!asked && mayAsk && (
        <button type="button" className="erp-actbtn erp-actbtn-primary self-start"
          style={{ height: 32 }} disabled={busy || picked.length === 0}
          data-tip={picked.length === 0 && free
            ? 'Erst suchen, bei wem angefragt werden soll.' : undefined}
          onClick={() => onAction({ action: 'ask', suppliers: picked })}>
          Bei {picked.length} anfragen
        </button>
      )}

      {asked && p.quotes.map((q) => (
        <QuoteRow key={q.supplier_object_id} q={q} p={p} busy={busy} active={active}
          onAction={onAction}
          price={prices[q.supplier_object_id] ?? ''}
          onPrice={(v) => setPrices((c) => ({ ...c, [q.supplier_object_id]: v }))}
          lead={days[q.supplier_object_id] ?? ''}
          onLead={(v) => setDays((c) => ({ ...c, [q.supplier_object_id]: v }))} />
      ))}

      {/* ►► **Der Weg zurück gibt es, BEVOR etwas angefragt ist** (Testnotiz #775). ◄◄
          Er hing an `asked` – wer «Beschaffen» gewählt hatte, kam damit erst wieder
          heraus, nachdem er angefragt hatte. Dabei ist genau davor am wenigsten zugesagt.
          Was «zurück» hier heisst, sagt der Beleg (`undo`): vor der Bestellung nimmt es
          die Anfrage zurück – und wo der Einkauf eine **Wahl** war, ist es die Wahl. */}
      {may(p, active, 'revoke') && (
        <button type="button" className="erp-actbtn erp-actbtn-neutral self-start"
          style={{ height: 28 }} disabled={busy}
          onClick={() => onAction({ action: 'revoke' })}>
          <Undo2 size={13} /> {p.undo}
        </button>
      )}
    </div>
  );
}

/**
 * **Eine Angebotszeile ist eine kleine Karte, keine gequetschte Zeile** (#752).
 *
 * Nummer, Name, zwei Eingaben und zwei Knöpfe in EINER Flexzeile brachen bei der Breite
 * der Prozessspur (~460 px) unschön um – und die beiden 30-px-Quadrate schwammen darin
 * herum. Jetzt **zwei Zeilen**, durch eine Haarlinie vom Nachbarn getrennt: oben, wer es
 * ist und was es kostet; darunter – nur wenn offen **und** erlaubt – die Eingaben mit
 * ihren Aktionen rechts.
 *
 * **Die Bestellangabe steht bei ihm** (`ref`), denn sie gehört ihm: seine Artikelnummer
 * oder sein Shop-Link. Sieht sie aus wie eine Adresse, ist sie eine – die Heuristik
 * steht an dieser einen Stelle, statt ein zweites Feld «ist Link» zu erfinden.
 */
function QuoteRow({ q, p, busy, active, price, lead, onPrice, onLead, onAction }: {
  q: PurchaseQuote; p: Filled; busy?: boolean; active: boolean;
  price: string; lead: string;
  onPrice: (v: string) => void; onLead: (v: string) => void;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
}) {
  const declined = q.state === 'abgelehnt';
  const open = !declined && q.amount == null;
  // **Ohne Lieferfrist keine Offerte** – dieselbe Regel wie im Dienst
  // (`purchase._quote`). Hier ist sie die freundliche Hälfte: der Knopf bleibt zu,
  // statt die Eingabe erst am Server scheitern zu lassen.
  const ready = price.trim() !== '' && lead.trim() !== '';
  const mayQuote = may(p, active, 'quote');
  const mayOrder = may(p, active, 'order');

  return (
    <div className="flex flex-col gap-1.5"
      style={{ borderTop: '1px solid var(--border-1)', paddingTop: 7 }}>
      <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
        <ObjId value={q.supplier_object_id} />
        <span className="flex-1 truncate text-[13px]" style={{ color: 'var(--fg-2)' }}>
          {q.supplier_name}
        </span>
        {declined && (
          <span className="flex items-center gap-1 text-[12.5px]" style={{ color: 'var(--danger)' }}>
            <CircleSlash size={12} /> Absage
          </span>
        )}
        {q.amount != null && (
          <span className="flex items-baseline gap-2 text-[13px]">
            <span style={{ fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
              {formatAmount(q.amount)} {p.currency}
            </span>
            {q.lead_days != null && (
              <span style={{ color: 'var(--fg-4)' }}>{q.lead_days} Tage</span>
            )}
          </span>
        )}
      </div>

      {q.ref && <SupplierRef value={q.ref} />}

      {open && mayQuote && (
        <div className="flex flex-wrap items-center gap-1.5">
          <input className={inputCls} {...numericInputProps} placeholder="Betrag netto"
            style={{ flex: '1 1 110px', minWidth: 104 }} value={price}
            onChange={(e) => onPrice(numericOnly(e.target.value, { decimals: true }))} />
          <input className={inputCls} {...numericInputProps} placeholder="Tage"
            style={{ flex: '0 1 70px', minWidth: 60 }} value={lead}
            onChange={(e) => onLead(numericOnly(e.target.value))} />
          {/* **Symbol, Erklärung im Hover** – und die Wörter gelten für beide Rollen:
              er gibt seine Offerte ab, wir schreiben seine auf. Ein Wort, das nur eine
              der beiden Seiten meint, wäre ein `if` in Textform. */}
          <button type="button" className="erp-actbtn erp-actbtn-primary erp-actbtn-icon"
            style={{ height: 30 }} disabled={busy || !ready}
            aria-label="Offerte erfassen"
            data-tip={ready ? 'Offerte erfassen'
              : 'Betrag und Lieferfrist – ohne Frist gibt es keinen Liefertermin'}
            onClick={() => onAction({
              action: 'quote', supplier: q.supplier_object_id,
              amount: Number(price), lead_days: Number(lead),
            })}>
            <Check size={14} />
          </button>
          <button type="button" className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon"
            style={{ height: 30 }} disabled={busy}
            aria-label="Absage" data-tip="Liefert nicht"
            onClick={() => onAction({ action: 'decline', supplier: q.supplier_object_id })}>
            <CircleSlash size={14} />
          </button>
        </div>
      )}

      {open && !mayQuote && (
        <span className="text-[12.5px]" style={{ color: 'var(--fg-4)' }}>angefragt</span>
      )}

      {q.amount != null && mayOrder && (
        <button type="button" className="erp-actbtn erp-actbtn-primary self-start"
          style={{ height: 30 }} disabled={busy}
          onClick={() => onAction({
            action: 'order', supplier: q.supplier_object_id, amount: q.amount,
          })}>
          {verbOf(p) || 'Bestellen'}
        </button>
      )}
    </div>
  );
}

/**
 * **Wie man bei ihm bestellt** – seine Artikelnummer oder sein Shop-Link (#753).
 *
 * Sie steht in der **Definition**, nicht am Beleg: sie ist eine Eigenschaft der Paarung
 * Modul × Lieferant und ändert sich nicht je Bestellung. Am Beleg wäre sie eine Angabe,
 * die man bei jedem Vorgang neu abschreibt.
 */
function SupplierRef({ value }: { value: string }) {
  const link = /^https?:\/\//i.test(value);
  if (!link) {
    return (
      <span className="truncate text-[12px]"
        style={{ color: 'var(--fg-3)', fontFamily: 'var(--font-mono)' }}>{value}</span>
    );
  }
  return (
    <a href={value} target="_blank" rel="noopener noreferrer"
      className="flex items-center gap-1 text-[12px] truncate self-start"
      style={{ color: 'var(--accent)' }} data-tip={value}>
      <ArrowUpRight size={12} style={{ flex: 'none' }} />
      <span className="truncate">Beim Lieferanten öffnen</span>
    </a>
  );
}


/**
 * **Bestellt — und die Sendungsnummer kommt danach.**
 *
 * Sie entsteht **nach** der Bestellung; sie am Bestellen mitzugeben hiesse, sie zu
 * erfinden oder das Bestellen zu verzögern, bis sie da ist. Und sie ist die eine Angabe,
 * die der Lieferant selbst beisteuert – er verschickt, er kennt sie.
 *
 * **Wie man bei ihm bestellt, steht dagegen in der Definition** (#753): seine
 * Artikelnummer, sein Shop-Link. Das ist eine Eigenschaft der Paarung Modul × Lieferant
 * und ändert sich nicht je Bestellung – hier wäre es eine Angabe, die man bei jedem
 * Vorgang neu abschreibt.
 *
 * **Verliert der Beleg seine Grundlage, ändert das System hier nichts.** Ab dieser Stufe
 * ist eine zweite Partei gebunden – es steht eine Bestellung beim Lieferanten. Also wird
 * **gemeldet** und auf die Bestätigung gewartet, statt still eine andere Menge zu
 * behaupten.
 */
function Ordered({ p, busy, active, onAction }: {
  p: Filled; busy?: boolean; active: boolean;
  onAction: (body: { action: string } & Record<string, unknown>) => void;
}) {
  const [track, setTrack] = useState(p.tracking ?? '');
  const mayNote = may(p, active, 'note');
  // **Auto-Save wie überall im Haus** – kein Speichern-Knopf. Er war die einzige Stelle
  // im ERP mit einem, und er tat scheinbar nichts: der getippte Wert stand ja schon da,
  // gespeichert wurde still, und sichtbar änderte sich nur, dass der Knopf ausgraute.
  const flush = useAutosave(
    track, mayNote && !busy && track !== (p.tracking ?? ''),
    () => onAction({ action: 'note', tracking: track }),
  );

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
          {/* **Ein Satz für beide Rollen.** «mit Lieferant klären» war an das Personal
              adressiert – der Lieferant las eine Aufforderung an sich selbst, jemand
              anderen anzurufen. «Zu klären» stimmt für beide. */}
          <span>
            Bestellt für <b style={{ fontVariantNumeric: 'tabular-nums' }}>{total(p)}</b>,
            gebraucht <b style={{ fontVariantNumeric: 'tabular-nums' }}>{p.clarify_quantity}</b>
            {' '}– zu klären.
          </span>
          {may(p, active, 'clarified') && (
            <button type="button" className="erp-actbtn erp-actbtn-neutral"
              style={{ height: 28 }} disabled={busy}
              onClick={() => onAction({ action: 'clarified' })}>
              Lieferant hat zugestimmt
            </button>
          )}
        </div>
      )}

      {/* **Die Sendungsnummer – und nur sie** (#753). Wo man bei diesem Lieferanten
          bestellt, steht in der Definition und damit an seiner Angebotszeile; der Termin
          ist aus Bestelldatum und Lieferfrist ableitbar. Beides hier tippen zu lassen
          wären zweite Aussagen über dieselbe Sache.

          **Der Lieferant darf sie eintragen** – er verschickt, er kennt sie. Dass er
          darf, sagt `can`, nicht eine Rollenabfrage.

          **Gesperrt ist keine Lese-Anzeige.** Ein ausgegrautes Eingabefeld lädt zum
          Klicken ein und tut dann nichts; was feststeht, steht als Wert da. */}
      {mayNote ? (
        <div style={{ maxWidth: 340 }}>
          <Label>Sendungsnummer</Label>
          <input className={inputCls} value={track}
            placeholder="sobald sie vorliegt"
            onChange={(e) => setTrack(e.target.value)}
            onBlur={flush}
            onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); flush(); } }} />
        </div>
      ) : p.tracking ? (
        <div style={{ maxWidth: 340 }}>
          <ReadField label="Sendungsnummer" value={p.tracking} mono />
        </div>
      ) : null}

      {/* **Das Wort kommt vom Beleg** (`undo`): ab der Bestellung heisst «zurück»
          stornieren – dort liegt eine Bestellung beim Lieferanten. Wo der Einkauf eine
          Wahl war, ist das Modul danach wieder frei und kann selbst bringen; wo er der
          Zweck war, bleibt der Beleg als Absage stehen. */}
      {may(p, active, 'revoke') && (
        <button type="button" className="erp-actbtn erp-actbtn-danger self-start"
          style={{ height: 28 }} disabled={busy}
          onClick={() => onAction({ action: 'revoke' })}>
          <Undo2 size={13} /> {p.undo}
        </button>
      )}
    </div>
  );
}
