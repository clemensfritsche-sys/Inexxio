'use client';

import { createContext, useContext } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';
import { StatusDot } from '@/components/erp/fields';
import { formatAmount } from '@/lib/utils';
import { NOTHING } from '@/lib/when';

/**
 * **Die Bauteile, aus denen ein Prozessschrittmodul besteht** – Fläche, Kopf, Zeile, Betrag,
 * Leiste. Kein eigenes Design-System: die Regeln aus `docs/design-system/README.md`, hier
 * **einmal** angewendet (Vorlage `detail-frame.SPEC`).
 */

/** **Die Fläche einer Modul-Karte** – wie `SPEC.card`, schmaler gepolstert; die Modulfarbe
 *  lebt in der Marke, nicht in der Fläche. */
export const MODULE_CARD: CSSProperties = {
  background: 'var(--bg-1)',
  border: '1px solid var(--border-1)',
  borderRadius: 'var(--r-lg)',
  boxShadow: 'var(--shadow-sm)',
  padding: '16px 18px',
};

/** **Der Name des Moduls** – `SpecHead` eine Nummer kleiner. */
export const MODULE_TITLE: CSSProperties = {
  font: '700 16px var(--font-display)',
  letterSpacing: '-.01em',
  color: 'var(--fg-1)',
};

/**
 * **Die Höhen der Knöpfe eines Moduls** – an einer Stelle. `row` sitzt in einer
 * Tabellenzeile, `inline` in einer Handlungsleiste, `main`/`stage` ist die eine Handlung,
 * die eine Karte bzw. eine Stufe abschliesst.
 */
export const ACT_H = { row: 26, inline: 30, main: 34, stage: 42 } as const;

/** **Der Abstand zwischen zwei Feldern einer Formular-Zeile**; unter der Beschriftung bringt
 *  `controls.Label` seine 4 px mit. */
export const FIELD_GAP = 12;

/**
 * **Ein Knopf ist ein Symbol, und beim Zeigen klappt sein Name daneben auf** (`.ix-tuck`) –
 * nur in einer Leiste, die nicht umbricht (`.ix-actions`). **In einer Zeile (`InRow`) klappt er
 * nicht aus**, der Name steht in der Blase. Der `tip` hängt an einer Hülle, weil ein gesperrter
 * Knopf den Zeiger nicht in jedem Browser meldet.
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
  /** **Ein Quadrat** – über `--actbtn-w`, weil ein Inline-`width` das Ausklappen verhinderte. */
  square?: boolean;
  /** Ein **Grund**, keine zweite Beschriftung – als Blase an der Hülle. */
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
  const bubble = steady ? (tip ? `${label} — ${tip}` : label) : tip;
  return bubble ? <span data-tip={bubble} className="inline-flex">{button}</span> : button;
}

/**
 * **DIE ZEILEN-GRAMMATIK — eine Zeile, fünf Plätze, immer dieselben.**
 *
 * ```
 * [ Identifikator ] [ Meta ] ······ [ Aktion ] [ Datum ] [ Betrag ]
 * ```
 *
 * * **Der Identifikator steht links** (Rechnungsnummer, Zahlungsart) – nichts davor.
 * * **Meta folgt in derselben Zeile** und gibt als Erstes Platz ab.
 * * **Die Aktionen** (`RowActions`) sind im Ruhezustand unsichtbar, bei Hover und Fokus
 *   da, auf einem Gerät ohne Zeiger dauerhaft (`.ix-row`/`.ix-rowactions`) – und
 *   **belegen ihren Platz immer** (`opacity`, kein `display`), sonst rutschte der Betrag
 *   unter dem Zeiger.
 * * **Das Datum** ist die zweite Zahl der Zeile und steht direkt links vom Betrag; es
 *   schrumpft nicht («20.8.2026» hat keine Umbruchstelle).
 * * **Der Betrag steht IMMER ganz rechts** – auf derselben Flucht in jeder Zeile, weil er
 *   das letzte Element ist.
 *
 * **Strikt einreihig**: was nicht passt, wird gekappt (Meta zuerst).
 */
