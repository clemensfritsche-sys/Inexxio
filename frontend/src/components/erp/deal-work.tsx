'use client';

import { useCallback, useState } from 'react';
import {
  AlertTriangle, ArrowUpRight, CalendarClock, Check, ChevronDown, CircleSlash, FileText,
  Lock, Send, Undo2, Wallet,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { DealEmbed, DealParty, DealQuote } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import {
  Label, ReadField, inputCls, numericInputProps, numericOnly,
} from '@/components/erp/fields';
import {
  DEAL_PARTY, DEAL_STAGE, DEAL_TASK, QUOTE_STATE, dealDirection,
} from '@/lib/modules';
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

      <Row label={d.stages[0]?.label ?? ''} done={!!d.stages[0]?.done}
        active={!!d.stages[0]?.active && !cancelled}>
        <Offer d={d} busy={busy} active={active && !!d.stages[0]?.active}
          onAction={onAction} />
      </Row>

      <Row label={d.stages[1]?.label ?? ''} done={agreed && !cancelled}
        active={!!d.stages[1]?.active && !cancelled}>
        {agreed && <Agreed d={d} busy={busy} active={active} onAction={onAction} />}
      </Row>

      {/* **Das Geld – eine Zeile, keine Stufe.** Sie steht dort, wo man sie erwartet
          (dritte Position), und ist ab der Zusage bedienbar; die Kette darüber sagt
          weiterhin nur, was **zugesagt** ist. */}
      {/* ►►► **Die Geld-Zeile hängt an `can`, an sonst nichts.** ◄◄◄

          Sie bekam `active` wie die beiden Stufen darüber – und `active` heisst «dieses
          Modul ist gerade dran». Bei einem **Zahlungsziel** ist es das längst nicht mehr,
          wenn das Geld kommt: gemessen erlaubte der Dienst Rechnung und Zahlung an einem
          abgeschlossenen Auftrag, die Karte bot **null** Knöpfe an. Eine erfundene Sperre,
          die der Dienst nicht kennt – und die erfundene hat keinen Schlüssel (dieselbe
          Fehlerform wie damals bei «nicht bestanden», PROCESS_CORE §4.5).

          Die beiden Stufen behalten `active`: dort ist es richtig – man verhandelt nicht
          an einem Modul, das nicht dran ist. */}
      <Row last label={d.money_label} done={!!d.settled && !!Number(d.charged ?? 0)}
        active={agreed && !cancelled}>
        {agreed && <Money d={d} busy={busy} onAction={onAction} />}
      </Row>

      {cancelled && (
        <div className="flex items-center gap-1.5 mt-1 text-[12.5px]"
          style={{ color: 'var(--danger)' }}>
          <CircleSlash size={13} /> {d.stage_label}
        </div>
      )}

      {/* ►►► **Der Modul-Abschluss steht AM ENDE der Karte** (Testnotiz #829). ◄◄◄

          Er stand in der Stufe «Auftrag», also **mitten** in der Kette – und darunter kam
          noch die Geld-Zeile. Ein Knopf, der ein Modul abschliesst, sagt damit «hier ist
          Schluss», während sichtbar noch etwas folgt; man liest ihn als Abschluss *dieser
          Stufe* statt des Moduls. Rechnung und Zahlung gehören zum Modul, auch wenn sie
          nachgelagert kommen – also steht der Abschluss hinter ihnen.

          **Warum es nicht weitergeht, steht da, wo man weiterklicken würde**: die Sperre
          (`prepaid`) ersetzt an genau dieser Stelle den Knopf. Der Server weist ebenso ab
          (`deal.assert_completable`) – dies ist die freundliche Hälfte. */}
      {agreed && active && (d.prepaid && !d.settled ? (
        <p className="text-[12.5px] mt-2" style={{ color: 'var(--warning)' }}>
          Erst nach Zahlungseingang: {formatAmount(d.paid)} von {formatAmount(d.amount)}
          {' '}bezahlt.
        </p>
      ) : <div className="mt-2">{children}</div>)}
    </div>
  );
}

