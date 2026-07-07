'use client';

import { useEffect, useRef, useState } from 'react';
import { Eraser, Check, Loader2, PenLine } from 'lucide-react';
import { api, attachmentUrl } from '@/lib/api';

/**
 * Digitale Unterschrift (wie bei Wix Studio): auf die Fläche zeichnen (Maus/Finger),
 * «Übernehmen» lädt sie als Bild-Attachment hoch und meldet die URL. Ist bereits eine
 * Unterschrift gesetzt (``value``), wird sie nur noch angezeigt.
 */
export function SignaturePad({ value, onChange, disabled = false, signerHint }: {
  value: string | null;
  onChange: (url: string | null) => void;
  disabled?: boolean;
  signerHint?: string;   // «nur … darf unterschreiben» / Hinweis
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const dirty = useRef(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Canvas auf Anzeigegrösse skalieren (scharfe Linien auf Retina).
  useEffect(() => {
    const c = canvasRef.current;
    if (!c || value) return;
    const ratio = window.devicePixelRatio || 1;
    const rect = c.getBoundingClientRect();
    c.width = rect.width * ratio;
    c.height = rect.height * ratio;
    const ctx = c.getContext('2d');
    if (ctx) { ctx.scale(ratio, ratio); ctx.lineWidth = 2.2; ctx.lineCap = 'round'; ctx.strokeStyle = '#0f172a'; }
  }, [value]);

  function pos(e: React.PointerEvent) {
    const c = canvasRef.current!;
    const r = c.getBoundingClientRect();
    return { x: e.clientX - r.left, y: e.clientY - r.top };
  }
  function down(e: React.PointerEvent) {
    if (disabled) return;
    drawing.current = true; dirty.current = true;
    const ctx = canvasRef.current!.getContext('2d')!;
    const p = pos(e); ctx.beginPath(); ctx.moveTo(p.x, p.y);
    (e.target as Element).setPointerCapture?.(e.pointerId);
  }
  function move(e: React.PointerEvent) {
    if (!drawing.current) return;
    const ctx = canvasRef.current!.getContext('2d')!;
    const p = pos(e); ctx.lineTo(p.x, p.y); ctx.stroke();
  }
  function up() { drawing.current = false; }

  function clear() {
    const c = canvasRef.current;
    if (!c) return;
    c.getContext('2d')!.clearRect(0, 0, c.width, c.height);
    dirty.current = false; setErr(null);
  }

  async function accept() {
    if (!dirty.current) { setErr('Bitte zuerst unterschreiben.'); return; }
    setBusy(true); setErr(null);
    try {
      const blob: Blob = await new Promise((res, rej) =>
        canvasRef.current!.toBlob((b) => (b ? res(b) : rej()), 'image/png'));
      const { url } = await api.uploadAttachment(new File([blob], 'unterschrift.png', { type: 'image/png' }));
      onChange(url);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Unterschrift konnte nicht gespeichert werden');
    } finally { setBusy(false); }
  }

  if (value) {
    return (
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={attachmentUrl(value)} alt="Unterschrift" style={{ height: 60, maxWidth: 240, objectFit: 'contain', border: '1px solid var(--border-1)', borderRadius: 8, background: '#fff', padding: 4 }} />
        {!disabled && (
          <button type="button" onClick={() => onChange(null)}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer' }}>
            <Eraser size={13} /> Neu zeichnen
          </button>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {signerHint && <span style={{ fontSize: 11.5, color: 'var(--fg-4)' }}>{signerHint}</span>}
      <canvas ref={canvasRef}
        onPointerDown={down} onPointerMove={move} onPointerUp={up} onPointerLeave={up}
        style={{ width: '100%', height: 130, border: '1px dashed var(--border-2)', borderRadius: 10, background: '#fff', touchAction: 'none', cursor: disabled ? 'not-allowed' : 'crosshair' }} />
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 11.5, color: 'var(--fg-4)', flex: 1 }}>
          <PenLine size={13} /> Hier unterschreiben
        </span>
        <button type="button" onClick={clear} disabled={disabled || busy}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '6px 11px', borderRadius: 8, border: '1px solid var(--border-2)', background: '#fff', color: 'var(--fg-3)', fontSize: 12.5, fontWeight: 600, cursor: 'pointer' }}>
          <Eraser size={13} /> Löschen
        </button>
        <button type="button" onClick={accept} disabled={disabled || busy}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 6, padding: '6px 13px', borderRadius: 8, border: 'none', background: '#2563eb', color: '#fff', fontSize: 12.5, fontWeight: 700, cursor: 'pointer' }}>
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Check size={13} />} Übernehmen
        </button>
      </div>
      {err && <span style={{ fontSize: 11.5, color: 'var(--danger)' }}>{err}</span>}
    </div>
  );
}
