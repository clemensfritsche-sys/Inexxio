'use client';

import { createContext, useContext, useEffect, useState } from 'react';
import { QueryClient, useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { qk } from '@/lib/queries';
import { tell } from '@/lib/notice';
import { isSettled, markSettled } from '@/lib/settled';
import type { Pinned, Proposal, Recording } from '@/types';

/**
 * ►►► **Die Vorschläge der KI – gelesen an EINER Stelle** (Bauplan Phase 3, «Oberfläche»). ◄◄◄
 *
 * Ein Feld (`useField`) fragt die offenen Vorschläge seines Datensatzes unter EINEM Schlüssel
 * (`qk.proposals`) – alle Felder einer Ansicht teilen die Antwort. Das Angeheftete im Verlauf
 * fragt `qk.pins`. Beide lädt jeder Schreibvorgang nach (`lib/feed.LOGGED`): ob ein Vorschlag
 * offen ist, leitet der Server aus dem Log ab.
 *
 * **Nur im ERP**: Vorschläge sind Sache des Personals. Das Konto und die Kundenseiten tragen
 * denselben Feld-Baustein, aber keinen `ProposalClient` – dort fragt kein Feld.
 */
export const ProposalClient = createContext<QueryClient | null>(null);

/** Ein Client, der nie fragt – nur damit `useQuery` ausserhalb des ERP etwas hat. */
let idle: QueryClient | null = null;
const idleClient = () => (idle ??= new QueryClient());

/**
 * **Was lokal schon entschieden ist** («Übernehmen», ✕) – verschwindet sofort, auch wenn eine
 * Antwort, die vor dem Speichern unterwegs war, ihn noch als offen nennt; nach 30 s zählt
 * wieder der Server (`lib/settled`): scheiterte das Speichern, ist der Vorschlag wieder da.
 */
const stillOpen = (list: Proposal[]) => list.filter((p) => !isSettled(p.id));
/** Das Angeheftete ohne das, was lokal schon entschieden ist – auch für die Antwort einer
 *  Handlung («neu ansehen», «lösen»). */
export const pinnedOpen = (p: Pinned): Pinned => ({ ...p, proposals: stillOpen(p.proposals) });

/** Die offenen Vorschläge eines Datensatzes – ohne Datensatz oder ausserhalb des ERP keine Frage. */
export function useProposals(objectId: number | null | undefined, wanted = true) {
  const client = useContext(ProposalClient);
  return useQuery({
    queryKey: qk.proposals(objectId ?? 0),
    queryFn: ({ signal }) => api.proposals(objectId!, { signal }).then(stillOpen),
    enabled: !!client && !!objectId && wanted,
    meta: { what: 'Vorschläge' },
  }, client ?? idleClient());
}

/** **Das Angeheftete** – offene Vorschläge (immer, zuerst) und die Hinweise. */
export function usePinned(objectId: number) {
  const client = useContext(ProposalClient);
  return useQuery({
    queryKey: qk.pins(objectId),
    queryFn: ({ signal }) => api.pins(objectId, { signal }).then(pinnedOpen),
    enabled: !!client,
    meta: { what: 'Angeheftetes' },
  }, client ?? idleClient());
}

/** Meine Erfassungen, die noch nicht abgelegt sind («+» und das Angeheftete). */
export function useOpenIntakes() {
  const client = useContext(ProposalClient);
  return useQuery({
    queryKey: qk.openIntakes(),
    queryFn: ({ signal }) => api.openIntakes({ signal }),
    enabled: !!client,
    meta: { what: 'Erfassungen' },
  }, client ?? idleClient());
}

/** Meine Aufnahmen, die noch nicht fertig sind («+» unter «Nicht abgelegt»: wird abgeschrieben
 *  oder fehlgeschlagen). Fertige stehen als offene Erfassung da (`useOpenIntakes`). */
export function useOpenRecordings() {
  const client = useContext(ProposalClient);
  return useQuery<Recording[]>({
    queryKey: qk.openRecordings(),
    queryFn: ({ signal }) => api.openRecordings({ signal }),
    enabled: !!client,
    meta: { what: 'Aufnahmen' },
  }, client ?? idleClient());
}

/** Den Vorschlag lokal schliessen – in beiden Antworten, in denen er steht. */
function settle(client: QueryClient | null, p: Proposal): void {
  markSettled(p.id);
  if (!client) return;
  client.setQueryData<Proposal[]>(qk.proposals(p.object_id), (l) => l?.filter((x) => x.id !== p.id));
  client.setQueryData<Pinned>(qk.pins(p.object_id),
    (pin) => pin && { ...pin, proposals: pin.proposals.filter((x) => x.id !== p.id) });
}

/** Die zwei Entscheide am Vorschlag: übernommen (lokal, der Server leitet es ab) und ✕. */
export function useDecide() {
  const client = useContext(ProposalClient);
  return {
    /** «Übernehmen» ist Tippen – hier verschwindet nur das Zeichen, bis der Server es weiss. */
    taken: (p: Proposal) => settle(client, p),
    reject: (p: Proposal) => api.rejectProposal(p.id)
      .then(() => settle(client, p), tell(`Vorschlag «${p.label}»`, 'Nicht verworfen')),
  };
}

/** **«Zum Feld»** – das Fenster am Feld öffnen (`ProposalMark` hört darauf). */
export const PROPOSAL_OPEN = 'inexxio:proposal-open';

/** Welche dieser Vorschläge haben ihr Feld gerade auf der Seite? (Reiter wechseln, Karten
 *  klappen – darum beobachtet, nicht einmal gefragt.) */
export function useFieldsOnPage(ids: number[]): Set<number> {
  const [found, setFound] = useState<Set<number>>(() => new Set());
  const key = ids.join(',');
  useEffect(() => {
    const wanted = key ? key.split(',') : [];
    const look = () => {
      const now = new Set(wanted.filter((id) => document.querySelector(`[data-proposal="${id}"]`)).map(Number));
      setFound((was) => (was.size === now.size && [...now].every((x) => was.has(x)) ? was : now));
    };
    look();
    if (!wanted.length) return;
    const mo = new MutationObserver(look);
    mo.observe(document.body, { childList: true, subtree: true, attributes: true, attributeFilter: ['data-proposal'] });
    return () => mo.disconnect();
  }, [key]);
  return found;
}

/** Steht das Feld zu diesem Vorschlag auf der Seite? Dann dorthin und das Fenster öffnen. */
export function openAtField(id: number): boolean {
  const el = document.querySelector(`[data-proposal="${id}"]`);
  if (!el) return false;
  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  window.dispatchEvent(new CustomEvent(PROPOSAL_OPEN, { detail: { id } }));
  return true;
}
