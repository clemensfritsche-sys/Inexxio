'use client';

import { useEffect, useRef, useState } from 'react';
import type { ElementType, ReactNode } from 'react';
import { AlertCircle, ArrowLeft, ChevronDown, GitBranch, Search, Info, Loader2, CheckCircle2, Sparkles, ExternalLink } from 'lucide-react';
import type { StatusTone, StatusCfg } from '@/lib/status-flow';
import { TYPE_META } from '@/lib/erp-record';
import type { ErpRecordType } from '@/types';
import { formatObjectId } from '@/lib/utils';

// ─── Karte: der Container eines Formular-Abschnitts ──────────────────────────

/**
 * Symbol + Titel + optionaler rechter Slot (Speicher-Anzeige), darunter der Inhalt –
 * die Anatomie der Profileinstellungen, die der ERP-Benutzer seit Notiz #294 spiegelt
 * und der Unternehmens-Datensatz seit Runde 21.
 *
 * Sie stand vorher lokal in `user-detail.tsx`; hier ist sie EINE Stelle, damit die
 * beiden Ansichten nicht wieder auseinanderlaufen. `icon` ist optional: eine Überschrift
 * braucht kein Symbol, wenn sie die Sache schon benennt (Notizen #308/#311).
 */
export function Card({ icon: Icon, title, right, children }: {
  icon?: ElementType; title: string; right?: ReactNode; children: ReactNode;
}) {
  return (
    <div style={{ background: '#fff', border: '1px solid var(--border-1)', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    gap: 12, padding: '18px 24px', borderBottom: '1px solid var(--border-1)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          {Icon && <Icon style={{ width: 16, height: 16, color: 'var(--fg-3)', flex: 'none' }} />}
          <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-1)', margin: 0 }}>{title}</h2>
        </div>
        {right}
      </div>
      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 20 }}>{children}</div>
    </div>
  );
}

export const TILE: Record<string, React.CSSProperties> = {
  box: {
    background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)',
    padding: '18px 20px', display: 'flex', gap: 14, alignItems: 'flex-start',
    width: '100%', font: 'inherit', textAlign: 'left',
  },
  ico: {
    width: 40, height: 40, borderRadius: 'var(--r-sm)', background: 'var(--bg-2)',
    color: 'var(--fg-2)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none',
  },
  k: {
    font: '600 11.5px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.07em',
    color: 'var(--fg-3)', display: 'flex', alignItems: 'center', gap: 6,
  },
  hint: { width: 13, height: 13, color: 'var(--fg-4)', cursor: 'help', display: 'inline-flex' },
  v: {
    font: '700 18px var(--font-body)', color: 'var(--fg-1)', marginTop: 6,
    fontVariantNumeric: 'tabular-nums', display: 'flex', alignItems: 'center', gap: 8,
    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  sub: { font: '500 13px var(--font-body)', color: 'var(--fg-3)', marginTop: 3, fontVariantNumeric: 'tabular-nums' },
  goto: { marginLeft: 'auto', color: 'var(--accent)', display: 'flex', alignSelf: 'center' },
  /** Volle Breite im Kachel-Raster (Standort-Karten, Spezifikation). */
  wide: { gridColumn: '1 / -1' },
};

// ─── Spezifikations-Karte: die Lese-Ansicht eines Datensatzes ────────────────
//
// EINE Karte, in der die Angaben eines Datensatzes stehen – warme Fläche, Haarlinie,
// sanfter Schatten, mit dem Schirm wachsende Polsterung. Sie stand bisher nur im
// Artikel; die Auftragsspezifikation trug stattdessen lose Kacheln nebeneinander
// (Notiz #267). Jetzt teilen sich beide dieselbe Anatomie – Karte + Werteraster +
// Lesefeld – damit die Spezifikation eines Auftrags aussieht wie die eines Artikels.

/**
 * ►►► **Die Breite eines Datensatz-Fensters — EINE Zahl für alle.** ◄◄◄ (Notiz #763)
 *
 * Vorher gab es drei Antworten: Artikel und Instanz begrenzten auf 880, das Unternehmen
 * auf 760, der **Benutzer auf gar nichts** – sein Formular lief auf einem breiten Schirm
 * über die volle Fensterbreite auseinander, und eine Zeile wurde unlesbar lang.
 *
 * Die einzige Ausnahme ist das **Prozessbild**: es hat drei Spuren und misst seine Breite
 * selbst (`flow-line.metricsFor`). Das ist kein Ausrutscher, sondern eine andere Sache –
 * ein Formular liest man in einer Spalte, ein Diagramm braucht seine Bahnen.
 */
export const DETAIL_MAXW = 880;

/**
 * Der Inhalt eines Datensatz-Reiters: **zentriert, auf {@link DETAIL_MAXW} begrenzt**.
 *
 * Eine Komponente statt eines wiederholten `style` – sonst ist die nächste Ansicht wieder
 * die, die es vergisst.
 */
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
    background: '#fff', border: '1px solid var(--border-1)', borderRadius: 'var(--r-lg)',
    boxShadow: 'var(--shadow-sm)', padding: 'clamp(16px, 4vw, 30px)',
  } as React.CSSProperties,
  /** auto-fit-Werteraster; `min(100%, …)` kollabiert auf Mobile sauber. */
  grid: {
    display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(100%, 240px), 1fr))',
    gap: '22px clamp(18px, 4vw, 40px)',
  } as React.CSSProperties,
};

/**
 * **Der Kopf einer Spezifikations-Karte**: grosses getöntes Symbol + Titel + optionaler
 * rechter Slot. Stand lokal im Artikel-Detail und war dort auf «Spezifikation»
 * festgenagelt – womit jede zweite Ansicht (Bestand, Instanz) sich einen eigenen Kopf
 * hätte bauen müssen und die Karten nur noch *ähnlich* ausgesehen hätten.
 */
