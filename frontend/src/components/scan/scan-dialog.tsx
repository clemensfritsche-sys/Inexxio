'use client';

import { useEffect, useRef, useState } from 'react';
import { Camera, CameraOff, Check, AlertTriangle, X, Keyboard, ScanLine } from 'lucide-react';
import { parseScannedCode, matchesExpected } from '@/lib/scan';
import { useBarcodeScanner } from '@/components/scan/use-barcode-scanner';
import { fmtObjId } from '@/components/erp/user-detail';

// Anfrage an den zentralen Scanner. `expected` schaltet den Verifikations-Modus
// frei: nur ein passender Code wird quittiert (grün), ein falscher Code wird rot
// abgewiesen – ohne `expected` ist es ein reiner Lookup (erster gültiger Code zählt).
export interface ScanRequest {
  title?: string;
  hint?: string;
  expected?: number | number[] | null;
  onResult: (objectId: number) => void;
}

// Verzögerung, nach der bei laufender Kamera der Hinweis auf manuelle Eingabe erscheint.
const MANUAL_HINT_MS = 2500;
// Mehrfach-Lesungen desselben Codes innerhalb dieser Spanne ignorieren (ZXing feuert laufend).
const THROTTLE_MS = 1400;

type Feedback = { kind: 'ok' | 'bad'; id: number } | null;

