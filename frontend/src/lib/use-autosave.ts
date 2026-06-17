import { useCallback, useEffect, useRef } from 'react';

/**
 * Debounced Auto-Save. Speichert automatisch, sobald sich die `signature`
 * (serialisierter Formularzustand) ändert und `canSave` true ist. Gibt eine
 * `flush`-Funktion zurück, um sofort zu speichern (z. B. bei Enter).
 */
export function useAutosave(
  signature: string,
  canSave: boolean,
  onSave: () => void,
  delay = 1500,
): () => void {
  const state = useRef({ canSave, onSave });
  state.current = { canSave, onSave };
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!canSave) return;
    timer.current = setTimeout(() => state.current.onSave(), delay);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [signature, canSave, delay]);

  return useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    if (state.current.canSave) state.current.onSave();
  }, []);
}
