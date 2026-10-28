import { useCallback, useEffect, useRef, useState } from 'react';
import { createSaver, type Saver } from './saver';
import { tell } from './notice';

/**
 * **Auto-Save – ein Modul, eine Vorgabe, EINE Logik** (`lib/saver.ts`). Im ERP wird nicht
 * abgeschickt, sondern gespeichert: debounced 3 s, Enter löst sofort aus (Hausregel). Für
 * beide Formen gilt dasselbe: ein offener Stand geht beim Verlassen (Unmount) und beim
 * Wechsel des Datensatzes (`resetKey`) **sofort** hinaus, Speichervorgänge laufen
 * hintereinander (nie überholt ein älterer einen neueren), und ein Fehler meldet sich über
 * `tell()`. Zwei Formen, weil zwei Aufrufstellen Verschiedenes in der Hand haben:
 *
 * - `useAutosaveValue` – ein **Formularwert**, und der Hook meldet den Zustand
 *   (`SaveStatus` für `SaveStatusIndicator`). Für Detailfenster mit Karten-Kopf.
 * - `useAutosaveSignature` – eine **Signatur** des Zustands und ein Rückruf; den Zustand
 *   meldet der Aufrufer selbst (der Beleg: `busy` und die Antwort des Servers).
 */
export const AUTOSAVE_DELAY = 3000;

/** Wie lange «Gespeichert» stehen bleibt, bevor die Anzeige wieder verschwindet. */
const SAVED_SHOWN = 2500;

export type SaveStatus = 'idle' | 'dirty' | 'saving' | 'saved' | 'error';

/** Fehler eines Auto-Saves – unten rechts, auch wenn die Karte schon weg ist. */
const report = tell('Änderung', 'Nicht gespeichert');

/** Ein Saver je Bauteil; beim Verlassen geht der offene Stand sofort hinaus. */
function useSaver<T>(onStatus?: (s: SaveStatus) => void, onError?: (e: unknown) => void): Saver<T> {
  const hooks = useRef({ onStatus, onError });
  hooks.current = { onStatus, onError };
  const ref = useRef<Saver<T> | null>(null);
  if (!ref.current) {
    ref.current = createSaver<T>({
      delay: AUTOSAVE_DELAY,
      onStatus: (s) => hooks.current.onStatus?.(s),
      onError: (e) => { report(e); hooks.current.onError?.(e); },
    });
  }
  const saver = ref.current;
  useEffect(() => () => {
    // Nach dem Verlassen meldet sich nur noch `tell` – kein setState auf ein totes Bauteil.
    hooks.current = { onStatus: undefined, onError: undefined };
    void saver.flush();
  }, [saver]);
  return saver;
}

/**
 * Speichert `value`, sobald er sich ändert (debounced). `resetKey` wechselt mit dem
 * Datensatz: der offene Stand geht dann sofort an den alten, und der erste Wert danach ist
 * geladen, nicht getippt.
 */
export function useAutosaveValue<T>(
  value: T,
  save: (v: T) => Promise<void>,
  resetKey?: unknown,
): { status: SaveStatus; errorMsg: string; saveNow: () => Promise<void> } {
  const [status, setStatus] = useState<SaveStatus>('idle');
  const [errorMsg, setErrorMsg] = useState('');
  const idle = useRef<ReturnType<typeof setTimeout> | null>(null);
  const saver = useSaver<T>(
    (s) => {
      if (idle.current) { clearTimeout(idle.current); idle.current = null; }
      setStatus(s);
      if (s === 'saved') idle.current = setTimeout(() => setStatus('idle'), SAVED_SHOWN);
    },
    (e) => setErrorMsg(e instanceof Error ? e.message : 'Fehler'),
  );
  useEffect(() => () => { if (idle.current) clearTimeout(idle.current); }, []);

  // Der geladene Stand – er ist nicht getippt und geht nicht hinaus. Gesetzt nur beim
  // Wechsel des Datensatzes, nicht bei jedem neuen Wert.
  const latest = useRef({ value, save });
  latest.current = { value, save };
  const loaded = useRef(value);
  useEffect(() => {
    void saver.flush();
    loaded.current = latest.current.value;
  }, [resetKey, saver]);

  // `save` reist mit dem Wert (Saver) – er gehört zu dem Stand, den er speichert.
  useEffect(() => {
    if (Object.is(value, loaded.current)) return;
    saver.change(value, latest.current.save);
  }, [value, saver]);

  const saveNow = useCallback(() => saver.flush(), [saver]);
  return { status, errorMsg, saveNow };
}

/**
 * Speichert, sobald sich die `signature` (serialisierter Zustand) ändert und `canSave`
 * wahr ist. Gibt `flush` zurück, um sofort zu speichern (Enter).
 *
 * Pro Signatur wird **höchstens einmal** automatisch gespeichert: schlägt ein Speichern
 * fehl, ginge derselbe Stand sonst in Endlosschleife wieder hinaus. Erneut gesendet wird
 * erst nach einer Änderung (neue Signatur) oder per `flush()`. Wird `canSave` falsch (der
 * Server hat den Stand schon), verfällt der offene Stand.
 */
export function useAutosaveSignature(
  signature: string,
  canSave: boolean,
  onSave: () => Promise<unknown> | void,
): () => void {
  const saver = useSaver<string>();
  const fired = useRef<string | null>(null);
  const now = useRef({ signature, canSave, onSave });
  now.current = { signature, canSave, onSave };
  const queue = useCallback((sig: string) => {
    const save = now.current.onSave;
    saver.change(sig, (s) => { fired.current = s; return save(); });
  }, [saver]);

  useEffect(() => {
    if (!canSave) { saver.cancel(); return; }
    if (fired.current !== signature) queue(signature);
  }, [signature, canSave, saver, queue]);

  // Sofort speichern (Enter): erlaubt bewusst einen erneuten Versuch für dieselbe Signatur.
  return useCallback(() => {
    if (!now.current.canSave) return;
    if (!saver.pending()) queue(now.current.signature);
    void saver.flush();
  }, [saver, queue]);
}
