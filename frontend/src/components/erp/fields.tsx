'use client';

import { createContext, useContext, useEffect, useRef, useState } from 'react';
import type { ElementType, ReactNode } from 'react';
import { AlertCircle, ArrowUpRight, ArrowLeft, ChevronDown, Search, Info, Loader2, CheckCircle2, Sparkles, ExternalLink, Lock } from 'lucide-react';
import type { StatusAction, StatusTone, StatusCfg } from '@/lib/status-flow';
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

// ─── Kachel: die Grundform der Detail-Ansichten ──────────────────────────────

/**
 * Symbol-Kasten links, Versalien-Label, Inhalt darunter – die EINE Kachel-Optik, die
 * sich die Kennzahlen und die Standort-Karten der Instanz teilen. Vorher stand dieselbe
 * Anatomie dreimal im Code, weshalb die Standort-Karte neben den Kacheln fremd wirkte.
 *
 * Jede Kachel trägt ihre eigene Haarlinie (Weissraum dazwischen) statt in einem
 * durchgefärbten Raster zu sitzen: so bleibt eine unvollständige letzte Reihe einfach
 * leer, statt als grauer Block zu erscheinen.
 */
export function TileShell({ icon: Icon, label, hint, right, style, onClick, children }: {
  icon: ElementType; label: string; hint?: string; right?: ReactNode;
  style?: React.CSSProperties; onClick?: () => void; children: ReactNode;
}) {
  const clickable = !!onClick;
  const Comp: ElementType = clickable ? 'button' : 'div';
  return (
    <Comp
      onClick={onClick}
      className={clickable ? 'erp-tile erp-tile-link' : 'erp-tile'}
      style={{ ...TILE.box, ...(clickable ? { cursor: 'pointer' } : null), ...style }}
    >
      <div style={TILE.ico}><Icon size={19} /></div>
      <div style={{ minWidth: 0, flex: 1, textAlign: 'left' }}>
        <div style={TILE.k}>
          {label}
          {hint && <span style={TILE.hint} data-tip={hint}><Info size={13} /></span>}
          {right && <span style={{ marginLeft: 'auto' }}>{right}</span>}
        </div>
        {children}
      </div>
      {clickable && <span style={TILE.goto}><ArrowUpRight size={18} /></span>}
    </Comp>
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
      {Icon && <Icon size={13} style={{ color: '#94a3b8' }} />}
      <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', color: '#64748b' }}>{children}</span>
      {info && <InfoHint text={info} />}
      {right && <span style={{ marginLeft: 'auto' }}>{right}</span>}
    </div>
  );
}

/** Einheitlicher Prozessschritt-Kopf: getöntes Symbol + Titel + optional ⓘ-Hover + rechter
 *  Slot (z. B. Status). EIN Look über alle Schritt-Panels (Bewegung/Ressource/…). */
