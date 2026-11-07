'use client';

import { createContext, useContext } from 'react';
/**
 * **Was ein Vorschlag im Feed auslösen kann** – an EINER Stelle (Feed-Seite) gehalten, damit das
 * Angeheftete in jedem Verlauf dieselben Wege nimmt wie «+»:
 *
 * - `createDraft` – «Entwurf öffnen»: der **bestehende** Anlege-Entwurf, vorausgefüllt; angelegt
 *   wird erst mit seiner Freigabe (kein zweiter Anlageweg).
 *
 * Ausserhalb des Feeds (`null`) stehen diese Knöpfe nicht da.
 */
export interface CaptureActions {
  createDraft: (type: 'user' | 'organization', values: Record<string, string>) => void;
}

export const CaptureContext = createContext<CaptureActions | null>(null);

export function useCapture(): CaptureActions | null {
  return useContext(CaptureContext);
}
