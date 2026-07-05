'use client';

/**
 * Inexxio KI – der rechte-geschützte Assistent (ADR 004, Blaupause).
 *
 * Ein schwebender Launcher (unten rechts) öffnet den Chat. Der Verlauf lebt im
 * Client (sessionStorage, überlebt Navigation); das Backend ist stateless und
 * scoped jede Antwort über die Authz der angemeldeten Person. Kritische
 * KI-Vorschläge erscheinen als Karten mit Bestätigen/Ablehnen (menschliches Gate).
 * Ohne konfigurierten Provider (GET /ai/config → enabled=false) rendert das
 * Widget NICHTS – das ERP bleibt unverändert.
 */

import { useCallback, useEffect, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowRight, Check, Loader2, Send, Sparkles, X } from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Components } from 'react-markdown';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import type { AiChatMessage, AiProposal } from '@/types';

/** Event, mit dem die KI dem ERP-Feed signalisiert «ich habe Daten verändert – lade neu». */
export const DATA_CHANGED_EVENT = 'inexxio:data-changed';

type NavTarget = { path: string; label: string };

interface ChatItem {
  role: 'user' | 'assistant';
  content: string;
  proposals?: AiProposal[];
  navigate?: NavTarget;   // Navigationsvorschlag der KI (Knopf «… anzeigen»)
}

const STORE_KEY = 'inexxio_ai_chat_v1';
const GREETING = 'Guten Tag! Ich bin die Inexxio KI. Ich beantworte Fragen zu Ihren Daten '
  + 'im System und helfe bei Artikeln, Aufträgen oder im Shop – womit kann ich helfen?';

function loadHistory(): ChatItem[] {
  try {
    const raw = sessionStorage.getItem(STORE_KEY);
    if (raw) return JSON.parse(raw) as ChatItem[];
  } catch { /* leerer Start */ }
  return [];
}

