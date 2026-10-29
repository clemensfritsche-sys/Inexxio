'use client';

import { useEffect } from 'react';

/**
 * Selbstheilung nach einem Deploy (statischer Export + Firebase Hosting).
 *
 * Bei jedem Deploy werden die alten, **gehashten** JS-Chunks (`_next/static/chunks/*`)
 * ersetzt/gelöscht. Ein Client, der die App über einen Deploy hinweg **offen** hat,
 * lädt beim nächsten Klick den Route-Chunk noch per ALTEM Hash → 404 → `ChunkLoadError`.
 * Die Navigation «passiert dann einfach nichts» (der Router bricht still ab).
 *
 * Dieser Guard fängt genau diese Fehlerklasse ab und lädt die Seite **einmal** neu
 * (frisches HTML `no-cache` → frische Chunk-Referenzen → App funktioniert wieder).
 * Gegen Endlos-Reloads mit einem sessionStorage-Zeitfenster abgesichert. Nur
 * Chunk-/Modul-Ladefehler lösen aus – normale Laufzeitfehler bleiben unberührt
 * (die fängt die ErrorBoundary).
 */

const FLAG = 'inexxio_chunk_reload_at';
const COOLDOWN_MS = 30_000;

function isChunkError(text: string | undefined | null): boolean {
  if (!text) return false;
  return /ChunkLoadError|Loading chunk [\w-]+ failed|Failed to fetch dynamically imported module|error loading dynamically imported module|Importing a module script failed/i.test(
    text,
  );
}

function recoverOnce(): void {
  try {
    const last = Number(sessionStorage.getItem(FLAG) || '0');
    if (Date.now() - last < COOLDOWN_MS) return; // gerade erst neu geladen → keine Schleife
    sessionStorage.setItem(FLAG, String(Date.now()));
  } catch {
    /* sessionStorage evtl. blockiert – dann trotzdem einmalig neu laden */
  }
  window.location.reload();
}

export function ChunkReloadGuard(): null {
  useEffect(() => {
    const onError = (e: ErrorEvent) => {
      if (isChunkError(e?.message) || isChunkError((e?.error as Error | undefined)?.message)) {
        recoverOnce();
      }
    };
    const onRejection = (e: PromiseRejectionEvent) => {
      const r = e?.reason as { message?: string; name?: string } | undefined;
      if (isChunkError(r?.message) || isChunkError(r?.name)) recoverOnce();
    };
    window.addEventListener('error', onError);
    window.addEventListener('unhandledrejection', onRejection);
    return () => {
      window.removeEventListener('error', onError);
      window.removeEventListener('unhandledrejection', onRejection);
    };
  }, []);
  return null;
}
