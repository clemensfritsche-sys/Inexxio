'use client';

import { createContext, useContext, useEffect, useRef, useState } from 'react';
import { QueryClient, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import { tell } from '@/lib/notice';
import type { Pinned, Recording, Talk } from '@/types';

/**
 * ►►► **Der Assistent – gelesen an EINER Stelle** (Projektakte, Phase 5). ◄◄◄
 *
 * Gespräche (`qk.openTalks`), Aufnahmen (`qk.openRecordings`) und das Angeheftete (`qk.pins`)
 * sind Queries wie alles im ERP; was ein Handgriff ändert, lädt `lib/feed` nach (ein Handgriff
 * kann alles, was das ERP kann). **Nur im ERP**: der Assistent ist Sache des Personals – ausserhalb
 * gibt es keinen `AssistantClient`, und nichts fragt.
 */
export const AssistantClient = createContext<QueryClient | null>(null);

/** Ein Client, der nie fragt – nur damit `useQuery` ausserhalb des ERP etwas hat. */
let idle: QueryClient | null = null;
const idleClient = () => (idle ??= new QueryClient());

/** Meine offenen Gespräche – die neuesten zuerst. */
export function useOpenTalks() {
  const client = useContext(AssistantClient);
  return useQuery<Talk[]>({
    queryKey: qk.openTalks(),
    queryFn: ({ signal }) => api.openTalks({ signal }),
    enabled: !!client,
    meta: { what: 'Gespräche' },
  }, client ?? idleClient());
}

/** Meine Aufnahmen, die noch nicht fertig sind (wird abgeschrieben, gescheitert). */
export function useOpenRecordings() {
  const client = useContext(AssistantClient);
  return useQuery<Recording[]>({
    queryKey: qk.openRecordings(),
    queryFn: ({ signal }) => api.openRecordings({ signal }),
    enabled: !!client,
    meta: { what: 'Aufnahmen' },
  }, client ?? idleClient());
}

/**
 * ►►► **Die Zahl am «+»** – meine offenen Gespräche und Aufnahmen, die nicht abgeschrieben werden
 * konnten. Eine Aufnahme, die gerade abgeschrieben wird oder deren Text in der Eingabe wartet, ist
 * kein Gespräch – sie zählt nicht. Dieselben Listen wie «Offene Gespräche» im «+» – EINE Quelle; an
 * der Person zählt es nicht (`services/todo`). ◄◄◄
 */
export function useUnfinished(): { count: number; failed: boolean } {
  const talks = useOpenTalks().data ?? [];
  const failed = (useOpenRecordings().data ?? []).filter((r) => r.state === 'failed');
  return { count: talks.length + failed.length, failed: failed.length > 0 };
}

/**
 * ►►► **Auf einen Blick** – kommt sofort mit dem letzten Stand; sagt der Server `stale` (im
 * Umfeld hat sich seither etwas geändert), wählt die KI einmal neu, still im Hintergrund. ◄◄◄
 * Sonst fragt nichts die KI – kein Aufruf, keine Kosten (`services/pins`).
 */
export function usePinned(objectId: number) {
  const client = useContext(AssistantClient);
  const query = useQuery<Pinned>({
    queryKey: qk.pins(objectId),
    queryFn: ({ signal }) => api.pins(objectId, { signal }),
    enabled: !!client,
    meta: { what: 'Angeheftetes' },
  }, client ?? idleClient());
  const asked = useRef<string>('');
  const [choosing, setChoosing] = useState(false);
  const stale = !!query.data?.stale;
  const mark = query.data?.mark ?? 0;
  useEffect(() => {
    if (!client || !stale) return;
    const key = `${objectId}:${mark}`;
    if (asked.current === key) return;             // je Stand des Umfelds einmal – nie im Kreis
    asked.current = key;
    setChoosing(true);
    api.refreshPins(objectId).then((next) => client.setQueryData(qk.pins(objectId), next),
      tell('Angeheftetes', 'Nicht neu gewählt')).finally(() => setChoosing(false));
  }, [client, objectId, stale, mark]);
  return { ...query, choosing };
}

/** Ein Gespräch – gelesen, solange es offen ist. */
export function useTalk(id: number | null) {
  const client = useContext(AssistantClient);
  return useQuery<Talk>({
    queryKey: qk.talk(id ?? 0),
    queryFn: ({ signal }) => api.talk(id!, { signal }),
    enabled: !!client && !!id,
    meta: { what: 'Gespräch' },
  }, client ?? idleClient());
}
