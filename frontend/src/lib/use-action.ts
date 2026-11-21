'use client';

import { useCallback, useState } from 'react';

/**
 * ►►► **Eine Handlung am Server – läuft, scheitert oder gelingt. EIN Baustein dafür.** ◄◄◄
 *
 * `run(fn)` setzt `busy`, leert den Fehler, wartet auf `fn` und gibt ihr Ergebnis zurück. Scheitert
 * sie, steht der Satz des Servers in `error`, `onError` sieht den Fehler selbst, und `run` gibt
 * `undefined`. `busy` sperrt Handlungen, nie Felder (Hausregel). Was die Antwort bewirkt (in den
 * Cache legen, weiter navigieren), macht der Aufrufer – der Baustein kennt nur den Ablauf.
 * `fallback` ist der Satz, wenn der Fehler keinen eigenen hat.
 *
 * **Jede Handlung am Server läuft hierüber** – ein eigenes `[busy, setBusy]` neben einem
 * `api.…`-Aufruf weist `scripts/action.test.mjs` ab.
 */
export function useAction(fallback?: string) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const run = useCallback(async <T,>(fn: () => Promise<T>,
                                    onError?: (e: unknown) => void): Promise<T | undefined> => {
    setBusy(true);
    setError(null);
    try {
      return await fn();
    } catch (e) {
      setError(errorText(e, fallback));
      onError?.(e);
      return undefined;
    } finally {
      setBusy(false);
    }
  }, [fallback]);
  return { busy, error, setError, run };
}

/** **Der Satz eines Fehlers** – die Meldung des Servers, sonst `fallback`, sonst der Wert selbst. */
export function errorText(e: unknown, fallback?: string): string {
  if (e instanceof Error) return e.message;
  return fallback ?? String(e);
}
