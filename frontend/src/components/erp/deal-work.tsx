'use client';

import { useCallback, useState } from 'react';
import { CircleSlash, FileText, Lock, Trash2, Undo2, Wallet } from 'lucide-react';
import { api } from '@/lib/api';
import type { DealEmbed, DealParty } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import {
  Label, ReadField, inputCls, numericInputProps, numericOnly,
} from '@/components/erp/fields';
import { DEAL_STAGE, dealDirection } from '@/lib/modules';
import { formatAmount, localDate } from '@/lib/utils';

/**
 * ►►► **Der Geldvorgang an der Ausführungsstelle — drei Stufen und zwei Achsen.** ◄◄◄
 *
 * `Angebot → Zusage → Abgeschlossen`, in beide Richtungen dieselben. Was den Einkauf vom
 * Verkauf unterscheidet, sind **Wörter** – und die reisen fertig mit dem Vorgang
 * (`DealEmbed.label`, `stages[].label`, `party_word`, `charge_word`). Diese Komponente
 * braucht dafür **kein einziges `if` auf die Richtung**; sie zeichnet, was sie bekommt.
 *
 * **Und sie bewegt keine Stücke.** Der Scan, der das Modul abschliesst, steht als
 * `children` in der Stufe «Zusage» – dieselbe Bauart wie überall: kein zweiter
 * Bestätigungsweg daneben.
 *
 * ## Die Knöpfe hängen an `can`, nie an einer Rollen- oder Stufenabfrage
 *
 * Was hier möglich ist, sagt der Server (`services/deal.ACTIONS`) – und **dieselbe**
 * Tabelle weist in `apply` ab. Wäre das nur ein Anzeige-Hinweis, liefen Knopf und Tür
 * beim nächsten Verb auseinander; ein Knopf, der nie etwas tun kann, ist kein Angebot.
 *
 * ## Gerechnet wird nichts im Browser
 *
 * *Berechnet*, *bezahlt*, *offen* und *noch nicht berechnet* sind Ableitungen des Servers
 * (`domain/deal.balance`). Eine zweite Formel hier wiche ab, und ihre Zahl sähe trotzdem
 * richtig aus. Beträge über `formatAmount`, Zahlen tabellarisch (`.ix-tnum`).
 */
