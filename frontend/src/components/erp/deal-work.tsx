'use client';

import { Fragment, useCallback, useEffect, useState } from 'react';
import {
  AlertTriangle, ArrowUpRight, CalendarClock, Check, ChevronDown, CircleSlash,
  ClipboardList, CreditCard, FileText, Landmark, Loader2, Lock, RotateCcw, Send,
  Undo2, Wallet, X,
} from 'lucide-react';
import { api } from '@/lib/api';
import type { DealEmbed, DealParty, DealQuote, DealSide, TransferInfo } from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import { PayOnline } from '@/components/erp/pay-online';
import {
  Label, MICRO_LABEL, Segmented, TermField, inputCls, numericInputProps, numericOnly,
} from '@/components/erp/fields';
import {
  ACT_H, ActionButton, Actions, MODULE_GRID, ModuleMeta, ModuleSection,
} from '@/components/erp/module-ui';
import {
  DEAL_PARTY, DEAL_STAGE, DEAL_TASK_HINT, QUOTE_STATE, dealDirection,
} from '@/lib/modules';
import { useAutosave } from '@/lib/use-autosave';
import { formatAmount, localDate } from '@/lib/utils';

/**
 * ►►► **Der Geldvorgang an der Ausführungsstelle — EIN Beleg, der wächst.** ◄◄◄
 *
 * *Belegkopf · Positionen · Bedingungen · Rückläufe · Rechnung & Zahlungen ·
 * Handlungen* – in **beide** Richtungen dasselbe. Was Einnahme von Ausgabe unterscheidet,
 * **reist fertig mit** (`label`, `stages[].label/verb`, `party_word`, `ask_verb`,
 * `charge_word`) – die Karte braucht dafür **kein einziges `if` auf die Richtung**; ein
 * Wächter zählt sie.
 *
 * ## Ein Dokument, kein Stapel von Blöcken (Testnotiz #899)
 *
 * Vorher war die Karte eine **Kette**: Positionen, dann der Abschnitt «Angebot», dann der
 * Abschnitt «Auftrag», dann das Geld. Jeder Abschnitt trug seinen eigenen Kopf, und mit
 * der Zusage kam ein Block dazu, der Partner, Summe und Fristen **noch einmal** zeigte –
 * ein zweiter Beleg neben dem ersten.
 *
 * Jetzt ist es **ein** Beleg, und die Zusage **erweitert** ihn: der Kopf heisst danach
 * «Auftrag» statt «Angebot» und nennt den Empfänger, die Preisspalte trägt die gebuchten
 * Zahlen statt des Entwurfs, die Bedingungen stehen als Auskunft statt als Feld, die
 * Rückläufe klappen auf eine Zeile zusammen, und darunter kommt das Geld dazu. Dieselben
 * Zeilen, ein Zustand weiter.
 *
 * *Ein späterer PDF-Export ist damit dieselbe Ableitung ohne Knöpfe – nicht ein zweiter
 * Beleg, der beim nächsten Feld auseinanderläuft.*
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

/*
 * ►►► **«auf 100000801-1» gibt es nicht mehr** (Testnotiz #861). ◄◄◄
 *
 * Hier stand `chargeRef` – die Nummer der Rechnung, auf die eine Zahlung geht, für ein
 * kleines Wort am Zeilenende. Seit die Zahlungen **eingerückt unter ihrer Rechnung**
 * stehen, sagt es die Form; sie zusätzlich auszuschreiben wäre dieselbe Angabe zweimal,
 * und in einer engen Zeile kostet die zweite den Platz, den das Datum braucht.
 */

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
/**
 * ►►► **Eine Frist heisst, wie sie heisst — «0 Tage» gibt es nicht** (Testnotiz #885). ◄◄◄
 *
 * *«Kann man hier es intuitiver machen und sagen: wenn 0 Tage = Vorauszahlung, ansonsten
 * x Tage.»* – Und das ist keine zweite Formulierung, sondern **dieselbe Liste**: die
 * üblichen Werte reisen mit ihren Namen mit (`payment_terms` / `lead_terms`), weil
 * `TermField` sie zum Auswählen braucht. Hier werden sie gelesen statt ein zweites Mal
 * geschrieben – wer «Vorauszahlung» wählt, liest danach «Vorauszahlung».
 *
 * Ein Wert, der in keiner Liste steht, ist die freie Eingabe und heisst «x Tage».
 */
function termText(days: number | null | undefined,
  terms: { days: number; label: string }[] | null | undefined): string | null {
  if (days == null) return null;
  return (terms ?? []).find((t) => t.days === days)?.label ?? `${days} Tage`;
}

/**
 * **In wie vielen Tagen** – aus einem ISO-Datum, in Kalendertagen ab heute.
 *
 * Gerechnet auf **Mitternacht Ortszeit** auf beiden Seiten: sonst hinge «heute fällig»
 * an der Uhrzeit, zu der jemand hinsieht.
 */
/** **Das Datum in n Tagen** als ISO-Tag – die Gegenrichtung von `daysUntil` (#884). */
function inDays(days: number): string {
  const day = new Date();
  day.setHours(12, 0, 0, 0);
  day.setDate(day.getDate() + days);
  return day.toISOString().slice(0, 10);
}

