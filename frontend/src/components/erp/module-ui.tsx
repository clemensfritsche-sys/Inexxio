'use client';

import { createContext, useContext } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { formatAmount } from '@/lib/utils';

/**
 * **Die Bauteile, aus denen ein Prozessschrittmodul besteht** – die Fläche, der Kopf, ein
 * Abschnitt, die Zeile, der Betrag, die Leiste. Jedes künftige Modul baut darauf, statt
 * sie neu zu erfinden.
 *
 * Bewusst **kein neues Design-System**: jede Zahl kommt aus
 * `styles/design-system/colors_and_type.css`, jede Regel steht in
 * `docs/design-system/README.md`. Neu ist nur, dass sie hier **einmal** angewendet sind
 * statt an jeder Aufrufstelle mit leicht anderen Werten. Die Vorlage ist die
 * Detail-Ansicht eines Datensatzes (`fields.SPEC`).
 */

/**
 * **Die Fläche einer Modul-Karte.** Weiss, Haarlinie, ein leiser Schatten – dieselbe
 * Karte wie `SPEC.card`, nur mit der Polsterung einer schmalen Prozessspalte. Die
 * Modulfarbe lebt in der **Marke**, nicht in der Fläche (Struktur vor Fläche).
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
 * **Die Höhen der Knöpfe eines Moduls** – an einer Stelle. `row` sitzt in einer
 * Tabellenzeile, `inline` in einer Handlungsleiste, `main`/`stage` ist die eine Handlung,
 * die eine Karte bzw. eine Stufe abschliesst.
 */
export const ACT_H = { row: 26, inline: 30, main: 34, stage: 42 } as const;

/**
 * **Der Abstand zwischen zwei Feldern einer Formular-Zeile** (#987/#990). **Unter** der
 * Beschriftung gibt es keinen: `fields.Label` bringt seine 4 px mit.
 */
export const FIELD_GAP = 12;

/**
 * **Ein Knopf ist ein Symbol, und beim Zeigen klappt sein Name daneben auf** (#877–#896,
 * #900): `.ix-tuck` in `globals.css`. Die Geste braucht **Platz** – in einer umbrechenden
 * Zeile schwingt der Knopf (er wird breiter, die Zeile bricht um, der Zeiger fällt ab).
 * Darum steht er in `Actions` (bricht nicht um).
 *
 * **In einer Zeile (`RowActions`) klappt er NICHT aus** – gemessen schwang er dort bei
 * 375 px. Die Entscheidung trifft die Zeile über `InRow`, nicht jede Aufrufstelle; der
 * Name steht dann in der Blase, die am Layout nichts ändert.
 *
 * Der Grund (`tip`) hängt an einer Hülle, nicht am Knopf: `.ix-tuck` ist
 * `overflow: hidden` und schnitte ein `::after` weg (#790).
 */
const InRow = createContext(false);

