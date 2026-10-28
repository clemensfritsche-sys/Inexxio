'use client';

import { useRef, useState } from 'react';
import { Loader2, Send } from 'lucide-react';
import { api } from '@/lib/api';
import { inputCls } from '@/components/erp/fields';

/** Was eine Runde dem Entwurf übergibt: das Papier und was dazu gehört. */
interface ComposedPaper {
  html: string;
  art: string;
  name: string;
  signers: { object_id: number; name: string }[];
}

type Turn = { who: 'user' | 'ai'; text: string };

/**
 * ►►► **Verfassen im Gespräch** – der Mensch sagt, was er braucht, die KI schreibt das Papier
 * in unserer Vorlage. ◄◄◄ Jede Runde schickt den Verlauf und den letzten Stand; das neue Papier
 * steht sofort links im Entwurf, Art und Name in ihren Feldern. Gespeichert wird nichts – ein
 * Dokument entsteht erst mit «Freigeben».
 */
export function ComposeChat({ onPaper }: { onPaper: (paper: ComposedPaper) => void }) {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const current = useRef<Record<string, unknown> | null>(null);

  async function say() {
    const said = text.trim();
    if (!said || busy) return;
    const next: Turn[] = [...turns, { who: 'user', text: said }];
    setTurns(next);
    setText('');
    setBusy(true);
    try {
      const r = await api.composeDocument(next, current.current);
      setTurns((t) => [...t, { who: 'ai', text: r.reply || '…' }]);
      if (r.paper && r.html) {
        current.current = r.paper as Record<string, unknown>;
        onPaper({ html: r.html, art: r.art ?? '', name: r.name ?? '', signers: r.signers ?? [] });
      }
    } catch (e) {
      setTurns((t) => [...t, { who: 'ai', text: (e as Error).message }]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {turns.length === 0 && (
          <span style={{ fontSize: 13, color: 'var(--fg-3)', lineHeight: 1.5 }}>
            Was soll es werden? Zum Beispiel: «Wartungsvertrag für den Heukran der Muster AG, jährlich,
            CHF 1’200, Hans Muster unterschreibt.»
          </span>
        )}
        {turns.map((t, i) => (
          <div key={i} style={{ alignSelf: t.who === 'user' ? 'flex-end' : 'flex-start', maxWidth: '88%',
            background: t.who === 'user' ? 'var(--accent-soft)' : 'var(--bg-3)', color: 'var(--fg-1)',
            borderRadius: 12, padding: '8px 12px', fontSize: 13.5, lineHeight: 1.45, whiteSpace: 'pre-wrap',
            overflowWrap: 'anywhere' }}>{t.text}</div>
        ))}
        {busy && (
          <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12.5, color: 'var(--fg-3)' }}>
            <Loader2 size={14} className="animate-spin" /> Die KI schreibt …
          </span>
        )}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <textarea className={inputCls} value={text} rows={2} maxLength={4000}
          placeholder={turns.length ? 'Was soll anders sein?' : 'Beschreiben Sie das Dokument'}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void say(); } }}
          style={{ flex: 1, resize: 'vertical', minHeight: 44 }} />
        <button type="button" className="erp-actbtn erp-actbtn-primary" disabled={busy || !text.trim()}
          onClick={() => void say()} aria-label="Senden" style={{ height: 44, flex: 'none' }}>
          <Send size={15} />
        </button>
      </div>
    </div>
  );
}
