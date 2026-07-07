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
export function DocumentCamera({ onCapture, onCode, captureLabel = 'Als Dokument erfassen', captureEnabled = true }: {
  onCapture: (file: File) => void;
  onCode?: (objectId: number) => void;
  captureLabel?: string;
  captureEnabled?: boolean;   // false = reiner Scanner (kein Auslöser/Upload), z. B. Lieferant
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
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      <div style={viewport}>
        {live ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video ref={videoRef} style={video} muted playsInline autoPlay />
        ) : (
          <div style={cameraOff}>
            <CameraOff size={28} strokeWidth={1.5} />
            <span style={{ fontSize: 12, marginTop: 8, maxWidth: 240, textAlign: 'center' }}>
              {state === 'denied' ? 'Kein Kamerazugriff – bitte «Datei hochladen» nutzen.'
                : 'Kamera nicht verfügbar – bitte «Datei hochladen» nutzen.'}
            </span>
          </div>
        )}
        {live && <div style={frame} />}
        {live && !detected && (
          <div style={hintChip}><ScanLine size={13} /> Dokument in den Rahmen halten</div>
        )}
        {onCode && detected != null && (
          <button type="button" onClick={() => onCode(detected)} style={openChip}>
            <ScanLine size={14} /> Datensatz {fmtObjId(detected)} öffnen <ArrowRight size={14} />
          </button>
        )}
      </div>

      {captureEnabled && (
        <>
          {/* Auslöser (Kamera-first) */}
          <button type="button" onClick={capture} disabled={!live} style={{ ...shutter, opacity: live ? 1 : 0.5 }}>
            <Camera size={19} /> {captureLabel}
          </button>

          {/* Rückfall: Datei hochladen (PDF/Bild) */}
          <button type="button" onClick={() => fileRef.current?.click()} style={uploadLink}>
            <Upload size={15} /> Stattdessen Datei hochladen (PDF/Bild)
          </button>
          <input ref={fileRef} type="file" accept="application/pdf,image/*" hidden
            onChange={(e) => { const f = e.target.files?.[0]; if (f) onCapture(f); }} />
        </>
      )}
    </div>
  );
}

const viewport: React.CSSProperties = {
  position: 'relative', width: '100%', aspectRatio: '4 / 3', background: '#0f172a',
  borderRadius: 12, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
};
const video: React.CSSProperties = { width: '100%', height: '100%', objectFit: 'cover' };
const cameraOff: React.CSSProperties = { display: 'flex', flexDirection: 'column', alignItems: 'center', color: '#94a3b8', padding: 24 };
const frame: React.CSSProperties = {
  position: 'absolute', inset: '10% 8%', border: '3px solid rgba(255,255,255,0.85)', borderRadius: 12,
  boxShadow: '0 0 0 9999px rgba(0,0,0,0.18)', pointerEvents: 'none',
};
const hintChip: React.CSSProperties = {
  position: 'absolute', top: 12, display: 'inline-flex', alignItems: 'center', gap: 6, padding: '5px 11px',
  borderRadius: 999, background: 'rgba(15,23,42,.6)', color: '#fff', fontSize: 11.5, fontWeight: 600, pointerEvents: 'none',
};
const openChip: React.CSSProperties = {
  position: 'absolute', bottom: 12, display: 'inline-flex', alignItems: 'center', gap: 7, padding: '8px 14px',
  borderRadius: 999, background: '#2563eb', color: '#fff', fontSize: 13, fontWeight: 700, cursor: 'pointer', border: 'none',
  boxShadow: '0 6px 18px rgba(37,99,235,.4)',
};
const shutter: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 9, width: '100%', minHeight: 48,
  borderRadius: 12, border: 'none', background: 'var(--inexxio-red, #E51A14)', color: '#fff',
  fontSize: 15, fontWeight: 700, cursor: 'pointer',
};
const uploadLink: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 8, width: '100%', minHeight: 42,
  borderRadius: 10, border: '1px solid var(--border-2, #e2e8f0)', background: '#fff', color: 'var(--fg-2, #475569)',
  fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
