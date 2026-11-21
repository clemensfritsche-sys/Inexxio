'use client';

/**
 * **Die Kamera — ohne jede Deutung ihres Bildes.** Hier der Besitz des Streams (öffnen, Linse,
 * Lampe, aufräumen); darüber wahlweise ein `Attach` – beim Scannen der Decoder, beim
 * Fotografieren nichts.
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
 * **Was während des laufenden Bildes daran hängt** (z. B. der Decoder): bekommt Element und
 * Stream und gibt sein eigenes Aufräumen zurück.
 */
export type Attach = (
  el: HTMLVideoElement | null, stream: MediaStream,
) => Promise<(() => void) | null>;

/**
 * **Welche Kamera?** – rein, ohne Browser, damit die Regel prüfbar ist. `facingMode` allein
 * wählt auf Telefonen oft die Ultraweitwinkel-Linse, die bei 10 cm nicht scharf stellt. Die
 * Heuristik liest die Gerätenamen: Rückkameras bevorzugen, Sonderlinsen ausschliessen; sonst
 * `null` (dann gilt `facingMode`).
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
 * Kapselt Stream, Linsenwahl, Taschenlampe und Aufräumen. `attach` läuft, sobald das Bild
 * steht, und darf ein eigenes Cleanup zurückgeben. Der Stream gehört diesem Hook, nicht dem,
 * der mitliest: ein Besitzer, ein Cleanup (Tracks werden explizit gestoppt).
 */
export function useCamera(active: boolean, attach?: Attach) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [state, setState] = useState<ScanState>('starting');
  // `null` = das Gerät kann es nicht; sonst der aktuelle Zustand der Lampe.
  const [torch, setTorchState] = useState<boolean | null>(null);
  // Die Kamera-Wahl steckt im State, damit ein Wechsel über das Cleanup des Effekts läuft.
  const [deviceId, setDeviceId] = useState<string | null>(null);
  const trackRef = useRef<MediaStreamTrack | null>(null);
  const attachRef = useRef(attach);
  attachRef.current = attach;

  useEffect(() => { if (active) setDeviceId(remembered()); }, [active]);

  useEffect(() => {
    if (!active) return;

    const supported = typeof navigator !== 'undefined' && !!navigator.mediaDevices?.getUserMedia;
    if (!supported) { setState('unsupported'); return; }

    // Video-Element einmal festhalten – stabil für die Lebensdauer dieses Effekts.
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
        // Ein gemerktes Gerät kann verschwinden – dann zählt, dass die Kamera läuft.
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

      // Die Linsenwahl braucht Gerätenamen – die gibt es erst nach der Freigabe; wirkt über
      // `setDeviceId` beim nächsten Effektlauf.
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
      // Der Stream gehört uns – also geben wir ihn frei, Track für Track.
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
