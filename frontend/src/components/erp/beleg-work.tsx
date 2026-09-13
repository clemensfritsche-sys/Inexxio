'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import {
  AlertTriangle, Check, ChevronDown, CircleSlash, ClipboardList,
  CreditCard, FileText, Loader2, Plus, RotateCcw, Send, Undo2,
  Wallet, X,
} from 'lucide-react';
import { api } from '@/lib/api';
import type {
  TransferInfo, VoucherEmbed, VoucherParty, VoucherQuoteOut, VoucherSide,
} from '@/types';
import { ObjId } from '@/components/erp/obj-id';
import { ObjectSelect } from '@/components/erp/object-select';
import { PayOnline } from '@/components/erp/pay-online';
import {
  Label, MICRO_LABEL, Segmented, inputCls, numericInputProps, numericOnly,
} from '@/components/erp/fields';
import {
  ACT_H, ActionButton, ConfirmButton, FIELD_GAP, ModuleSection, Row, RowActions,
} from '@/components/erp/module-ui';
import { DEAL_STAGE, QUOTE_STATE } from '@/lib/modules';
import { TONE } from '@/lib/status-flow';
import { useAutosave } from '@/lib/use-autosave';
import { formatAmount } from '@/lib/utils';
import { day, formatWhen, when } from '@/lib/when';

/**
 * ►►► **Der Beleg an der Ausführungsstelle — EIN Dokument, das WÄCHST.** ◄◄◄
 *
 * Der Neuaufbau des Zahlungsmoduls (`docs/neuaufbau-zahlungsmodul.md`). Der Vorgänger
 * (`deal-work.tsx`) entstand als Modulkarte und wurde über mehrere Runden zu einem Beleg
 * umgeformt; hier ist er von der ersten Zeile an einer:
 *
 *     Belegkopf → Positionen → Konditionen → Rückläufe → Rechnung & Zahlung → Chronik
 *
 * Das ist die Ordnung, die ein Beleg seit Jahrhunderten hat. Und er **wächst**, statt
 * umzuschalten: mit der Zusage heisst der Kopf «Auftragsbestätigung» statt «Offerte» und
 * nennt den Empfänger, die Preisspalte trägt die gebuchten Zahlen statt des Entwurfs, die
 * Konditionen stehen als Auskunft statt als Feld, die Rückläufe klappen auf eine Zeile
 * zusammen, und darunter kommt das Geld dazu. **Dieselben Zeilen, ein Zustand weiter** –
 * ein späterer PDF-Export ist damit dieselbe Komponente ohne Knöpfe.
 *
 * ## Kein einziges `if` auf die Richtung
 *
 * Was Einnahme von Ausgabe unterscheidet, **reist fertig mit** (`label`,
 * `stages[].label/verb`, `party_word`, `ask_verb`, `we_quote`, `ref_label`). Diese Datei
 * kennt weder «Kunde» noch «Lieferant»; sie fragt `may(...)` und zeichnet.
 *
 * ## Was man ändern kann, sieht man (Testnotiz #922)
 *
 * *«Es soll so ausschauen wie der finale Beleg, nur eben gehighlighted, damit man sieht:
 * ah, dieser Wert kann angepasst werden. ACHTUNG: Ich will das auch für alle anderen
 * Angaben auf dem Beleg.»*
 *
 * Also **eine** Auszeichnung (`.ix-editable` in `globals.css`), und jeder änderbare Wert
 * trägt sie: Währung · Zahlungsfrist · Lieferfrist · Lieferbedingung · Preis · MWST ·
 * Zolltarifnummer · Ursprungsland · Gegenpartei. Eine Haarlinie in der leisen Stimme des
 * Hauses, ohne Layoutwirkung – keine andere Grösse, Form oder Schrift.
 *
 * ## Die Handlung, die weiterbringt, sieht überall gleich aus (Testnotiz #923)
 *
 * *«Kann dieser Button so gross und ausdrucksstark werden wie ‹Vorgang abschliessen› am
 * Schluss? Eine UI-Logik.»* – Genau: `StageAction` ist **ein** Bauteil für «Anbieten /
 * Anfragen», «Angebot annehmen» und den Modul-Abschluss. Volle Breite, Fläche, 42 px –
 * dieselben Masse wie der Knopf, der jedes Modul beendet (`order-detail`).
 *
 * ## Und drei Dinge stehen nicht mehr da
 *
 * Die **Vorauszahlungs-Pille** im Kopf (#924/#925): ob vorausbezahlt wird, sagt die
 * **Zahlungsfrist** in den Konditionen – eine Zeile tiefer, wo man sie ändert. Die
 * Überschrift **«Konditionen»** (#926): die drei Zeilen darunter sagen selbst, was sie
 * sind. Und die **Währung** steht bei den Beträgen (#921), nicht in einem eigenen Feld.
 */
type Filled = Omit<VoucherEmbed,
  'stages' | 'entries' | 'allowed' | 'can' | 'quotes' | 'lines'> & {
  stages: NonNullable<VoucherEmbed['stages']>;
  entries: NonNullable<VoucherEmbed['entries']>;
  allowed: NonNullable<VoucherEmbed['allowed']>;
  can: NonNullable<VoucherEmbed['can']>;
  quotes: NonNullable<VoucherEmbed['quotes']>;
  lines: NonNullable<VoucherEmbed['lines']>;
};

type Action = { action: string } & Record<string, unknown>;
type Send = (body: Action) => Promise<unknown> | void;

/**
 * ►►► **Anfragen bzw. anbieten — EIN Payload, zwei Aufrufer** (Testnotiz #941). ◄◄◄
 *
 * *«Ist die Funktion dieses Buttons wirklich aktiv? Funktioniert die Logik dahinter?»* –
 * Nein, und der Grund war eine **zweite Nutzlast**: der Knopf im Belegkopf schickte
 * `ask` **ohne** die beiden Fristen, und der Dienst weist ein Angebot ohne sie zu Recht
 * ab (aus ihnen kommen Fälligkeit und Termin). Der Knopf am Angebot schickte sie mit,
 * also tat derselbe Befehl je nach Herkunft etwas anderes.
 *
 * Gebaut wird die Nutzlast jetzt **an einer Stelle** (in `BelegWork`, wo der Entwurf der
 * Fristen ohnehin wohnt); wer fragt, sagt nur noch **wen**.
 */
type Ask = (parties?: number[]) => void;

/**
 * **Darf man das hier tun?** – die eine Frage, und sie geht an den Server.
 *
 * `can` ist Auskunft **und** Tor (`services/voucher`): dieselbe Liste rendert die Knöpfe
 * und weist ab. Eine zweite Bedingung in dieser Datei wäre ein zweiter Massstab – und der
 * bekäme die nächste Regel nicht mit.
 *
 * **Das aktive Modul ist nicht die Bedingung.** Ein Zahlungsziel läuft weiter, wenn die
 * Ware längst draussen ist; die Geld-Zeilen hängen darum allein an `can` (#821). Die
 * beiden **Stufen** fragen zusätzlich nach `active` – dort ist es richtig.
 */
function may(d: Filled, action: string): boolean {
  return d.can.includes(action);
}

/** Das Vorzeichen drehen – die Vorbelegung einer Korrektur bzw. Erstattung. */
function negate(amount: string): string {
  const clean = amount.trim();
  return clean.startsWith('-') ? clean.slice(1) : `-${clean}`;
}

/** Wie viele Tage von heute bis zu diesem Datum? Negativ heisst: vorbei. */

