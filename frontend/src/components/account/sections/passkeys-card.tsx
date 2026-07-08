'use client';

import { useEffect, useState } from 'react';
import { KeyRound, Plus, Trash2, ShieldCheck, Info, AlertCircle, Fingerprint } from 'lucide-react';
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
  const [showNameInput, setShowNameInput] = useState(false);
  const [deviceName, setDeviceName] = useState('');
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
      const created = await registerPasskey(deviceName.trim() || undefined);
      setPasskeys((prev) => [created, ...prev]);
      setDeviceName('');
      setShowNameInput(false);
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

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <KeyRound style={{ width: 16, height: 16, color: '#64748b' }} />
        <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Passkeys</h2>
      </div>

      <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 16px', background: '#F8FAFC', borderRadius: 8, border: '1px solid #E2E8F0' }}>
          <Fingerprint style={{ width: 16, height: 16, color: '#64748b', flexShrink: 0, marginTop: 1 }} />
          <p style={{ fontSize: 13, color: '#475569', margin: 0, lineHeight: 1.55 }}>
            Melden Sie sich künftig ohne E-Mail-Link an – mit Face ID, Touch ID, Windows Hello oder
            einem Sicherheitsschlüssel. Ein Passkey ist an dieses Gerät gebunden und verlässt es nie.
          </p>
        </div>

        {error && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 14px', background: '#FEF2F2', borderRadius: 8, border: '1px solid #FCA5A5' }}>
            <AlertCircle style={{ width: 14, height: 14, color: '#dc2626', flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 13, color: '#dc2626', margin: 0 }}>{error}</p>
          </div>
        )}

        {loading ? (
          <p style={{ fontSize: 13, color: '#94a3b8', margin: 0 }}>Wird geladen…</p>
        ) : passkeys.length === 0 ? (
          <p style={{ fontSize: 13, color: '#64748b', margin: 0 }}>
            Noch kein Passkey hinterlegt.
          </p>
        ) : (
          <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>
            {passkeys.map((pk) => (
              <li
                key={pk.id}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12, padding: '12px 14px',
                  border: '1px solid #E2E8F0', borderRadius: 8,
                }}
              >
                <ShieldCheck style={{ width: 18, height: 18, color: '#16a34a', flexShrink: 0 }} />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <p style={{ fontSize: 14, fontWeight: 600, color: '#0F172A', margin: 0 }}>
                    {pk.device_name || 'Passkey'}
                  </p>
                  <p style={{ fontSize: 12, color: '#94a3b8', margin: '2px 0 0' }}>
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
                    width: 32, height: 32, borderRadius: 8, border: '1px solid #E2E8F0',
                    background: '#fff', color: '#dc2626', cursor: 'pointer', flexShrink: 0,
                  }}
                >
                  <Trash2 style={{ width: 15, height: 15 }} />
                </button>
              </li>
            ))}
          </ul>
        )}

        {!supported ? (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 14px', background: '#F0F9FF', borderRadius: 8, border: '1px solid #BAE6FD' }}>
            <Info style={{ width: 14, height: 14, color: '#0284c7', flexShrink: 0, marginTop: 1 }} />
            <p style={{ fontSize: 12, color: '#0369a1', margin: 0 }}>
              Dieser Browser unterstützt keine Passkeys. Bitte einen aktuellen Browser verwenden.
            </p>
          </div>
        ) : showNameInput ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <input
              type="text"
              value={deviceName}
              onChange={(e) => setDeviceName(e.target.value)}
              placeholder="Gerätename (z. B. «iPhone», optional)"
              maxLength={80}
              autoFocus
              onKeyDown={(e) => { if (e.key === 'Enter') handleAdd(); }}
              style={{
                width: '100%', padding: '10px 14px', borderRadius: 8, border: '1px solid #E2E8F0',
                fontSize: 14, color: '#0F172A', outline: 'none',
              }}
            />
            <div style={{ display: 'flex', gap: 10 }}>
              <button
                onClick={handleAdd}
                disabled={adding}
                style={{
                  padding: '8px 18px', borderRadius: 8, border: 'none', background: '#E51A14',
                  color: '#fff', fontSize: 13, fontWeight: 600, cursor: adding ? 'wait' : 'pointer',
                  opacity: adding ? 0.6 : 1,
                }}
              >
                {adding ? 'Wird erstellt…' : 'Passkey erstellen'}
              </button>
              <button
                type="button"
                onClick={() => { setShowNameInput(false); setDeviceName(''); setError(''); }}
                style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer' }}
              >
                Abbrechen
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setShowNameInput(true)}
            style={{
              alignSelf: 'flex-start', display: 'flex', alignItems: 'center', gap: 8,
              padding: '8px 16px', borderRadius: 8, border: '1px solid #E2E8F0', background: '#fff',
              fontSize: 13, fontWeight: 500, color: '#374151', cursor: 'pointer',
            }}
          >
            <Plus style={{ width: 15, height: 15 }} />
            Passkey hinzufügen
          </button>
        )}
      </div>
    </div>
  );
}