export function SpecHead({ icon: Icon, title, right }: {
  icon: ElementType; title: string; right?: ReactNode;
}) {
  // **Auf jede Überschrift folgt eine Haarlinie** (Notiz #762). Vorher trug nur der
  // Abschnitts-Kopf eine, der Karten-Kopf nicht – dieselbe Sache in zwei Formen, und man
  // sah der Karte an, dass ihre Gliederung aus zwei Zeiten stammt.
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 12,
      paddingBottom: 14, marginBottom: 22, borderBottom: '1px solid var(--border-1)',
    }}>
      <span style={SPEC_ICO}><Icon size={17} /></span>
      <h2 style={{ font: '800 18px var(--font-display)', letterSpacing: '-.01em', margin: 0, flex: 1, color: 'var(--fg-1)' }}>{title}</h2>
      {right && <span style={{ flex: 'none' }}>{right}</span>}
    </div>
  );
}

/**
 * Unterabschnitt einer Spezifikations-Karte: 32-px-Symbol + Titel über einer Haarlinie,
 * darunter das Werte-Raster. Gliedert eine Karte, ohne eine zweite Karte zu öffnen.
 */
export function SpecSection({ icon: Icon, title, right, grid = true, children }: {
  icon: ElementType; title: string; right?: ReactNode; grid?: boolean; children: ReactNode;
}) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 11, paddingBottom: 14, margin: '18px 0 20px', borderBottom: '1px solid var(--border-1)' }}>
        <span style={{ ...SPEC_ICO, width: 32, height: 32 }}><Icon size={16} /></span>
        <h3 style={{ font: '800 16px var(--font-display)', letterSpacing: '-.01em', margin: 0, flex: 1, color: 'var(--fg-1)' }}>{title}</h3>
        {right && <span style={{ flex: 'none' }}>{right}</span>}
      </div>
      <div style={grid ? SPEC.grid : undefined}>{children}</div>
    </div>
  );
}

const SPEC_ICO: React.CSSProperties = {
  width: 34, height: 34, borderRadius: 'var(--r-sm)', background: '#F4EBDD', color: '#9A7238',
  display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none',
};

function linkHost(href: string): string {
  try { return new URL(href).hostname.replace(/^www\./, ''); } catch { return href; }
}

/** Read-only-Feld: kleines Symbol + Versalien-Overline + kräftiger Wert. Optional
 *  Einheit/mono, Link (Host + Pfeil) oder ⓘ-Hinweis bei abgeleiteten Werten. */