type Filled = Omit<DealEmbed, 'stages' | 'entries' | 'allowed' | 'can'> & {
  stages: NonNullable<DealEmbed['stages']>;
  entries: NonNullable<DealEmbed['entries']>;
  allowed: NonNullable<DealEmbed['allowed']>;
  can: NonNullable<DealEmbed['can']>;
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
  /** Der Scan, der das Modul abschliesst. */
  children?: React.ReactNode;
}) {
  // Die Listen sind serverseitig immer gesetzt; der generierte Typ lässt sie optional,
  // weil Pydantic-Defaults dort so ankommen. Einmal hier vereinheitlicht statt an jeder
  // Lesestelle ein `?? []`.
  const d: Filled = {
    ...deal, stages: deal.stages ?? [], entries: deal.entries ?? [],
    allowed: deal.allowed ?? [], can: deal.can ?? [],
  };
  const cancelled = d.stage === DEAL_STAGE.cancelled;
  const dir = dealDirection(d.direction);

  return (
    <div className="flex flex-col">
      <Head d={d} />
      {d.stages.map((stage, i) => {
        const last = i === d.stages.length - 1;
        // **Die Regel der Hauptachse, eine Ebene tiefer**: kräftig bis zur offenen
        // Stelle, Haarlinie danach. Storniert heisst: keine Stufe ist mehr aktiv – die
        // gegangene Kette bleibt aber stehen, wo sie stand.
        const walked = stage.done;
        const now = stage.active && !cancelled;
        return (
          <div key={stage.key} className="flex gap-2.5">
            <div className="flex flex-col items-center" style={{ width: 14, flex: 'none' }}>
              <Dot done={stage.done} active={now} />
              {!last && (
                <div style={{
                  flex: 1, width: walked ? 2 : 1, minHeight: 14,
                  background: walked ? 'var(--fg-2)' : 'var(--border-2)',
                }} />
              )}
            </div>
            <div className="flex-1 min-w-0" style={{ paddingBottom: last ? 0 : 12 }}>
              <span style={{
                font: `${now ? 700 : 600} 12.5px var(--font-body)`,
                color: now ? 'var(--fg-1)' : stage.done ? 'var(--fg-2)' : 'var(--fg-4)',
              }}>{stage.label}</span>
              {/* **Eine Stufe zeigt, was sie trägt – auch wenn sie vorbei ist.**
                  Gehandelt wird nur dort, wo die Stufe dran ist UND ihr Modul. */}
              {stage.key === DEAL_STAGE.offer && (stage.active || stage.done) && (
                <Agreement d={d} busy={busy} active={active && !!stage.active}
                  verb={stage.verb ?? ''} onAction={onAction} />
              )}
              {stage.key === DEAL_STAGE.agreed && (stage.active || stage.done) && (
                <Work d={d} active={active && !!stage.active}>{children}</Work>
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
          Eine Zahlung macht aus einem Angebot keine Zusage, und **nach** einem Storno
          ist eine Erstattung der Normalfall, nicht die Ausnahme. */}
      <Money d={d} busy={busy} active={active} dirIcon={dir.icon} onAction={onAction} />
    </div>
  );
}

/**
 * **Worum es geht — und in welche Richtung.**
 *
 * Der Satz steht in der Definition (Pflicht beim Modellieren) und lautet bei jedem
 * Vorgang dieses Moduls gleich; ihn am Band abzufragen wäre ein Feld, das immer dasselbe
 * aufnimmt. Daneben das Zeichen der Richtung: hinein ↔ hinaus.
 */
function Head({ d }: { d: Filled }) {
  const dir = dealDirection(d.direction);
  const Icon = dir.icon;
  return (
    <div className="flex items-center gap-2 flex-wrap"
      style={{ marginBottom: 10, paddingBottom: 8, borderBottom: '1px solid var(--border-1)' }}>
      <span data-tip={dir.hint} style={{ color: 'var(--fg-3)', display: 'flex' }}>
        <Icon size={14} />
      </span>
      <span style={{ font: '700 11px var(--font-body)', textTransform: 'uppercase',
        letterSpacing: '.07em', color: 'var(--fg-4)' }}>{d.label}</span>
      {d.subject && (
        <span className="text-[12.5px] min-w-0" style={{ color: 'var(--fg-2)' }}>
          {d.subject}
        </span>
      )}
      {/* **Die Sperre ist eine Auskunft, keine Warnung.** Sie steht als Eigenschaft
          dieses Moduls da, nicht als Fehler – gesperrt ist erst, wer abschliessen will,
          bevor bezahlt ist, und das sagt dann der Server. */}
      {d.prepaid && (
        <span className="flex items-center gap-1 text-[12px]"
          data-tip="Dieses Modul schliesst erst ab, wenn der zugesagte Betrag bezahlt ist."
          style={{ color: 'var(--fg-3)' }}>
          <Lock size={11} /> Erst zahlen
        </span>
      )}
    </div>
  );
}

/**
 * ►►► **Die Zusage — mit wem, über wie viel, zu welcher Frist.** ◄◄◄
 *
 * Alles in **einem** Formular, weil es eine Sache ist. Und **eine** Schaltfläche, deren
 * Wort die Stufe nennt (`stage.verb` – «Zusagen» ↔ «Beauftragen»): ein Literal hier wäre
 * die zweite Aussage darüber, in welche Richtung dieser Vorgang zeigt.
 *
 * **Zugelassene Gegenparteien oder freie Suche** – dieselbe Komponente (`ObjectSelect`),
 * nur eine andere Quelle. Steht in der Definition eine Liste, gilt sie; steht keine da,
 * heisst das **frei** und nicht «niemand».
 */
function Agreement({ d, busy, active, verb, onAction }: {
  d: Filled; busy?: boolean; active: boolean; verb: string;
  onAction: (body: Action) => void;
}) {
  const [party, setParty] = useState<number | null>(d.party_object_id ?? null);
  const [amount, setAmount] = useState(d.amount ?? '');
  const [days, setDays] = useState(d.due_days == null ? '' : String(d.due_days));
  const [ref, setRef] = useState(d.reference ?? '');

  // **Die zugelassene Liste, wo es sie gibt – sonst die Suche.** Beide liefern dieselbe
  // Form, also braucht das Feld keine Fallunterscheidung.
  const find = useCallback(
    (q: string): Promise<DealParty[]> => {
      if (d.allowed.length) {
        const needle = q.trim().toLowerCase();
        return Promise.resolve(d.allowed.filter(
          (o) => !needle || String(o.object_id).includes(needle)
            || (o.name ?? '').toLowerCase().includes(needle)));
      }
      return api.searchDealParties(q).catch(() => []);
    },
    [d.allowed],
  );

  // Steht die Zusage, ist sie ein **Wert** und kein gesperrtes Feld: was feststeht,
  // steht als Text da (dieselbe Regel wie am Beschaffungs-Beleg, #749).
  if (!active) {
    return (
      <div className="grid gap-2 mt-1.5"
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
        {d.reference && <ReadField label="Referenz" value={d.reference} />}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2.5 mt-1.5">
      <ObjectSelect<DealParty>
        label={d.party_word}
        value={party}
        selected={party && d.party_object_id === party
          ? { object_id: party, name: d.party_name ?? '' } : null}
        find={find}
        scanLabel={d.party_word}
        placeholder="Nummer oder Name"
        onChange={(nr) => setParty(nr)}
      />
      <div className="grid gap-2"
        style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))' }}>
        <div>
          <Label required>Betrag</Label>
          <input className={`${inputCls} ix-tnum`} {...numericInputProps}
            value={amount} aria-label="Betrag" placeholder="0.00"
            onChange={(e) => setAmount(numericOnly(e.target.value))} />
        </div>
        <div>
          <Label>Zahlungsfrist (Tage)</Label>
          <input className={`${inputCls} ix-tnum`} {...numericInputProps}
            value={days} aria-label="Zahlungsfrist in Tagen" placeholder="30"
            onChange={(e) => setDays(numericOnly(e.target.value, { decimals: false }))} />
        </div>
        <div>
          <Label>Referenz</Label>
          <input className={inputCls} value={ref} aria-label="Referenz"
            placeholder="ihre Nummer"
            onChange={(e) => setRef(e.target.value)} />
        </div>
      </div>
      {may(d, active, 'agree') && (
        <div>
          <button type="button" className="erp-actbtn" disabled={busy}
            onClick={() => onAction({
              action: 'agree', party, amount,
              due_days: days === '' ? null : Number(days), reference: ref,
            })}>
            {verb || 'Zusagen'}
          </button>
        </div>
      )}
    </div>
  );
}

/**
 * **Die zugesagte Stufe trägt den Scan — und die eine Gegenhandlung.**
 *
 * Der Scan ist das, was das Modul abschliesst; er steht darin und nicht daneben, weil er
 * genau hier passiert. Und `revoke` steht **an derselben Stelle wie die Zusage**: ein
 * Modul räumt selbst auf, es gibt keinen Storno-Endpunkt daneben.
 */
function Work({ d, active, children }: {
  d: Filled; active: boolean; children?: React.ReactNode;
}) {
  return (
    <div className="mt-1.5 flex flex-col gap-2">
      {/* **Warum es nicht weitergeht, steht da, wo man weiterklicken würde.** Der Server
          weist ebenso ab (`deal.assert_completable`) – dies ist die freundliche Hälfte. */}
      {active && d.prepaid && !d.settled && (
        <p className="text-[12.5px]" style={{ color: 'var(--warning)' }}>
          Erst nach Zahlungseingang: {formatAmount(d.paid)} von {formatAmount(d.amount)}
          {' '}bezahlt.
        </p>
      )}
      {active && (!d.prepaid || d.settled) && children}
    </div>
  );
}

/**
 * ►►► **Das Geld — zwei Achsen, eine Liste.** ◄◄◄
 *
 * **Forderung** und **Zahlung** sind getrennt, und genau deshalb braucht keines der
 * Szenarien einen Modus: Vorauszahlung ist «erst fordern, dann zahlen», eine Anzahlung
 * ist eine Forderung über einen Teil, eine Gutschrift eine **negative** Forderung, eine
 * Erstattung eine **negative** Zahlung.
 *
 * **Die Vorgaben tun die Arbeit**: eine neue Forderung schlägt *zugesagt − berechnet*
 * vor, eine neue Zahlung den *offenen* Betrag. Der Normalfall ist damit ein Klick.
 */
function Money({ d, busy, active, dirIcon: DirIcon, onAction }: {
  d: Filled; busy?: boolean; active: boolean;
  dirIcon: React.ElementType;
  onAction: (body: Action) => void;
}) {
  const [open, setOpen] = useState<'' | 'charge' | 'payment'>('');
  // Solange nichts zugesagt ist, gibt es keine Summe – und nichts zu zeigen.
  if (d.amount == null) return null;

  const openAmount = Number(d.open ?? 0);
  const owed = openAmount < 0;
  const nothingYet = !Number(d.charged ?? 0) && !Number(d.paid ?? 0);
  const overdue = d.entries.some((e) => e.overdue);
  return (
    <div className="flex flex-col gap-2" style={{
      marginTop: 12, paddingTop: 10, borderTop: '1px solid var(--border-1)',
    }}>
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
            : openAmount === 0 ? 'Bezahlt' : owed ? 'Wir schulden' : d.open_word}
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

      {(d.entries.length > 0) && (
        <div className="flex flex-col">
          {d.entries.map((e) => (
            // **Die Zeile darf umbrechen, und die Referenz darf schrumpfen.** Gemessen
            // in Chromium: eine QR-Referenz («QR 21 00000 00003 …») ist breiter als ein
            // Telefon, und ohne `min-width: 0` gibt eine Flex-Zelle nicht nach – sie
            // quetschte das Datum daneben auf **0 px** und schob die Zeile aus der Karte
            // (5 px bei 375, 44 px bei 320). Nicht sichtbar am Schreibtisch.
            <div key={e.id} className="flex items-center gap-2 py-1 text-[12.5px] flex-wrap"
              style={{ borderTop: '1px solid var(--border-1)' }}>
              <span style={{ color: 'var(--fg-4)', display: 'flex', flex: 'none' }}
                data-tip={e.kind === 'charge' ? d.charge_word : d.payment_word}>
                {e.kind === 'charge' ? <FileText size={13} /> : <DirIcon size={13} />}
              </span>
              <span className="ix-tnum font-semibold" style={{
                color: e.overdue ? 'var(--danger)' : 'var(--fg-1)', flex: 'none',
              }}>{formatAmount(e.amount)}</span>
              {/* **Die Referenz nimmt den Rest und wird gekappt, das Datum nicht.**
                  Umgekehrt war es falsch: das Datum bekam den Rest (`flex-1`) und
                  behielt bei einer 227 px breiten QR-Referenz **39 px** – «20.8.2026»
                  hat keine Umbruchstelle und malte sich 17 px über seine Box hinaus
                  (gemessen: 380,1 px bei 375 px Fenster, und **kein** Element-Rahmen
                  zeigte es, nur der Text selbst). Eine Referenz darf gekappt werden –
                  ihr voller Wert steht im Hover –, ein Datum nicht. */}
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
        {may(d, active, 'charge') && (
          <button type="button" className="erp-actbtn" disabled={busy}
            onClick={() => setOpen(open === 'charge' ? '' : 'charge')}>
            <FileText size={13} /> {d.charge_word}
          </button>
        )}
        {may(d, active, 'pay') && (
          <button type="button" className="erp-actbtn" disabled={busy}
            onClick={() => setOpen(open === 'payment' ? '' : 'payment')}>
            <Wallet size={13} /> {d.payment_word}
          </button>
        )}
        {/* **Die eine Gegenhandlung** – und ihr Wort kommt vom Server (`undo`). */}
        {may(d, active, 'revoke') && d.undo && (
          <button type="button" className="erp-actbtn" disabled={busy}
            onClick={() => onAction({ action: 'revoke' })}>
            <Undo2 size={13} /> {d.undo}
          </button>
        )}
      </div>

      {open !== '' && (
        <Entry kind={open} d={d} busy={busy}
          onCancel={() => setOpen('')}
          onSubmit={(body) => { setOpen(''); onAction(body); }} />
      )}
    </div>
  );
}

/**
 * **Eine Zeile Geld erfassen** – dasselbe Formular für beide Achsen.
 *
 * Der Unterschied ist eine Vorgabe und ein Feld: eine Forderung schlägt *zugesagt −
 * berechnet* vor und hat eine Fälligkeit, eine Zahlung schlägt den *offenen* Betrag vor.
 * Zwei Formulare wären dieselbe Sache zweimal.
 *
 * **Negativ ist erlaubt** (`signed`): das ist die Gutschrift bzw. die Erstattung – keine
 * dritte Art, sondern ein Vorzeichen.
 */
function Entry({ kind, d, busy, onCancel, onSubmit }: {
  kind: 'charge' | 'payment'; d: Filled; busy?: boolean;
  onCancel: () => void; onSubmit: (body: Action) => void;
}) {
  const suggestion = kind === 'charge' ? d.uncharged : d.open;
  const [amount, setAmount] = useState(suggestion ?? '');
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

/** Der Punkt einer Stufe – gefüllt, wenn gegangen; Ring, wenn sie dran ist. */
function Dot({ done, active }: { done?: boolean; active?: boolean }) {
  return (
    <span style={{
      width: 10, height: 10, borderRadius: 999, flex: 'none', marginTop: 3,
      background: done ? 'var(--fg-2)' : 'var(--bg-1)',
      border: `${active ? 2 : 1}px solid ${
        done || active ? 'var(--fg-2)' : 'var(--border-2)'}`,
    }} />
  );
}
