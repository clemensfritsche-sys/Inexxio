'use client';

import { useEffect, useState } from 'react';
import { QueryCache, QueryClient } from '@tanstack/react-query';
import { DATA_CHANGED, MESSAGES_CHANGED, areaKey, feedKey, touchedBy } from '@/lib/feed';
import { TODO_CHANGED } from '@/lib/todo';
import { tell } from '@/lib/notice';

/** Ab wann eine Liste als veraltet gilt: kehrt man nach einer Pause zurück (Tab wieder
 *  sichtbar), lädt sie EINMAL nach. Bewusst kein Polling – das kostet Cloud-Run-Zeit, ohne
 *  dass jemand hinschaut. */
const STALE_AFTER_MS = 60_000;

/** Was eine Query bei einem Fehler meldet – «Nicht geladen: <what> – <Grund>». */
declare module '@tanstack/react-query' {
  interface Register { queryMeta: { what: string } }
}

/**
 * **Der Query-Client des ERP** – einer je Seitenaufruf (`app/(erp)/layout.tsx`).
 *
 * - **Nichts scheitert still**: jeder Fehler einer Query geht über `lib/notice` (`tell`),
 *   genannt mit `meta.what`.
 * - Kein zweiter Wiederholungs-Weg: `lib/api.ts` wiederholt Transportfehler selbst.
 * - Gleichzeitige Abrufe derselben Liste sind EINER (React Query entdoppelt je Schlüssel).
 */
function feedClient(): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (e, query) => tell(query.meta?.what ?? 'Daten')(e),
    }),
    defaultOptions: {
      queries: { retry: false, staleTime: STALE_AFTER_MS, refetchOnWindowFocus: true },
    },
  });
}

/**
 * Der Client samt Anschluss an `lib/api.ts` – **die eine Stelle der Invalidierung**: nach
 * jedem Schreibvorgang werden nur die betroffenen Bereiche invalidiert (`touchedBy(path)`,
 * Listen des Feeds und Detailansichten, unbekannt → alle). Was gerade angezeigt wird, lädt
 * sofort nach; der Rest beim nächsten Gebrauch. Neue Nachrichten laden Verlauf, «zu tun» und
 * Personen (ein unbekannter Absender ist jetzt eine Person), eine erledigte Aufgabe «zu tun».
 */
export function useFeedClient(): QueryClient {
  const [client] = useState(feedClient);
  useEffect(() => {
    const invalidate = (key: readonly string[]) => { void client.invalidateQueries({ queryKey: key }); };
    const onChanged = (e: Event) => {
      const path = (e as CustomEvent<{ path?: string }>).detail?.path ?? '';
      touchedBy(path).forEach((area) => invalidate(areaKey(area)));
    };
    const onMessages = () => {
      invalidate(feedKey('todo')); invalidate(feedKey('people')); invalidate(areaKey('messages'));
    };
    const onTodo = () => invalidate(feedKey('todo'));
    window.addEventListener(DATA_CHANGED, onChanged);
    window.addEventListener(MESSAGES_CHANGED, onMessages);
    window.addEventListener(TODO_CHANGED, onTodo);
    return () => {
      window.removeEventListener(DATA_CHANGED, onChanged);
      window.removeEventListener(MESSAGES_CHANGED, onMessages);
      window.removeEventListener(TODO_CHANGED, onTodo);
    };
  }, [client]);
  return client;
}