export function BelegWork({
  voucher, busy, active, orderObjectId, stepId, onAction, onPaid, children,
}: {
  voucher: VoucherEmbed;
  busy: boolean;
  /** Ist dieses Modul an der Reihe? Nur die **Stufen** fragen danach – Geld nie (#821). */
  active: boolean;
  orderObjectId: number;
  stepId: number;
  onAction: Send;
  /** Der Auftrag soll neu geladen werden – eine Karten-Zahlung kommt über den Webhook. */
  onPaid: () => void;
  /** Der Inhalt des Moduls selbst (der Abschluss) – **am Ende der Karte** (#829). */
  children?: ReactNode;
}) {
  const d = voucher as Filled;
  const agreed = d.stage !== DEAL_STAGE.offer;
  // ►►► **Es gibt keinen Entwurf im Browser mehr** (Testnotiz #985). ◄◄◄ Hier stand der
  // gehobene Zustand der beiden Fristen: sie reisten allein in der Nutzlast von `ask` mit,
  // also verwarf ein Reload sie. Sie werden jetzt sofort geschrieben wie jeder andere
  // änderbare Wert des Belegs (Verb `terms`) – `ask` liest sie vom Beleg, und die Aufrufer
  // sagen nur noch, **wen** sie fragen (#941: der eine Payload-Bauer).
  const onAsk = useCallback<Ask>((parties) => {
    void onAction({
      action: 'ask',
      ...(parties && parties.length ? { parties } : {}),
    });
  }, [onAction]);

  return (
    <div className="flex flex-col" style={{ minWidth: 0 }}>
      <DocHead d={d} busy={busy} onAction={onAction} onAsk={onAsk} />
      <Goods d={d} busy={busy} onAction={onAction} />
      <Terms d={d} busy={busy} onAction={onAction} />
      <Quotes d={d} busy={busy} active={active} onAsk={onAsk} onAction={onAction} />
      {agreed && (
        <Money d={d} busy={busy} orderObjectId={orderObjectId} stepId={stepId}
          onAction={onAction} onPaid={onPaid} />
      )}
      {/* ►►► **Der Modul-Abschluss steht am ENDE** (Testnotiz #829) – und der Storno
          daneben (#957). ◄◄◄ */}
      <Footer d={d} busy={busy} onAction={onAction}>{children}</Footer>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// ►►► DIE BAUSTEINE DES BELEGS
// ═══════════════════════════════════════════════════════════════════════════════

/**
 * ►►► **Ein Wert, den man ändern kann** (Testnotiz #922). ◄◄◄
 *
 * Die eine Hülle – sie setzt nur die Klasse und sagt, wann sie **nicht** gilt. Dass die
 * Auszeichnung so aussieht, wie sie aussieht, steht in `globals.css`; hier steht, **wo**
 * sie gilt, und das ist die ganze Regel: jeder änderbare Wert auf dem Beleg.
 *
 * `as` ist die Form, die der Aufrufer ohnehin braucht – ein `<span>` mitten in einer
 * Zeile, ein `<div>` um ein Feld. Ein zweites Bauteil dafür wäre dieselbe Regel ein
 * zweites Mal.
 *
 * ►►► **Die Auszeichnung ist deckungsgleich mit dem Bedienelement** (Testnotiz #948). ◄◄◄
 *
 * *«Das gehighlightete Feld ist deutlich grösser als das selektierbare Feld. Das ist ein
 * design- und UX-technisches No-Go. Bitte eine robuste Lösung etablieren und bei allen
 * Eingabefeldern kontrollieren.»*
 *
 * Die Ursache war der **Display-Typ**: als reines Inline-Element nahm die Hülle die Höhe
 * der **Zeile** (Schriftgrösse × Zeilenhöhe), während das Bedienelement darin seine eigene,
 * kleinere Box hatte. Sichtbar getönt war also mehr, als man treffen konnte.
 *
 * `inline-flex` löst es **konstruktiv** statt durch abgestimmte Zahlen: die Hülle nimmt
 * genau die Höhe ihres Kindes, und das Kind streckt sich auf ihre – es gibt danach nur
 * **eine** Box. Eine Messung, die zwei Zahlen vergleicht, könnte ein Auseinanderlaufen nur
 * melden; so kann es nicht entstehen.
 */
function Editable({ on = true, as: Tag = 'span', style, title, missing, children }: {
  on?: boolean;
  as?: 'span' | 'div';
  style?: CSSProperties;
  title?: string;
  /**
   * ►►► **Ein Pflichtwert, der fehlt, sagt es an SEINER Stelle** (Testnotiz #964). ◄◄◄
   *
   * *«Alle Eingabefelder hier in diesem Modul – also alles, was so leicht blau hinterlegt
   * ist – sollen Muss-Felder sein.»* Und «leicht blau hinterlegt» ist genau diese Hülle:
   * die Regel gehört darum ihr und nicht neun Aufrufstellen.
   *
   * Es ist **dieselbe Auszeichnung in einer anderen Stimme** – kein Sternchen, kein
   * Ausrufezeichen, keine zweite Form: die Fläche wird warnfarben statt akzentfarben,
   * Grösse und Schrift bleiben, wie #922/#948 sie festgelegt haben. Ein Beleg sieht aus
   * wie ein Beleg, nur sagt er, wo er noch nicht fertig ist.
   *
   * **Die Regel selbst steht im Dienst** (`voucher._assert_complete`): dies ist ihre
   * freundliche Hälfte, kein zweiter Massstab – wer den Beleg trotzdem hinausschickt,
   * bekommt einen Satz, der die Position nennt.
   */
  missing?: boolean;
  children: ReactNode;
}) {
  // **Und sie darf sich nicht strecken** – das war die gemessene Ursache: in einer
  // Spalte (`flex-col`) wird jedes Kind **blockifiziert** und auf die volle Breite
  // gezogen; die getönte Fläche war damit 229 px breit, das `<select>` darin 44 px
  // (gemessen, genau der gemeldete Unterschied).
  //
  // ►►► **Die Streckung nimmt `width: fit-content` zurück, nicht `align-self`**
  // (Testnotizen #961/#963). ◄◄◄
  //
  // *«Hier ist so ein komischer Höhenversatz zwischen Objektname und Nummer»* · *«auch
  // hier ist so ein leichter Höhenversatz zwischen den Werten»* – **eine** Ursache, zwei
  // Meldungen. `align-self: start` stand hier und beantwortet die Streckung richtig, aber
  // es beantwortet zugleich eine **zweite** Frage, die es nicht beantworten darf: in
  // einer **Zeile** ist die Querachse die senkrechte, und `start` heisst dort «oben
  // ausgerichtet» – die Hülle fiel damit aus dem `items-baseline` bzw. `items-center`
  // ihres Elternteils heraus, und neben einer Angabe anderer Schriftgrösse stand sie
  // sichtbar versetzt.
  //
  // `fit-content` löst genau das eine Problem: eine **definite** Quergrösse schliesst
  // `align-self: stretch` aus (CSS Flexbox §8.3), also streckt sich in der Spalte nichts
  // mehr – und in der Zeile bleibt die senkrechte Ausrichtung die des Elternteils. Die
  // Hülle muss ihren Kontext weiterhin nicht kennen.
  const box: CSSProperties = Tag === 'span'
    ? { display: 'inline-flex', width: 'fit-content', maxWidth: '100%', ...style }
    // **Auch der Block-Fall ist ein Flex-Kasten** – sonst ist die Hülle so hoch wie ihre
    // Zeile (24 px) und das Feld darin 19,5 px; gemessen am Betragsfeld der Angebotszeile.
    : { display: 'flex', ...style };
  return (
    <Tag className={on ? `ix-editable${missing ? ' is-missing' : ''}` : undefined}
      style={box}
      {...(on ? {} : { 'aria-disabled': true as const })}
      {...(on && missing ? { 'aria-invalid': true as const } : {})}
      {...(title ? { 'data-tip': missing ? `${title} – Pflichtangabe` : title } : {})}>
      {children}
    </Tag>
  );
}

/**
 * ►►► **Die Handlung, die den Beleg eine Stufe weiterbringt** (Testnotiz #923). ◄◄◄
 *
 * *«Kann dieser Button so gross und ausdrucksstark werden wie ‹Vorgang abschliessen› am
 * Schluss? Eine UI-Logik.»*
 *
 * Ja – und es ist buchstäblich dieselbe Form: volle Breite, Fläche, 42 px, 14 px Schrift.
 * Sie steht **einmal** hier und gilt für «Anbieten / Anfragen» wie für «Angebot annehmen»;
 * der Modul-Abschluss selbst trägt sie in `order-detail`, wo er entsteht.
 *
 * Ein Knopf, der den Beleg weiterbringt, sieht überall gleich aus – das ist die verlangte
 * UI-Logik und kein Sonderfall für eine Zeile.
 */
function StageAction({ icon: Icon, label, disabled, tip, onClick }: {
  icon: typeof Check;
  label: string;
  disabled?: boolean;
  tip?: string;
  onClick: () => void;
}) {
  return (
    <button type="button" className="erp-actbtn erp-actbtn-primary w-full"
      disabled={disabled} style={{ height: ACT_H.stage, fontSize: 14 }}
      {...(tip ? { 'data-tip': tip } : {})} onClick={onClick}>
      <Icon size={16} /> {label}
    </button>
  );
}

/**
 * ►►► **Die dominante Handlung, und daneben die leise** (Testnotiz #976). ◄◄◄
 *
 * *«Kann man diesen Bereich ähnlich darstellen wie ‹Vorgang abschliessen› und daneben das
 * unscheinbarere Abbrechen?»*
 *
 * Das ist keine Eigenschaft einer Zeile, sondern die **Anatomie einer Entscheidung** auf
 * diesem Beleg: eine Handlung bringt ihn weiter und nimmt den Platz, alles andere steht
 * als Quadrat daneben und klappt beim Zeigen seinen Namen aus. Sie steht darum **einmal**
 * – die Fusszeile der Karte (Abschluss ↔ Storno) und der Zuschlag an einer Angebotszeile
 * (annehmen ↔ absagen) sind dieselbe Zeile.
 */
function StageRow({ children, aside }: { children?: ReactNode; aside?: ReactNode }) {
  return (
    <div className="flex items-stretch" style={{ gap: 8, minWidth: 0 }}>
      {children && <div style={{ flex: 1, minWidth: 0 }}>{children}</div>}
      {aside}
    </div>
  );
}

/** Was man an einer Angebotszeile tut, wenn man den Preis nennt – in beiden Richtungen. */
const QUOTE_VERB = 'Offerte erfassen';

/**
 * ►►► **Ein Feld auf dem Beleg sieht aus wie der Beleg** (Testnotiz #922). ◄◄◄
 *
 * *«So dass es eigentlich ausschaut wie der final definierte Beleg, nur eben
 * gehighlighted.»* – Ein gerahmter Eingabekasten tut das **nicht**: er ist die Form eines
 * Formulars, und ein Beleg ist kein Formular. Die Eingaben auf der Karte tragen darum
 * keinen Rahmen und keine Fläche; was sie von einer gedruckten Zeile unterscheidet, ist
 * allein die Haarlinie aus `.ix-editable`.
 *
 * `inputCls` bleibt richtig, wo man wirklich ein **Formular** ausfüllt – im Editor und in
 * der Erfassungsmaske einer Geld-Zeile.
 */
const DOC_FIELD: CSSProperties = {
  background: 'transparent', border: 0, outline: 'none', padding: 0,
  font: 'inherit', color: 'inherit',
};

/**
 * ►►► **Der gedruckte Wert IST das Bedienelement** (Testnotizen #929/#930/#934/#935). ◄◄◄
 *
 * Dreimal derselbe Satz: *«Ich möchte die gleiche Logik, das gleiche Design wie bei der
 * Währung, sodass es aussieht wie ein richtiger Beleg und eben gewisse Variablen
 * veränderbar sind.»* – Also ist es keine Eigenschaft der Währung, sondern die **Form
 * eines änderbaren Werts im Beleg**, und sie steht einmal.
 *
 * Sichtbar ist ein `<span>` in der Schrift, die dort ohnehin steht; bedienbar ein
 * **unsichtbares** `<select>` darüber. Das ist nicht nur Kosmetik – es löst zugleich das
 * gemeldete Breiten-Problem (#935): ein natives Auswahlfeld nimmt die Breite seiner
 * **längsten Zeile** («DPU · Geliefert entladen»), und daneben sass der Pfeil dann
 * scheinbar eingerückt. Hier bestimmt die **Anzeige** die Breite, und das Bedienelement
 * legt sich exakt darüber.
 *
 * Steht der Wert fest, bleibt der Text – ohne Auszeichnung. Eine Linie, die
 * Änderbarkeit verspricht, wäre dort eine Unwahrheit.
 *
 * ►►► **Und ein Wähler ist mindestens so breit, dass man ihn trifft** (#942). ◄◄◄
 *
 * *«Bei Zahlungsfrist, Lieferfrist, Lieferbedingung kann ich nichts eingeben oder
 * auswählen.»* – Gemessen: die Trefferfläche war **13 × 24 px**, nämlich die Breite des
 * gedruckten «—». Das ist die Kehrseite der Regel «der gedruckte Wert IST das
 * Bedienelement»: wo noch nichts dasteht, steht auch kein Bedienelement. `MIN_PICK` ist
 * darum eine **Untergrenze**, keine Breite – ein gesetzter Wert bestimmt sie weiterhin
 * selbst –, und sie gilt für die Haarlinie **und** die Fläche: was man anklicken kann,
 * muss man auch sehen.
 */
const MIN_PICK = 44;

function DocPick({ on, value, text, options, face, tip, busy, aria, missing, onChange }: {
  on: boolean;
  value: string;
  /** Was dasteht – der **kurze** Name, nie die Zeile des Auswahlfelds. */
  text: string;
  options: { value: string; label: string }[];
  face?: CSSProperties;
  tip?: string;
  busy?: boolean;
  aria: string;
  /** Pflichtangabe und noch leer (#964) – siehe `Editable.missing`. */
  missing?: boolean;
  onChange: (value: string) => void;
}) {
  const shown = <span aria-hidden style={face}>{text}</span>;
  if (!on) return shown;
  // ►►► **EINE Box** (#948): Auszeichnung und Bedienelement sitzen auf demselben Element –
  // der frühere Zwischen-`<span>` war die zweite, und sie konnte grösser sein als das
  // `<select>`, das sie versprach. `inset: 0` deckt jetzt exakt die getönte Fläche.
  return (
    <Editable title={tip} missing={missing}
      style={{ position: 'relative', minWidth: MIN_PICK, maxWidth: '100%' }}>
      {shown}
      <select value={value} disabled={busy} aria-label={aria}
        onChange={(e) => onChange(e.target.value)}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%',
                 opacity: 0, cursor: 'pointer' }}>
        {options.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </Editable>
  );
}

/**
 * ►►► **Ein Datensatz auf dem Beleg — dieselbe Form, nur mit Suche** (#928/#929/#930). ◄◄◄
 *
 * Ein `<select>` geht hier nicht: ein Partner ist eine **Referenz**, keine Aufzählung
 * (`ObjectSelect` ist die eine Bauart dafür). Die Regel bleibt trotzdem dieselbe – im
 * Ruhezustand steht der **Name** da, so wie er gedruckt würde, mit der Auszeichnung aus
 * #922; der Klick macht daraus die Suche.
 *
 * Damit ist der frühere Stift-Knopf am Aussteller entfallen (#929): *«Statt diesem Button
 * kann nicht der darunter befindliche Unternehmensname als veränderbare Variable
 * deklariert werden?»* – Doch, und es ist dieselbe Form wie überall sonst.
 */
function DocRef<T extends { object_id: number; name: string }>({
  on, text, placeholder, value, selected, find, face, tip, onChange,
}: {
  on: boolean;
  text: ReactNode;
  placeholder: string;
  value: number | null;
  selected?: T | null;
  find: (query: string) => Promise<T[]>;
  face?: CSSProperties;
  tip?: string;
  onChange: (objectId: number | null, option: T | null) => void;
}) {
  const [open, setOpen] = useState(false);
  // **Wer klickt, will tippen.** Ohne den Sprung in das Feld kostet die Wahl zwei Klicks –
  // der erste öffnet nur, und das sieht aus wie ein Aussetzer.
  const focus = useCallback((node: HTMLDivElement | null) => {
    node?.querySelector('input')?.focus();
  }, []);

  if (!on) return <span style={face}>{text}</span>;
  if (!open) {
    return (
      <Editable title={tip}>
        <button type="button" onClick={() => setOpen(true)}
          style={{ ...DOC_FIELD, ...face, cursor: 'pointer', textAlign: 'left',
                   maxWidth: '100%' }}>
          {text}
        </button>
      </Editable>
    );
  }
  return (
    <div ref={focus} style={{ minWidth: 0 }}>
      <Editable as="div" style={{ minWidth: 170 }}>
        <ObjectSelect<T>
          value={value} selected={selected} placeholder={placeholder} find={find}
          onChange={(n, option) => { setOpen(false); onChange(n, option); }}
        />
      </Editable>
    </div>
  );
}

/** Eine Pflichtangabe, die fehlt – klein, rot, an ihrer Stelle. Erfunden wird nichts. */
function Missing({ what }: { what: string }) {
  return (
    <span style={{ ...MICRO_LABEL, color: 'var(--danger)' }}>{what} fehlt</span>
  );
}

/**
 * ►►► **Eine leise Auskunft — und ihre Blase steht DARÜBER** (Testnotiz #978). ◄◄◄
 *
 * *«Den Hovertext direkt darüber und nicht wie jetzt irgendwo.»*
 *
 * Die Blase des Hauses sitzt über der **Mitte ihres Elements** (`[data-tip]::after`,
 * `left: 50%`). Das ist richtig – nur war das Element nicht die Auskunft, sondern die
 * ganze Zeile: ein Kind einer Flex-**Spalte** wird blockifiziert und auf die volle Breite
 * gezogen, und bei 460 px stand die Blase einen halben Beleg neben den drei Wörtern, die
 * sie erklärt.
 *
 * `width: fit-content` ist die Antwort und nicht `align-self` – dieselbe Lehre wie bei
 * `Editable` (#961/#963): eine **definite** Quergrösse wirkt in der Spalte *und* in der
 * Zeile, `align-self: start` beantwortet in der Zeile die falsche Frage.
 *
 * Sie steht als **Bauteil** da, weil es drei Aufrufstellen sind (wann offeriert, wann
 * angenommen, wie bestellt) – dreimal dieselben vier Werte wären dreimal die Chance, dass
 * einer abweicht.
 */
function Note({ tip, icon: Icon, children }: {
  tip?: string | null; icon?: typeof ClipboardList; children: ReactNode;
}) {
  return (
    <span className="inline-flex items-center"
      style={{ gap: 6, fontSize: 11.5, color: 'var(--fg-3)', width: 'fit-content',
               flex: 'none', minWidth: 0 }}
      {...(tip ? { 'data-tip': tip } : {})}>
      {Icon && <Icon size={11} style={{ flex: 'none' }} />}
      {children}
    </span>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Der Belegkopf
// ───────────────────────────────────────────────────────────────────────────────

/**
 * Wie viele Zeilen ein Partei-Block hat – siehe `Party`.
 *
 * ►►► **Sechs statt sieben** (Testnotiz #940): die Objektnummer steht **neben** dem Namen,
 * nicht vier Zeilen darunter. Das ist die Form, in der dieses Haus einen Datensatz nennt
 * (#933) – und damit braucht sie auch keine eigene Beschriftung «Nr.» mehr.
 *
 * ►►► **Und eine siebte für die zweite Anschrift** (Testnotiz #952). ◄◄◄ Rechnungs- und
 * Lieferadresse müssen nicht gleich sein. Die Zeile steht auf **beiden** Seiten, auch wo
 * sie leer bleibt: die Symmetrie ist die Aussage, nicht die Dichte (#913).
 *
 * ►►► **Und eine achte ÜBER der Rolle – die Auswahl** (Testnotiz #981). ◄◄◄ *«Gefühlt
 * sollte die Auswahloptionen oberhalb vom Headline Leistungsempfänger stehen und dann je
 * nachdem was angewählt wurde unterhalb der Headline die Angaben geladen werden.»*
 *
 * Sie stand bis hierher **in** der Namenszeile, also *unter* der Rolle und an der Stelle,
 * an der sonst der Name steht: die Chips ersetzten die Angabe, die sie auswählen. Über
 * der Rolle ist es die Reihenfolge des Lesens – erst *wen meine ich*, dann *was gilt für
 * ihn*. Auf unserer Seite bleibt die Zeile leer; die Symmetrie ist dieselbe Regel wie bei
 * jeder anderen (#913).
 */
const PARTY_ROWS = 8;

/**
 * **Der Belegkopf** – beide Parteien, und sonst nichts.
 *
 * ►►► **Die Belegart steht hier NICHT** (Testnotizen #974/#977). ◄◄◄ *«Ich habe eigentlich
 * gesagt, dass dies nicht angezeigt werden soll hier oben.»* – Und das stimmt: #974 hiess
 * «diese Anzeige verschwindet», und aus «Erledigt» die **Belegart** zu machen war eine
 * Auslegung, keine Umsetzung. Sie sagt hier auch nichts, was die Karte nicht schon sagt:
 * wie weit der Beleg ist, steht als Punkt an **jedem** Abschnitt (`ModuleSection state`),
 * und was als Nächstes zu tun ist, steht auf dem Knopf, der es tut.
 *
 * **Der Storno bleibt** – er ist keine Belegart, sondern eine **Tatsache** über dieses
 * Papier, und er steht sonst nirgends (bis #970 stand er in der Chronik).
 *
 * Ebenfalls entfallen: der **offene Betrag** (#902 – auf einer Offerte ist nichts
 * gefordert, und «Offen 0.00» liest sich wie «bezahlt»; er steht an der Rechnung) und die
 * **Vorauszahlungs-Pille** (#924/#925 – das sagt die Zahlungsfrist, wo man sie ändert).
 */
function DocHead({ d, busy, onAction, onAsk }: {
  d: Filled; busy: boolean; onAction: Send; onAsk: Ask;
}) {
  return (
    <ModuleSection first>
      <div className="flex flex-col" style={{ gap: 14, minWidth: 0 }}>
        {d.cancelled_on && (
          <span style={{ ...MICRO_LABEL, color: 'var(--danger)', width: 'fit-content' }}
            data-tip={formatWhen(d.cancelled_on).title}>
            storniert · {when(d.cancelled_on)}
          </span>
        )}
        <Parties d={d} busy={busy} onAction={onAction} onAsk={onAsk} />
        <Gaps rows={d.gaps ?? []} />
      </div>
    </ModuleSection>
  );
}

/**
 * ►►► **Beide Parteien auf EINEM Raster** (Testnotiz #913). ◄◄◄
 *
 * Vorher floss jede Seite für sich untereinander: hatte die eine kein «z. H.», rutschte
 * bei ihr alles eine Zeile hoch, und die Anschrift der einen stand neben der Nummer der
 * anderen. Sie teilen jetzt **ein** Raster mit einer festen Zeile je Angabe (`subgrid`) –
 * fehlt eine, bleibt die Zeile **leer**: die Symmetrie ist die Aussage, nicht die Dichte.
 */
function Parties({ d, busy, onAction, onAsk }: {
  d: Filled; busy: boolean; onAction: Send; onAsk: Ask;
}) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 200px), 1fr))',
      gridTemplateRows: `repeat(${PARTY_ROWS}, auto)`,
      gap: '14px 24px', minWidth: 0,
    }}>
      <Party side={d.supplier} d={d} busy={busy} onAction={onAction} onAsk={onAsk} />
      <Party side={d.customer} d={d} busy={busy} onAction={onAction} onAsk={onAsk} />
    </div>
  );
}

