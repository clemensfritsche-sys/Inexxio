'use client';

import { createContext, useContext } from 'react';
import type { Handgriff } from '@/types';
import type { Creatable } from '@/components/erp/feed-panel';

/** Ein Entwurf, den ein Handgriff öffnet – die Werte vorausgefüllt, `handgriff` wird erledigt,
 *  sobald der Entwurf freigegeben ist. */
export interface DraftFromHandgriff {
  kind: 'user' | 'organization' | 'article' | 'order' | 'document';
  /** Die einfachen Werte als Text (Felder des Entwurfs). */
  values: Record<string, string>;
  /** Die Werte, wie die KI sie vorbereitete (Zeilen eines Auftrags). */
  body?: Record<string, unknown>;
  handgriff: number;
}

/**
 * **Wo das ERP einen Entwurf hat** – überall, wo es «Neu anlegen» gibt (Person, Firma, Artikel,
 * Auftrag, Dokument): die Anlage-Route der Handlung ist der Schlüssel. Der Entwurf öffnet
 * ausgefüllt; mit «Freigeben» ist der Vorschlag erledigt.
 */
const DRAFTS: Record<string, DraftFromHandgriff['kind']> = {
  '/api/v1/erp/records': 'user',
  '/api/v1/admin/companies': 'organization',
  '/api/v1/erp/articles': 'article',
  '/api/v1/erp/orders': 'order',
  '/api/v1/erp/documents': 'document',
};

/** Welche Anlage der Feed zu einem Entwurf öffnet – die eine Zuordnung (ERP und Website-«+»). */
export const CREATABLE_OF: Record<DraftFromHandgriff['kind'], Creatable> = {
  user: 'person', organization: 'company', article: 'article', order: 'order', document: 'document',
};

/** ►► **Der Entwurf zu einem Vorschlag** – oder `null`, wenn das ERP dafür keinen hat. Die eine
 *  Ableitung: die Karte im Gespräch und die Feed-Seite (auch vom «+» der Website) lesen sie. ◄◄ */
export function draftFrom(h: Handgriff): DraftFromHandgriff | null {
  const kind = h.method === 'POST' ? DRAFTS[h.path] : undefined;
  if (!kind) return null;
  const body = (h.body && typeof h.body === 'object' ? h.body : {}) as Record<string, unknown>;
  // Die einfachen Werte als Text für die Felder; ein Verweis auf einen anderen Vorschlag
  // ({"$handgriff": n}) ist noch keine Nummer und bleibt leer, bis jener übernommen ist.
  const values = Object.fromEntries(Object.entries(body)
    .filter(([, v]) => typeof v === 'string' || typeof v === 'number' || typeof v === 'boolean')
    .map(([k, v]) => [k, String(v)]));
  return { kind, values, body, handgriff: h.id };
}

/**
 * **Was ein Handgriff im Feed auslösen kann** – an EINER Stelle (Feed-Seite bzw. `/erp/erfassen`)
 * gehalten, damit «Auf einen Blick» in jedem Verlauf dieselben Wege nimmt wie das «+»:
 *
 * - `openDraft` – «Entwurf öffnen»: der **bestehende** Anlege-Entwurf, vorausgefüllt; angelegt
 *   wird erst mit seiner Freigabe (kein zweiter Anlageweg), danach ist der Handgriff erledigt.
 *
 * Ausserhalb des Feeds (`null`) steht dieser Knopf nicht da.
 */
export interface CaptureActions {
  openDraft: (d: DraftFromHandgriff) => void;
}

export const CaptureContext = createContext<CaptureActions | null>(null);

export function useCapture(): CaptureActions | null {
  return useContext(CaptureContext);
}