export function LedgerRow({ ident, meta, actions, date, amount, tip }: {
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
  /** Die Erklärung am Betrag – dort trägt die Farbe den Zustand. */
  tip?: string;
}) {
  return (
    <div className="ix-row flex items-baseline" style={{ gap: 10, minWidth: 0, flexWrap: 'nowrap' }}>
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

/** **Knöpfe, die ihre Breite behalten** – für eine Leiste, die umbrechen darf (Name in der Blase). */
export function Steady({ children }: { children: ReactNode }) {
  return <InRow.Provider value>{children}</InRow.Provider>;
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

/* **Eine Rückfrage gibt es nicht**: die Sicherheit kommt aus den Guards, nicht aus einem
 * zusätzlichen Klick. */

/** **Die Handlung, die eine Sache eine Stufe weiterbringt**: volle Breite, 42 px (Beleg, Zeiterfassung). */
export function StageAction({ icon: Icon, label, disabled, onClick }: {
  icon: LucideIcon;
  label: string;
  disabled?: boolean;
  onClick: () => void;
}) {
  return (
    <button type="button" className="erp-actbtn erp-actbtn-primary w-full"
      disabled={disabled} style={{ height: ACT_H.stage, fontSize: 14 }} onClick={onClick}>
      <Icon size={16} /> {label}
    </button>
  );
}

/**
 * **EIN Betrag — Zahl, Währung, Zustandsfarbe.** Die Währung ist ein Kind der Zahl und erbt
 * ihre Farbe; formatiert wird hier, sonst nirgends. `currency` darf ein Knoten sein (Wähler).
 */
export function Amount({ value, sign, currency, decimals = 2, color, size = 13, weight = 600,
                         tip, children }: {
  value?: string | number | null;
  /** Ein Vorzeichen vor der Zahl (`+` Einnahme, `−`/`-` Ausgabe) – nur, wo es eine Zahl gibt. */
  sign?: string;
  /** Der Code – oder der Wähler, wo er einer ist. Ohne Angabe steht nur die Zahl. */
  currency?: ReactNode;
  decimals?: number;
  /** Der Ampelton des Zustands; ohne Angabe die Schriftfarbe der Umgebung. */
  color?: string;
  size?: number;
  weight?: number;
  tip?: string;
  /** **Derselbe Betrag, nur eingegeben**: ein Feld statt der Zahl, die Währung bleibt als Suffix. */
  children?: ReactNode;
}) {
  return (
    <span {...(tip ? { 'data-tip': tip } : {})}
      className={children ? 'inline-flex items-baseline' : undefined}
      style={{
        color, font: `${weight} ${size}px var(--font-body)`,
        fontVariantNumeric: 'tabular-nums', whiteSpace: 'nowrap',
      }}>
      {children ?? (value == null || value === '' ? NOTHING : `${sign ?? ''}${formatAmount(value, decimals)}`)}
      {currency != null && currency !== '' && (
        <span style={{ color: 'inherit', opacity: 0.72, fontSize: size - 1,
                       fontWeight: 500, marginLeft: 4, flex: 'none' }}>{currency}</span>
      )}
    </span>
  );
}

/**
 * **Ein Anteil an einem Ganzen — Leiste, Wort, Zahl.** `StockBar` ist ihre Ausprägung für
 * die Zustände von Einzelinstanzen.
 *
 * - **Die Beschriftung gehört zur Leiste**: zwei gleichfarbige Segmente sind nur am
 *   **Wort** zu unterscheiden.
 * - **Eine Haarlinie zwischen den Segmenten** als `border`, nicht als `gap` – sonst
 *   summierten sich die Breiten über 100 %.
 * - **Der Gewählte tritt hervor, die anderen verschwinden nicht** – sonst wäre es ein Filter.
 */
type BarSegment = {
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

export function ValueBar({ segments, height = 10, onPick, active, legendHint }: {
  segments: BarSegment[];
  height?: number;
  /** Klick auf ein Segment bzw. seine Beschriftung. Ohne Handler ist alles Anzeige. */
  onPick?: (key: string) => void;
  /** Welches Segment gerade offen ist – es tritt hervor, die anderen zurück. */
  active?: string | null;
  /** Was der Klick bedeutet, je nachdem ob dieses Segment offen ist. */
  legendHint?: (open: boolean) => string | undefined;
}) {
  const total = segments.reduce((n, s) => n + s.value, 0);
  const faded = (key: string) => active != null && active !== key;
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
      {/* Bricht um statt zu scrollen (seitwärts scrollen ist im ERP verboten). */}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
        {segments.map((s) => (
          <SegmentMark key={s.key} seg={s} open={active === s.key}
            dimmed={faded(s.key)} hint={legendHint} onPick={onPick} />
        ))}
      </div>
    </div>
  );
}

/** **Punkt · Wort · Zahl** – wie jeder Status im Haus, die Zahl in Tabellenziffern. */
function SegmentMark({ seg, open, dimmed, hint, onPick }: {
  seg: BarSegment; open: boolean; dimmed: boolean;
  hint?: (open: boolean) => string | undefined;
  onPick?: (key: string) => void;
}) {
  const body = (
    <>
      <StatusDot color={seg.color} />
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
