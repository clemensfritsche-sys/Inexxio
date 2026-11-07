'use client';

import { useEffect, useState } from 'react';
import { Info, TriangleAlert, X } from 'lucide-react';
import { type Notice, dismiss, subscribe } from '@/lib/notice';

/** **Die Meldungen von `lib/notice`** – unten rechts, über allem, je eine Zeile mit Schliessen. */
export function NoticeHost() {
  const [list, setList] = useState<Notice[]>([]);
  useEffect(() => subscribe(setList), []);
  if (!list.length) return null;
  return (
    <div role="status" aria-live="polite"
      style={{ position: 'fixed', right: 16, bottom: 16, zIndex: 90, display: 'flex', flexDirection: 'column',
               gap: 8, maxWidth: 'min(420px, calc(100vw - 32px))' }}>
      {list.map((n) => (
        <div key={n.id} className="shadow-ds-md"
          style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '10px 12px', borderRadius: 10,
                   background: 'var(--bg-1)', border: '1px solid var(--border-2)', color: 'var(--fg-1)',
                   fontSize: 13, lineHeight: 1.45 }}>
          {n.tone === 'info'
            ? <Info size={15} aria-hidden style={{ flex: 'none', marginTop: 2, color: 'var(--accent)' }} />
            : <TriangleAlert size={15} aria-hidden style={{ flex: 'none', marginTop: 2, color: 'var(--warning)' }} />}
          <span style={{ flex: 1, minWidth: 0, overflowWrap: 'anywhere' }}>{n.text}</span>
          <button type="button" onClick={() => dismiss(n.id)} aria-label="Schliessen"
            style={{ flex: 'none', background: 'none', border: 0, padding: 0, cursor: 'pointer', color: 'var(--fg-3)' }}>
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  );
}
