'use client';

import { Fragment, useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, ArrowUpRight, CalendarClock, Check, ChevronDown, CircleSlash,
  ClipboardList, CreditCard, FileText, Lock, Send, Undo2, Wallet,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { DealEmbed, DealParty, DealQuote } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import { PayOnline } from '@/components/erp/pay-online';
import {
  Label, MICRO_LABEL, inputCls, numericInputProps, numericOnly,
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

/**
 * **Der negative Betrag zu einer Zeile** – die Vorbelegung einer Korrektur (#842).
 *
 * Als Zeichenkette gerechnet, weil Beträge als Zeichenkette reisen: wo es auf den Rappen
 * ankommt, wird nicht durch `float` gerechnet, auch nicht für einen Vorschlag.
 */
function negate(amount: string): string {
  return amount.startsWith('-') ? amount.slice(1) : `-${amount}`;
}

/**
 * **Die Nummer der stornierten Zeile** – für den Hover an einer Gegenbuchung (#841).
 *
 * Eine **Ableitung** aus derselben Liste, die ohnehin dasteht: der Verweis ist eine Id,
 * und die Nummer daneben steht eine Zeile höher. Ein zweites Feld vom Server wäre
 * dieselbe Angabe ein zweites Mal.
 */
function reversedRef(d: Filled, entryId: number): string {
  const src = d.entries.find((x) => x.id === entryId);
  return src?.reference ? `Storno zu ${src.reference}` : 'Storno';
}

/**
 * ►►► **Die Steuer einer Zeile – im HOVER, nicht in der Zeile.** ◄◄◄
 *
 * Sie gehört auf den Beleg (MWSTG Art. 26 Bst. f) und steht darum bei der Zahl, um die
 * es geht: Netto, je Satz die Steuer, und – wenn sie abweicht – das Leistungsdatum. In
 * die Zeile geschrieben wären es bei zwei Sätzen fünf zusätzliche Zahlen neben Betrag,
 * Referenz und Datum; bei 320 px ist dort kein Platz, und die ERP-Regel des Hauses sagt
 * es ohnehin: Infotexte im Hover.
 *
 * ``''`` heisst «nichts zu sagen» – eine **Zahlung** trägt keine Steuer, sie begleicht
 * sie. Der Aufrufer gibt dann keinen Hinweis mit, statt einen leeren zu zeigen.
 */
function taxTip(d: Filled, e: Filled['entries'][number]): string {
  const parts = (e.vat ?? []).map(
    (v) => `${d.vat_label} ${v.rate} % ${formatAmount(v.tax, d.currency_decimals)} (netto ${formatAmount(v.net, d.currency_decimals)})`);
  if (e.service_date) {
    parts.push(`${d.service_date_label} ${localDate(e.service_date)}`);
  }
  return parts.join(' · ');
}

/** **Darf man das hier?** – die einzige Frage über Rechte, die diese Komponente stellt. */
function may(d: Filled, active: boolean, action: string): boolean {
  return active && d.can.includes(action);
}

export function DealWork({
  deal, busy, active = true, orderObjectId, stepId, onAction, onPaid, children,
}: {
  deal: DealEmbed;
  busy?: boolean;
  /** Die Adresse für den einen Weg, der **kein** Verb am Vorgang ist: `…/deal/payment`. */
  orderObjectId: number;
  stepId: number;
  /**
   * **Es ist bezahlt worden** – lade den Auftrag nach.
   *
   * Kein `onAction`: eine Online-Zahlung ist keine Handlung *am Vorgang* (sie bucht
   * nichts, das tut der Webhook). Ein Verb dafür wäre eine Behauptung über eine Buchung,
   * die es in diesem Moment noch gar nicht gibt.
   */
  onPaid?: () => void;
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
      <Head d={d} busy={busy} active={active} onAction={onAction} />
      <Goods d={d} />

      <Row label={d.stages[0]?.label ?? ''} done={!!d.stages[0]?.done}
        active={!!d.stages[0]?.active && !cancelled}>
        <Offer d={d} busy={busy} active={active && !!d.stages[0]?.active}
          onAction={onAction} />
      </Row>

      <Row label={d.stages[1]?.label ?? ''} done={agreed && !cancelled}
        active={!!d.stages[1]?.active && !cancelled}>
        {agreed && <Agreed d={d} />}
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
        {agreed && <Money d={d} busy={busy} onAction={onAction}
          orderObjectId={orderObjectId} stepId={stepId} onPaid={onPaid} />}
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

          ►►► **Und warum es nicht weitergeht, steht NICHT ein zweites Mal da** (#849). ◄◄◄

          Hier stand ein Satz «Erst nach Zahlungseingang: X von Y bezahlt.» – und er sagte
          dreimal dasselbe: die Sperre selbst steht als Auskunft im **Kopf** («Erst
          zahlen», mit dem Grund im Hover), die beiden Zahlen stehen in der **Geld-Zeile**
          direkt darüber, und dass der Knopf fehlt, sieht man. Ein Hinweis, der nichts
          Neues sagt, liest sich wie eine Fehlermeldung.

          Der Knopf ist damit schlicht **nicht da**, solange die Sperre greift – dieselbe
          Form wie überall im Haus: ein Knopf, der nie etwas tun kann, ist kein Angebot.
          Der Server weist ebenso ab (`deal.assert_completable`). */}
      {agreed && active && !(d.prepaid && !d.settled) && (
        <div className="mt-2">{children}</div>
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
/**
 * ►►► **In welcher Währung wird gehandelt?** — EINE Angabe je Vorgang. ◄◄◄
 *
 * Sie steht im **Kopf** und nicht an jeder Zahl: ein Beleg hat *eine* Währung (zwei wären
 * zwei Belege), also ist sie eine Eigenschaft des Vorgangs und keine Spalte in der
 * Tabelle. Fünfzehnmal «CHF» neben fünfzehn Zahlen wäre Fläche statt Struktur.
 *
 * **Ob man sie noch wählen darf, sagt `can`** – dieselbe Tabelle, die auch das Tor ist:
 * ab der Zusage liegt draussen eine Zusage über *diese* Summe in *dieser* Währung. Der
 * Wert **verschwindet dann nicht**, er wird zur Auskunft mit dem Grund im Hover – sonst
 * beantwortet nichts mehr die Frage, worin dieser Beleg lautet.
 *
 * **Ein `<select>` ist hier richtig**: Währungen sind eine endliche Aufzählung, keine
 * Referenz auf einen Datensatz (die Regel des Hauses erlaubt genau das). Der Katalog
 * kommt vom Server – eine zweite Liste im Browser liefe beim ersten neuen Code
 * auseinander. **Umgerechnet wird nichts**: ein Kurs hat ein Datum und eine Quelle, und
 * wer ohne beides umrechnet, erfindet Zahlen.
 */
function Currency({ d, busy, active, onAction }: {
  d: Filled; busy?: boolean; active: boolean; onAction: (body: Action) => void;
}) {
  if (!may(d, active, 'currency')) {
    return (
      <span className="text-[12px] ix-tnum" style={{ color: 'var(--fg-3)', flex: 'none' }}
        data-tip={`${d.currency_label} – ab der Zusage gebunden: draussen liegt eine `
          + 'Zusage über diesen Betrag in dieser Währung.'}>{d.currency}</span>
    );
  }
  return (
    <select className="text-[12px] ix-tnum" aria-label="Währung" disabled={busy}
      value={d.currency} data-tip={d.currency_label}
      style={{
        flex: 'none', padding: '2px 4px', borderRadius: 6, background: 'transparent',
        border: '1px solid var(--border-1)', color: 'var(--fg-2)',
      }}
      onChange={(e) => onAction({ action: 'currency', currency: e.target.value })}>
      {(d.currencies ?? []).map((c) => (
        <option key={c.code} value={c.code}>{c.code}</option>
      ))}
    </select>
  );
}

function Head({ d, busy, active, onAction }: {
  d: Filled; busy?: boolean; active: boolean; onAction: (body: Action) => void;
}) {
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
      <Currency d={d} busy={busy} active={active} onAction={onAction} />
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
      {d.lines.map((line, i) => {
        const spec = line.spec ?? [];
        const key = line.article_id ?? -(i + 1);
        const shown = open === key;
        return (
          <div key={key} className="flex flex-col">
            <button type="button" className="flex items-center gap-2 py-1 text-left"
              style={{ background: 'none', border: 0, padding: '4px 0' }}
              aria-expanded={shown}
              onClick={() => setOpen(shown ? null : key)}>
              <span className="ix-tnum text-[12.5px] font-semibold"
                style={{ color: 'var(--fg-1)', flex: 'none' }}>{line.quantity}×</span>
              <span className="text-[12.5px] truncate" style={{ color: 'var(--fg-1)' }}>
                {line.article_name || 'Ohne Artikel'}
              </span>
              {line.article_object_id != null && (
                <ObjId value={line.article_object_id} />
              )}
              {spec.length > 0 && (
                <ChevronDown size={13} style={{
                  color: 'var(--fg-4)', flex: 'none',
                  transform: shown ? 'rotate(180deg)' : undefined,
                }} />
              )}
              {/* ►►► **Der Preis steht an SEINER Position** (MWSTG Art. 26). ◄◄◄

                  Steuersatz und Einzelpreis gehören der **Sache**: sechs Wellen zu 8.1 %
                  und eine Ausfuhr zu 0 % stehen auf demselben Papier. Sie unten in einem
                  eigenen Block zu wiederholen wäre dieselbe Angabe ein zweites Mal – und
                  zwei Zahlen zu einer Sache sind eine zu viel.

                  **Erst, wenn es einen gibt**: solange niemand einen Preis genannt hat,
                  steht hier nichts (eine 0.00 wäre eine Behauptung). */}
              <span className="flex-1" style={{ minWidth: 0 }} />
              {line.price != null && (
                <span className="flex items-center gap-2" style={{ flex: 'none' }}>
                  <span className="text-[11.5px] ix-tnum" style={{ color: 'var(--fg-4)' }}
                    data-tip={`${line.vat} % ${d.vat_label}`}>{line.vat} %</span>
                  <span className="text-[12.5px] ix-tnum" style={{ color: 'var(--fg-3)' }}
                    data-tip="Einzelpreis netto">{formatAmount(line.price, d.currency_decimals)}</span>
                  <span className="text-[12.5px] ix-tnum font-semibold"
                    style={{ color: 'var(--fg-1)', minWidth: 74, textAlign: 'right' }}
                    data-tip="Positionssumme netto">
                    {formatAmount(Number(line.price) * line.quantity,
                      d.currency_decimals)}
                  </span>
                </span>
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

  // ►►► **Was WIR anbieten, füllen wir VOR dem Hinausgehen** (Testnotiz #837). ◄◄◄
  //
  // Bei einer **Ausgabe** fragen wir an und warten auf seine Offerte – die Zeile geht
  // leer hinaus, und das ist ihr Sinn. Bei einer **Einnahme** nennen **wir** den Preis:
  // ein Angebot ohne Betrag ist keines, und ihn danach nachzutragen hiesse, dem Kunden
  // zwischendurch eine leere Zeile zu zeigen.
  //
  // Gefragt wird die **Angabe** (`we_quote`), nie die Richtung – der Server sagt sie,
  // und der Dienst weist ohne Betrag ab. Dies ist die freundliche Hälfte.
  //
  // **Die Zeilen kommen aus dem PROZESS, nicht aus einem «+»-Knopf**: was angeboten wird,
  // sind die Artikel der Stücke, die vor dem Modul stehen (`d.lines`). Gibt es keine
  // (Miete, Lohn, Gebühr), ist es **eine** Zeile ohne Artikel – dieselbe Mechanik mit
  // einer entarteten Zeile, kein zweiter Fall.
  const blank = useCallback((): PriceRow[] => (d.lines.length > 0
    ? d.lines.map((l) => ({ article: l.article_id ?? null, price: '', vat: d.vat_rate }))
    : [{ article: null, price: '', vat: d.vat_rate }]), [d.lines, d.vat_rate]);
  const [offer, setOffer] = useState<{ rows: PriceRow[]; lead: string; days: string }>(
    () => ({ rows: blank(), lead: '', days: '' }));
  const ready = !d.we_quote || offer.rows.some((r) => r.price.trim() !== '');

  /** **Eine Abwahl gilt für die Anfrage, die man gerade stellt** (#835) – sie fällt mit
   *  dem Absenden. Sonst blieb der zweite Partner abgewählt, nachdem man den ersten
   *  gefragt hatte: «Bei 0 anbieten», gesperrt, bis zum Refresh. */
  const send = (parties: number[]) => {
    onAction({
      action: 'ask', parties,
      ...(d.we_quote ? {
        lines: offer.rows.map((r) => ({
          article: r.article, price: r.price === '' ? '0' : r.price, vat: r.vat,
        })),
        lead_days: offer.lead === '' ? null : Number(offer.lead),
        payment_days: offer.days === '' ? null : Number(offer.days),
      } : {}),
    });
    setDropped([]);
    setOffer({ rows: blank(), lead: '', days: '' });
  };

  return (
    <div className="flex flex-col gap-2 mt-1.5">
      {d.quotes.map((q) => (
        <QuoteRow key={q.party_object_id} d={d} quote={q} busy={busy} active={active}
          onAction={onAction} />
      ))}

      {mayAsk && d.we_quote && free && (
        <OurOffer d={d} value={offer} onChange={setOffer} />
      )}
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
            if (nr !== null) send([nr]);
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
          <OurOffer d={d} value={offer} onChange={setOffer} />
          <button type="button" className="erp-actbtn erp-actbtn-primary self-start"
            style={{ height: 32 }} disabled={busy || chosen.length === 0 || !ready}
            data-tip={chosen.length === 0 ? 'Niemand gewählt – eine Zeile anklicken.'
              : !ready ? 'Ohne Preis gibt es nichts anzubieten.' : undefined}
            onClick={() => send(chosen.map((o) => o.object_id))}>
            <Send size={13} /> Bei {chosen.length} {d.ask_verb.toLowerCase()}
          </button>
        </div>
      ))}
    </div>
  );
}

/**
 * ►►► **Was WIR anbieten — die POSITIONEN sind der Preis** (MWSTG Art. 26). ◄◄◄
 *
 * Bei einer **Ausgabe** fragt man an und wartet: die Zeile geht leer hinaus, der Partner
 * füllt sie. Bei einer **Einnahme** ist es umgekehrt – wir nennen den Preis, und ein
 * Angebot ohne Preis ist keines.
 *
 * **Und ein Betrag allein trägt keinen Steuersatz.** Er hängt an der *Sache*: sechs Wellen
 * zu 8.1 % und eine Ausfuhr zu 0 % stehen auf demselben Papier. Gefragt wird darum je
 * Position **Preis (netto) und Satz**; der Angebotsbetrag ist ihre **Brutto-Summe** – eine
 * getippte Zahl daneben wäre die zweite Aussage über dieselbe Sache.
 *
 * **Gibt es keine Positionen** (Miete, Lohn, Gebühr), ist es **eine** Zeile ohne Artikel:
 * derselbe Mechanismus mit einer entarteten Zeile, kein zweiter Fall.
 */
export type PriceRow = { article: number | null; price: string; vat: string };

function OurOffer({ d, value, onChange }: {
  d: Filled;
  value: { rows: PriceRow[]; lead: string; days: string };
  onChange: (next: { rows: PriceRow[]; lead: string; days: string }) => void;
}) {
  if (!d.we_quote) return null;
  const set = (i: number, patch: Partial<PriceRow>) => onChange({
    ...value, rows: value.rows.map((r, n) => (n === i ? { ...r, ...patch } : r)),
  });
  return (
    <div className="flex flex-col gap-2">
      {value.rows.map((row, i) => {
        const line = d.lines.find((l) => l.article_id === row.article);
        return (
          <div key={row.article ?? -1} className="flex items-end gap-2 flex-wrap">
            <div className="flex items-center gap-1.5 text-[12.5px]"
              style={{ flex: '1 1 140px', minWidth: 0, paddingBottom: 7 }}>
              {line && <span className="ix-tnum font-semibold" style={{ flex: 'none' }}>
                {line.quantity}×</span>}
              <span className="truncate" style={{ color: 'var(--fg-2)' }}>
                {line?.article_name || 'Ohne Artikel'}
              </span>
            </div>
            <div style={{ width: 104 }}>
              <Label required>Preis netto</Label>
              <input className={`${inputCls} ix-tnum`} {...numericInputProps}
                value={row.price} aria-label="Preis netto" placeholder="0.00"
                onChange={(e) => set(i, { price: numericOnly(e.target.value) })} />
            </div>
            {/* **Der Katalog kommt vom Server** – ein getippter Satz ist einer, den es
                nicht gibt, und er fällt erst bei der Abrechnung auf. */}
            <div style={{ width: 116 }}>
              <Label>{d.vat_label}</Label>
              <select className={inputCls} value={row.vat} aria-label={d.vat_label ?? ''}
                onChange={(e) => set(i, { vat: e.target.value })}>
                {(d.vat_rates ?? []).map((r) => (
                  <option key={r.rate} value={r.rate}>{r.rate} %</option>
                ))}
              </select>
            </div>
          </div>
        );
      })}
      <div className="flex items-end gap-2 flex-wrap">
        <div style={{ width: 104 }}>
          <Label>Lieferfrist</Label>
          <input className={`${inputCls} ix-tnum`} {...numericInputProps} value={value.lead}
            aria-label="Lieferfrist in Tagen" placeholder="Tage"
            onChange={(e) => onChange({
              ...value, lead: numericOnly(e.target.value, { decimals: false }) })} />
        </div>
        <div style={{ width: 116 }}>
          <Label>Zahlungsfrist</Label>
          <input className={`${inputCls} ix-tnum`} {...numericInputProps} value={value.days}
            aria-label="Zahlungsfrist in Tagen" placeholder="Tage"
            onChange={(e) => onChange({
              ...value, days: numericOnly(e.target.value, { decimals: false }) })} />
        </div>
        {/* **Was das Angebot kostet, rechnet niemand im Kopf**: dieselbe Regel wie beim
            Server (je Satz auf der Summe) – nur als Vorschau, gebucht wird dort. */}
        <Sums rows={value.rows} lines={d.lines} label={d.vat_label ?? 'MWST'}
          decimals={d.currency_decimals} />
      </div>
    </div>
  );
}

/**
 * **Netto · Steuer · Brutto** – die drei Zahlen unter dem Strich.
 *
 * ►►► **Gerundet wird je SATZ auf der SUMME**, nie je Position aufsummiert. ◄◄◄ Bei zwölf
 * Zeilen weicht die Summe der gerundeten Einzelbeträge sonst um Rappen von der gerundeten
 * Summe ab, und eine MWST-Abrechnung kennt keine Rappen-Toleranz. Dieselbe Regel wie im
 * Dienst (`domain/deal.vat_split`) – hier als **Vorschau**, gebucht wird dort.
 */
function Sums({ rows, lines, label, decimals }: {
  rows: PriceRow[]; lines: Filled['lines']; label: string;
  /**
   * ►►► **Die kleinste Einheit DIESER Währung** (ISO 4217). ◄◄◄
   *
   * Auch die Vorschau rundet je Währung: ein fest auf zwei Stellen gerundeter
   * Yen-Betrag wäre hier eine andere Zahl als die, die der Dienst danach bucht – und
   * die Vorschau hätte genau den einen Zweck verfehlt, den sie hat.
   */
  decimals: number;
}) {
  const unit = 10 ** decimals;
  const buckets = new Map<string, number>();
  rows.forEach((r) => {
    const qty = lines.find((l) => l.article_id === r.article)?.quantity ?? 1;
    const net = Math.round(Number(r.price || 0) * qty * unit) / unit;
    buckets.set(r.vat, (buckets.get(r.vat) ?? 0) + net);
  });
  let net = 0; let tax = 0;
  buckets.forEach((sum, rate) => {
    net += sum; tax += Math.round(sum * Number(rate) * unit / 100) / unit;
  });
  if (net === 0 && tax === 0) return null;
  return (
    <div className="flex flex-col gap-0.5 text-[12px] ix-tnum"
      style={{ marginLeft: 'auto', textAlign: 'right', paddingBottom: 2 }}>
      <span style={{ color: 'var(--fg-4)' }}>Netto {formatAmount(net, decimals)}</span>
      <span style={{ color: 'var(--fg-4)' }}>{label} {formatAmount(tax, decimals)}</span>
      <span className="font-semibold" style={{ color: 'var(--fg-1)' }}>
        {formatAmount(net + tax, decimals)}
      </span>
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
  // ►►► **Was der Partner ändert, kommt hier an** (Testnotiz #846). ◄◄◄
  //
  // Die drei Felder sind **lokal**, damit man tippen kann, ohne dass jede Taste zum
  // Server geht – aber ein `useState`-Startwert wird genau **einmal** gelesen. Ändert die
  // Gegenpartei danach ihre Zahlungsfrist, kommt der neue Wert in `quote` an, und das Feld
  // zeigt weiter den alten: wer dann etwas anderes korrigierte und speicherte, **schrieb
  // die alte Frist zurück**. Ein stiller Rückschritt, und nichts sagte, warum.
  //
  // Nachgezogen wird darum bei einem **Wechsel des Server-Werts** – nicht bei jedem
  // Rendern: die Abhängigkeit ist der Wert selbst, also überschreibt es keine Eingabe,
  // die gerade läuft. Dieselbe Bauart wie `defaultOpen` an der Modul-Karte (#727).
  const remote = `${quote.amount ?? ''}|${quote.lead_days ?? ''}|${quote.payment_days ?? ''}`;
  useEffect(() => {
    const [a, l, p2] = remote.split('|');
    setAmount(a); setLead(l); setDays(p2);
  }, [remote]);
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
            {formatAmount(quote.amount, d.currency_decimals)}
          </span>
        )}
        {/* **Beide Fristen stehen da, und jede sagt, welche sie ist** (#846). Die
            Lieferfrist stand als blosses «14 Tage» daneben, die **Zahlungsfrist** gar
            nicht – obwohl man sie eingeben kann und der Partner sie ändert. Zwei nackte
            Tageszahlen nebeneinander wären nicht unterscheidbar, also trägt jede ihr
            Wort im Hover und ihr Symbol daneben. */}
        {!declined && quote.lead_days != null && (
          <span className="flex items-center gap-1 text-[12px] ix-tnum"
            style={{ color: 'var(--fg-4)', flex: 'none' }}
            data-tip={`Lieferfrist ${quote.lead_days} Tage`}>
            <CalendarClock size={11} />{quote.lead_days}
          </span>
        )}
        {!declined && quote.payment_days != null && (
          <span className="flex items-center gap-1 text-[12px] ix-tnum"
            style={{ color: 'var(--fg-4)', flex: 'none' }}
            data-tip={`Zahlungsfrist ${quote.payment_days} Tage`}>
            <Wallet size={11} />{quote.payment_days}
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
              {/* ►►► **Wo WIR den Preis nennen, gibt es hier kein Betragsfeld.** ◄◄◄

                  Er steht in den **Positionen** – dort hängt der Steuersatz (MWSTG
                  Art. 26), und der Angebotsbetrag ist ihre Brutto-Summe. Ein Feld
                  daneben wäre nicht nur die zweite Aussage über dieselbe Sache: der
                  Dienst weist eine so genannte Zahl ab (`_quote` liest bei einer
                  Einnahme ausschliesslich die Zeilen), es wäre also ein Knopf, der
                  garantiert scheitert.

                  Die beiden **Fristen** bleiben: sie sind in beiden Richtungen unsere
                  bzw. seine Angabe, und sie hängen nicht am Preis. */}
              {!d.we_quote && (
                <div style={{ width: 110 }}>
                  {/* **Was muss ich eingeben?** – die Marke am Label sagt es, und der
                      Knopf daneben bleibt zu, solange es fehlt. */}
                  <Label required>Betrag</Label>
                  <input className={`${inputCls} ix-tnum`} {...numericInputProps}
                    value={amount} aria-label="Betrag" placeholder="0.00"
                    onChange={(e) => setAmount(numericOnly(e.target.value))} />
                </div>
              )}
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
                style={{ height: ACT_H }}
                disabled={busy || (!d.we_quote && amount.trim() === '')}
                aria-label="Offerte erfassen"
                data-tip={!d.we_quote && amount.trim() === ''
                  ? 'Ohne Betrag gibt es keine Offerte'
                  : 'Offerte erfassen – Preis und Fristen festhalten'}
                onClick={() => onAction({
                  action: 'quote', party,
                  // **Nur senden, was man auch nennt** – wo die Positionen den Preis
                  // tragen, bleibt er, wie er ist (dieselbe Regel im Dienst).
                  ...(d.we_quote ? {} : { amount }),
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
 * **Was bei diesem Partner zu tun ist** – seine Artikelnummer, sein Shop-Link, ein Satz.
 *
 * Sieht sie aus wie eine Adresse, ist sie eine: die Heuristik steht an dieser **einen**
 * Stelle, statt ein zweites Feld «ist Link» zu erfinden, das jemand falsch ankreuzt.
 *
 * ►►► **Hier ist es eine AUSKUNFT, keine Frage** (Testnotiz #836). ◄◄◄
 *
 * «Was ist zu tun?» stand als Beschriftung vor dem Wert – ein Fragezeichen über einer
 * Antwort. Im **Editor** ist die Frage richtig, dort füllt man sie aus; an der
 * Angebotszeile steht das Ergebnis, und was es ist, sagt das Symbol (ERP-Regel: Symbole
 * statt Text, Erklärung im Hover). Ein Wort weniger in einer Zeile, die ohnehin eng ist.
 */
function PartyRef({ value }: { value: string }) {
  const link = /^https?:\/\//i.test(value);
  if (!link) {
    return (
      <span className="flex items-center gap-1.5 text-[12px]" style={{ paddingBottom: 4 }}
        data-tip={`${DEAL_TASK} ${value}`}>
        <ClipboardList size={12} style={{ color: 'var(--fg-4)', flex: 'none' }} />
        <span className="ix-tnum truncate" style={{ color: 'var(--fg-3)', minWidth: 0 }}>
          {value}</span>
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
 * ►►► **Der bestätigte Auftrag — WER, WAS ES KOSTET, ZU WELCHEN BEDINGUNGEN.** ◄◄◄
 *
 * Gemeldet war «schaut total beschissen aus. bitte komplett neu machen» (#847), und die
 * Meldung hatte recht: hier stand ein `auto-fit`-Raster aus vier gleich lauten Lesefeldern
 * – Partner, Betrag, Zahlungsfrist, Bestätigt –, das je nach Breite in eine, zwei oder
 * vier Spalten zerfiel. Alle vier gleich gross, keine Ordnung, und der **Betrag** – die
 * einzige Zahl, um die es geht – stand als drittes Kästchen von links.
 *
 * Die Ordnung ist jetzt die eines **Belegs**, weil es einer ist:
 *
 * 1. **Wer** – der Partner, eine Zeile, Nummer und Name.
 * 2. **Was es kostet** – rechtsbündig Netto · Steuer je Satz · Total, unter einer
 *    Haarlinie. Dieselbe Aufteilung, die auf der Rechnung steht (MWSTG Art. 26), und
 *    dieselbe Rechnung wie im Dienst: **je Satz auf der Summe** gerundet.
 * 3. **Zu welchen Bedingungen** – Zahlungsfrist und Zusagedatum, klein und daneben.
 *
 * ►►► **Die Positionen stehen NICHT noch einmal hier.** ◄◄◄ Sie stehen oben in `Goods`,
 * seit die Zeile ihren Preis und ihren Satz trägt – das ist die Position, und eine
 * zweite Aufzählung wäre dieselbe Angabe an zwei Orten. Hier steht nur die **Summe**.
 *
 * **Ohne Positionen bleibt der Total allein**, und das ist kein Sonderfall: bei einer
 * *Ausgabe* nennt die Gegenpartei den Preis, und die Steuer steht auf **ihrer** Rechnung
 * – wir kennen sie erst, wenn wir die Rechnung erfassen. Ein «Netto 0.00» daneben wäre
 * eine Behauptung über eine Zahl, die wir nicht haben.
 */
function Agreed({ d }: { d: Filled }) {
  const split = d.vat_split ?? [];
  return (
    <div className="flex flex-col gap-2.5 mt-1.5">
      {/* ►►► **Nummer und Name auf EINER Zeile** (Testnotiz #838) – der Name wird
          gekappt. `flex-wrap` schob ihn bei enger Spalte darunter, und dort las er sich
          wie eine zweite Angabe. */}
      <div className="flex items-center gap-2 text-[12.5px]" style={{ minWidth: 0 }}>
        <span style={{ ...MICRO_LABEL, flex: 'none' }}>{d.party_word}</span>
        {d.party_object_id ? (
          <>
            <ObjId value={d.party_object_id} />
            <span className="truncate" style={{ color: 'var(--fg-1)', minWidth: 0 }}
              data-tip={d.party_name || undefined}>{d.party_name}</span>
          </>
        ) : <span style={{ color: 'var(--fg-4)' }}>—</span>}
      </div>

      {/* ►►► **Die Abrechnung — rechtsbündig, tabellarisch, mit einer Haarlinie.** ◄◄◄
          Zahlen werden von rechts gelesen, und der **Total** ist die eine Zahl, um die es
          geht: er trägt die Linie über sich und die einzige kräftige Schrift. Struktur
          vor Fläche – kein Kasten, keine zweite Farbe. */}
      <div style={{ marginLeft: 'auto', minWidth: 0 }}>
        <div className="grid gap-x-4 text-[12.5px] ix-tnum"
          style={{ gridTemplateColumns: 'auto minmax(0, max-content)', rowGap: 2 }}>
          {d.net != null && (
            <>
              <span style={{ color: 'var(--fg-4)' }}>Netto</span>
              <span style={{ color: 'var(--fg-2)', textAlign: 'right' }}>
                {formatAmount(d.net, d.currency_decimals)}</span>
            </>
          )}
          {/* **Je Satz eine Zeile** – zwei Sätze auf einem Beleg sind der Normalfall
              (sechs Wellen zu 8.1 %, eine Ausfuhr zu 0 %), und die Abrechnung verlangt
              sie einzeln. Eine Summe «MWST» allein wäre für die Abrechnung wertlos. */}
          {split.map((v) => (
            <Fragment key={v.rate}>
              <span style={{ color: 'var(--fg-4)' }}>{d.vat_label} {v.rate} %</span>
              <span style={{ color: 'var(--fg-2)', textAlign: 'right' }}>
                {formatAmount(v.tax, d.currency_decimals)}</span>
            </Fragment>
          ))}
          {/* **Die Haarlinie geht über BEIDE Spalten** – als eigene Rasterzeile.
              An die beiden Zellen geschrieben wäre sie zweimal unterbrochen: der
              Spaltenabstand liegt dazwischen, und ein Strich mit einem Loch in der Mitte
              sieht nach einem Fehler aus, nicht nach einer Summe. */}
          {split.length > 0 && (
            <span style={{
              gridColumn: '1 / -1', height: 1, marginTop: 3, marginBottom: 3,
              background: 'var(--border-2)',
            }} />
          )}
          <span className="font-semibold" style={{ color: 'var(--fg-1)' }}>Total</span>
          {/* ►►► **Die eine Zahl, die ihre Währung MITSAGT.** ◄◄◄ Nicht jede Zeile –
              der Beleg lautet auf eine Währung, und sie steht im Kopf. Aber der Total
              ist die Zahl, die abgeschrieben, zitiert und überwiesen wird; sie ohne
              ihren Code zu zeigen hiesse, sich auf einen Blick nach oben zu verlassen. */}
          <span className="font-semibold" style={{
            color: 'var(--fg-1)', textAlign: 'right',
          }}>{formatAmount(d.amount, d.currency_decimals)} {d.currency}</span>
        </div>
      </div>

      {/* **Die Bedingungen** – klein und nebeneinander: sie sind Beiwerk zur Zahl, keine
          gleichrangige vierte Kachel. */}
      {(d.due_days != null || d.agreed_on) && (
        <div className="flex items-center gap-x-4 gap-y-1 flex-wrap text-[12px]">
          {d.due_days != null && (
            <span className="flex items-center gap-1.5">
              <span style={MICRO_LABEL}>Zahlungsfrist</span>
              <span className="ix-tnum" style={{ color: 'var(--fg-2)' }}>
                {d.due_days} Tage</span>
            </span>
          )}
          {d.agreed_on && (
            <span className="flex items-center gap-1.5">
              <span style={MICRO_LABEL}>Bestätigt</span>
              <span className="ix-tnum" style={{ color: 'var(--fg-2)' }}>
                {localDate(d.agreed_on)}</span>
            </span>
          )}
        </div>
      )}
      {/* ►►► **Kein Referenz-Feld** (#812) – die Rechnungsnummer erzeugt der Dienst
          selbst, und was bei diesem Partner zu tun ist, steht an seiner Angebotszeile. */}
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
function Money({ d, busy, orderObjectId, stepId, onAction, onPaid }: {
  d: Filled; busy?: boolean;
  orderObjectId: number; stepId: number;
  onAction: (body: Action) => void;
  onPaid?: () => void;
}) {
  // **Hier gilt allein `can`** – siehe die Begründung an der Aufrufstelle.
  const active = true;
  const [form, setForm] = useState<'' | 'charge' | 'payment'>('');
  /** Die Bezahlkarte ist offen. Ein eigener Zustand, weil sie kein `Entry` ist: sie
   *  bucht nichts und schickt keine Handlung – sie führt eine Zahlung aus. */
  const [paying, setPaying] = useState(false);
  /** Der vorbelegte Betrag einer **Korrektur** (#842) – leer heisst «Vorgabe des Servers». */
  const [correct, setCorrect] = useState('');
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
            {formatAmount(Math.abs(openAmount), d.currency_decimals)} {d.currency}
          </span>
        )}
        <span className="text-[12px] ix-tnum" style={{ color: 'var(--fg-4)' }}>
          {formatAmount(d.charged, d.currency_decimals)} berechnet · {formatAmount(d.paid, d.currency_decimals)} bezahlt · von{' '}
          {formatAmount(d.amount, d.currency_decimals)}
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
                cursor: taxTip(d, e) ? 'help' : undefined,
              }} data-tip={taxTip(d, e) || undefined}>{formatAmount(e.amount, d.currency_decimals)}</span>
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
              {/* ►►► **Man storniert einen BELEG, kein Ereignis** (Testnotiz #842). ◄◄◄

                  Eine **Rechnung** ist ein Beleg, den wir ausstellen – den nimmt eine
                  Stornorechnung zurück (`reverse`, eine Gegenbuchung mit **eigener**
                  Nummer, #841). Eine **Zahlung** ist etwas anderes: die Aufzeichnung
                  dessen, was auf dem Konto passiert ist. Ein Ereignis der Aussenwelt
                  macht man nicht ungeschehen.

                  Wer sich vertippt hat oder wem das Geld zurückkam, bucht eine **zweite
                  Zahlung** – und welcher der beiden Fälle es ist, weiss nur ein Mensch.
                  Angeboten wird sie darum **vorbelegt**, angelegt wird sie nicht: die
                  Regel des Hauses, dieselbe wie bei «nicht bestanden» (§4.5).

                  Die Sperre steht im **Dienst** (`_reverse` weist eine Zahlung ab); dies
                  ist die freundliche Hälfte. */}
              {e.reverses != null && (
                <span className="text-[11.5px]" style={{ color: 'var(--fg-4)', flex: 'none' }}
                  data-tip={reversedRef(d, e.reverses)}>Storno</span>
              )}
              {e.reversed && (
                <span className="text-[11.5px]" style={{ color: 'var(--fg-4)', flex: 'none' }}>
                  storniert
                </span>
              )}
              {may(d, active, 'reverse') && e.kind === 'charge'
                && !e.reversed && e.reverses == null && (
                <button type="button"
                  className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon"
                  style={{ height: 26 }}
                  disabled={busy} aria-label="Rechnung stornieren"
                  data-tip="Stornieren – es entsteht eine Stornorechnung mit eigener Nummer; beide Zeilen bleiben stehen."
                  onClick={() => onAction({ action: 'reverse', entry: e.id })}>
                  <CircleSlash size={13} />
                </button>
              )}
              {may(d, active, 'pay') && e.kind === 'payment' && (
                <button type="button"
                  className="erp-actbtn erp-actbtn-neutral erp-actbtn-icon"
                  style={{ height: 26 }}
                  disabled={busy} aria-label="Zahlung korrigieren"
                  data-tip="Korrigieren – erfasst eine zweite Zahlung über den negativen Betrag. Das ist der Erfassungsfehler ebenso wie die Erstattung."
                  onClick={() => { setCorrect(negate(e.amount)); setForm('payment'); }}>
                  <Undo2 size={13} />
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
            onClick={() => { setCorrect(''); setForm(form === 'charge' ? '' : 'charge'); }}>
            <FileText size={13} /> {d.charge_word}
          </button>
        )}
        {may(d, active, 'pay') && (
          <button type="button" className={tone('payment')} disabled={busy}
            style={{ height: 30 }}
            data-tip="Geld buchen – ein negativer Betrag ist die Erstattung."
            onClick={() => { setCorrect(''); setForm(form === 'payment' ? '' : 'payment'); }}>
            <Wallet size={13} /> {d.payment_word}
          </button>
        )}
        {/* ►►► **Bezahlen ist eine dritte Handlung, kein zweites «erfassen».** ◄◄◄
            «Erfassen» schreibt auf, was schon geschehen ist (eine Überweisung liegt auf
            dem Konto); dieser Knopf lässt es geschehen – und bucht selbst nichts.

            **Ob es ihn gibt, sagt `can`** (`pay_online`): nur wo das Geld zu uns fliesst,
            nur mit eingerichtetem Dienst, nur wenn etwas gefordert **und** offen ist.
            Dieselbe Liste ist auch am Endpunkt das Tor – die Oberfläche prüft nichts
            nach. Und **die Gegenpartei hat ihn ebenso**: dass der Kunde bei uns bezahlt
            statt auf einer fremden Seite, ist der Sinn der Sache. */}
        {may(d, active, 'pay_online') && (
          <button type="button" className="erp-actbtn erp-actbtn-primary" disabled={busy}
            style={{ height: 30 }}
            data-tip="Jetzt online bezahlen – gebucht wird, sobald der Zahlungsdienst es bestätigt."
            onClick={() => { setForm(''); setPaying((p) => !p); }}>
            <CreditCard size={13} /> {d.pay_online_word}
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
        <Entry kind={form} d={d} busy={busy} preset={correct || undefined}
          onCancel={() => { setForm(''); setCorrect(''); }}
          onSubmit={(body) => { setForm(''); setCorrect(''); onAction(body); }} />
      )}

      {paying && (
        <PayOnline orderObjectId={orderObjectId} stepId={stepId}
          label={d.pay_online_word}
          onDone={() => onPaid?.()} onClose={() => setPaying(false)} />
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
function Entry({ kind, d, busy, preset, onCancel, onSubmit }: {
  kind: 'charge' | 'payment'; d: Filled; busy?: boolean;
  /** Ein vorbelegter Betrag – die **Korrektur** einer Zahlung (#842). */
  preset?: string;
  onCancel: () => void; onSubmit: (body: Action) => void;
}) {
  const [amount, setAmount] = useState(
    preset ?? (kind === 'charge' ? d.next_charge : d.next_payment) ?? '');
  const [ref, setRef] = useState('');
  // ►►► **Eine Nummer, die WIR vergeben, tippt niemand** (Testnotiz #840). ◄◄◄
  //
  // Das Feld gibt es genau dort, wo die Nummer **von aussen** kommt: an einer
  // Lieferantenrechnung (sie steht auf seinem Papier) und an jeder Zahlung (QR-Referenz,
  // Zahlungszweck). Wo **wir** nummerieren, gibt es kein Feld – der Server erzeugt die
  // Nummer aus der Serie, und ein Eingabefeld daneben wäre die zweite Aussage über
  // dieselbe Sache; ein Platzhalter «automatisch» war ein Feld, das nichts aufnimmt.
  //
  // ►►► **EIN Feld für beide Zeilen-Arten** (#850): bei einer Einnahme trägt auch die
  // Zahlung unsere Nummer (sie referenziert unsere Rechnung), also gibt es dort **kein**
  // Feld – weder an der Rechnung noch an der Zahlung. Wie es heisst, sagt der Server
  // (`ref_label`); die Oberfläche fragt nie nach der Richtung.
  const refLabel = d.ref_label;
  // ►►► **Die Steuer-Angaben gehören der FORDERUNG, nicht dem Geld.** ◄◄◄
  //
  // Eine **Zahlung** trägt keine Steuer – sie begleicht sie; ein Steuersatz an einer
  // Überweisung wäre eine Angabe ohne Aussage. Und der **Satz** wird nur dort gefragt, wo
  // wir die Positionen *nicht* preisen: nennen wir den Preis (`we_quote`), steht der Satz
  // an der Position, und der Dienst verteilt eine Teilrechnung anteilig über alle Sätze
  // (`domain/deal.split_for`) – ein Feld daneben wäre die zweite Aussage. Nennt ihn die
  // Gegenpartei, steht die Steuer auf **ihrer** Rechnung, und wir schreiben sie ab.
  const taxed = kind === 'charge';
  const [vat, setVat] = useState(d.vat_rate);
  // ►►► **Das Leistungsdatum kommt aus dem PROZESS** (Testnotiz #852). ◄◄◄
  //
  // «Wann wurde die Leistung erbracht?» weiss der Auftrag: es ist der Tag, an dem die
  // Stücke dieses Modul erreicht haben (`DealEmbed.service_date`) – und das Rechnungs-
  // datum ist es **nicht**: eine Rechnung, die zwei Wochen später geschrieben wird,
  // verschöbe damit die Steuerperiode (MWSTG Art. 26 Bst. c).
  //
  // **Vorbelegt, nicht erzwungen**: ein Mensch weiss von Teilleistungen, von denen der
  // Log nichts weiss. Gerechnet wird es **nicht hier** – der Server leitet es ab, und
  // eine zweite Formel im Browser wiche ab, während ihre Zahl richtig aussähe.
  const [service, setService] = useState(d.service_date ?? '');
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
        {taxed && !d.we_quote && (
          <div>
            <Label>{d.vat_label}</Label>
            <select className={inputCls} value={vat} aria-label={d.vat_label}
              onChange={(e) => setVat(e.target.value)}>
              {(d.vat_rates ?? []).map((r) => (
                <option key={r.rate} value={r.rate}>{r.rate} % · {r.label}</option>
              ))}
            </select>
          </div>
        )}
        {/* **Wann die Leistung erbracht wurde** (MWSTG Art. 26 Bst. c) – vorbelegt aus
            dem Prozess (#852). Leer heisst «wie gebucht»: das gilt, solange noch nichts
            an diesem Modul angekommen ist. */}
        {taxed && (
          <div>
            <Label>{d.service_date_label}</Label>
            <input type="date" className={inputCls} value={service}
              aria-label={d.service_date_label}
              onChange={(e) => setService(e.target.value)} />
          </div>
        )}
        {refLabel && (
          <div>
            <Label>{refLabel}</Label>
            <input className={inputCls} value={ref} aria-label={refLabel}
              placeholder="optional"
              onChange={(e) => setRef(e.target.value)} />
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <button type="button" className="erp-actbtn erp-actbtn-primary"
          style={{ height: 30 }} disabled={busy || amount.trim() === ''}
          onClick={() => onSubmit({
            action: kind === 'charge' ? 'charge' : 'pay', amount, reference: ref,
            ...(taxed ? {
              ...(d.we_quote ? {} : { vat }),
              ...(service ? { service_date: service } : {}),
            } : {}),
          })}>
          <Check size={13} /> Buchen
        </button>
        <button type="button" className="erp-actbtn erp-actbtn-neutral"
          style={{ height: 30 }} onClick={onCancel}>Abbrechen</button>
      </div>
    </div>
  );
}
