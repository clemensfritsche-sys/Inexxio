'use client';

import { useEffect, useRef, type KeyboardEvent as ReactKeyboardEvent, type RefObject } from 'react';

/** Was in einem Dialog den Fokus nehmen kann. */
const FOCUSABLE = 'input:not([disabled]), textarea:not([disabled]), select:not([disabled]), '
  + 'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';

/**
 * ►►► **Wie sich ein Dialog verhält – EINE Stelle** (Änderungsakte U8). ◄◄◄
 *
 * Jeder Dialog sieht aus, wie er aussehen muss (Anmelden als Glas-Karte, Scannen mit Kamera, das
 * «+» als Blatt …); **verhalten** tun sich alle gleich:
 *
 * - **Fokus hinein** – auf das erste Bedienelement (`focus: 'first'`), sonst auf den Dialog
 *   selbst; `focus: 'self'` lässt ihn am Dialog (Scannen mit laufender Kamera: keine Tastatur),
 *   `'none'` überlässt ihn dem Dialog.
 * - **Fokus zurück** beim Schliessen – dorthin, wo er vorher war.
 * - **Escape schliesst** (`onClose`; ohne `onClose` ist der Dialog gerade nicht schliessbar, z. B.
 *   während einer Aufnahme) – **nur den obersten**: liegt ein Dialog über einem anderen (der
 *   Scanner über dem Entwurf), schliesst Escape den, der zuletzt aufging.
 * - **Tab bleibt im Dialog** (`onKeyDown` an den Dialog hängen): die Bedienelemente im Kreis.
 */
/** Die offenen Dialoge, der zuletzt geöffnete zuoberst – Escape gilt dem obersten, der gerade
 *  schliessbar ist (ein Hinweis ohne `onClose` hält niemanden auf). */
const open: { current: (() => void) | null | undefined }[] = [];

export function useDialog<T extends HTMLElement = HTMLDivElement>(
  onClose?: (() => void) | null,
  opts: { focus?: 'first' | 'self' | 'none'; modal?: boolean } = {},
): { ref: RefObject<T | null>; onKeyDown: (e: ReactKeyboardEvent) => void } {
  const ref = useRef<T | null>(null);
  const close = useRef(onClose);
  close.current = onClose;
  const focus = opts.focus ?? 'first';

  useEffect(() => {
    const me = close;
    open.push(me);
    const before = document.activeElement as HTMLElement | null;
    const node = ref.current;
    if (node && focus !== 'none' && !node.contains(document.activeElement)) {
      const target = focus === 'first' ? node.querySelector<HTMLElement>(FOCUSABLE) : null;
      (target ?? node).focus();
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || !close.current) return;
      if ([...open].reverse().find((d) => d.current) === me) close.current();
    };
    window.addEventListener('keydown', onKey);
    return () => {
      open.splice(open.indexOf(me), 1);
      window.removeEventListener('keydown', onKey);
      if (before && document.contains(before)) before.focus?.();
    };
  }, [focus]);

  const onKeyDown = (e: ReactKeyboardEvent) => {
    if (e.key !== 'Tab' || opts.modal === false) return;
    const items = ref.current?.querySelectorAll<HTMLElement>(FOCUSABLE);
    if (!items?.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  };
  return { ref, onKeyDown };
}