export function AiAssistant({ context }: { context?: string }) {
  const [ready, setReady] = useState(false);       // eingeloggt + KI aktiviert
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const router = useRouter();

  // Immer ans Ende scrollen, wenn der Chat geöffnet wird (nicht oben stehen bleiben).
  const scrollToEnd = useCallback(() => {
    requestAnimationFrame(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight }));
  }, []);
  useEffect(() => { if (open) scrollToEnd(); }, [open, scrollToEnd]);

  // Eigenständige Auth-Prüfung (das Widget hängt in mehreren Layouts): Token setzen,
  // dann die KI-Verfügbarkeit klären. Ausgeloggt/inaktiv → gar nicht rendern.
  useEffect(() => {
    const unsub = onAuthChange(async (fbUser) => {
      if (!fbUser) { setReady(false); return; }
      try {
        api.setToken(await fbUser.getIdToken());
        const cfg = await api.getAiConfig();
        setReady(cfg.enabled);
      } catch { setReady(false); }
    });
    return unsub;
  }, []);

  // Verlauf einmal beim Mounten laden – überlebt so einen Seiten-Refresh (nicht erst
  // beim Öffnen), damit ein laufendes KI-Gespräch nach dem Neuladen erhalten bleibt.
  useEffect(() => { setItems(loadHistory()); }, []);
  useEffect(() => {
    try { sessionStorage.setItem(STORE_KEY, JSON.stringify(items.slice(-40))); } catch { /* voll */ }
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [items]);

  const send = useCallback(async () => {
    const text = input.trim();
    if (!text || busy) return;
    setInput('');
    setError(null);
    const next = [...items, { role: 'user' as const, content: text }];
    setItems(next);
    setBusy(true);
    try {
      const history: AiChatMessage[] = next
        .filter((m) => m.content.trim())
        .slice(-16)
        .map((m) => ({ role: m.role, content: m.content }));
      const res = await api.aiChat(history, context);
      setItems((cur) => [...cur, {
        role: 'assistant', content: res.reply, proposals: res.proposals,
        navigate: res.navigate ?? undefined,
      }]);
      // Hat die KI ERP-Daten verändert (Artikel/Auftrag/Schritt angelegt/geändert)?
      // → Feed/Detail live nachladen, ohne dass der Nutzer manuell aktualisieren muss.
      if (res.changed && typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent(DATA_CHANGED_EVENT));
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'KI derzeit nicht erreichbar');
      setItems((cur) => cur.slice(0, -1));   // Nutzertext zurück ins Feld
      setInput(text);
    } finally { setBusy(false); }
  }, [input, busy, items, context]);

  async function decide(actionId: number, decision: 'confirm' | 'reject') {
    setBusy(true); setError(null);
    try {
      const updated = decision === 'confirm'
        ? await api.aiConfirmAction(actionId)
        : await api.aiRejectAction(actionId);
      setItems((cur) => cur.map((m) => ({
        ...m,
        proposals: m.proposals?.map((p) => (p.id === actionId ? updated : p)),
      })));
      setItems((cur) => [...cur, {
        role: 'assistant',
        content: decision === 'confirm'
          ? `Erledigt – «${updated.summary}» wurde ausgeführt.`
          : `Verstanden – «${updated.summary}» wurde verworfen.`,
      }]);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Aktion fehlgeschlagen');
    } finally { setBusy(false); }
  }

  if (!ready) return null;

  return (
    <>
      {/* Launcher – Ink-Fläche, Rot nur als Fokus-/Hover-Akzent (Farbe = Bedeutung). */}
      {!open && (
        <button
          type="button"
          onClick={() => setOpen(true)}
          title="Inexxio KI – Assistent öffnen"
          aria-label="Inexxio KI – Assistent öffnen"
          className="fixed bottom-5 right-5 z-50 flex items-center justify-center rounded-full bg-fg-1 text-bg-1 shadow-ds-md transition-transform hover:scale-105 hover:shadow-ds-red"
          style={{ height: 52, width: 52 }}
        >
          <Sparkles size={22} />
        </button>
      )}

      {open && (
        <div
          className="fixed bottom-5 right-5 z-50 flex flex-col overflow-hidden rounded-ds-lg border border-border-1 bg-bg-1 shadow-ds-lg"
          style={{ width: 'min(420px, calc(100vw - 24px))', height: 'min(620px, calc(100vh - 40px))' }}
          role="dialog" aria-label="Inexxio KI"
        >
          {/* Kopf */}
          <div className="flex items-center gap-2.5 border-b border-border-1 bg-bg-2 px-4 py-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-fg-1 text-bg-1">
              <Sparkles size={15} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="font-display text-sm font-bold tracking-tight text-fg-1">Inexxio KI</div>
              <div className="truncate text-[11px] text-fg-4" title="Sieht nur, was Sie sehen dürfen – Antworten stützen sich auf echte Systemdaten.">
                Antwortet nur aus Ihren Daten
              </div>
            </div>
            <button type="button" onClick={() => setOpen(false)} aria-label="Schliessen"
              className="rounded-ds-sm p-1.5 text-fg-3 transition-colors hover:bg-bg-3 hover:text-fg-1">
              <X size={16} />
            </button>
          </div>

          {/* Verlauf */}
          <div ref={listRef} className="flex-1 overflow-y-auto px-4 py-3">
            <div className="flex flex-col gap-2.5">
              <Bubble role="assistant" content={GREETING} />
              {items.map((m, i) => (
                <div key={i} className="flex flex-col gap-2">
                  <Bubble role={m.role} content={m.content} />
                  {m.navigate && (
                    <button
                      type="button"
                      onClick={() => { setOpen(false); router.push(m.navigate!.path); }}
                      className="flex items-center gap-2 self-start rounded-ds-md border border-border-1 bg-bg-1 px-3.5 py-2 text-xs font-semibold text-accent-ink transition-colors hover:bg-accent-soft"
                    >
                      <ArrowRight size={14} /> {m.navigate.label}
                    </button>
                  )}
                  {m.proposals?.map((p) => (
                    <ProposalCard key={p.id} proposal={p} busy={busy}
                      onDecide={(d) => decide(p.id, d)} />
                  ))}
                </div>
              ))}
              {busy && (
                <div className="flex items-center gap-2 self-start rounded-ds-md bg-bg-2 px-3 py-2 text-xs text-fg-3">
                  <Loader2 size={13} className="animate-spin" /> denkt nach…
                </div>
              )}
            </div>
          </div>

          {/* Fehler + Eingabe */}
          <div className="border-t border-border-1 bg-bg-1 p-3">
            {error && <div className="mb-2 text-xs text-danger">{error}</div>}
            <div className="flex items-end gap-2">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
                }}
                rows={1}
                placeholder="Frage oder Auftrag an die KI…"
                className="max-h-28 min-h-[42px] flex-1 resize-none rounded-ds-md border border-border-1 bg-bg-1 px-3 py-2.5 text-sm text-fg-2 outline-none placeholder:text-fg-4 focus:ring-2 focus:ring-accent"
              />
              <button
                type="button" onClick={send} disabled={busy || !input.trim()}
                aria-label="Senden"
                className="flex h-[42px] w-[42px] shrink-0 items-center justify-center rounded-ds-md bg-inexxio text-white transition-opacity disabled:opacity-40"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

// Markdown-Renderer für Antworten der KI: **fett**, Listen und saubere Tabellen werden
// gerendert (statt roher Sternchen). Komponenten auf die Design-Tokens gemappt; kompakt
// für die Chat-Blase. Kein rohes HTML (react-markdown ohne rehype-raw = XSS-sicher).
const MD_COMPONENTS: Components = {
  p: (props) => <p className="mb-2 leading-relaxed last:mb-0" {...props} />,
  ul: (props) => <ul className="mb-2 list-disc space-y-0.5 pl-4 last:mb-0" {...props} />,
  ol: (props) => <ol className="mb-2 list-decimal space-y-0.5 pl-4 last:mb-0" {...props} />,
  li: (props) => <li className="leading-snug" {...props} />,
  strong: (props) => <strong className="font-semibold text-fg-1" {...props} />,
  em: (props) => <em className="italic" {...props} />,
  a: (props) => <a className="text-accent underline underline-offset-2" target="_blank" rel="noreferrer" {...props} />,
  code: (props) => <code className="rounded bg-bg-3 px-1 py-0.5 font-mono text-[12px] text-fg-1" {...props} />,
  pre: (props) => <pre className="mb-2 overflow-x-auto rounded-ds-md bg-bg-3 p-2 text-[12px] last:mb-0" {...props} />,
  h1: (props) => <h4 className="mb-1 mt-1 font-display text-sm font-bold text-fg-1" {...props} />,
  h2: (props) => <h4 className="mb-1 mt-1 font-display text-sm font-bold text-fg-1" {...props} />,
  h3: (props) => <h4 className="mb-1 mt-1 font-display text-sm font-bold text-fg-1" {...props} />,
  hr: () => <hr className="my-2 border-border-1" />,
  table: (props) => (
    <div className="mb-2 overflow-x-auto last:mb-0">
      <table className="w-full border-collapse text-[12px]" {...props} />
    </div>
  ),
  thead: (props) => <thead className="border-b border-border-2 text-left" {...props} />,
  th: (props) => <th className="px-2 py-1 font-semibold text-fg-2" {...props} />,
  td: (props) => <td className="border-t border-border-1 px-2 py-1 align-top text-fg-2" {...props} />,
};

function Bubble({ role, content }: { role: 'user' | 'assistant'; content: string }) {
  const mine = role === 'user';
  if (mine) {
    return (
      <div className="max-w-[85%] self-end whitespace-pre-wrap rounded-ds-md bg-fg-1 px-3 py-2 text-sm text-bg-1">
        {content}
      </div>
    );
  }
  return (
    <div className="max-w-[85%] self-start rounded-ds-md bg-bg-2 px-3 py-2 text-sm text-fg-2">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD_COMPONENTS}>
        {content}
      </ReactMarkdown>
    </div>
  );
}

