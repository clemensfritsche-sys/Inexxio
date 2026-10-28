'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Camera, CameraOff, Check, Loader2, RotateCcw, X, Zap } from 'lucide-react';
import { useCamera } from '@/components/scan/use-camera';
import { type Cv, type Pixels, type Quad, detect, frame, loadCv, moved, warp } from '@/lib/doc-scan';

/** So breit wird das Live-Bild für die Suche verkleinert – schnell genug für 4 Bilder je Sekunde. */
const PROBE_W = 480;
/** Alle wie viele Millisekunden gesucht wird. */
const PROBE_MS = 250;
/** So oft hintereinander muss das Blatt ruhig liegen, bis es von selbst aufnimmt (≈ 1.5 s). */
const STEADY = 6;
/** «Ruhig» heisst: keine Ecke bewegt sich um mehr als diesen Anteil der Bildbreite. */
const STILL = 0.02;

/** Ein aufgenommenes Bild – in voller Auflösung, mit den Ecken des Blatts darin. */
interface Shot { px: Pixels; quad: Quad; url: string }

/**
 * ►►► **Der Dokumentscanner** – Kamera, Blatt finden, von selbst aufnehmen, Ecken
 * nachziehen, «Nächste Seite», «Fertig». ◄◄◄
 *
 * Liegt das Blatt ruhig im Bild, nimmt der Scanner von selbst auf; der Auslöser geht immer.
 * Nach jeder Aufnahme stehen die vier Ecken da und lassen sich ziehen; «Übernehmen» zieht das
 * Blatt gerade. Die Seiten gehen als Bilder an den Entwurf, die Freigabe macht ein PDF daraus.
 * Lädt OpenCV nicht, bleibt es ein Fotoapparat (die Ecken stehen dann am Bildrand).
 */
