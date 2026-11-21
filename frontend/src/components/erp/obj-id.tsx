'use client';

import { createContext, useContext } from 'react';
import { formatObjectId } from '@/lib/utils';

/** Stellt eine Funktion bereit, um per Objektnummer den zugehörigen Datensatz zu öffnen. */
export const ErpNavContext = createContext<((objectId: number) => void) | null>(null);

export function useErpNav(): ((objectId: number) => void) | null {
  return useContext(ErpNavContext);
}

/**
 * Zeigt eine 9-stellige Objektnummer an. Liegt ein Navigations-Handler im Context
 * (ERP-Feed) und ist die Nummer vorhanden, wird sie zum klickbaren Link, der den
 * referenzierten Datensatz öffnet.
 */
export function ObjId({ value, mono = true, label }: {
  value: number | null | undefined;
  mono?: boolean;
  /** **Wie die Nummer heisst**, wenn sie genauer ist als der Datensatz (Einzelinstanz
   *  `100000123-3` → geöffnet wird die Instanz). */
  label?: string;
}) {
  const nav = useErpNav();
  const text = label ?? formatObjectId(value);
  // **Eine Objektnummer sieht überall gleich aus**: feste Grösse, Ziffern tabellarisch.
  const baseStyle: React.CSSProperties = {
    fontFamily: mono ? 'var(--font-mono), monospace' : undefined,
    fontSize: 12.5, fontWeight: 600, fontVariantNumeric: 'tabular-nums', lineHeight: 1.4,
  };
  if (!nav || value == null) {
    return <span style={baseStyle}>{text}</span>;
  }
  // ►►► **Sie sieht aus wie eine Nummer, nicht wie ein Hyperlink** ◄◄◄ – im Ruhezustand in
  // Textfarbe; Farbe und Unterstreichung erst beim Zeigen (`.erp-objid`). Form wie ohne Ziel.
  return (
    <button
      type="button"
      className="erp-objid"
      onClick={(e) => { e.stopPropagation(); nav(value); }}
      data-tip="Datensatz öffnen"
      style={baseStyle}
    >
      {text}
    </button>
  );
}
