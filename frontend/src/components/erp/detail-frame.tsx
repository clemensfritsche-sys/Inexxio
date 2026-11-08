'use client';

import type { ElementType, ReactNode } from 'react';
import { ArrowLeft, GitBranch, Home, Sparkles, ExternalLink } from 'lucide-react';
import type { StatusTone, StatusCfg } from '@/lib/status-tone';
import { TYPE_META } from '@/lib/erp-record';
import type { ErpRecordType, Todo, TodoItem } from '@/types';
import { jumpToTodo, todoTip } from '@/lib/todo';
import { formatObjectId } from '@/lib/utils';
import { webHref } from '@/lib/web-link';
import { InfoHint } from '@/components/erp/hints';
import { MICRO_LABEL, StatusBadge } from '@/components/erp/fields';

// ►►► **Die Anatomie eines Datensatz-Fensters** – Kopf (`DetailHeader`, `RecordIcon`), Breite
// (`DetailBody`), Karten (`Card`, `SPEC`, `SpecHead`, `SpecSection`, `ReadField`) und
// Abschnitte (`SectionSep`, `TodoChip`). ◄◄◄

// ─── Karte: der Container eines Formular-Abschnitts ──────────────────────────

/**
 * Symbol (optional) + Titel + rechter Slot (Speicher-Anzeige), darunter der Inhalt – EINE
 * Anatomie für Konto, Benutzer und Unternehmen.
 */
export function Card({ icon: Icon, title, right, children, info, extra, unclipped, anchor }: {
  icon?: ElementType; title: string; right?: ReactNode; children: ReactNode;
  /** ⓘ neben dem Titel – die Erklärung im Hover. */
  info?: string;
  /** Neben dem Titel, z. B. die Zahl «zu tun» (`TodoChip`). */
  extra?: ReactNode;
  /** Ohne `overflow: hidden` – sonst schneidet die Karte die Hover-Blasen ihres Inhalts ab. */
  unclipped?: boolean;
  /** Sprungziel der Zahl am Symbol (`data-todo`). */
  anchor?: string;
}) {
  return (
    <div data-todo={anchor} style={{ background: 'var(--bg-1)', border: '1px solid var(--border-1)',
      borderRadius: 12, overflow: unclipped ? undefined : 'hidden', scrollMarginTop: 16 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    gap: 12, padding: '18px 24px', borderBottom: '1px solid var(--border-1)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          {Icon && <Icon style={{ width: 16, height: 16, color: 'var(--fg-3)', flex: 'none' }} />}
          <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-1)', margin: 0 }}>{title}</h2>
          {info && <InfoHint text={info} />}
          {extra}
        </div>
        {right}
      </div>
      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>{children}</div>
    </div>
  );
}

// ─── Spezifikations-Karte: die Lese-Ansicht eines Datensatzes ────────────────
// Karte + Werteraster + Lesefeld – dieselbe Anatomie für Artikel und Auftrag.

/**
 * ►►► **Die Breite eines Datensatz-Fensters — EINE Zahl für alle.** ◄◄◄ Ausnahme ist das
 * Prozessbild mit seinen drei Spuren – es misst seine Breite selbst.
 */
export const DETAIL_MAXW = 880;

/** Der Inhalt eines Datensatz-Reiters: **zentriert, auf {@link DETAIL_MAXW} begrenzt**. */
export function DetailBody({ children, gap, style }: {
  children: ReactNode;
  /** Abstand zwischen den Karten; ohne ihn stapelt der Aufrufer selbst. */
  gap?: number;
  style?: React.CSSProperties;
}) {
  return (
    <div style={{
      maxWidth: DETAIL_MAXW, marginInline: 'auto', width: '100%',
      ...(gap ? { display: 'flex', flexDirection: 'column', gap } : null),
      ...style,
    }}>
      {children}
    </div>
  );
}

export const SPEC = {
  card: {
    background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)',
    boxShadow: 'var(--shadow-sm)', padding: 'clamp(16px, 4vw, 30px)',
  } as React.CSSProperties,
  /** auto-fit-Werteraster; `min(100%, …)` kollabiert auf Mobile sauber. */
  grid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))',
    gap: '22px clamp(18px, 4vw, 40px)',
  } as React.CSSProperties,
};

