'use client';

/**
 * **Der Decoder — die Deutung des Kamerabildes, und sonst nichts.**
 *
 * Die Kamera selbst steht daneben (`use-camera.ts`): Stream, Linsenwahl, Taschenlampe,
 * Aufräumen. Hier hängt nur noch die Frage «steht in diesem Bild ein Code?» daran.
 *
 * Genau daran hing die zweite Verwendung fest (Testnotiz #718): ein **Foto** braucht die
 * ganze Kamera und keine einzige Zeile Decoder. Solange beides in einem Hook steckte,
 * hätte es entweder eine Kopie der Kamera-Mechanik gebraucht oder einen Schalter «nicht
 * decodieren» – zwei Wege, dasselbe zweimal zu haben.
 *
 * **Zwei Decoder, eine Schnittstelle.** Zuerst der native `BarcodeDetector`
 * (Chrome/Android, ChromeOS, neuere Safari): schneller, akkuschonender – und weil ZXing
 * erst im Rückfall **dynamisch** geladen wird, kommen die ~112 kB auf diesen Geräten gar
 * nicht erst über die Leitung. Der Rückfall ist ZXing, unverändert in seiner Fähigkeit
 * (QR, Data Matrix, Code128/39, EAN, …).
 */

import { useCallback, useRef } from 'react';

import { useCamera, type Attach } from './use-camera';

export { pickCamera, useCamera, type Attach, type ScanState } from './use-camera';

/** Wie oft der native Decoder ein Bild ansieht. 7/s reicht fürs Auge und schont den Akku. */
const NATIVE_TICK_MS = 140;

// ─── Die native Schnittstelle (nicht in lib.dom) ─────────────────────────────
interface DetectedBarcode { rawValue: string }
interface BarcodeDetectorLike { detect(source: CanvasImageSource): Promise<DetectedBarcode[]> }
interface BarcodeDetectorCtor {
  new (options?: { formats?: string[] }): BarcodeDetectorLike;
  getSupportedFormats?: () => Promise<string[]>;
}

function nativeDetector(): BarcodeDetectorCtor | null {
  if (typeof window === 'undefined') return null;
  return (window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector ?? null;
}

/**
 * Kamera **plus** Decoder. Liefert dasselbe wie `useCamera` – `videoRef`, `state`,
 * Taschenlampe –, und der Callback feuert bei jedem erkannten Code mit dem **Rohtext**;
 * Deutung und Verifikation passieren oben (`lib/scan.ScanReading`).
 */
export function useBarcodeScanner(active: boolean, onText: (text: string) => void) {
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  const attach = useCallback<Attach>(async (el, src) => {
    let dead = false;
    const hit = (raw: string) => { if (!dead) onTextRef.current(raw); };

    const Ctor = nativeDetector();
    if (Ctor && el) {
      const formats = await Ctor.getSupportedFormats?.().catch(() => []) ?? [];
      if (!formats.length || formats.includes('qr_code')) {
        const detector = new Ctor(formats.length ? { formats } : undefined);
        let timer = 0;
        const tick = async () => {
          if (dead) return;
          try {
            const found = await detector.detect(el);
            if (found[0]?.rawValue) hit(found[0].rawValue);
          } catch { /* einzelnes Bild unlesbar – der nächste Takt zählt */ }
          if (!dead) timer = window.setTimeout(tick, NATIVE_TICK_MS);
        };
        tick();
        return () => { dead = true; window.clearTimeout(timer); };
      }
    }

    // Rückfall: ZXing – erst hier geladen, damit der Brocken auf Geräten mit
    // nativem Decoder gar nicht erst angefragt wird.
    const { BrowserMultiFormatReader } = await import('@zxing/browser');
    if (dead) return null;
    const reader = new BrowserMultiFormatReader();
    const controls = el
      ? await reader.decodeFromVideoElement(el, (result) => { if (result) hit(result.getText()); })
      : await reader.decodeFromStream(src, undefined, (result) => { if (result) hit(result.getText()); });
    return () => { dead = true; controls.stop(); };
  }, []);

  return useCamera(active, attach);
}
