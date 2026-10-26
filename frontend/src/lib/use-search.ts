import { useEffect, useState } from 'react';

/**
 * **Eine Suche beim Tippen – entprellt, mit Veralterungs-Schutz.** Die eine Stelle für
 * «tippen sucht»: Referenzfeld (`SearchSelect`), Scanner-Vorschläge, Empfänger einer
 * Nachricht, Artikelnamen. Vorher stand dasselbe Muster (`setTimeout` + `stale = true`)
 * an jeder dieser Stellen ausgeschrieben.
 *
 * - **Entprellt** um `delay` ms – nicht jede Taste fragt den Server.
 * - **Eine ältere Antwort überholt nie eine neuere** (tippen und sofort löschen).
 * - **Ohne Suche oder mit zu kurzer Eingabe gibt es keine Treffer** – `search` darf
 *   `null` sein, dann ist die Suche schlicht aus (z. B. ein verifizierender Scan).
 * - **Ein Fehler leert die Liste und sagt es** (`failed`), statt eine alte stehen zu lassen.
 */
export function useSearch<T>(
  query: string,
  search: ((q: string) => Promise<T[]>) | null | undefined,
  { delay = 250, minLength = 1 }: { delay?: number; minLength?: number } = {},
): { hits: T[]; failed: boolean; pending: boolean } {
  const [hits, setHits] = useState<T[]>([]);
  const [failed, setFailed] = useState(false);
  // Für welche Eingabe die Treffer gelten – solange sie nicht zur Eingabe passt, sucht es
  // noch (`pending`): «Keine Treffer» VOR der Antwort war eine falsche Aussage (Chrome-Test).
  const [answered, setAnswered] = useState<string | null>(null);
  const q = query.trim();
  useEffect(() => {
    if (!search || q.length < minLength) { setHits([]); setFailed(false); setAnswered(q); return; }
    let stale = false;
    const t = setTimeout(() => {
      search(q)
        .then((r) => { if (!stale) { setHits(r); setFailed(false); setAnswered(q); } })
        .catch(() => { if (!stale) { setHits([]); setFailed(true); setAnswered(q); } });
    }, delay);
    return () => { stale = true; clearTimeout(t); };
  }, [q, search, delay, minLength]);
  const pending = !!search && q.length >= minLength && answered !== q;
  return { hits, failed, pending };
}