/** **Der Kopf einer Spezifikations-Karte**: getöntes Symbol + Titel + rechter Slot. */
export function SpecHead({ icon: Icon, title, right }: {
  icon: ElementType; title: string; right?: ReactNode;
}) {
  // Auf jede Überschrift folgt eine Haarlinie.
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      paddingBottom: 14, marginBottom: 22, borderBottom: '1px solid var(--border-1)',
    }}>
      <span style={SPEC_ICO}><Icon size={17} /></span>
      <h2 style={{ font: '700 18px var(--font-display)', letterSpacing: '-.01em', margin: 0, flex: 1, color: 'var(--fg-1)' }}>{title}</h2>
      {right && <span style={{ flex: 'none' }}>{right}</span>}
    </div>
  );
}

/**
 * Unterabschnitt einer Spezifikations-Karte: 32-px-Symbol + Titel über einer Haarlinie,
 * darunter das Werte-Raster. Gliedert eine Karte, ohne eine zweite Karte zu öffnen.
 */
export function SpecSection({ icon: Icon, title, children }: {
  icon: ElementType; title: string; children: ReactNode;
}) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, paddingBottom: 14, margin: '18px 0 20px', borderBottom: '1px solid var(--border-1)' }}>
        <span style={{ ...SPEC_ICO, width: 32, height: 32 }}><Icon size={16} /></span>
        <h3 style={{ font: '600 16px var(--font-display)', letterSpacing: '-.01em', margin: 0, flex: 1, color: 'var(--fg-1)' }}>{title}</h3>
      </div>
      <div style={SPEC.grid}>{children}</div>
    </div>
  );
}

const SPEC_ICO: React.CSSProperties = {
  width: 34, height: 34, borderRadius: 'var(--r-sm)', background: 'var(--accent-soft)', color: 'var(--accent)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none',
};

function linkHost(href: string): string {
  try { return new URL(href).hostname.replace(/^www\./, ''); } catch { return href; }
}

/** Read-only-Feld: kleines Symbol + Versalien-Overline + kräftiger Wert. Optional
 *  Einheit/mono, Link (Host + Pfeil – nur ins Web, sonst Text) oder ⓘ-Hinweis bei
 *  abgeleiteten Werten. */
