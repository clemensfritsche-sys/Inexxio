'use client';

import type { CSSProperties } from 'react';

/**
 * ►►► **Laden = die graue Form dessen, was kommt** – EIN Baustein für jede Stelle, an der das
 * ERP auf den Server wartet. ◄◄◄
 *
 * Kein «Lädt …», kein Kreisel: die Fläche zeigt schon ihre Form (Zeilen, eine Liste, eine
 * Karte), damit nichts springt, wenn die Antwort da ist. Der Schimmer ist `.erp-skel`
 * (`globals.css`, bei «weniger Bewegung» still). Drei Formen:
 *
 * - `lines` – Textzeilen (Verlauf, Protokoll, eine Karte)
 * - `rows`  – Listenzeilen mit Symbol (Feed, Nummern)
 * - `block` – eine Fläche bestimmter Höhe (Karte, Bild)
 */
export function Skeleton({ lines, rows, block, label = 'Wird geladen', style }: {
  lines?: number; rows?: number; block?: number; label?: string; style?: CSSProperties;
}) {
  return (
    <div role="status" aria-busy="true" aria-label={label}
      style={{ display: 'flex', flexDirection: 'column', gap: rows ? 14 : 8, ...style }}>
      {block != null && <span className="erp-skel" style={{ height: block, borderRadius: 12 }} />}
      {Array.from({ length: rows ?? 0 }, (_, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span className="erp-skel" style={{ width: 28, height: 28, borderRadius: 8, flex: 'none' }} />
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span className="erp-skel" style={{ height: 11, width: `${70 - (i % 3) * 12}%` }} />
            <span className="erp-skel" style={{ height: 9, width: `${42 - (i % 2) * 10}%` }} />
          </div>
        </div>
      ))}
      {Array.from({ length: lines ?? (rows || block != null ? 0 : 3) }, (_, i) => (
        <span key={i} className="erp-skel" style={{ height: 12, width: `${92 - (i % 3) * 18}%` }} />
      ))}
    </div>
  );
}

/** **Ein ganzes Datensatz-Fenster lädt** – Kopf, dann zwei Karten in der Breite des Fensters. */
export function DetailSkeleton() {
  return (
    <div style={{ padding: 20, display: 'flex', flexDirection: 'column', gap: 20 }}>
      <Skeleton rows={1} label="Datensatz wird geladen" />
      <Skeleton block={120} label="Datensatz wird geladen" />
      <Skeleton lines={4} label="Datensatz wird geladen" />
    </div>
  );
}
