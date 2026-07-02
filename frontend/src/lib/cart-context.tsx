'use client';

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { CartItem } from '@/types';

// ─── Warenkorb (lokaler State, in localStorage persistiert) ──────────────────────
// State of the Art: der Warenkorb lebt clientseitig (kein Backend-Cart) und wird erst
// beim Checkout an den Server übergeben (Defer-Modell). Abos werden separat gekauft –
// das erzwingt der Store (ein Abo verträgt sich nicht mit anderen Positionen).

const STORAGE_KEY = 'inexxio.cart.v1';

interface CartContextValue {
  items: CartItem[];
  count: number;
  subtotal: number;          // indikativ, CHF
  currency: string;
  hydrated: boolean;         // localStorage geladen? (vor true NICHT auf leeren Korb reagieren)
  add: (item: CartItem) => { ok: boolean; reason?: string };
  setQuantity: (key: string, quantity: number) => void;
  remove: (key: string) => void;
  clear: () => void;
  keyOf: (item: { article_object_id: number; price_id: number }) => string;
}

const CartContext = createContext<CartContextValue | null>(null);

function keyOf(item: { article_object_id: number; price_id: number }): string {
  return `${item.article_object_id}:${item.price_id}`;
}

export function CartProvider({ children }: { children: React.ReactNode }) {
  const [items, setItems] = useState<CartItem[]>([]);
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setItems(JSON.parse(raw) as CartItem[]);
    } catch { /* ignore */ }
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(items)); } catch { /* ignore */ }
  }, [items, hydrated]);

  // FIX: Das Ergebnis wurde bisher INNERHALB des setItems-Updaters gesetzt und danach
  // zurückgegeben – React garantiert aber nicht, dass der Updater synchron läuft (nur eine
  // Eager-Evaluation-Optimierung liess es meist funktionieren). Bei ausstehenden Updates wäre
  // die Abo-Ablehnung («Abos werden einzeln gekauft») verloren gegangen. Die Prüfung läuft
  // jetzt VOR setItems gegen den aktuellen State (useCallback-Dep auf items).
  const add = useCallback((item: CartItem): { ok: boolean; reason?: string } => {
    const isSub = item.kind === 'subscription';
    const hasSub = items.some((p) => p.kind === 'subscription');
    // Abos werden einzeln gekauft: weder Abo zu vollem Korb, noch etwas zu einem Abo.
    if ((isSub && items.length > 0) || (!isSub && hasSub)) {
      return { ok: false, reason: 'Abos werden einzeln gekauft – bitte separat zur Kasse gehen.' };
    }
    setItems((prev) => {
      const k = keyOf(item);
      const existing = prev.find((p) => keyOf(p) === k);
      if (existing) {
        // Abo: Menge bleibt 1 (ein Vertrag); sonst aufaddieren.
        return prev.map((p) => keyOf(p) === k
          ? { ...p, quantity: isSub ? 1 : p.quantity + item.quantity } : p);
      }
      return [...prev, { ...item, quantity: isSub ? 1 : item.quantity }];
    });
    return { ok: true };
  }, [items]);

  const setQuantity = useCallback((key: string, quantity: number) => {
    setItems((prev) => prev.map((p) => keyOf(p) === key
      ? { ...p, quantity: Math.max(1, quantity) } : p));
  }, []);

  const remove = useCallback((key: string) => {
    setItems((prev) => prev.filter((p) => keyOf(p) !== key));
  }, []);

  const clear = useCallback(() => setItems([]), []);

  const value = useMemo<CartContextValue>(() => ({
    items,
    count: items.reduce((n, p) => n + p.quantity, 0),
    subtotal: items.reduce((s, p) => s + p.gross * p.quantity, 0),
    currency: items[0]?.currency ?? 'CHF',
    hydrated,
    add, setQuantity, remove, clear, keyOf,
  }), [items, hydrated, add, setQuantity, remove, clear]);

  return <CartContext.Provider value={value}>{children}</CartContext.Provider>;
}

export function useCart(): CartContextValue {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error('useCart must be used within CartProvider');
  return ctx;
}

// Tolerante Variante: liefert null statt zu werfen, wenn kein Provider vorhanden ist
// (z. B. die geteilte Navbar auf ERP-/Konto-Seiten ohne Warenkorb-Kontext).
export function useCartOptional(): CartContextValue | null {
  return useContext(CartContext);
}