/**
 * **Eine Zeile der Kette** – Punkt, Linie, Beschriftung, Inhalt.
 *
 * Dieselbe Regel wie die Hauptachse, eine Ebene tiefer: kräftige Linie bis zur offenen
 * Stelle, Haarlinie danach. Ein Bauteil statt dreimal derselbe Aufbau – sonst laufen die
 * drei Zeilen beim ersten Eingriff auseinander.
 *
 * ►►► **Die Beschriftung steht auf Höhe ihres Punktes** (Testnotiz #798). ◄◄◄
 *
 * Punkt und Wort standen beide mit einem geratenen `marginTop` da – der eine 3 px, das
 * andere auf der Grundlinie seiner Zeilenhöhe. Zwei Ränder, die sich zufällig treffen
 * müssen, treffen sich beim ersten anderen Schriftgrad nicht mehr. Jetzt teilen sie
 * **eine** Zeilenhöhe (`HEAD_H`) und werden darin zentriert: die Ausrichtung ist eine
 * Eigenschaft der Zeile, keine zweier Abstände.
 *
 * **Und die aktive Zeile ist die lauteste.** Wo man steht, sagt die Karte ohne ein Wort
 * mehr: gefüllter Punkt in der Akzentfarbe, Beschriftung in Versalien und kräftig. Die
 * übrigen bleiben Struktur – keine Fläche, keine zweite Farbe.
 */
const HEAD_H = 18;

/**
 * **Alle Knöpfe einer Angebotszeile sind exakt gleich hoch** (#810).
 *
 * Zwei Knöpfe nebeneinander, die sich um einen Pixel unterscheiden, lesen sich als
 * Rangfolge – gemeint ist aber «entweder das oder das». Die Höhe steht darum an **einer**
 * Stelle; die Breite eines Symbol-Knopfes gibt `.erp-actbtn-icon` vor (32 px, quadratisch).
 */
const ACT_H = 30;

function Row({ label, done, active, last, children }: {
  label: string; done?: boolean; active?: boolean;
  last?: boolean; children?: React.ReactNode;
}) {
  return (
    <div className="flex gap-2.5">
      <div className="flex flex-col items-center" style={{ width: 14, flex: 'none' }}>
        {/* Der Punkt sitzt in einer Box der Zeilenhöhe und ist darin zentriert – genau
            so wie die Beschriftung daneben. */}
        <span className="flex items-center justify-center"
          style={{ height: HEAD_H, flex: 'none' }}>
          <span style={{
            width: 10, height: 10, borderRadius: 999, display: 'block',
            background: done ? 'var(--fg-2)' : active ? 'var(--accent)' : 'transparent',
            border: done || active ? 'none' : '1px solid var(--border-2)',
          }} />
        </span>
        {!last && (
          <div style={{
            flex: 1, width: done ? 2 : 1, minHeight: 10,
            background: done ? 'var(--fg-2)' : 'var(--border-2)',
          }} />
        )}
      </div>
      <div className="flex-1 min-w-0" style={{ paddingBottom: last ? 0 : 14 }}>
        <div className="flex items-center" style={{ height: HEAD_H }}>
          <span style={{
            font: `${active ? 800 : 600} ${active ? 11.5 : 12.5}px var(--font-body)`,
            letterSpacing: active ? '.07em' : undefined,
            textTransform: active ? 'uppercase' : undefined,
            color: active ? 'var(--accent-ink)' : done ? 'var(--fg-2)' : 'var(--fg-4)',
          }}>{label}</span>
        </div>
        {children}
      </div>
    </div>
  );
}

/**
 * **In welche Richtung — als SYMBOL, nicht als Dauertext** (#797/#799).
 *
 * Das Wort daneben sagte dieselbe Sache ein zweites Mal und war bei jeder Karte im Weg;
 * die Bedeutung steht darum im Hover – dieselbe Regel wie bei jedem Symbol-Knopf im Haus.
 *
 * **Das Symbol bildet ab, was man TUT**: Einkaufswagen ↔ Handschlag, dasselbe Paar wie
 * beim Beschaffungs-Beleg (#799). Plus und Minus waren die Buchhaltungssprache, aber
 * nicht die dessen, der davorsteht – und auf 15 px kaum unterscheidbar. Es sitzt darum
 * in einer getönten Marke wie jedes Modul-Symbol im Haus und ist gross genug, um es zu
 * erkennen, ohne hinzuzeigen.
 */
