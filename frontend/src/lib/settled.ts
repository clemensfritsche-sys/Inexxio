/**
 * ►►► **Was lokal schon entschieden ist – für eine Weile** (`lib/proposals`). ◄◄◄
 *
 * «Übernehmen» oder ✕ blendet einen Vorschlag sofort aus, auch wenn eine Antwort, die vor dem
 * Speichern unterwegs war, ihn noch als offen nennt. Das gilt **nur `SETTLE_MS` lang**: ob ein
 * Vorschlag offen ist, leitet der Server aus dem Log ab. Scheitert das Speichern nach
 * «Übernehmen», meldet der Server ihn danach weiter als offen – und er ist wieder da.
 * Kein Dauer-Merker, kein Haken ins Auto-Save.
 */

/** So lange bleibt ein lokal entschiedener Vorschlag ausgeblendet (Auto-Save + Antwort). */
export const SETTLE_MS = 30_000;

const since = new Map<number, number>();

/** Den Vorschlag ab jetzt ausblenden – für `SETTLE_MS`. */
export function markSettled(id: number, now: number = Date.now()): void {
  since.set(id, now);
}

/** Ist er gerade lokal entschieden? Nach `SETTLE_MS` nicht mehr (dann zählt der Server). */
export function isSettled(id: number, now: number = Date.now()): boolean {
  const at = since.get(id);
  if (at === undefined) return false;
  if (now - at < SETTLE_MS) return true;
  since.delete(id);
  return false;
}
