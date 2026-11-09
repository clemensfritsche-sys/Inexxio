'use client';

import { createContext, useContext } from 'react';

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
