'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { CameraOff, Check, AlertTriangle, X, Search, ScanLine, Building2, User as UserIcon, Boxes, Package, Layers } from 'lucide-react';
import {
  parseScannedCode, validateForStep, OBJECT_ID_MIN, OBJECT_ID_MAX,
  type ScanCandidate, type ScanKind, type ScanStep, type ScanRequest,
} from '@/lib/scan';
import { useBarcodeScanner } from '@/components/scan/use-barcode-scanner';
import { fmtObjId } from '@/components/erp/user-detail';

export type { ScanRequest };

// Mehrfach-Lesungen desselben Codes kurz ignorieren (ZXing feuert laufend).
const THROTTLE_MS = 1200;

// Symbol + Bezeichnung je erwartetem Objekttyp («was scanne ich jetzt?»).
const KIND_META: Record<ScanKind, { icon: React.ElementType; label: string }> = {
  company: { icon: Building2, label: 'Unternehmen' },
  user:       { icon: UserIcon,  label: 'Person' },
  instance:   { icon: Boxes,     label: 'Instanz' },
  article:    { icon: Package,   label: 'Artikel' },
  process:    { icon: Layers,    label: 'Prozess' },
  object:     { icon: ScanLine,  label: 'Datensatz' },
};

// Defensiv: ein unerwarteter/neuer ``kind`` (z. B. eine Standort-Art wie «company», die kein
// scannbarer Objekttyp ist) darf NIE die App crashen – Fallback auf das generische «Datensatz».
function kindMeta(kind: ScanKind | undefined | null) {
  return (kind && KIND_META[kind]) || KIND_META.object;
}

type Feedback = { kind: 'ok' | 'bad'; text: string } | null;