export function ReadField({ icon: Icon, label, value, unit, mono, full, autoHint, spread, link }: {
  icon?: ElementType; label: string; value?: ReactNode; unit?: string;
  mono?: boolean; full?: boolean; autoHint?: string; spread?: string; link?: string;
}) {
  return (
    <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start', gridColumn: full ? '1 / -1' : undefined }}>
      {Icon && (
        <span style={{ width: 22, height: 22, color: 'var(--fg-4)', display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none', marginTop: 2 }}>
          <Icon size={18} />
        </span>
      )}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ font: '700 11px var(--font-body)', textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--fg-4)', display: 'flex', alignItems: 'center', gap: 5 }}>
          {label}
          {autoHint && <span style={{ display: 'inline-flex', color: 'var(--fg-4)', cursor: 'help' }} data-tip={autoHint}><Sparkles size={12} /></span>}
        </div>
        {link ? (
          <a href={link} target="_blank" rel="noreferrer"
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginTop: 6, font: '600 14.5px var(--font-body)', color: 'var(--accent-ink)' }}>
            {linkHost(link)} <ExternalLink size={13} />
          </a>
        ) : (
          <div style={{ font: '600 15.5px var(--font-body)', color: 'var(--fg-1)', marginTop: 6, lineHeight: 1.35, overflowWrap: 'anywhere', ...(mono ? { fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', fontSize: 14.5 } : null) }}>
            {value}{unit && <span style={{ font: '500 13px var(--font-body)', color: 'var(--fg-3)', marginLeft: 3 }}>{unit}</span>}
          </div>
        )}
        {/* Spanne: bewusst leiser als der Median – sie ordnet ein, sie ist nicht die Aussage. */}
        {spread && (
          <div style={{ marginTop: 4, font: '500 11.5px var(--font-body)', color: 'var(--fg-4)', fontVariantNumeric: 'tabular-nums' }}>
            {spread}
          </div>
        )}
      </div>
    </div>
  );
}

// ─── Hover-Hilfen: Erklärungen/Infotexte gehören in den Hover, nicht in die Fläche ──

/** Leichter Hover-/Fokus-Tooltip (dunkle Sprechblase). Trägt erklärende Texte, ohne
 *  die Oberfläche zu fluten – «weniger ist mehr». */
export function Tooltip({ text, children, side = 'top' }: {
  text: string; children: ReactNode; side?: 'top' | 'bottom';
}) {
  const [show, setShow] = useState(false);
  return (
    <span style={{ position: 'relative', display: 'inline-flex', alignItems: 'center' }}
      onMouseEnter={() => setShow(true)} onMouseLeave={() => setShow(false)}
      onFocus={() => setShow(true)} onBlur={() => setShow(false)}>
      {children}
      {show && (
        <span role="tooltip" style={{
          position: 'absolute', zIndex: 50, left: '50%', transform: 'translateX(-50%)',
          ...(side === 'top' ? { bottom: '100%', marginBottom: 7 } : { top: '100%', marginTop: 7 }),
          padding: '7px 10px', borderRadius: 7, background: '#0f172a', color: '#fff',
          fontSize: 11, fontWeight: 500, lineHeight: 1.4, width: 'max-content', maxWidth: 240,
          textAlign: 'left', whiteSpace: 'normal', boxShadow: '0 6px 18px rgba(0,0,0,0.22)', pointerEvents: 'none',
        }}>{text}</span>
      )}
    </span>
  );
}

/** Dezentes ⓘ-Symbol; die Erklärung erscheint im Hover. Ersetzt Infotext-Blöcke. */
export function InfoHint({ text, side }: { text: string; side?: 'top' | 'bottom' }) {
  return (
    <Tooltip text={text} side={side}>
      <Info size={13} style={{ color: '#cbd5e1', cursor: 'help', flexShrink: 0 }} />
    </Tooltip>
  );
}

/** Einheitlicher Abschnitts-Titel (Symbol + Versalien-Label + optional ⓘ-Hover + rechte Slot). */
export function SectionTitle({ icon: Icon, info, right, children }: {
  icon?: ElementType; info?: string; right?: ReactNode; children: ReactNode;
}) {
  return (
    <div
      data-fb-section={typeof children === 'string' ? children : undefined}
      style={{ display: 'flex', alignItems: 'center', gap: 6, margin: '4px 2px 8px' }}
    >
      {Icon && <Icon size={13} style={{ color: 'var(--fg-4)' }} />}
      <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#64748b' }}>{children}</span>
      {info && <InfoHint text={info} />}
      {right && <span style={{ marginLeft: 'auto' }}>{right}</span>}
    </div>
  );
}

/** Einheitlicher Prozessschritt-Kopf: getöntes Symbol + Titel + optional ⓘ-Hover + rechter
 *  Slot (z. B. Status). EIN Look über alle Schritt-Panels (Bewegung/Ressource/…). */
export function PanelHeader({ icon: Icon, title, tone = 'var(--accent)', info, right }: {
  icon: ElementType; title: string; tone?: string; info?: string; right?: ReactNode;
}) {
  return (
    // `data-fb-section` benennt den Abschnitt für eine Testnotiz: im Prozess-Editor
    // sagt «Bewegung» mehr als jede Positions-Kette im Selektor.
    <div data-fb-section={title} style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ width: 26, height: 26, borderRadius: 7, flexShrink: 0, background: `${tone}14`, color: tone, display: 'inline-flex', alignItems: 'center', justifyContent: 'center' }}>
        <Icon size={15} />
      </span>
      <span style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>{title}</span>
      {info && <InfoHint text={info} />}
      {right && <span style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center' }}>{right}</span>}
    </div>
  );
}

export const inputCls = 'w-full px-2.5 py-1.5 text-sm rounded-md border bg-white outline-none focus:ring-2 focus:ring-accent focus:border-transparent transition-colors';

/**
 * **Schieber** für eine Wahl mit wenigen, einander ausschliessenden Optionen: EIN Gleis,
 * ein Reiter, der zur aktiven Option gleitet. Nebeneinanderstehende Knöpfe lassen offen,
 * dass sie sich ausschliessen – die Bewegung zeigt es ohne ein Wort Erklärung.
 *
 * `symbolOnly` blendet die Beschriftung aus (nur Symbol, Bedeutung im Hover) – für enge
 * Stellen, an denen das Wort ohnehin nur Platz füllt. Gesperrte Optionen bleiben sichtbar
 * und nennen ihren Grund ebenfalls im Hover.
 *
 * **Der Hover kommt sofort** (Testnotiz #618): über `data-tip` wie überall sonst im ERP,
 * nicht über `title`. Der native Browser-Tooltip wartet rund eine Sekunde – wo das Symbol
 * die Bedeutung allein nicht trägt, ist das genau die Sekunde, in der man ratlos ist. Weil
 * es hier an EINER Stelle steht, gilt es für jeden Umschalter im Haus.
 */
export function IconSwitch<T extends string>({ value, onChange, options, symbolOnly, labelActiveOnly }: {
  value: T; onChange: (v: T) => void;
  /** ``mark`` setzt einen dezenten Punkt an eine (nicht gewählte) Option – z. B. die
   *  abgeleitete Empfehlung: sie markiert sich selbst, statt einen Erklärsatz zu brauchen. */
  options: { value: T; icon: ElementType; label: string; hint?: string; disabled?: boolean; mark?: boolean }[];
  symbolOnly?: boolean;
  /** Nur die AKTIVE Option zeigt ihr Wort, die übrigen nur ihr Symbol – für Achsen mit
   *  vielen Werten (Mengeneinheit): man sieht auf einen Blick, was gilt, ohne dass sechs
   *  Wörter nebeneinander um Aufmerksamkeit ringen. */
  labelActiveOnly?: boolean;
}) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  const wrapRef = useRef<HTMLDivElement>(null);
  // Der gleitende Reiter wird **gemessen**, nicht gerechnet: sobald die Optionen
  // unterschiedlich breit sind (aktives Wort sichtbar, übrige nur Symbol), stimmt ein
  // «100/N %»-Raster nicht mehr.
  const [thumb, setThumb] = useState<{ left: number; width: number } | null>(null);
  useEffect(() => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const measure = () => {
      const el = wrap.querySelector<HTMLElement>(`[data-ix-idx="${index}"]`);
      if (el) setThumb({ left: el.offsetLeft, width: el.offsetWidth });
    };
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, [index, options.length, labelActiveOnly, symbolOnly]);

  return (
    // ``labelActiveOnly`` hat naturgemäss ungleich breite Optionen – dann soll sich der
    // Regler an seinen Inhalt schmiegen statt die ganze Spalte zu füllen (Notizen #224/#225).
    <div ref={wrapRef} style={{
      position: 'relative', display: symbolOnly || labelActiveOnly ? 'inline-flex' : 'flex',
      alignSelf: 'flex-start', maxWidth: '100%', flexWrap: 'wrap',
      padding: 3, borderRadius: 999, background: 'var(--bg-2)', border: '1px solid var(--border-1)',
    }}>
      <span aria-hidden style={{
        position: 'absolute', top: 3, bottom: 3,
        left: thumb ? thumb.left : 3, width: thumb ? thumb.width : 0,
        opacity: thumb ? 1 : 0,
        transition: 'left .18s cubic-bezier(.4,0,.2,1), width .18s cubic-bezier(.4,0,.2,1)',
        borderRadius: 999, background: '#fff', boxShadow: '0 1px 2px rgba(0,0,0,.12)',
      }} />
      {options.map((o, i) => {
        const active = o.value === value;
        const Icon = o.icon;
        const showLabel = !symbolOnly && (!labelActiveOnly || active);
        return (
          <button key={o.value} type="button" role="tab" aria-selected={active} data-ix-idx={i}
            aria-label={o.label}
            // Der **Name** wächst im Hover heraus (siehe unten); die längere **Erklärung**
            // bleibt der Tooltip – aber nur, wenn sie mehr sagt als der Name.
            data-tip={o.hint && o.hint !== o.label ? o.hint : undefined} data-tip-pos="bottom"
            className="ix-seg"
            onClick={o.disabled ? undefined : () => onChange(o.value)} disabled={o.disabled}
            style={{
              position: 'relative', flex: labelActiveOnly ? '0 0 auto' : (symbolOnly ? undefined : 1),
              display: 'inline-flex', alignItems: 'center',
              justifyContent: 'center', gap: 6, padding: symbolOnly ? '6px 16px' : '7px 12px',
              border: 'none', background: 'none', borderRadius: 999,
              font: '600 12px var(--font-body)', cursor: o.disabled ? 'not-allowed' : 'pointer',
              opacity: o.disabled ? 0.4 : 1, transition: 'color .18s',
              color: active ? 'var(--accent-ink)' : 'var(--fg-3)', whiteSpace: 'nowrap',
            }}>
            <Icon size={14} />
            {/* **Der Buttonname erscheint daneben** (Testnotiz #624) – dieselbe Geste wie an
                der Palette. Wo das Wort ohnehin steht (aktive Option, voller Modus), gibt es
                nichts einzublenden; sonst wächst es im Hover heraus. Der gleitende Reiter
                wird ohnehin gemessen (ResizeObserver), also folgt er der neuen Breite. */}
            {showLabel ? o.label : (
              <span className="ix-seg-label"><span>{o.label}</span></span>
            )}
            {o.mark && !active && <span aria-hidden style={{ width: 5, height: 5, borderRadius: 999, background: 'var(--accent)', flexShrink: 0 }} />}
          </button>
        );
      })}
    </div>
  );
}

/**
 * **Der EINE Kopf jedes Datensatz-Fensters** (Notiz #242).
 *
 * Alle Detail-Ansichten sahen sich ähnlich, aber keine zwei gleich: mal 26 px Titel, mal
 * 28 px, mal klebend, mal nicht, beim Benutzer sogar ein ganz anderes Layout (runder
 * Avatar, «Obj.-Nr.»-Block rechts). Diese Anatomie ist jetzt verbindlich – und sie ist
 * dieselbe Aussage wie im Feed:
 *
 *     [Symbol]  TYP (Eyebrow)
 *               **Name**
 *               Objektnummer · Symbol-Aktionen · Status-Aktionen        [Status rechts]
 *
 * Der Typ steht als Eyebrow, der **Name** als Titel, die Objektnummer als monospaced
 * Zeile darunter – und die Aktionen dort, wo sie hingehören: bei der Objektnummer. Rechts
 * bleibt allein der Zustand (plus optional die Speicher-Anzeige).
 */
/**
 * **Das Symbol eines Datensatzes — EINE Komponente für Feed und Detail-Kopf** (#697/#699).
 *
 * Symbol, Farbfamilie und Form kommen aus `TYPE_META`; nur die **Grösse** unterscheidet
 * die beiden Orte. Ein Benutzer ist rund (ein Foto in einem Quadrat sieht falsch aus) –
 * diese eine Formregel steht **hier**, abgeleitet aus dem Typ, damit keine Aufrufstelle
 * sie neu erfinden kann.
 *
 * **Die Abweichung ist ein Zeichen am Symbol, kein Textlabel** (#699). Sie ist keine
 * Eigenschaft des Auftrags, sondern eine Auskunft über die Herkunft seiner Stücke – und
 * weil Feed und Kopf dieselbe Komponente benutzen, können sie nicht auseinanderlaufen
 * (genau der Fehler aus #688).
 */
export function RecordIcon({ type, size, photoUrl, initials, deviation }: {
  type: ErpRecordType;
  size: number;
  photoUrl?: string | null;
  initials?: string;
  deviation?: boolean;
}) {
  const meta = TYPE_META[type];
  const Icon = meta.icon;
  const round = type === 'user';
  const mark = Math.max(11, Math.round(size * 0.34));
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
      {deviation && (
        <span
          style={{
            position: 'absolute', right: -2, bottom: -2,
            width: mark, height: mark, borderRadius: 999,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            background: 'var(--warning)', color: '#fff',
            // Der Ring hebt das Zeichen von jeder Symbolfarbe ab – ohne ihn verschwände
            // es auf einer getönten Fläche.
            boxShadow: '0 0 0 2px var(--bg-1)',
          }}
          data-tip="Abweichung – dieser Auftrag hat Einzelinstanzen aus einem laufenden Auftrag übernommen"
        >
          <GitBranch size={Math.round(mark * 0.62)} />
        </span>
      )}
    </div>
  );
}

