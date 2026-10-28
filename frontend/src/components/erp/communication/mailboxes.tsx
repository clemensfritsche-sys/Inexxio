'use client';

import { useState } from 'react';
import { api } from '@/lib/api';
import { StatusDot } from '@/components/erp/fields';
import type { Mailbox } from '@/types';

/** Das Postfach dieses Datensatzes – mit Zustand und, wo ich darf, Verbinden/Trennen.
 *  Ohne Anbindung (kein OAuth-Client) steht hier nichts: dann wird eine Mail erfasst. */
export function Mailboxes({ boxes }: { boxes: Mailbox[] }) {
  const [error, setError] = useState<string | null>(null);
  const shown = boxes.filter((b) => b.connected || b.may_connect || b.problem);
  if (!shown.length) return null;
  const connect = (b: Mailbox) => api.connectMailbox(b.channel)
    .then((r) => { window.location.href = r.url; })
    .catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht verbinden.'));
  // Danach lädt das Postfach über `lib/feed.TOUCHES` selbst nach.
  const drop = (b: Mailbox) => api.disconnectMailbox(b.channel)
    .catch((e) => setError(e instanceof Error ? e.message : 'Konnte nicht trennen.'));
  const link = { border: 0, background: 'none', padding: 0, font: 'inherit', fontSize: 12,
    color: 'var(--accent)', cursor: 'pointer' } as const;
  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 16px', marginBottom: 16, fontSize: 12,
      color: 'var(--fg-3)' }}>
      <span style={{ color: 'var(--fg-2)', fontWeight: 600 }}>Postfach</span>
      {shown.map((b) => (
        <span key={b.channel} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, minWidth: 0 }}
          data-tip={b.problem ?? (b.connected ? 'Verbunden – Mails gehen hinaus und kommen herein'
            : 'Nicht verbunden')}>
          <StatusDot color={b.problem ? 'var(--danger)' : b.connected ? 'var(--success)' : 'var(--fg-4)'} />
          <span className="truncate">{b.address || 'Kein Postfach'}</span>
          {b.may_connect && (b.connected
            ? <button type="button" style={link} onClick={() => void drop(b)}>Trennen</button>
            : <button type="button" style={link} onClick={() => void connect(b)}>
                {b.problem ? 'Neu verbinden' : 'Verbinden'}</button>)}
        </span>
      ))}
      {error && <span style={{ color: 'var(--danger)' }}>{error}</span>}
    </div>
  );
}
