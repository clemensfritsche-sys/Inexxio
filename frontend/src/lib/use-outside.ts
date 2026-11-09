'use client';

import { useEffect, useRef, type RefObject } from 'react';

/**
 * ►►► **Ein Klick daneben schliesst – EIN Baustein für jedes Aufklapp-Menü und jede Liste.** ◄◄◄
 *
 * Solange `open`, ruft ein Zeiger-Druck ausserhalb aller `inside`-Elemente `onOutside`. Mehrere
 * Elemente, weil eine Liste per Portal am `body` hängt und kein Nachfahre ihres Feldes ist.
 * `ignore` (ein Selektor) nennt, was darüber liegt und trotzdem dazugehört (der Scan-Dialog
 * einer Auswahl). `pointerdown` deckt Maus, Stift und Finger ab und kommt vor dem `click` –
 * ein Klick auf eine Zeile der Liste kommt also an, weil die Liste `inside` ist.
 */
export function useOutside(open: boolean, onOutside: () => void,
                           inside: RefObject<Element | null>[], ignore?: string) {
  const latest = useRef(onOutside);
  latest.current = onOutside;
  const refs = useRef(inside);
  refs.current = inside;
  useEffect(() => {
    if (!open) return;
    const away = (e: PointerEvent) => {
      const t = e.target as Element | null;
      if (!t || refs.current.some((r) => r.current?.contains(t))) return;
      if (ignore && t.closest?.(ignore)) return;
      latest.current();
    };
    document.addEventListener('pointerdown', away);
    return () => document.removeEventListener('pointerdown', away);
  }, [open, ignore]);
}
