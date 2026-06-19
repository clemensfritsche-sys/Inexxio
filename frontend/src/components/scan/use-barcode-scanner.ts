'use client';

import { useEffect, useRef, useState } from 'react';
import { BrowserQRCodeReader, type IScannerControls } from '@zxing/browser';

// Lebenszyklus der Kamera-Erfassung:
//   starting     → Kamera wird angefragt/initialisiert
//   scanning     → Live-Bild läuft, sucht laufend nach Codes
//   denied       → Kein Zugriff (Berechtigung abgelehnt / keine Kamera)
//   unsupported  → Browser kann nicht auf die Kamera zugreifen (kein getUserMedia)
export type ScanState = 'starting' | 'scanning' | 'denied' | 'unsupported';

/**
 * Kapselt die gesamte Kamera-/Decode-Mechanik (ZXing). Liefert ein `videoRef`
 * für das Vorschau-Element und den aktuellen `state`. Der Callback feuert bei
 * jedem erkannten Code mit dem Rohtext – Parsing/Verifikation passiert oben.
 *
 * Bevorzugt die Rückkamera (`facingMode: environment`). Räumt Stream + Decode-
 * Loop beim Unmount/Deaktivieren sauber ab.
 */
export function useBarcodeScanner(active: boolean, onText: (text: string) => void) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [state, setState] = useState<ScanState>('starting');
  // Callback stabil halten, ohne den Effekt neu zu starten (sonst flackert die Kamera).
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  useEffect(() => {
    if (!active) return;

    const supported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
    if (!supported) { setState('unsupported'); return; }

    let controls: IScannerControls | null = null;
    let cancelled = false;
    setState('starting');

    const reader = new BrowserQRCodeReader();
    reader
      .decodeFromConstraints(
        { video: { facingMode: 'environment' } },
        videoRef.current ?? undefined,
        (result) => { if (result) onTextRef.current(result.getText()); },
      )
      .then((c) => {
        if (cancelled) { c.stop(); return; }
        controls = c;
        setState('scanning');
      })
      .catch(() => { if (!cancelled) setState('denied'); });

    return () => {
      cancelled = true;
      controls?.stop();
    };
  }, [active]);

  return { videoRef, state };
}
