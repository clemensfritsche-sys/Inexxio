/**
 * ►►► **Ein Fehler ist nie stumm** – die eine Stelle, an der das Frontend einen gescheiterten
 * Abruf meldet. ◄◄◄
 *
 * Wer lädt und bei einem Fehler nichts anderes zu tun hat, schreibt `.catch(tell('Aufträge'))`
 * statt `.catch(() => {})`: unten rechts steht dann «Nicht geladen: Aufträge – <Grund vom
 * Server>», statt dass eine leere Liste «nichts da» vortäuscht. Dieselbe Meldung
 * kommt in einem Fenster von fünf Minuten nur einmal (ein Abgleich im Hintergrund meldet
 * sich sonst alle 30 s). Angezeigt wird sie von `components/layout/notice-host.tsx`.
 */

export interface Notice { id: number; text: string }

const REPEAT_MS = 5 * 60 * 1000;
const SHOW_MS = 10_000;

let shown: Notice[] = [];
let nextId = 1;
const lastAt = new Map<string, number>();
const listeners = new Set<(list: Notice[]) => void>();

function publish() { listeners.forEach((fn) => fn(shown)); }

/** Eine Meldung zeigen – dieselbe nur einmal je fünf Minuten. */
export function notify(text: string, now = Date.now()): void {
  const last = lastAt.get(text);
  if (last !== undefined && now - last < REPEAT_MS) return;
  lastAt.set(text, now);
  const notice = { id: nextId++, text };
  shown = [...shown, notice].slice(-3);
  publish();
  if (typeof window !== 'undefined') window.setTimeout(() => dismiss(notice.id), SHOW_MS);
}

export function dismiss(id: number): void {
  shown = shown.filter((n) => n.id !== id);
  publish();
}

export function subscribe(fn: (list: Notice[]) => void): () => void {
  listeners.add(fn);
  fn(shown);
  return () => { listeners.delete(fn); };
}

/** Der Grund in einem Satz – die Meldung des Servers, sonst «keine Antwort». */
function reasonOf(e: unknown): string {
  const msg = e instanceof Error ? e.message.trim() : '';
  return msg || 'keine Antwort vom Server';
}

/** **Der Ersatz für `.catch(() => {})`** – `what` ist, was nicht kam («Aufträge»), oder mit
 *  `verb`, was nicht ging («Nicht abgeglichen: Postfach»). */
export function tell(what: string, verb = 'Nicht geladen'): (e: unknown) => void {
  return (e) => notify(`${verb}: ${what} – ${reasonOf(e)}`);
}