/**
 * **Eine Seite des Belegkopfs.** Jede Angabe belegt **ihre** Zeile im gemeinsamen Raster –
 * darum steht überall ein `<div />` statt `null`, wo nichts dasteht.
 *
 * ►►► **Die Gegenpartei wählt man dort, wo sie steht** (Testnotiz #912). ◄◄◄ *Ändern, wo
 * man liest*: der Leistungsempfänger **ist** das Bedienelement, nicht ein Feld an anderer
 * Stelle, dessen Wirkung man drei Zeilen höher sucht.
 */
function Party({ side, d, busy, onAction, onAsk }: {
  side: VoucherSide | null | undefined; d: Filled; busy: boolean; onAction: Send;
  onAsk: Ask;
}) {
  // ►►► **Welcher Angefragte gerade dasteht** (Testnotiz #951). ◄◄◄
  //
  // *«Was mich noch stört: die jeweilige Anschrift ist nicht sichtbar … es müssen nicht
  // alle auf einmal sein, aber immer mindestens eine geladen und ggf. auf Wunsch die
  // anderen auch.»*
  //
  // Ein **Beleg** hat einen Adressaten – also steht einer vollständig da, und ein Klick
  // auf einen Chip schaltet um. Die Seiten **reisen alle mit** (`recipients`): bei einer
  // Handvoll Angefragten kostet das nichts, und ein Endpunkt «Anschrift zu Nummer» wäre
  // ein zweiter Weg zu einer Angabe, die der Beleg ohnehin liefert.
  const [shown, setShown] = useState<number | null>(null);
  if (!side) return <div />;
  // **Wer die Gegenseite ist, sagt die Struktur** (`ours` vom Server) – nicht ein Vergleich
  // auf «Leistungserbringer». Ein Spiegel über die API-Grenze wird beim ersten Umbenennen
  // still falsch.
  const list = side.ours ? [] : (d.recipients ?? []);
  // **Mindestens eine** – der Adressat, wenn es einen gibt, sonst der erste Angefragte.
  const current = shown ?? side.object_id ?? list[0]?.object_id ?? null;
  const view = list.find((r) => r.object_id === current) ?? side;
  return (
    <div style={{
      display: 'grid', gridRow: `span ${PARTY_ROWS}`, gridTemplateRows: 'subgrid',
      rowGap: 3, minWidth: 0, alignContent: 'start',
    }}>
      {/* ►►► **Die Auswahl steht ÜBER der Rolle** (Testnotiz #981). ◄◄◄ Erst *wen meine
          ich*, dann *was gilt für ihn* – und was angewählt ist, steht darunter. */}
      {side.ours
        ? <div />
        : (
          <Recipients d={d} side={side} busy={busy} onAsk={onAsk}
            current={current} onShow={setShown} onAction={onAction} />
        )}
      <span style={MICRO_LABEL} data-tip={side.hint || undefined}>{side.label}</span>
      {/* ►►► **Name und Nummer in EINER Zeile** (Testnotiz #940). ◄◄◄ Sie benennen
          **einen** Datensatz – dieselbe Form wie in der Positionszeile (#933). */}
      <span className="flex items-baseline" style={{ gap: 8, minWidth: 0 }}>
        {side.ours
          ? <Issuer d={d} side={side} onAction={onAction} />
          : (
            <span className="truncate"
              style={{ font: '600 13px var(--font-body)', color: 'var(--fg-1)',
                       minWidth: 0 }}>
              {view.name || <Missing what="Name" />}
            </span>
          )}
        {view.object_id != null && (
          <span style={{ flex: 'none' }}><ObjId value={view.object_id} /></span>
        )}
      </span>
      {view.attn
        ? <span style={{ fontSize: 12, color: 'var(--fg-2)' }}>{view.attn}</span>
        : <div />}
      {(view.address ?? []).length
        ? <Anschrift label={view.address_label} lines={view.address ?? []} />
        /* ►►► **Was fehlt, wird gesagt – aber nur über jemanden, den es gibt** (#939).
            ◄◄◄ Solange kein Adressat feststeht, nennt die Seite **niemanden**; «Anschrift
            fehlt» wäre dann eine Aussage über eine leere Stelle. Dieselbe Regel wie im
            Dienst (`gaps` prüft die Gegenseite erst, wenn sie bekannt ist). */
        : <div>{view.object_id != null ? <Missing what="Anschrift" /> : null}</div>}
      {/* ►►► **Die Lieferadresse, wo sie eine eigene ist** (Testnotiz #952). ◄◄◄ Sie
          entsteht aus Angaben, die am Benutzer stehen – erfunden wird nichts; wo es nur
          eine Anschrift gibt, bleibt die Zeile leer und **keine** der beiden trägt eine
          Beschriftung: eine Unterscheidung ohne Gegenstück ist keine.
          *Die physische Lieferung selbst bleibt Sache des Bewegen-Moduls; hier steht die
          Anschrift auf dem Beleg, nicht der Transport.* */}
      {(view.shipping ?? []).length
        ? <Anschrift label={view.shipping_label} lines={view.shipping ?? []} />
        : <div />}
      {/* ►►► **E-Mail und Telefon untereinander** (Testnotiz #944). ◄◄◄ Es sind zwei
          Wege, nicht ein Wert – und auf der Breite einer Beleg-Spalte brach die Zeile
          ohnehin, nur an einer beliebigen Stelle. */}
      {view.email || view.phone
        ? (
          <span style={{ fontSize: 12, color: 'var(--fg-3)', whiteSpace: 'pre-line' }}>
            {[view.email, view.phone].filter(Boolean).join('\n')}
          </span>
        )
        : <div />}
      {view.uid
        ? <span style={{ fontSize: 12, color: 'var(--fg-3)' }}>{view.uid}</span>
        : <div />}
    </div>
  );
}

/** Eine Anschrift als Zeilen – mit Beschriftung nur, wo es zwei gibt (#952). */
function Anschrift({ label, lines }: { label?: string | null; lines: string[] }) {
  return (
    <span className="flex flex-col" style={{ gap: 1, minWidth: 0 }}>
      {label && <span style={MICRO_LABEL}>{label}</span>}
      <span style={{ fontSize: 12, color: 'var(--fg-2)', whiteSpace: 'pre-line' }}>
        {lines.join('\n')}
      </span>
    </span>
  );
}

/**
 * ►►► **Die Gegenpartei — EINE Liste, EINE Form** (Testnotizen #912/#951/#962). ◄◄◄
 *
 * *«Ich kann immer noch nicht einen User abwählen oder wieder aktivieren – es bleiben
 * immer beide aktiv. Zudem sehe ich die Anschrift(en) nicht … Finde hierfür endlich eine
 * schlanke und vor allem gute ROBUSTE Lösung, visuell sehr minimalistisch wie immer.»*
 *
 * **Der Befund war eine Doppelung, kein kaputter Knopf.** Dieselbe Sache stand in **zwei**
 * Formensprachen da: eine angefragte Partei als *Chip* mit Zustandspunkt und ✕, eine
 * zugelassene, noch nicht angefragte als `+ Name`-Knopf – und der trug ausgerechnet
 * `.ix-editable`, die Auszeichnung **änderbarer Werte**. Damit sah *jede* Partei dauerhaft
 * «aktiv» aus, und ob eine angefragt war, war an der Form nicht abzulesen.
 *
 * Jetzt: **ein Chip je möglicher Gegenpartei** (zugelassene ∪ angefragte, `recipients`
 * vom Server) und **eine Anatomie** – Punkt, Name, Handlung:
 *
 * * **Der Punkt sagt, ob angefragt ist**: gefüllt in der Zustandsfarbe ↔ hohler Ring.
 * * **Der Name zeigt die Anschrift** – immer, auch bei einer, die noch nicht angefragt
 *   ist. Genau das war die zweite Hälfte der Meldung: im Offertenschritt ist noch niemand
 *   angefragt, und die Anschrift will man sehen, **bevor** man anbietet.
 * * **Die Handlung steht rechts im Chip und ist genau eine**: `+` fragt an, `✕` zieht
 *   zurück. Ein Klick, eine Wirkung; zwei Knöpfe in einer Hülle, nie einer im anderen
 *   (verschachtelte Knöpfe sind ungültiges HTML).
 *
 * **Und die Liste hängt nicht mehr an `ask`.** Sie stand nur da, solange man anfragen
 * *durfte* – fehlte eine Stammdatenangabe (`gaps`), verschwand mit dem Anfragen auch das
 * Abwählen und die Anschrift. Was man **tun** darf, entscheidet weiterhin `can`, je Chip;
 * was man **sehen** darf, ist eine andere Frage.
 *
 * ►►► **Sie ist nur noch die Auswahl** (Testnotiz #981). ◄◄◄ Sie stand in der Namenszeile
 * und trug damit zwei Aufgaben: auswählen **und** die Gewählte benennen. Jetzt steht sie
 * über der Rolle, und der Name steht dort, wo er auf jedem Beleg steht – darunter. Nach
 * dem Zuschlag gibt es nichts mehr zu wählen: dann ist die Zeile leer (die unterlegenen
 * Angebote sind der Nachweis und stehen in ihrem Abschnitt).
 */
function Recipients({ d, side, busy, current, onAsk, onShow, onAction }: {
  d: Filled; side: VoucherSide; busy: boolean;
  /** Wessen Anschrift gerade dasteht – der Chip dazu ist markiert. */
  current: number | null;
  onAsk: Ask;
  onShow: (objectId: number) => void;
  onAction: Send;
}) {
  const open = d.stage === DEAL_STAGE.offer;
  const [picked, setPicked] = useState<VoucherParty | null>(null);
  const find = useCallback((q: string) => api.searchVoucherParties(q).catch(() => []), []);

  // Steht der Zuschlag, gibt es nichts mehr zu wählen – der Name steht eine Zeile tiefer,
  // wo er auf jedem Beleg steht.
  if (!open) return <div />;
  const asked = new Map(d.quotes.map((q) => [q.party_object_id, q]));
  const free = (d.allowed ?? []).length === 0;
  const canAsk = may(d, 'ask');
  // ►►► **Abwählen ist die Gegenhandlung zum Anfragen** (Testnotiz #951). ◄◄◄ Die
  // Hausregel steht seit dem Beschaffen-Modul: jede Zusage nach aussen hat ihre
  // Gegenhandlung an derselben Stelle. **Ob** es geht, sagt `can` (der Server sperrt die
  // zugesagte Zeile – dort ist der Storno der Weg).
  const canDrop = may(d, 'unask');
  // **Die Reihenfolge kommt vom Server** (`recipients`: Definition zuerst, frei
  // Hinzugefügte dahinter). Sie hier neu zu sortieren wäre eine zweite Ordnung.
  const rows = (d.recipients ?? []).filter((r) => r.object_id != null);
  return (
    <div className="flex flex-wrap items-center" style={{ gap: 6, minWidth: 0 }}>
      {rows.map((r) => {
        const number = r.object_id as number;
        const quote = asked.get(number);
        return (
          <Chip key={number} name={r.name || String(number)} number={number}
            state={quote ? (quote.state ?? QUOTE_STATE.asked) : null}
            active={number === current}
            onShow={() => onShow(number)}
            onAsk={!quote && canAsk && !busy ? () => onAsk([number]) : undefined}
            onDrop={quote && canDrop && quote.state !== QUOTE_STATE.chosen && !busy
              ? () => void onAction({ action: 'unask', party: number })
              : undefined} />
        );
      })}
      {free && (
        // ►►► **Dieselbe Form wie jeder änderbare Wert** (#928/#930). ◄◄◄ Im Ruhezustand
        // steht da, was auf dem Beleg stünde – der Klick macht daraus die Suche. Nur wo
        // die Definition **niemanden** nennt: wo sie es tut, ist die Liste die Antwort.
        <DocRef<VoucherParty>
          on text={rows.length ? `+ ${d.party_word}` : d.party_word}
          placeholder={d.party_word} tip={d.party_word}
          face={{ fontSize: 13, color: 'var(--fg-3)' }}
          value={picked?.object_id ?? null} selected={picked} find={find}
          onChange={(_n, option) => {
            setPicked(null);
            if (option) onAsk([option.object_id]);
          }}
        />
      )}
    </div>
  );
}

/**
 * **Eine mögliche Gegenpartei** – Punkt, Name, Handlung. Die Anatomie jedes Zustands im
 * Haus, und hier gibt es sie **einmal** für beide Fälle (#962).
 *
 * ►►► **Der Chip trägt zwei Knöpfe, nie einen im anderen** (Testnotiz #951): der **Name**
 * zeigt die Anschrift, das Zeichen rechts fragt an bzw. zieht zurück. Verschachtelte
 * Knöpfe sind ungültiges HTML, und ein einziger müsste erraten, was gemeint war.
 *
 * ►►► **Und er trägt KEINEN Zustandspunkt** (Testnotiz #983). ◄◄◄ *«Ein optisch störender
 * Punkt/Separator.»* – Er war es, und zwar aus einem Grund: er sagte als **vierter**, was
 * an derselben Stelle schon dreimal steht. Was angefragt ist, sagt das **Zeichen rechts**
 * (`+` = noch nicht, `✕` = angefragt und zurückziehbar), die **Textfarbe** (gedämpft ↔
 * normal) und das **Wort im Hover**; ausführlich steht es eine Zeile tiefer im Abschnitt
 * *Angebote*, wo jede Zeile ihren eigenen Punkt und ihr eigenes Wort trägt.
 *
 * Ein 6-px-Punkt in einer Reihe von Pillen ist genau die Form, in der «Punkt + Wort» nicht
 * mehr gilt: das Wort fehlt, und was bleibt, ist ein Zeichen, das man deuten muss.
 */
function Chip({ name, number, state, active, onShow, onAsk, onDrop }: {
  name: string; number: number;
  /** Der Zustand der Angebotszeile – `null` heisst «noch nicht angefragt». */
  state: string | null;
  active?: boolean;
  onShow?: () => void;
  onAsk?: () => void;
  onDrop?: () => void;
}) {
  const look = quoteLook(state);
  return (
    <span className="inline-flex items-center" style={{
      gap: 6, padding: `3px ${onAsk || onDrop ? 4 : 8}px 3px 8px`, borderRadius: 999,
      border: `1px solid ${active ? 'var(--accent)' : 'var(--border-1)'}`,
      background: active ? 'var(--accent-soft)' : undefined,
      fontSize: 12, color: state ? 'var(--fg-1)' : 'var(--fg-3)', minWidth: 0,
    }} data-tip={look.label}>
      <button type="button" onClick={onShow} aria-label={`Anschrift von ${name || number}`}
        className="truncate" style={{ ...DOC_FIELD, maxWidth: 150,
                                      cursor: onShow ? 'pointer' : 'default' }}>
        {name || number}
      </button>
      {onAsk && (
        <button type="button" onClick={onAsk} aria-label="Anfragen" data-tip="Anfragen"
          style={{ ...DOC_FIELD, display: 'inline-flex', color: 'var(--accent)',
                   cursor: 'pointer', padding: '0 2px' }}>
          <Plus size={11} />
        </button>
      )}
      {onDrop && (
        <button type="button" onClick={onDrop} aria-label="Anfrage zurückziehen"
          data-tip="Anfrage zurückziehen"
          style={{ ...DOC_FIELD, display: 'inline-flex', color: 'var(--danger)',
                   cursor: 'pointer', padding: '0 2px' }}>
          <X size={11} />
        </button>
      )}
    </span>
  );
}

/** Der Zustand einer Angebotszeile als Punkt + Wort – die eine Auflösung. */
function quoteLook(state: string | null): { label: string; color: string } {
  if (state === QUOTE_STATE.chosen) return { label: 'Zugesagt', color: 'var(--ok)' };
  if (state === QUOTE_STATE.declined) return { label: 'Abgesagt', color: 'var(--danger)' };
  if (state === QUOTE_STATE.quoted) return { label: 'Offeriert', color: 'var(--warn)' };
  if (state === null) return { label: 'Noch nicht angefragt', color: 'var(--fg-4)' };
  return { label: 'Angefragt', color: 'var(--fg-4)' };
}

