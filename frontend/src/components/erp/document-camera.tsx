'use client';

import { useRef, useState } from 'react';
import { Camera, CameraOff, Upload, ScanLine, ArrowRight } from 'lucide-react';
import { useBarcodeScanner } from '@/components/scan/use-barcode-scanner';
import { parseScannedCode } from '@/lib/scan';
import { fmtObjId } from '@/components/erp/user-detail';

const THROTTLE_MS = 1200;

/**
 * Kamera-first Aufnahme für Dokumente – teilt sich die Kamera-Mechanik mit dem Objekt-Scanner
 * (`useBarcodeScanner`: ZXing, alle Code-Arten). Die Kamera startet sofort; ein grosser
 * Auslöser fotografiert das Dokument (Frame → JPEG-Datei). Als Rückfall gibt es «Datei
 * hochladen» (PDF/Bild).
 *
 * **Kombiniert (Feed):** ist `onCode` gesetzt, läuft die Barcode-Erkennung mit – erkennt sie
 * eine Objektnummer, erscheint ein dezenter Chip «Datensatz öffnen» (Antippen navigiert). So
 * dient EINE Kamera für Scannen UND Dokumentieren, ohne Moduswechsel: erkannter Code = Chip,
 * Auslöser = Dokument. Ein Barcode auf einem Lieferschein kapert also nichts – man drückt
 * einfach den Auslöser.
 */
export function DocumentCamera({ onCapture, onCode, captureLabel = 'Als Dokument erfassen', captureEnabled = true, extra }: {
  onCapture: (file: File) => void;
  onCode?: (objectId: number) => void;
  captureLabel?: string;
  captureEnabled?: boolean;   // false = reiner Scanner (kein Auslöser/Upload), z. B. Lieferant
  extra?: React.ReactNode;    // Zusatzfunktion im Bild (z. B. Nummern-Eingabe)
}) {
  const [detected, setDetected] = useState<number | null>(null);
  const lastRef = useRef<{ id: number; at: number } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function handleText(raw: string) {
    if (!onCode) return;
    const id = parseScannedCode(raw);
    if (id == null) return;
    const now = Date.now();
    if (lastRef.current && lastRef.current.id === id && now - lastRef.current.at < THROTTLE_MS) return;
    lastRef.current = { id, at: now };
    setDetected(id);   // NICHT automatisch navigieren – nur anbieten (Chip)
  }

  const { videoRef, state } = useBarcodeScanner(true, handleText);
  const live = state === 'starting' || state === 'scanning';

  function capture() {
    const v = videoRef.current;
    if (!v || !v.videoWidth) return;
    const canvas = document.createElement('canvas');
    canvas.width = v.videoWidth;
    canvas.height = v.videoHeight;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.drawImage(v, 0, 0);
    canvas.toBlob((blob) => {
      if (blob) onCapture(new File([blob], `foto-${Date.now()}.jpg`, { type: 'image/jpeg' }));
    }, 'image/jpeg', 0.9);
  }

  return (
    // **Dieselbe Bildsprache wie der Objekt-Scanner** (Notiz #119): die Fläche IST die Kamera,
    // alle Bedienelemente liegen als milchige Chips darüber. Der Unterschied ist die
    // Zusatzfunktion – Auslöser, Datei-Upload und (optional) die Nummern-Eingabe.
    <div style={surface}>
      {live ? (
        // eslint-disable-next-line jsx-a11y/media-has-caption
        <video ref={videoRef} style={video} muted playsInline autoPlay />
      ) : (
        <div style={cameraOff}>
          <CameraOff size={28} strokeWidth={1.5} />
          <span style={{ fontSize: 12, marginTop: 8, maxWidth: 240, textAlign: 'center' }}>
            {state === 'denied' ? 'Kein Kamerazugriff – bitte Datei hochladen.'
              : 'Kamera nicht verfügbar – bitte Datei hochladen.'}
          </span>
        </div>
      )}

      {live && (
        <div style={frame}>
          {!detected && <div className="ix-scanbeam" style={beam} />}
        </div>
      )}
      {onCode && detected != null && (
        <button type="button" onClick={() => onCode(detected)} style={openChip}>
          <ScanLine size={14} /> Datensatz {fmtObjId(detected)} öffnen <ArrowRight size={14} />
        </button>
      )}

      <div style={controls}>
        {extra}
        {captureEnabled && (
          <>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <button type="button" onClick={capture} disabled={!live} style={{ ...shutter, opacity: live ? 1 : 0.5 }}>
                <Camera size={19} /> {captureLabel}
              </button>
              <button type="button" onClick={() => fileRef.current?.click()} style={uploadBtn}
                aria-label="Datei hochladen (PDF/Bild)" title="Datei hochladen (PDF/Bild)">
                <Upload size={17} />
              </button>
            </div>
            <input ref={fileRef} type="file" accept="application/pdf,image/*" hidden
              onChange={(e) => { const f = e.target.files?.[0]; if (f) onCapture(f); }} />
          </>
        )}
      </div>
    </div>
  );
}

const surface: React.CSSProperties = {
  position: 'absolute', inset: 0, background: '#0B1220',
  display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
};
// pointerEvents:none – auf iOS/Safari rendert das <video> sonst ÜBER den absolut
// positionierten Overlays und verschluckt Taps auf den «öffnen»-Chip (Bug: Chip reagiert nicht).
const video: React.CSSProperties = { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', pointerEvents: 'none' };
const cameraOff: React.CSSProperties = { display: 'flex', flexDirection: 'column', alignItems: 'center', color: 'rgba(255,255,255,.6)', padding: 24 };
const frame: React.CSSProperties = {
  position: 'absolute', inset: '12% 8% 26%', border: '2px solid rgba(255,255,255,.85)', borderRadius: 18,
  boxShadow: '0 0 0 9999px rgba(4,8,16,0.42)', pointerEvents: 'none', overflow: 'hidden',
};
const beam: React.CSSProperties = {
  position: 'absolute', left: '5%', right: '5%', top: '50%', height: 2, borderRadius: 2,
  background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.95), transparent)',
  boxShadow: '0 0 12px rgba(255,255,255,.6)',
};
const openChip: React.CSSProperties = {
  position: 'absolute', top: 52, zIndex: 3, display: 'inline-flex', alignItems: 'center', gap: 7, padding: '10px 16px',
  borderRadius: 999, background: '#fff', color: 'var(--fg-1)', fontSize: 13.5, fontWeight: 700, cursor: 'pointer', border: 'none',
};
const controls: React.CSSProperties = {
  position: 'absolute', left: 14, right: 14, bottom: 14, display: 'flex', flexDirection: 'column', gap: 8,
};
// Auslöser: ruhig statt laut – das Fotografieren ist Routine, kein Rot-Moment.
const shutter: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 9, flex: 1, minHeight: 48,
  borderRadius: 12, border: '1px solid rgba(255,255,255,.28)', background: 'rgba(15,23,42,.62)',
  backdropFilter: 'blur(10px)', color: '#fff', fontSize: 14.5, fontWeight: 700, cursor: 'pointer',
};
// Rückfall «Datei hochladen»: nur Symbol, Bedeutung im Hover.
const uploadBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 48, minHeight: 48, flex: 'none',
  borderRadius: 12, border: '1px solid rgba(255,255,255,.22)', background: 'rgba(15,23,42,.5)',
  backdropFilter: 'blur(10px)', color: '#fff', cursor: 'pointer',
};
