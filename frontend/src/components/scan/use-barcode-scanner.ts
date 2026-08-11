'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

// Lebenszyklus der Kamera-Erfassung:
//   starting     → Kamera wird angefragt/initialisiert
//   scanning     → Live-Bild läuft, sucht laufend nach Codes
//   denied       → Kein Zugriff (Berechtigung abgelehnt / keine Kamera)
//   unsupported  → Browser kann nicht auf die Kamera zugreifen (kein getUserMedia)
export type ScanState = 'starting' | 'scanning' | 'denied' | 'unsupported';

/** Welche Kamera zuletzt getaugt hat – damit die Wahl nur EINMAL je Gerät passiert. */
const CAMERA_KEY = 'inexxio_scan_camera';

/** Wie oft der native Decoder ein Bild ansieht. 7/s reicht fürs Auge und schont den Akku. */
const NATIVE_TICK_MS = 140;

// ─── Die native Schnittstelle (nicht in lib.dom) ─────────────────────────────
interface DetectedBarcode { rawValue: string }
interface BarcodeDetectorLike { detect(source: CanvasImageSource): Promise<DetectedBarcode[]> }
interface BarcodeDetectorCtor {
  new (options?: { formats?: string[] }): BarcodeDetectorLike;
  getSupportedFormats?: () => Promise<string[]>;
}
// `torch` ist Teil des Media-Capture-Entwurfs, aber (noch) nicht der TS-Typen.
type TorchCapabilities = MediaTrackCapabilities & { torch?: boolean };
type TorchConstraint = MediaTrackConstraintSet & { torch?: boolean };

function nativeDetector(): BarcodeDetectorCtor | null {
  if (typeof window === 'undefined') return null;
  return (window as unknown as { BarcodeDetector?: BarcodeDetectorCtor }).BarcodeDetector ?? null;
}

/**
 * **Welche Kamera?** – rein, ohne Browser, damit die Regel prüfbar ist.
 *
 * `facingMode: 'environment'` allein überlässt die Wahl dem Browser, und der greift auf
 * Telefonen mit mehreren Rückkameras oft zur **Ultraweitwinkel**-Linse. Die stellt bei
 * 10 cm nicht scharf – und genau so hält man ein Etikett. Das ist die häufigste Ursache
 * für «der Scanner erkennt nichts».
 *
 * Die Heuristik liest die Gerätenamen, weil es die einzige Angabe ist, die vor dem
 * Öffnen eines Streams zur Verfügung steht: Rückkameras bevorzugen, offensichtliche
 * Sonderlinsen ausschliessen. Findet sie nichts Besseres, gibt sie `null` zurück –
 * dann bleibt es beim `facingMode`, also beim heutigen Verhalten.
 */
export function pickCamera(devices: MediaDeviceInfo[]): string | null {
  const cams = devices.filter((d) => d.kind === 'videoinput' && d.deviceId);
  if (cams.length < 2) return null;              // eine Kamera – nichts zu wählen

  const BACK = /\b(back|rear|environment)\b|rück|hinten|arrière|trasera|traseira/i;
  const SPECIAL = /ultra|weitwinkel|wide[-\s]?angle|tele|zoom|depth|truedepth|makro|macro/i;

  const back = cams.filter((d) => BACK.test(d.label));
  const pool = back.length ? back : cams;
  const plain = pool.filter((d) => !SPECIAL.test(d.label));
  return (plain[0] ?? pool[0])?.deviceId ?? null;
}

function remembered(): string | null {
  try { return window.localStorage.getItem(CAMERA_KEY); } catch { return null; }
}
function remember(id: string | null) {
  try {
    if (id) window.localStorage.setItem(CAMERA_KEY, id);
    else window.localStorage.removeItem(CAMERA_KEY);
  } catch { /* privater Modus – dann wählt eben jedes Mal neu */ }
}

/**
 * Kapselt die gesamte Kamera-/Decode-Mechanik. Liefert ein `videoRef` für das
 * Vorschau-Element, den `state`, und – wo das Gerät es kann – die **Taschenlampe**.
 * Der Callback feuert bei jedem erkannten Code mit dem **Rohtext**; Deutung und
 * Verifikation passieren oben (`lib/scan.ScanReading`).
 *
 * **Zwei Decoder, eine Schnittstelle.** Zuerst der native `BarcodeDetector`
 * (Chrome/Android, ChromeOS, neuere Safari): schneller, akkuschonender – und weil
 * ZXing erst im Rückfall **dynamisch** geladen wird, kommen die ~112 kB auf diesen
 * Geräten gar nicht erst über die Leitung. Der Rückfall ist ZXing, unverändert in
 * seiner Fähigkeit (QR, Data Matrix, Code128/39, EAN, …).
 *
 * **Der Stream gehört diesem Hook**, nicht dem Decoder. Vorher öffnete ZXing ihn selbst
 * (`decodeFromConstraints`) – und dessen `stop()` beendet nur die Decode-Schleife und
 * lässt die Kamera offen; über mehrere Scans summierten sich die Video-Puffer auf
 * mehrere GB. Ein Besitzer, ein Cleanup: hier werden Tracks explizit gestoppt.
 */