export function DetailHeader({
  type, photoUrl, initials, deviation, title, placeholder = 'Ohne Bezeichnung',
  objectId, objectIdText, objectIdHint, actions, status, right, onBack, children, tabs,
}: {
  /**
   * **Der Datensatztyp — und sonst nichts** (Testnotiz #697).
   *
   * Symbol, Farbfamilie und Eyebrow kommen aus der EINEN Quelle (`lib/erp-record.TYPE_META`)
   * und werden hier aufgelöst. Vorher reichte jede Ansicht sie einzeln herein: drei von
   * fünf mit hart getippten Hex-Werten und einem zweiten Mal ausgeschriebenem Namen –
   * dieselbe Aussage an zwei Orten, und der Feed konnte davon abweichen, ohne dass es
   * jemandem auffiel. Was **variieren darf, ist der Inhalt**; Layout, Raster, Farben,
   * Schriften und Logik dürfen es nicht, also lassen sie sich hier nicht mehr übergeben.
   */
  type: ErpRecordType;
  /** Rundes Foto statt des Symbol-Kastens (Benutzer). Die Geometrie steht hier. */
  photoUrl?: string | null;
  /** Fällt das Foto weg: Initialen im selben runden Kasten. */
  initials?: string;
  /** **Abweichung** – ein Zeichen am Symbol, siehe `RecordIcon` (#699). */
  deviation?: boolean;
  /** `null` = dieser Datensatz hat (noch) keinen Namen → Platzhalter, kursiv. */
  title: string | null;
  placeholder?: string;
  objectId?: number | null;
  /** Ersetzt die formatierte Objektnummer (z. B. «—» beim Anlegen, solange es sie nicht gibt). */
  objectIdText?: string;
  /** Erklärung dazu – im **Hover**, nicht in der Fläche (Notiz #389). */
  objectIdHint?: string;
  /** Symbol-/Status-Aktionen – stehen bei der Objektnummer. */
  actions?: ReactNode;
  /** Der Zustand – **immer** als `StatusBadge` gerendert, damit er überall gleich gross
   *  und gleich gesetzt ist (Notizen #264/#268); die Aufrufer können nicht abweichen. */
  status?: StatusCfg;
  /** Rechte Spalte NEBEN dem Status (Speicher-Anzeige, «Abbrechen» beim Anlegen). */
  right?: ReactNode;
  onBack?: () => void;
  /** Banner unter der Kopfzeile. */
  children?: ReactNode;
  /**
   * Die **Reiter-Zeile** – Teil der Kopf-Anatomie, nicht beliebiges Kind (Notiz #595).
   *
   * Nur ihretwegen hat der Kopf `paddingBottom: 0`: der rote Aktiv-Balken eines Reiters
   * soll genau auf der Kopf-Haarlinie liegen (#290). Wo es **keine** Reiter gibt – der
   * Lieferant sieht keine –, klebte die Objektnummer-Zeile darum ohne jeden Abstand auf
   * der Linie. Als eigener Slot entscheidet der Kopf das selbst, und die Aufrufer können
   * beim Abstand nicht mehr auseinanderlaufen (sie trugen 10 px und 16 px).
   */
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
          deviation={deviation} />
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
              {/* Etwas grösser als im Feed (Notiz #359): im Kopf ist der Zustand eine der
                  drei Hauptaussagen (Typ · Name · Zustand) und darf neben einem 22-px-Titel
                  nicht wie eine Fussnote wirken. Weil ihn NUR diese eine Stelle rendert,
                  gilt die Grösse für jeden Datensatztyp gleich. */}
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

/**
 * Status-Aktion in der Kopf-Aktionszeile («Freigeben», «Reaktivieren»).
 *
 * Sie steht neben den 28-px-Symbolknöpfen und ist darum **exakt so hoch wie sie** (Notiz
 * #286): war sie höher, wuchs die ganze Zeile in dem Moment, in dem die Aktion erschien –
 * und schrumpfte wieder, sobald sie wegfiel. Beide Detail-Ansichten (Artikel, Auftrag)
 * hatten dieselbe Zeile zweimal ausgeschrieben; jetzt gibt es eine Stelle.
 */
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
    // paddingBottom 0 **mit** Reitern: sie sitzen bündig an der Unterkante, sodass der rote
    // Aktiv-Balken (2px border-bottom je Reiter) genau auf der Kopf-Haarlinie liegt – nicht
    // mehr 20px darüber schwebend (Notiz #290). Ohne Reiter setzt `DetailHeader` den
    // Fussabstand selbst (Notiz #595); der Wert hier ist darum nur der Ausgangspunkt.
    padding: '20px clamp(14px, 4vw, 28px) 0', borderBottom: '1px solid var(--border-1)',
    background: 'rgba(255,255,255,.93)', backdropFilter: 'blur(8px)', flexShrink: 0,
  },
  top: { display: 'flex', alignItems: 'flex-start', gap: 'clamp(10px, 3vw, 16px)', flexWrap: 'wrap' },
  eyebrow: {
    font: 'var(--overline)', letterSpacing: 'var(--tracking-overline)',
    textTransform: 'uppercase', color: 'var(--inexxio-red)', marginBottom: 6,
  },
  title: {
    // **Einzelangaben, KEINE `font`-Kurzschreibweise** – und das ist kein Geschmack.
    //
    // Der Titel wird konditional überschrieben (`titleEmpty` setzt `fontWeight`/
    // `fontStyle` für den Platzhalter). Fällt diese Überschreibung später weg – beim
    // Auftrag passiert genau das, weil er als einziger Datensatztyp ohne Namen startet
    // und ihn nachlädt –, entfernt React die Longhand, indem es sie auf `''` setzt. Der
    // Wert aus der Kurzschreibweise kommt dabei **nicht** zurück: sie hat ihn in die
    // Deklaration geschrieben, und das Löschen der Longhand löscht ihn daraus. Übrig
    // bleibt der Initialwert – 400 statt 800. Als Einzelangabe steht 800 dagegen in
    // jedem Zustand im Objekt und wird zurückgeschrieben.
    fontFamily: 'var(--font-display)', fontWeight: 800, fontSize: 26,
    letterSpacing: '-.03em', margin: 0, lineHeight: 1.05,
    color: 'var(--fg-1)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
  },
  titleEmpty: { color: 'var(--fg-4)', fontStyle: 'italic', fontWeight: 700 },
  sub: { display: 'flex', alignItems: 'center', gap: 9, marginTop: 9, flexWrap: 'wrap' },
  subN: { fontFamily: 'var(--font-mono)', fontVariantNumeric: 'tabular-nums', color: 'var(--fg-3)', fontSize: 13 },
  idsep: { width: 1, height: 16, background: 'var(--border-2)', margin: '0 2px' },
  right: { display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 12, flex: 'none' },
};