export function DocScanner({ onDone, onCancel }: {
  onDone: (pages: Blob[]) => void; onCancel: () => void;
}) {
  const [cv, setCv] = useState<Cv | null>(null);
  const [cvFailed, setCvFailed] = useState(false);
  const [shot, setShot] = useState<Shot | null>(null);
  const [pages, setPages] = useState<Blob[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let gone = false;
    loadCv().then(({ cv: m }) => { if (!gone) setCv(m); }).catch(() => { if (!gone) setCvFailed(true); });
    return () => { gone = true; };
  }, []);

  const take = useCallback(async (s: Shot) => {
    setBusy(true);
    try {
      const flat = cv ? warp(cv, s.px, s.quad) : s.px;
      const blob = await toJpeg(flat);
      setPages((p) => [...p, blob]);
      setShot(null);
    } finally {
      setBusy(false);
    }
  }, [cv]);

  return createPortal(
    <div style={{ position: 'fixed', inset: 0, zIndex: 70, background: '#0b0b0c', color: '#fff',
                  display: 'flex', flexDirection: 'column', paddingTop: 'env(safe-area-inset-top, 0px)' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 14px' }}>
        <button type="button" onClick={onCancel} aria-label="Abbrechen" style={CHIP}><X size={15} /></button>
        <span style={{ flex: 1, fontSize: 13, opacity: 0.8 }}>
          {shot ? 'Ecken prüfen – ziehen, wo nötig' : cv ? 'Blatt ins Bild halten – es nimmt von selbst auf'
            : cvFailed ? 'Ohne Blatterkennung – selbst auslösen' : 'Scanner startet …'}
        </span>
        {pages.length > 0 && !shot && (
          <button type="button" onClick={() => onDone(pages)} style={{ ...CHIP, background: '#fff', color: '#0b0b0c', fontWeight: 600 }}>
            <Check size={15} /> Fertig ({pages.length} {pages.length === 1 ? 'Seite' : 'Seiten'})
          </button>
        )}
      </div>
      <div style={{ flex: 1, minHeight: 0, position: 'relative' }}>
        {shot
          ? <Adjust shot={shot} busy={busy} onRetake={() => setShot(null)}
              onTake={(quad) => void take({ ...shot, quad })} />
          : <Live cv={cv} onShot={setShot} next={pages.length > 0} />}
      </div>
    </div>,
    document.body,
  );
}

/** Das laufende Bild: sucht das Blatt, zeigt es, nimmt auf, wenn es ruhig liegt. */
function Live({ cv, onShot, next }: { cv: Cv | null; onShot: (s: Shot) => void; next: boolean }) {
  const { videoRef, state, torch, setTorch } = useCamera(true);
  const [quad, setQuad] = useState<Quad | null>(null);
  const probe = useRef<HTMLCanvasElement | null>(null);
  const steady = useRef(0);
  const last = useRef<Quad | null>(null);
  const live = state === 'starting' || state === 'scanning';

  const capture = useCallback((found: Quad | null) => {
    const v = videoRef.current;
    if (!v?.videoWidth) return;
    const px = grab(v, v.videoWidth);
    const k = v.videoWidth / PROBE_W;
    const q = found ? found.map((p) => ({ x: p.x * k, y: p.y * k })) as Quad : frame(px.width, px.height);
    onShot({ px, quad: q, url: toUrl(px) });
  }, [onShot, videoRef]);

  useEffect(() => {
    if (!cv) return;
    const t = setInterval(() => {
      const v = videoRef.current;
      if (!v?.videoWidth) return;
      const found = detect(cv, grab(v, PROBE_W, probe));
      setQuad(found);
      steady.current = found && last.current && moved(found, last.current, PROBE_W) < STILL ? steady.current + 1 : 0;
      last.current = found;
      if (found && steady.current >= STEADY) { steady.current = 0; capture(found); }
    }, PROBE_MS);
    return () => clearInterval(t);
  }, [cv, capture, videoRef]);

  if (!live) {
    return (
      <div style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center',
                    justifyContent: 'center', gap: 10, padding: 24, textAlign: 'center', opacity: 0.8 }}>
        <CameraOff size={28} strokeWidth={1.5} />
        <span style={{ fontSize: 13 }}>
          {state === 'denied' ? 'Kein Kamerazugriff.' : 'Dieses Gerät hat keine nutzbare Kamera.'} Im Entwurf
          lässt sich die Datei stattdessen wählen.
        </span>
      </div>
    );
  }
  const v = videoRef.current;
  const k = v?.videoWidth ? PROBE_W / v.videoWidth : 1;
  return (
    <>
      {/* eslint-disable-next-line jsx-a11y/media-has-caption */}
      <video ref={videoRef} muted playsInline autoPlay style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
      {quad && v?.videoWidth ? (
        <svg viewBox={`0 0 ${PROBE_W} ${Math.round(v.videoHeight * k)}`} preserveAspectRatio="xMidYMid meet"
          style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
          <polygon points={quad.map((p) => `${p.x},${p.y}`).join(' ')}
            fill="rgba(255,255,255,.12)" stroke="#fff" strokeWidth={2} />
        </svg>
      ) : null}
      <div style={{ position: 'absolute', insetInline: 0, bottom: 0, display: 'flex', justifyContent: 'center',
                    alignItems: 'center', gap: 12, padding: 18 }}>
        {next && <span style={{ ...CHIP, pointerEvents: 'none' }}>Nächste Seite</span>}
        <button type="button" onClick={() => capture(quad)} aria-label="Auslösen"
          style={{ width: 62, height: 62, borderRadius: 999, background: '#fff', color: '#0b0b0c',
                   border: '4px solid rgba(255,255,255,.5)', display: 'grid', placeItems: 'center' }}>
          <Camera size={22} />
        </button>
        {torch !== null && (
          <button type="button" onClick={() => void setTorch(!torch)} aria-label="Licht" style={CHIP}><Zap size={14} /></button>
        )}
      </div>
    </>
  );
}

