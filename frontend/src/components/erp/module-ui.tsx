'use client';

import type { CSSProperties, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { MICRO_LABEL } from '@/components/erp/fields';

/**
 * ►►► **Die Bauteile, aus denen ein Prozessschrittmodul besteht.** ◄◄◄
 *
 * Das Zahlungsmodul ist das erste, das in dieser Sprache gebaut ist – **alle weiteren
 * folgen**. Damit sie es nicht ein zweites Mal erfinden müssen, steht hier, was ein Modul
 * *als Modul* ausmacht, und nicht, was ein Geldvorgang ist: die Fläche, der Kopf, ein
 * Abschnitt, die Meta-Zeile, die Leiste und die Stufen.
 *
 * Es ist bewusst **kein neues Design-System**: jede Zahl kommt aus
 * `styles/design-system/colors_and_type.css`, jede Regel steht schon in
 * `docs/design-system/README.md`. Neu ist nur, dass sie hier **einmal** angewendet sind
 * statt an jeder Aufrufstelle mit leicht anderen Werten – genau die Form, in der eine
 * Gestaltungsregel auseinanderläuft, ohne dass es jemandem auffällt (die Lehre aus
 * `MICRO_LABEL`).
 *
 * **Die Vorlage ist die Detail-Ansicht eines Datensatzes** (`fields.SPEC` am Artikel):
 * weisse Karte, Haarlinie, `--r-lg`, ein grosser Kopf mit getönter Marke, darunter stille
 * Abschnitte über einer Linie. Ein Modul ist ein Datensatz-artiges Ding in einer Spalte –
 * es soll aussehen wie das Haus, nicht wie ein Sonderfall.
 */

/**
 * **Die Fläche einer Modul-Karte.** Weiss, Haarlinie, ein leiser Schatten – dieselbe
 * Karte wie `SPEC.card`, nur mit der Polsterung einer schmalen Prozessspalte statt der
 * einer Detail-Ansicht.
 *
 * *Sie war einmal getönt (die Modulfarbe als Fläche).* Bei fünf Modulen untereinander
 * standen damit fünf farbige Blöcke in der Spalte, und die ERP-Regel des Hauses lautet
 * **Struktur vor Fläche**. Die Farbe lebt weiter – in der **Marke**, wo sie das Modul
 * benennt, statt es zu übertönen.
 */
export const MODULE_CARD: CSSProperties = {
  background: 'var(--bg-1)',
  border: '1px solid var(--border-1)',
  borderRadius: 'var(--r-lg)',
  boxShadow: 'var(--shadow-sm)',
  padding: '16px 18px',
};

/**
 * **Der Name des Moduls** – die eine laute Zeile der Karte, in der Display-Schrift des
 * Hauses (`SpecHead` eine Nummer kleiner, weil die Prozessspalte schmal ist).
 */
export const MODULE_TITLE: CSSProperties = {
  font: '800 16px var(--font-display)',
  letterSpacing: '-.01em',
  color: 'var(--fg-1)',
};

/**
 * **Die Höhen der Knöpfe eines Moduls** – an einer Stelle, nicht als `style={{height: 30}}`
 * an dreissig Aufrufstellen (dort standen 26, 30, 32 und 38 nebeneinander, ohne dass
 * jemand sagen konnte, warum).
 *
 * `row` sitzt in einer Tabellenzeile, `inline` in einer Handlungsleiste, `main` ist die
 * eine Handlung, die eine Karte abschliesst.
 */
export const ACT_H = { row: 26, inline: 30, main: 34 } as const;

/**
 * ►►► **Ein Knopf ist ein Symbol, und beim Zeigen steht sein Name da.** ◄◄◄
 *
 * Sieben Testnotizen sagen denselben Satz (#877/#878/#880/#887/#888/#895/#896):
 * *«kann man hier so einen Button machen wie bei der Auswahl der Module – also ein Icon
 * und beim Hover der Text dazu»*. Genau das ist dieses Bauteil, und es gibt es **einmal**:
 * ein Quadrat mit dem Zeichen, der Name in der Blase des Hauses, der Name im
 * `aria-label`. Vorher stand dieselbe Form an sieben Aufrufstellen ausgeschrieben – mit
 * Höhen, Ausprägungen und Hinweisen, die schon leicht auseinanderliefen.
 *
 * ►►► **Und er braucht PLATZ, sonst schwingt er — gemessen, nicht geschätzt.** ◄◄◄
 *
 * Ein erster Anlauf setzte die Geste in die dichte, **umbrechende** Geld-Zeile: der Knopf
 * wird breiter, die Zeile bricht neu um, der Zeiger fällt vom Knopf, er klappt ein, die
 * Zeile bricht zurück – gemessen **32 → 63 → 51 → 59 px** in 800 ms, mit kippendem
 * `:hover`. Ein Bedienelement, das unter dem Zeiger wegläuft, ist keines.
 *
 * Daraus wurde nicht «dann eben eine Blase» (so stand es eine Runde lang, und #900 hat es
 * zu Recht zurückgewiesen), sondern **`Actions`**: eine Zeile, die *nicht* umbricht.
 * Dort schiebt der Knopf beim Aufklappen nur seine Nachbarn zur Seite und bleibt selbst,
 * wo er ist.
 *
 * **Der Grund hängt an einer Hülle, nicht am Knopf**: `.ix-tuck` ist `overflow: hidden`
 * (sonst böte der eingeklappte Name seitwärts zu scrollen an), und das schneidet ein
 * `::after` weg – die Blase wäre unsichtbar (die Lehre aus #790).
 */
export function ActionButton({
  icon: Icon, label, tone = 'neutral', height = ACT_H.row, tip, disabled, onClick,
}: {
  icon: LucideIcon;
  /** Was der Knopf tut – das Wort, das beim Zeigen daneben aufklappt, und das `aria-label`. */
  label: string;
  tone?: 'primary' | 'neutral' | 'danger';
  height?: number;
  /**
   * Ein **Grund**, keine zweite Beschriftung – er steht als Blase an der Hülle. Meist der
   * Satz, warum es gerade nicht geht, oder was die Handlung nach sich zieht.
   */
  tip?: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  const button = (
    <button type="button" disabled={disabled} onClick={onClick}
      className={`erp-actbtn erp-actbtn-${tone} erp-actbtn-icon ix-tuck`}
      style={{ height }} aria-label={label}>
      <Icon size={13} />
      <span className="ix-tuck-name">{label}</span>
    </button>
  );
  return tip ? <span data-tip={tip} className="inline-flex">{button}</span> : button;
}

/**
 * **Die Zeile, in der Handlungs-Knöpfe stehen.** Sie bricht **nicht** um – genau daran
 * hing das Schwingen oben. Wer einen ausklappenden Knopf in eine umbrechende Zeile setzt,
 * bekommt ihn nicht ruhig.
 */
export function Actions({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <div className="ix-actions" style={style}>{children}</div>;
}

/**
 * ►►► **Wie weit ist ein Schritt?** ◄◄◄ `past` – vorbei · `active` – dran · `ahead` –
 * steht noch aus.
 *
 * **Bewusst nicht `done`/`open`.** Das sind die Wörter, mit denen ein *Modul* seine
 * eigenen Stufen benennt (`DEAL_STAGE.done`) bzw. mit denen eine Leiste sagt, welcher
 * Abschnitt gerade **offen** ist. Hier geht es um etwas Drittes: wie weit man ist. Ein
 * Wort, das in derselben Datei zwei Dinge meint, ist die Form, in der ein Vergleich still
 * falsch wird.
 */
export type StepState = 'past' | 'active' | 'ahead';

const STEP_COLOR: Record<StepState, string> = {
  past: 'var(--fg-2)',
  active: 'var(--accent)',
  ahead: 'var(--border-2)',
};

/**
 * **Ein Abschnitt einer Modul-Karte** – Versalien-Beschriftung über einer Haarlinie,
 * rechts Platz für das, was zum Abschnitt gehört (die Währung, eine Gegenhandlung).
 *
 * Bewusst **ohne** Symbol und ohne Display-Schrift: in einer Karte mit drei Abschnitten
 * wären drei getönte Quadrate und drei fette Überschriften lauter als der Inhalt. Der
 * grosse Kopf steht oben, hier gliedert es nur.
 *
 * ►►► **Der Verlauf steht AN den Abschnitten, nicht als Leiste darüber** (Testnotiz
 * #868). ◄◄◄
 *
 * *«Kann man diese Anzeige nicht vertikal machen und es so visuell etwas besser
 * strukturieren – mir passt das da oben nicht.»* – Hier stand eine waagrechte
 * Stufen-Leiste (`ModuleSteps`), die dieselben drei Wörter trug wie die drei Abschnitte
 * darunter. Seit es keine Reiter mehr gibt (#863) versteckte sie nichts mehr; sie sagte
 * nur noch, **wie weit** der Vorgang ist – und dafür braucht es keine zweite Zeile mit
 * denselben Namen.
 *
 * **Die Abschnitte SIND die vertikale Fassung.** Sie stehen ohnehin untereinander, in
 * derselben Reihenfolge; ihnen einen **Punkt** voranzustellen (Punkt + Wort, die Anatomie
 * jedes Status im Haus) sagt dasselbe an der Stelle, an der man es liest. Ein Wort weniger
 * doppelt, eine Zeile weniger Fläche.
 */
export function ModuleSection({ title, state, right, children, first }: {
  /**
   * **Leer heisst: kein Kopf.** Sagt der Name nichts, was der Inhalt nicht schon sagt,
   * ist eine Überschrift Fläche.
   */
  title?: string;
  /** Wie weit dieser Abschnitt ist – Punkt vor der Beschriftung. Ohne Angabe: kein Punkt. */
  state?: StepState;
  right?: ReactNode;
  /** Der erste Abschnitt schliesst direkt an die Kopf-Linie an. */
  first?: boolean;
  children: ReactNode;
}) {
  return (
    <section style={{ marginTop: first ? 0 : 18, minWidth: 0 }}>
      {(title || right) && (
        <div className="flex items-center gap-2" style={{
          paddingBottom: 8, marginBottom: 12, borderBottom: '1px solid var(--border-1)',
        }}>
          {/* ►►► **Die Status-Spalte steht immer, auch leer.** ◄◄◄
              Ein Punkt vor der Beschriftung rückt sie um seine Breite ein – und in einer
              Karte, in der nur *manche* Abschnitte ein Schritt sind (die übrigen sind
              Inhalt), stünden die Überschriften dann auf zwei verschiedenen Kanten.
              Gemessen: 18 px ↔ 33 px im selben Beleg. Der Platz wird darum reserviert;
              was ihn füllt, sagt der Abschnitt. */}
          <span aria-hidden className="rounded-full" style={{
            width: 7, height: 7, flex: 'none',
            background: state ? STEP_COLOR[state] : 'transparent',
          }} />
          <span style={{
            ...MICRO_LABEL, flex: 1, minWidth: 0,
            // **Wo man steht, ist die lauteste Zeile** – dieselbe Geste wie in der
            // Bestandsleiste: der offene Ausschnitt tritt hervor, die übrigen bleiben da.
            color: state === 'active' ? 'var(--fg-1)' : undefined,
          }}>{title}</span>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

/*
 * ►►► **`ModuleMeta` ist entfallen** (Testnotiz #918). ◄◄◄
 *
 * Sie war die leise Zeile unter dem Kopf – «was über den ganzen Vorgang gilt und in
 * keinen Abschnitt gehört». Zuletzt trug sie genau **eine** Angabe, das Zusagedatum; und
 * seit der Abschnitt darunter eine **Chronik** ist («wann wurde offeriert, wann wurde
 * angenommen»), stand sie dort zum zweiten Mal. Ein bestehender Wächter hat es gemeldet,
 * kaum dass die Chronik stand.
 *
 * Damit hatte sie **keinen Leser mehr**. Ein Bauteil des Design-Systems ohne Aufrufer ist
 * genau das, was beim nächsten Umbau still abweicht – und ein neues Modul, das eine
 * solche Zeile braucht, schreibt drei Zeilen Flexbox, statt eine Vorlage zu erben, deren
 * Masse niemand mehr geprüft hat.
 */

/**
 * **Das Werteraster eines Moduls** – dasselbe wie am Datensatz (`SPEC.grid`), nur mit
 * einer schmaleren Mindestspalte: eine Prozessspalte ist rund 460 px breit, und mit
 * 240 px Minimum fiele sie immer auf eine Spalte zurück.
 */
export const MODULE_GRID: CSSProperties = {
  display: 'grid',
  gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 180px), 1fr))',
  gap: '16px 24px',
};

/**
 * ►►► **Ein Anteil an einem Ganzen — Leiste, Wort, Zahl.** ◄◄◄
 *
 * Die Bestandsleiste am Artikel beantwortet «wie viel habe ich, und wie viel davon ist
 * verfügbar» in einem Bild; **die Frage ist nicht die des Bestands**, sondern die jeder
 * Aufteilung: wie viel ist bezahlt, wie viel offen, wie viel noch nicht berechnet – wie
 * weit ist ein Vorgang. `StockBar` ist seither die Ausprägung dieser Leiste für Zustände
 * von Einzelinstanzen, und **hier steht sie einmal**.
 *
 * Die Regeln von dort gelten unverändert, weil sie nicht am Bestand hängen:
 *
 * - **Die Beschriftung gehört zur Leiste, nicht daneben.** Farbe allein unterscheidet
 *   nicht – zwei gleichfarbige Segmente sind strukturell nicht zu trennen, das **Wort**
 *   ist die Unterscheidung (Testnotiz #789).
 * - **Eine Haarlinie zwischen den Segmenten** – als `border`, nicht als `gap`: bei `gap`
 *   summierten sich die Prozentbreiten über 100 %, und das letzte Segment fiele hinter
 *   `overflow: hidden`.
 * - **Der Gewählte tritt hervor, die anderen verschwinden nicht.** Ein Segment, das aus
 *   der Zeile fällt, sobald man ein anderes ansieht, wäre ein Filter.
 */
export type BarSegment = {
  key: string;
  label: string;
  /** Der Anteil – dieselbe Einheit wie bei den Geschwistern (Stück, Geld, Schritte). */
  value: number;
  /** Der Ampelton bzw. die Farbe dieses Segments. */
  color: string;
  /** Was rechts neben dem Wort steht. Ohne Angabe: nichts. */
  text?: string;
  /** Die Erklärung am Segment der Leiste. */
  hint?: string;
};

export function ValueBar({ segments, height = 10, onPick, active, legendHint, trailing,
  dim = true }: {
  segments: BarSegment[];
  height?: number;
  /** Klick auf ein Segment bzw. seine Beschriftung. Ohne Handler ist alles Anzeige. */
  onPick?: (key: string) => void;
  /** Welches Segment gerade offen ist – es tritt hervor, die anderen zurück. */
  active?: string | null;
  /**
   * ►►► **Treten die anderen zurück, wenn eines gewählt ist?** ◄◄◄
   *
   * Beim **Bestand** ja: dort ersetzt das Hervortreten einen Filter – man sieht sich
   * einen Zustand an, die übrigen bleiben da, aber leise.
   *
   * Bei den **Stufen** nein, und das ist kein Geschmack: dort trägt die Farbe den
   * Fortschritt (vorbei ↔ dran ↔ steht noch aus). Gedämpft sehen «vorbei» und «steht
   * noch aus» gleich aus – gemessen war die halbe Leiste danach dasselbe Blassgrau, und
   * *wie weit bin ich* war nicht mehr abzulesen. Welche Stufe **offen** ist, sagt die
   * Beschriftung ohnehin (fett, dunkler, unterstrichen).
   */
  dim?: boolean;
  /** Was der Klick bedeutet, je nachdem ob dieses Segment offen ist. */
  legendHint?: (open: boolean) => string | undefined;
  /** Was am Ende der Beschriftungszeile steht – z. B. ein «Alles»-Schalter. */
  trailing?: ReactNode;
}) {
  const total = segments.reduce((n, s) => n + s.value, 0);
  const faded = (key: string) => dim && active != null && active !== key;
  return (
    <div className="flex flex-col gap-2">
      {total === 0 ? (
        <div className="rounded-full" style={{ height, background: 'var(--bg-3)' }} aria-hidden />
      ) : (
        <div className="flex w-full overflow-hidden rounded-full" style={{ height }}>
          {segments.map((s, i) => {
            const dimmed = faded(s.key);
            const style: CSSProperties = {
              width: `${(s.value / total) * 100}%`,
              background: s.color,
              opacity: dimmed ? 0.3 : 1,
              borderRight: i < segments.length - 1 ? '1px solid var(--bg-1)' : undefined,
              transition: 'opacity .12s',
            };
            if (!onPick) return <span key={s.key} data-tip={s.hint} style={style} />;
            return (
              <button key={s.key} type="button" aria-label={s.hint ?? s.label}
                data-tip={s.hint} style={style}
                onClick={(e) => { e.stopPropagation(); onPick(s.key); }} />
            );
          })}
        </div>
      )}
      {/* Sie bricht um statt zu scrollen: seitwärts scrollen ist im ERP verboten, und bei
          sechs Segmenten auf 375 px passen sie nicht in eine Zeile. */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {segments.map((s) => (
          <SegmentMark key={s.key} seg={s} open={active === s.key}
            dimmed={faded(s.key)} hint={legendHint} onPick={onPick} />
        ))}
        {trailing}
      </div>
    </div>
  );
}

/**
 * **Punkt · Wort · Zahl** – die kleinste vollständige Aussage über einen Anteil, und
 * dieselbe Anatomie, mit der das Haus jeden Status schreibt (Design System: Status =
 * Punkt + Wort). Die Zahl steht in Tabellenziffern daneben, damit untereinander stehende
 * Zeilen bündig bleiben.
 */
function SegmentMark({ seg, open, dimmed, hint, onPick }: {
  seg: BarSegment; open: boolean; dimmed: boolean;
  hint?: (open: boolean) => string | undefined;
  onPick?: (key: string) => void;
}) {
  const body = (
    <>
      <span aria-hidden className="rounded-full" style={{
        width: 7, height: 7, flex: 'none', background: seg.color,
      }} />
      <span className={open ? 'font-medium' : undefined}
        style={{ color: open ? 'var(--fg-1)' : 'var(--fg-2)' }}>{seg.label}</span>
      {seg.text && <span className="ix-tnum" style={{ color: 'var(--fg-3)' }}>{seg.text}</span>}
    </>
  );
  const style: CSSProperties = {
    opacity: dimmed ? 0.55 : 1,
    borderBottom: `1px solid ${open ? seg.color : 'transparent'}`,
    paddingBottom: 1,
    transition: 'opacity .12s',
  };
  if (!onPick) {
    return <span className="flex items-center gap-1.5 text-[12.5px]" style={style}>{body}</span>;
  }
  return (
    <button type="button" aria-pressed={open} data-tip={hint?.(open)}
      className="flex items-center gap-1.5 text-[12.5px]" style={style}
      onClick={(e) => { e.stopPropagation(); onPick(seg.key); }}>
      {body}
    </button>
  );
}

/*
 * ►►► **Eine Stufen-LEISTE gibt es nicht mehr** (Testnotiz #868). ◄◄◄
 *
 * Hier stand `ModuleSteps` (+ `ModuleStep`, `ALL_STEPS`): eine waagrechte Leiste über der
 * Karte, die jeden Schritt als Segment zeigte. Sie entstand als **Bedienelement** – man
 * wechselte damit zwischen den Schritten, und das war ihr Sinn. Seit alles untereinander
 * steht (#863) hatte sie keinen Handler mehr, und was blieb, war eine Zeile, die dieselben
 * drei Wörter trug wie die drei Abschnitte darunter.
 *
 * *«Mir passt das da oben nicht.»* – Der Verlauf steht jetzt **an** den Abschnitten
 * (`ModuleSection state`), also dort, wo man den Namen ohnehin liest: Punkt + Wort, die
 * Anatomie jedes Status im Haus, und von oben nach unten gelesen ist es die vertikale
 * Fassung derselben Aussage.
 *
 * `ValueBar` bleibt, wo sie hingehört: bei einem **Anteil an einem Ganzen** (Bestand).
 * Drei Schritte sind kein Anteil – sie waren als drei gleich breite Segmente gezeichnet,
 * was schon sagt, dass die Breite nichts bedeutete.
 */
