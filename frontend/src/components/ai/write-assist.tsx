'use client';

/**
 * KI-Schreibhilfe für das Dokumente-Prozessschrittmodul (ADR 004, Phase «Dokumente»).
 *
 * Ein kompakter Assist-Balken über dem Editor: Anweisung eintippen («Erstelle einen
 * Rahmenvertrag …», «Formuliere §2 präziser») → die KI liefert das strukturierte
 * Dokument, das den Entwurf ERSETZT (der Autosave des Panels übernimmt das Speichern;
 * bis dahin ist nichts festgeschrieben – «Ausstellen» bleibt der menschliche Schritt).
 * Ohne konfigurierte KI rendert die Komponente nichts.
 */

import { useState } from 'react';
import { Loader2, Sparkles } from 'lucide-react';
import { api } from '@/lib/api';
import type { AiDocContent, DocumentContent } from '@/types';
import { useAiConfig } from '@/components/ai/use-ai';

export function AiWriteAssist({ current, onResult }: {
  current: DocumentContent | null;
  onResult: (content: DocumentContent) => void;
}) {
  const cfg = useAiConfig();
  const [instruction, setInstruction] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!cfg?.enabled) return null;

  async function run() {
    const text = instruction.trim();
    if (!text || busy) return;
    setBusy(true); setError(null);
    try {
      const payload: AiDocContent | null = current
        ? {
            title: current.title ?? '',
            subtitle: current.subtitle ?? null,
            body: current.body ?? '',
          }
        : null;
      const res = await api.aiWrite(text, payload);
      onResult({
        title: res.content.title ?? '',
        subtitle: res.content.subtitle ?? null,
        body: res.content.body ?? '',
      });
      setInstruction('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Schreibhilfe fehlgeschlagen');
    } finally { setBusy(false); }
  }

  return (
    <div className="rounded-ds-md border border-border-1 bg-bg-2 p-2.5">
      <div className="mb-1.5 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider text-fg-3"
        title="Die KI verfasst oder überarbeitet den Entwurf – nichts wird ohne Sie ausgestellt.">
        <Sparkles size={11} /> KI-Schreibhilfe
      </div>
      <div className="flex items-center gap-2">
        <input
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); run(); } }}
          placeholder="z. B. «Erstelle einen Wartungsvertrag für die CNC-Fräse» oder «Formuliere §2 präziser»"
          disabled={busy}
          className="min-w-0 flex-1 rounded-ds-sm border border-border-1 bg-bg-1 px-3 py-2 text-[13px] text-fg-2 outline-none placeholder:text-fg-4 focus:ring-2 focus:ring-accent"
        />
        <button
          type="button" onClick={run} disabled={busy || !instruction.trim()}
          className="flex shrink-0 items-center gap-1.5 rounded-ds-sm bg-fg-1 px-3.5 py-2 text-xs font-semibold text-bg-1 transition-opacity disabled:opacity-40"
        >
          {busy ? <Loader2 size={13} className="animate-spin" /> : <Sparkles size={13} />}
          {busy ? 'Schreibt…' : 'Verfassen'}
        </button>
      </div>
      {error && <div className="mt-1.5 text-xs text-danger">{error}</div>}
    </div>
  );
}