export function ScanDialog({ steps, onComplete, onClose }: ScanRequest & { onClose: () => void }) {
  const [stepIndex, setStepIndex] = useState(0);
  const [query, setQuery] = useState('');
  const [feedback, setFeedback] = useState<Feedback>(null);
  // Refs vermeiden veraltete Closures im Kamera-Callback (robustes Weiterschalten).
  const stepIndexRef = useRef(0);
  const results = useRef<number[]>([]);
  const lock = useRef(false);                 // während der Erfolgs-Quittierung sperren
  const completed = useRef(false);
  const lastRef = useRef<{ id: number; at: number } | null>(null);

  const step: ScanStep | undefined = steps[stepIndex];
  const multi = steps.length > 1;

  function handle(objectId: number) {
    if (lock.current || completed.current) return;
    const cur = steps[stepIndexRef.current];
    if (!cur) return;
    if (!validateForStep(objectId, cur)) {
      const text = cur.expected != null
        ? `${fmtObjId(objectId)} ist nicht das erwartete Objekt`
        : `${fmtObjId(objectId)} ist nicht im ERP`;
      setFeedback({ kind: 'bad', text });
      return;
    }
    // gültig → kurz grün zeigen, dann weiter / abschliessen
    lock.current = true;
    results.current = [...results.current, objectId];
    setFeedback({ kind: 'ok', text: `Erkannt: ${fmtObjId(objectId)}` });
    window.setTimeout(() => {
      const next = stepIndexRef.current + 1;
      if (next >= steps.length) {
        completed.current = true;
        onComplete(results.current);
      } else {
        stepIndexRef.current = next;
        setStepIndex(next);
        setQuery('');
        setFeedback(null);
        lock.current = false;
      }
    }, 380);
  }

  // Kamera-Treffer: Rohtext → Objektnummer; ungültige bleiben sichtbar, Kamera läuft weiter.
  // lastRef wird NICHT bei Schrittwechsel zurückgesetzt → ein im Bild verbleibender
  // (bereits quittierter) Code löst auf dem Folgeschritt keinen Fehlalarm aus.
  function handleText(raw: string) {
    if (lock.current || completed.current) return;
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
    // Der ganze Container IST die Kameraansicht. Kein Kopf, kein Erklärtext, kein zweiter
    // Kasten: was zu tun ist, steht im Bild – und was man sucht, tippt man im Bild.
    // Klick daneben schliesst (identisch zum ×), Esc ebenso.
    <div style={backdrop} onClick={onClose}>
      <div style={sheet} onClick={(e) => e.stopPropagation()}>
        {cameraLive ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <video ref={videoRef} style={video} muted playsInline autoPlay />
        ) : (
          <div style={cameraOff}>
            <CameraOff size={30} strokeWidth={1.5} />
            <span style={{ fontSize: 12, marginTop: 8, maxWidth: 260, textAlign: 'center' }}>
              {state === 'denied' ? 'Kein Kamerazugriff – bitte suchen.' : 'Kamera nicht verfügbar – bitte suchen.'}
            </span>
          </div>
        )}

        {/* Schritt-Fortschritt (nur bei Sequenz) – hauchdünn am oberen Rand */}
        {multi && (
          <div style={progressBar}>
            {steps.map((_, i) => (
              <span key={i} style={{ height: 3, flex: 1, borderRadius: 2, background: i < stepIndex ? 'var(--success)' : i === stepIndex ? '#fff' : 'rgba(255,255,255,.28)' }} />
            ))}
          </div>
        )}

        <button onClick={onClose} aria-label="Schliessen" style={closeBtn}><X size={18} /></button>

        {/* Zielrahmen mit Suchstrahl + der EINEN Angabe, die zählt: was soll gescannt werden. */}
        <div style={{ ...frame, borderColor: feedback?.kind === 'bad' ? 'var(--danger)' : feedback?.kind === 'ok' ? 'var(--success)' : 'rgba(255,255,255,.85)' }}>
          {cameraLive && !feedback && <div className="ix-scanbeam" style={beam} />}
        </div>
        {step && !feedback && (
          <div style={targetLabel}>
            {step.kind && (() => { const K = kindMeta(step.kind).icon; return <K size={15} strokeWidth={2} />; })()}
            {step.label}
          </div>
        )}

        {feedback && (
          <div style={{ ...badge, background: feedback.kind === 'ok' ? 'var(--success)' : 'var(--danger)' }}>
            {feedback.kind === 'ok' ? <Check size={14} /> : <AlertTriangle size={14} />} {feedback.text}
          </div>
        )}

        {/* Suche – im Bild statt darunter: eine milchige Leiste am unteren Rand. */}
        <div style={searchBar}>
          <div style={{ position: 'relative' }}>
            <Search size={15} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'rgba(255,255,255,.7)', pointerEvents: 'none' }} />
            <input
              value={query}
              onChange={(e) => { setQuery(e.target.value); setFeedback(null); }}
              onKeyDown={(e) => { if (e.key === 'Enter' && typedDirectOk) submitQuery(); }}
              autoFocus
              placeholder="Objektnummer suchen, z. B. 003"
              style={input}
            />
          </div>

          {suggestions.length > 0 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 152, overflowY: 'auto' }}>
              {suggestions.map((c) => (
                <button key={c.objectId} onClick={() => handle(c.objectId)} style={suggestionBtn}>
                  <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700 }}>{fmtObjId(c.objectId)}</span>
                  <span style={{ opacity: .8, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.label}</span>
                </button>
              ))}
            </div>
          )}

          {suggestions.length === 0 && query.trim() !== '' && (
            <button onClick={submitQuery} disabled={!typedDirectOk} style={{ ...primaryBtn, opacity: typedDirectOk ? 1 : 0.45 }}>
              {typedId != null ? `${fmtObjId(typedId)} übernehmen` : 'Übernehmen'}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

const backdrop: React.CSSProperties = {
  position: 'fixed', inset: 0, zIndex: 100, background: 'rgba(15,23,42,0.62)',
  display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16,
};
// Die Sheet-Fläche IST die Kamera: dunkel, randlos, alles Weitere liegt darüber.
const sheet: React.CSSProperties = {
  position: 'relative', width: '100%', maxWidth: 420, aspectRatio: '3 / 4', maxHeight: '82vh',
  background: '#0B1220', borderRadius: 18, overflow: 'hidden',
  boxShadow: '0 24px 60px rgba(15,23,42,0.4)',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
};
const video: React.CSSProperties = { position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover' };
const cameraOff: React.CSSProperties = {
  display: 'flex', flexDirection: 'column', alignItems: 'center', color: 'rgba(255,255,255,.6)', padding: 24,
};
const progressBar: React.CSSProperties = {
  position: 'absolute', top: 10, left: 14, right: 14, display: 'flex', gap: 5,
};
const closeBtn: React.CSSProperties = {
  position: 'absolute', top: 10, right: 10, border: 'none', cursor: 'pointer', display: 'flex',
  padding: 11, borderRadius: 999, color: '#fff', background: 'rgba(15,23,42,.45)',
  backdropFilter: 'blur(6px)',
};
const frame: React.CSSProperties = {
  position: 'absolute', width: '64%', aspectRatio: '1 / 1', border: '2px solid rgba(255,255,255,.85)',
  borderRadius: 18, boxShadow: '0 0 0 9999px rgba(4,8,16,0.42)', transition: 'border-color .15s',
  overflow: 'hidden',
};
// Der Suchstrahl: eine weiche Linie, die den Rahmen abtastet.
const beam: React.CSSProperties = {
  position: 'absolute', left: '6%', right: '6%', top: '50%', height: 2, borderRadius: 2,
  background: 'linear-gradient(90deg, transparent, rgba(255,255,255,.95), transparent)',
  boxShadow: '0 0 12px rgba(255,255,255,.6)',
};
// Die EINE Angabe im Bild: was soll gescannt werden.
const targetLabel: React.CSSProperties = {
  position: 'absolute', top: 'calc(50% + 34%)', display: 'inline-flex', alignItems: 'center', gap: 7,
  padding: '7px 14px', borderRadius: 999, background: 'rgba(15,23,42,.55)', backdropFilter: 'blur(6px)',
  color: '#fff', font: '700 13px var(--font-body)', letterSpacing: '.01em', maxWidth: '82%',
  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
};
const badge: React.CSSProperties = {
  position: 'absolute', top: 'calc(50% + 34%)', display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '7px 14px', borderRadius: 999, color: '#fff', fontSize: 12.5, fontWeight: 700, maxWidth: '86%',
};
const searchBar: React.CSSProperties = {
  position: 'absolute', left: 14, right: 14, bottom: 14, display: 'flex', flexDirection: 'column', gap: 6,
};
const input: React.CSSProperties = {
  width: '100%', paddingLeft: 36, paddingRight: 12, paddingTop: 11, paddingBottom: 11, fontSize: 14,
  border: '1px solid rgba(255,255,255,.22)', borderRadius: 12, outline: 'none', boxSizing: 'border-box',
  background: 'rgba(15,23,42,.5)', backdropFilter: 'blur(10px)', color: '#fff',
};
const suggestionBtn: React.CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', width: '100%', textAlign: 'left',
  border: '1px solid rgba(255,255,255,.18)', borderRadius: 10, cursor: 'pointer', fontSize: 13,
  background: 'rgba(15,23,42,.55)', backdropFilter: 'blur(10px)', color: '#fff',
};
const primaryBtn: React.CSSProperties = {
  padding: '10px 14px', borderRadius: 10, border: 'none', background: '#fff', color: 'var(--fg-1)',
  fontSize: 13, fontWeight: 700, cursor: 'pointer',
};
