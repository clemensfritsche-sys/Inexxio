/**
 * ►►► **Der Kern des Auto-Saves** – ohne React, darum allein prüfbar
 * (`scripts/autosave.test.mjs`); die Hooks in `lib/use-autosave.ts` sind nur seine Hülle. ◄◄◄
 *
 * - **Ein Stand ist offen** (`dirty`), sobald `change` ihn meldet; nach `delay` geht er
 *   hinaus, `flush` schickt ihn sofort (Enter, Wechsel des Datensatzes, Verlassen).
 * - **Speichern geschieht hintereinander**: läuft eins, wartet der nächste Stand, bis es
 *   fertig ist, und geht dann mit dem **neuesten** Wert – nie überholt ein älterer PATCH
 *   einen neueren.
 * - **Ein Stand reist mit seiner Speicherfunktion**: was für Datensatz A getippt wurde, geht
 *   an A, auch wenn die Ansicht schon B zeigt.
 * - Ein Fehler lässt den Stand nicht still fallen: er geht an `onError`; `flush` versucht
 *   ihn erneut, eine neue Änderung ebenso. Von selbst wiederholt wird nichts (keine Schleife).
 */
export type SaverStatus = 'dirty' | 'saving' | 'saved' | 'error';

export interface Saver<T> {
  /** Ein neuer Stand – er geht nach der Wartezeit hinaus. */
  change(value: T, save: (value: T) => Promise<unknown> | void): void;
  /** Der offene Stand sofort; das Versprechen hält, bis auch Nachgereichtes gespeichert ist. */
  flush(): Promise<void>;
  /** Den offenen Stand verwerfen (der Server hat ihn schon, oder er darf nicht hinaus). */
  cancel(): void;
  /** Ist ein Stand offen oder unterwegs? */
  pending(): boolean;
}

export function createSaver<T>(opts: {
  delay: number;
  onStatus?: (status: SaverStatus) => void;
  onError?: (e: unknown) => void;
}): Saver<T> {
  type Job = { value: T; save: (value: T) => Promise<unknown> | void };
  let next: Job | null = null;
  let failed: Job | null = null;
  let running: Promise<void> | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;

  const stopTimer = () => { if (timer) { clearTimeout(timer); timer = null; } };

  function start(job: Job): Promise<void> {
    opts.onStatus?.('saving');
    running = Promise.resolve()
      .then(() => job.save(job.value))
      .then(() => { failed = null; opts.onStatus?.(next ? 'dirty' : 'saved'); },
        (e: unknown) => { failed = job; opts.onStatus?.('error'); opts.onError?.(e); })
      .finally(() => { running = null; });
    return running;
  }

  async function flush(): Promise<void> {
    stopTimer();
    while (running) await running;
    const job = next ?? failed;
    if (!job) return;
    next = null;
    await start(job);
    // Was während des Speicherns dazukam, geht gleich hinterher – mit dem neuesten Wert.
    if (next) await flush();
  }

  return {
    change(value, save) {
      next = { value, save };
      opts.onStatus?.('dirty');
      stopTimer();
      timer = setTimeout(() => { timer = null; void flush(); }, opts.delay);
    },
    flush,
    cancel() { stopTimer(); next = null; },
    pending: () => next !== null || running !== null,
  };
}