export function ScanDialog({ title, hint, expected, onResult, onClose }: ScanRequest & { onClose: () => void }) {
  const [manualOpen, setManualOpen] = useState(false);
  const [manual, setManual] = useState('');
  const [feedback, setFeedback] = useState<Feedback>(null);
  const lastRef = useRef<{ id: number; at: number } | null>(null);
  const doneRef = useRef(false);
  const verify = expected != null;

  function finish(objectId: number) {
    if (doneRef.current) return;
    doneRef.current = true;
    setFeedback({ kind: 'ok', id: objectId });
    // Bei Verifikation kurz das grüne ✓ zeigen, sonst sofort übernehmen.
    window.setTimeout(() => onResult(objectId), verify ? 450 : 0);
  }

  function handle(objectId: number) {
    if (matchesExpected(objectId, expected)) {
      finish(objectId);
    } else {
      setFeedback({ kind: 'bad', id: objectId });
    }
  }

  function handleText(raw: string) {
    const id = parseScannedCode(raw);
    if (id == null || doneRef.current) return;
    const now = Date.now();
    if (lastRef.current && lastRef.current.id === id && now - lastRef.current.at < THROTTLE_MS) return;
    lastRef.current = { id, at: now };
    handle(id);
  }

  const { videoRef, state } = useBarcodeScanner(true, handleText);
  const cameraLive = state === 'starting' || state === 'scanning';

  // Manuelle Eingabe automatisch anbieten: nach kurzer Zeit ohne Treffer
  // bzw. sofort, wenn die Kamera nicht verfügbar ist.
  useEffect(() => {
    if (state === 'denied' || state === 'unsupported') { setManualOpen(true); return; }
    const t = window.setTimeout(() => setManualOpen(true), MANUAL_HINT_MS);
    return () => window.clearTimeout(t);
  }, [state]);

  // Escape schliesst den Dialog
  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  function submitManual() {
    const id = parseScannedCode(manual);
    if (id == null) { setFeedback(null); setManual(''); return; }
    handle(id);
  }

  return (
    <div style={backdrop} onClick={onClose}>
      <div style={sheet} onClick={(e) => e.stopPropagation()}>
        <div style={head}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 14, fontWeight: 700, color: '#0F172A' }}>
            <ScanLine size={17} style={{ color: '#2563eb' }} /> {title ?? 'Code scannen'}
          </span>
          <button onClick={onClose} aria-label="Schliessen" style={iconBtn}><X size={18} /></button>
        </div>

        {/* Kamera-Viewfinder */}
        <div style={viewport}>
          {cameraLive && (
            // eslint-disable-next-line jsx-a11y/media-has-caption
            <video ref={videoRef} style={video} muted playsInline autoPlay />
          )}
          {!cameraLive && (
            <div style={cameraOff}>
              <CameraOff size={34} strokeWidth={1.5} />
              <span style={{ fontSize: 13, marginTop: 8, maxWidth: 260, textAlign: 'center' }}>
                {state === 'denied'
                  ? 'Kein Kamerazugriff. Bitte Berechtigung erlauben oder die Nummer manuell eingeben.'
                  : 'Kamera auf diesem Gerät/Browser nicht verfügbar. Bitte Nummer manuell eingeben.'}
              </span>
            </div>
          )}

          {/* Scan-Rahmen + Status-Overlay */}
          {cameraLive && <div style={{ ...frame, borderColor: feedback?.kind === 'bad' ? '#dc2626' : feedback?.kind === 'ok' ? '#16a34a' : 'rgba(255,255,255,0.85)' }} />}
          {feedback && (
            <div style={{ ...badge, background: feedback.kind === 'ok' ? '#16a34a' : '#dc2626' }}>
              {feedback.kind === 'ok' ? <Check size={15} /> : <AlertTriangle size={15} />}
              {feedback.kind === 'ok' ? `Erkannt: ${fmtObjId(feedback.id)}` : `Falscher Code: ${fmtObjId(feedback.id)}`}
            </div>
          )}
        </div>

        <div style={{ padding: '12px 16px', display: 'flex', flexDirection: 'column', gap: 10 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: '#64748b' }}>
            <Camera size={13} /> {hint ?? (verify ? 'Etikett des erwarteten Objekts scannen.' : 'QR-/Barcode eines Datensatzes vor die Kamera halten.')}
          </span>

          {/* Manuelle Eingabe – Fallback, wenn das Scannen nicht klappt */}
          {!manualOpen ? (
            <button onClick={() => setManualOpen(true)} style={linkBtn}>
              <Keyboard size={13} /> Erfassung nicht möglich? Nummer manuell eingeben
            </button>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: '#475569' }}>Objektnummer manuell</span>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  value={manual}
                  onChange={(e) => setManual(e.target.value.replace(/\D/g, '').slice(0, 9))}
                  onKeyDown={(e) => { if (e.key === 'Enter') submitManual(); }}
                  inputMode="numeric" autoFocus placeholder="z. B. 100000042"
                  style={input}
                />
                <button onClick={submitManual} disabled={parseScannedCode(manual) == null} style={primaryBtn}>
                  Übernehmen
                </button>
              </div>
              {feedback?.kind === 'bad' && (
                <span style={{ fontSize: 11, color: '#dc2626' }}>
                  {fmtObjId(feedback.id)} passt nicht zum erwarteten Objekt.
                </span>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const backdrop: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(15,23,42,0.6)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
};
const sheet: React.CSSProperties = {
  width: '100%', maxWidth: 380, background: '#fff', borderRadius: 16, overflow: 'hidden',
  boxShadow: '0 20px 60px rgba(0,0,0,0.35)',
};
const head: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '12px 16px', borderBottom: '1px solid #F1F5F9',
};
const viewport: React.CSSProperties = {
  position: 'relative', width: '100%', aspectRatio: '1 / 1', background: '#0f172a',
  display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
};
const video: React.CSSProperties = { width: '100%', height: '100%', objectFit: 'cover' };
const cameraOff: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', color: '#94a3b8', padding: 24,
};
const frame: React.CSSProperties = {
  position: 'absolute', width: '62%', aspectRatio: '1 / 1', border: '3px solid rgba(255,255,255,0.85)',
  borderRadius: 16, boxShadow: '0 0 0 9999px rgba(0,0,0,0.25)', transition: 'border-color 0.15s',
};
const badge: React.CSSProperties = {
  position: 'absolute', bottom: 12, display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '6px 12px', borderRadius: 999, color: '#fff', fontSize: 12, fontWeight: 700,
};
const iconBtn: React.CSSProperties = {
  border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2, display: 'flex',
};
const linkBtn: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, alignSelf: 'flex-start',
  border: 'none', background: 'none', color: '#2563eb', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0,
};
const input: React.CSSProperties = {
  flex: 1, padding: '8px 10px', fontSize: 14, fontFamily: 'monospace', border: '1px solid #E2E8F0',
  borderRadius: 8, background: '#F8FAFC', outline: 'none',
};
const primaryBtn: React.CSSProperties = {
  padding: '8px 14px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff',
  fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