export function ActionButton({
  icon: Icon, label, tone = 'neutral', height = ACT_H.row, square, tip, disabled, onClick,
}: {
  icon: LucideIcon;
  /** Was der Knopf tut – das Wort, das beim Zeigen daneben aufklappt, und das `aria-label`. */
  label: string;
  tone?: 'primary' | 'neutral' | 'danger';
  height?: number;
  /**
   * **Ein Quadrat in der Höhe, die daneben steht** (#957). Gesetzt über die CSS-Variable
   * `--actbtn-w`, damit `.ix-tuck:hover { width: auto }` den Namen ausklappen kann – ein
   * Inline-`width` gewönne gegen jede Regel.
   */
  square?: boolean;
  /**
   * Ein **Grund**, keine zweite Beschriftung – er steht als Blase an der Hülle. Meist der
   * Satz, warum es gerade nicht geht, oder was die Handlung nach sich zieht.
   */
  tip?: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  const steady = useContext(InRow);
  const button = (
    <button type="button" disabled={disabled} onClick={onClick}
      className={`erp-actbtn erp-actbtn-${tone} erp-actbtn-icon${steady ? '' : ' ix-tuck'}`}
      style={square
        ? ({ height, '--actbtn-w': `${height}px` } as CSSProperties)
        : { height }}
      aria-label={label}>
      <Icon size={13} />
      {!steady && <span className="ix-tuck-name">{label}</span>}
    </button>
  );
  // **In einer Zeile sagt die Blase den Namen** – und den Grund dahinter, wie überall.
  const bubble = steady ? (tip ? `${label} — ${tip}` : label) : tip;
  return bubble ? <span data-tip={bubble} className="inline-flex">{button}</span> : button;
}

/**
 * **DIE ZEILEN-GRAMMATIK — eine Zeile, fünf Plätze, immer dieselben** (#996–#1002,
 * #1011/#1012).
 *
 * ```
 * [ Identifikator ] [ Meta ] ······ [ Aktion ] [ Datum ] [ Betrag ]
 * ```
 *
 * * **Der Identifikator steht links** (Rechnungsnummer, Zahlungsart) – nichts davor.
 * * **Meta folgt in derselben Zeile** und gibt als Erstes Platz ab.
 * * **Die Aktionen** (`RowActions`) sind im Ruhezustand unsichtbar, bei Hover und Fokus
 *   da, auf einem Gerät ohne Zeiger dauerhaft (`.ix-row`/`.ix-rowactions`, #832) – und
 *   **belegen ihren Platz immer** (`opacity`, kein `display`), sonst rutschte der Betrag
 *   unter dem Zeiger.
 * * **Das Datum** ist die zweite Zahl der Zeile und steht direkt links vom Betrag; es
 *   schrumpft nicht («20.8.2026» hat keine Umbruchstelle).
 * * **Der Betrag steht IMMER ganz rechts** – auf derselben Flucht in jeder Zeile, weil er
 *   das letzte Element ist.
 *
 * **Strikt einreihig**: was nicht passt, wird gekappt (Meta zuerst).
 */
export function LedgerRow({ ident, meta, actions, date, amount, tip, faded }: {
  /** Was diese Zeile **ist** – Rechnungsnummer, Zahlungsart. */
  ident: ReactNode;
  /** Zusatzangaben – geben als Erstes Platz ab. */
  meta?: ReactNode;
  /** Korrekturen an **dieser** Zeile; sie erscheinen bei Hover und Fokus. */
  actions?: ReactNode;
  /** Datum bzw. Fälligkeit – direkt links vom Betrag, schrumpft nicht. */
  date?: ReactNode;
  /** Die Zahl. Sie steht rechts, tabellarisch, und rührt sich nie. */
  amount: ReactNode;
  /** Die Erklärung am Betrag – dort trägt die Farbe den Zustand (#997). */
  tip?: string;
  /** Eine stornierte Zeile bleibt stehen, tritt aber zurück. */
  faded?: boolean;
}) {
  return (
    <div className="ix-row flex items-baseline" style={{
      gap: 10, minWidth: 0, flexWrap: 'nowrap', opacity: faded ? 0.55 : 1,
    }}>
      <span className="truncate" style={{
        flex: '0 1 auto', minWidth: 0, fontSize: 12.5, color: 'var(--fg-2)',
      }}>{ident}</span>
      <span className="truncate" style={{
        flex: '1 1 auto', minWidth: 0, fontSize: 11.5, color: 'var(--fg-3)',
        fontVariantNumeric: 'tabular-nums',
      }}>{meta}</span>
      {actions && <RowActions>{actions}</RowActions>}
      {date != null && date !== '' && (
        <span style={{
          flex: 'none', marginLeft: actions ? undefined : 'auto',
          fontSize: 11.5, color: 'var(--fg-3)', textAlign: 'right',
          fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
        }}>{date}</span>
      )}
      <span style={{
        flex: 'none', font: '600 13px var(--font-body)',
        fontVariantNumeric: 'tabular-nums',
      }} {...(tip ? { 'data-tip': tip } : {})}>{amount}</span>
    </div>
  );
}

/** Die Knöpfe **am Ende** ihrer Zeile – siehe `LedgerRow`. Sie behalten ihre Breite (`InRow`). */
export function RowActions({ children }: { children: ReactNode }) {
  return (
    <InRow.Provider value>
      <span className="ix-rowactions ix-actions" style={{ flex: 'none', marginLeft: 'auto' }}>
        {children}
      </span>
    </InRow.Provider>
  );
}

/*
 * **Eine Rückfrage gibt es nicht** (#1022): die Sicherheit kommt aus den Guards, nicht aus
 * einem zusätzlichen Klick – ein Storno schreibt eine Gegenbuchung (eine zweite lehnt der
 * Dienst ab), eine Erstattung ist idempotent. Wo eine Handlung wirklich unumkehrbar wäre,
 * ist die Antwort ein Guard, keine Frage.
 */

/**
 * **Die Zeile, in der Handlungs-Knöpfe stehen.** Sie bricht **nicht** um – sonst schwingt
 * ein ausklappender Knopf (siehe `ActionButton`).
 */
export function Actions({ children, style }: { children: ReactNode; style?: CSSProperties }) {
  return <div className="ix-actions" style={style}>{children}</div>;
}

/**
 * **Wie weit ist ein Schritt?** `past` – vorbei · `active` – dran · `ahead` – steht noch
 * aus. Bewusst nicht `done`/`open`: das sind die Wörter der Beleg-Stufen bzw. der Leiste.
 */
export type StepState = 'past' | 'active' | 'ahead';

const STEP_COLOR: Record<StepState, string> = {
  past: 'var(--fg-2)',
  active: 'var(--accent)',
  ahead: 'var(--border-2)',
};

/** **Die Luft über einem Abschnitt** (#971/#1006) – sie gehört der Gattung, nicht der Aufrufstelle. */
const SECTION_GAP = 34;

/**
 * **EIN Betrag — Zahl, Währung, Zustandsfarbe** (#1007). Die Währung ist ein **Kind** der
 * Zahl und erbt ihre Farbe (`color: inherit`) – sie kann keine andere haben; zurücktreten
 * tut sie über Grösse, Gewicht und Deckkraft. Formatiert wird hier, sonst nirgends.
 * `currency` darf ein **Knoten** sein: am Total ist der Code zugleich der Wähler (#917).
 */
export function Amount({ value, currency, decimals = 2, color, size = 13, weight = 600,
                         tip, children }: {
  value?: string | number | null;
  /** Der Code – oder der Wähler, wo er einer ist. Ohne Angabe steht nur die Zahl. */
  currency?: ReactNode;
  decimals?: number;
  /** Der Ampelton des Zustands; ohne Angabe die Schriftfarbe der Umgebung. */
  color?: string;
  size?: number;
  weight?: number;
  tip?: string;
  /**
   * **Derselbe Betrag, nur eingegeben** (#1010/#1017): ein Eingabefeld tritt an die Stelle
   * der Zahl, die Währung bleibt als Suffix in derselben Hülle (`Editable` liegt aussen).
   * Keine Betrags-Ausgabe und kein Betrags-Feld ohne Währung.
   */
  children?: ReactNode;
}) {
  return (
    <span {...(tip ? { 'data-tip': tip } : {})}
      className={children ? 'inline-flex items-baseline' : undefined}
      style={{
        color, font: `${weight} ${size}px var(--font-body)`,
        fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
      }}>
      {children ?? formatAmount(value, decimals)}
      {currency != null && currency !== '' && (
        <span style={{ color: 'inherit', opacity: 0.72, fontSize: size - 1,
                       fontWeight: 500, marginLeft: 4, flex: 'none' }}>{currency}</span>
      )}
    </span>
  );
}

/**
 * **Ein Abschnitt einer Modul-Karte** – Kopfleiste mit Versalien-Beschriftung, rechts
 * Platz für das, was zum Abschnitt gehört. **Der Verlauf steht an den Abschnitten**
 * (#868): ein Punkt vor der Beschriftung sagt, wie weit der Abschnitt ist (Punkt + Wort,
 * die Anatomie jedes Status im Haus) – eine eigene Stufen-Leiste gibt es nicht.
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
    // `data-fb-section` benennt den Abschnitt für eine Testnotiz («‹Modul› › ‹Abschnitt›»).
    <section data-fb-section={title || undefined}
      style={{ marginTop: first ? 0 : SECTION_GAP, minWidth: 0 }}>
      {(title || right) && (
        // **Der Abschnittskopf ist eine LEISTE** (#1015): gedämpfte Füllung (`--bg-3`),
        // dunkle Schrift, kräftige Trennlinie – nicht Vollschwarz (Struktur vor Fläche).
        // Über die volle Modulbreite: der negative Seitenrand entspricht der Polsterung
        // der Karte (`MODULE_CARD.padding` = 18 px).
        <div className="flex items-center gap-2" style={{
          padding: '6px 18px', margin: '0 -18px 14px',
          background: 'var(--bg-3)', borderBottom: '2px solid var(--border-2)',
        }}>
          {/* **Die Status-Spalte steht immer, auch leer**: sonst stünden die Überschriften
              von Schritt- und Inhalts-Abschnitten auf zwei Kanten (gemessen 18 ↔ 33 px). */}
          <span aria-hidden className="rounded-full" style={{
            width: 7, height: 7, flex: 'none',
            background: state ? STEP_COLOR[state] : 'transparent',
          }} />
          {/* **Der Kopf ist eine Stufe über dem Feld-Label** (#1051): das Overline-Register
              (`--overline`, `--tracking-overline`) in 800 statt `MICRO_LABEL`, das jede
              Beschriftung **in** einem Abschnitt trägt. */}
          <span style={{
            flex: 1, minWidth: 0,
            font: 'var(--overline)', fontWeight: 800,
            letterSpacing: 'var(--tracking-overline)',
            textTransform: 'uppercase',
            color: 'var(--fg-1)',
          }}>{title}</span>
          {right}
        </div>
      )}
      {children}
    </section>
  );
}

/**
 * **Ein Anteil an einem Ganzen — Leiste, Wort, Zahl.** `StockBar` ist ihre Ausprägung für
 * die Zustände von Einzelinstanzen.
 *
 * - **Die Beschriftung gehört zur Leiste**: zwei gleichfarbige Segmente sind nur am
 *   **Wort** zu unterscheiden (#789).
 * - **Eine Haarlinie zwischen den Segmenten** als `border`, nicht als `gap` – sonst
 *   summierten sich die Breiten über 100 %.
 * - **Der Gewählte tritt hervor, die anderen verschwinden nicht** – sonst wäre es ein Filter.
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
   * **Treten die anderen zurück, wenn eines gewählt ist?** Beim Bestand ja (das ersetzt
   * einen Filter); wo die Farbe einen Fortschritt trägt, nein – gedämpft sähen «vorbei»
   * und «steht noch aus» gleich aus.
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