function daysUntil(iso: string): number {
  const due = new Date(`${iso}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - today.getTime()) / 86400000);
}

/**
 * ►►► **EIN Datum je Zeile — und es sagt, was zu tun ist** (Testnotiz #890). ◄◄◄
 *
 * *«Braucht es das erste Datum oder nur fällig? … wäre noch cool und intuitiver zu sagen
 * fällig in x Tagen und als Hover-Information das Datum.»* – In der Zeile standen beide
 * Daten nebeneinander («6.9.2026 · fällig 6.9.2026»), und in einer engen Zeile sind zwei
 * Datumsangaben zwei Zahlen, die man vergleichen muss, um die eine Aussage zu bekommen,
 * um die es geht: **wie viel Zeit bleibt**.
 *
 * Die Zeile sagt darum die **Frist**, der Hover die beiden **Daten** – gebucht und fällig.
 * Wo es keine Fälligkeit gibt (eine Zahlung, eine Rechnung ohne Frist), bleibt das
 * Buchungsdatum: dort ist es die ganze Aussage.
 */
function dateText(e: Filled['entries'][number]): { text: string; tip: string } {
  const booked = localDate(e.booked_on);
  if (!e.due_on) return { text: booked, tip: `Gebucht ${booked}` };
  const left = daysUntil(e.due_on);
  const tip = `Gebucht ${booked} · fällig ${localDate(e.due_on)}`;
  if (left > 0) return { text: `fällig in ${left} Tagen`, tip };
  if (left === 0) return { text: 'heute fällig', tip };
  return { text: `überfällig seit ${-left} Tagen`, tip };
}

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

  // ►►► **Alles untereinander — es gibt keine Reiter mehr** (Testnotiz #863). ◄◄◄
  //
  // *«Ich mag diese Reiter-Ansicht nicht, ich möchte alles auf einmal sehen
  // untereinander.»* – Und die Meldung hat recht, weil der Vorgang **einer** ist: das
  // Angebot erklärt die Zusage, die Zusage erklärt die Rechnung. Wer eine Rechnung
  // schreibt und dabei nachsehen will, was zugesagt war, hatte zwei Klicks dazwischen.
  //
  // *Der Wechsel war die Antwort auf «bei vier Buchungen ist die Karte zwei Bildschirme
  // hoch», und die Sorge bleibt richtig – aber sie ist eine Frage der **Dichte**, nicht
  // des Versteckens: die Positionen tragen jetzt ihre Preise selbst (#862), der
  // bestätigte Auftrag zeigt nur noch die Summe, und die Zahlungen stehen **eingerückt
  // unter ihrer Rechnung** (#861) statt als flache Liste.*
  //
  // ►►► **Und der Verlauf steht AN den Abschnitten** (Testnotiz #868). ◄◄◄
  //
  // Die Leiste blieb eine Runde lang als Übersicht stehen (`ModuleSteps` ohne Handler) –
  // *«mir passt das da oben nicht»*, und die Meldung hat wieder recht: sie trug dieselben
  // drei Wörter wie die drei Abschnitte darunter, nur waagrecht und eine Zeile früher.
  // Wo sie nichts mehr versteckt, sagt sie nur noch **wie weit** – und das gehört an die
  // Überschrift, nicht über die Karte (`ModuleSection state`, Punkt + Wort).

  // ►►► **Der Angebotsentwurf wohnt hier, weil die Tabelle EINE ist** (#862). ◄◄◄
  //
  // Preis und Satz standen im Angebot (`OurOffer`), die Zeilen oben in `Goods` – zwei
  // Tabellen über dieselbe Sache. Jetzt gibt es eine, und sie steht über beiden: also
  // gehört der Entwurf dorthin, wo beide ihn sehen.
  //
  // **Gehalten wird er je ARTIKEL, nicht als Liste.** Eine Liste müsste nachgezogen
  // werden, sobald der Prozess eine Position dazustellt – und ein Nachziehen löscht
  // getippte Preise. Als Zuordnung fällt das weg: die Zeilen kommen aus `d.lines`, der
  // getippte Wert steht daneben und findet seine Zeile über die Artikelnummer.
  const [prices, setPrices] = useState<Record<string, PriceRow>>({});
  const rowKey = (article: number | null) => String(article ?? 'none');
  const rows: PriceRow[] = (d.lines.length
    ? d.lines.map((l) => l.article_id ?? null) : [null]
  ).map((a) => prices[rowKey(a)] ?? { article: a, price: '', vat: d.vat_rate });
  const setRow = (article: number | null, patch: Partial<PriceRow>) => setPrices((p) => ({
    ...p,
    [rowKey(article)]: {
      ...(p[rowKey(article)] ?? { article, price: '', vat: d.vat_rate }), ...patch,
    },
  }));
  const [offer, setOffer] = useState<{ lead: string; days: string }>(
    { lead: '', days: '' });
  // **Preise tippt man nur, wo WIR sie nennen – und nur, solange man anbieten kann.**
  // Danach ist die Tabelle das, was sie immer war: die Auskunft, worum es geht.
  const pricing = d.we_quote && may(d, active, 'ask');

  return (
    <div className="flex flex-col">
      {/* ►►► **Die Karte IST der Beleg** (Testnotiz #899). ◄◄◄

          *«Alle dargestellten Informationen bauen aufeinander auf – Anfrage / Auftrag /
          Rechnung. Man könnte es wie ein Dokument aufbauen und dann Schritt für Schritt
          erweitern … später beim PDF-Export ist dann jeder Schritt einfach um die
          jeweiligen Informationen reduziert oder erweitert.»*

          Genau so steht sie jetzt da, und zwar in der Ordnung, die ein Beleg seit
          Jahrhunderten hat:

          1. **Belegkopf** – was für ein Beleg das ist, an wen, seit wann.
          2. **Positionen** – worum es geht, mit Preis, Satz und Summe.
          3. **Bedingungen** – Währung und die beiden Fristen, aus denen Fälligkeit und
             Liefertermin folgen.
          4. **Rückläufe** – was die Gegenparteien geantwortet haben.
          5. **Rechnung & Zahlungen**.
          6. **Handlungen** – ganz am Ende, wie die Unterschrift.

          Es **wächst**: vor der Zusage heisst der Kopf «Angebot» und die Rückläufe stehen
          offen; nach der Zusage heisst er «Auftrag», nennt den Partner und das Datum, die
          Rückläufe klappen auf eine Zeile zusammen, und darunter kommt das Geld dazu.
          Ein späterer PDF-Export ist damit **dieselbe Komponente ohne Knöpfe** – kein
          zweiter Beleg, der beim nächsten Feld auseinanderläuft. */}
      <DocHead d={d} />

      {/* ►►► **EINE Positionstabelle** (Testnotiz #862). ◄◄◄
          *«Der Positions-Abschnitt ist doppelt.»* – Er war es: oben stand, worum es geht
          (Menge, Name, Nummer, und seit #847 auch Preis und Satz), und im Angebot noch
          einmal dieselben Zeilen, nur mit Eingabefeldern. Derselbe Datensatz in zwei
          Tabellen, und die untere sagte weniger (kein Chevron, keine Spezifikation).

          Es ist **eine** Tabelle: dieselben Zeilen, und wo wir den Preis nennen dürfen,
          sind Preis und Satz dort **Eingaben** statt Anzeigen. Was gehandelt wird, sagt
          der Prozess – auch beim Eintippen. */}
      <Goods d={d} rows={rows} editable={pricing} onPrice={setRow} />

      {/* ►►► **Zu welchen Bedingungen** (Testnotizen #897/#899). ◄◄◄
          Währung und die beiden Fristen standen an drei Orten – die Währung im Angebot,
          die Fristen einmal in `OurOffer` und einmal an der Angebotszeile. Es ist **ein**
          Abschnitt des Belegs, und er steht dort, wo er auf einem Beleg steht: unter der
          Summe, über den Antworten. */}
      <Terms d={d} busy={busy} active={active} editable={pricing}
        value={offer} onChange={setOffer} onAction={onAction} />

      {/* **Der Punkt vor der Überschrift sagt, wie weit es ist** (#868) – Punkt + Wort,
          von oben nach unten gelesen.

          ►►► **Ein Storno macht die Zusage nicht ungeschehen** ◄◄◄ – *«die gegangenen
          Stufen bleiben stehen»* (`services/deal._revoke`), dieselbe Regel wie «die Linie
          sagt die Vergangenheit» am Prozessbild (§8.1a). Storniert werden kann nur ab der
          Zusage (`ACTIONS`), ein stornierter Vorgang **war** also zugesagt – der Punkt
          steht darum auf «vorbei», nicht auf «steht noch aus». */}
      <ModuleSection title={d.stages[0]?.label ?? ''}
        state={agreed ? 'past' : 'active'}>
        <Offer d={d} busy={busy} active={active && !!d.stages[0]?.active}
          agreed={agreed} rows={rows} offer={offer} onSent={() => setPrices({})}
          onAction={onAction} />
      </ModuleSection>

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
      {/* **Ohne Zahlen gibt es keinen Abschnitt** – eine Überschrift über einer leeren
          Fläche ist eine Auskunft, die nichts sagt. So sieht es eine Gegenpartei, die
          nicht den Zuschlag hat: `open` kommt gar nicht erst mit. */}
      {agreed && d.open != null && (
        <ModuleSection title={d.money_label}
          state={d.settled && Number(d.charged ?? 0) ? 'past'
            : cancelled ? 'ahead' : 'active'}>
          <Money d={d} busy={busy} onAction={onAction}
            orderObjectId={orderObjectId} stepId={stepId} onPaid={onPaid} />
        </ModuleSection>
      )}

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
      {/* ►►► **Und die Gegenhandlung steht DANEBEN** (Testnotiz #874). ◄◄◄

          «Auftrag stornieren» stand in der Geld-Zeile – zwischen «Rechnung erfassen» und
          «Zahlung erfassen», also unter lauter Buchungen. Es ist aber keine Buchung,
          sondern die Gegenhandlung des **ganzen Vorgangs**: das Gegenstück zu «Vorgang
          abschliessen», nicht zu «Zahlung erfassen». Beide stehen darum am Ende der
          Karte, in einer Zeile – die eine bringt den Vorgang ans Ziel, die andere nimmt
          ihn zurück. */}
      {/* ►►► **Die Fusszeile eines Belegs** (Testnotiz #899). ◄◄◄ Handlungen stehen nicht
          zwischen den Angaben, sondern unter dem Strich – dort, wo auf einem Papier die
          Unterschrift steht. Die Haarlinie ist dieselbe wie über jedem Abschnitt, nur
          eine Zeile tiefer; ohne sie schwebten zwei Knöpfe unter der letzten Zahl. */}
      {(may(d, active, 'revoke') && d.undo) || (agreed && active && !(d.prepaid && !d.settled)) ? (
        <div className="flex items-center gap-2 flex-wrap" style={{
          marginTop: 18, paddingTop: 12, borderTop: '1px solid var(--border-1)',
        }}>
          {agreed && active && !(d.prepaid && !d.settled) && children}
          {may(d, active, 'revoke') && d.undo && (
            <button type="button" className="erp-actbtn erp-actbtn-danger" disabled={busy}
              style={{ height: ACT_H.inline }}
              data-tip="Nimmt die Zusage zurück – die gegangenen Stufen bleiben stehen."
              onClick={() => onAction({ action: 'revoke' })}>
              <Undo2 size={13} /> {d.undo}
            </button>
          )}
        </div>
      ) : null}
    </div>
  );
}

/*
 * ►►► **Die drei Schritte brauchen keine Schlüssel mehr** (Testnotiz #868). ◄◄◄
 *
 * Hier standen `OFFER`, `AGREED` und `MONEY` – die **Identität** der drei Schritte, mit
 * der die Stufen-Leiste sagte, welcher offen ist. Es gibt sie nicht mehr: seit alles
 * untereinander steht (#863) ist nichts zu wählen, und seit der Verlauf an den
 * Überschriften steht (#868), ist nichts zu benennen. Die **Wörter** kamen ohnehin vom
 * Server (`stages[].label`, `money_label`).
 *
 * Mit ihnen ist `moneyValue` entfallen – die eine Zahl der Geld-Stufe, also der Wert, den
 * die Leiste rechts neben «Rechnung & Zahlung» trug.
 */

/**
 * ►►► **Wie lange nach einer Online-Zahlung nachgefragt wird** (Testnotiz #857). ◄◄◄
 *
 * Gebucht wird vom **Webhook**, nicht vom Browser des Zahlenden – zwischen dem «bezahlt»
 * der Karte und der Meldung liegen ein bis drei Sekunden. Zehn Versuche im
 * Anderthalb-Sekunden-Takt sind rund **15 Sekunden**: lang genug für den Normalfall, kurz
 * genug, dass niemand einer Anzeige zusieht, die nichts mehr sagt. Bleibt die Meldung aus,
 * hört die Karte auf zu fragen, statt eine Buchung zu behaupten.
 */
const WAIT_TRIES = 10;
const WAIT_STEP = 1500;

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
const CURRENCY_LABEL = 'Währung';

function Currency({ d, busy, active, onAction }: {
  d: Filled; busy?: boolean; active: boolean; onAction: (body: Action) => void;
}) {
  // ►►► **Steht sie fest, steht sie an den ZAHLEN — und sonst nirgends** (#876/#881). ◄◄◄
  //
  // Hier stand dann eine Lese-Anzeige «Währung: CHF». Sie war richtig, solange der Code
  // nur beim Total und beim offenen Betrag mitlief – jetzt steht er an **jedem** Betrag,
  // den man abschreibt, und ein eigenes Feld daneben sagt dieselbe Sache ein zweites Mal.
  // *Damit ist die Regel aus #864 («verschwindet nicht, wird zur Auskunft») abgelöst: die
  // Auskunft gibt es weiterhin, sie steht nur dort, wo die Frage entsteht.*
  if (!may(d, active, 'currency')) return null;
  return (
    // **So breit, wie die Beschriftung ist** (#869): sie trägt den Code *und* den Namen
    // («CHF · Schweizer Franken»), und ein natives Auswahlfeld zeigt geschlossen genau
    // den Text der gewählten Zeile – zu schmal steht dort «CHF · Schw…», also der halbe
    // Name statt einer Auskunft. Mehr als die Karte wird es nie (`maxWidth: 100%`).
    //
    // ►►► **Ohne Beschriftung darüber** (Testnotiz #876) – *«das Auswahlfeld ist intuitiv
    // genug»*: es zeigt geschlossen «CHF · Schweizer Franken», und ein Wort «Währung»
    // darüber wiederholt, was in der Zeile selbst steht. Benannt bleibt es für den, der
    // die Karte hört (`aria-label`).
    <div style={{ width: 190, maxWidth: '100%' }}>
      <select className={inputCls} aria-label={CURRENCY_LABEL} disabled={busy}
        data-tip="Die Währung dieses Vorgangs – ab der Zusage gebunden."
        value={d.currency}
        onChange={(e) => onAction({ action: 'currency', currency: e.target.value })}>
        {/* ►►► **Die Beschriftung TRÄGT den Code schon** (Testnotiz #869). ◄◄◄
            `currency.label` liefert «CHF · Schweizer Franken» – der Code davor ergab
            «CHF · CHF · Schweizer Franken». Die Zusammensetzung gehört dem Server
            (eine Stelle, ein Format); wer sie hier ein zweites Mal baut, sagt dieselbe
            Angabe zweimal, sobald die eine sich ändert. */}
        {(d.currencies ?? []).map((c) => (
          <option key={c.code} value={c.code}>{c.label}</option>
        ))}
      </select>
    </div>
  );
}

/*
 * ►►► **Einen «Anteil» gibt es nicht** (Testnotiz #867). ◄◄◄
 *
 * Hier stand `Share` – eine Prozentzahl, die sagte, welchen Teil der Positionen *dieser*
 * Vorgang abrechnet. Gedacht war sie als Gegenstück zu «eine Rechnung je Modul» (#866):
 * die Anzahlung als zweites Modul mit 30 %. *«Ich checke diese Funktion nicht.»* – und
 * sie wird auch nicht gebraucht: **wer den Preis nennt, nennt ihn je Position**, und ein
 * zweites Modul trägt schlicht seine eigenen Positionspreise. Eine Zahl, die man erklären
 * muss, um ein Feld zu füllen, das man in derselben Tabelle direkt schreiben kann, ist ein
 * Begriff zu viel.
 */

/**
 * **Eine Angabe, die feststeht** – Beschriftung und Wert, mit dem Grund im Hover.
 *
 * Ein **gesperrtes Eingabefeld ist keine Lese-Anzeige** (die Regel aus #749): es sieht
 * aus wie ein Feld, das gleich etwas aufnimmt, und sagt nicht, warum es das nicht tut.
 */
function Fixed({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div style={{ minWidth: 0 }}>
      <span style={MICRO_LABEL}>{label}</span>
      <div className="ix-tnum text-[13px]" data-tip={hint}
        style={{ color: 'var(--fg-2)', paddingTop: 6, cursor: hint ? 'help' : undefined }}>
        {value}
      </div>
    </div>
  );
}

/**
 * ►►► **Der Belegkopf — was das hier ist, an wen, und seit wann.** ◄◄◄
 *
 * *Hier stand eine `Meta`-Zeile: Richtung, Termin, Sperre – drei Auskünfte nebeneinander,
 * die zu keinem Schritt gehörten.* Sie war richtig, solange die Karte eine Kette von
 * Schritten war. Als **Beleg** (#899) fehlte ihr das Wichtigste: die **Belegart**. Ein
 * Papier, das nicht sagt, ob es ein Angebot oder ein Auftrag ist, ist keines.
 *
 * ## Die Belegart IST der Fortschritt
 *
 * «Angebot» → «Auftrag» → (storniert) sind genau die Stufen, die der Server ohnehin
 * benennt (`stages[].label`, `stage_label`). Sie hier als Titel zu führen, ersetzt keinen
 * Mechanismus, es zeigt den vorhandenen an der Stelle, an der man ihn liest – und die
 * Karte wächst damit, statt umzuschalten.
 *
 * ## Die Richtung bleibt ein SYMBOL
 *
 * «Einnahme»/«Ausgabe» als Dauertext stand einmal daneben und sagte dieselbe Sache
 * zweimal (#797). Der Titel ist jetzt das laute Wort; die Richtung ist das Zeichen davor,
 * mit ihrer Bedeutung im Hover – dieselbe Regel wie bei jedem Symbol im Haus.
 *
 * ## Die beiden Parteien stehen erst da, wenn es sie gibt
 *
 * Vor der Zusage nennen die **Rückläufe** die Adressaten – es sind mehrere, und einen
 * davon vorwegzunehmen wäre eine Behauptung. Mit der Zusage steht genau einer fest, und
 * dann gehört er dorthin, wo auf jedem Beleg der Empfänger steht: in den **Belegkopf**
 * (`Parties`), mit Rolle, Anschrift und – beim Aussteller – der UID.
 *
 * ## Die EINE Information steht oben rechts
 *
 * *Was muss man in unter einer Sekunde finden?* – **was noch offen ist.** Sie stand
 * nirgends: die Geld-Zeile listet die Buchungen, aber die Summe daraus (`open`) wurde
 * gar nicht angezeigt. Sie steht darum hier, an der Kante, an der man sie sucht – und
 * **genau einmal**.
 */
function DocHead({ d }: { d: Filled }) {
  const dir = dealDirection(d.direction);
  const Icon = dir.icon;
  const cancelled = d.stage === DEAL_STAGE.cancelled;
  const agreed = d.stage !== DEAL_STAGE.offer;
  const kind = cancelled ? d.stage_label
    : (agreed ? d.stages[1]?.label : d.stages[0]?.label) ?? d.label;
  return (
    <>
      <div className="flex items-center gap-2 flex-wrap" style={{ marginBottom: 6 }}>
        {/* **Das Symbol zeigt, was man tut** – Einkaufswagen ↔ Handschlag (#799/#845);
            was es heisst, steht im Hover, nicht als zweites Wort daneben. */}
        <span className="flex items-center" data-tip={dir.hint}
          style={{ flex: 'none', cursor: 'help', color: 'var(--fg-3)' }}>
          <Icon size={14} />
        </span>
        <span style={{
          font: '800 14px var(--font-display)', letterSpacing: '-.01em',
          color: cancelled ? 'var(--danger)' : 'var(--fg-1)',
        }}>{kind}</span>
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
        {/* ►►► **Die eine Information — was noch offen ist.** ◄◄◄

            Sie kam bisher zwar mit (`open`), stand aber nirgends: die Geld-Zeile zeigt
            die einzelnen Buchungen, ihre **Summe** zeigte niemand. Genau sie ist die
            Frage, die ein Mensch an diesem Beleg zuerst hat.

            **Rot heisst überfällig**, und die Antwort darauf kommt vom Server
            (`entries[].overdue` – fällig **und** noch etwas offen); eine zweite Formel
            hier wiche ab und sähe trotzdem richtig aus.

            Sie steht **einmal**: unten wiederholt sie niemand. */}
        {d.open != null && (
          <span className="flex items-baseline gap-1.5" style={{ flex: 'none' }}
            data-tip="Gefordert und noch nicht bezahlt – die Summe über alle Rechnungen dieses Vorgangs.">
            <span style={MICRO_LABEL}>{d.open_word}</span>
            <span className="ix-tnum" style={{
              font: '700 14px var(--font-display)', letterSpacing: '-.01em',
              color: overdue(d) ? 'var(--danger)' : 'var(--fg-1)',
            }}>{formatAmount(d.open, d.currency_decimals)} {d.currency}</span>
          </span>
        )}
      </div>
      <Parties d={d} />
      {/* ►►► **Das Datum steht ALLEIN in der Meta-Zeile** (#838/#883). ◄◄◄
          Hier stand daneben «An 100000123 Muster AG» – seit der Belegkopf beide Parteien
          mit ihrer Rolle nennt, wäre das dieselbe Angabe ein zweites Mal, nur ärmer (ohne
          Anschrift, ohne UID) und ohne zu sagen, welche Rolle der Genannte hat. */}
      {d.agreed_on && (
        <ModuleMeta>
          <span className="ix-tnum"
            data-tip="Tag der Zusage – ab ihm laufen Liefer- und Zahlungsfrist.">
            {localDate(d.agreed_on)}
          </span>
        </ModuleMeta>
      )}
    </>
  );
}

/**
 * ►►► **Ist an diesem Vorgang etwas überfällig?** ◄◄◄
 *
 * Gefragt wird der **Server**, nicht die Uhr des Browsers: `overdue` heisst *fällig **und**
 * noch etwas offen* – zwei Bedingungen, und die zweite kennt nur, wer die Buchungen
 * rechnet. Eine zweite Formel hier wiche ab und sähe trotzdem richtig aus.
 */
function overdue(d: Filled): boolean {
  return d.entries.some((e) => e.overdue);
}

/**
 * ►►► **Der Belegkopf — wer stellt ihn, und wer bekommt ihn** (MWSTG Art. 26). ◄◄◄
 *
 * Eine Rechnung ist erst eine, wenn sie **beide Seiten** nennt: Name und Ort, wie im
 * Geschäftsverkehr aufgetreten, und beim Aussteller die **UID** – ohne sie kann dem
 * Empfänger der Vorsteuerabzug verweigert werden.
 *
 * ## Die Rolle steht im WORT, nicht in der Position
 *
 * «Lieferant» ↔ «Kunde» kommen fertig vom Server (`DealSide.label`), und **welche Seite
 * welche trägt**, entscheidet dort die Richtung. Diese Komponente fragt dafür kein
 * einziges Mal, ob es eine Einnahme oder eine Ausgabe ist – sie zeichnet zwei Blöcke.
 *
 * ## Was fehlt, wird gesagt – nicht erfunden
 *
 * Eine Pflichtangabe, die nicht hinterlegt ist, steht als kleines rotes **«fehlt»** da.
 * Eine erfundene Zeile wäre auf einem Beleg schlimmer als eine leere, und eine leere
 * Stelle ohne Vermerk sähe aus wie eine, die es so geben darf.
 *
 * ## Eine Seite ohne Namen gibt es gar nicht
 *
 * Vor der Zusage steht der Partner nicht fest, und wer den Zuschlag **nicht** hat, sieht
 * die Gegenseite nicht (`won`). Beides ist derselbe Fall: eine Seite ohne Namen wird
 * nicht gezeichnet – sonst stünde dort dreimal «fehlt» für etwas, das nicht fehlt.
 */
function Parties({ d }: { d: Filled }) {
  // **Wer der Aussteller ist, sagt das Feld – nicht sein Name.** Ein Vergleich auf das
  // Wort «Lieferant» wäre ein Spiegel über die API-Grenze, der beim ersten Umbenennen
  // still falsch wird; hier steht die Rolle in der Struktur selbst.
  const sides = ([[d.supplier, true], [d.customer, false]] as const).filter(
    (pair): pair is readonly [DealSide, boolean] => !!pair[0] && !!pair[0].name);
  if (!sides.length) return null;
  return (
    <div style={{ ...MODULE_GRID, gap: '12px 24px', marginBottom: 14 }}>
      {sides.map(([s, issuer]) => (
        <div key={s.label} style={{ minWidth: 0 }}>
          <span style={MICRO_LABEL}>{s.label}</span>
          <div className="flex items-center gap-2" style={{ minWidth: 0, paddingTop: 5 }}>
            {s.object_id != null && <ObjId value={s.object_id} />}
            <span className="truncate font-semibold text-[13px]"
              style={{ color: 'var(--fg-1)', minWidth: 0 }} data-tip={s.name}>{s.name}</span>
          </div>
          {/* **Die Anschrift kommt als ZEILEN**, wie sie auf dem Beleg steht – die
              Reihenfolge gehört dorthin, wo Adressen gebaut werden (`address.lines`).
              Eine zweite Fassung hier wäre die Stelle, an der beim nächsten Feld eine
              Zeile verrutscht. */}
          {s.address?.length ? (
            <div className="text-[12px]" style={{ color: 'var(--fg-3)', paddingTop: 3 }}>
              {s.address.map((line) => <div key={line} className="truncate">{line}</div>)}
            </div>
          ) : <Missing what="Anschrift" />}
          {/* **Die UID nur beim Aussteller** – eine des Empfängers führt das System nicht,
              und für den Inland-Beleg ist sie auch nicht verlangt. Wo sie hingehört und
              fehlt, sagt es die Zeile. */}
          {issuer && (s.uid
            ? <div className="ix-tnum text-[12px]"
              style={{ color: 'var(--fg-3)', paddingTop: 3 }}
              data-tip="Ohne sie kann dem Empfänger der Vorsteuerabzug verweigert werden.">
              {s.uid}
            </div>
            : <Missing what="UID" />)}
        </div>
      ))}
    </div>
  );
}

/**
 * **Eine Pflichtangabe, die nicht hinterlegt ist** – klein, rot, benannt.
 *
 * Sie steht dort, wo die Angabe stünde: eine leere Stelle sähe aus wie eine, die es so
 * geben darf, und ein Platzhalter wie eine Angabe.
 */
function Missing({ what }: { what: string }) {
  return (
    <div className="flex items-center gap-1 text-[12px]"
      style={{ color: 'var(--danger)', paddingTop: 3 }}
      data-tip={`${what} fehlt – sie gehört auf einen Beleg (MWSTG Art. 26).`}>
      <AlertTriangle size={11} /> {what} fehlt
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
/**
 * **Wie schmal eine Sache noch benannt werden darf** – Menge, ein paar Zeichen Name und
 * die Objektnummer. Sie ist zugleich die Ausgangsbreite, an der der Umbruch entscheidet.
 */
const NAME_MIN = 190;

/**
 * **Wie eine Position heisst – Nummer UND Name** (#853), für ein `aria-label`.
 *
 * Im Bild stehen die beiden nebeneinander; wer die Karte **hört**, bekommt nur diesen
 * einen String – und «Preis netto – Blech» ist bei zwei Blechen keine Kennung.
 */
function named(line: Filled['lines'][number]): string {
  return [line.article_object_id, line.article_name || 'ohne Artikel']
    .filter(Boolean).join(' ');
}

function Goods({ d, rows, editable, onPrice }: {
  d: Filled;
  /** Der Angebotsentwurf – je Zeile Preis und Satz, gehalten in `DealWork` (#862). */
  rows: PriceRow[];
  /** **Darf man hier tippen?** Nur wo wir den Preis nennen und noch anbieten können. */
  editable: boolean;
  onPrice: (article: number | null, patch: Partial<PriceRow>) => void;
}) {
  const [open, setOpen] = useState<number | null>(null);
  // **Ohne Positionen gibt es den Abschnitt nicht** – eine Überschrift über einer leeren
  // Fläche ist eine Auskunft, die nichts sagt. Bei Miete, Lohn oder einer Gebühr steht
  // hier nichts, und das ist richtig: die Sache ist der Vorgang selbst.
  //
  // **Ausser man muss einen Preis nennen**: dann ist es **eine** Zeile ohne Artikel –
  // derselbe Mechanismus mit einer entarteten Zeile, kein zweiter Fall (so stand es
  // schon im Angebotsblock, den diese Tabelle abgelöst hat).
  const items: Filled['lines'] = d.lines.length ? d.lines : (editable ? [{
    article_id: null, article_object_id: null, article_name: '', quantity: 1,
    spec: [], price: null, vat: d.vat_rate,
  }] : []);
  // ►►► **Was es kostet, steht bei dem, was es ist** (Testnotiz #899). ◄◄◄
  //
  // Die Summe stand einmal einen Abschnitt tiefer im bestätigten Auftrag – also getrennt
  // von den Zahlen, aus denen sie kommt. Auf einem Beleg steht sie unter ihren Positionen,
  // und hier ist es dieselbe Ableitung: vor der Zusage die **Vorschau** aus den getippten
  // Preisen, danach die **gebuchten** Zahlen des Servers.
  //
  // **Ohne Positionen bleibt der Total allein**, und das ist kein Sonderfall: bei einer
  // *Ausgabe* nennt die Gegenpartei den Preis, und die Steuer steht auf **ihrer** Rechnung
  // – wir kennen sie erst, wenn wir sie erfassen. Miete, Lohn und Gebühr haben ohnehin
  // keine Position; der Abschnitt heisst dann schlicht nach dem, was darin steht.
  const summed = !editable && d.amount != null;
  if (!items.length && !summed) return null;
  return (
    <ModuleSection title={items.length ? 'Positionen' : 'Betrag'}>
      {items.map((line, i) => {
        const spec = line.spec ?? [];
        const key = line.article_id ?? -(i + 1);
        const shown = open === key;
        const row = rows.find((r) => r.article === (line.article_id ?? null))
          ?? { article: line.article_id ?? null, price: '', vat: d.vat_rate };
        return (
          <div key={key} className="flex flex-col">
            {/* ►►► **Was die Sache benennt, schrumpft ALS EINES.** ◄◄◄

                Menge, Name, Nummer und Chevron standen als vier Geschwister neben dem
                Preisblock, drei davon `flex: none` – schrumpfen konnte allein der Name,
                und war er auf null, lief die Zeile über: gemessen **+17 px** bei 320 px
                im echten Kartenrahmen. Als **eine** schrumpfende Gruppe geht es auf,
                ohne dass eine Zahl weicht; gekappt wird der Name (#838).

                **Und unter die Breite eines Namens schrumpft sie nicht**: mit
                `flex: 1 1 NAME_MIN` steht die Untergrenze als *Ausgangsbreite* da, und
                genau daran entscheidet der Umbruch – passt der Preisblock nicht mehr
                daneben, rutscht **er** auf die zweite Zeile (`marginLeft: auto`, also
                weiterhin rechts). Ohne sie schrumpfte der Name bei 320 px auf **0 px**:
                die Zeile lief nicht über, aber sie nannte die Sache nicht mehr (#853).

                *Eine Medienabfrage wäre hier falsch: die Karte ist auch auf einem
                1440-px-Schirm rund 460 px breit – gefragt ist die Breite der **Karte**,
                und die kennt allein der Umbruch selbst.* */}
            <div className="flex flex-wrap items-center gap-x-2 gap-y-1"
              style={{ padding: '4px 0' }}>
              <span className="flex items-center gap-2 min-w-0"
                style={{ flex: `1 1 ${NAME_MIN}px` }}>
                {/* **Die Nummer steht NEBEN dem Schalter, nicht darin**: sie führt zum
                    Artikel, und ein Link in einem Knopf ist zweierlei an einer Stelle.
                    Aufgeklappt wird über Menge, Name und Chevron. */}
                <button type="button"
                  className="flex items-center gap-2 min-w-0 text-left"
                  style={{ background: 'none', border: 0, padding: 0 }}
                  aria-expanded={shown} disabled={spec.length === 0}
                  onClick={() => setOpen(shown ? null : key)}>
                  <span className="ix-tnum text-[12.5px] font-semibold"
                    style={{ color: 'var(--fg-1)', flex: 'none' }}>{line.quantity}×</span>
                  <span className="text-[12.5px] truncate" style={{ color: 'var(--fg-1)' }}>
                    {line.article_name || 'Ohne Artikel'}
                  </span>
                  {spec.length > 0 && (
                    <ChevronDown size={13} style={{
                      color: 'var(--fg-4)', flex: 'none',
                      transform: shown ? 'rotate(180deg)' : undefined,
                    }} />
                  )}
                </button>
                {line.article_object_id != null && (
                  <ObjId value={line.article_object_id} />
                )}
              </span>
              {/* ►►► **Der Preis steht an SEINER Position** (MWSTG Art. 26). ◄◄◄

                  Steuersatz und Einzelpreis gehören der **Sache**: sechs Wellen zu 8.1 %
                  und eine Ausfuhr zu 0 % stehen auf demselben Papier.

                  ►►► **Und es ist DIESELBE Zeile, in der man sie eingibt** (#862). ◄◄◄
                  Der Angebotsblock hatte eine zweite Tabelle mit denselben Zeilen und
                  Eingabefeldern – derselbe Datensatz zweimal, einmal als Auskunft und
                  einmal als Formular, mit zwei Schreibweisen und einer Chevron-Spalte
                  Unterschied. Hier ist es eine Tabelle, die tippen lässt, solange man
                  anbieten darf.

                  **Erst, wenn es einen gibt**: solange niemand einen Preis genannt hat,
                  steht hier nichts (eine 0.00 wäre eine Behauptung). */}
              {editable ? (
                <span className="flex items-end gap-2"
                  style={{ flex: 'none', marginLeft: 'auto' }}>
                  {/* **Auch der gesprochene Name trägt die Nummer** (#853): bei zwei
                      Positionen sind «Preis netto – Blech» und «Preis netto – Blech»
                      dasselbe Feld, und wer die Karte hört statt sieht, hat sonst keine
                      Kennung. Dieselbe Regel wie im Bild, ein Ort weiter. */}
                  <div style={{ width: 100 }}>
                    <Label required>Preis netto</Label>
                    <input className={`${inputCls} ix-tnum`} {...numericInputProps}
                      value={row.price} placeholder="0.00"
                      aria-label={`Preis netto – ${named(line)}`}
                      onChange={(e) => onPrice(row.article,
                        { price: numericOnly(e.target.value) })} />
                  </div>
                  {/* **Der Katalog kommt vom Server** – ein getippter Satz ist einer, den
                      es nicht gibt, und er fällt erst bei der Abrechnung auf. */}
                  <div style={{ width: 92 }}>
                    <Label>{d.vat_label}</Label>
                    <select className={inputCls} value={row.vat}
                      aria-label={`${d.vat_label} – ${named(line)}`}
                      onChange={(e) => onPrice(row.article, { vat: e.target.value })}>
                      {(d.vat_rates ?? []).map((r) => (
                        <option key={r.rate} value={r.rate}>{r.rate} %</option>
                      ))}
                    </select>
                  </div>
                </span>
              ) : line.price != null && (
                <span className="flex items-center gap-2"
                  style={{ flex: 'none', marginLeft: 'auto' }}>
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
            </div>
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
      {/* **Was das Angebot kostet, rechnet niemand im Kopf** – dieselbe Regel wie im
          Dienst (je Satz auf der Summe), nur als **Vorschau**; gebucht wird dort. Sie
          steht unter den Zahlen, aus denen sie kommt, statt einen Bildschirm tiefer im
          Angebotsblock. */}
      {editable && (
        <Sums rows={rows} lines={d.lines} label={d.vat_label ?? 'MWST'}
          decimals={d.currency_decimals} code={d.currency} />
      )}
      {summed && (
        <Totals net={d.net ?? null} splits={d.vat_split ?? []} total={d.amount ?? '0'}
          label={d.vat_label ?? 'MWST'} decimals={d.currency_decimals}
          code={d.currency} />
      )}
    </ModuleSection>
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
 *
 * ►►► **Nach dem Zuschlag sind es RÜCKLÄUFE — eine Zeile** (Testnotiz #899). ◄◄◄
 *
 * *«Ein Beleg + Rückläufe»* – der Beleg ist unser Angebot bzw. unsere Anfrage, und die
 * Antworten der Gegenparteien stehen darunter. Solange verhandelt wird, ist das die
 * Arbeitsfläche. **Danach ist es Vergangenheit**: wer den Zuschlag hat, steht im
 * Belegkopf, und die unterlegenen Zeilen sind eine Auskunft, kein Bedienelement.
 *
 * Sie **verschwinden nicht** (der Vergleich ist der Nachweis, warum man so entschieden
 * hat) – sie klappen auf **eine** Zeile zusammen, die sagt, wie viele es waren. Aufklappen
 * ist ein Klick; die Zeile selbst ist der Schalter.
 */
function Offer({ d, busy, active, agreed, offer, rows, onSent, onAction }: {
  d: Filled; busy?: boolean; active: boolean;
  /** Ist zugesagt? Dann sind die Zeilen Historie und stehen zusammengeklappt da. */
  agreed: boolean;
  /** Die beiden Fristen des Belegs (Abschnitt «Bedingungen») – hier nur für «vollständig?». */
  offer: { lead: string; days: string };
  rows: PriceRow[];
  /** Der Entwurf ist hinaus – die getippten Preise dürfen fallen. */
  onSent: () => void;
  onAction: (body: Action) => void;
}) {
  const [picked, setPicked] = useState<DealParty | null>(null);
  const [shown, setShown] = useState(false);
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

  // ►►► **Wer den Preis nennt, nennt auch die beiden Fristen** (#854/#856). ◄◄◄
  //
  // Sie sind der Rest der Zusage: aus der Lieferfrist kommt der Termin, aus der
  // Zahlungsfrist die Fälligkeit – und, wenn sie null ist, die Vorauszahlung. Der Dienst
  // weist ein Angebot ohne sie ab (`_assert_terms`); dies ist die freundliche Hälfte.
  // Bei einer **Ausgabe** geht die Zeile leer hinaus, dort füllt sie die Gegenpartei.
  //
  // **Der Preis steht nicht mehr hier**, sondern an seiner Position (#862) – er kommt als
  // `rows` herein, damit dieselbe Bedingung gilt wie vorher: ohne Preis kein Angebot.
  const ready = !d.we_quote || (rows.some((r) => r.price.trim() !== '')
    && offer.lead !== '' && offer.days !== '');

  /** **Eine Abwahl gilt für die Anfrage, die man gerade stellt** (#835) – sie fällt mit
   *  dem Absenden. Sonst blieb der zweite Partner abgewählt, nachdem man den ersten
   *  gefragt hatte: «Bei 0 anbieten», gesperrt, bis zum Refresh. */
  const send = (parties: number[]) => {
    onAction({
      action: 'ask', parties,
      ...(d.we_quote ? {
        lines: rows.map((r) => ({
          article: r.article, price: r.price === '' ? '0' : r.price, vat: r.vat,
        })),
        lead_days: offer.lead === '' ? null : Number(offer.lead),
        payment_days: offer.days === '' ? null : Number(offer.days),
      } : {}),
    });
    setDropped([]);
    onSent();
  };

  // ►►► **Zusammengeklappt sagt EINE Zeile, wie viele es waren** (#899). ◄◄◄
  //
  // Bei genau einem Angebot wäre «1 von 1 Angeboten gewählt» eine Rechnung über nichts –
  // dort steht schlicht, was passiert ist.
  const summary = d.quotes.length === 1
    ? `${d.stages[0]?.label ?? 'Angebot'} angenommen`
    : `1 von ${d.quotes.length} Angeboten gewählt`;
  const folded = agreed && !shown;

  return (
    <div className="flex flex-col gap-2">
      {/* **Die Zeile ist der Schalter** – kein Knopf daneben, dieselbe Geste wie überall
          im Haus, wo ein Klick eine Ansicht öffnet. */}
      {agreed && d.quotes.length > 0 && (
        <button type="button" className="flex items-center gap-1.5 text-[12.5px] self-start"
          style={{ color: 'var(--fg-3)' }} aria-expanded={shown}
          onClick={() => setShown(!shown)}>
          <ChevronDown size={13} style={{
            color: 'var(--fg-4)', flex: 'none',
            transform: shown ? 'rotate(180deg)' : undefined,
          }} />
          {summary}
        </button>
      )}

      {!folded && d.quotes.map((q) => (
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
          <button type="button" className="erp-actbtn erp-actbtn-primary self-start"
            style={{ height: ACT_H.inline }} disabled={busy || chosen.length === 0 || !ready}
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
 * zu 8.1 % und eine Ausfuhr zu 0 % stehen auf demselben Papier.
 *
 * ►►► **Genannt werden sie an der POSITION selbst** (Testnotiz #862). ◄◄◄ Hier stand eine
 * zweite Tabelle mit denselben Zeilen und Eingabefeldern – *«der Positions-Abschnitt ist
 * doppelt»*, und das war er wörtlich: derselbe Datensatz, einmal als Auskunft und einmal
 * als Formular, in zwei Schreibweisen. Übrig bleiben die beiden **Fristen**: sie gehören
 * dem Angebot als Ganzem und keiner einzelnen Zeile.
 */
export type PriceRow = { article: number | null; price: string; vat: string };

/**
 * ►►► **Die Bedingungen — Währung und die beiden Fristen, an EINER Stelle.** ◄◄◄
 *
 * *Hier stand `OurOffer`: zwei Fristen unter dem Angebotsspiegel, und die Währung stand
 * eine Zeile darüber.* Als **Beleg** gelesen (#899) ist das derselbe Abschnitt: «zu
 * welchen Bedingungen». Er steht darum unter der Summe und über den Antworten – genau
 * dort, wo er auf einem Angebot steht.
 *
 * ►►► **Die Zahlungsfrist steht ÜBER der Lieferfrist** (Testnotiz #897). ◄◄◄
 *
 * Sie ist die folgenreichere der beiden: aus ihr kommt die Fälligkeit jeder Rechnung, und
 * wenn sie null ist, ist sie die **Vorauszahlung** – also die Frage, ob überhaupt geliefert
 * wird, bevor Geld da ist. Die Lieferfrist beantwortet «wann», die Zahlungsfrist «wann
 * und ob». Was mehr entscheidet, steht oben.
 *
 * **Beide sind Pflicht** (#854/#855/#856), und ihre üblichen Werte haben Namen: «Sofort»
 * bzw. «Vorauszahlung» statt einer 0, die aussieht wie eine Lücke. Der Dienst weist ein
 * Angebot ohne sie ab (`_assert_terms`); dies ist die freundliche Hälfte.
 *
 * **Nach der Zusage stehen sie als Auskunft da** – die Frist, wie sie heisst, und der
 * Liefertermin, den sie erzeugt hat. *Er stand einmal im Kopf der Karte; dort war er eine
 * Auskunft zwischen anderen, hier ist er die Antwort auf die Frage, die eine Zeile höher
 * steht.*
 */
function Terms({ d, busy, active, editable, value, onChange, onAction }: {
  d: Filled; busy?: boolean; active: boolean;
  /** Dürfen **wir** die Fristen nennen? Nur wo wir das Angebot schreiben (`we_quote`). */
  editable: boolean;
  value: { lead: string; days: string };
  onChange: (next: { lead: string; days: string }) => void;
  onAction: (body: Action) => void;
}) {
  const agreed = d.stage !== DEAL_STAGE.offer;
  // **Ohne Inhalt gibt es den Abschnitt nicht** – eine Überschrift über einer leeren
  // Fläche ist eine Auskunft, die nichts sagt. Bei einer *Ausgabe* vor der Zusage nennt
  // die Gegenpartei die Fristen an **ihrer** Zeile; hier bleibt dann die Währung.
  if (!may(d, active, 'currency') && !editable && !agreed) return null;
  return (
    <ModuleSection title="Bedingungen">
      <div className="flex flex-col gap-2">
        {/* ►►► **Die Währung ist eine Bedingung** (#864/#876/#881). ◄◄◄
            Sie ist eine **Entscheidung** über das, was hinausgeht – und ab der Zusage
            gebunden, weil draussen dann eine Zusage über diesen Betrag in *dieser*
            Währung liegt. Danach steht hier nichts mehr: dann sagen es die Beträge
            selbst. */}
        <Currency d={d} busy={busy} active={active} onAction={onAction} />
        {editable && (
          <>
            <TermField label={d.payment_term_label ?? 'Zahlungsfrist'} required
              value={value.days} onChange={(v) => onChange({ ...value, days: v })}
              terms={d.payment_terms ?? []} freeMin={d.term_free_min ?? 1}
              freeLabel={d.term_free_label ?? 'Individuell'} />
            <TermField label={d.lead_term_label ?? 'Lieferfrist'} required
              value={value.lead} onChange={(v) => onChange({ ...value, lead: v })}
              terms={d.lead_terms ?? []} freeMin={d.term_free_min ?? 1}
              freeLabel={d.term_free_label ?? 'Individuell'}
              preview={value.lead === '' ? undefined
                : `Liefertermin ab heute: ${localDate(inDays(Number(value.lead)))}`} />
          </>
        )}
        {!editable && agreed && (
          <div className="flex items-center gap-x-4 gap-y-1 flex-wrap text-[12px]">
            {/* ►►► **«0 Tage» gibt es nicht — sie heisst «Vorauszahlung»** (#885). ◄◄◄
                Gelesen aus derselben Liste, aus der sie gewählt wurde; ein Wert
                ausserhalb davon ist die freie Eingabe und heisst «x Tage». */}
            {d.due_days != null && (
              <span className="flex items-center gap-1.5">
                <span style={MICRO_LABEL}>{d.payment_term_label}</span>
                <span className="ix-tnum" style={{ color: 'var(--fg-2)' }}>
                  {termText(d.due_days, d.payment_terms)}</span>
              </span>
            )}
            {/* ►►► **Der Liefertermin — und ob er vorbei ist** (#814). ◄◄◄
                Ein Verzug ist kein Zustand, den jemand pflegt: er ist *Termin vorbei und
                noch nicht erledigt*, dieselbe Ableitung wie «überfällig» bei einer
                Forderung. Was man dann tun kann, gibt es alles schon – warten,
                stornieren, und das Geld läuft davon unabhängig weiter. */}
            {d.due_date && (
              <span className="flex items-center gap-1.5" style={{
                color: d.late ? 'var(--danger)' : undefined, cursor: 'help',
              }} data-tip={d.late
                ? 'Der zugesagte Liefertermin ist vorbei und das Modul ist noch nicht erledigt.'
                : 'Zugesagter Liefertermin – Zusagedatum plus Lieferfrist.'}>
                {d.late ? <AlertTriangle size={12} /> : <CalendarClock size={12} />}
                <span style={MICRO_LABEL}>{d.late ? 'überfällig seit' : 'Liefertermin'}</span>
                <span className="ix-tnum" style={{
                  color: d.late ? 'var(--danger)' : 'var(--fg-2)',
                }}>{localDate(d.due_date)}</span>
              </span>
            )}
          </div>
        )}
      </div>
    </ModuleSection>
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
function Sums({ rows, lines, label, decimals, code }: {
  rows: PriceRow[]; lines: Filled['lines']; label: string;
  /** Der Währungscode – er steht beim **Total**, der Zahl, die hinausgeht (#881). */
  code: string;
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
  let net = 0;
  const splits: { rate: string; tax: number }[] = [];
  buckets.forEach((sum, rate) => {
    net += sum;
    splits.push({ rate, tax: Math.round(sum * Number(rate) * unit / 100) / unit });
  });
  const tax = splits.reduce((n, s) => n + s.tax, 0);
  if (net === 0 && tax === 0) return null;
  return (
    <Totals net={net} splits={splits} total={net + tax} label={label}
      decimals={decimals} code={code} />
  );
}

/**
 * ►►► **Die Abrechnung — rechtsbündig, tabellarisch, mit einer Haarlinie.** ◄◄◄
 *
 * Zahlen werden von rechts gelesen, und der **Total** ist die eine Zahl, um die es geht:
 * er trägt die Linie über sich und die einzige kräftige Schrift. Struktur vor Fläche –
 * kein Kasten, keine zweite Farbe.
 *
 * **Es gibt sie einmal** (#899): die **Vorschau** aus den getippten Preisen und die
 * **gebuchte** Summe des Servers sind dieselbe Aufstellung, und sie standen als zwei
 * Bauteile in zwei Abschnitten – mit zwei Schreibweisen für Netto, Steuer und Total. Wer
 * eine davon ändert, ändert die andere nicht.
 *
 * **Ohne Netto bleibt der Total allein**, und das ist kein Sonderfall: bei einer *Ausgabe*
 * nennt die Gegenpartei den Preis, und die Steuer steht auf **ihrer** Rechnung – ein
 * «Netto 0.00» daneben wäre eine Behauptung über eine Zahl, die wir nicht haben.
 */
function Totals({ net, splits, total, label, decimals, code }: {
  net: number | string | null;
  /** Je Steuersatz eine Zeile – zwei Sätze auf einem Beleg sind der Normalfall. */
  splits: { rate: string; tax: number | string }[];
  total: number | string;
  label: string;
  /** Die kleinste Einheit dieser Währung (ISO 4217) – auch die Vorschau rundet je Währung. */
  decimals: number;
  code: string;
}) {
  return (
    // **Über die ganze Breite, Wort links, Zahl rechts** – die Ordnung, in der ein Beleg
    // seine Summe schreibt. Ein kompakter Block am rechten Rand wäre in einer 460 px
    // schmalen Karte enger als nötig, und die Zahlen stünden dann mitten in der Fläche
    // statt an ihrer Kante.
    <div style={{ minWidth: 0, paddingTop: 6 }}>
      <div className="grid gap-x-4 text-[12.5px] ix-tnum"
        style={{ gridTemplateColumns: '1fr max-content', rowGap: 2 }}>
        {net != null && (
          <>
            <span style={{ color: 'var(--fg-4)' }}>Netto</span>
            <span style={{ color: 'var(--fg-2)', textAlign: 'right' }}>
              {formatAmount(net, decimals)}</span>
          </>
        )}
        {/* **Je Satz eine Zeile** – zwei Sätze auf einem Beleg sind der Normalfall
            (sechs Wellen zu 8.1 %, eine Ausfuhr zu 0 %), und die Abrechnung verlangt sie
            einzeln. Eine Summe «MWST» allein wäre für die Abrechnung wertlos. */}
        {splits.map((v) => (
          <Fragment key={v.rate}>
            <span style={{ color: 'var(--fg-4)' }}>{label} {v.rate} %</span>
            <span style={{ color: 'var(--fg-2)', textAlign: 'right' }}>
              {formatAmount(v.tax, decimals)}</span>
          </Fragment>
        ))}
        {/* **Die Haarlinie geht über BEIDE Spalten** – als eigene Rasterzeile. An die
            beiden Zellen geschrieben wäre sie zweimal unterbrochen: der Spaltenabstand
            liegt dazwischen, und ein Strich mit einem Loch in der Mitte sieht nach einem
            Fehler aus, nicht nach einer Summe. */}
        {splits.length > 0 && (
          <span style={{
            gridColumn: '1 / -1', height: 1, marginTop: 3, marginBottom: 3,
            background: 'var(--border-2)',
          }} />
        )}
        <span className="font-semibold" style={{ color: 'var(--fg-1)' }}>Total</span>
        {/* ►►► **Die eine Zahl, die ihre Währung MITSAGT.** ◄◄◄ Nicht jede Zeile – der
            Beleg lautet auf eine Währung. Aber der Total ist die Zahl, die abgeschrieben,
            zitiert und überwiesen wird; sie ohne ihren Code zu zeigen hiesse, sich auf
            einen Blick nach oben zu verlassen. */}
        <span className="font-semibold" style={{ color: 'var(--fg-1)', textAlign: 'right' }}>
          {formatAmount(total, decimals)} {code}</span>
      </div>
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

  // ►►► **Kein «Offerte erfassen» mehr — es wird gespeichert** (Testnotiz #879). ◄◄◄
  //
  // *«Kann man diesen Button weglassen und ihn gegen die Autosave-Funktion ersetzen?»* –
  // Ja, und es ist die **Hausregel**, nicht eine Ausnahme: im ERP wird nicht abgeschickt,
  // sondern gespeichert (`use-autosave`, debounced). Der Knopf war der einzige seiner Art
  // in dieser Karte und sah aus, als täte er etwas anderes als das Tippen daneben.
  //
  // **Gespeichert wird erst, wenn die Zeile vollständig ist.** Der Dienst weist eine
  // Offerte ohne Betrag oder ohne eine der beiden Fristen ab (`_quote` → `_assert_terms`);
  // ein Auto-Save beim ersten Tastendruck liefe also gegen eine Fehlermeldung, die nur
  // sagt, dass man noch nicht fertig ist. Dieselbe Bedingung, die vorher den Knopf
  // sperrte – nur ohne Knopf.
  const filled = (d.we_quote || amount.trim() !== '') && lead !== '' && days !== '';
  const changed = `${amount}|${lead}|${days}` !== remote;
  const mayQuote = may(d, active, 'quote') && !chosen && !declined;
  useAutosave(`${party}|${amount}|${lead}|${days}`, mayQuote && filled && changed, () => {
    onAction({
      action: 'quote', party,
      // **Nur senden, was man auch nennt** – wo die Positionen den Preis tragen, bleibt
      // er, wie er ist (dieselbe Regel im Dienst).
      ...(d.we_quote ? {} : { amount }),
      lead_days: lead === '' ? null : Number(lead),
      payment_days: days === '' ? null : Number(days),
    });
  });

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
        {/* ►►► **Der Betrag nennt seine Währung** (Testnotiz #881). ◄◄◄ Sie stand als
            eigener Abschnitt darüber; hier ist sie dort, wo sie gebraucht wird – an der
            Zahl, die man abschreibt und vergleicht. */}
        {!declined && quote.amount && (
          <span className="ix-tnum text-[12.5px] font-semibold"
            style={{ color: 'var(--fg-1)', flex: 'none' }}>
            {formatAmount(quote.amount, d.currency_decimals)} {d.currency}
          </span>
        )}
        {/* **Beide Fristen stehen da, und jede sagt, welche sie ist** (#846). Die
            Lieferfrist stand als blosses «14 Tage» daneben, die **Zahlungsfrist** gar
            nicht – obwohl man sie eingeben kann und der Partner sie ändert. Zwei nackte
            Tageszahlen nebeneinander wären nicht unterscheidbar, also trägt jede ihr
            Wort im Hover und ihr Symbol daneben. */}
        {/* **Und die Frist heisst, wie sie heisst** (#885): «Vorauszahlung» statt «0», aus
            derselben Liste, aus der man sie wählt. */}
        {/* ►►► **Die Zahlungsfrist steht VOR der Lieferfrist** (Testnotiz #897). ◄◄◄
            Dieselbe Reihenfolge wie im Abschnitt «Bedingungen» – sie ist die
            folgenreichere Angabe (aus ihr kommt die Fälligkeit, und null heisst
            Vorauszahlung), und eine Zeile, die dieselben zwei Werte anders herum
            aufzählt als das Formular darüber, liest sich als zwei verschiedene
            Angaben. */}
        {!declined && quote.payment_days != null && (
          <span className="flex items-center gap-1 text-[12px] ix-tnum"
            style={{ color: 'var(--fg-4)', flex: 'none' }}
            data-tip={`${d.payment_term_label}: ${termText(quote.payment_days, d.payment_terms)}`}>
            <Wallet size={11} />{termText(quote.payment_days, d.payment_terms)}
          </span>
        )}
        {!declined && quote.lead_days != null && (
          <span className="flex items-center gap-1 text-[12px] ix-tnum"
            style={{ color: 'var(--fg-4)', flex: 'none' }}
            data-tip={`${d.lead_term_label}: ${termText(quote.lead_days, d.lead_terms)}`}>
            <CalendarClock size={11} />{termText(quote.lead_days, d.lead_terms)}
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
              {/* **Dieselben beiden Fristen wie im Angebot** – eine Ebene später, und
                  darum dasselbe Bauteil: sie sind hier seine Angabe statt unserer, aber
                  es ist dieselbe Frage (#854/#856). Zwei Bauarten für ein Feld liefen
                  beim nächsten üblichen Wert auseinander. */}
              {/* ►►► **Was aus der Lieferfrist folgt, steht darunter** (#884). ◄◄◄
                  *«Bei Datum muss man immer rechnen»* – eben: darum bleibt die Eingabe
                  «in x Tagen», und **das Datum rechnet das System**. Es ist dasselbe, das
                  nach der Zusage als Liefertermin im Kopf steht (`_delivery` =
                  Zusagedatum + Frist); vor der Zusage ist der Bezug **heute**, und genau
                  das sagt das Wort «ab heute». Ein eigenes Datumsfeld daneben wäre die
                  zweite Aussage über dieselbe Sache. */}
              {/* **Zahlungsfrist über Lieferfrist** (#897) – dieselbe Reihenfolge wie
                  im Abschnitt «Bedingungen»; zwei Formulare für dieselben zwei Fragen
                  dürfen nicht anders herum fragen. */}
              <div style={{ flex: '1 1 100%', minWidth: 0 }}
                className="flex flex-col gap-2">
                <TermField label={d.payment_term_label ?? 'Zahlungsfrist'} required
                  value={days} onChange={setDays}
                  terms={d.payment_terms ?? []} freeMin={d.term_free_min ?? 1}
                  freeLabel={d.term_free_label ?? 'Individuell'} />
                <TermField label={d.lead_term_label ?? 'Lieferfrist'} required
                  value={lead} onChange={setLead}
                  terms={d.lead_terms ?? []} freeMin={d.term_free_min ?? 1}
                  freeLabel={d.term_free_label ?? 'Individuell'}
                  preview={lead === '' ? undefined
                    : `Liefertermin ab heute: ${localDate(inDays(Number(lead)))}`} />
              </div>
            </>
          )}
          {/* ►►► **Absage und Zuschlag sind Symbol-Knöpfe** (Testnotiz #880). ◄◄◄
              *«Ein Icon, und beim Hover der Text dazu»* – dieselbe Geste wie die
              Modul-Palette, und in einer 460 px schmalen Spalte macht sie aus zwei
              Textknöpfen zwei Zeichen. Der Zuschlag bleibt die **naheliegende** Handlung:
              das sagt seine Fläche (`primary`), nicht seine Breite. */}
          <Actions>
            {may(d, active, 'decline') && !declined && (
              <ActionButton icon={CircleSlash} label="Absage" height={ACT_H.inline}
                disabled={busy} onClick={() => onAction({ action: 'decline', party })} />
            )}
            {may(d, active, 'agree') && !declined && (
              <ActionButton icon={Check} label={d.stages[0]?.verb ?? 'Annehmen'}
                tone="primary" height={ACT_H.inline} disabled={busy || !quote.amount}
                tip={quote.amount ? undefined : 'Ohne Preis gibt es keine Zusage'}
                onClick={() => onAction({ action: 'agree', party })} />
            )}
          </Actions>
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
  // ►►► **Der Hover sagt, WAS das ist — nicht noch einmal, was dasteht** (#882). ◄◄◄
  //
  // *«Die Hover-Information ist scheisse.»* – Sie lautete «Was ist zu tun? 123456», also
  // die Frage plus **denselben Wert, der einen Zentimeter weiter links steht**. Eine
  // Blase, die den sichtbaren Text wiederholt, ist keine Auskunft; sie ist die Stelle, an
  // der man aufhört, Blasen zu lesen.
  //
  // Erklärt wird darum die **Angabe**: was für eine Art Wert das ist und wofür er da ist.
  // Der Wert selbst steht in der Zeile – und wo er zu lang wird, ist er ein Link, und der
  // trägt seine Adresse ohnehin im Hover.
  const TIP = `Bestellangabe für diesen ${DEAL_PARTY} – ${DEAL_TASK_HINT.toLowerCase()}.`;
  if (!link) {
    return (
      <span className="flex items-center gap-1.5 text-[12px]" style={{ paddingBottom: 4 }}
        data-tip={TIP}>
        <ClipboardList size={12} style={{ color: 'var(--fg-4)', flex: 'none' }} />
        <span className="ix-tnum truncate" style={{ color: 'var(--fg-3)', minWidth: 0 }}>
          {value}</span>
      </span>
    );
  }
  return (
    <a href={value} target="_blank" rel="noopener noreferrer" data-tip={`${TIP} ${value}`}
      className="flex items-center gap-1 text-[12px] truncate self-start"
      style={{ color: 'var(--accent)', paddingBottom: 4, minWidth: 0 }}>
      <ArrowUpRight size={12} style={{ flex: 'none' }} />
      <span className="truncate">Beim {DEAL_PARTY} öffnen</span>
    </a>
  );
}

/*
 * ►►► **Den «bestätigten Auftrag» gibt es nicht mehr als Block** (Testnotiz #899). ◄◄◄
 *
 * Hier stand `Agreed`: Partner, Abrechnung und Bedingungen in einem eigenen Abschnitt
 * unter der Stufe «Auftrag». Er war die richtige Antwort auf #847 («schaut total
 * beschissen aus») – aber er war ein **zweiter Beleg neben dem ersten**: derselbe
 * Partner, dieselbe Summe, dieselben Fristen, nur eine Stufe später und in anderer
 * Reihenfolge als oben.
 *
 * *«Alle dargestellten Informationen bauen aufeinander auf … man könnte es wie ein
 * Dokument aufbauen und dann Schritt für Schritt erweitern.»* – Genau das: seine drei
 * Teile sind dorthin gegangen, wo sie auf einem Beleg stehen, und **nur** dorthin.
 *
 * * **Wer** → in den Belegkopf (`DocHead`, «An 100000123 Muster AG», mit dem Datum).
 * * **Was es kostet** → unter seine Positionen (`Goods` → `Totals`) – dieselbe
 *   Aufstellung, die vorher die Vorschau war, jetzt mit den gebuchten Zahlen.
 * * **Zu welchen Bedingungen** → in den Abschnitt `Terms`, neben die Frist, aus der der
 *   Termin kommt.
 *
 * Die Karte **wächst** damit, statt einen Block dazuzuschalten: dieselben Zeilen tragen
 * vor der Zusage einen Entwurf und danach die Zusage.
 */

/**
 * ►►► **Wie weit eine Rechnung ist — ein Punkt AN IHR** (Testnotiz #875). ◄◄◄
 *
 * *«Ich brauche diese Anzeige so nicht. Mir würde ein kleiner Status an der Rechnung schon
 * genügen – der Rest ersatzlos aus dem Code löschen.»*
 *
 * Hier stand eine Leiste über der Liste (`MoneyBar`): *bezahlt · offen · überzahlt · nicht
 * berechnet* als Anteile eines Ganzen. Sie war richtig gedacht, solange ein Vorgang
 * mehrere Rechnungen tragen konnte – da war die Aufteilung eine eigene Aussage. **Seit
 * #866 gibt es je Modul genau eine**, und damit sagt sie dasselbe wie die eine Zeile
 * darunter, nur als Balken: eine Zusammenfassung von einem.
 *
 * Übrig bleibt, was die Frage wirklich beantwortet: **Punkt und Wort an der Rechnung** –
 * dieselbe Anatomie, mit der das Haus jeden Status schreibt. Der Betrag steht daneben,
 * wenn noch etwas offen ist; ist nichts mehr offen, heisst der Punkt schlicht «Bezahlt».
 *
 * **Abgeleitet, nicht gemeldet**: aus `open` und `overdue` dieser Zeile, die beide
 * ohnehin mitreisen. Ein Zustandsfeld dafür wäre die zweite Wahrheit neben der Zahl.
 */
/**
 * **Wie schmal eine Beleg-Nummer noch lesbar ist** – «100000887-1» in Tabellenziffern.
 * Sie ist die Kennung der Zeile; darunter bricht die Zeile um, statt sie zu kappen.
 */
const REF_MIN = 96;

type InvoiceState = { label: string; color: string; hint: string };

function invoiceState(d: Filled, e: Filled['entries'][number]): InvoiceState | null {
  if (e.kind !== 'charge' || e.reverses != null || e.open == null) return null;
  const open = Number(e.open);
  // **Storniert sagt die Zeile selbst** – ein zweiter Punkt daneben wäre dasselbe Wort.
  if (e.reversed) return null;
  if (open === 0) {
    return {
      label: 'Bezahlt', color: 'var(--success)',
      hint: 'Gefordert und beglichen – auf dieser Rechnung ist nichts mehr offen.',
    };
  }
  if (open < 0) {
    return {
      label: 'Überzahlt', color: 'var(--info)',
      hint: 'Mehr bezahlt als gefordert – so viel ist zurückzugeben.',
    };
  }
  return e.overdue
    ? { label: 'Überfällig', color: 'var(--danger)', hint: 'Fällig und noch nicht bezahlt.' }
    : { label: d.open_word, color: 'var(--warning)', hint: 'Gefordert und noch nicht bezahlt.' };
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
  /**
   * ►►► **Ein Formular gehört zu einer Zeile** (Testnotizen #859/#861). ◄◄◄
   *
   * Vorher war es ein Zustand ohne Adressat (`'' | 'charge' | 'payment'`): das Formular
   * stand unter der Liste, und **worauf** die Zahlung ging, entschied ein Auswahlfeld
   * darin. Jetzt trägt der Zustand die **Rechnung** mit – der Knopf steht an ihr, also
   * ist die Frage schon beantwortet, wenn das Formular aufgeht.
   */
  const [form, setForm] = useState<{
    kind: 'charge' | 'payment'; charge?: number | null; preset?: string;
  } | null>(null);
  /** Welche Rechnung gerade online bezahlt wird. Ein eigener Zustand, weil die Karte
   *  kein `Entry` ist: sie bucht nichts und schickt keine Handlung – sie führt aus. */
  const [paying, setPaying] = useState<number | null>(null);
  /** Welche Rechnung ihre Bankverbindung zeigt (#865) – eine **Auskunft**, keine Buchung. */
  const [transfer, setTransfer] = useState<number | null>(null);
  /**
   * ►►► **Nach dem Bezahlen wird kurz nachgefragt** (Testnotiz #857). ◄◄◄
   *
   * «Es stand, dass es bestätigt wird, sobald der Zahlungsdienst es meldet – angezeigt
   * hat er es dann auch, aber erst nach einem Refresh.» Genau so ist es gebaut, und der
   * Grund ist richtig: **gebucht wird vom Webhook**, nicht vom Browser des Zahlenden
   * (wer ihn schliesst, darf keine Buchung verschlucken). Zwischen dem «bezahlt» der
   * Karte und der Meldung liegen ein bis drei Sekunden – und in denen lädt ein einziges
   * Nachladen zu früh.
   *
   * Der einfache Weg dafür ist **fragen**, nicht ein zweiter Kanal: kein WebSocket, kein
   * SSE für **ein** Ereignis, das einmal je Zahlung eintrifft. Nachgefragt wird, bis die
   * Zeile da ist – erkennbar daran, dass sich die Summe der Zahlungen ändert –, längstens
   * ein paar Sekunden. Bleibt sie aus, steht die Karte still da, statt es zu behaupten:
   * der Nachweis ist die Zeile, und die entsteht dort, wo das Geld gemeldet wird.
   */
  const [wait, setWait] = useState<{ paid: string; tries: number } | null>(null);
  useEffect(() => {
    if (!wait) return;
    // **Die Zeile ist da** – oder wir haben lange genug gefragt.
    if (d.paid !== wait.paid || wait.tries >= WAIT_TRIES) {
      // ►►► **Und dann schliesst die Bezahlkarte** (Testnotiz #893). ◄◄◄
      //
      // *«Es hat geklappt und wird angezeigt, aber diese Meldung verschwindet erst nach
      // einem Refresh.»* – Sie stand still da, weil niemand sie zumachte: `onDone` startete
      // das Nachfragen, aber `paying` blieb auf der Rechnung stehen, und die Karte zeigte
      // weiter ihren Abschluss-Satz («… sobald der Zahlungsdienst sie bestätigt hat»).
      // Genau **dann**, wenn die Zeile erscheint, ist der Satz überholt – also endet die
      // Karte an derselben Bedingung, an der auch das Nachfragen endet. Keine zweite Uhr,
      // kein zweiter Zustand: es ist dieselbe Antwort auf dieselbe Frage.
      if (d.paid !== wait.paid) setPaying(null);
      setWait(null);
      return;
    }
    const t = setTimeout(() => {
      setWait((w) => (w ? { ...w, tries: w.tries + 1 } : w));
      onPaid?.();
    }, WAIT_STEP);
    return () => clearTimeout(t);
  }, [wait, d.paid, onPaid]);
  // Ohne Zahlen gibt es nichts zu zeigen – so sieht es eine Gegenpartei.
  if (d.open == null) return null;

  // ►►► **Die Zahlungen stehen unter IHRER Rechnung** (Testnotiz #861). ◄◄◄
  //
  // *«Die Zahlung sollte zur Rechnung gruppiert werden.»* – Sie standen als **flache**
  // Liste da, chronologisch, und die Zugehörigkeit war ein kleines «auf 100000801-1» am
  // Zeilenende: bei zwei Rechnungen und vier Zahlungen musste man Nummern vergleichen,
  // um zu sehen, was worauf ging.
  //
  // Eingerückt sagt es die **Form** – dieselbe Geste wie bei der Stückliste unter ihrer
  // Einzelinstanz (#724: «erst wohin, dann was»). Ein Feld dafür braucht es nicht: die
  // Zuordnung steht seit #858 an der Zahlung.
  //
  // **Unter die Rechnung gehört auch ihr Storno**: er ist ihre Gegenbuchung, kein
  // eigenständiger Beleg – oben stünden sonst zwei Zeilen mit demselben Betrag und
  // verschiedenem Vorzeichen, und welche welche zurücknimmt, sähe man nicht.
  const invoices = d.entries.filter((e) => e.kind === 'charge' && e.reverses == null);
  const under = (id: number) => d.entries.filter((e) => (e.kind === 'payment'
    ? e.charge_id === id : e.reverses === id));
  // **Was zu keiner Rechnung gehört, verschwindet nicht.** Zahlungen aus der Zeit vor
  // #858 tragen keine Zuordnung, und eine Online-Zahlung auf eine inzwischen stornierte
  // Rechnung ebenso wenig – geraten wird nichts, gezeigt schon.
  const loose = d.entries.filter((e) => e.kind === 'payment' && e.charge_id == null);

  const row = (e: Filled['entries'][number], sub: boolean) => (
    <EntryRow key={e.id} d={d} e={e} sub={sub} busy={busy} active={active}
      onAction={onAction}
      onPay={(charge, preset) => {
        setPaying(null); setTransfer(null);
        setForm({ kind: 'payment', charge, preset });
      }}
      onPayOnline={(charge) => {
        setForm(null); setTransfer(null);
        setPaying((p) => (p === charge ? null : charge));
      }}
      onTransfer={(charge) => {
        setForm(null); setPaying(null);
        setTransfer((t) => (t === charge ? null : charge));
      }}
      onRefund={(entry) => api.refundPayment(orderObjectId, stepId, entry)
        .then(() => { setWait({ paid: d.paid ?? '', tries: 0 }); onPaid?.(); })}
      panel={(
        <>
          {paying === e.id && (
            <PayOnline orderObjectId={orderObjectId} stepId={stepId} chargeId={e.id}
              label={d.pay_online_word}
              onDone={() => { setWait({ paid: d.paid ?? '', tries: 0 }); onPaid?.(); }}
              onClose={() => setPaying(null)} />
          )}
          {transfer === e.id && (
            <Transfer orderObjectId={orderObjectId} stepId={stepId} entryId={e.id} />
          )}
          {form?.kind === 'payment' && form.charge === e.id && (
            <Entry kind="payment" d={d} busy={busy} preset={form.preset}
              chargeId={e.id}
              onCancel={() => setForm(null)}
              onSubmit={(body) => { setForm(null); onAction(body); }} />
          )}
        </>
      )} />
  );

  return (
    <div className="flex flex-col gap-2">
      {(invoices.length > 0 || loose.length > 0) && (
        <div className="flex flex-col">
          {invoices.map((inv) => (
            <div key={inv.id} className="flex flex-col">
              {row(inv, false)}
              {/* **Die Einrückung IST die Zugehörigkeit** – eine Haarlinie links führt
                  das Auge zurück auf die Rechnung, unter der sie stehen. */}
              {under(inv.id).length > 0 && (
                <div className="flex flex-col"
                  style={{ marginLeft: 13, paddingLeft: 9, borderLeft: '1px solid var(--border-1)' }}>
                  {under(inv.id).map((e) => row(e, true))}
                </div>
              )}
            </div>
          ))}
          {loose.length > 0 && (
            <div className="flex flex-col">
              {invoices.length > 0 && (
                <span style={{ ...MICRO_LABEL, paddingTop: 8 }}
                  data-tip="Diese Zahlungen nennen keine Rechnung – geraten wird nichts.">
                  Nicht zugeordnet
                </span>
              )}
              {loose.map((e) => row(e, false))}
            </div>
          )}
        </div>
      )}

      {/* ►►► **Hier unten steht GENAU EINE Handlung** (Testnotizen #859/#874). ◄◄◄

          Bezahlen, überweisen und stornieren gehören zu **einer** Rechnung, also stehen sie
          an ihrer Zeile. Übrig bleibt die **Rechnung selbst** – sie gehört keiner Zeile,
          sie entsteht erst.

          **Zwei Knöpfe sind dabei gefallen** (#874 – *«gibt es hier Buttons, die doppelt
          sind bzw. in der Abfolge und der Logik keinen Sinn machen?»*):

          * **«Gutschrift erfassen»** stand hier, sobald die eine Rechnung dieses Moduls
            stand (#866) – und daneben, an ihrer Zeile, gab es bereits «Gutschrift»
            (`reverse_word`). Zwei Knöpfe mit demselben Wort, zwei verschiedene Wirkungen:
            der eine nimmt **diese Rechnung** zurück (mit Bezug, und er gibt den Platz für
            eine neue frei), der andere buchte eine **freistehende** negative Forderung,
            die zu keiner Rechnung gehörte und in der Liste als zweite Rechnung erschien.
            Was #866 für eine Korrektur vorsieht, steht in seinem eigenen Fehlersatz:
            **stornieren und neu stellen**. Eine Minderung ohne Rücknahme (Kulanz) ist die
            Gutschrift an der Zeile.
          * **«Zahlung erfassen»** stand hier für den Fall «es gibt keine Rechnung» – den
            gibt es nicht: ``can`` führt ``pay`` erst, wenn eine Forderung gebucht ist
            (#822), und ohne Forderung ist die Liste leer. Ein Ast, den niemand erreicht,
            ist von einem kaputten nicht zu unterscheiden. */}
      {may(d, active, 'charge') && !d.credit_only && (
        <button type="button" className={`erp-actbtn self-start ${d.next_charge != null
          ? 'erp-actbtn-primary' : 'erp-actbtn-neutral'}`}
          disabled={busy} style={{ height: ACT_H.inline }}
          data-tip="Eine Forderung buchen – ein negativer Betrag ist die Gutschrift."
          onClick={() => setForm(form?.kind === 'charge' ? null : { kind: 'charge' })}>
          <FileText size={13} /> {d.charge_word}
        </button>
      )}

      {/* Die Forderung gehört keiner Zeile – sie entsteht erst. */}
      {form?.kind === 'charge' && (
        <Entry kind="charge" d={d} busy={busy}
          onCancel={() => setForm(null)}
          onSubmit={(body) => { setForm(null); onAction(body); }} />
      )}
      {form?.kind === 'payment' && form.charge == null && (
        <Entry kind="payment" d={d} busy={busy} preset={form.preset}
          onCancel={() => setForm(null)}
          onSubmit={(body) => { setForm(null); onAction(body); }} />
      )}

      {/* **Was gerade passiert, steht da – und es behauptet keine Buchung.** Die Zeile
          entsteht, wenn der Dienst sie meldet; bis dahin ist «wird gebucht» die ehrliche
          Auskunft und «gebucht» wäre beim nächsten Blick eine Lüge. */}
      {wait && (
        <span className="flex items-center gap-1.5 text-[12.5px]"
          style={{ color: 'var(--fg-4)' }}>
          <Loader2 size={13} className="animate-spin" />
          Zahlung ausgeführt – sie wird gebucht, sobald der Zahlungsdienst sie meldet.
        </span>
      )}
    </div>
  );
}

/**
 * ►►► **Eine Zeile Geld — und was man AN IHR tun kann** (Testnotizen #859/#860). ◄◄◄
 *
 * *«Wie kann ich bestimmen, welche Rechnung ich bezahle?»* – Gar nicht, und das war der
 * Fehler: die Knöpfe standen **unter** der Liste, also galten sie dem Vorgang. Kassiert
 * wurde immer die älteste offene (`stripe_pay.prepare` nahm `open_charges[0]`), und der
 * Betrag kam aus einem Auswahlfeld im Formular.
 *
 * Ein Knopf **an** der Zeile beantwortet die Frage, indem er sie nicht stellt.
 *
 * ►►► **Storno ODER Gutschrift — dasselbe Verb, zwei Wörter** (#860). ◄◄◄ *«Wenn bezahlt
 * wurde, dann kann ich ja quasi nicht mehr stornieren.»* – Richtig: dann heisst dieselbe
 * Gegenbuchung **Gutschrift**, und danach steht die Erstattung an. Welches Wort gilt,
 * **sagt der Server** (`reverse_word`, aus dem, was auf diese Rechnung geflossen ist) –
 * eine zweite Formel hier wiche ab und sähe trotzdem richtig aus.
 */
function EntryRow({ d, e, sub, busy, active, panel, onAction, onPay, onPayOnline,
  onTransfer, onRefund }: {
  d: Filled; e: Filled['entries'][number];
  /** Steht sie eingerückt unter ihrer Rechnung? Dann trägt sie keine eigene Trennlinie. */
  sub: boolean;
  busy?: boolean; active: boolean;
  /** Was unter dieser Zeile aufgeht – Formular, Bezahlkarte oder Bankverbindung. */
  panel: React.ReactNode;
  onAction: (body: Action) => void;
  /** `null` heisst «keiner Rechnung zugeordnet» – dann steht das Formular unten. */
  onPay: (charge: number | null, preset?: string) => void;
  onPayOnline: (charge: number) => void;
  onTransfer: (charge: number) => void;
  onRefund: (entry: number) => void;
}) {
  const invoice = e.kind === 'charge';
  const tip = taxTip(d, e);
  const state = invoiceState(d, e);
  return (
    <div className="flex flex-col">
      <div className="flex items-center gap-2 py-1 text-[12.5px] flex-wrap"
        style={{ borderTop: sub ? undefined : '1px solid var(--border-1)' }}>
        <span style={{ color: 'var(--fg-4)', display: 'flex', flex: 'none' }}
          data-tip={invoice ? d.charge_word : d.payment_word}>
          {invoice ? <FileText size={13} /> : <Wallet size={13} />}
        </span>
        <span className="ix-tnum font-semibold" style={{
          color: e.overdue ? 'var(--danger)' : 'var(--fg-1)', flex: 'none',
          cursor: tip ? 'help' : undefined,
        }} data-tip={tip || undefined}>{formatAmount(e.amount, d.currency_decimals)}</span>
        {/* **Die Referenz nimmt den Rest und wird gekappt, das Datum nicht.**
            Umgekehrt lief der Datumstext über seine eigene Box hinaus – gemessen
            380,1 px bei 375 px Fenster, und kein Element-Rahmen zeigte es. */}
        {/* ►►► **Aber sie wird nicht bis zur Unkenntlichkeit gekappt.** ◄◄◄ Sie ist die
            **Nummer des Belegs**, also seine Kennung – bei «100…» weiss niemand mehr,
            welche Rechnung dasteht. Sie schrumpft darum nur bis `REF_MIN`; darunter
            **bricht die Zeile um** (sie ist `flex-wrap`), statt die Identität
            wegzuschneiden. Dieselbe Lehre wie bei der Positionszeile (#847): ohne
            Untergrenze läuft nichts über und die Sache ist trotzdem nicht mehr benannt. */}
        {e.reference && (
          <span className="ix-tnum truncate flex-1" data-tip={e.reference}
            style={{ color: 'var(--fg-3)', minWidth: REF_MIN }}>{e.reference}</span>
        )}
        {/* ►►► **«auf 100000801-1» steht nicht mehr da** (#861). ◄◄◄ Die Zuordnung sagt
            seit dieser Runde die **Einrückung**; sie zusätzlich auszuschreiben wäre
            dieselbe Angabe zweimal, und die zweite kostet in einer engen Zeile den Platz,
            den das Datum braucht. Wo sie **fehlt**, sagt es die Gruppe darüber. */}
        {/* ►►► **Der kleine Status an der Rechnung** (Testnotiz #875). ◄◄◄ Punkt + Wort –
            die Anatomie jedes Status im Haus –, und der Betrag daneben, solange noch
            etwas offen ist. Er ersetzt die Leiste über der Liste: bei **einer** Rechnung
            je Modul (#866) war sie die Zusammenfassung von einem. */}
        {state && (
          <span className="flex items-center gap-1.5 text-[11.5px]"
            style={{ color: 'var(--fg-4)', flex: 'none', cursor: 'help' }}
            data-tip={state.hint}>
            <span aria-hidden className="rounded-full" style={{
              width: 7, height: 7, flex: 'none', background: state.color,
            }} />
            {state.label}
            {e.open != null && Number(e.open) !== 0 && (
              <span className="ix-tnum">{formatAmount(e.open, d.currency_decimals)}</span>
            )}
          </span>
        )}
        {/* ►►► **Ein Datum, und es sagt die Frist** (Testnotiz #890). ◄◄◄ Die beiden
            Daten stehen im Hover; in der Zeile steht, was man wissen will. */}
        <span style={{ color: e.overdue ? 'var(--danger)' : 'var(--fg-4)', flex: 'none',
          cursor: 'help' }} data-tip={dateText(e).tip}>{dateText(e).text}</span>
        {/* **Wie bezahlt wurde** (#865) – bar, Überweisung, Karte. `null` heisst «nicht
            festgehalten», nicht «bar»; dann steht hier nichts. */}
        {e.method_label && (
          <span className="text-[11.5px]" style={{ color: 'var(--fg-4)', flex: 'none' }}
            data-tip={`${d.method_label}: ${e.method_label}`}>{e.method_label}</span>
        )}
        {e.reverses != null && (
          <span className="text-[11.5px]" style={{ color: 'var(--fg-4)', flex: 'none' }}
            data-tip={reversedRef(d, e.reverses)}>Storno</span>
        )}
        {e.reversed && (
          <span className="text-[11.5px]" style={{ color: 'var(--fg-4)', flex: 'none' }}>
            storniert
          </span>
        )}

        {/* ►►► **Jeder Knopf dieser Zeile klappt seinen Namen aus** (Testnotizen
            #888/#895/#896/#900). ◄◄◄ Dreimal derselbe Satz an drei Zeilen – Rechnung,
            bezahlte Rechnung, Karten-Zahlung –, also ist es keine Eigenschaft der Zeile,
            sondern die Form eines Knopfes im Haus (`ActionButton`).

            ►►► **Und sie stehen darum in EINER Zeile, die nicht umbricht.** ◄◄◄ Genau
            daran scheiterte der erste Anlauf: die Angaben-Zeile ist `flex-wrap`, der
            aufklappende Knopf liess sie neu umbrechen, der Zeiger fiel vom Knopf, er
            klappte ein, die Zeile brach zurück – gemessen 32 → 63 → 51 → 59 px in 800 ms.
            In `Actions` schiebt er nur seine Nachbarn zur Seite.

            ►►► **Und die Gruppe bekommt eine EIGENE Zeile** (`flex: 1 1 100%`). ◄◄◄
            Gemessen bei 375 px: als letztes Kind der umbrechenden Angaben-Zeile brach
            **sie selbst** um, sobald ein Knopf aufklappte – der Knopf sprang eine Zeile
            tiefer, der Zeiger verlor ihn, er klappte ein, die Gruppe sprang zurück
            (32 → 66 → 32 → 57 → … px). Eine eigene Zeile kann nicht umbrechen; dieselbe
            Form, die die Angebotszeile seit #752 hat (oben wer und wie viel, darunter die
            Handlungen). **Linksbündig**, nicht `margin-left: auto`: rechts angeschlagen
            wanderte die ganze Gruppe beim Aufklappen nach links – und mit ihr der Knopf
            unter dem Zeiger. */}
        <Actions style={{ flex: '1 1 100%' }}>
        {/* ►►► **Zahlung erfassen — an der Rechnung, die sie begleicht** (#859), und nur
            solange auf ihr etwas AUSSTEHT (#894). ◄◄◄
            *«Braucht es diesen Button noch, wenn der Status auf grün ist – bezahlt?»* –
            Nein: an einer ausgeglichenen Rechnung gibt es nichts mehr aufzuschreiben.
            **Überzahlt bleibt er** (offen < 0): dann steht die Rückgabe an, und die ist
            eine gewöhnliche Zahlung mit negativem Betrag. Eine Ableitung aus derselben
            Zahl, die den Punkt daneben färbt – kein zweiter Zustand. */}
        {invoice && may(d, active, 'pay') && !e.reversed && Number(e.open ?? 0) !== 0 && (
          <ActionButton icon={Wallet} label={d.payment_word} disabled={busy}
            tip={`Aufschreiben, was auf diese Rechnung geflossen ist.`}
            onClick={() => onPay(e.id)} />
        )}
        {/* **Bezahlen ist eine dritte Handlung, kein zweites «erfassen».** «Erfassen»
            schreibt auf, was geschehen ist; dieser Knopf lässt es geschehen – und bucht
            selbst nichts. Ob es ihn gibt, sagt `can`; **welche** Rechnung er kassiert,
            sagt die Zeile, an der er steht. */}
        {invoice && may(d, active, 'pay_online') && Number(e.open ?? 0) > 0 && (
          <ActionButton icon={CreditCard} label={d.pay_online_word} tone="primary"
            disabled={busy}
            tip="Gebucht wird, sobald der Zahlungsdienst es bestätigt."
            onClick={() => onPayOnline(e.id)} />
        )}
        {/* ►►► **Die dritte Bezahlart ist eine AUSKUNFT** (#865). ◄◄◄ Bar wird erfasst,
            die Karte wird ausgeführt – die **Überweisung** löst der Zahlende selbst aus,
            und was er dafür braucht, sind Angaben: Bankverbindung, Referenz, QR. */}
        {e.transferable && (
          <ActionButton icon={Landmark} label={d.transfer_word}
            tip="Bankverbindung und QR-Rechnung zu diesem Beleg."
            onClick={() => onTransfer(e.id)} />
        )}
        {/* **Storno ODER Gutschrift** – dieselbe Gegenbuchung, und das Wort kommt vom
            Server (#860): was bezahlt ist, nimmt man nicht zurück, man schreibt es gut. */}
        {invoice && may(d, active, 'reverse') && !e.reversed && e.reverses == null && (
          <ActionButton icon={CircleSlash} label={e.reverse_word ?? 'Stornieren'}
            tone="danger" disabled={busy}
            tip={'Es entsteht eine Gegenbuchung mit eigener Nummer; beide Zeilen bleiben '
              + 'stehen.'}
            onClick={() => onAction({ action: 'reverse', entry: e.id })} />
        )}
        {/* ►►► **Zurückerstatten — über den Dienst, der eingezogen hat** (#860). ◄◄◄
            Nur an einer **Karten**-Zahlung: bar und per Überweisung ist die Erstattung
            die Korrektur daneben, eine gewöhnliche Zahlung mit negativem Betrag. */}
        {!invoice && e.refundable && (
          <ActionButton icon={RotateCcw} label={d.refund_online_word} disabled={busy}
            tip={'Der Zahlungsdienst gibt die Belastung zurück; gebucht wird, sobald er '
              + 'es meldet.'}
            onClick={() => onRefund(e.id)} />
        )}
        {/* **Korrigieren ist kein neues Verb** (#842) – es öffnet die gewöhnliche
            Erfassung mit dem **negativen Betrag vorbelegt**. Ob es ein Erfassungsfehler
            war oder ob das Geld zurückkam, weiss nur ein Mensch. */}
        {!invoice && may(d, active, 'pay') && (
          <ActionButton icon={Undo2} label={d.refund_word} disabled={busy}
            tip={'Erfasst eine zweite Zahlung über den negativen Betrag – der '
              + 'Erfassungsfehler ebenso wie die Erstattung von Hand.'}
            onClick={() => onPay(e.charge_id ?? null, negate(e.amount))} />
        )}
        </Actions>
      </div>
      {panel}
    </div>
  );
}

/**
 * ►►► **Wie man diese Rechnung überweist** (Testnotiz #865). ◄◄◄
 *
 * *«Am besten einen international gültigen QR-Code, welcher vom Kunden gescannt werden
 * kann, damit man die Überweisung teilautomatisch machen kann.»*
 *
 * **Bankverbindung im Klartext UND als Code** – nicht entweder-oder: der QR spart das
 * Abtippen, der Klartext ist der Weg, wenn die Kamera nicht mitspielt oder die Bank den
 * Code nicht kennt. Wo es keinen geben kann (fremde Währung, keine CH-IBAN), steht der
 * **Grund** daneben statt einer leeren Fläche – ein QR, der in der App des Kunden einen
 * Fehler wirft, wäre schlimmer als keiner.
 *
 * **Erzeugt wird er im Backend** (`services/qrbill`): die Nutzlast ist eine Liste von
 * einunddreissig Zeilen in fester Reihenfolge, und eine zweite Fassung hier wäre die
 * Stelle, an der beim nächsten Feld eine Zeile verrutscht – das sieht man einem QR nicht
 * an. Geholt wird er **erst auf Klick**; er ist ein paar Kilobyte SVG.
 */
function Transfer({ orderObjectId, stepId, entryId }: {
  orderObjectId: number; stepId: number; entryId: number;
}) {
  const [info, setInfo] = useState<TransferInfo | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let dead = false;
    api.dealTransfer(orderObjectId, stepId, entryId)
      .then((t) => { if (!dead) setInfo(t); })
      .catch((e) => { if (!dead) setError(e instanceof Error ? e.message : String(e)); });
    return () => { dead = true; };
  }, [orderObjectId, stepId, entryId]);
  return (
    <div className="flex flex-col gap-2" style={{
      padding: 10, marginTop: 4, borderRadius: 8, border: '1px solid var(--border-1)',
    }}>
      {error && <span className="text-[12.5px]" style={{ color: 'var(--danger)' }}>{error}</span>}
      {!info && !error && (
        <span className="flex items-center gap-1.5 text-[12.5px]" style={{ color: 'var(--fg-4)' }}>
          <Loader2 size={13} className="animate-spin" /> Einzahlungsschein wird erzeugt …
        </span>
      )}
      {info && (
        <div className="flex items-start gap-4 flex-wrap">
          <div className="flex flex-col gap-2" style={{ flex: '1 1 200px', minWidth: 0 }}>
            <Fixed label="Empfänger" value={info.creditor} />
            {info.iban && <Fixed label="IBAN" value={info.iban} />}
            {/* ►►► **Woher die Referenz kommt, steht dran** (Testnotiz #871). ◄◄◄
                *«Leitet sich diese von der Rechnungsnummer ab oder nicht?»* – Ja, und
                genau das war die Auskunft, die fehlte: der Hinweis nannte die Norm und
                nicht die **Herkunft**, und die Rechnungsnummer stand in diesem Feld gar
                nicht (der Trennstrich fällt weg, weil ISO 11649 nur Buchstaben und
                Ziffern kennt – aus «100000886-1» wird «…1000008861», und ohne den Satz
                sieht das nach einer erfundenen Zahl aus). */}
            <Fixed label="Referenz" value={info.reference}
              hint={`Creditor Reference (ISO 11649) aus der Rechnungsnummer ${info.invoice}`
                + ' – ohne Trennstrich, mit zwei Prüfziffern. So kommt die Zahlung mit '
                + 'unserem Beleg zurück, ohne dass jemand etwas abtippt.'} />
            <Fixed label="Betrag" value={`${info.amount} ${info.currency}`} />
          </div>
          {/* **Das Bild kommt fertig vom Server.** Es trägt keine Angabe aus einer
              Eingabe – nur die Module des Codes –, und es hier zusammenzusetzen hiesse,
              die einunddreissig Zeilen ein zweites Mal zu pflegen. */}
          {info.qr && (
            <div style={{ flex: 'none', width: 168 }}
              dangerouslySetInnerHTML={{ __html: info.qr }} />
          )}
          {info.problem && (
            <span className="text-[12px]" style={{ color: 'var(--fg-3)', flex: '1 1 180px' }}>
              {info.problem}
            </span>
          )}
        </div>
      )}
      {/* ►►► **Kein «Schliessen»-Knopf** (Testnotiz #889). ◄◄◄ Der Knopf, der die
          Auskunft geöffnet hat, schliesst sie auch – er ist ein Schalter (`onTransfer`
          setzt um). Ein zweiter Weg zum selben Ziel, drei Zentimeter tiefer, ist genau
          die Doppelung, die das Haus sonst überall wegnimmt. */}
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
function Entry({ kind, d, busy, preset, chargeId, onCancel, onSubmit }: {
  kind: 'charge' | 'payment'; d: Filled; busy?: boolean;
  /** Ein vorbelegter Betrag – die **Korrektur** einer Zahlung (#842). */
  preset?: string;
  /**
   * ►►► **Auf welche Rechnung diese Zahlung geht** (Testnotizen #858/#859). ◄◄◄
   *
   * Hier stand ein **Auswahlfeld** über den offenen Rechnungen. Es ist entfallen, und
   * zwar zweimal begründet: seit #866 lebt je Modul höchstens eine, und seit #859 steht
   * der Knopf **an ihrer Zeile** – die Frage ist beantwortet, bevor das Formular aufgeht.
   *
   * `undefined` heisst «keine genannt»; dann ordnet der Dienst zu, was zuzuordnen ist.
   */
  chargeId?: number;
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
  // ►►► **WIE bezahlt wurde — bar oder per Überweisung** (Testnotiz #865). ◄◄◄
  //
  // *«Im Grunde gibt es 3 Arten von Bezahlsystemen: Barzahlung, Zahlung per Karte und
  // Zahlung via Banküberweisung.»* – Und sie sind **eine Angabe an der Zahlung**, kein
  // zweites Modell: gebucht wird in jedem Fall dieselbe Zeile.
  //
  // **Die Karte steht nicht zur Wahl**: sie entsteht beim Zahlungsdienst und kommt über
  // den Webhook. Von Hand erfasst wäre sie eine Behauptung ohne Beleg – der Dienst weist
  // sie ab (`dm.assert_method`), und die Liste hier bietet sie gar nicht erst an.
  //
  // **Zwei Werte sind ein Schieber**, keine Auswahlliste – dieselbe Regel wie bei der
  // Richtung im Editor (#782).
  const methods = kind === 'payment' ? (d.methods ?? []) : [];
  const [method, setMethod] = useState(methods[0]?.key ?? '');
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
        {/* ►►► **Das Leistungsdatum ist längst AUTOMATISCH** (Testnotiz #886). ◄◄◄
            *«Muss ich das wirklich hier angeben? Ich verstehe es nicht – gibt es nicht
            etwas, um es zu automatisieren? Brauche ich es überhaupt?»*

            Der Reihe nach, und die Antwort steht jetzt im Hover statt in keinem Satz:
            **Brauchen ja** – auf einer Schweizer Rechnung ist das Datum der Leistung eine
            Pflichtangabe (MWSTG Art. 26 Bst. c), und es ist **nicht** das Rechnungsdatum:
            eine zwei Wochen später geschriebene Rechnung verschöbe sonst die Steuerperiode.
            **Angeben nein** – es steht schon da: der Server leitet es aus dem Prozess ab
            (der Tag, an dem die Stücke dieses Modul erreicht haben) und füllt das Feld.

            Es bleibt trotzdem ein Feld und nicht eine Lese-Anzeige, weil ein Mensch von
            Teilleistungen weiss, von denen der Log nichts weiss – **vorbelegt, nicht
            erzwungen**. Leer heisst «wie gebucht»; das gilt, solange an diesem Modul noch
            nichts angekommen ist. */}
        {taxed && (
          <div>
            <Label>{d.service_date_label}</Label>
            <input type="date" className={inputCls} value={service}
              aria-label={d.service_date_label}
              data-tip={'Wann die Leistung erbracht wurde – Pflichtangabe auf der Rechnung '
                + '(MWSTG Art. 26). Vorbelegt aus dem Prozess: der Tag, an dem die Stücke '
                + 'dieses Modul erreicht haben. Ändern nur bei einer Teilleistung.'}
              onChange={(e) => setService(e.target.value)} />
          </div>
        )}
        {/* **Wie bezahlt wurde** (#865) – zwei Werte, also ein Schieber. */}
        {methods.length > 0 && (
          <Segmented label={d.method_label} value={method} onChange={setMethod}
            options={methods.map((m) => ({ value: m.key, label: m.label }))} />
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
      {/* ►►► **«Buchen» sagt nicht, was gebucht wird** (Testnotiz #887). ◄◄◄
          *«Kann man hier so einen Button machen wie bei der Auswahl der Module … und
          zudem finde ich den Button «Buchen» nicht wirklich gut.»* – Beides stimmt, und
          das zweite war eine erfundene Vokabel: der Server nennt die Handlung längst
          («Rechnung erfassen» ↔ «Zahlung erfassen»), und genau dieses Wort steht auch auf
          dem Knopf, der dieses Formular geöffnet hat. Zwei Wörter für eine Handlung sind
          die Stelle, an der man sich fragt, ob es zwei sind.
          Und zurück geht es mit demselben Zeichen, mit dem das Haus überall zurückgeht. */}
      <Actions>
        <ActionButton icon={Check} tone="primary" height={ACT_H.inline}
          label={kind === 'charge' ? d.charge_word : d.payment_word}
          disabled={busy || amount.trim() === ''}
          onClick={() => onSubmit({
            action: kind === 'charge' ? 'charge' : 'pay', amount, reference: ref,
            // **Worauf sie geht** – der Knopf stand an der Rechnung, also nennt sie die
            // Karte. Der Dienst leitete sie zwar selbst ab; was gebucht wird, soll aber
            // die Stelle gesagt haben, an der jemand geklickt hat.
            ...(chargeId != null ? { charge_id: chargeId } : {}),
            ...(method ? { method } : {}),
            ...(taxed ? {
              ...(d.we_quote ? {} : { vat }),
              ...(service ? { service_date: service } : {}),
            } : {}),
          })} />
        <ActionButton icon={X} label="Abbrechen" height={ACT_H.inline}
          onClick={onCancel} />
      </Actions>
    </div>
  );
}