export function useBarcodeScanner(active: boolean, onText: (text: string) => void) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [state, setState] = useState<ScanState>('starting');
  // `null` = das Gerät kann es nicht; sonst der aktuelle Zustand der Lampe.
  const [torch, setTorchState] = useState<boolean | null>(null);
  // Die Kamera-Wahl steckt im State, damit ein Wechsel den Effekt neu laufen lässt –
  // und damit durch DESSEN Cleanup geht. Ein Umschalten von Hand wäre ein zweiter
  // Abbau-Pfad neben dem, der das Speicherleck behebt.
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const trackRef = useRef<MediaStreamTrack | null>(null);
  const onTextRef = useRef(onText);
  onTextRef.current = onText;

  useEffect(() => { if (active) setDeviceId(remembered()); }, [active]);

  useEffect(() => {
    if (!active) return;

    const supported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
    if (!supported) { setState('unsupported'); return; }

    // Video-Element einmal festhalten – stabil für die Lebensdauer dieses Effekts
    // (und im Cleanup verlässlich verfügbar, ohne den wandernden Ref erneut zu lesen).
    const videoEl = videoRef.current;
    let cancelled = false;
    let stopDecoder: (() => void) | null = null;
    let stream: MediaStream | null = null;
    setState('starting');

    async function open(id: string | null): Promise<MediaStream> {
      const video: MediaTrackConstraints = id
        ? { deviceId: { exact: id } }
        : { facingMode: { ideal: 'environment' } };
      video.width = { ideal: 1280 };
      video.height = { ideal: 720 };
      return navigator.mediaDevices.getUserMedia({ video });
    }

    async function start() {
      try {
        stream = await open(deviceId);
      } catch {
        // Ein gemerktes Gerät kann verschwinden (anderes Telefon, anderer Browser).
        // Dann zählt nicht der Merker, sondern dass die Kamera läuft.
        if (deviceId) { remember(null); stream = await open(null).catch(() => null); }
      }
      if (!stream) { if (!cancelled) setState('denied'); return; }
      if (cancelled) { stream.getTracks().forEach((t) => t.stop()); return; }

      const track = stream.getVideoTracks()[0] ?? null;
      trackRef.current = track;
      const caps = track?.getCapabilities?.() as TorchCapabilities | undefined;
      setTorchState(caps?.torch ? false : null);

      if (videoEl) {
        videoEl.srcObject = stream;
        await videoEl.play().catch(() => { /* Autoplay-Politik – das Bild kommt trotzdem */ });
      }
      if (cancelled) return;
      setState('scanning');

      // Die Linsenwahl braucht Gerätenamen, und die gibt es erst NACH der Freigabe.
      // Darum läuft sie hier – und wirkt über `setDeviceId` beim nächsten Effektlauf.
      if (!deviceId) {
        const devices = await navigator.mediaDevices.enumerateDevices().catch(() => []);
        const better = pickCamera(devices);
        const current = track?.getSettings?.().deviceId;
        if (!cancelled && better && better !== current) { remember(better); setDeviceId(better); return; }
        if (current) remember(current);
      }

      stopDecoder = await decode(videoEl, stream);
    }

    async function decode(el: HTMLVideoElement | null, src: MediaStream): Promise<(() => void) | null> {
      const hit = (raw: string) => { if (!cancelled) onTextRef.current(raw); };

      const Ctor = nativeDetector();
      if (Ctor && el) {
        const formats = await Ctor.getSupportedFormats?.().catch(() => []) ?? [];
        if (!formats.length || formats.includes('qr_code')) {
          const detector = new Ctor(formats.length ? { formats } : undefined);
          let timer = 0;
          const tick = async () => {
            if (cancelled) return;
            try {
              const found = await detector.detect(el);
              if (found[0]?.rawValue) hit(found[0].rawValue);
            } catch { /* einzelnes Bild unlesbar – der nächste Takt zählt */ }
            if (!cancelled) timer = window.setTimeout(tick, NATIVE_TICK_MS);
          };
          tick();
          return () => window.clearTimeout(timer);
        }
      }

      // Rückfall: ZXing – erst hier geladen, damit der Brocken auf Geräten mit
      // nativem Decoder gar nicht erst angefragt wird.
      const { BrowserMultiFormatReader } = await import('@zxing/browser');
      if (cancelled) return null;
      const reader = new BrowserMultiFormatReader();
      const controls = el
        ? await reader.decodeFromVideoElement(el, (result) => { if (result) hit(result.getText()); })
        : await reader.decodeFromStream(src, undefined, (result) => { if (result) hit(result.getText()); });
      return () => controls.stop();
    }

    start().catch(() => { if (!cancelled) setState('denied'); });

    return () => {
      cancelled = true;
      stopDecoder?.();
      trackRef.current = null;
      // Der Stream gehört uns – also geben WIR ihn frei, Track für Track. Ohne das
      // bleibt die Kamera offen und die Video-Puffer wachsen über jeden Scan hinweg.
      const open = (stream ?? (videoEl?.srcObject as MediaStream | null));
      open?.getTracks?.().forEach((t) => t.stop());
      if (videoEl) videoEl.srcObject = null;
    };
  }, [active, deviceId]);

  /** Taschenlampe schalten. In Halle und Regal ist sie der Unterschied zwischen geht und nicht. */
  const setTorch = useCallback(async (on: boolean) => {
    const track = trackRef.current;
    if (!track) return;
    try {
      await track.applyConstraints({ advanced: [{ torch: on } as TorchConstraint] });
      setTorchState(on);
    } catch { /* Gerät verweigert – dann bleibt die Lampe, wie sie war */ }
  }, []);

  return { videoRef, state, torch, setTorch };
}