export function ReadField({ icon: Icon, label, value, unit, mono, full, autoHint, link }: {
  icon?: ElementType; label: string; value?: ReactNode; unit?: string;
  mono?: boolean; full?: boolean; autoHint?: string; link?: string;
}) {
  const href = webHref(link);
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', gridColumn: full ? '1 / -1' : undefined }}>
      {Icon && (
        <span style={{ width: 22, height: 22, color: 'var(--fg-4)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none', marginTop: 2 }}>
          <Icon size={18} />
        </span>
      )}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ ...MICRO_LABEL, display: 'flex', alignItems: 'center', gap: 5 }}>
          {label}
          {autoHint && <span style={{ display: 'inline-flex', color: 'var(--fg-4)', cursor: 'help' }} data-tip={autoHint}><Sparkles size={12} /></span>}
        </div>
        {href ? (
          <a href={href} target="_blank" rel="noreferrer"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 6, font: '600 14.5px var(--font-body)', color: 'var(--accent-ink)' }}>
            {linkHost(href)} <ExternalLink size={13} />
          </a>
        ) : (
          <div style={{ font: '600 15.5px var(--font-body)', color: 'var(--fg-1)', marginTop: 6, lineHeight: 1.35, overflowWrap: 'anywhere', ...(mono ? { fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', fontSize: 14.5 } : null) }}>
            {value ?? link}{unit && <span style={{ font: '500 13px var(--font-body)', color: 'var(--fg-3)', marginLeft: 3 }}>{unit}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

/** ►►► **Ein Zeichen am Symbol – eine Form für alle.** ◄◄◄ Unten rechts, was der Datensatz
 *  **ist** (eigene Gesellschaft, Abweichung), oben rechts, was **zu tun** ist; ab zehn «9+». */
function IconMark({ corner, size, bg, tip, children, list, onClick }: {
  corner: 'top' | 'bottom'; size: number; bg: string; tip: string; children: ReactNode;
  /** Mehrzeiliger Hover (je Abschnitt eine Zeile). */
  list?: boolean;
  /** Klick springt zur Stelle (nur im Kopf). */
  onClick?: () => void;
}) {
  return (
    <span className="tabular-nums" data-tip={tip} aria-label={tip}
      data-tip-list={list ? '' : undefined} data-tip-pos={list ? 'bottom' : undefined}
      role={onClick ? 'button' : undefined} tabIndex={onClick ? 0 : undefined}
      onClick={onClick ? (e) => { e.stopPropagation(); onClick(); } : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === 'Enter') onClick(); } : undefined}
      style={{
        position: 'absolute', right: -3, [corner]: -3, cursor: onClick ? 'pointer' : undefined, zIndex: 1,
        minWidth: size, height: size, padding: '0 3px', borderRadius: 999,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: bg, color: '#fff', font: `700 ${Math.round(size * 0.66)}px/1 var(--font-body)`,
        // Der Ring hebt das Zeichen von jeder Symbolfarbe ab.
        boxShadow: '0 0 0 2px var(--bg-1)',
      }}>
      {children}
    </span>
  );
}

/** ►►► **Die kleine Zahl am Abschnitt** – dieselbe Form wie am Symbol, nur inline: an
 *  «Zeiterfassung», «Stammdaten», «Adressen», «Feiertage». Ohne Aufgabe steht nichts da. */
export function TodoChip({ items }: { items: TodoItem[] }) {
  const n = items.reduce((a, i) => a + i.count, 0);
  if (!n) return null;
  const red = items.some((i) => i.red);
  return (
    <span className="tabular-nums" data-tip={todoTip(items)} data-tip-list=""
      aria-label={todoTip(items)} style={{
        minWidth: 16, height: 16, padding: '0 4px', borderRadius: 999, display: 'inline-flex',
        alignItems: 'center', justifyContent: 'center', color: '#fff', letterSpacing: 0,
        background: red ? 'var(--danger)' : 'var(--warning)', font: '700 10.5px/1 var(--font-body)',
      }}>
      {n > 9 ? '9+' : n}
    </span>
  );
}

/** ►►► **Hier beginnt ein Bereich** – eine Haarlinie mit dem Mikro-Label in der Mitte
 *  (Stammdaten, Zeiterfassung); daneben die Zahl, wenn darin etwas zu tun ist. */
export function SectionSep({ label, todo, anchor, tip }: {
  label: string; todo?: TodoItem[]; anchor?: string;
  /** Was der Bereich ist – im Hover am Wort, nicht als Zeile darunter. */
  tip?: string;
}) {
  return (
    <div role="separator" aria-label={label} data-todo={anchor} style={{
      ...MICRO_LABEL, color: 'var(--fg-3)', display: 'flex', alignItems: 'center', gap: 12,
      margin: '8px 0 -4px', scrollMarginTop: 16,
    }}>
      <span style={{ flex: 1, height: 1, background: 'var(--border-1)' }} />
      <span {...(tip ? { 'data-tip': tip } : {})}
        style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        {label}{todo && <TodoChip items={todo} />}
      </span>
      <span style={{ flex: 1, height: 1, background: 'var(--border-1)' }} />
    </div>
  );
}

/**
 * **Das Symbol eines Datensatzes — EINE Komponente für Feed und Detail-Kopf.** Alles aus
 * `TYPE_META`, nur die Grösse variiert; ein Benutzer ist rund. Die Abweichung ist ein
 * Zeichen am Symbol, kein Textlabel.
 */
export function RecordIcon({ type, size, photoUrl, initials, deviation, own, todo, onTodo }: {
  type: ErpRecordType;
  size: number;
  photoUrl?: string | null;
  initials?: string;
  deviation?: boolean;
  /** Eine **unserer** Gesellschaften – dieselbe Form wie die Abweichung: ein Zeichen
   *  am Symbol, kein Text daneben. */
  own?: boolean;
  /** **Was zu tun ist** (`lib/todo`) – Zahl oben rechts, rot wenn dringend, Hover je Abschnitt. */
  todo?: Todo | null;
  /** Klick auf die Zahl (Kopf): zur ersten Stelle springen. */
  onTodo?: () => void;
}) {
  const meta = TYPE_META[type];
  const Icon = meta.icon;
  const round = type === 'user';
  const mark = Math.max(14, Math.round(size * 0.4));
  return (
    <div style={{ position: 'relative', width: size, height: size, flex: 'none' }}>
      <div style={{
        width: '100%', height: '100%', overflow: 'hidden',
        borderRadius: round ? '50%' : 'var(--r-md)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        background: photoUrl ? 'transparent' : meta.bg,
        color: meta.fg,
        font: `700 ${Math.round(size * 0.34)}px var(--font-body)`,
      }}>
        {photoUrl
          // eslint-disable-next-line @next/next/no-img-element
          ? <img src={photoUrl} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
          : initials || <Icon size={Math.round(size * 0.46)} />}
      </div>
      {own && (
        <IconMark corner="bottom" size={mark} bg="var(--accent)"
          tip="Eigenes Unternehmen – eine unserer Gesellschaften">
          <Home size={Math.round(mark * 0.62)} />
        </IconMark>
      )}
      {deviation && (
        <IconMark corner="bottom" size={mark} bg="var(--warning)"
          tip="Abweichung – dieser Auftrag hat Einzelinstanzen aus einem laufenden Auftrag übernommen">
          <GitBranch size={Math.round(mark * 0.62)} />
        </IconMark>
      )}
      {!!todo?.count && (
        <IconMark corner="top" size={mark} list onClick={onTodo}
          bg={todo.red ? 'var(--danger)' : 'var(--warning)'} tip={todoTip(todo.items)}>
          {todo.count > 9 ? '9+' : todo.count}
        </IconMark>
      )}
    </div>
  );
}

/**
 * **Der EINE Kopf jedes Datensatz-Fensters** – dieselbe Aussage wie im Feed:
 *
 *     [Symbol]  TYP (Eyebrow)
 *               **Name**
 *               Objektnummer · Symbol-Aktionen · Status-Aktionen        [Status rechts]
 */
export function DetailHeader({
  type, photoUrl, initials, deviation, own, todo, title, placeholder = 'Ohne Bezeichnung',
  objectId, objectIdText, objectIdHint, actions, status, right, onBack, children, tabs,
}: {
  /** **Der Datensatztyp — und sonst nichts**: Symbol, Farbe und Eyebrow aus `TYPE_META`. */
  type: ErpRecordType;
  /** Rundes Foto statt des Symbol-Kastens (Benutzer). Die Geometrie steht hier. */
  photoUrl?: string | null;
  /** Fällt das Foto weg: Initialen im selben runden Kasten. */
  initials?: string;
  /** **Abweichung** – ein Zeichen am Symbol, siehe `RecordIcon`. */
  deviation?: boolean;
  /** **Eigenes Unternehmen** – ein Zeichen am Symbol wie die Abweichung. */
  own?: boolean;
  /** **Was zu tun ist** – die Zahl am Symbol, siehe `RecordIcon`; ein Klick springt hin. */
  todo?: Todo | null;
  /** `null` = dieser Datensatz hat (noch) keinen Namen → Platzhalter, kursiv. */
  title: string | null;
  placeholder?: string;
  objectId?: number | null;
  /** Ersetzt die formatierte Objektnummer (z. B. «—» beim Anlegen, solange es sie nicht gibt). */
  objectIdText?: string;
  /** Erklärung dazu – im **Hover**, nicht in der Fläche. */
  objectIdHint?: string;
  /** Symbol-/Status-Aktionen – stehen bei der Objektnummer. */
  actions?: ReactNode;
  /** Der Zustand – **immer** als `StatusBadge`, überall gleich. */
  status?: StatusCfg;
  /** Rechte Spalte NEBEN dem Status (Speicher-Anzeige, «Abbrechen» beim Anlegen). */
  right?: ReactNode;
  onBack?: () => void;
  /** Banner unter der Kopfzeile. */
  children?: ReactNode;
  /** Die **Reiter-Zeile** – ein eigener Slot: mit Reitern liegt der Aktiv-Balken auf der
   *  Kopf-Haarlinie, ohne setzt der Kopf seinen Fussabstand selbst. */
  tabs?: ReactNode;
}) {
  const meta = TYPE_META[type];
  return (
    <div style={{ ...DH.head, paddingBottom: tabs ? 0 : 14 }}>
      {onBack && (
        <button onClick={onBack} className="flex items-center gap-1 text-sm mb-3 md:hidden" style={{ color: 'var(--accent)' }}>
          <ArrowLeft size={15} /> Zurück
        </button>
      )}
      <div style={DH.top}>
        <RecordIcon type={type} size={56} photoUrl={photoUrl} initials={initials}
          deviation={deviation} own={own} todo={todo}
          onTodo={todo ? () => jumpToTodo(todo.items) : undefined} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={DH.eyebrow}>{meta.label}</div>
          <h1 style={{ ...DH.title, ...(title ? null : DH.titleEmpty) }}>{title ?? placeholder}</h1>
          <div style={DH.sub}>
            <span style={DH.subN} data-tip={objectIdHint} data-tip-pos="bottom">
              {objectIdText ?? formatObjectId(objectId)}
            </span>
            {actions}
          </div>
        </div>
        {(right || status) && (
          <div style={DH.right}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              {right}
              {/* Etwas grösser als im Feed: eine der drei Hauptaussagen des Kopfs. */}
              {status && <StatusBadge cfg={status} size={11.5} />}
            </div>
          </div>
        )}
      </div>
      {children}
      {tabs && <div style={{ marginTop: 14 }}>{tabs}</div>}
    </div>
  );
}

/** Status-Aktion in der Kopf-Aktionszeile – **exakt so hoch wie die 28-px-Symbolknöpfe**,
 *  damit die Zeile nicht springt. */
export function HeaderAction({ label, tone = 'primary', hint, disabled, onClick }: {
  label: string; tone?: StatusTone; hint?: string; disabled?: boolean; onClick: () => void;
}) {
  return (
    <button type="button"
      className={`erp-actbtn ${tone === 'primary' ? 'erp-actbtn-primary' : 'erp-actbtn-neutral'}`}
      style={{ height: 28, padding: '0 12px', fontSize: 12 }}
      data-tip={hint} data-tip-pos="bottom"
      disabled={disabled} onClick={onClick}>
      {label}
    </button>
  );
}

/** Trennstrich zwischen Aktionsgruppen im Kopf (Objektnummer | Symbole | Status-Aktion). */
export function HeaderSep() {
  return <span style={DH.idsep} />;
}

export const DH: Record<string, React.CSSProperties> = {
  head: {
    // paddingBottom 0 mit Reitern (Aktiv-Balken auf der Haarlinie); ohne setzt `DetailHeader` ihn.
    padding: '20px clamp(14px, 4vw, 28px) 0', borderBottom: '1px solid var(--border-1)',
    background: 'rgba(255,255,255,.93)', backdropFilter: 'blur(8px)', flexShrink: 0,
  },
  top: { display: 'flex', alignItems: 'flex-start', gap: 'clamp(10px, 3vw, 16px)', flexWrap: 'wrap' },
  eyebrow: {
    font: 'var(--overline)', letterSpacing: 'var(--tracking-overline)',
    textTransform: 'uppercase', color: 'var(--inexxio-red)', marginBottom: 6,
  },
  title: {
    // **Einzelangaben, KEINE `font`-Kurzschreibweise**: fällt die Überschreibung `titleEmpty`
    // weg, setzt React die Longhand auf `''` – aus einer Kurzschreibweise käme der Wert nicht zurück.
    fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 26,
    letterSpacing: '-.03em', margin: 0, lineHeight: 1.05,
    color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  titleEmpty: { color: 'var(--fg-4)', fontStyle: 'italic', fontWeight: 700 },
  sub: { display: 'flex', alignItems: 'center', gap: 9, marginTop: 9, flexWrap: 'wrap' },
  subN: { fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-3)', fontSize: 13 },
  idsep: { width: 1, height: 16, background: 'var(--border-2)', margin: '0 2px' },
  right: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 12, flex: 'none' },
};
