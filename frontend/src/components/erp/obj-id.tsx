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
  /**
   * **Wie die Nummer heisst**, wenn sie genauer ist als der Datensatz, auf den sie
   * führt: die Nummer einer Einzelinstanz (`100000123-3`) meint ein Stück, aber
   * geöffnet wird ihre Instanz – ein Stück hat keinen eigenen Datensatz.
   *
   * Kein zweiter Weg, eine Nummer zu schreiben: dieselbe Komponente, dieselbe Grösse,
   * dieselbe Tabellenziffer – nur der Text ist präziser.
   */
  label?: string;
}) {
  const nav = useErpNav();
  const text = label ?? formatObjectId(value);
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
  // ►►► **Sie sieht aus wie eine Nummer, nicht wie ein Hyperlink** (Testnotiz #784). ◄◄◄
  //
  // Blau + fett + unterstrichen sind die drei Marker, an denen man im Web einen Link
  // erkennt – und im ERP steht diese Nummer in fast jeder Zeile: das Raster las sich als
  // Linkliste, und die Kennung war die lauteste Angabe darin. Im Ruhezustand trägt sie
  // darum die Farbe ihres Textes; dass sie etwas tut, sagt der Zeiger und – sobald er
  // darauf steht – Farbe **und** Unterstreichung (`.erp-objid`, `:focus-visible` deckt
  // den Tastaturweg ab).
  //
  // **Die Form bleibt dieselbe wie bei einer Nummer ohne Ziel** (#282): `baseStyle` ist
  // geteilt, die Auszeichnung kommt allein aus der Klasse. Zwei Grössen für dieselbe
  // Kennung wären der erste Schritt zurück zu «Nummern sehen je nach Ort anders aus».
  // Fett bleibt beides: es ist die Auszeichnung der **Kennung**, kein Link-Marker.
  return (
    <button
      type="button"
      className="erp-objid"
      onClick={(e) => { e.stopPropagation(); nav(value); }}
      title="Datensatz öffnen"
      style={baseStyle}
    >
      {text}
    </button>
  );
}