/**
 * **Dialog** – die EINE Fensterform für eine Entscheidung. Klick daneben und `Esc`
 * schliessen; ein × wäre ein zweiter Weg für dasselbe, ein «Abbrechen» ein dritter
 * (Notizen #153/#154). Der Inhalt ist die Entscheidung, sonst nichts.
 */
export function Dialog({ icon: Icon, title, tone = 'var(--warning)', width = 520, onClose, children }: {
  icon?: ElementType; title: string; tone?: string; width?: number;
  onClose: () => void; children: ReactNode;
}) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  return (
    <div onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'rgba(15,23,42,.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60, padding: 16 }}>
      <div onClick={(e) => e.stopPropagation()}
        style={{ background: '#fff', borderRadius: 'var(--r-lg)', width: `min(${width}px, 100%)`, maxHeight: '86vh', overflowY: 'auto', boxShadow: 'var(--shadow-lg)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px', borderBottom: '1px solid var(--border-1)' }}>
          {Icon && <Icon size={18} style={{ color: tone }} />}
          <span style={{ font: '800 15px var(--font-display)', color: 'var(--fg-1)' }}>{title}</span>
        </div>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>{children}</div>
      </div>
    </div>
  );
}

/**
 * **Eine Palette: Symbole in einer Reihe.** Mehr nicht – der Name steht im Hover des
 * einzelnen Symbols (#518). Der Baustein bleibt, damit dieselbe Geste an allen drei
 * Stellen (Module · Erfassungsfelder · Unterdeckung) gleich aussieht.
 */
