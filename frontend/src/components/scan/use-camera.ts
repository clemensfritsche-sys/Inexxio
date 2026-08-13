'use client';

/**
 * **Die Kamera — ohne jede Deutung ihres Bildes** (Testnotiz #718).
 *
 * Sie war mit dem Decoder verwoben: ein Hook öffnete den Stream, wählte die Linse,
 * schaltete die Lampe **und** suchte laufend nach Codes. Für ein Foto brauchte es davon
 * alles ausser dem letzten – und «alles ausser einem» ist die Ansage, dass an dieser
 * Stelle zwei Dinge stecken.
 *
 * Getrennt ist es dieselbe Mechanik in zwei Schichten: hier der **Besitz des Streams**
 * (öffnen, Linse wählen, Lampe, aufräumen), darüber wahlweise ein `Attach` – beim
 * Scannen der Decoder, beim Fotografieren nichts. Kein zweiter Kamera-Layer, keine
 * zweite Aufräum-Stelle, kein zweites Speicherleck.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

// Lebenszyklus der Kamera-Erfassung:
//   starting     → Kamera wird angefragt/initialisiert
//   scanning     → Live-Bild läuft (und wer mitliest, liest mit)
//   denied       → Kein Zugriff (Berechtigung abgelehnt / keine Kamera)
//   unsupported  → Browser kann nicht auf die Kamera zugreifen (kein getUserMedia)
export type ScanState = 'starting' | 'scanning' | 'denied' | 'unsupported';

/** Welche Kamera zuletzt getaugt hat – damit die Wahl nur EINMAL je Gerät passiert. */
const CAMERA_KEY = 'inexxio_scan_camera';

// `torch` ist Teil des Media-Capture-Entwurfs, aber (noch) nicht der TS-Typen.
type TorchCapabilities = MediaTrackCapabilities & { torch?: boolean };
type TorchConstraint = MediaTrackConstraintSet & { torch?: boolean };

/**
 * **Was während des laufenden Bildes daran hängt** – der Decoder ist genau so einer.
 *
 * Die Kamera weiss nichts davon, was mit ihrem Bild geschieht: sie öffnet den Stream,
 * wählt die Linse, schaltet die Lampe und räumt auf. Wer mitlesen will, bekommt Element
 * und Stream und gibt sein eigenes Aufräumen zurück.
 */
export type Attach = (
  el: HTMLVideoElement | null, stream: MediaStream,
) => Promise<(() => void) | null>;

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

/**
 * Kapselt Stream, Linsenwahl, Taschenlampe und Aufräumen. `attach` läuft, sobald das
 * Bild steht, und darf ein eigenes Cleanup zurückgeben.
 *
 * **Der Stream gehört diesem Hook**, nicht dem, der mitliest. Vorher öffnete ZXing ihn
 * selbst (`decodeFromConstraints`) – und dessen `stop()` beendet nur die Decode-Schleife
 * und lässt die Kamera offen; über mehrere Scans summierten sich die Video-Puffer auf
 * mehrere GB. Ein Besitzer, ein Cleanup.
 */
export function useCamera(active: boolean, attach?: Attach) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [state, setState] = useState<ScanState>('starting');
  // `null` = das Gerät kann es nicht; sonst der aktuelle Zustand der Lampe.
  const [torch, setTorchState] = useState<boolean | null>(null);
  // Die Kamera-Wahl steckt im State, damit ein Wechsel den Effekt neu laufen lässt –
  // und damit durch DESSEN Cleanup geht. Ein Umschalten von Hand wäre ein zweiter
  // Abbau-Pfad neben dem, der das Speicherleck behebt.
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const trackRef = useRef<MediaStreamTrack | null>(null);
  const attachRef = useRef(attach);
  attachRef.current = attach;

  useEffect(() => { if (active) setDeviceId(remembered()); }, [active]);

  useEffect(() => {
    if (!active) return;

    const supported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
    if (!supported) { setState('unsupported'); return; }

    // Video-Element einmal festhalten – stabil für die Lebensdauer dieses Effekts
    // (und im Cleanup verlässlich verfügbar, ohne den wandernden Ref erneut zu lesen).
    const videoEl = videoRef.current;
    let cancelled = false;
    let detach: (() => void) | null = null;
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

      detach = (await attachRef.current?.(videoEl, stream)) ?? null;
    }

    start().catch(() => { if (!cancelled) setState('denied'); });

    return () => {
      cancelled = true;
      detach?.();
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
