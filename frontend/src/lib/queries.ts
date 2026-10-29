'use client';

import { useEffect, useRef, useState } from 'react';
import { hashKey, keepPreviousData, useQuery, type QueryKey } from '@tanstack/react-query';
import { api, type Req } from '@/lib/api';
import type { Detail } from '@/lib/feed';

/**
 * ►►► **Die Schlüssel der Detailansichten – an EINER Stelle gebaut.** ◄◄◄
 *
 * Das erste Glied ist der Bereich aus `lib/feed.DETAILS`; über ihn invalidiert die Tabelle
 * `TOUCHES` nach einem Schreibvorgang (`lib/use-feed.ts`). Die Listen des Feeds stehen unter
 * `feed.feedKey`. **Query-Daten treiben nie ein Formular**: ein Formular mit Auto-Save wird
 * einmal befüllt und hält dann seinen eigenen Zustand.
 */
const key = (area: Detail, ...rest: unknown[]) => [area, ...rest] as const;

type Scope = { person: number } | { company: number };

export const qk = {
  order: (id: number) => key('order', id),
  instance: (id: number) => key('instance', id),
  article: (id: number) => key('article', id),
  articleProcess: (id: number) => key('articleProcess', id),
  stock: (id: number) => key('stock', id),
  units: (id: number, statuses: readonly string[]) => key('units', id, statuses),
  genealogy: (id: number, suffix: number) => key('units', id, 'genealogy', suffix),
  unitOptions: (opts: object) => key('unitOptions', opts),
  document: (id: number) => key('document', id),
  documentsOf: (id: number) => key('documentsOf', id),
  payments: (scope: Scope) => key('payments', scope),
  messages: (scope: { person?: number; company?: number }) => key('messages', scope),
  senders: () => key('senders'),
  mailboxes: (company: number) => key('mailboxes', company),
  newsletter: (person: number) => key('newsletter', person),
  company: (id: number) => key('company', id),
};

/** Die Dokumente an einem Datensatz – Kacheln, Rechtstexte. */
export function useDocumentsOf(objectId: number | null | undefined) {
  return useQuery({
    queryKey: qk.documentsOf(objectId ?? 0),
    queryFn: ({ signal }) => api.documentsOf(objectId!, { signal }),
    enabled: !!objectId,
    meta: { what: 'Dokumente' },
  });
}

/** Wie lange eine Eingabe ruhen muss, bevor eine Prüfung oder Vorschau fragt. */
const SETTLE_MS = 250;

/** Der Wert, nachdem er `ms` lang gleich geblieben ist (verglichen wie ein Query-Schlüssel). */
export function useSettled<T>(value: T, ms = SETTLE_MS): T {
  const [settled, setSettled] = useState(value);
  const latest = useRef(value);
  latest.current = value;
  const hash = hashKey([value]);
  useEffect(() => {
    const t = setTimeout(() => setSettled(latest.current), ms);
    return () => clearTimeout(t);
  }, [hash, ms]);
  return settled;
}

/**
 * ►►► **Prüfen und Vorschau – eine Form für alle** (Auftrag, Artikel, Zeiterfassung). ◄◄◄
 *
 * Die Eingabe wird entprellt (`SETTLE_MS`) und ist Teil des Schlüssels: eine Antwort auf eine
 * ältere Eingabe kann die neuere nie überschreiben, eine überholte Anfrage bricht ab
 * (`signal`). Bis die neue Antwort da ist, bleibt die alte stehen (`keepPreviousData`) – die
 * Fläche springt nicht. `input === null` heisst: nichts zu fragen.
 */
export function useDebouncedQuery<I, R>({ name, input, ask, what }: {
  /** Wofür (erstes Glied des Schlüssels) – nie invalidiert: die Antwort hängt an der Eingabe. */
  name: string;
  input: I | null;
  ask: (input: I, req: Req) => Promise<R>;
  what: string;
}) {
  const settled = useSettled(input);
  const queryKey: QueryKey = ['check', name, settled];
  return useQuery({
    queryKey,
    queryFn: ({ signal }) => ask(settled as I, { signal }),
    enabled: settled !== null,
    placeholderData: keepPreviousData,
    staleTime: Infinity,
    meta: { what },
  });
}
