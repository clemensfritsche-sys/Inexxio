import { useCallback, useEffect, useRef } from 'react';

/**
 * Debounced Auto-Save. Speichert automatisch, sobald sich die `signature`
 * (serialisierter Formularzustand) ändert und `canSave` true ist. Gibt eine
 * `flush`-Funktion zurück, um sofort zu speichern (z. B. bei Enter).
 *
 * Wichtig: Pro Signatur wird **höchstens einmal** automatisch gespeichert.
 * Schlägt ein Speichern fehl (z. B. Netzwerk-/Serverfehler), würde sonst der
 * Wechsel von `saving` (true→false) `canSave` erneut wahr machen und denselben
 * Stand in Endlosschleife wieder senden. Stattdessen wird der Fehler angezeigt
 * und erst nach einer **Änderung** (neue Signatur) bzw. manuell per `flush()`
 * (Enter) erneut gesendet.
 */
export function useAutosave(
  signature: string,
  canSave: boolean,
  onSave: () => void,
  delay = 1500,
): () => void {
  const state = useRef({ canSave, onSave, signature });
  state.current = { canSave, onSave, signature };
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Signatur, für die zuletzt ein Auto-Save ausgelöst wurde (verhindert Loop).
  const firedSig = useRef<string | null>(null);

  useEffect(() => {
    if (!canSave) return;
    if (firedSig.current === signature) return;   // dieser Stand wurde bereits (versucht zu) speichern
    timer.current = setTimeout(() => {
      firedSig.current = signature;
      state.current.onSave();
    }, delay);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [signature, canSave, delay]);

  // Sofort speichern (Enter): erlaubt bewusst auch einen erneuten Versuch für
  // dieselbe Signatur (manueller Retry nach einem Fehler).
  return useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    if (state.current.canSave) {
      firedSig.current = state.current.signature;
      state.current.onSave();
    }
  }, []);
}
