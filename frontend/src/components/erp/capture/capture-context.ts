'use client';

import { createContext, useContext } from 'react';

/** Ein Entwurf, den ein Handgriff öffnet – die Werte vorausgefüllt, `handgriff` wird erledigt,
 *  sobald der Entwurf freigegeben ist. */
export interface DraftFromHandgriff {
  kind: 'user' | 'organization' | 'document';
  values: Record<string, string>;
  handgriff: number;
}

/**
 * **Was ein Handgriff im Feed auslösen kann** – an EINER Stelle (Feed-Seite bzw. `/erp/erfassen`)
 * gehalten, damit das Angeheftete in jedem Verlauf dieselben Wege nimmt wie das «+»:
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
