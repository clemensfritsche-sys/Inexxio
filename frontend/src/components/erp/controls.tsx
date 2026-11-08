'use client';

import { useEffect, useId, useRef, useState } from 'react';
import type { ElementType, ReactNode } from 'react';
import { type LucideIcon } from 'lucide-react';

// ►►► **Die Bedienelemente** – die eine Feldform (`inputClass`), Beschriftung (`Label`),
// Schieber (`IconSwitch`), Umschalter (`Segmented`), Dialog, Palette, Zahlenfelder und der
// Symbol-Knopf im Feld (`FieldAction`). ◄◄◄

/**
 * ►►► **EINE Form für jedes Eingabefeld**; je Lage ändert sich nur die Farbe (`inputClass`). ◄◄◄
 * Ein Wert auf dem Beleg ist gedruckter Text mit `.ix-editable` (`beleg/shared.DOC_FIELD`).
 */
const INPUT_FORM = 'w-full rounded-ds-md border px-3 py-2 text-sm outline-none placeholder:text-fg-4 transition-colors focus:ring-[3px] focus:ring-accent-soft';
const INPUT_TONE = {
  normal: 'border-border-2 bg-bg-1 text-fg-1 focus:border-accent',
  /** Pflicht und leer, oder das Format stimmt nicht – gemeldet, nicht gesperrt. */
  warn: 'border-warning bg-warning-bg text-fg-1',
  read: 'border-border-1 bg-bg-2 text-fg-4 cursor-default',
} as const;

export function inputClass(tone: keyof typeof INPUT_TONE = 'normal'): string {
  return `${INPUT_FORM} ${INPUT_TONE[tone]}`;
}

export const inputCls = inputClass();

/**
 * **Schieber** für wenige, einander ausschliessende Optionen: ein Reiter gleitet zur aktiven.
 * Gesperrte Optionen bleiben sichtbar und nennen ihren Grund im Hover (`data-tip`, nie `title`).
 */