export function PanelHeader({ icon: Icon, title, tone = '#2563eb', info, right }: {
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
            aria-label={o.label} title={o.hint ?? o.label}
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
            <Icon size={14} />{showLabel && o.label}
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
export function DetailHeader({
  icon: Icon, iconBg, iconFg, avatar, eyebrow, title, placeholder = 'Ohne Bezeichnung',
  objectId, objectIdText, objectIdHint, actions, status, right, onBack, children,
}: {
  icon?: ElementType;
  iconBg?: string;
  iconFg?: string;
  /** Ersetzt den Symbol-Kasten (Benutzer: rundes Foto/Initialen). */
  avatar?: ReactNode;
  eyebrow: string;
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
  /** Banner und Reiter unter der Kopfzeile. */
  children?: ReactNode;
}) {
  return (
    <div style={DH.head}>
      {onBack && (
        <button onClick={onBack} className="flex items-center gap-1 text-sm mb-3 md:hidden" style={{ color: 'var(--accent)' }}>
          <ArrowLeft size={15} /> Zurück
        </button>
      )}
      <div style={DH.top}>
        {avatar ?? (
          <div style={{ ...DH.ico, background: iconBg ?? 'var(--bg-2)', color: iconFg ?? 'var(--fg-2)' }}>
            {Icon && <Icon size={26} />}
          </div>
        )}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={DH.eyebrow}>{eyebrow}</div>
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
    // paddingBottom 0: die Reiter sitzen bündig an der Unterkante des Kopf-Containers, sodass
    // der rote Aktiv-Balken (2px border-bottom je Reiter) genau auf der Kopf-Haarlinie liegt –
    // nicht mehr 20px darüber schwebend (Notiz #290, gilt für ALLE Detailköpfe via DH.head).
    padding: '20px clamp(14px, 4vw, 28px) 0', borderBottom: '1px solid var(--border-1)',
    background: 'rgba(255,255,255,.93)', backdropFilter: 'blur(8px)', flexShrink: 0,
  },
  top: { display: 'flex', alignItems: 'flex-start', gap: 'clamp(10px, 3vw, 16px)', flexWrap: 'wrap' },
  ico: {
    width: 56, height: 56, borderRadius: 'var(--r-md)', flex: 'none',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  eyebrow: {
    font: 'var(--overline)', letterSpacing: 'var(--tracking-overline)',
    textTransform: 'uppercase', color: 'var(--inexxio-red)', marginBottom: 6,
  },
  title: {
    font: '800 26px var(--font-display)', letterSpacing: '-.03em', margin: 0, lineHeight: 1.05,
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
        style={{ background: '#fff', borderRadius: 'var(--r-lg)', width: `min(${width}px, 100%)`, maxHeight: '86vh', overflowY: 'auto', boxShadow: 'var(--shadow-md)' }}>
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
 * **Ein Weg als Symbol – der Name klappt beim Hover auf** (`.erp-palette`).
 *
 * Die etablierte Geste für «wähle etwas aus einer offenen Palette»: die Symbole stehen
 * sichtbar da, ein Klick führt aus, der Name erscheint beim Hover und die ausführliche
 * Erklärung im Tooltip. Prozessschritt-Module (Notiz #223), Erfassungsfelder (#229) und die
 * Antworten auf eine Unterdeckung (#376) benutzen dieselbe Geste – also dieselbe
 * Implementierung, statt sie ein drittes Mal abzuschreiben.
 */
export function PaletteButton({ icon: Icon, label, hint, tone, bg, border, size = 19, disabled, onClick }: {
  icon: ElementType;
  /** Kurzer Name – erscheint beim Hover neben dem Symbol. */
  label: string;
  /** Ausführliche Erklärung – erscheint als Tooltip (`data-tip`). */
  hint?: string;
  tone?: string; bg?: string; border?: string; size?: number;
  disabled?: boolean;
  onClick: () => void;
}) {
  // **Der Knopf ist ein Symbol, fertig.** Der Name steht in der reservierten Zeile
  // darunter (`Palette`) – weder wächst der Knopf (#502/#503: die Zeile brach um und er
  // wanderte unter dem Cursor weg) noch überdeckt eine Pille die Nachbarn (#509/#510).
  const ctx = useContext(PaletteCtx);
  return (
    <button type="button" onClick={onClick} disabled={disabled} data-tip={hint}
      aria-label={label} className="erp-palette"
      onMouseEnter={() => !disabled && ctx?.(label)} onMouseLeave={() => ctx?.(null)}
      onFocus={() => !disabled && ctx?.(label)} onBlur={() => ctx?.(null)}
      style={{
        background: bg ?? 'var(--bg-2)', borderColor: border ?? 'var(--border-1)',
        color: tone ?? 'var(--fg-2)', opacity: disabled ? .5 : 1,
        cursor: disabled ? 'default' : 'pointer',
      }}>
      <Icon size={size} style={{ flexShrink: 0 }} />
      <span className="erp-palette-label">{label}</span>
    </button>
  );
}

/** Welcher Name gerade in der Bildunterschrift steht – die Palette meldet ihn hier an. */
const PaletteCtx = createContext<((label: string | null) => void) | null>(null);

/**
 * **Eine Palette: Symbole in einer Reihe, der Name in EINER Zeile darunter.**
 *
 * Die Zeile ist immer da (feste Höhe) – deshalb bewegt sich beim Hovern nichts, und es
 * überdeckt auch nichts. `hint` steht in der Zeile, solange niemand auf ein Symbol zeigt;
 * so ist der Platz nicht leer, sondern erklärt, was zu tun ist.
 */
export function Palette({ hint, children, style }: {
  hint?: string; children: React.ReactNode; style?: React.CSSProperties;
}) {
  const [label, setLabel] = useState<string | null>(null);
  return (
    <PaletteCtx.Provider value={setLabel}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, ...style }}>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
          {children}
        </div>
        <div className="erp-palette-caption" aria-live="polite">
          {label ?? (hint ? <span style={{ color: 'var(--fg-4)', fontWeight: 500 }}>{hint}</span> : null)}
        </div>
      </div>
    </PaletteCtx.Provider>
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
export function numericOnly(raw: string, opts: { decimals?: boolean } = {}): string {
  const { decimals = true } = opts;
  const cleaned = raw.replace(',', '.').replace(/[^\d.]/g, '');
  if (!decimals) return cleaned.replace(/\./g, '');
  const [head, ...rest] = cleaned.split('.');       // höchstens EIN Trenner
  return rest.length ? `${head}.${rest.join('')}` : head;
}

/** Tastatur/Verhalten passend zum Zahlenfeld (Mobile: Ziffernblock). */
export const numericInputProps = { inputMode: 'decimal' as const, autoComplete: 'off' };

export function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: '#94a3b8', marginBottom: 4 }}>
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

export function TextField({ label, value, onChange, error, placeholder, required, hint }: {
  label: string; value: string; onChange: (v: string) => void;
  error?: string | null; placeholder?: string; required?: boolean; hint?: string;
}) {
  return (
    <div>
      <Label required={required}>{label}</Label>
      <input
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        className={inputCls}
        style={{ borderColor: error ? '#fca5a5' : '#e2e8f0' }}
      />
      {error ? <ErrorText msg={error} /> : hint ? (
        <div style={{ marginTop: 4, fontSize: 11, color: '#94a3b8' }}>{hint}</div>
      ) : null}
    </div>
  );
}

/** Durchsuchbare Referenz-Auswahl (Combobox). Filtert Optionen per Tippen –
 *  z. B. «003» findet die Objektnummer 100000003. */
/**
 * Neueste zuerst: Datensatz-Auswahlen zeigen die **grösste Nummer oben**. Objektnummern
 * werden aufsteigend vergeben – wer einen Datensatz referenziert, meint fast immer einen
 * der zuletzt angelegten, nicht den ältesten von tausend. Greift nur, wenn ALLE Werte
 * Zahlen sind (sonst bleibt die vom Aufrufer gewählte Reihenfolge unangetastet).
 */
function newestFirst(options: { value: string; label: string }[]): { value: string; label: string }[] {
  const isNum = (v: string) => v !== '' && Number.isFinite(Number(v));
  const numeric = options.filter((o) => isNum(o.value));
  // Nicht-numerische Einträge sind Platzhalter («— wählen —», «Standard erben») und
  // bleiben vorn. Mehr als einer davon heisst: die Liste ist gemischt (z. B. Standort-
  // Ziele wie `user:100000002`) – dann bleibt die Reihenfolge des Aufrufers unangetastet.
  const others = options.filter((o) => !isNum(o.value));
  if (numeric.length < 2 || others.length > 1) return options;
  return [...others, ...numeric.sort((a, b) => Number(b.value) - Number(a.value))];
}

export function SearchSelect({ label, value, onChange, options, required, placeholder }: {
  label?: string; value: string; onChange: (v: string) => void;
  options: { value: string; label: string }[]; required?: boolean; placeholder?: string;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const ref = useRef<HTMLDivElement>(null);
  const selected = options.find((o) => o.value === value);
  const ordered = newestFirst(options);

  useEffect(() => {
    function onDoc(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) { setOpen(false); setQuery(''); }
    }
    document.addEventListener('mousedown', onDoc);
    return () => document.removeEventListener('mousedown', onDoc);
  }, []);

  const q = query.trim().toLowerCase();
  const filtered = q ? ordered.filter((o) => o.label.toLowerCase().includes(q)) : ordered;

  function pick(v: string) { onChange(v); setOpen(false); setQuery(''); }

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      {label && <Label required={required}>{label}</Label>}
      <div style={{ position: 'relative' }}>
        <input
          value={open ? query : (selected?.label ?? '')}
          placeholder={placeholder ?? '— wählen —'}
          onFocus={() => { setOpen(true); setQuery(''); }}
          onChange={(e) => { setQuery(e.target.value); if (!open) setOpen(true); }}
          className={inputCls}
          style={{ borderColor: '#e2e8f0', paddingRight: 28 }}
        />
        {open
          ? <Search size={14} style={{ position: 'absolute', right: 9, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
          : <ChevronDown size={14} style={{ position: 'absolute', right: 9, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />}
      </div>
      {open && (
        <div style={{ position: 'absolute', zIndex: 40, top: 'calc(100% + 4px)', left: 0, right: 0, maxHeight: 240, overflowY: 'auto', background: '#fff', border: '1px solid #e2e8f0', borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.12)' }}>
          {filtered.length === 0 ? (
            <div style={{ padding: '10px 12px', fontSize: 13, color: '#94a3b8' }}>Keine Treffer</div>
          ) : filtered.map((o) => (
            <button key={o.value} type="button" onClick={() => pick(o.value)}
              style={{ display: 'block', width: '100%', textAlign: 'left', padding: '8px 12px', fontSize: 13, border: 'none',
                background: o.value === value ? 'var(--accent-soft)' : '#fff', color: o.value === value ? 'var(--accent-ink)' : 'var(--fg-1)', cursor: 'pointer' }}>
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

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

function statusActionStyle(tone: StatusTone = 'neutral', disabled?: boolean): React.CSSProperties {
  const base: React.CSSProperties = {
    padding: '3px 10px', borderRadius: 6, fontSize: 12, fontWeight: 600,
    cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.5 : 1,
  };
  // Design-System: Rot = der EINE laute CTA-Akzent (Primär, gefüllt). Destruktiv bleibt
  // bewusst leise (rote Outline, nicht gefüllt), Neutral = graue Outline. Kein Blau mehr.
  if (tone === 'primary') return { ...base, border: 'none', background: 'var(--inexxio-red)', color: '#fff' };
  if (tone === 'danger') return { ...base, border: '1px solid var(--danger-bg)', background: 'var(--bg-1)', color: 'var(--danger)' };
  return { ...base, border: '1px solid var(--border-2)', background: 'var(--bg-1)', color: 'var(--fg-3)' };
}

/** Status-Badge + Prozess-Buttons (Freigeben / Deaktivieren / Reaktivieren). */
export function StatusFlow({ cfg, actions = [], busy, onAction }: {
  cfg: StatusCfg;
  actions?: StatusAction[];
  busy?: boolean;
  onAction?: (target: string) => void;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
      <StatusBadge cfg={cfg} />
      {actions.map((a) => (
        <button
          key={a.target}
          type="button"
          title={a.hint}
          disabled={busy || a.disabled}
          onClick={() => onAction?.(a.target)}
          style={statusActionStyle(a.tone, busy || a.disabled)}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}

/** Grosse, eindeutige Hauptaktion (touch-first, volle Breite, ≥44 px). Ein
 *  klarer «Was jetzt?»-Button je Prozessschritt – statt mehrerer kleiner Knöpfe. */
export function PrimaryButton({ icon: Icon, children, onClick, disabled, tone = 'primary' }: {
  icon?: React.ElementType; children: React.ReactNode; onClick: () => void;
  disabled?: boolean; tone?: 'primary' | 'success';
}) {
  // **Ruhige Hauptaktion.** Rot ist im Design-System der EINE laute Akzent – er gehört zur
  // Entscheidung über den Datensatz («Freigeben»), nicht zur alltäglichen Arbeit im Schritt.
  // «Scannen & bewegen» in Rot las sich wie ein Fehler; die Aktion ist aber Routine. Darum
  // Schwarz (dieselbe Stimme wie ``.erp-actbtn-primary``); GRÜN bleibt der Abschluss.
  return (
    <button onClick={onClick} disabled={disabled}
      style={{
        display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%',
        minHeight: 44, padding: '0 16px', borderRadius: 10, border: 'none',
        background: tone === 'success' ? 'var(--success)' : 'var(--inexxio-black)', color: '#fff',
        fontSize: 14, fontWeight: 700, cursor: disabled ? 'not-allowed' : 'pointer',
        opacity: disabled ? 0.55 : 1,
      }}>
      {Icon && <Icon size={18} />} {children}
    </button>
  );
}

export function Placeholder({ icon: Icon, title, text }: { icon: React.ElementType; title: string; text: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', textAlign: 'center', padding: 24 }}>
      <Icon size={40} strokeWidth={1} style={{ color: '#CBD5E1' }} />
      <p style={{ marginTop: 12, fontSize: 14, fontWeight: 600, color: '#64748b' }}>{title}</p>
      <p style={{ marginTop: 4, fontSize: 13, color: '#94a3b8', maxWidth: 280 }}>{text}</p>
    </div>
  );
}

// Autosave-Statusanzeige («Speichert… / Gespeichert») – geteilt von allen Detailfenstern
// (vorher 3 identische Kopien in Artikel-/Auftrag-/Lagerplatz-Detail).
export function SaveIndicator({ saving, flash }: { saving: boolean; flash: boolean }) {
  if (saving) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#94a3b8' }}><Loader2 size={12} className="animate-spin" /> Speichert…</span>;
  if (flash) return <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: 11, color: '#16a34a' }}><CheckCircle2 size={12} /> Gespeichert</span>;
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

/**
 * **Eine lange Liste, die scrollt – ohne Balken, aber sichtbar** (Testnotiz #473).
 *
 * Ein Scrollbalken ist ein Fremdkörper in einer Oberfläche aus Haarlinien und Weissraum;
 * ihn wegzulassen darf aber nicht heissen, dass niemand merkt, dass es weitergeht. Die
 * Kante, an der noch etwas liegt, **blasst darum aus** – oben wie unten, und jede nur
 * dann, wenn dort wirklich noch etwas ist. Das ist dieselbe Sprache, in der auch die
 * Nachbar-Prozesse im Fluss zurücktreten (``.ix-flow-aside``).
 */
export function ScrollFade({ max, children }: { max: number; children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [edge, setEdge] = useState({ top: false, bottom: false });
  function measure() {
    const el = ref.current;
    if (!el) return;
    const bottom = el.scrollHeight - el.scrollTop - el.clientHeight > 2;
    const top = el.scrollTop > 2;
    setEdge((e) => (e.top === top && e.bottom === bottom ? e : { top, bottom }));
  }
  useEffect(measure);
  const FADE = 26;
  const stops = [
    edge.top ? `transparent 0, #000 ${FADE}px` : '#000 0',
    edge.bottom ? `#000 calc(100% - ${FADE}px), transparent 100%` : '#000 100%',
  ].join(', ');
  const mask = `linear-gradient(to bottom, ${stops})`;
  return (
    <div ref={ref} onScroll={measure} className="ix-noscrollbar"
      style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: max,
        overflowY: 'auto', WebkitMaskImage: mask, maskImage: mask }}>
      {children}
    </div>
  );
}

/**
 * **Ein künftiger Schritt zeigt, was GEPLANT ist** (Testnotiz #487).
 *
 * «Wird aktiv, sobald der vorherige Schritt erledigt ist» war die einzige Auskunft – nett,
 * aber sie beantwortet nicht die Frage, die man an dieser Stelle hat: *was soll hier
 * eigentlich passieren?* Das steht längst im Panel (Prüfumfang, Ziel, Ressourcenzeilen,
 * Lieferant); es wurde nur nicht gerendert. Jetzt zeigt der Schritt seine Planung, und
 * diese Zeile sagt, dass sie noch nicht dran ist – die Aktionen bleiben aus.
 */
export function PlannedNotice() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5,
      color: 'var(--fg-4)' }}>
      <Lock size={13} style={{ flexShrink: 0 }} />
      Geplant – wird aktiv, sobald der vorherige Schritt erledigt ist.
    </div>
  );
}
