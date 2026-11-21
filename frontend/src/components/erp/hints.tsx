'use client';

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { ReactNode } from 'react';
import { AlertCircle, Info } from 'lucide-react';

// ►►► **Was erklärt oder meldet** – Hover-Blase (`data-tip` · `Tooltip`), ⓘ (`InfoHint`),
// Fehlerzeile (`ErrorText`). Erklärungen gehören in den Hover, nicht in die Fläche. ◄◄◄

/**
 * ►►► **EINE Hover-Blase für die ganze App** – wer etwas erklärt, setzt `data-tip="…"` an das
 * Element (oder nimmt `Tooltip`/`InfoHint`); gezeigt wird sie von `TipHost`, der einmal im
 * Wurzel-Layout hängt. ◄◄◄
 *
 * - **Am `body`, nicht im Element** (Portal, `position: fixed` aus dem Rechteck des Auslösers):
 *   kein `overflow: hidden` eines Vorfahren schneidet sie ab, und sie erbt nichts von ihm – keine
 *   Grossschreibung einer Überschrift, keine gesperrte Schrift. Der Text steht, wie er
 *   geschrieben ist (Satzschreibung).
 * - **Sie kippt am Rand**: oben ist die Vorgabe; reicht der Platz nicht, unten (bzw. links ↔
 *   rechts), und waagrecht bleibt sie im Fenster.
 * - **Die innere gewinnt**: gezeigt wird das nächste `[data-tip]` vom Zeiger aus.
 * - **Ohne Zeigegerät ist der Fokus der Hover**; mit Maus nur der Fokus der Tastatur
 *   (`:focus-visible`) – ein Klick lässt keine Blase stehen.
 * - `data-tip-pos="bottom|left|right"` ändert die Vorgabe, `data-tip-list` setzt Zeilen
 *   (`\n`) untereinander, `data-tip-hidden` schweigt.
 */
export function TipHost() {
  const [at, setAt] = useState<Element | null>(null);
  useEffect(() => {
    const tipOf = (t: EventTarget | null) => (t instanceof Element ? t.closest('[data-tip]') : null);
    const over = (e: PointerEvent) => {
      if (e.pointerType === 'touch') return;
      setAt(tipOf(e.target));
    };
    const out = (e: PointerEvent) => {
      if (!tipOf(e.relatedTarget)) setAt(null);
    };
    const focus = (e: FocusEvent) => {
      const el = tipOf(e.target);
      const touch = window.matchMedia('(hover: none)').matches;
      if (el && (touch || (e.target as Element).matches(':focus-visible'))) setAt(el);
    };
    const blur = () => setAt(null);
    const away = () => setAt(null);
    document.addEventListener('pointerover', over);
    document.addEventListener('pointerout', out);
    document.addEventListener('focusin', focus);
    document.addEventListener('focusout', blur);
    window.addEventListener('scroll', away, true);
    document.addEventListener('keydown', away);
    return () => {
      document.removeEventListener('pointerover', over);
      document.removeEventListener('pointerout', out);
      document.removeEventListener('focusin', focus);
      document.removeEventListener('focusout', blur);
      window.removeEventListener('scroll', away, true);
      document.removeEventListener('keydown', away);
    };
  }, []);
  const gone = useCallback(() => setAt(null), []);
  return at ? <Bubble at={at} onGone={gone} /> : null;
}

type Side = 'top' | 'bottom' | 'left' | 'right';
const GAP = 8;
const EDGE = 8;

/** Die Blase an einem Element – folgt ihm (Text, Lage), bis es weg ist. */
function Bubble({ at, onGone }: { at: Element; onGone: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [text, setText] = useState(() => at.getAttribute('data-tip') ?? '');
  useLayoutEffect(() => {
    let frame = 0;
    const place = () => {
      const el = box.current;
      if (!at.isConnected || at.hasAttribute('data-tip-hidden')) { onGone(); return; }
      const now = at.getAttribute('data-tip') ?? '';
      setText((t) => (t === now ? t : now));
      if (el) {
        const p = position(at.getBoundingClientRect(), el.getBoundingClientRect(),
          (at.getAttribute('data-tip-pos') as Side | null) ?? 'top');
        el.style.left = `${p.left}px`;
        el.style.top = `${p.top}px`;
        el.style.visibility = 'visible';
      }
      frame = requestAnimationFrame(place);
    };
    place();
    return () => cancelAnimationFrame(frame);
  }, [at, onGone]);
  if (!text.trim()) return null;
  const list = at.hasAttribute('data-tip-list');
  return createPortal(
    <div ref={box} role="tooltip" className="ix-tip" data-list={list || undefined}>{text}</div>,
    document.body,
  );
}

/** Wohin die Blase kommt: die Vorgabe, sonst die Gegenseite; immer ganz im Fenster. */
function position(r: DOMRect, b: DOMRect, want: Side): { left: number; top: number } {
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const clamp = (v: number, max: number) => Math.max(EDGE, Math.min(v, max - EDGE));
  const fits: Record<Side, boolean> = {
    top: r.top - b.height - GAP >= EDGE,
    bottom: r.bottom + b.height + GAP <= vh - EDGE,
    left: r.left - b.width - GAP >= EDGE,
    right: r.right + b.width + GAP <= vw - EDGE,
  };
  const flip: Record<Side, Side> = { top: 'bottom', bottom: 'top', left: 'right', right: 'left' };
  const side = fits[want] || !fits[flip[want]] ? want : flip[want];
  if (side === 'top' || side === 'bottom') {
    return {
      left: clamp(r.left + r.width / 2 - b.width / 2, vw - b.width),
      top: side === 'top' ? r.top - b.height - GAP : r.bottom + GAP,
    };
  }
  return {
    left: side === 'left' ? r.left - b.width - GAP : r.right + GAP,
    top: clamp(r.top + r.height / 2 - b.height / 2, vh - b.height),
  };
}

/** **Ein Hinweis an einem beliebigen Inhalt** – dieselbe Blase wie `data-tip`. */
export function Tooltip({ text, children, side = 'top' }: {
  text: string; children: ReactNode; side?: 'top' | 'bottom';
}) {
  return (
    <span data-tip={text} data-tip-pos={side === 'top' ? undefined : side}
      style={{ display: 'inline-flex', alignItems: 'center' }}>
      {children}
    </span>
  );
}

/** Dezentes ⓘ-Symbol; die Erklärung erscheint im Hover. Ersetzt Infotext-Blöcke. */
export function InfoHint({ text }: { text: string }) {
  return (
    <Tooltip text={text}>
      <Info size={13} style={{ color: 'var(--fg-4)', cursor: 'help', flexShrink: 0 }} />
    </Tooltip>
  );
}

export function ErrorText({ msg }: { msg: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginTop: 4, fontSize: 11, color: 'var(--danger)' }}>
      <AlertCircle size={11} /> {msg}
    </div>
  );
}
