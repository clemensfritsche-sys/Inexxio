'use client';

/**
 * KI-Bildbearbeitung für Shop-Produktbilder (ADR 004, Phase «Bild» – Gemini/Nano Banana).
 *
 * Bild auswählen, Anweisung eintippen («Hintergrund weiss», «freistellen», «heller») –
 * das Ergebnis wird als NEUES Bild angehängt (das Original bleibt; Entfernen wie gewohnt
 * über die Foto-Verwaltung). Rendert nichts, wenn die Bild-KI nicht konfiguriert ist.
 */

import { useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { api, attachmentUrl } from '@/lib/api';
import { useAiConfig } from '@/components/ai/use-ai';

export function AiImageAssist({ images, onAdd }: {
  images: string[];
  onAdd: (url: string) => void;
}) {
  const cfg = useAiConfig();
  const [selected, setSelected] = useState<string | null>(null);
  const [instruction, setInstruction] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!cfg?.image_enabled || images.length === 0) return null;

  async function run() {
    const text = instruction.trim();
    const src = selected ?? images[0];
    if (!text || !src || busy) return;
    setBusy(true); setError(null);
    try {
      const res = await api.aiImageEdit(src, text);
      onAdd(res.url);
      setInstruction('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Bildbearbeitung fehlgeschlagen');
    } finally { setBusy(false); }
  }

  const active = selected ?? images[0];

  return (
    <div className="mt-2 rounded-ds-md border border-border-1 bg-bg-2 p-2.5">
      <div className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider text-fg-3"
        title="Die KI erzeugt eine bearbeitete Kopie als neues Bild – das Original bleibt erhalten.">
        <Sparkles size={11} /> Mit KI bearbeiten
      </div>
      {images.length > 1 && (
        <div className="mb-2 flex gap-1.5 overflow-x-auto">
          {images.map((url) => (
            <button key={url} type="button" onClick={() => setSelected(url)}
              title="Dieses Bild bearbeiten"
              className="shrink-0 overflow-hidden rounded-ds-sm border-2 transition-colors"
              style={{ borderColor: url === active ? 'var(--accent)' : 'var(--border-1)' }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={attachmentUrl(url)} alt="" style={{ width: 44, height: 44, objectFit: 'cover', display: 'block' }} />
            </button>
          ))}
        </div>
      )}
      <div className="flex items-center gap-2">
        <input
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); run(); } }}
          placeholder="z. B. «Hintergrund weiss und Produkt freistellen»"
          disabled={busy}
          className="min-w-0 flex-1 rounded-ds-sm border border-border-1 bg-bg-1 px-3 py-2 text-[13px] text-fg-2 outline-none placeholder:text-fg-4 focus:ring-2 focus:ring-accent"
        />
        <button
          type="button" onClick={run} disabled={busy || !instruction.trim()}
          className="flex shrink-0 items-center gap-1.5 rounded-ds-sm bg-fg-1 px-3.5 py-2 text-xs font-semibold text-bg-1 transition-opacity disabled:opacity-40"
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
          {busy ? 'Bearbeitet…' : 'Erzeugen'}
        </button>
      </div>
      {error && <div className="mt-1.5 text-xs text-danger">{error}</div>}
    </div>
  );
}