export function Palette({ children, style }: {
  children: React.ReactNode; style?: React.CSSProperties;
}) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', ...style }}>
      {children}
    </div>
  );
}

/**
 * Ein Weg im Dialog – **der Klick IST die Ausführung**, keine zweite Bestätigung
 * darunter (Notiz #155). Nichts ist vorausgewählt oder hervorgehoben: die Wege sind
 * gleichwertig, die Entscheidung trifft der Mensch und nicht die Gestaltung (#152).
 */
export function ChoiceButton({ icon: Icon, tone, title, text, disabled, onClick }: {
  /** Symbol des Weges – auf einen Blick erkennbar, noch vor dem Lesen (Notiz #284). */
  icon?: ElementType;
  /** Farbe des Symbols (z. B. `var(--danger)` für den endgültigen Weg). */
  tone?: string;
  title: string; text?: string; disabled?: boolean; onClick: () => void;
}) {
  return (
    <button type="button" disabled={disabled} onClick={onClick}
      style={{
        display: 'flex', alignItems: 'center', gap: 12, width: '100%',
        textAlign: 'left', padding: '12px 14px', borderRadius: 'var(--r-md)', cursor: disabled ? 'default' : 'pointer',
        border: '1px solid var(--border-1)', background: '#fff', opacity: disabled ? .6 : 1,
      }}>
      {Icon && (
        <span style={{
          width: 34, height: 34, borderRadius: 'var(--r-sm)', flex: 'none',
          background: 'var(--bg-2)', color: tone ?? 'var(--fg-2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <Icon size={17} />
        </span>
      )}
      <span style={{ minWidth: 0 }}>
        <span style={{ display: 'block', font: '700 13.5px var(--font-body)', color: 'var(--fg-1)' }}>{title}</span>
        {text && <span style={{ display: 'block', fontSize: 12, color: 'var(--fg-3)', marginTop: 2 }}>{text}</span>}
      </span>
    </button>
  );
}

/**
 * Die EINE Regel für Zahlenfelder (Mengen, Perioden, Prozente): nur Ziffern, optional
 * EIN Dezimaltrenner. Das Komma wird zum Punkt – wer «2,5» tippt, meint 2.5, und das
 * Backend rechnet mit Punkt.
 *
 * Bewusst eine Filterfunktion statt `<input type="number">`: dessen Spinner, Scroll-Rad
 * und länderabhängige Trennzeichen sind in Formularen mehr Ärger als Hilfe – und ein
 * `type="number"` liefert bei ungültiger Eingabe einen LEEREN Wert, wodurch getippte
 * Zeichen spurlos verschwinden. Hier bleibt der Wert immer sichtbar und sauber.
 */
export function numericOnly(
  raw: string, opts: { decimals?: boolean; signed?: boolean } = {},
): string {
  const { decimals = true, signed = false } = opts;
  // **Ein Minus ist an genau einer Stelle richtig: ganz vorn.** Wo negative Beträge eine
  // Aussage sind (eine Gutschrift ist eine negative Rechnung), muss man es tippen können
  // – aber nicht mittendrin, und nicht zweimal.
  const minus = signed && raw.trimStart().startsWith('-') ? '-' : '';
  const cleaned = raw.replace(',', '.').replace(/[^\d.]/g, '');
  if (!decimals) return minus + cleaned.replace(/\./g, '');
  const [head, ...rest] = cleaned.split('.');       // höchstens EIN Trenner
  return minus + (rest.length ? `${head}.${rest.join('')}` : head);
}

/** Tastatur/Verhalten passend zum Zahlenfeld (Mobile: Ziffernblock). */
export const numericInputProps = { inputMode: 'decimal' as const, autoComplete: 'off' };

export function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-4)', marginBottom: 4 }}>
      {children}{required && <span style={{ color: '#dc2626' }}> *</span>}
    </div>
  );
}

export function ErrorText({ msg }: { msg: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, fontSize: 11, color: '#dc2626' }}>
      <AlertCircle size={11} /> {msg}
    </div>
  );
}

/**
 * **Eine Zeile der Auswahl – und ihre Form ist die des Scanners.**
 *
 * `label` ist die Hauptangabe (bei einem Datensatz seine Objektnummer), `name` die leise
 * daneben. Getrennt, weil dieselbe Zeile in **beiden** Oberflächen gleich aussehen soll:
 * `100000123 · Regal B`, die Nummer tabellarisch, der Name gedämpft. Als ein fertiger
 * String liesse sich das nicht auszeichnen – und der Dialog sähe anders aus als das Feld,
 * aus dem er kommt.
 *
 * Ohne `name` bleibt alles wie bisher: eine schlichte Zeile (Aufzählungen, «nichts»).
 */
export interface SelectOption { value: string; label: string; name?: string }

/** Wie eine Zeile als **Text** aussieht – im geschlossenen Feld und beim Filtern. */
const optionText = (o: SelectOption) => (o.name ? `${o.label} · ${o.name}` : o.label);

/** Durchsuchbare Referenz-Auswahl (Combobox). Filtert Optionen per Tippen –
 *  z. B. «003» findet die Objektnummer 100000003. */