/** Kritischer KI-Vorschlag: Karte mit menschlichem Gate (Bestätigen = die EINE laute Aktion). */
function ProposalCard({ proposal, busy, onDecide }: {
  proposal: AiProposal; busy: boolean; onDecide: (d: 'confirm' | 'reject') => void;
}) {
  const open = proposal.status === 'proposed';
  const statusLabel: Record<string, string> = {
    proposed: 'Wartet auf Bestätigung', executed: 'Ausgeführt',
    rejected: 'Verworfen', failed: 'Fehlgeschlagen',
  };
  const dot = proposal.status === 'executed' ? 'var(--success, #16a34a)'
    : proposal.status === 'failed' ? 'var(--danger, #dc2626)'
    : proposal.status === 'rejected' ? 'var(--fg-4)' : 'var(--warning, #C8861A)';
  return (
    <div className="self-start rounded-ds-md border border-border-2 bg-bg-1 px-3 py-2.5" style={{ maxWidth: '92%' }}>
      <div className="mb-1 flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-wider text-fg-3">
        <Sparkles size={11} /> KI-Vorschlag
      </div>
      <div className="text-sm text-fg-1">{proposal.summary}</div>
      <div className="mt-1.5 flex items-center gap-1.5 text-[11.5px] text-fg-3">
        <span aria-hidden style={{ width: 6, height: 6, borderRadius: 999, background: dot, display: 'inline-block' }} />
        {statusLabel[proposal.status] ?? proposal.status}
      </div>
      {open && (
        <div className="mt-2.5 flex gap-2">
          <button
            type="button" disabled={busy} onClick={() => onDecide('confirm')}
            className="flex items-center gap-1.5 rounded-ds-md bg-inexxio px-3.5 py-2 text-xs font-semibold text-white transition-opacity disabled:opacity-50"
          >
            <Check size={13} /> Bestätigen
          </button>
          <button
            type="button" disabled={busy} onClick={() => onDecide('reject')}
            className="rounded-ds-md border border-border-1 bg-bg-1 px-3.5 py-2 text-xs font-semibold text-fg-3 transition-colors hover:bg-bg-2 disabled:opacity-50"
          >
            Ablehnen
          </button>
        </div>
      )}
    </div>
  );
}
