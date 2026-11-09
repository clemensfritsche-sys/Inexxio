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
  /** Das Protokoll eines Moduls – unter seinem Auftrag (lädt mit ihm nach). */
  stepRecord: (order: number, step: number) => key('order', order, 'record', step),
  transfer: (order: number, step: number) => key('order', order, 'transfer', step),
  correctable: (order: number, step: number) => key('order', order, 'correctable', step),
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
  history: (objectId: number) => key('history', objectId),
  senders: () => key('senders'),
  mailboxes: (company: number) => key('mailboxes', company),
  newsletter: (person: number) => key('newsletter', person),
  company: (id: number) => key('company', id),
  /** Das Angeheftete eines Datensatzes (offene Handgriffe, Wissen). */
  pins: (objectId: number) => key('pins', objectId),
  /** Meine offenen Gespräche (die Zahl am «+»). */
  openTalks: () => key('talks', 'open'),
  /** Ein Gespräch. */
  talk: (id: number) => key('talks', id),
  /** Meine Aufnahmen, die noch nicht fertig sind (Phase 4). */
  openRecordings: () => key('recordings', 'open'),
  /** Die Zeiterfassung einer Person (ein Monat) und einer Gesellschaft (Feiertage, Regeln). */
  time: (person: number, month?: string) => key('time', person, month ?? null),
  companyTime: (company: number, year: number) => key('time', 'company', company, year),
  /** Was sich selten ändert: der Modul-Katalog, die Auswahl für einen Entwurf. */
  catalog: (what: string, ...rest: unknown[]) => key('catalog', what, ...rest),
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