export function IconSwitch<T extends string>({ value, onChange, options, labelActiveOnly }: {
  value: T; onChange: (v: T) => void;
  /** ``mark`` setzt einen dezenten Punkt an eine nicht gewählte Option (z. B. die Empfehlung). */
  options: { value: T; icon: ElementType; label: string; hint?: string; disabled?: boolean; mark?: boolean }[];
  /** Nur die AKTIVE Option zeigt ihr Wort – für Achsen mit vielen Werten (Mengeneinheit). */
  labelActiveOnly?: boolean;
}) {
  const index = Math.max(0, options.findIndex((o) => o.value === value));
  const wrapRef = useRef<HTMLDivElement>(null);
  // Der Reiter wird **gemessen** – die Optionen sind unterschiedlich breit.
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
  }, [index, options.length, labelActiveOnly]);

  return (
    // Mit ``labelActiveOnly`` schmiegt sich der Regler an seinen Inhalt.
    <div ref={wrapRef} style={{
      position: 'relative', display: labelActiveOnly ? 'inline-flex' : 'flex',
      alignSelf: 'flex-start', maxWidth: '100%', flexWrap: 'wrap',
      padding: 3, borderRadius: 999, background: 'var(--bg-2)', border: '1px solid var(--border-1)',
    }}>
      <span aria-hidden style={{
        position: 'absolute', top: 3, bottom: 3,
        left: thumb ? thumb.left : 3, width: thumb ? thumb.width : 0,
        opacity: thumb ? 1 : 0,
        transition: 'left .18s cubic-bezier(.4,0,.2,1), width .18s cubic-bezier(.4,0,.2,1)',
        borderRadius: 999, background: 'var(--bg-1)', boxShadow: '0 1px 2px rgba(0,0,0,.12)',
      }} />
      {options.map((o, i) => {
        const active = o.value === value;
        const Icon = o.icon;
        const showLabel = !labelActiveOnly || active;
        return (
          <button key={o.value} type="button" role="tab" aria-selected={active} data-ix-idx={i}
            aria-label={o.label}
            // Der Name wächst im Hover heraus; der Tooltip nur, wenn er mehr sagt.
            data-tip={o.hint && o.hint !== o.label ? o.hint : undefined} data-tip-pos="bottom"
            className="ix-seg"
            onClick={o.disabled ? undefined : () => onChange(o.value)} disabled={o.disabled}
            style={{
              position: 'relative', flex: labelActiveOnly ? '0 0 auto' : 1,
              display: 'inline-flex', alignItems: 'center',
              justifyContent: 'center', gap: 6, padding: '7px 12px',
              border: 'none', background: 'none', borderRadius: 999,
              font: '600 12px var(--font-body)', cursor: o.disabled ? 'not-allowed' : 'pointer',
              opacity: o.disabled ? 0.4 : 1, transition: 'color .18s',
              color: active ? 'var(--accent-ink)' : 'var(--fg-3)', whiteSpace: 'nowrap',
            }}>
            <Icon size={14} />
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

/** **Dialog** – die EINE Fensterform für eine Entscheidung; Klick daneben und `Esc` schliessen
 *  (kein ×, kein «Abbrechen»). */
export function Dialog({ icon: Icon, title, tone = 'var(--warning)', width = 520, onClose, children }: {
  icon?: ElementType; title: string; tone?: string; width?: number;
  onClose: () => void; children: ReactNode;
}) {
  const titleId = useId();
  const panel = useRef<HTMLDivElement>(null);
  const close = useRef(onClose);
  close.current = onClose;
  // **Fokus hinein und zurück**: beim Öffnen auf das erste Bedienelement (sonst den Dialog
  // selbst), beim Schliessen dorthin, wo er vorher war. Escape schliesst.
  useEffect(() => {
    const before = document.activeElement as HTMLElement | null;
    const node = panel.current;
    if (node && !node.contains(document.activeElement)) {
      (node.querySelector<HTMLElement>(FOCUSABLE) ?? node).focus();
    }
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') close.current(); }
    window.addEventListener('keydown', onKey);
    return () => {
      window.removeEventListener('keydown', onKey);
      before?.focus?.();
    };
  }, []);
  return (
    <div onClick={onClose}
      style={{ position: 'fixed', inset: 0, background: 'color-mix(in srgb, var(--bg-dark) 45%, transparent)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 60, padding: 16 }}>
      <div ref={panel} role="dialog" aria-modal="true" aria-labelledby={titleId} tabIndex={-1}
        onClick={(e) => e.stopPropagation()}
        style={{ background: 'var(--bg-1)', borderRadius: 'var(--r-lg)', width: `min(${width}px, 100%)`, maxHeight: '86vh', overflowY: 'auto', boxShadow: 'var(--shadow-lg)', outline: 'none' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 20px', borderBottom: '1px solid var(--border-1)' }}>
          {Icon && <Icon size={18} aria-hidden style={{ color: tone }} />}
          <h2 id={titleId} style={{ font: '700 15px var(--font-display)', color: 'var(--fg-1)', margin: 0 }}>{title}</h2>
        </div>
        <div style={{ padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: 12 }}>{children}</div>
      </div>
    </div>
  );
}

/** Was im Dialog den Fokus nehmen kann – das erste davon bekommt ihn beim Öffnen. */
const FOCUSABLE = 'input:not([disabled]), textarea:not([disabled]), select:not([disabled]), button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

/** **Eine Palette: Symbole in einer Reihe**, der Name im Hover. */
export function Palette({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center' }}>
      {children}
    </div>
  );
}

/**
 * Die EINE Regel für Zahlenfelder: nur Ziffern, optional EIN Dezimaltrenner (Komma → Punkt).
 * Bewusst statt `type="number"`, das bei ungültiger Eingabe einen leeren Wert liefert.
 */
export function numericOnly(
  raw: string, opts: { decimals?: boolean | number; signed?: boolean } = {},
): string {
  const { decimals = true, signed = false } = opts;
  // Ein Minus nur ganz vorn (mit `signed`).
  const minus = signed && raw.trimStart().startsWith('-') ? '-' : '';
  const cleaned = raw.replace(',', '.').replace(/[^\d.]/g, '');
  if (decimals === false || decimals === 0) return minus + cleaned.replace(/\./g, '');
  const [head, ...rest] = cleaned.split('.');       // höchstens EIN Trenner
  // ►►► **Wie viele Nachkommastellen, sagt die WÄHRUNG** ◄◄◄ (JPY null, KWD drei); `true` = unbegrenzt.
  const tail = rest.join('');
  const kept = typeof decimals === 'number' ? tail.slice(0, decimals) : tail;
  return minus + (rest.length ? `${head}.${kept}` : head);
}

/** Tastatur/Verhalten passend zum Zahlenfeld (Mobile: Ziffernblock). */
export const numericInputProps = { inputMode: 'decimal' as const, autoComplete: 'off' };

export function Label({ children, required }: { children: React.ReactNode; required?: boolean }) {
  return (
    <div style={{ fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--fg-4)', marginBottom: 4 }}>
      {children}{required && <span style={{ color: 'var(--danger)' }}> *</span>}
    </div>
  );
}

/**
 * ►►► **Eine Aktion sitzt IM Feld, nicht daneben** ◄◄◄ (z. B. die Kamera am rechten
 * Innenrand) – ein Bauteil für jedes Suchfeld. `onMouseDown` hält den Fokus aus dem Feld.
 */
export function FieldAction({ icon, label, disabled, onClick }: {
  icon: ReactNode; label: string; disabled?: boolean; onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="erp-fieldaction"
      data-tip={label}
      aria-label={label}
      disabled={disabled}
      onMouseDown={(e) => e.preventDefault()}
      onClick={onClick}
    >
      {icon}
    </button>
  );
}

/**
 * **Eine Wahl aus wenigen Werten** – zwei bis vier Möglichkeiten nebeneinander. Mit Symbol
 * stehen sie auf Inhaltsbreite, ohne gleichmässig verteilt; **das Wort bleibt immer** – bei
 * einer Wahl ist es die Sache selbst (anders als bei einem Knopf).
 */
export function Segmented({ value, onChange, options, disabled, tip }: {
  value: string; onChange: (v: string) => void;
  options: { value: string; label: string; icon?: LucideIcon }[];
  /** Gesperrt – der Wert bleibt sichtbar, der Grund steht in ``tip`` (Hover). */
  disabled?: boolean;
  tip?: string;
}) {
  const tucked = options.some((o) => o.icon);
  return (
    <div data-tip={tip}>
      <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
        {options.map((o) => {
          const active = value === o.value;
          const Icon = o.icon;
          return (
            <button
              key={o.value}
              type="button"
              onClick={() => onChange(o.value)}
              disabled={disabled}
              aria-label={o.label}
              aria-pressed={active}
              style={{
                display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                gap: 6,
                flex: tucked ? 'none' : 1,
                padding: '6px 10px',
                fontSize: 13, fontWeight: 600,
                borderRadius: 8, cursor: disabled ? 'default' : 'pointer',
                border: `1px solid ${active ? 'var(--accent)' : 'var(--border-2)'}`,
                background: active ? 'var(--accent-soft)' : 'var(--bg-1)',
                color: active ? 'var(--accent-ink)' : 'var(--fg-3)',
              }}
            >
              {Icon && <Icon size={14} style={{ flex: 'none' }} />}
              {o.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
