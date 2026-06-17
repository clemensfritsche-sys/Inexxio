'use client';

import { createContext, useContext } from 'react';
import { fmtObjId } from '@/components/erp/user-detail';

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
  const text = fmtObjId(value);
  const baseStyle: React.CSSProperties = {
    fontFamily: mono ? 'monospace' : undefined,
    fontWeight: 700,
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
        color: '#2563eb', textDecoration: 'underline', textUnderlineOffset: 2,
      }}
    >
      {text}
    </button>
  );
}
