'use client';

import { useEffect, useState } from 'react';
import { Plus, Trash2, ShieldCheck, Info, AlertCircle, Fingerprint } from 'lucide-react';
import { api } from '@/lib/api';
import { registerPasskey, passkeySupported, isPasskeyCancellation } from '@/lib/passkey';
import type { Passkey } from '@/types';

function formatDate(iso: string | null): string {
  if (!iso) return '–';
  try {
    return new Intl.DateTimeFormat('de-CH', { dateStyle: 'medium' }).format(new Date(iso));
  } catch {
    return '–';
  }
}

export function PasskeysCard() {
  const [passkeys, setPasskeys] = useState<Passkey[]>([]);
  const [loading, setLoading] = useState(true);
  const [supported, setSupported] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    setSupported(passkeySupported());
    let cancelled = false;
    api.listPasskeys()
      .then((rows) => { if (!cancelled) setPasskeys(rows); })
      .catch(() => { /* Liste bleibt leer */ })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  async function handleAdd() {
    if (adding) return;
    setError('');
    setAdding(true);
    try {
      // Kein Name nötig – wird serverseitig automatisch vergeben (durchnummeriert).
      const created = await registerPasskey();
      setPasskeys((prev) => [created, ...prev]);
    } catch (err: unknown) {
      if (!isPasskeyCancellation(err)) {
        setError(err instanceof Error ? err.message : 'Passkey konnte nicht hinzugefügt werden.');
      }
    } finally {
      setAdding(false);
    }
  }

  async function handleDelete(id: number) {
    setError('');
    const prev = passkeys;
    setPasskeys((rows) => rows.filter((p) => p.id !== id));
    try {
      await api.deletePasskey(id);
    } catch (err: unknown) {
      setPasskeys(prev); // Rollback
      setError(err instanceof Error ? err.message : 'Passkey konnte nicht entfernt werden.');
    }
  }

  const empty = !loading && passkeys.length === 0;

  return (
    <div style={{ background: 'var(--bg-1)', border: '1px solid var(--border-1)', borderRadius: 'var(--r-md)', overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '18px 24px', borderBottom: '1px solid var(--border-1)' }}>
        <Fingerprint style={{ width: 16, height: 16, color: 'var(--fg-3)' }} />
        <h2 style={{ fontSize: 15, fontWeight: 600, color: 'var(--fg-1)', margin: 0 }}>Passkeys</h2>
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 16px', background: 'var(--bg-2)', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-1)' }}>
          <Fingerprint style={{ width: 16, height: 16, color: 'var(--inexxio-red)', flexShrink: 0, marginTop: 1 }} />
          <p style={{ fontSize: 13, color: 'var(--fg-2)', margin: 0, lineHeight: 1.55 }}>
            Melden Sie sich künftig ohne E-Mail-Link an – mit Face&nbsp;ID, Touch&nbsp;ID, Windows&nbsp;Hello oder
            einem Sicherheitsschlüssel. Ein Passkey ist an dieses Gerät gebunden und verlässt es nie.
          </p>
        </div>

        {error && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 14px', background: 'var(--danger-bg)', borderRadius: 'var(--r-sm)', border: '1px solid var(--danger)' }}>
            <AlertCircle style={{ width: 14, height: 14, color: 'var(--danger)', flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>{error}</p>
          </div>
        )}

        {loading ? (
          <p style={{ fontSize: 13, color: 'var(--fg-4)', margin: 0 }}>Wird geladen…</p>
        ) : empty ? (
          <p style={{ fontSize: 13, color: 'var(--fg-3)', margin: 0, lineHeight: 1.55 }}>
            Noch kein Passkey hinterlegt. Richten Sie jetzt einen ein – das ist die schnellste und
            sicherste Art, sich anzumelden.
          </p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {passkeys.map((pk) => (
              <li
                key={pk.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px',
                  border: '1px solid var(--border-1)', borderRadius: 'var(--r-sm)',
                }}
              >
                <ShieldCheck style={{ width: 18, height: 18, color: 'var(--success)', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 14, fontWeight: 600, color: 'var(--fg-1)', margin: 0 }}>
                    {pk.device_name || 'Passkey'}
                  </p>
                  <p style={{ fontSize: 12, color: 'var(--fg-3)', margin: '2px 0 0' }}>
                    Hinzugefügt {formatDate(pk.created_at)}
                    {pk.last_used_at ? ` · Zuletzt ${formatDate(pk.last_used_at)}` : ''}
                    {pk.backed_up ? ' · Synchronisiert' : ''}
                  </p>
                </div>
                <button
                  onClick={() => handleDelete(pk.id)}
                  aria-label="Passkey entfernen"
                  title="Passkey entfernen"
                  style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    width: 32, height: 32, borderRadius: 'var(--r-sm)', border: '1px solid var(--border-1)',
                    background: 'var(--bg-1)', color: 'var(--danger)', cursor: 'pointer', flexShrink: 0,
                  }}
                >
                  <Trash2 style={{ width: 15, height: 15 }} />
                </button>
              </li>
            ))}
          </ul>
        )}

        {!supported ? (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 14px', background: 'var(--info-bg)', borderRadius: 'var(--r-sm)', border: '1px solid var(--info)' }}>
            <Info style={{ width: 14, height: 14, color: 'var(--info)', flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 12, color: 'var(--info)', margin: 0 }}>
              Dieser Browser unterstützt keine Passkeys. Bitte einen aktuellen Browser verwenden.
            </p>
          </div>
        ) : empty ? (
          /* Erster Passkey: der EINE laute Akzent – ein gefüllter roter CTA (Design-System). */
          <button
            onClick={handleAdd}
            disabled={adding}
            style={{
              alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '10px 18px', borderRadius: 'var(--r-pill)', border: 'none',
              background: 'var(--inexxio-red)', color: '#fff',
              fontSize: 13.5, fontWeight: 600, cursor: adding ? 'wait' : 'pointer', opacity: adding ? 0.6 : 1,
            }}
          >
            <Fingerprint style={{ width: 16, height: 16 }} />
            {adding ? 'Wird erstellt…' : 'Passkey einrichten'}
          </button>
        ) : (
          /* Weitere Passkeys: dezent (nicht mit dem CTA konkurrieren). */
          <button
            onClick={handleAdd}
            disabled={adding}
            style={{
              alignSelf: 'flex-start', display: 'inline-flex', alignItems: 'center', gap: 8,
              padding: '8px 16px', borderRadius: 'var(--r-sm)', border: '1px solid var(--border-2)',
              background: 'var(--bg-1)', fontSize: 13, fontWeight: 500, color: 'var(--fg-2)',
              cursor: adding ? 'wait' : 'pointer', opacity: adding ? 0.6 : 1,
            }}
          >
            <Plus style={{ width: 15, height: 15 }} />
            {adding ? 'Wird erstellt…' : 'Weiteren Passkey hinzufügen'}
          </button>
        )}
      </div>
    </div>
  );
}
