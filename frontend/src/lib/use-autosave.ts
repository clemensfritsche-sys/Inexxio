import { useCallback, useEffect, useRef, useState } from 'react';

/**
 * **Auto-Save – ein Modul, eine Vorgabe.** Im ERP wird nicht abgeschickt, sondern
 * gespeichert: debounced 3 s, Enter löst sofort aus (Hausregel). Zwei Formen, weil zwei
 * Aufrufstellen Verschiedenes in der Hand haben:
 *
 * - `useAutosaveValue` – ein **Formularwert**, und der Hook meldet den Zustand
 *   (`SaveStatus` für `SaveStatusIndicator`). Für Detailfenster mit Karten-Kopf.
 * - `useAutosaveSignature` – eine **Signatur** des Zustands und ein Rückruf; den Zustand
 *   meldet der Aufrufer selbst (der Beleg: `busy` und die Antwort des Servers).
 *
 * Beide warten `AUTOSAVE_DELAY` – zwei Vorgaben wären zwei Antworten auf «wann speichert
 * das ERP?».
 */
export const AUTOSAVE_DELAY = 3000;

/** Wie lange «Gespeichert» stehen bleibt, bevor die Anzeige wieder verschwindet. */
const SAVED_SHOWN = 2500;

export type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error';

/**
 * Speichert `value`, sobald er sich ändert (debounced). `resetKey` wechselt mit dem
 * Datensatz: der erste Wert nach dem Wechsel ist geladen, nicht getippt.
 */
export function useAutosaveValue<T>(
  value: T,
  save: (v: T) => Promise<void>,
  resetKey?: unknown,
): { status: SaveStatus; errorMsg: string; saveNow: () => Promise<void> } {
  const [status, setStatus] = useState<SaveStatus>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const skipRef = useRef(true);
  const saveRef = useRef(save);
  saveRef.current = save;
  const valueRef = useRef(value);
  valueRef.current = value;
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const run = useCallback(async () => {
    setStatus('saving');
    try {
      await saveRef.current(valueRef.current);
      setStatus('saved');
      timerRef.current = setTimeout(() => setStatus('idle'), SAVED_SHOWN);
    } catch (e: unknown) {
      setErrorMsg(e instanceof Error ? e.message : 'Fehler');
      setStatus('error');
    }
  }, []);

  useEffect(() => {
    skipRef.current = true;
  }, [resetKey]);

  useEffect(() => {
    if (skipRef.current) {
      skipRef.current = false;
      return;
    }
    setStatus('dirty');
    timerRef.current = setTimeout(run, AUTOSAVE_DELAY);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [value, run]);

  const saveNow = useCallback(async () => {
    if (timerRef.current) { clearTimeout(timerRef.current); timerRef.current = null; }
    await run();
  }, [run]);

  return { status, errorMsg, saveNow };
}

/**
 * Speichert, sobald sich die `signature` (serialisierter Zustand) ändert und `canSave`
 * wahr ist. Gibt `flush` zurück, um sofort zu speichern (Enter).
 *
 * Pro Signatur wird **höchstens einmal** automatisch gespeichert: schlägt ein Speichern
 * fehl, machte der Wechsel von `saving` (true→false) `canSave` erneut wahr, und derselbe
 * Stand ginge in Endlosschleife wieder hinaus. Erneut gesendet wird erst nach einer
 * Änderung (neue Signatur) oder per `flush()`.
 */
export function useAutosaveSignature(
  signature: string,
  canSave: boolean,
  onSave: () => void,
): () => void {
  const state = useRef({ canSave, onSave, signature });
  state.current = { canSave, onSave, signature };
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  // Signatur, für die zuletzt ein Auto-Save ausgelöst wurde (verhindert die Schleife).
  const firedSig = useRef<string | null>(null);

  useEffect(() => {
    if (!canSave) return;
    if (firedSig.current === signature) return;
    timer.current = setTimeout(() => {
      firedSig.current = signature;
      state.current.onSave();
    }, AUTOSAVE_DELAY);
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [signature, canSave]);

  // Sofort speichern (Enter): erlaubt bewusst einen erneuten Versuch für dieselbe
  // Signatur (manueller Retry nach einem Fehler).
  return useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    if (state.current.canSave) {
      firedSig.current = state.current.signature;
      state.current.onSave();
    }
  }, []);
}