/** Die Aufnahme mit ihren vier Ecken – ziehen, dann übernehmen. */
function Adjust({ shot, busy, onRetake, onTake }: {
  shot: Shot; busy: boolean; onRetake: () => void; onTake: (q: Quad) => void;
}) {
  const [quad, setQuad] = useState<Quad>(shot.quad);
  const svg = useRef<SVGSVGElement | null>(null);
  const drag = useRef<number | null>(null);
  const { width: w, height: h } = shot.px;

  const move = (e: React.PointerEvent) => {
    if (drag.current == null || !svg.current) return;
    const pt = svg.current.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const at = pt.matrixTransform(svg.current.getScreenCTM()?.inverse());
    const i = drag.current;
    setQuad((q) => q.map((p, j) => (j === i ? { x: clamp(at.x, w), y: clamp(at.y, h) } : p)) as Quad);
  };
  const r = Math.max(w, h) / 45;
  return (
    <>
      <svg ref={svg} viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="xMidYMid meet"
        onPointerMove={move} onPointerUp={() => { drag.current = null; }} onPointerLeave={() => { drag.current = null; }}
        style={{ width: '100%', height: '100%', touchAction: 'none', display: 'block' }}>
        <image href={shot.url} width={w} height={h} />
        <polygon points={quad.map((p) => `${p.x},${p.y}`).join(' ')} fill="rgba(255,255,255,.12)"
          stroke="#fff" strokeWidth={r / 4} />
        {quad.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r={r} fill="rgba(255,255,255,.35)" stroke="#fff" strokeWidth={r / 5}
            style={{ cursor: 'grab' }}
            onPointerDown={(e) => { drag.current = i; (e.target as Element).setPointerCapture?.(e.pointerId); }} />
        ))}
      </svg>
      <div style={{ position: 'absolute', insetInline: 0, bottom: 0, display: 'flex', justifyContent: 'center',
                    gap: 10, padding: 18 }}>
        <button type="button" onClick={onRetake} style={CHIP}><RotateCcw size={14} /> Neu aufnehmen</button>
        <button type="button" onClick={() => onTake(quad)} disabled={busy}
          style={{ ...CHIP, background: '#fff', color: '#0b0b0c', fontWeight: 600 }}>
          {busy ? <Loader2 size={14} className="animate-spin" /> : <Check size={14} />} Übernehmen
        </button>
      </div>
    </>
  );
}

const CHIP: React.CSSProperties = {
  display: 'inline-flex', alignItems: 'center', gap: 6, height: 34, padding: '0 12px', borderRadius: 999,
  background: 'rgba(255,255,255,.18)', color: '#fff', border: 0, fontSize: 13, backdropFilter: 'blur(6px)',
};

const clamp = (v: number, max: number) => Math.min(max, Math.max(0, v));

/** Ein Einzelbild aus dem Strom – in der verlangten Breite. */
function grab(v: HTMLVideoElement, width: number, keep?: React.MutableRefObject<HTMLCanvasElement | null>): Pixels {
  const c = keep?.current ?? document.createElement('canvas');
  if (keep) keep.current = c;
  c.width = width;
  c.height = Math.round(v.videoHeight * (width / v.videoWidth));
  const g = c.getContext('2d', { willReadFrequently: true })!;
  g.drawImage(v, 0, 0, c.width, c.height);
  return g.getImageData(0, 0, c.width, c.height);
}

function canvasOf(px: Pixels): HTMLCanvasElement {
  const c = document.createElement('canvas');
  c.width = px.width;
  c.height = px.height;
  c.getContext('2d')!.putImageData(new ImageData(new Uint8ClampedArray(px.data), px.width, px.height), 0, 0);
  return c;
}

const toUrl = (px: Pixels) => canvasOf(px).toDataURL('image/jpeg', 0.8);

function toJpeg(px: Pixels): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvasOf(px).toBlob((b) => (b ? resolve(b) : reject(new Error('Bild nicht erzeugt'))), 'image/jpeg', 0.85);
  });
}
