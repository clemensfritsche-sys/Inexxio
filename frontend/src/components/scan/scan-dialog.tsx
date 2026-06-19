'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { Camera, CameraOff, Check, AlertTriangle, X, Search, ScanLine } from 'lucide-react';
import {
  parseScannedCode, validateForStep, OBJECT_ID_MIN, OBJECT_ID_MAX,
  type ScanCandidate, type ScanStep, type ScanRequest,
} from '@/lib/scan';
import { useBarcodeScanner } from '@/components/scan/use-barcode-scanner';
import { fmtObjId } from '@/components/erp/user-detail';

export type { ScanRequest };

// Mehrfach-Lesungen desselben Codes kurz ignorieren (ZXing feuert laufend).
const THROTTLE_MS = 1200;

type Feedback = { kind: 'ok' | 'bad'; text: string } | null;

export function ScanDialog({ title, steps, onComplete, onClose }: ScanRequest & { onClose: () => void }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [query, setQuery] = useState('');
  const [feedback, setFeedback] = useState<Feedback>(null);
  const results = useRef<number[]>([]);
  const busy = useRef(false);                 // während der Erfolgs-Quittierung sperren
  const lastRef = useRef<{ id: number; at: number } | null>(null);

  const step: ScanStep | undefined = steps[stepIndex];
  const multi = steps.length > 1;

  function accept(objectId: number) {
    if (busy.current || !step) return;
    busy.current = true;
    setFeedback({ kind: 'ok', text: `Erkannt: ${fmtObjId(objectId)}` });
    results.current = [...results.current, objectId];
    window.setTimeout(() => {
      if (stepIndex + 1 >= steps.length) {
        onComplete(results.current);
      } else {
        setStepIndex((i) => i + 1);
        setQuery('');
        setFeedback(null);
        lastRef.current = null;
        busy.current = false;
      }
    }, 420);
  }

  function handle(objectId: number) {
    if (!step) return;
    if (validateForStep(objectId, step)) {
      accept(objectId);
    } else {
      const text = step.expected != null
        ? `${fmtObjId(objectId)} ist nicht das erwartete Objekt`
        : `${fmtObjId(objectId)} ist nicht im ERP`;
      setFeedback({ kind: 'bad', text });
    }
  }

  // Kamera-Treffer: Rohtext → Objektnummer; ungültige bleiben sichtbar, Kamera läuft weiter.
  function handleText(raw: string) {
    if (busy.current) return;
    const id = parseScannedCode(raw);
    if (id == null) { setFeedback({ kind: 'bad', text: 'Kein gültiger Objekt-Code' }); return; }
    const now = Date.now();
    if (lastRef.current && lastRef.current.id === id && now - lastRef.current.at < THROTTLE_MS) return;
    lastRef.current = { id, at: now };
    handle(id);
  }

  const { videoRef, state } = useBarcodeScanner(true, handleText);
  const cameraLive = state === 'starting' || state === 'scanning';

  useEffect(() => {
    function onKey(e: KeyboardEvent) { if (e.key === 'Escape') onClose(); }
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Semantische Suche: tippt man «003», erscheint 100000003 als Vorschlag.
  const suggestions = useMemo<ScanCandidate[]>(() => {
    const q = query.trim().toLowerCase();
    if (!q || !step?.candidates) return [];
    return step.candidates
      .filter((c) => fmtObjId(c.objectId).includes(q) || c.label.toLowerCase().includes(q))
      .slice(0, 6);
  }, [query, step]);

  // Direkte Übernahme einer eingetippten vollständigen Objektnummer (ohne Vorschlag).
  const typedId = parseScannedCode(query);
  const typedDirectOk = typedId != null && (!step?.restrict || step.candidates?.some((c) => c.objectId === typedId));

  function submitQuery() {
    if (typedId == null) {
      setFeedback({ kind: 'bad', text: `Nummer muss ${OBJECT_ID_MIN}–${OBJECT_ID_MAX} sein` });
      return;
    }
    handle(typedId);
  }

  return (
    <div style={backdrop} onClick={onClose}>
      <div style={sheet} onClick={(e) => e.stopPropagation()}>
        {/* Kopf */}
        <div style={head}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
            <ScanLine size={17} style={{ color: '#2563eb', flexShrink: 0 }} />
            <span style={{ fontSize: 14, fontWeight: 700, color: '#0F172A', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {title ?? 'Code scannen'}
            </span>
          </div>
          <button onClick={onClose} aria-label="Schliessen" style={iconBtn}><X size={18} /></button>
        </div>

        {/* Schritt-Fortschritt (nur bei Sequenz) */}
        {multi && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 16px 0' }}>
            {steps.map((_, i) => (
              <span key={i} style={{ height: 4, flex: 1, borderRadius: 2, background: i < stepIndex ? '#16a34a' : i === stepIndex ? '#2563eb' : '#e2e8f0' }} />
            ))}
          </div>
        )}

        {/* Aktueller Schritt */}
        <div style={{ padding: '10px 16px 0' }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: '#0F172A' }}>
            {multi ? `Schritt ${stepIndex + 1}/${steps.length}: ` : ''}{step?.label ?? '—'}
          </div>
          {step?.hint && <div style={{ fontSize: 12, color: '#64748b', marginTop: 2 }}>{step.hint}</div>}
        </div>

        {/* Kamera-Viewfinder */}
        <div style={{ padding: '10px 16px 0' }}>
          <div style={viewport}>
            {cameraLive && (
              // eslint-disable-next-line jsx-a11y/media-has-caption
              <video ref={videoRef} style={video} muted playsInline autoPlay />
            )}
            {!cameraLive && (
              <div style={cameraOff}>
                <CameraOff size={30} strokeWidth={1.5} />
                <span style={{ fontSize: 12, marginTop: 8, maxWidth: 260, textAlign: 'center' }}>
                  {state === 'denied'
                    ? 'Kein Kamerazugriff – bitte unten manuell suchen/eingeben.'
                    : 'Kamera nicht verfügbar – bitte unten manuell suchen/eingeben.'}
                </span>
              </div>
            )}
            {cameraLive && (
              <div style={{ ...frame, borderColor: feedback?.kind === 'bad' ? '#dc2626' : feedback?.kind === 'ok' ? '#16a34a' : 'rgba(255,255,255,0.9)' }} />
            )}
            {feedback && (
              <div style={{ ...badge, background: feedback.kind === 'ok' ? '#16a34a' : '#dc2626' }}>
                {feedback.kind === 'ok' ? <Check size={14} /> : <AlertTriangle size={14} />} {feedback.text}
              </div>
            )}
          </div>
        </div>

        {/* Manuelle Suche – sofort sichtbar (semantische Objektnummer-Suche) */}
        <div style={{ padding: '12px 16px 16px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <span style={{ display: 'flex', alignItems: 'center', gap: 7, fontSize: 12, color: '#64748b' }}>
            <Camera size={13} /> Code vor die Kamera halten – oder manuell suchen:
          </span>
          <div style={{ position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 10, top: '50%', transform: 'translateY(-50%)', color: '#94a3b8', pointerEvents: 'none' }} />
            <input
              value={query}
              onChange={(e) => { setQuery(e.target.value); setFeedback(null); }}
              onKeyDown={(e) => { if (e.key === 'Enter' && typedDirectOk) submitQuery(); }}
              autoFocus
              placeholder="Objektnummer oder Suche, z. B. 003"
              style={input}
            />
          </div>

          {/* Vorschläge */}
          {suggestions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 168, overflowY: 'auto' }}>
              {suggestions.map((c) => (
                <button key={c.objectId} onClick={() => handle(c.objectId)} style={suggestionBtn}>
                  <span style={{ fontFamily: 'monospace', fontWeight: 700, color: '#2563eb' }}>{fmtObjId(c.objectId)}</span>
                  <span style={{ color: '#475569', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.label}</span>
                </button>
              ))}
            </div>
          )}

          {/* Direkte Übernahme einer vollständigen Nummer ohne Vorschlagsliste */}
          {suggestions.length === 0 && query.trim() !== '' && (
            <button onClick={submitQuery} disabled={!typedDirectOk} style={{ ...primaryBtn, opacity: typedDirectOk ? 1 : 0.5 }}>
              {typedId != null ? `${fmtObjId(typedId)} übernehmen` : 'Übernehmen'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const backdrop: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(15,23,42,0.55)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
};
const sheet: React.CSSProperties = {
  width: '100%', maxWidth: 380, background: '#fff', borderRadius: 14, overflow: 'hidden',
  border: '1px solid #E2E8F0', boxShadow: '0 20px 50px rgba(15,23,42,0.25)',
};
const head: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '12px 16px', borderBottom: '1px solid #F1F5F9',
};
const viewport: React.CSSProperties = {
  position: 'relative', width: '100%', aspectRatio: '4 / 3', background: '#0f172a',
  borderRadius: 10, display: 'flex', alignItems: 'center', justifyContent: 'center', overflow: 'hidden',
};
const video: React.CSSProperties = { width: '100%', height: '100%', objectFit: 'cover' };
const cameraOff: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', color: '#94a3b8', padding: 24,
};
const frame: React.CSSProperties = {
  position: 'absolute', width: '60%', aspectRatio: '1 / 1', border: '3px solid rgba(255,255,255,0.9)',
  borderRadius: 14, boxShadow: '0 0 0 9999px rgba(0,0,0,0.22)', transition: 'border-color 0.15s',
};
const badge: React.CSSProperties = {
  position: 'absolute', bottom: 10, display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '5px 11px', borderRadius: 999, color: '#fff', fontSize: 12, fontWeight: 700, maxWidth: '90%',
};
const iconBtn: React.CSSProperties = {
  border: 'none', background: 'none', color: '#94a3b8', cursor: 'pointer', padding: 2, display: 'flex',
};
const input: React.CSSProperties = {
  width: '100%', paddingLeft: 32, paddingRight: 12, paddingTop: 9, paddingBottom: 9, fontSize: 14,
  border: '1px solid #E2E8F0', borderRadius: 8, background: '#F8FAFC', outline: 'none', boxSizing: 'border-box',
};
const suggestionBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '8px 10px', width: '100%', textAlign: 'left',
  border: '1px solid #E2E8F0', borderRadius: 8, background: '#fff', cursor: 'pointer', fontSize: 13,
};
const primaryBtn: React.CSSProperties = {
  padding: '9px 14px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff',
  fontSize: 13, fontWeight: 600, cursor: 'pointer',
};