function Head({ d }: { d: Filled }) {
  const dir = dealDirection(d.direction);
  const Icon = dir.icon;
  return (
    <div className="flex items-center gap-2 flex-wrap"
      style={{ marginBottom: 8, paddingBottom: 7, borderBottom: '1px solid var(--border-1)' }}>
      {/* **Symbol UND Wort** – zusammen eine Marke, nicht ein Symbol allein auf einer
          eigenen Zeile. Solange der Satz «Was ist daran zu tun?» daneben stand, trug die
          Zeile Inhalt; ohne ihn (#805) blieb ein 28-px-Quadrat auf voller Breite übrig,
          und genau das war die Meldung: «nimmt zu viel Platz ein und ist nicht prominent
          genug» (#815). Ein Wort, das dort steht, kostet keinen Platz mehr – es füllt den,
          der ohnehin verbraucht wird. */}
      <span className="flex items-center gap-1.5 rounded-ds-sm" data-tip={dir.hint}
        style={{
          padding: '3px 8px 3px 6px', flex: 'none', cursor: 'help',
          background: 'var(--accent-soft)', color: 'var(--accent-ink)',
        }}>
        <Icon size={16} />
        <span style={{
          font: '800 11px var(--font-body)', textTransform: 'uppercase',
          letterSpacing: '.07em',
        }}>{d.label}</span>
      </span>
      {/* ►►► **Der Liefertermin — und ob er vorbei ist** (#814). ◄◄◄
          Ein Verzug ist kein Zustand, den jemand pflegt: er ist *Termin vorbei und noch
          nicht erledigt*, dieselbe Ableitung wie «überfällig» bei einer Forderung. Was man
          dann tun kann, gibt es alles schon – warten, stornieren, und das Geld läuft
          davon unabhängig weiter. */}
      {d.due_date && (
        <span className="flex items-center gap-1 text-[12px]" style={{
          color: d.late ? 'var(--danger)' : 'var(--fg-3)', flex: 'none',
        }} data-tip={d.late
          ? 'Der zugesagte Liefertermin ist vorbei und das Modul ist noch nicht erledigt.'
          : 'Zugesagter Liefertermin – Zusagedatum plus Lieferfrist.'}>
          {d.late ? <AlertTriangle size={12} /> : <CalendarClock size={12} />}
          {d.late ? 'überfällig seit ' : 'Liefertermin '}{localDate(d.due_date)}
        </span>
      )}
      <span className="flex-1" style={{ minWidth: 0 }} />
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
  // ►►► **Gehalten wird die Wahl nur, BIS sie als Zeile dasteht** (#794 → #820). ◄◄◄
  //
  // Sie wird gehalten, weil das Feld sonst im Moment des Klicks leer dasteht – die Wahl
  // ist noch nicht gespeichert (#794). Sobald der Server sie als Angebotszeile
  // zurückgibt, ist sie es aber, und dann steht derselbe Partner **zweimal** da: einmal
  // als Zeile, einmal im Feld darunter. Das Feld ist ein **Hinzufüger**, kein
  // Auswahlfeld – es zeigt, was man als Nächstes tun kann, nicht was getan ist.
  //
  // Eine **Ableitung**, kein zweiter Zustand: ein `setPicked(null)` an der Antwort wäre
  // die Stelle, die man beim nächsten Pfad vergisst.
  const held = picked && !d.quotes.some((q) => q.party_object_id === picked.object_id)
    ? picked : null;
  const find = useCallback(
    (q: string) => api.searchDealParties(q).catch(() => []), []);

  const open = d.allowed.filter((a) => !d.quotes.some(
    (q) => q.party_object_id === a.object_id));
  const free = d.allowed.length === 0;
  const mayAsk = may(d, active, 'ask');

  // ►►► **Wen man anfragt, wählt man AUS** (#809) – dieselbe Geste wie im
  // Beschaffen-Modul: alle sind vorgewählt, ein Klick nimmt einen heraus. Vorher war
  // «Anfragen (2)» eine Ansage statt einer Wahl; wer nur einen von zweien fragen wollte,
  // konnte es nicht sagen.
  const [dropped, setDropped] = useState<number[]>([]);
  const chosen = open.filter((o) => !dropped.includes(o.object_id));

  return (
    <div className="flex flex-col gap-2 mt-1.5">
      {d.quotes.map((q) => (
        <QuoteRow key={q.party_object_id} d={d} quote={q} busy={busy} active={active}
          onAction={onAction} />
      ))}

      {mayAsk && (free ? (
        // **Wo niemand zugelassen ist, wird gesucht** – dieselbe Bauart wie überall.
        <ObjectSelect<DealParty>
          label={d.party_word}
          value={held?.object_id ?? null}
          selected={held}
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
        <div className="flex flex-col gap-1.5">
          {open.map((o) => {
            // **Die Zeile IST der Schalter** – kein Häkchen daneben. Gewählt heisst
            // getönt mit Haken, abgewählt heisst blass; dieselbe Geste wie überall im
            // Haus, wo ein Klick die Entscheidung ist.
            const on = !dropped.includes(o.object_id);
            return (
              <button key={o.object_id} type="button" disabled={busy}
                className="flex items-center gap-2 text-[13px] rounded-ds-sm w-full"
                style={{
                  padding: '5px 8px', textAlign: 'left',
                  border: `1px solid ${on ? 'var(--border-2)' : 'transparent'}`,
                  background: on ? 'var(--bg-1)' : 'transparent',
                  opacity: on ? 1 : 0.5,
                }}
                onClick={() => setDropped((cur) => (on
                  ? [...cur, o.object_id]
                  : cur.filter((n) => n !== o.object_id)))}>
                <Check size={13} style={{
                  flex: 'none', color: on ? 'var(--success)' : 'var(--fg-4)',
                  opacity: on ? 1 : 0.35,
                }} />
                <ObjId value={o.object_id} />
                <span className="truncate" style={{ color: 'var(--fg-3)' }}>{o.name}</span>
              </button>
            );
          })}
          <button type="button" className="erp-actbtn erp-actbtn-primary self-start"
            style={{ height: 32 }} disabled={busy || chosen.length === 0}
            data-tip={chosen.length === 0
              ? 'Niemand gewählt – eine Zeile anklicken.' : undefined}
            onClick={() => onAction({
              action: 'ask', parties: chosen.map((o) => o.object_id),
            })}>
            <Send size={13} /> Bei {chosen.length} {d.ask_verb.toLowerCase()}
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
 *
 * ►►► **Offerte und Absage sind Symbol-Knöpfe** (Testnotiz #800) – wie im
 * Beschaffungs-Beleg, und aus demselben Grund: das Wort «Offerte» beschreibt einen
 * **Zustand**, während der Knopf eine **Handlung** auslöst. Ein Haken heisst «festhalten»,
 * ein durchgestrichener Kreis «kommt nicht in Frage»; was sie bedeuten, steht im Hover.
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
        {/* ►►► **Abgesagt ist abgesagt** (#811). ◄◄◄
            Betrag und Lieferfrist standen weiter da, auch nachdem jemand abgelehnt hatte –
            ein Angebot, das es nicht mehr gibt, mit einem Termin, den niemand mehr zusagt.
            Die Zahlen bleiben in den Daten (der Log ist die Historie); was hier steht, ist
            der **heutige** Stand, und der lautet: nichts. */}
        {!declined && quote.amount && (
          <span className="ix-tnum text-[12.5px] font-semibold"
            style={{ color: 'var(--fg-1)', flex: 'none' }}>
            {formatAmount(quote.amount)}
          </span>
        )}
        {!declined && quote.lead_days != null && (
          <span className="text-[12px]" style={{ color: 'var(--fg-4)', flex: 'none' }}>
            {quote.lead_days} Tage
          </span>
        )}
        {declined && (
          <span className="flex items-center gap-1 text-[12px]"
            style={{ color: 'var(--danger)', flex: 'none' }}>
            <CircleSlash size={12} /> abgesagt
          </span>
        )}
      </div>

      {/* ►►► **Wie man bei IHM bestellt** – seine Artikelnummer, sein Shop-Link (#753).
          Sie steht in der **Definition** und damit an seiner Zeile: eine Eigenschaft der
          Paarung Modul × Gegenpartei, die sich nicht je Vorgang ändert. ◄◄◄ */}
      {quote.ref && <PartyRef value={quote.ref} />}

      {active && !chosen && (may(d, active, 'quote') || may(d, active, 'agree')) && (
        <div className="flex items-end gap-2 flex-wrap" style={{ paddingBottom: 8 }}>
          {may(d, active, 'quote') && (
            <>
              <div style={{ width: 110 }}>
                {/* **Was muss ich eingeben?** – die Marke am Label sagt es, und der Knopf
                    daneben bleibt zu, solange es fehlt. Zwei Formen einer Aussage. */}
                <Label required>Betrag</Label>
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
              <button type="button"
                className="erp-actbtn erp-actbtn-primary erp-actbtn-icon"
                style={{ height: ACT_H }} disabled={busy || amount.trim() === ''}
                aria-label="Offerte erfassen"
                data-tip={amount.trim() === ''
                  ? 'Ohne Betrag gibt es keine Offerte'
                  : 'Offerte erfassen – den genannten Preis festhalten'}
                onClick={() => onAction({
                  action: 'quote', party, amount,
                  lead_days: lead === '' ? null : Number(lead),
                  payment_days: days === '' ? null : Number(days),
                })}>
                <Check size={14} />
              </button>
            </>
          )}
          {may(d, active, 'decline') && !declined && (
            <button type="button"
              className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon"
              style={{ height: ACT_H }} disabled={busy}
              aria-label="Absage" data-tip="Absage · kommt nicht in Frage"
              onClick={() => onAction({ action: 'decline', party })}>
              <CircleSlash size={14} />
            </button>
          )}
          {/* **Der Zuschlag** – das eine Verb, das in beiden Richtungen gleich heisst.
              Er ist die **naheliegende Handlung** dieser Zeile und trägt darum die
              Fläche; die beiden Symbol-Knöpfe daneben sind die Vorstufe. */}
          {may(d, active, 'agree') && !declined && (
            <button type="button" className="erp-actbtn erp-actbtn-primary"
              style={{ height: ACT_H }} disabled={busy || !quote.amount}
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
 * **Wie man bei ihm bestellt** – seine Artikelnummer oder sein Shop-Link.
 *
 * Sieht sie aus wie eine Adresse, ist sie eine: die Heuristik steht an dieser **einen**
 * Stelle, statt ein zweites Feld «ist Link» zu erfinden, das jemand falsch ankreuzt.
 */
function PartyRef({ value }: { value: string }) {
  const link = /^https?:\/\//i.test(value);
  if (!link) {
    return (
      <span className="flex items-baseline gap-1.5 text-[12px]" style={{ paddingBottom: 4 }}>
        <span style={{ color: 'var(--fg-4)', flex: 'none' }}>{DEAL_TASK}</span>
        <span className="ix-tnum truncate" style={{ color: 'var(--fg-3)', minWidth: 0 }}
          data-tip={value}>{value}</span>
      </span>
    );
  }
  return (
    <a href={value} target="_blank" rel="noopener noreferrer" data-tip={value}
      className="flex items-center gap-1 text-[12px] truncate self-start"
      style={{ color: 'var(--accent)', paddingBottom: 4, minWidth: 0 }}>
      <ArrowUpRight size={12} style={{ flex: 'none' }} />
      <span className="truncate">Beim {DEAL_PARTY} öffnen</span>
    </a>
  );
}

/**
 * **Der bestätigte Auftrag** – was feststeht, steht als **Wert** da, nicht in einem
 * gesperrten Feld. Und darin die Bestätigung, die das Modul abschliesst.
 */
function Agreed({ d, busy, active, onAction }: {
  d: Filled; busy?: boolean; active: boolean; onAction: (body: Action) => void;
}) {
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
      {/* ►►► **Kein Referenz-Feld mehr** (#812). ◄◄◄
          «Ich checke nicht, warum hier dieses Eingabefeld ist» – zu Recht: es beantwortete
          keine Frage, die jemand hat. Die **Rechnungsnummer** erzeugt der Dienst längst
          selbst (`<Auftragsnummer>[-n]`), und was bei diesem Partner zu tun ist, steht an
          seiner Angebotszeile. Damit hatte die Handlung `note` keinen Aufrufer mehr und ist
          mitgegangen. */}
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
 * die Oberfläche rechnet nichts nach.
 *
 * ►►► **Und sie stehen ALLE da — die Rangfolge sagt die Fläche, kein Umweg.** ◄◄◄
 *
 * Sie lagen einmal unter «Weitere»: ein Auswahlmenü ist die richtige Form für viele
 * gleichrangige Dinge, hier waren es drei – und eines davon (der Storno) ist die
 * Gegenhandlung des ganzen Vorgangs. Was man jetzt tun kann, muss man **sehen**; welches
 * davon das naheliegende ist, sagt die Ausprägung des Knopfes (`-primary` ↔ `-neutral`
 * ↔ `-danger`), nicht ein Klick, der es erst hervorholt.
 */
function Money({ d, busy, onAction }: {
  d: Filled; busy?: boolean; onAction: (body: Action) => void;
}) {
  // **Hier gilt allein `can`** – siehe die Begründung an der Aufrufstelle.
  const active = true;
  const [form, setForm] = useState<'' | 'charge' | 'payment'>('');
  // Ohne Zahlen gibt es nichts zu zeigen – so sieht es eine Gegenpartei.
  if (d.open == null) return null;

  const openAmount = Number(d.open);
  const nothingYet = !Number(d.charged ?? 0) && !Number(d.paid ?? 0);
  const overdue = d.entries.some((e) => e.overdue);
  // **Die naheliegende Handlung**: erst fordern, dann kassieren.
  const primary = d.next_charge != null ? 'charge'
    : d.next_payment != null ? 'payment' : '';
  // Ein Knopf trägt Fläche, wenn er der Vorschlag ist – sonst bleibt er ein Umriss.
  const tone = (mine: string) => (mine === primary
    ? 'erp-actbtn erp-actbtn-primary' : 'erp-actbtn erp-actbtn-neutral');

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
              {/* ►►► **Storniert wird, nicht gelöscht** (#823/#824). ◄◄◄
                  Eine Rechnungsnummer ist vergeben, ein Beleg ist draussen – das Symbol
                  darf darum kein Papierkorb sein: er verspricht, dass die Zeile
                  verschwindet. Was passiert, ist eine **Gegenbuchung**; beide Zeilen
                  bleiben stehen, und `reverses` markiert die stornierte. Eine
                  Gegenbuchung selbst lässt sich nicht stornieren – dann bietet der
                  Server das Verb an dieser Zeile gar nicht erst an. */}
              {e.reverses != null && (
                <span className="text-[11.5px]" style={{ color: 'var(--fg-4)', flex: 'none' }}>
                  Storno
                </span>
              )}
              {e.reversed && (
                <span className="text-[11.5px]" style={{ color: 'var(--fg-4)', flex: 'none' }}>
                  storniert
                </span>
              )}
              {may(d, active, 'reverse') && !e.reversed && e.reverses == null && (
                <button type="button"
                  className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon"
                  style={{ height: 26 }}
                  disabled={busy} aria-label="Zeile stornieren"
                  data-tip="Stornieren – es entsteht eine Gegenbuchung; beide Zeilen bleiben stehen."
                  onClick={() => onAction({ action: 'reverse', entry: e.id })}>
                  <CircleSlash size={13} />
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="flex items-center gap-2 flex-wrap">
        {may(d, active, 'charge') && (
          <button type="button" className={tone('charge')} disabled={busy}
            style={{ height: 30 }}
            data-tip="Eine Forderung buchen – ein negativer Betrag ist die Gutschrift."
            onClick={() => setForm(form === 'charge' ? '' : 'charge')}>
            <FileText size={13} /> {d.charge_word}
          </button>
        )}
        {may(d, active, 'pay') && (
          <button type="button" className={tone('payment')} disabled={busy}
            style={{ height: 30 }}
            data-tip="Geld buchen – ein negativer Betrag ist die Erstattung."
            onClick={() => setForm(form === 'payment' ? '' : 'payment')}>
            <Wallet size={13} /> {d.payment_word}
          </button>
        )}
        {/* **Die eine Gegenhandlung** – und ihr Wort kommt vom Server (`undo`). Sie
            trägt die Warnfarbe, nicht die Fläche: sichtbar, aber nie der Vorschlag. */}
        {may(d, active, 'revoke') && d.undo && (
          <button type="button" className="erp-actbtn erp-actbtn-danger" disabled={busy}
            style={{ height: 30 }}
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
        <button type="button" className="erp-actbtn erp-actbtn-primary"
          style={{ height: 30 }} disabled={busy || amount.trim() === ''}
          onClick={() => onSubmit({
            action: kind === 'charge' ? 'charge' : 'pay', amount, reference: ref,
          })}>
          <Check size={13} /> Buchen
        </button>
        <button type="button" className="erp-actbtn erp-actbtn-neutral"
          style={{ height: 30 }} onClick={onCancel}>Abbrechen</button>
      </div>
    </div>
  );
}
