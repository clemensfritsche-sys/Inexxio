'use client';

import type { CSSProperties, ReactNode } from 'react';
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
 * **Ein Abschnitt einer Modul-Karte** – Versalien-Beschriftung über einer Haarlinie,
 * rechts Platz für das, was zum Abschnitt gehört (die Währung, eine Gegenhandlung).
 *
 * Bewusst **ohne** Symbol und ohne Display-Schrift: in einer Karte mit drei Abschnitten
 * wären drei getönte Quadrate und drei fette Überschriften lauter als der Inhalt. Der
 * grosse Kopf steht oben, hier gliedert es nur.
 */
export function ModuleSection({ title, right, children, first }: {
  /**
   * **Leer heisst: kein Kopf.** Steht der Name des Abschnitts schon eine Zeile höher –
   * in der Stufen-Leiste, hervorgehoben –, dann sagt eine Überschrift darunter dasselbe
   * Wort ein zweites Mal. Ein Kopf, der nichts Neues sagt, ist Fläche.
   */
  title?: string;
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
          <span style={{ ...MICRO_LABEL, flex: 1, minWidth: 0 }}>{title}</span>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

/**
 * **Die Meta-Zeile** – was über den ganzen Vorgang gilt und in keinen Abschnitt gehört:
 * Richtung, Währung, ein Termin, eine Sperre. Eine Zeile, leise, umbrechend.
 */
export function ModuleMeta({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-x-3 gap-y-1 flex-wrap text-[12px]"
      style={{ color: 'var(--fg-3)', marginBottom: 14 }}>
      {children}
    </div>
  );
}

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

/**
 * ►►► **Die Stufen eines Moduls — und wie man zwischen ihnen wechselt.** ◄◄◄
 *
 * Gemeldet war: *«es gibt diese drei Schritte … aber ich muss irgendwie zwischen den
 * Schritten hin- und herwechseln können oder alles auf einen Blick sehen.»*
 *
 * Die frühere Fassung war eine **Kette aus Punkt und Linie**, in der alle drei Stufen
 * immer offen untereinander standen: bei einem Vorgang mit vier Buchungen war die Karte
 * zwei Bildschirme hoch, und was gerade dran war, musste man suchen. Sie sagte den
 * Verlauf – und liess ihn nicht bedienen.
 *
 * Es ist **dieselbe Leiste wie beim Bestand**, mit Stufen statt Zuständen: die Segmente
 * zeigen den Verlauf in einem Bild, die Beschriftung darunter nennt jede Stufe mit ihrer
 * einen Zahl, **und sie ist zugleich das Bedienelement**. Ein neues Modul mit Stufen
 * bekommt dieselbe Zeile, ohne eine Zeile Code dafür zu schreiben.
 *
 * ►►► **Und sie darf auch nur ZEIGEN** (Testnotiz #863). ◄◄◄
 *
 * *«Ich mag diese Reiter-Ansicht nicht, ich möchte alles auf einmal sehen untereinander.»*
 * – Ohne `onOpen` ist sie genau das: eine **Übersicht**. Die Segmente sagen weiterhin, wie
 * weit der Vorgang ist; nur versteckt die Leiste nichts mehr, also gibt es auch nichts zu
 * öffnen (und darum keinen «Alles»-Schalter, der immer an wäre).
 *
 * Das ist dieselbe Bauart wie bei `ValueBar` selbst: **ohne Handler ist alles Anzeige.**
 * Zwei Bauteile – eines zum Wechseln, eines zum Zeigen – wären zwei Fassungen derselben
 * Leiste, und die zweite bliebe beim nächsten neuen Zustand stehen.
 */
export type ModuleStep = {
  key: string;
  label: string;
  /**
   * `past` – vorbei · `active` – dran · `ahead` – steht noch aus.
   *
   * **Bewusst nicht `done`/`open`.** Das sind die Wörter, mit denen ein *Modul* seine
   * eigenen Stufen benennt (`DEAL_STAGE.done`) bzw. mit denen diese Leiste sagt, welcher
   * Abschnitt gerade **offen** ist. Hier geht es um etwas Drittes: wie weit man ist. Ein
   * Wort, das in derselben Datei zwei Dinge meint, ist die Form, in der ein Vergleich
   * still falsch wird – und ein Wächter, der Stufen-Literale sucht, kann die beiden
   * Bedeutungen nicht auseinanderhalten.
   */
  state: 'past' | 'active' | 'ahead';
  /** Die eine Zahl dieser Stufe. Leer heisst «dazu gibt es noch nichts zu sagen». */
  value?: string;
  hint?: string;
};

/** Der Wert, bei dem alle Stufen offen stehen. */
export const ALL_STEPS = 'all';

const STEP_COLOR: Record<ModuleStep['state'], string> = {
  past: 'var(--fg-2)',
  active: 'var(--accent)',
  ahead: 'var(--border-2)',
};

export function ModuleSteps({ steps, open, onOpen, allLabel = 'Alles' }: {
  steps: ModuleStep[];
  /** Die offene Stufe – oder `ALL_STEPS`. Ohne `onOpen` bedeutungslos. */
  open?: string;
  /** **Ohne Handler ist die Leiste eine Übersicht** – sie versteckt dann nichts (#863). */
  onOpen?: (key: string) => void;
  allLabel?: string;
}) {
  const all = open === ALL_STEPS;
  return (
    // Sie ist ein **Band**, kein Absatz: darüber steht, worum es geht, darunter der
    // gewählte Schritt. Ohne die Luft oben klebte sie am letzten Eintrag des Abschnitts
    // davor und las sich, als gehörte sie noch dazu.
    <div style={{ margin: '14px 0 16px' }}>
      <ValueBar
        segments={steps.map((s) => ({
          key: s.key, label: s.label, value: 1, color: STEP_COLOR[s.state],
          text: s.value || undefined, hint: s.hint,
        }))}
        active={onOpen && !all ? open : null}
        dim={false}
        onPick={onOpen}
        legendHint={onOpen && ((shown) => (shown ? 'Ist offen' : 'Diesen Schritt öffnen'))}
        trailing={onOpen && (
          <button type="button" aria-pressed={all}
            data-tip={all ? 'Nur den gewählten Schritt zeigen' : 'Alle Schritte zeigen'}
            className="flex items-center gap-1.5 text-[12.5px]"
            style={{
              marginLeft: 'auto',
              color: all ? 'var(--accent-ink)' : 'var(--fg-3)',
              borderBottom: `1px solid ${all ? 'var(--accent)' : 'transparent'}`,
              paddingBottom: 1,
            }}
            onClick={(e) => {
              e.stopPropagation();
              onOpen(all ? (steps.find((s) => s.state === 'active') ?? steps[0]).key
                : ALL_STEPS);
            }}>
            {allLabel}
          </button>
        )}
      />
    </div>
  );
}