/**
 * **Welche unserer Gesellschaften den Beleg stellt** – vorgewählt, hier steht die
 * Korrektur. Nur, wo es mehr als eine gibt: eine Auswahl mit genau einer Antwort ist keine.
 */
function Issuer({ d, side, onAction }: {
  d: Filled; side: VoucherSide; onAction: Send;
}) {
  // **Stabil über Renderings** – sonst baut `find` bei jedem Rendern neu, und das
  // Suchfeld verlöre seine Ergebnisse mitten im Tippen.
  const options = useMemo(() => d.issuers ?? [], [d.issuers]);
  // **Die Liste reist mit dem Vorgang** – ein eigener Such-Endpunkt für eine Handvoll
  // Gesellschaften wäre ein Weg zu viel. Gesucht wird darum in ihr.
  const find = useCallback(
    async (q: string) => options
      .filter((o) => o.object_id != null)
      .map((o) => ({ object_id: o.object_id as number, name: o.name }))
      .filter((o) => !q.trim()
        || o.name.toLowerCase().includes(q.toLowerCase())
        || String(o.object_id).includes(q.trim())),
    [options]);

  const face: CSSProperties = { font: '600 13px var(--font-body)', color: 'var(--fg-1)' };
  const chosen = options.find((o) => o.object_id === d.issuer);
  return (
    <DocRef
      // ►►► **Wählbar, solange man darf** (Testnotiz #936). ◄◄◄ Hier stand
      // `options.length > 1` – «eine Auswahl mit genau einer Antwort ist keine». Das
      // stimmt für eine *Frage*, nicht für eine **Korrektur**: wer nachsehen will, welche
      // Gesellschaft den Beleg stellt, findet sonst kein Bedienelement und hält die
      // Vorwahl für unabänderlich. Die Automatik bleibt, wie sie war – der Aussteller ist
      // mit der Freigabe eingefroren (`issuer_of`), hier steht nur die Korrektur.
      on={may(d, 'issuer')}
      text={side.name || <Missing what="Firma" />}
      placeholder={d.issuer_label} tip={d.issuer_label} face={face}
      value={d.issuer ?? null}
      selected={chosen?.object_id != null
        ? { object_id: chosen.object_id, name: chosen.name } : null}
      find={find}
      onChange={(n) => void onAction({ action: 'issuer', issuer: n })}
    />
  );
}


/**
 * ►►► **Was fehlt, um weiterzukommen** – `StepNeed` für Stammdaten. ◄◄◄
 *
 * Wo sie hingehört (klickbar), was fehlt und **warum dieser Beleg sie braucht**. Kein
 * Zustand und kein Pausenwert: der Knopf ist nicht da, und hier steht, woran es liegt.
 */
