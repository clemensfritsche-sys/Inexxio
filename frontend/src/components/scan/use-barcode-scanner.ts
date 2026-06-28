'use client';

import { useEffect, useRef, useState } from 'react';
import { BrowserMultiFormatReader, type IScannerControls } from '@zxing/browser';

// Lebenszyklus der Kamera-Erfassung:
//   starting     → Kamera wird angefragt/initialisiert
//   scanning     → Live-Bild läuft, sucht laufend nach Codes
//   denied       → Kein Zugriff (Berechtigung abgelehnt / keine Kamera)
//   unsupported  → Browser kann nicht auf die Kamera zugreifen (kein getUserMedia)
export type ScanState = 'starting' | 'scanning' | 'denied' | 'unsupported';

/**
 * Kapselt die gesamte Kamera-/Decode-Mechanik (ZXing, **alle** Code-Arten:
 * QR, Data Matrix, Code128/39, EAN, …). Liefert ein `videoRef` für das
 * Vorschau-Element und den aktuellen `state`. Der Callback feuert bei jedem
 * erkannten Code mit dem Rohtext – Parsing/Verifikation passiert oben.
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

    // Video-Element einmal festhalten – stabil für die Lebensdauer dieses Effekts
    // (und im Cleanup verlässlich verfügbar, ohne den wandernden Ref erneut zu lesen).
    const videoEl = videoRef.current;
    let controls: IScannerControls | null = null;
    let cancelled = false;
    setState('starting');

    const reader = new BrowserMultiFormatReader();
    reader
      .decodeFromConstraints(
        { video: { facingMode: 'environment' } },
        videoEl ?? undefined,
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
      // ZXing's `stop()` beendet je nach Version nur die Decode-Schleife, lässt aber
      // den Kamera-MediaStream am Video-Element offen. Über mehrere Scan-Vorgänge
      // hinweg summieren sich die Video-Puffer zu enormem Speicherverbrauch (mehrere
      // GB). Darum den Stream + alle Tracks hier explizit freigeben.
      const stream = videoEl?.srcObject as MediaStream | null;
      if (stream && typeof stream.getTracks === 'function') {
        stream.getTracks().forEach((t) => t.stop());
      }
      if (videoEl) videoEl.srcObject = null;
    };
  }, [active]);

  return { videoRef, state };
}
