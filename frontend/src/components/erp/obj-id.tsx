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
export function ObjId({ value, mono = true }: { value: number | null | undefined; mono?: boolean }) {
  const nav = useErpNav();
  const text = formatObjectId(value);
  // **Eine Objektnummer sieht überall gleich aus** (Notiz #282): sie erbte bisher die
  // Schriftgrösse ihrer Umgebung und wurde in einem grossen Lesefeld zur dominantesten
  // Angabe der Zeile – obwohl sie eine Kennung ist, keine Aussage. Eigene, feste Grösse
  // (wie schon die eine Formatierung aus #263), Ziffern tabellarisch.
  const baseStyle: React.CSSProperties = {
    fontFamily: mono ? 'var(--font-mono), monospace' : undefined,
    fontSize: 12.5, fontWeight: 600, fontVariantNumeric: 'tabular-nums', lineHeight: 1.4,
  };
  if (!nav || value == null) {
    return <span style={baseStyle}>{text}</span>;
  }
  return (
    <button
      type="button"
      onClick={(e) => { e.stopPropagation(); nav(value); }}
      title="Datensatz öffnen"
      style={{
        ...baseStyle, border: 'none', background: 'none', padding: 0, cursor: 'pointer',
        color: 'var(--accent)', textDecoration: 'underline', textUnderlineOffset: 2,
      }}
    >
      {text}
    </button>
  );
}