/**
 * Neueste zuerst: Datensatz-Auswahlen zeigen die **grösste Nummer oben**. Objektnummern
 * werden aufsteigend vergeben – wer einen Datensatz referenziert, meint fast immer einen
 * der zuletzt angelegten, nicht den ältesten von tausend. Greift nur, wenn ALLE Werte
 * Zahlen sind (sonst bleibt die vom Aufrufer gewählte Reihenfolge unangetastet).
 */
function newestFirst(options: SelectOption[]): SelectOption[] {
  const isNum = (v: string) => v !== '' && Number.isFinite(Number(v));
  const numeric = options.filter((o) => isNum(o.value));
  // Nicht-numerische Einträge sind Platzhalter («— wählen —», «Standard erben») und
  // bleiben vorn. Mehr als einer davon heisst: die Liste ist gemischt (z. B. Standort-
  // Ziele wie `user:100000002`) – dann bleibt die Reihenfolge des Aufrufers unangetastet.
  const others = options.filter((o) => !isNum(o.value));
  if (numeric.length < 2 || others.length > 1) return options;
  return [...others, ...numeric.sort((a, b) => Number(b.value) - Number(a.value))];
}

export function SearchSelect({ label, value, onChange, options, required, placeholder,
                               search, emptyOption, action }: {
  label?: string; value: string; onChange: (v: string) => void;
  options: SelectOption[]; required?: boolean; placeholder?: string;
  /**
   * **Eine Handlung AM Feld, nicht daneben.**
   *
   * Sie sitzt am rechten Innenrand und ersetzt dort das Zierzeichen (Chevron ↔ Lupe):
   * ein Bedienelement mit zwei Eingängen statt zweier Bedienelemente für eine Frage. Der
   * Chevron sagt «hier ist eine Liste» – dasselbe sagt der Klick, und er sagt es beim
   * Ausprobieren; eine echte Aktion ist der Platz wert.
   *
   * Ohne die Angabe bleibt alles wie bisher.
   */
  action?: { icon: ReactNode; label: string; onClick: () => void; disabled?: boolean };
  /**
   * **«Nichts» ist eine Wahl – also steht sie in der Liste.**
   *
   * Ist dieser Text gesetzt, führt die Liste ihn als **erste Zeile** mit dem Wert `''`,
   * und ein leeres Feld zeigt ihn an, statt einen Platzhalter zu zeigen. Damit steht die
   * getroffene Entscheidung da, nicht ihr Fehlen.
   *
   * Es ersetzt drei Notbehelfe, die sonst nebeneinander wachsen: einen erklärenden
   * Platzhalter («leer lassen für …»), einen Erklärsatz darunter und einen
   * X-Knopf daneben, mit dem man eine Wahl wieder wegnimmt. Drei Stellen für eine
   * Aussage – und keine davon ist die Liste, in der man wählt (Testnotizen #734–#736).
   *
   * Ohne die Angabe bleibt alles wie bisher: leer heisst «noch nicht gewählt».
   */
  emptyOption?: string;
  /**
   * **Wo die Auswahl zu gross für eine Liste ist: suchen statt mitgeben.**
   *
   * Ohne diese Angabe bleibt alles wie bisher – die Optionen kommen fertig, gefiltert
   * wird im Browser. Mit ihr fragt das Feld beim Tippen den Server; `options` trägt dann
   * nur noch die **gewählte** Option, damit die Anzeige stimmt.
   *
   * Dieselbe Bauart wie beim Scanner (`candidates` ↔ `suggest`): eine Komponente, zwei
   * Quellen. Ein zweites Auswahlfeld «mit Suche» wäre ein zweiter Weg zu derselben Sache
   * – und der erste, der beim nächsten Feld auseinanderläuft.
   */
  search?: (query: string) => Promise<SelectOption[]>;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [found, setFound] = useState<SelectOption[]>([]);
  const ref = useRef<HTMLDivElement>(null);
  // Die Leer-Zeile steht **vor** der Sortierung und bleibt vorn: `newestFirst` lässt
  // nicht-numerische Werte ohnehin an Ort und Stelle.
  const all = emptyOption ? [{ value: '', label: emptyOption }, ...options] : options;
  const selected = all.find((o) => o.value === value);
  const ordered = newestFirst(all);

  // Entprellt, mit Veralterungs-Schutz: wer weitertippt, bekommt nicht die Antwort auf
  // die vorherige Eingabe. Dieselbe Regel wie im Scan-Dialog.
  useEffect(() => {
    if (!search) return;
    const q = query.trim();
    if (!q) { setFound([]); return; }
    let stale = false;
    const t = window.setTimeout(() => {
      search(q)
        .then((r) => { if (!stale) setFound(r); })
        .catch(() => { if (!stale) setFound([]); });
    }, 250);
    return () => { stale = true; window.clearTimeout(t); };
  }, [query, search]);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) { setOpen(false); setQuery(''); }
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const q = query.trim().toLowerCase();
  // Sucht das Feld serverseitig, ist die Antwort die Liste – ein zweiter Filter darüber
  // würde wegwerfen, was der Server gerade als Treffer benannt hat.
  const empty = emptyOption ? [{ value: '', label: emptyOption }] : [];
  const filtered = search
    // Sucht das Feld serverseitig, ist die Antwort die Liste – ein zweiter Filter darüber
    // würde wegwerfen, was der Server gerade als Treffer benannt hat. Die Leer-Zeile ist
    // keine Server-Antwort und bleibt darum immer erreichbar: sie ist die Rücknahme.
    ? (q ? [...empty, ...found] : ordered)
    : (q ? ordered.filter((o) => optionText(o).toLowerCase().includes(q)) : ordered);

  function pick(v: string) { onChange(v); setOpen(false); setQuery(''); setFound([]); }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {label && <Label required={required}>{label}</Label>}
      <div style={{ position: 'relative' }}>
        <input
          value={open ? query : (selected ? optionText(selected) : '')}
          placeholder={placeholder ?? '— wählen —'}
          onFocus={() => { setOpen(true); setQuery(''); }}
          onChange={(e) => { setQuery(e.target.value); if (!open) setOpen(true); }}
          className={inputCls}
          style={{ borderColor: 'var(--border-2)', paddingRight: action ? 34 : 28 }}
        />
        {action ? (
          // Der Klick gehört der Aktion, nicht dem Feld: `onMouseDown` verhindert, dass
          // der Fokus ins Eingabefeld springt (das öffnete sonst die Liste, während sich
          // der Dialog davorlegt), und die Liste schliesst, bevor die Aktion läuft – sie
          // steht INNERHALB des Feldes, also greift der Klick-daneben-Schliesser nicht.
          <button
            type="button"
            className="erp-fieldaction"
            data-tip={action.label}
            aria-label={action.label}
            disabled={action.disabled}
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => { setOpen(false); setQuery(''); action.onClick(); }}
          >
            {action.icon}
          </button>
        ) : open
          ? <Search size={14} style={glyph} />
          : <ChevronDown size={14} style={glyph} />}
      </div>
      {open && (
        <div style={{ position: 'absolute', zIndex: 40, top: 'calc(100% + 4px)', left: 0, right: 0, maxHeight: 240, overflowY: 'auto', background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-sm)', boxShadow: 'var(--shadow-lg)' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '10px 12px', fontSize: 13, color: 'var(--fg-4)' }}>
              {search && !q ? 'Nummer oder Name eingeben' : 'Keine Treffer'}
            </div>
          ) : filtered.map((o) => (
            <button key={o.value} type="button" onClick={() => pick(o.value)}
              style={{ display: 'flex', alignItems: 'center', gap: 10, width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, border: 'none',
                background: o.value === value ? 'var(--accent-soft)' : 'var(--bg-1)', color: o.value === value ? 'var(--accent-ink)' : 'var(--fg-1)', cursor: 'pointer' }}>
              <OptionRow option={o} />
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * **Die eine Zeilenform einer Datensatz-Auswahl.**
 *
 * Nummer tabellarisch und kräftig, Name leise daneben – identisch im Feld und in der
 * Suchleiste des Scanners (`components/scan/scan-dialog.tsx`). Wer hier etwas ändert,
 * ändert es dort mit; deshalb steht sie als Bauteil da und nicht zweimal als JSX.
 *
 * Ohne `name` ist es eine schlichte Zeile – die «nichts»-Wahl etwa ist keine Nummer und
 * sieht darum auch nicht wie eine aus.
 */
export function OptionRow({ option }: { option: SelectOption }) {
  if (!option.name) return <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{option.label}</span>;
  return (
    <>
      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontVariantNumeric: 'tabular-nums', flex: 'none' }}>{option.label}</span>
      <span style={{ opacity: .75, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{option.name}</span>
    </>
  );
}

const glyph: React.CSSProperties = {
  position: 'absolute', right: 9, top: '50%', transform: 'translateY(-50%)',
  color: 'var(--fg-4)', pointerEvents: 'none',
};

export function Segmented({ label, value, onChange, options, required }: {
  label: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean;
}) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      <div style={{ display: 'flex', gap: 6 }}>
        {options.map((o) => {
          const active = value === o.value;
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => onChange(o.value)}
              style={{
                flex: 1, padding: '7px 10px', fontSize: 13, fontWeight: 600,
                borderRadius: 8, cursor: 'pointer',
                border: `1px solid ${active ? 'var(--accent)' : 'var(--border-2)'}`,
                background: active ? 'var(--accent-soft)' : '#fff',
                color: active ? 'var(--accent-ink)' : 'var(--fg-3)',
              }}
            >
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Der Zustand als Pille: Symbol + Farbe + Wort – **eine** Form, überall dieselbe (Feed wie
 * Detail-Kopf). Eine zwischenzeitliche «Punkt + Wort»-Variante für den Feed ist wieder
 * entfallen (Notiz #334): derselbe Zustand darf nicht je nach Ort anders aussehen; die Luft
 * im Feed kommt aus Polsterung und Zeilenabstand, nicht aus einer zweiten Status-Form.
 */
export function StatusBadge({ cfg, size = 10 }: { cfg: StatusCfg; size?: number }) {
  const Icon = cfg.icon;
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      fontSize: size, fontWeight: 700, padding: '2px 8px', borderRadius: 999,
      background: cfg.bg, color: cfg.color, whiteSpace: 'nowrap',
    }}>
      {Icon && <Icon size={size + 3} strokeWidth={2.5} />}
      {cfg.label}
    </span>
  );
}

// Autosave-Statusanzeige («Speichert… / Gespeichert») – geteilt von allen Detailfenstern
// (vorher 3 identische Kopien in Artikel-/Auftrag-/Lagerplatz-Detail).
export function SaveIndicator({ saving, flash }: { saving: boolean; flash: boolean }) {
  if (saving) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--fg-4)' }}><Loader2 size={12} className="animate-spin" /> Speichert…</span>;
  if (flash) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: 'var(--success)' }}><CheckCircle2 size={12} /> Gespeichert</span>;
  return null;
}


/**
 * **Beschriftete Wertzeile** («Kunde · Max Muster») – das Arbeitspferd der Panel-
 * Zusammenfassungen. Lag dreimal identisch im Code (Auftrags-Detail, Beschaffungs-
 * und Verkaufs-Panel), zweimal Zeichen für Zeichen gleich, einmal mit optionalem
 * Symbol. Jetzt eine Stelle – und dabei von hart kodierten Farben auf die
 * Design-Tokens gezogen.
 */
export function Row({ k, v, icon: Icon, hint }: {
  k: string; v: string; icon?: React.ElementType;
  /** Abgeleitetes Detail zur Zeile – gehört in den **Hover**, nicht in die Fläche. */
  hint?: string;
}) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, fontSize: 13 }}>
      <span data-tip={hint} style={{
        color: 'var(--fg-4)', flexShrink: 0, cursor: hint ? 'help' : undefined,
        display: 'inline-flex', alignItems: 'center', gap: 5,
      }}>
        {Icon && <Icon size={12} />}{k}
      </span>
      <span style={{ color: 'var(--fg-1)', fontWeight: 600, textAlign: 'right' }}>{v}</span>
    </div>
  );
}

