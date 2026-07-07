'use client';

import { useRef, useState } from 'react';
import { Camera, X, Loader2 } from 'lucide-react';
import { api, attachmentUrl } from '@/lib/api';

// Wiederverwendbare Foto-Erfassung: Kamera (mobil «Foto aufnehmen») ODER Datei/Galerie.
// Verwaltet eine Liste von Attachment-URLs (Strings); der Aufrufer speichert sie in seinem
// Feld (Datenerfassung-Stichprobe, Verkaufs-Inhalt …). Bilder werden serverseitig
// verkleinert/normalisiert.
export function PhotoCapture({ value, onChange, max = 8, disabled = false, label }: {
  value: string[];
  onChange: (urls: string[]) => void;
  max?: number;
  disabled?: boolean;
  label?: string;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function onPick(files: FileList | null) {
    if (!files || files.length === 0) return;
    setBusy(true); setErr(null);
    try {
      const room = Math.max(0, max - value.length);
      const picked = Array.from(files).slice(0, room);
      const uploaded: string[] = [];
      for (const f of picked) {
        const { url } = await api.uploadAttachment(f);
        uploaded.push(url);
      }
      onChange([...value, ...uploaded]);
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Upload fehlgeschlagen');
    } finally {
      setBusy(false);
      if (inputRef.current) inputRef.current.value = '';
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {label && <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--fg-3)' }}>{label}</span>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {value.map((u, i) => (
          <a key={i} href={attachmentUrl(u)} target="_blank" rel="noopener noreferrer"
            style={{ position: 'relative', width: 76, height: 76, borderRadius: 10, overflow: 'hidden', border: '1px solid var(--border-1)', display: 'block', flexShrink: 0 }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={attachmentUrl(u)} alt={`Foto ${i + 1}`} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
            {!disabled && !busy && (
              <button type="button" title="Entfernen"
                onClick={(e) => { e.preventDefault(); onChange(value.filter((_, idx) => idx !== i)); }}
                style={{ position: 'absolute', top: 2, right: 2, width: 28, height: 28, borderRadius: 999, border: 'none', background: 'rgba(10,10,11,.62)', color: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                <X size={12} />
              </button>
            )}
          </a>
        ))}
        {!disabled && value.length < max && (
          <button type="button" onClick={() => inputRef.current?.click()} disabled={busy}
            style={{ width: 76, height: 76, borderRadius: 10, border: '1px dashed var(--border-2)', background: 'var(--bg-2)', color: 'var(--accent)', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', gap: 4, cursor: busy ? 'default' : 'pointer', fontSize: 11, fontWeight: 600, flexShrink: 0 }}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : <Camera size={18} />}
            {busy ? 'Lädt…' : 'Foto'}
          </button>
        )}
      </div>
      <input ref={inputRef} type="file" accept="image/*" multiple hidden onChange={(e) => onPick(e.target.files)} />
      {err && <span style={{ fontSize: 11.5, color: 'var(--danger)' }}>{err}</span>}
    </div>
  );
}