function Gaps({ rows }: { rows: NonNullable<Filled['gaps']> }) {
  if (!rows.length) return null;
  return (
    <div className="flex flex-col" style={{
      gap: 6, padding: '9px 11px', borderRadius: 'var(--r-md)',
      background: 'var(--warn-bg)', border: '1px solid var(--warn)',
    }}>
      {rows.map((g, i) => (
        <div key={i} className="flex flex-col" style={{ gap: 2 }}>
          <span className="flex items-center" style={{ gap: 6, fontSize: 12.5 }}>
            <AlertTriangle size={12} style={{ color: 'var(--warn)', flex: 'none' }} />
            <strong style={{ fontWeight: 600 }}>{g.field_label}</strong>
            <span style={{ color: 'var(--fg-3)' }}>bei</span>
            {g.record_object_id
              ? <ObjId value={g.record_object_id} />
              : <span>{g.record_label}</span>}
          </span>
          <span style={{ fontSize: 11.5, color: 'var(--fg-3)', paddingLeft: 18 }}>
            {g.why}
          </span>
        </div>
      ))}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Die Positionen
// ───────────────────────────────────────────────────────────────────────────────

/** Unter dieser Breite nennt die Zeile ihre Sache nicht mehr – dann bricht sie um. */
const NAME_MIN = 190;

/**
 * ►►► **Die Positionen — und sie werden GESPEICHERT, nicht abgeschickt.** ◄◄◄
 *
 * Beim Vorgänger reisten die Preise in der Nutzlast des **Anfragens** mit: man tippte sie
 * und schickte sie im selben Zug hinaus. Damit gab es keinen Zustand «geschrieben, aber
 * noch nicht angeboten» – und die Hausregel «Auto-Save überall» galt ausgerechnet für das
 * Herzstück des Belegs nicht.
 *
 * Hier ist die Position **der Beleg**: sie wird geschrieben, sooft jemand tippt (`price`),
 * und `ask` schickt sie hinaus. Zwei Handlungen, zwei Verben.
 *
 * **Jeder Wert trägt die Auszeichnung** (#922): Preis, Satz, Zolltarifnummer und
 * Ursprungsland. Sie sehen aus wie auf dem fertigen Beleg, nur gehighlighted.
 */
function Goods({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  const editable = may(d, 'price') && d.we_quote;
  const customs = may(d, 'price');
  return (
    <ModuleSection title={d.goods_title || 'Positionen'}
      state={d.stage === DEAL_STAGE.offer ? 'active' : 'past'}>
      <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
        {d.lines.length === 0 && (
          <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>
            Vor diesem Modul steht noch nichts – die Positionen sind die Einzelinstanzen
            des Auftrags.
          </span>
        )}
        {d.lines.map((ln) => (
          <LineRow key={ln.id} d={d} line={ln} busy={busy}
            editable={editable} customs={customs} onAction={onAction} />
        ))}
        {/* ►►► **Was ist zu tun? — der Satz am Modul.** ◄◄◄ Er steht bei den Positionen,
            weil er von **ihnen** handelt («Härten auf 58 HRC»), und er steht **einmal**,
            weil er für jeden Partner gleich lautet.
            Er ist eine **Auskunft**, kein Feld: entschieden wird er beim Modellieren, wo
            man einen Fertigungsablauf definiert – hier wird der Ablauf abgearbeitet.
            **Leer heisst «gemäss Spezifikation»**, und das schreibt der Beleg nicht hin:
            eine Zeile, die «nichts Besonderes» sagt, ist keine Auskunft. */}
        {d.task && (
          <div className="flex" style={{ gap: 8, minWidth: 0,
                                         paddingTop: 2, alignItems: 'baseline' }}>
            <span style={{ ...MICRO_LABEL, flex: 'none' }}>{d.task_label}</span>
            <span style={{ fontSize: 12.5, color: 'var(--fg-2)', minWidth: 0 }}>
              {d.task}
            </span>
          </div>
        )}
        <Sums d={d} busy={busy} onAction={onAction} />
      </div>
    </ModuleSection>
  );
}

/** Eine Positionszeile – Menge, Sache, Zoll · Preis und Satz. */
function LineRow({ d, line, busy, editable, customs, onAction }: {
  d: Filled; line: Filled['lines'][number]; busy: boolean;
  editable: boolean; customs: boolean; onAction: Send;
}) {
  const [price, setPrice] = useState(line.price ?? '');
  const [vat, setVat] = useState(line.vat ?? 'normal');
  const [hs, setHs] = useState(line.hs_code ?? '');
  const [origin, setOrigin] = useState(line.origin_country ?? '');

  // **Was der Server sagt, gewinnt** – aber nur, wenn er sich ändert: ein `useState`-
  // Startwert wird einmal gelesen, und wer danach etwas anderes tippt, schriebe den alten
  // Wert zurück (#846).
  useEffect(() => { setPrice(line.price ?? ''); }, [line.price]);
  useEffect(() => { setVat(line.vat ?? 'normal'); }, [line.vat]);
  useEffect(() => { setHs(line.hs_code ?? ''); }, [line.hs_code]);
  useEffect(() => { setOrigin(line.origin_country ?? ''); }, [line.origin_country]);

  const dirty = price !== (line.price ?? '') || vat !== (line.vat ?? 'normal')
    || hs !== (line.hs_code ?? '') || origin !== (line.origin_country ?? '');
  const save = useCallback(() => {
    void onAction({
      action: 'price',
      lines: [{ id: line.id, price: price === '' ? null : price, vat,
                hs_code: hs, origin_country: origin }],
    });
  }, [onAction, line.id, price, vat, hs, origin]);
  const now = useAutosave(`${line.id}:${price}:${vat}:${hs}:${origin}`,
    dirty && !busy, save);

  return (
    <div className="flex flex-wrap items-start" style={{ gap: '6px 12px', minWidth: 0 }}>
      <div className="flex items-baseline"
        style={{ gap: 8, flex: `1 1 ${NAME_MIN}px`, minWidth: 0 }}>
        <span style={{ font: '600 13px var(--font-mono, var(--font-body))',
                       fontVariantNumeric: 'tabular-nums', flex: 'none' }}>
          {line.quantity}×
        </span>
        <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
          {/* ►►► **Name und Objektnummer stehen in EINER Zeile** (Testnotiz #933). ◄◄◄
              *«Der Name und die Objektnummer sollten immer in einer Linie, in einer Reihe
              sein, nicht umgebrochen.»* – Sie benennen **einen** Datensatz; untereinander
              lesen sie sich wie zwei Angaben. Gekappt wird der **Name**, nie die Nummer:
              sie ist die Kennung, an der man die Sache wiedererkennt. */}
          <span className="flex items-baseline" style={{ gap: 8, minWidth: 0 }}>
            <span className="truncate" style={{ fontSize: 13, color: 'var(--fg-1)' }}>
              {line.article_name || '—'}
            </span>
            {line.article_object_id != null && (
              <span style={{ flex: 'none' }}><ObjId value={line.article_object_id} /></span>
            )}
          </span>
          <span className="flex flex-wrap items-center" style={{ gap: 8, minWidth: 0 }}>
            {/* ►►► **Zoll: der Artikel belegt vor, der Beleg trägt den Wert** (#915). ◄◄◄
                Zolltarifnummer und Ursprungsland sind keine Beschreibung, sondern
                Voraussetzung der Ausfuhr – sie stehen offen in der Zeile, nicht hinter
                einem Klick. */}
            <Customs label="Zolltarif" value={hs} on={customs} width={86}
              busy={busy} onChange={setHs} onDone={now} />
            <Customs label="Ursprung" value={origin} on={customs} width={64}
              busy={busy} onChange={setOrigin} onDone={now} />
          </span>
        </div>
      </div>
      {d.we_quote && (
        // ►►► **Der Satz steht VOR dem Betrag** (Testnotiz #972). ◄◄◄
        //
        // *«Kann der MWST-Satz evtl. vor dem Betrag stehen? Irgendwie schaut das etwas
        // komisch aus, da alles weiter untereinander steht.»* – Und das ist nicht bloss
        // Geschmack: die **Zahl** ist die letzte Angabe der Zeile, sie steht rechtsbündig
        // und bildet mit der Zeile darunter eine Spalte. Stand der Satz dahinter,
        // verschob jede Satz-Beschriftung anderer Länge («8.10 % · Normalsatz» ↔ «0.00 %
        // · Export») den Betrag – die Beträge standen untereinander **nicht** unter-
        // einander. Der Satz ist die Eigenschaft, der Preis das Ergebnis.
        // ►►► **Und sie stehen auf EINER Grundlinie** (Testnotiz #963). ◄◄◄
        //
        // *«Entweder täusche ich mich, oder auch hier ist so ein leichter Höhenversatz
        // zwischen den Werten.»* – Er täuschte sich nicht: Satz (12 px) und Preis (13 px)
        // standen **mittig** ausgerichtet, und zwei verschieden grosse Texte in einer
        // Reihe sind mittig zentriert genau dann versetzt, wenn man sie nebeneinander
        // liest (gemessen: 2,75 px). Eine Zeile Text hat eine **Grundlinie**, und darauf
        // sitzen beide – dieselbe Ausrichtung wie überall sonst auf diesem Beleg.
        // ►►► **Und die Gruppe darf umbrechen** – gemessen, nicht vermutet. ◄◄◄ Sie stand
        // auf `flex: none`, also auf ihrer vollen Inhaltsbreite; bei einem langen
        // Satznamen («0.00 % · Steuerfreie Ausfuhrlieferung», seit dem Nullsatz mit zwei
        // Tatbeständen) sind das rund 300 px, und in einer 320-px-Spur lief die Zeile um
        // **13,8 px** über. Mit `0 1 auto` + Umbruch fällt der Preis unter seinen Satz,
        // statt aus der Karte zu ragen – und beide bleiben lesbar. *Ein Kürzen wäre die
        // andere Lösung und die falsche: der Rechtsgrund eines Nullsatzes gehört auf den
        // Beleg, nicht in einen Hover.*
        <div className="flex flex-wrap items-baseline justify-end"
          style={{ gap: '2px 10px', flex: '0 1 auto', minWidth: 0 }}>
          {/* ►►► **Der Steuersatz nennt seinen Prozentsatz** (Testnotiz #932). ◄◄◄
              *«‹Normalsatz›, ‹Reduziert› sind leider zu wenig aussagekräftig – es sollte
              immer noch der entsprechende Prozentsatz angegeben sein.»* Beides steht
              längst in den Daten (`label` + `rate`); zusammengesetzt wird es an **einer**
              Stelle (`vatText`), damit Auswahl und Anzeige nicht auseinanderlaufen. */}
          <DocPick on={editable} value={vat} text={vatText(line.vat_label, line.vat_rate)}
            busy={busy} aria={d.vat_label} tip={line.vat_note || d.vat_label}
            face={{ fontSize: 12, color: 'var(--fg-3)' }}
            options={(d.vat_rates ?? []).map((v) => ({
              value: v.key, label: vatText(v.label, v.rate) }))}
            onChange={(v) => { setVat(v); }} />
          <Editable on={editable} title="Einzelpreis, netto"
            missing={editable && price.trim() === ''}>
            {editable ? (
              // ►►► **Ein Betrag hat die Nachkommastellen SEINER Währung** (#931). ◄◄◄
              // *«Warum hat das vier Stellen? Eine Währung hat doch immer zwei.»* – Fast:
              // JPY hat null, KWD drei; die Zahl steht im Vorgang (`currency_decimals`).
              // Die vier kamen aus der Spalte `NUMERIC(18, 4)` – behoben ist das am
              // **Dienst**; hier wird verhindert, dass man sie überhaupt tippen kann.
              <input {...numericInputProps} value={price} disabled={busy}
                onChange={(e) => setPrice(
                  numericOnly(e.target.value, { decimals: d.currency_decimals ?? 2 }))}
                onBlur={now}
                onKeyDown={(e) => { if (e.key === 'Enter') now(); }}
                aria-label="Einzelpreis"
                style={{ ...DOC_FIELD, width: 92, textAlign: 'right', fontSize: 13,
                         fontVariantNumeric: 'tabular-nums' }} />
            ) : (
              <span style={{ fontSize: 13, fontVariantNumeric: 'tabular-nums' }}>
                {line.price ? formatAmount(line.price, d.currency_decimals ?? 2) : '—'}
              </span>
            )}
          </Editable>
        </div>
      )}
    </div>
  );
}

/**
 * **Ein Steuersatz heisst, wie er heisst – und wie hoch er ist** (Testnotiz #932).
 *
 * Name **und** Prozentsatz, an einer Stelle zusammengesetzt: «Normalsatz» allein sagt
 * nicht, ob 8.1 oder 7.7 gemeint ist, und ein Beleg, den man später liest, muss es sagen.
 * Beide Angaben reisen ohnehin mit (`label` · `rate`) – eine zweite Auflösung im Browser
 * wäre die Stelle, an der Auswahl und Anzeige auseinanderlaufen.
 */
function vatText(label?: string | null, rate?: string | null): string {
  const name = label ?? '';
  if (!rate) return name || '—';
  // ►►► **Der Wert zuerst, der Name danach** (Testnotiz #938). ◄◄◄ Auf einem Beleg ist
  // die **Zahl** die Aussage – der Name ist ihr Rechtsgrund. Und in einer Liste
  // untereinander steht so das Gleiche übereinander: «8.10 %», «2.60 %», «0.00 %».
  return name ? `${rate} % · ${name}` : `${rate} %`;
}

/**
 * Eine Zoll-Angabe – klein, an ihrer Zeile, und änderbar, solange der Beleg offen ist.
 *
 * ►►► **Die Beschriftung steht davor — beim Eingeben wie im fertigen Beleg** (#982). ◄◄◄
 *
 * *«Im fertigen Beleg steht eigentlich immer ‹Zolltarif xy, Ursprung xy› – hier bei der
 * Eingabe steht einfach nur das Eingabefeld, aber der entsprechende Text nicht davor. Das
 * ist eine unerlaubte Abweichung von unserer Logik.»*
 *
 * Und das stimmt: der Name stand als **Platzhalter** im Feld, also an genau der Stelle,
 * an der eine Oberfläche sagt «hier ist nichts» – und er verschwand beim ersten Zeichen.
 * Die ganze Regel dieses Belegs lautet *der gedruckte Wert IST das Bedienelement* (#922):
 * was man ändert, muss aussehen wie das, was gedruckt wird. Hier war es andersherum.
 *
 * Beschriftung und Wert sind darum **eine** Zeile in beiden Zuständen – dieselbe Grösse,
 * dieselbe Farbe; nur der Wert trägt die Auszeichnung, denn nur er ist änderbar.
 */
function Customs({ label, value, on, width, busy, onChange, onDone }: {
  label: string; value: string; on: boolean; width: number; busy: boolean;
  onChange: (v: string) => void; onDone: () => void;
}) {
  if (!on) {
    return value
      ? <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>{label} {value}</span>
      : null;
  }
  return (
    <span className="inline-flex items-baseline" style={{ gap: 4, minWidth: 0 }}>
      <span style={{ fontSize: 11.5, color: 'var(--fg-3)', flex: 'none' }}>{label}</span>
      <Editable title={label} missing={value.trim() === ''}>
        <input value={value} disabled={busy} aria-label={label}
          onChange={(e) => onChange(e.target.value)}
          onBlur={onDone}
          onKeyDown={(e) => { if (e.key === 'Enter') onDone(); }}
          style={{ ...DOC_FIELD, width, fontSize: 11.5, color: 'var(--fg-2)' }} />
      </Editable>
    </span>
  );
}

/**
 * ►►► **Netto · Steuer je Satz · Total — und jede Zahl nennt ihre Währung** (#921). ◄◄◄
 *
 * *«Eigentlich wäre es schon schön und einheitlich, wenn daneben die Währung stehen
 * würde.»* – Die Regel daraus: **jede Zahl, die man abschreibt oder überweist, nennt ihre
 * Währung.** Nicht an jedem Einzelpreis: dort stünde dasselbe Wort zwanzigmal.
 *
 * **Die Währung selbst IST das Bedienelement** (#917): kein Formularfeld über einer
 * Tabelle, in der sonst nur Zahlen stehen – der Code am Total, in derselben Schrift wie
 * die Zahl daneben, mit der Auszeichnung aus #922.
 */
function Sums({ d, busy, onAction }: {
  d: Filled; busy: boolean; onAction: Send;
}) {
  const splits = d.vat_split ?? [];
  const code = d.currency;
  const dec = d.currency_decimals ?? 2;
  if (!d.we_quote && !d.amount) return null;
  const total = d.amount ?? sum(splits, dec);
  return (
    <div className="flex flex-col" style={{
      gap: 4, marginTop: 4, paddingTop: 9, borderTop: '1px solid var(--border-1)',
    }}>
      {d.net != null && (
        <SumRow label="Netto" value={`${formatAmount(d.net, dec)} ${code}`} />
      )}
      {splits.map((v, i) => (
        <SumRow key={i} label={`${d.vat_label} ${v.label ?? v.rate} (${v.rate} %)`}
          value={`${formatAmount(v.tax, dec)} ${code}`} hint={v.note ?? undefined} />
      ))}
      <div className="flex items-baseline" style={{
        gap: 10, marginTop: 4, paddingTop: 7, borderTop: '1px solid var(--border-1)',
      }}>
        <span style={{ ...MICRO_LABEL, flex: 1 }}>Total</span>
        <span style={{ font: '700 14px var(--font-body)',
                       fontVariantNumeric: 'tabular-nums' }}>
          {formatAmount(total, dec)}
        </span>
        <Currency d={d} busy={busy} onAction={onAction} />
      </div>
    </div>
  );
}

function SumRow({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex items-baseline" style={{ gap: 10 }}>
      <span style={{ fontSize: 12, color: 'var(--fg-3)', flex: 1, minWidth: 0 }}
        {...(hint ? { 'data-tip': hint } : {})}>{label}</span>
      <span style={{ fontSize: 12.5, fontVariantNumeric: 'tabular-nums' }}>{value}</span>
    </div>
  );
}

function sum(rows: NonNullable<Filled['vat_split']>, dec: number): string {
  const total = rows.reduce(
    (n, r) => n + Number(r.net ?? 0) + Number(r.tax ?? 0), 0);
  return total.toFixed(dec);
}

/**
 * **Die Währung — der Code selbst ist der Wähler** (#917/#921).
 *
 * Sichtbar ist ein `<span>` in der Schrift der Zahl daneben; bedienbar ein unsichtbares
 * `<select>` darüber. Ein nativer Wähler zeigt geschlossen den Text **seiner** Zeile, und
 * der wäre bei «CHF · Schweizer Franken» auf Code-Breite ein halber Name.
 *
 * Steht die Zusage, gibt es nichts mehr zu wählen – dann ist es eine Tatsache, und die
 * Auszeichnung fällt mit ihr weg.
 */
function Currency({ d, busy, onAction }: {
  d: Filled; busy: boolean; onAction: Send;
}) {
  return (
    <DocPick on={may(d, 'currency')} value={d.currency} text={d.currency}
      face={{ font: '600 13px var(--font-body)', color: 'var(--fg-2)' }}
      tip={d.currency_label} busy={busy} aria={d.currency_label}
      options={(d.currencies ?? []).map((c) => ({ value: c.code, label: c.label }))}
      onChange={(currency) => void onAction({ action: 'currency', currency })} />
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Die Konditionen — ohne Überschrift (#926)
// ───────────────────────────────────────────────────────────────────────────────

/**
 * ►►► **Zahlungsfrist · Lieferfrist · Lieferbedingung — ohne Überschrift** (#926). ◄◄◄
 *
 * *«Ich würde gerne eine reduziertere Ansicht probieren, bei der es keine Überschrift
 * ‹Konditionen› mehr gibt, sondern einfach unter den Positionen und Beträgen die Zahlungs-
 * und Lieferkonditionen stehen. Sollte selbsterklärend genug sein.»* – Stimmt: jede der
 * drei Zeilen trägt ihren Namen, und ein Sammelbegriff darüber sagt nichts dazu.
 *
 * ►►► **Die Zahlungsfrist steht ÜBER der Lieferfrist** (#897). ◄◄◄ Sie ist die
 * folgenreichere Angabe: aus ihr kommt die Fälligkeit, und null heisst Vorauszahlung.
 *
 * **Wer den Preis nennt, nennt auch die Fristen** (`we_quote`): bei einer Einnahme
 * schreiben wir sie hier, bei einer Ausgabe füllt sie die Gegenpartei an ihrer Zeile.
 */
function Terms({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  const on = d.stage === DEAL_STAGE.offer && d.we_quote && may(d, 'terms');
  return (
    <ModuleSection>
      <div style={{ display: 'grid', gap: '10px 24px',
                    gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 170px), 1fr))' }}>
        <SavedTerm label={d.payment_term_label} on={on} busy={busy} field="payment_days"
          days={d.due_days} terms={d.payment_terms ?? []} onAction={onAction}
          freeMin={d.term_free_min ?? 1} freeLabel={d.term_free_label ?? 'Individuell'} />
        <SavedTerm label={d.lead_term_label} on={on} busy={busy} field="lead_days"
          days={d.lead_days} terms={d.lead_terms ?? []} onAction={onAction}
          hint={d.due_date ? `Termin ${day(d.due_date)}` : undefined}
          freeMin={d.term_free_min ?? 1} freeLabel={d.term_free_label ?? 'Individuell'} />
        <Delivery d={d} busy={busy} onAction={onAction} />
      </div>
    </ModuleSection>
  );
}

/**
 * ►►► **Eine Frist auf dem Beleg wird SOFORT geschrieben** (Testnotiz #985). ◄◄◄
 *
 * *«Eingaben in ‹Zahlungsfrist› und ‹Lieferfrist› werden nicht persistiert – nach einem
 * Reload sind sie wieder weg.»* – Sie waren die **einzige** Angabe des Belegs ohne eigenes
 * Verb: ein gehobener Zustand in `BelegWork`, mitgeschickt allein in der Nutzlast von
 * `ask`. Ein Reload verwarf ihn, und zwar stillschweigend.
 *
 * Der Fix ist nicht ein Zustand mehr, sondern **einer weniger**: dieselbe Bauart wie
 * `Delivery` – Entwurf, `useAutosave`, ein Verb (`terms`), und der Server ist die eine
 * Wahrheit. Damit greift er für **jede** weitere Angabe des Belegs, die so entsteht.
 *
 * **`Term` bleibt gesteuert** (Wert + `onChange`): an einer **Angebotszeile** füllt die
 * Gegenpartei Betrag und beide Fristen zusammen aus und schickt sie in einem Zug – dort
 * ist der eine Absenden-Knopf richtig, weil der Dienst die Offerte nur vollständig annimmt.
 */
function SavedTerm({ label, on, busy, field, days, terms, hint, freeMin, freeLabel,
                     onAction }: {
  label: string; on: boolean; busy: boolean;
  /** Welche der beiden Fristen – zugleich der Name im Befehl. */
  field: 'payment_days' | 'lead_days';
  days: number | null | undefined;
  terms: { days: number; label: string }[];
  hint?: string;
  freeMin: number; freeLabel: string;
  onAction: Send;
}) {
  const remote = days == null ? '' : String(days);
  const [draft, setDraft] = useState(remote);
  useEffect(() => { setDraft(remote); }, [remote]);

  const save = useCallback(() => {
    // **Die Null ist eine Angabe** («Vorauszahlung» · «Sofort») – darum auf den leeren
    // String geprüft, nicht auf Wahrheit: `Number('') === 0` machte aus «noch nichts
    // gewählt» die Vorauszahlung.
    void onAction({ action: 'terms',
                    [field]: draft === '' ? null : Number(draft) });
  }, [onAction, field, draft]);
  useAutosave(`${field}:${draft}`, draft !== remote && !busy, save);

  return (
    <Term label={label} on={on} busy={busy} value={draft} days={days} terms={terms}
      hint={hint} freeMin={freeMin} freeLabel={freeLabel} onChange={setDraft} />
  );
}

/**
 * ►►► **Eine Frist ist ein Wert auf dem Beleg, keine Knopfreihe** (Testnotiz #934). ◄◄◄
 *
 * *«So ist das aber noch nicht ganz richtig. Ich möchte die gleiche Logik, das gleiche
 * Design wie bei Währung oder Betragsangabe.»* – Dagestanden hatte ein `TermField`:
 * *Vorauszahlung · 30 Tage · Individuell* als drei Chips nebeneinander, also ein
 * **Formular** mitten im Beleg. Ein Beleg druckt «Zahlbar in 30 Tagen», und dass man das
 * ändern kann, sagt die Haarlinie – mehr nicht.
 *
 * Die freie Eingabe bleibt erhalten und ist derselbe Wert: wer sie wählt, bekommt an
 * **derselben Stelle** ein Zahlenfeld. Ein zweites Bedienelement daneben wäre die zweite
 * Aussage über dieselbe Frist.
 *
 * ►►► **Der Platzhalter trägt kein Steuerzeichen** (Testnotiz #943). ◄◄◄ Er stand hier
 * mit einem vorangestellten **NUL-Byte**, damit er mit keiner Tageszahl kollidieren
 * kann. Es reiste über `outerHTML` in die Testnotiz, und PostgreSQL nimmt **kein** NUL
 * in Text auf: das Speichern brach mit `UntranslatableCharacter` ab. Eindeutig ist er
 * auch so – eine Frist ist eine **Zahl**, und «frei» ist keine.
 */
const TERM_FREE = 'frei';

function Term({ label, on, busy, value, days, terms, hint, freeMin, freeLabel, onChange }: {
  label: string; on: boolean; busy: boolean;
  /** Der Entwurf (leer = noch nichts gewählt) – die gebuchte Zahl steht in `days`. */
  value: string;
  days: number | null | undefined;
  terms: { days: number; label: string }[];
  hint?: string;
  freeMin: number; freeLabel: string;
  onChange: (value: string) => void;
}) {
  const current = on ? value : (days == null ? '' : String(days));
  const named = terms.find((t) => String(t.days) === current);
  const free = current !== '' && !named;
  const [typing, setTyping] = useState(false);
  const word = current === ''
    ? '—'
    : (named ? named.label : `${current} Tag${current === '1' ? '' : 'e'}`);

  return (
    <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
      <span style={MICRO_LABEL}>{label}</span>
      {on && (free || typing) ? (
        <Editable title={label} missing={current === ''}>
          <input {...numericInputProps} autoFocus value={current} disabled={busy}
            aria-label={label}
            onChange={(e) => onChange(numericOnly(e.target.value, { decimals: false }))}
            onBlur={() => {
              setTyping(false);
              const n = Number(current);
              onChange(String(Number.isFinite(n) && n >= freeMin ? n : freeMin));
            }}
            onKeyDown={(e) => { if (e.key === 'Enter') e.currentTarget.blur(); }}
            style={{ ...DOC_FIELD, width: 64, fontSize: 13,
                     fontVariantNumeric: 'tabular-nums' }} />
        </Editable>
      ) : (
        <DocPick on={on} value={named ? current : ''} text={word} busy={busy} aria={label}
          missing={current === ''}
          face={{ fontSize: 13, color: 'var(--fg-1)' }} tip={hint}
          options={[
            ...(current === '' ? [{ value: '', label: '—' }] : []),
            ...terms.map((t) => ({ value: String(t.days), label: t.label })),
            { value: TERM_FREE, label: freeLabel },
          ]}
          onChange={(v) => {
            if (v === TERM_FREE) { setTyping(true); onChange(String(freeMin)); return; }
            onChange(v);
          }} />
      )}
    </div>
  );
}

/** Ein feststehender Wert – Versalien-Beschriftung, Wert darunter. Wie eine Beleg-Fusszeile. */
function Fixed({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
      <span style={MICRO_LABEL}>{label}</span>
      <span style={{ fontSize: 13, color: 'var(--fg-1)' }}
        {...(hint ? { 'data-tip': hint } : {})}>{value}</span>
    </div>
  );
}

/**
 * ►►► **Die Lieferbedingung — Klausel UND Ort sind EINE Vereinbarung** (#911). ◄◄◄
 *
 * Sie leben als **ein** Entwurf und gehen zusammen hinaus, sobald er vollständig ist: das
 * Feld hing einmal am Serverwert und schickte beim Wählen sofort die Klausel **ohne** Ort;
 * der Dienst weist das zu Recht ab («FCA» allein ist keine Vereinbarung), der Server
 * änderte also nichts, und es sah aus, als täte der Klick nichts.
 */
function Delivery({ d, busy, onAction }: { d: Filled; busy: boolean; onAction: Send }) {
  const editable = may(d, 'incoterm');
  const [key, setKey] = useState(d.incoterm ?? '');
  const [place, setPlace] = useState(d.incoterm_place ?? '');
  useEffect(() => { setKey(d.incoterm ?? ''); }, [d.incoterm]);
  useEffect(() => { setPlace(d.incoterm_place ?? ''); }, [d.incoterm_place]);

  const complete = key === '' || place.trim() !== '';
  const dirty = key !== (d.incoterm ?? '') || place !== (d.incoterm_place ?? '');
  const save = useCallback(() => {
    void onAction({ action: 'incoterm', incoterm: key || null, incoterm_place: place });
  }, [onAction, key, place]);
  const now = useAutosave(`${key}:${place}`, dirty && complete && !busy, save);

  if (!editable) {
    return (
      <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
        <span style={MICRO_LABEL}>{d.incoterm_label || 'Lieferbedingung'}</span>
        <span style={{ fontSize: 13, color: 'var(--fg-1)' }}>{d.incoterm_text || '—'}</span>
      </div>
    );
  }
  const chosen = (d.incoterms ?? []).find((t) => t.key === key);
  return (
    <div className="flex flex-col" style={{ gap: 2, minWidth: 0 }}>
      <span style={MICRO_LABEL}>{d.incoterm_label}</span>
      {/* ►►► **Die Klausel steht als KÜRZEL da, nicht als volle Zeile** (#935). ◄◄◄
          Gemeldet war «das Feld ist irgendwie super breit und der Dropdown-Button etwas
          eingerückt» – ein natives Auswahlfeld nimmt die Breite seiner längsten Zeile,
          und die heisst hier «DPU · Geliefert entladen». Sichtbar ist jetzt, was auf dem
          Beleg steht; die Erklärung folgt darunter als Satz. */}
      <DocPick on value={key} text={chosen ? chosen.key : '—'} busy={busy}
        aria={d.incoterm_label} face={{ fontSize: 13, color: 'var(--fg-1)' }}
        missing={key === ''}
        options={[{ value: '', label: '—' },
                  ...(d.incoterms ?? []).map((t) => ({
                    value: t.key, label: `${t.key} · ${t.label}` }))]}
        onChange={setKey} />
      {key !== '' && (
        <Editable as="div" missing={place.trim() === ''}>
          <input value={place} disabled={busy}
            placeholder={d.incoterm_place_label} aria-label={d.incoterm_place_label}
            onChange={(e) => setPlace(e.target.value)}
            onBlur={now}
            onKeyDown={(e) => { if (e.key === 'Enter') now(); }}
            style={{ ...DOC_FIELD, fontSize: 13, width: '100%' }} />
        </Editable>
      )}
      {/* ►►► **Die Erklärung steht SICHTBAR, nicht im Hover.** ◄◄◄ Es ist die Stelle im
          ganzen Beleg, an der ein Kürzel über Tausende entscheidet – und wer nicht weiss,
          dass er fragen müsste, findet keinen Hover. */}
      {chosen?.hint && (
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)' }}>{chosen.hint}</span>
      )}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Die Rückläufe
// ───────────────────────────────────────────────────────────────────────────────

/**
 * **Der Angebotsspiegel** – wir fragen an bzw. bieten an, sie nennen ihren Preis oder
 * sagen ab, wir geben den Zuschlag.
 *
 * **Zusammengeklappt wird erst NACH dem Zuschlag**: solange verhandelt wird, versteckt der
 * Beleg nichts; danach sind die unterlegenen Zeilen der **Nachweis**, warum so entschieden
 * wurde – und der gehört auf Klick, nicht auf den Bildschirm.
 */
function Quotes({ d, busy, active, onAsk, onAction }: {
  d: Filled; busy: boolean; active: boolean; onAsk: Ask; onAction: Send;
}) {
  const open = d.stage === DEAL_STAGE.offer;
  const [shown, setShown] = useState(false);
  const chosen = d.quotes.find((q) => q.state === QUOTE_STATE.chosen);
  const rest = d.quotes.filter((q) => q.state !== QUOTE_STATE.chosen);

  if (!d.quotes.length && !may(d, 'ask')) return null;
  // ►►► **Wann offeriert wurde, steht AM Abschnitt** (Testnotiz #968). ◄◄◄
  //
  // *«Kann hier noch eine kleine Info dazu, wann offeriert wurde – im Format ‹vor xx
  // Tagen offeriert›, und beim Hovern das genaue Datum und Uhrzeit.»*
  //
  // Es ist die Angabe, die bis hierher in der **Chronik** stand (#970): ein eigener
  // Abschnitt, der zwei Daten aufzählte, die beide woanders hingehören. Hier ist sie
  // eine Auskunft am Kopf – dort, wo man die Angebote ohnehin ansieht.
  //
  // **Die erste hinausgegangene Zeile ist die Aussage**: wer drei Parteien nacheinander
  // anfragt, hat trotzdem *einmal* offeriert; die einzelne Zeile sagt ihr eigenes Datum
  // an ihrem eigenen Ort.
  const first = d.quotes
    .map((q) => q.sent_at).filter((x): x is string => !!x).sort()[0];
  return (
    <ModuleSection title={d.quotes_title || 'Angebote'}
      state={open ? 'active' : 'past'}
      right={first && (
        <Note tip={formatWhen(first).title}>offeriert · {when(first)}</Note>
      )}>
      <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
        {open
          ? d.quotes.map((q) => (
            <QuoteRow key={q.id} d={q} voucher={d} busy={busy} onAction={onAction} />
          ))
          : (
            <>
              {chosen && (
                <QuoteRow d={chosen} voucher={d} busy={busy} onAction={onAction} />
              )}
              {rest.length > 0 && (
                <>
                  <button type="button"
                    className="inline-flex items-center self-start"
                    style={{ gap: 6, fontSize: 12, color: 'var(--fg-3)',
                             background: 'transparent', border: 0, cursor: 'pointer' }}
                    onClick={() => setShown((v) => !v)}>
                    <ChevronDown size={12} style={{
                      transform: shown ? 'rotate(180deg)' : undefined,
                      transition: 'transform .12s',
                    }} />
                    {d.quotes.length - rest.length} von {d.quotes.length} Angeboten gewählt
                  </button>
                  {shown && rest.map((q) => (
                    <QuoteRow key={q.id} d={q} voucher={d} busy={busy}
                      onAction={onAction} />
                  ))}
                </>
              )}
            </>
          )}
        {open && <Offer d={d} busy={busy} active={active} onAsk={onAsk} />}
      </div>
    </ModuleSection>
  );
}

/**
 * **Eine Angebotszeile** – wer, wie viel, welche Fristen, und was man damit tun kann.
 *
 * Sie ist zugleich der **Schalter für den Zuschlag** (#809): die Zeile IST die Wahl, kein
 * Häkchen daneben. Und **abgesagt ist abgesagt** (#811) – kein Preis, keine Frist mehr.
 */
function QuoteRow({ d, voucher: v, busy, onAction }: {
  d: VoucherQuoteOut; voucher: Filled; busy: boolean; onAction: Send;
}) {
  const look = quoteLook(d.state ?? QUOTE_STATE.asked);
  const declined = d.state === QUOTE_STATE.declined;
  const chosen = d.state === QUOTE_STATE.chosen;
  const dec = v.currency_decimals ?? 2;
  // **Offerieren darf, wer den Preis nennt** – und bei einer Einnahme nennen wir ihn
  // bereits in den Positionen; dort ist an dieser Zeile nichts einzutragen.
  const canQuote = may(v, 'quote') && !v.we_quote && !declined && !chosen;
  const canAgree = may(v, 'agree') && !declined && !chosen;
  const canDecline = may(v, 'decline') && !declined && !chosen;

  // **Welche Handlung diese Zeile weiterbringt** – eine Frage an die Daten, kein Rang, den
  // die Oberfläche vergibt: annehmen, sobald ein Preis dasteht; sonst ihn erfassen.
  const forward = canAgree && d.amount != null ? 'agree' : (canQuote ? 'quote' : null);

  const [amount, setAmount] = useState(d.amount ?? '');
  const [lead, setLead] = useState(d.lead_days == null ? '' : String(d.lead_days));
  const [pay, setPay] = useState(d.payment_days == null ? '' : String(d.payment_days));
  useEffect(() => { setAmount(d.amount ?? ''); }, [d.amount]);
  useEffect(() => { setLead(d.lead_days == null ? '' : String(d.lead_days)); },
    [d.lead_days]);
  useEffect(() => { setPay(d.payment_days == null ? '' : String(d.payment_days)); },
    [d.payment_days]);

  // **Je Handlung EIN Aufruf** – derselbe Knopf steht je nach Lage als Fläche oder als
  // Quadrat da, und zwei Fassungen desselben Befehls liefen beim nächsten Feld auseinander.
  const sendQuote = () => void onAction({
    action: 'quote', party: d.party_object_id, amount,
    ...(pay === '' ? {} : { payment_days: Number(pay) }),
    ...(lead === '' ? {} : { lead_days: Number(lead) }),
  });
  const sendAgree = () => void onAction({ action: 'agree', party: d.party_object_id });
  const sendDecline = () => void onAction({ action: 'decline', party: d.party_object_id });

  return (
    // ►►► **Die Haarlinie schliesst den Container, sie eröffnet ihn nicht** (#955). ◄◄◄
    // *«Der obere Strich in diesem Container ist irgendwie unnötig bzw. macht optisch
    // keinen Sinn – ich würde ihn pro Container unten setzen.»* – Und er war zugleich die
    // **zweite** Linie direkt unter der Trennlinie des Abschnitts.
    // ►►► **Und die Zeile ist kompakter** (#954): weniger Polsterung, weniger Abstand.
    <div className="flex flex-col" style={{
      gap: 6, padding: '0 0 7px', borderBottom: '1px solid var(--border-1)', minWidth: 0,
    }}>
      <div className="flex flex-wrap items-baseline" style={{ gap: '4px 10px', minWidth: 0 }}>
        <span aria-hidden className="rounded-full" style={{
          width: 6, height: 6, flex: 'none', background: look.color,
          alignSelf: 'center',
        }} />
        {/* ►►► **Nummer neben dem Namen — als EINE Gruppe** (Testnotiz #953). ◄◄◄ Beide
            benennen **einen** Datensatz; als Geschwister in einer umbrechenden Zeile
            rutschte die Nummer auf die nächste, sobald es eng wurde. Gekappt wird der
            Name, nie die Kennung (#853). */}
        <span className="flex items-baseline"
          style={{ gap: 8, flex: `1 1 ${NAME_MIN}px`, minWidth: 0 }}>
          <span className="truncate" style={{ fontSize: 13, minWidth: 0 }}>
            {d.party_name || d.party_object_id}
          </span>
          <span style={{ flex: 'none' }}><ObjId value={d.party_object_id} /></span>
        </span>
        {/* ►►► **Wann diese Zeile den Zuschlag bekam – NEBEN dem Betrag** (#969/#978).◄◄◄
            *«Kann das nicht irgendwo neben dem Betrag oder so stehen – und den Hovertext
            direkt darüber und nicht wie jetzt irgendwo.»*
            Beides hat **eine** Ursache: die Zeile stand als eigenes Kind der Spalte, und
            ein Kind einer Flex-Spalte wird auf die volle Breite gezogen. Die Blase sitzt
            über der **Mitte ihres Elements** – bei einer 460 px breiten Zeile also weit
            weg von den drei Wörtern, die sie erklärt. In der Kopfzeile ist die Angabe so
            breit wie ihr Text, und die Blase steht damit **konstruktiv** darüber. */}
        {chosen && d.agreed_at && (
          <Note tip={formatWhen(d.agreed_at).title}>angenommen · {when(d.agreed_at)}</Note>
        )}
        {d.amount != null && !declined && (
          <span style={{ font: '600 13px var(--font-body)',
                         fontVariantNumeric: 'tabular-nums' }}>
            {formatAmount(d.amount, dec)} {v.currency}
          </span>
        )}
      </div>
      {/* **Wie man bei ihm bestellt** – seine Artikelnummer, sein Shop-Link. Es gibt sie
          nur, wo wir bestellen; *was* zu tun ist, steht einmal am Beleg (`Task`). */}
      {d.ref && (
        <Note tip={v.order_label} icon={ClipboardList}>{d.ref}</Note>
      )}
      {canQuote && (
        <div className="flex flex-wrap items-end" style={{ gap: 10, minWidth: 0 }}>
          <Editable as="div" missing={amount.trim() === ''}>
            <input {...numericInputProps} value={amount} disabled={busy}
              onChange={(e) => setAmount(numericOnly(e.target.value))}
              aria-label="Betrag"
              style={{ ...DOC_FIELD, width: 110, textAlign: 'right', fontSize: 13,
                       fontVariantNumeric: 'tabular-nums' }} />
          </Editable>
          {/* **Dieselbe Frist-Form wie im Beleg** – zwei Bauarten für dieselbe Frage
              liefen beim nächsten üblichen Wert auseinander, und die Zeile des Partners
              ist derselbe Beleg, nur seine Seite davon. */}
          <Term label={v.payment_term_label} on busy={busy} value={pay} days={null}
            terms={v.payment_terms ?? []} onChange={setPay}
            freeMin={v.term_free_min ?? 1}
            freeLabel={v.term_free_label ?? 'Individuell'} />
          <Term label={v.lead_term_label} on busy={busy} value={lead} days={null}
            terms={v.lead_terms ?? []} onChange={setLead}
            freeMin={v.term_free_min ?? 1}
            freeLabel={v.term_free_label ?? 'Individuell'} />
        </div>
      )}
      {/* ►►► **Die Handlung, die weiterbringt – und daneben die leise Absage** (#976).◄◄◄
          *«Kann man diesen Bereich ähnlich darstellen wie ‹Vorgang abschliessen› und
          daneben das unscheinbarere Abbrechen?»* – Ja, und es ist **dieselbe** Zeile
          (`StageRow`), die die Karte ganz unten trägt: der Zuschlag ist für diese Zeile,
          was der Abschluss für das Modul ist. Drei gleich laute Knöpfe sind kein
          Vorschlag.
          **Welche die dominante ist, sagen die Daten**: annehmen, sobald ein Preis
          dasteht – sonst ihn erfassen. Eine Offerte zu **korrigieren**, während man sie
          annehmen könnte, ist der Nebenweg und steht als Quadrat daneben. */}
      <StageRow aside={(
        <>
          {canQuote && forward !== 'quote' && (
            <ActionButton icon={Send} label={QUOTE_VERB} tone="primary" height={ACT_H.stage} square
              disabled={busy || amount.trim() === ''} onClick={sendQuote} />
          )}
          {canDecline && (
            // ►►► **«Absage» – und sonst nichts** (Testnotiz #965). ◄◄◄ *«Hier soll
            // einfach nur ‹Absage› stehen und nicht ‹liefert nicht›.»* Der Zusatz stammte
            // aus dem Beschaffungs-Beleg, wo nur eingekauft wurde; an einer **Einnahme**
            // sagt er sogar das Falsche – dort liefern wir, und abgesagt hat der Kunde.
            <ActionButton icon={CircleSlash} label="Absage" tone="danger" height={ACT_H.stage}
              square disabled={busy} onClick={sendDecline} />
          )}
        </>
      )}>
        {forward === 'quote' && (
          <StageAction icon={Send} label={QUOTE_VERB}
            disabled={busy || amount.trim() === ''} onClick={sendQuote} />
        )}
        {forward === 'agree' && (
          // **Das Verb kommt vom Server** (`stages[0].verb`) – es ist das Wort der
          // Schwelle und lautet in beiden Richtungen gleich (#966: «Offerte annehmen»).
          <StageAction icon={Check} label={v.stages[0]?.verb ?? 'Offerte annehmen'}
            disabled={busy} onClick={sendAgree} />
        )}
      </StageRow>
    </div>
  );
}

/**
 * ►►► **Anbieten bzw. anfragen — und der Knopf sieht aus wie der am Ende** (#923). ◄◄◄
 *
 * Die Zahl im Wort ist die der Gegenparteien, die noch nichts bekommen haben; sie fällt
 * weg, wenn es nur eine gibt – dann ist die Wahl keine (#793).
 */
function Offer({ d, busy, active, onAsk }: {
  d: Filled; busy: boolean; active: boolean; onAsk: Ask;
}) {
  const allowed = d.allowed ?? [];
  const known = d.quotes.map((q) => q.party_object_id);
  const fresh = allowed.filter((p) => !known.includes(p.object_id));
  const canAsk = may(d, 'ask') && active;
  if (!canAsk || (allowed.length > 0 && fresh.length === 0)) return null;

  const label = allowed.length > 1
    ? `${d.ask_verb} (${fresh.length})`
    : d.ask_verb;
  return (
    <StageAction icon={Send} label={label} disabled={busy}
      tip={allowed.length === 0
        ? `Wähle oben den ${d.party_word}` : undefined}
      onClick={() => onAsk(fresh.map((p) => p.object_id))} />
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Rechnung & Zahlung
// ───────────────────────────────────────────────────────────────────────────────

const WAIT_TRIES = 10;
const WAIT_STEP = 1500;

/**
 * ►►► **ZWEI FÄCHER, EINE HANDLUNG, EINE WAHL** — der Umbau von «Rechnung & Zahlung». ◄◄◄
 *
 * *«Zu komplex, zu unstrukturiert, zu wirr, zu viele Optionen, die sich gegeneinander
 * stören, kannibalisieren.»*
 *
 * Gezählt, nicht vermutet: an einer Rechnung standen bis zu **sechs** gleich aussehende
 * Knöpfe, und sie bedeuteten **drei** verschiedene Dinge – eine Buchung («Rechnung
 * erfassen»), eine Korrektur («Stornieren») und eine blosse **Auskunft** («Überweisen»
 * zeigt IBAN und QR und bucht gar nichts). Dazu standen **zwei Rollen** in einer Zeile:
 * «Rechnung erfassen» ist unsere Handlung, «Jetzt bezahlen» die des Zahlenden – jeder sah
 * Knöpfe, die ihm nicht gehören. Und einen **Fortschritt** gab es nicht, obwohl es drei
 * klare Zustände gibt (nichts gefordert → gefordert → bezahlt).
 *
 * Drei Regeln räumen das auf:
 *
 * **(1) Zwei Fächer statt einer Knopfreihe.** Es sind nur zwei Fragen, und jede gehört
 * genau einer Seite: **Fordern** – *was schuldet uns jemand?* (uns: stellen, stornieren,
 * gutschreiben) – und **Begleichen** – *wie kommt das Geld hierher?* (dem Zahlenden: bar,
 * Überweisung, Karte). Beide sind ein ganz gewöhnlicher `ModuleSection` und tragen damit
 * denselben Fortschritts-Punkt wie jeder andere Abschnitt des Belegs. Dazwischen die
 * Zeile «Offen».
 *
 * **(2) Genau eine Handlung bringt weiter** – unten, breit, als `StageAction`: *Rechnung
 * stellen* → *Zahlung erfassen* → nichts mehr. Alles andere ist eine **Korrektur** und
 * steht klein bei der Zeile, die sie korrigiert; nie im selben Rang.
 *
 * **(3) Der Weg zum Geld ist eine Wahl, kein Verb** – ein Schieber statt dreier Knöpfe.
 * Was dahinter passiert, ist verschieden (buchen ↔ Angaben zeigen ↔ Zahlformular öffnen),
 * die **Frage** ist dieselbe. Welche Antworten es gibt, sagt der Server (`ways`) – aus
 * `can`, der Liste, die ohnehin Auskunft **und** Tor ist.
 *
 * **Und alles hängt weiter an `can`, nicht an «ist dran»**: ein Zahlungsziel läuft weiter,
 * wenn die Ware längst draussen ist. Eine erfundene Sperre hätte keinen Schlüssel –
 * dieselbe Fehlerform wie damals bei «nicht bestanden».
 */
function Money({ d, busy, orderObjectId, stepId, onAction, onPaid }: {
  d: Filled; busy: boolean; orderObjectId: number; stepId: number;
  onAction: Send; onPaid: () => void;
}) {
  const [form, setForm] = useState<{ kind: 'charge' | 'pay'; preset: string;
                                     method?: string } | null>(null);
  const [card, setCard] = useState(false);
  // **Die gewählte Antwort ist eine ABLEITUNG, kein zweiter Zustand**: fällt der Weg weg
  // (eine Rechnung ist bezahlt, ein Dienst nicht mehr eingerichtet), steht sie auf dem
  // ersten, den es noch gibt. Ein Zustand, der nachgezogen werden muss, wäre ein Effekt
  // und die Stelle, an der ein Knopf auf einen Weg zeigt, den der Server nicht mehr führt.
  const [picked, setPicked] = useState<string | null>(null);
  const ways = d.ways ?? [];
  const way = ways.find((w) => w.key === picked) ?? ways[0] ?? null;
  const dec = d.currency_decimals ?? 2;
  const code = d.currency;

  // **Angezeigt wird sofort, gebucht weiterhin vom Webhook** (#857): nachgefragt wird,
  // bis sich die Summe der Zahlungen ändert – höchstens zehnmal. Kein zweiter Kanal für
  // ein Ereignis, das einmal je Zahlung eintrifft.
  const [waiting, setWaiting] = useState(0);
  const paid = d.paid ?? '';
  useEffect(() => {
    if (waiting === 0) return;
    const t = setTimeout(() => { onPaid(); setWaiting((n) => n - 1); }, WAIT_STEP);
    return () => clearTimeout(t);
  }, [waiting, onPaid]);
  useEffect(() => { setWaiting(0); }, [paid]);

  const charges = d.entries.filter((e) => e.kind === 'charge');
  const payments = d.entries.filter((e) => e.kind === 'payment');
  const settle = d.settle_charge ?? null;
  const canCharge = may(d, 'charge') && !d.credit_only;

  // ►►► **Genau EINE Handlung bringt weiter** (Regel 2) – und welche, sagen die Daten:
  // erst fordern, dann kassieren. Alles andere ist eine Korrektur und steht bei ihrer
  // Zeile. Ein Rang, den die Oberfläche selbst vergäbe, wäre die zweite Regel neben `can`.
  const forward = canCharge
    ? { icon: FileText, label: d.charge_word,
        run: () => setForm({ kind: 'charge', preset: d.next_charge ?? '' }) }
    : way?.action === 'pay' && way.verb
      ? { icon: Wallet, label: way.verb,
          run: () => setForm({ kind: 'pay', preset: d.next_payment ?? '',
                               method: way.key }) }
      : way?.action === 'pay_online'
        ? { icon: CreditCard, label: way.verb ?? d.pay_online_word,
            run: () => setCard(true) }
        : null;

  return (
    <>
      {/* ►►► **Fach 1 — was schuldet uns jemand?** ◄◄◄ Es gehört uns: stellen,
          stornieren, gutschreiben. Der Punkt sagt, wo man steht – *aktiv*, solange nichts
          gefordert ist, *vorbei*, sobald die Forderung dasteht. */}
      <ModuleSection title={d.claim_title || 'Fordern'}
        state={charges.length ? 'past' : 'active'}>
        <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
          {charges.length === 0 && (
            <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>Nichts berechnet</span>
          )}
          {charges.map((e) => (
            <EntryRow key={e.id} d={d} e={e} busy={busy} onAction={onAction}
              orderObjectId={orderObjectId} stepId={stepId} onPaid={onPaid} />
          ))}
        </div>
      </ModuleSection>

      {/* ►►► **Fach 2 — wie kommt das Geld hierher?** ◄◄◄ Es gehört dem Zahlenden. Der
          Weg ist eine **Wahl** (Regel 3), und was er zeigt, sagt er selbst: eine Auskunft
          (Einzahlungsschein) oder ein Formular (Karte). Bei genau einer Antwort gibt es
          nichts zu wählen – dann steht der Schieber nicht da (dieselbe Regel wie #793). */}
      <ModuleSection title={d.settle_title || 'Begleichen'}
        state={!charges.length ? 'ahead' : (settle == null ? 'past' : 'active')}>
        <div className="flex flex-col" style={{ gap: 10, minWidth: 0 }}>
          {ways.length === 0 && payments.length === 0 && (
            <span style={{ fontSize: 12.5, color: 'var(--fg-3)' }}>
              {charges.length ? 'Nichts mehr offen' : 'Noch nichts zu begleichen'}
            </span>
          )}
          {ways.length > 1 && way && (
            <Segmented label={d.method_label} value={way.key}
              onChange={(v) => { setPicked(v); setCard(false); }}
              options={ways.map((w) => ({ value: w.key, label: w.label }))} />
          )}
          {/* **Die Auskunft kommt mit dem Weg** – nicht aus einem Vergleich auf
              «transfer»: ein Schlüssel-Vergleich hier wäre der Spiegel über die
              API-Grenze, der beim nächsten Weg still falsch wird. */}
          {way?.info && settle != null && (
            <Transfer orderObjectId={orderObjectId} stepId={stepId} entryId={settle} />
          )}
          {card && settle != null && (
            <PayOnline orderObjectId={orderObjectId} stepId={stepId} chargeId={settle}
              prepare={api.prepareVoucherPayment} label={d.pay_online_word}
              onDone={() => { setCard(false); setWaiting(WAIT_TRIES); onPaid(); }}
              onClose={() => setCard(false)} />
          )}
          {/* ►►► **Die Zahlungen stehen im Fach, in das sie gehören.** ◄◄◄ Bis #861
              standen sie eingerückt unter ihrer Rechnung – die Antwort auf «welche
              Zahlung gehört zu welcher?» in einer flachen Gesamtliste. Sie steht jetzt
              **an der Rechnung selbst**: deren Zeile sagt, wie viel von *ihr* offen ist
              (`state_label` vom Server) – eine Aussage statt einer Gruppierung. Und je
              Modul lebt ohnehin höchstens **eine** offene Forderung (#866). */}
          {payments.map((p) => (
            <EntryRow key={p.id} d={d} e={p} busy={busy} onAction={onAction}
              orderObjectId={orderObjectId} stepId={stepId} onPaid={onPaid} />
          ))}
        </div>
      </ModuleSection>

      {/* **Die Zeile «Offen» verbindet die beiden Fächer** – das Ergebnis von *gefordert
          minus beglichen*, und die einzige Zahl, die man abschreibt. */}
      {d.open != null && charges.length > 0 && (
        <div className="flex items-baseline" style={{
          gap: 10, marginTop: 14, paddingTop: 8, borderTop: '1px solid var(--border-1)',
        }}>
          <span style={{ ...MICRO_LABEL, flex: 1 }}>{d.open_word}</span>
          <span style={{ font: '700 14px var(--font-body)',
                         fontVariantNumeric: 'tabular-nums',
                         color: Number(d.open) > 0 ? 'var(--fg-1)' : 'var(--ok)' }}>
            {formatAmount(d.open, dec)}
          </span>
          <span style={{ font: '600 13px var(--font-body)', color: 'var(--fg-2)' }}>
            {code}
          </span>
        </div>
      )}

      {/* **Das Formular tritt an die Stelle des Knopfes** – zwei Handlungen gleichzeitig
          anzubieten wäre wieder die Reihe, die diese Runde abbaut. */}
      {form ? (
        <div style={{ marginTop: 12 }}>
          <Entry kind={form.kind} d={d} busy={busy} preset={form.preset}
            method={form.method ?? null} chargeId={settle}
            onCancel={() => setForm(null)}
            onSubmit={(body) => { setForm(null); void onAction(body); }} />
        </div>
      ) : forward && (
        <div style={{ marginTop: 12 }}>
          <StageAction icon={forward.icon} label={forward.label} disabled={busy}
            onClick={forward.run} />
        </div>
      )}
    </>
  );
}

/**
 * **Eine Geld-Zeile** – Nummer, Datum als Aussage, Betrag, Zustand und was man tun kann.
 *
 * ►►► **EIN Datum je Zeile** (#890). ◄◄◄ «6.9.2026 · fällig 6.9.2026» waren zwei Zahlen,
 * die man vergleichen muss, um die eine Aussage zu bekommen. Hier steht «fällig in 30
 * Tagen» bzw. «überfällig seit 17 Tagen»; die beiden Daten stehen im Hover.
 *
 * ►►► **Und hier stehen nur noch KORREKTUREN** (Regel 2). ◄◄◄ Bezahlen, überweisen und
 * online bezahlen sind Wege zum Geld und stehen im Fach «Begleichen» – als **eine** Wahl,
 * nicht als drei Knöpfe, die neben einem Storno im selben Rang stehen. Was bleibt, ist
 * das, was *diese* Zeile korrigiert: die Gegenbuchung an einer Rechnung, die zweite
 * Zahlung an einer Zahlung.
 */
function EntryRow({ d, e, busy, onAction, orderObjectId, stepId, onPaid }: {
  d: Filled; e: Filled['entries'][number]; busy: boolean;
  onAction: Send;
  orderObjectId: number; stepId: number; onPaid: () => void;
}) {
  const dec = d.currency_decimals ?? 2;
  const charge = e.kind === 'charge';
  // ►►► **Der Zustand kommt vom Server** (Testnotiz #991) – Wort und Ampelton
  // (`domain/voucher.charge_state`). Hier gerechnet wäre er die zweite Ableitung
  // derselben Zahlen, und die erste, die eine Rundungstoleranz vergisst.
  const state = e.state_label
    ? { label: e.state_label, color: TONE[e.state_tone as keyof typeof TONE]?.color
                                     ?? 'var(--fg-4)' }
    : null;
  // **EIN Datum je Zeile** (#890) – die Aussage steht da, die beiden Tatsachen im Hover.
  const stamp = charge && e.due_on
    ? { text: `fällig ${when(e.due_on).toLowerCase()}`,
        tip: `Rechnung ${day(e.booked_on)} · fällig ${day(e.due_on)}` }
    : { text: day(e.booked_on), tip: e.service_date
        ? `${d.service_date_label} ${day(e.service_date)}` : '' };

  return (
    <Row style={{ gap: 4, opacity: e.reversed ? 0.55 : 1 }}>
      <div className="flex flex-wrap items-baseline" style={{ gap: '3px 10px', minWidth: 0 }}>
        {state && (
          <span aria-hidden className="rounded-full" style={{
            width: 6, height: 6, flex: 'none', background: state.color,
            alignSelf: 'center',
          }} />
        )}
        {/* ►►► **Eine Zahlung beginnt mit ihrer ART** (Testnotiz #994). ◄◄◄ *«Im
            Abschnitt ‹Begleichen› soll jede Zahlungszeile mit der Zahlungsart beginnen,
            danach Betrag, Datum.»* – Das ist die Angabe, nach der man eine Zahlung
            wiedererkennt («die Karte», «die Überweisung»); die Referenz sagt sie nicht,
            und bei einer Barzahlung gibt es gar keine. Sie stand darum in der zweiten
            Zeile hinter dem Zustand – und die gibt es für eine Zahlung nicht mehr, seit
            der Zustand der **Rechnung** gehört (#988). */}
        <span className="truncate" style={{ fontSize: 12.5, color: 'var(--fg-2)',
                                            flex: '1 1 96px', minWidth: 0 }}>
          {(charge ? null : e.method_label) || e.reference
            || (charge ? 'Rechnung' : 'Zahlung')}
        </span>
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)', flex: 'none',
                       fontVariantNumeric: 'tabular-nums' }}
          {...(stamp.tip ? { 'data-tip': stamp.tip } : {})}>{stamp.text}</span>
        <span style={{ font: '600 13px var(--font-body)', flex: 'none',
                       fontVariantNumeric: 'tabular-nums',
                       color: Number(e.amount) < 0 ? 'var(--fg-3)' : 'var(--fg-1)' }}>
          {formatAmount(e.amount, dec)} {d.currency}
        </span>
        {/* ►►► **Die Korrekturen stehen AM Zeilenende** (#989/#993). ◄◄◄ Als
            freistehende Knöpfe unter der Zeile standen sie im selben Rang wie eine
            Buchung – und bei drei Zeilen dreimal. */}
        <RowActions>
          {charge && !e.reversed && may(d, 'reverse') && (
            <ConfirmButton icon={RotateCcw} label={e.reverse_word ?? 'Stornieren'}
              disabled={busy}
              tip="Eine Gegenbuchung – der Beleg bleibt stehen, er fordert nur nichts mehr."
              onConfirm={() => void onAction({ action: 'reverse', entry: e.id })} />
          )}
          {e.refundable && (
            <ConfirmButton icon={Undo2} label={d.refund_online_word ?? 'Online erstatten'}
              disabled={busy}
              onConfirm={() => void api.refundVoucherPayment(orderObjectId, stepId, e.id)
                .then(onPaid).catch(() => {})} />
          )}
          {!charge && may(d, 'pay') && (
            <ActionButton icon={Plus} label="Korrigieren" disabled={busy}
              tip="Eine zweite Zahlung mit dem negativen Betrag – ein Ereignis der
                   Aussenwelt macht man nicht ungeschehen."
              onClick={() => void onAction({
                action: 'pay', amount: negate(e.amount), charge_id: e.charge_id ?? null,
              })} />
          )}
        </RowActions>
      </div>
      {/* ►►► **Das Wort «Offen» steht NICHT zweimal** (Testnotiz #988). ◄◄◄ Der Zustand
          stand hier als zweite Zeile – und der Punkt eine Zeile höher sagt ihn bereits;
          «Offen» stand dazu ein drittes Mal in der Brücke zwischen den beiden Fächern,
          wo es die Zahl trägt. Was hier bleibt, ist nur, was **nur hier** steht. */}
      {(e.note || (charge && e.method_label)) && (
        <span className="flex items-center truncate"
          style={{ gap: 8, fontSize: 11.5, color: 'var(--fg-3)' }}>
          {charge && e.method_label && <span>{e.method_label}</span>}
          {e.note && <span className="truncate">{e.note}</span>}
        </span>
      )}
    </Row>
  );
}

/**
 * **Wie man diese Rechnung überweist** – Bankverbindung, Referenz und, wo er gilt, die
 * Swiss QR-Rechnung. Eine Auskunft, keine Buchung – erst auf Klick.
 */
function Transfer({ orderObjectId, stepId, entryId }: {
  orderObjectId: number; stepId: number; entryId: number;
}) {
  const [info, setInfo] = useState<TransferInfo | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let stale = false;
    void api.voucherTransfer(orderObjectId, stepId, entryId)
      .then((r) => { if (!stale) setInfo(r); })
      .catch(() => { if (!stale) setFailed(true); });
    return () => { stale = true; };
  }, [orderObjectId, stepId, entryId]);

  if (failed) {
    return <span style={{ fontSize: 12, color: 'var(--danger)' }}>
      Die Angaben zur Überweisung sind gerade nicht abrufbar.
    </span>;
  }
  if (!info) {
    return <span className="flex items-center" style={{ gap: 6, fontSize: 12,
                                                        color: 'var(--fg-3)' }}>
      <Loader2 size={12} className="animate-spin" /> Einen Moment …
    </span>;
  }
  return (
    <div className="flex flex-wrap" style={{
      gap: 14, padding: 11, borderRadius: 'var(--r-md)',
      border: '1px solid var(--border-1)', minWidth: 0,
    }}>
      <div className="flex flex-col" style={{ gap: 4, flex: '1 1 200px', minWidth: 0 }}>
        <Fixed label="Empfänger" value={info.creditor ?? ''} />
        <Fixed label="IBAN" value={info.iban ?? '—'} />
        {/* ►►► **Die Referenz sagt, WOHER sie kommt** (Testnotiz #871). ◄◄◄ Der Hinweis
            nannte nur die Norm – und «ISO 11649» ohne Bezug ist genau die Auskunft, aus
            der die Rückfrage entstand. Er nennt darum die **Rechnungsnummer**, aus der
            sie abgeleitet ist (ohne Trennstrich: die Norm kennt nur Buchstaben und
            Ziffern). */}
        <Fixed label="Referenz" value={info.reference ?? '—'}
          hint={`Aus der Rechnungsnummer ${info.invoice} abgeleitet (ISO 11649)`} />
        <Fixed label="Betrag" value={`${info.amount ?? ''} ${info.currency ?? ''}`} />
      </div>
      {info.qr ? (
        <div style={{ flex: '0 0 168px', width: 168 }}
          dangerouslySetInnerHTML={{ __html: info.qr }} />
      ) : (
        <span style={{ fontSize: 11.5, color: 'var(--fg-3)', flex: '1 1 160px' }}>
          {info.problem}
        </span>
      )}
    </div>
  );
}

/**
 * **Eine Geld-Zeile erfassen** – Betrag, und was sonst noch niemand gesagt hat.
 *
 * Die Vorgabe kommt vom Server (`next_charge` ↔ `next_payment`) und ist **nie negativ**:
 * überberechnet ist eine gültige Aussage, aber kein Vorschlag in einem Eingabefeld.
 *
 * ►►► **Die Zahlungsart fragt es NICHT mehr** (Regel 3). ◄◄◄ Sie ist die Wahl im Fach
 * «Begleichen» und damit längst getroffen, bevor dieses Formular aufgeht – ein zweites
 * Bedienelement dafür wäre die zweite Aussage über dieselbe Sache, und die getippte
 * gewänne auch dann, wenn sie der Wahl widerspricht. Der Schieber selbst ist geblieben,
 * er steht nur dort, wo die Frage entsteht (#967).
 *
 * **Und welche Rechnung gemeint ist, fragt es ebenso wenig** (#859/#866): je Modul lebt
 * höchstens eine offene, und der Server nennt sie (`settle_charge`).
 *
 * ►►► **Es ist EIN Formular, und es sieht aus wie jedes andere im Haus** (#987/#990).◄◄◄
 *
 * *«Beide Erfassungsformulare bitte auf den Standard der übrigen Module ziehen –
 * Feldhöhen, Spacing, Button-Hierarchie: eine Primäraktion, Abbrechen dezent.»*
 *
 * «Rechnung stellen» und «Zahlung erfassen» waren schon dieselbe Komponente; auseinander
 * lagen die **Masse**. Sie kommen jetzt aus den Bauteilen statt aus Zahlen an dieser
 * Stelle: `inputCls` als Feld (das Formularfeld des Hauses, unverändert), `FIELD_GAP`
 * zwischen zwei Feldern, **kein** eigener Abstand unter der Beschriftung (`Label` bringt
 * seine 4 px mit – der frühere `gap: 3` kam obendrauf), und die Fusszeile ist
 * **`StageRow`**: buchstäblich dieselbe Zeile wie der Abschluss der Karte und der
 * Zuschlag an einer Angebotszeile – **eine** Handlung nimmt die Breite, alles andere
 * steht als Quadrat daneben.
 *
 * Zwei gleich grosse Knöpfe nebeneinander sind keine Hierarchie, sondern eine Frage.
 */
function Entry({ kind, d, busy, preset, method, chargeId, onCancel, onSubmit }: {
  kind: 'charge' | 'pay'; d: Filled; busy: boolean; preset: string;
  /** Der im Fach «Begleichen» gewählte Weg – bei einer Forderung `null`. */
  method: string | null;
  chargeId: number | null;
  onCancel: () => void; onSubmit: (body: Action) => void;
}) {
  const [amount, setAmount] = useState(preset);
  const [reference, setReference] = useState('');
  const [vat, setVat] = useState(d.vat_rate ?? 'normal');
  // **Der Satz wird nur gefragt, wo es keine bepreisten Positionen gibt** – sonst kommt
  // die Aufteilung aus ihnen, und ein Feld daneben wäre eine zweite Aussage.
  const asksVat = kind === 'charge' && !d.we_quote;

  const book = () => onSubmit({
    action: kind, amount,
    ...(kind === 'pay' && method ? { method } : {}),
    ...(kind === 'pay' && chargeId != null ? { charge_id: chargeId } : {}),
    ...(asksVat ? { vat } : {}),
    ...(reference.trim() ? { reference: reference.trim() } : {}),
  });
  const ready = !busy && amount.trim() !== '';

  return (
    <div className="flex flex-col" style={{
      gap: 12, padding: 12, borderRadius: 'var(--r-md)',
      border: '1px solid var(--border-1)', minWidth: 0,
    }}>
      <div className="flex flex-wrap items-end" style={{ gap: FIELD_GAP, minWidth: 0 }}>
        <Ask label={kind === 'charge' ? d.charge_word : d.payment_word}>
          <input {...numericInputProps} value={amount} autoFocus
            onChange={(e) => setAmount(numericOnly(e.target.value, { signed: true }))}
            onKeyDown={(e) => { if (e.key === 'Enter' && ready) book(); }}
            className={inputCls} aria-label="Betrag"
            style={{ width: 120, textAlign: 'right',
                     fontVariantNumeric: 'tabular-nums' }} />
        </Ask>
        {asksVat && (
          <Ask label={d.vat_label}>
            <select className={inputCls} value={vat} aria-label={d.vat_label}
              onChange={(e) => setVat(e.target.value)}>
              {(d.vat_rates ?? []).map((v) => (
                <option key={v.key} value={v.key}>{v.label}</option>
              ))}
            </select>
          </Ask>
        )}
        {/* **Das Nummernfeld gibt es nur, wo die Nummer von AUSSEN kommt** – eine, die wir
            vergeben, tippt niemand ab. */}
        {d.ref_label && (
          <Ask label={d.ref_label} grow>
            <input value={reference} className={inputCls} aria-label={d.ref_label}
              onKeyDown={(e) => { if (e.key === 'Enter' && ready) book(); }}
              onChange={(e) => setReference(e.target.value)} />
          </Ask>
        )}
      </div>
      {/* **Eine Primäraktion, Abbrechen dezent** – dieselbe Zeile wie am Abschluss der
          Karte und am Zuschlag (#976). */}
      <StageRow aside={
        <ActionButton icon={X} label="Abbrechen" height={ACT_H.stage} square
          disabled={busy} onClick={onCancel} />
      }>
        <StageAction icon={Check} label="Buchen" disabled={!ready} onClick={book} />
      </StageRow>
    </div>
  );
}

/**
 * **Eine Frage im Formular** – Beschriftung über dem Feld, dieselbe Luft wie überall.
 *
 * Sie steht als Bauteil da und nicht dreimal als `<div className="flex flex-col"
 * style={{ gap: 3 }}>`: genau so laufen Masse auseinander, und genau das war #987/#990.
 */
function Ask({ label, grow, children }: {
  label?: string; grow?: boolean; children: ReactNode;
}) {
  return (
    // **Kein `gap` hier**: `Label` bringt seine eigenen 4 px mit (`fields.tsx`). Der
    // frühere `gap: 3` kam obendrauf – 7 px, und damit stand die Beschriftung an dieser
    // einen Stelle anders als überall sonst im Haus. Genau das war die Meldung.
    <div className="flex flex-col"
      style={{ minWidth: 0, ...(grow ? { flex: '1 1 160px' } : {}) }}>
      <Label>{label}</Label>
      {children}
    </div>
  );
}

// ───────────────────────────────────────────────────────────────────────────────
// Chronik und die Handlungen unter dem Strich
// ───────────────────────────────────────────────────────────────────────────────

/*
 * ►►► **Eine Chronik gibt es nicht mehr** (Testnotiz #970). ◄◄◄
 *
 * *«Die Chronik kann hier vollständig und gänzlich entfallen. Ich möchte die Information
 * dort darstellen, wo sie eigentlich angezeigt werden (wie bspw. die beiden zuvor
 * genannten Punkte).»*
 *
 * Sie zählte **zwei Daten** auf, und beide haben einen eigenen Ort: *wann offeriert
 * wurde* steht am Kopf der Angebote (#968), *wann zugesagt wurde* an der Zeile, bei der
 * zugesagt wurde (#969) – und *wann storniert wurde* im Belegkopf, neben der Belegart.
 * Ein Abschnitt, der dieselben Daten ein zweites Mal nennt, ist nicht der Nachweis,
 * sondern seine ärmere Kopie: nacktes Datum statt Aussage.
 *
 * Damit sind `Chronicle`, `VoucherEmbed.history_title` und `vo.HISTORY_TITLE` entfallen.
 */

/**
 * **Die Handlungen unter dem Strich** – wie die Unterschrift auf einem Beleg.
 *
 * Der **Zuschlag** steht an der Angebotszeile (dort wirkt er), der **Abschluss** und der
 * **Storno** hier: der eine bringt den Vorgang ans Ziel, der andere nimmt ihn zurück.
 *
 * ►►► **Und sie stehen NEBENEINANDER, in klarer Rangfolge** (Testnotiz #957). ◄◄◄
 *
 * *«Ich hätte gerne, dass es neben dem grossen Button ‹Vorgang abschliessen› platziert
 * wird, jedoch nur ein quadratischer Button mit Icon, sodass der Hauptfokus und der absolut
 * dominante Button immer noch ‹Vorgang abschliessen› ist.»*
 *
 * Also **eine** Zeile: der Abschluss nimmt den ganzen Platz (`flex: 1`), der Storno ein
 * Quadrat in derselben Höhe. Beim Zeigen klappt sein Name daneben auf – dieselbe Geste wie
 * jeder Symbol-Knopf im Haus (#900), und mehr braucht er nicht: dass er die Gegenhandlung
 * ist, sagt die Warnfarbe.
 *
 * **Wann es ihn gibt, sagt `can`** – und das ist die Antwort auf die Frage der Notiz, ob
 * ein Abbruch «zu jedem Schritt sauber etabliert» ist: beide Stufen führen `revoke`, und
 * solange **nichts hinausgegangen** ist, führt der Server ihn nicht (es gibt dann nichts
 * abzubrechen). Das Wort dazu kommt ebenfalls von dort (`undo`): im Angebot «Vorgang
 * abbrechen», ab der Zusage «Auftrag stornieren» – vor der Zusage gibt es keinen Auftrag,
 * den man stornieren könnte.
 */
function Footer({ d, busy, onAction, children }: {
  d: Filled; busy: boolean; onAction: Send; children?: ReactNode;
}) {
  if (!children && !d.undo) return null;
  return (
    <div style={{ marginTop: 18, paddingTop: 12, borderTop: '1px solid var(--border-1)' }}>
      <StageRow aside={d.undo && (
        <ActionButton icon={CircleSlash} label={d.undo} tone="danger"
          height={ACT_H.stage} square
          disabled={busy}
          tip="Der Beleg behält seinen Weg – ein Storno sagt nur, dass nichts mehr kommt."
          onClick={() => void onAction({ action: 'revoke' })} />
      )}>
        {children}
      </StageRow>
    </div>
  );
}
