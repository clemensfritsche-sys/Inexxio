'use client';

import { useEffect, useState } from 'react';
import { Plus, Trash2, Fingerprint } from 'lucide-react';
import { api } from '@/lib/api';
import { registerPasskey, passkeySupported, isPasskeyCancellation } from '@/lib/passkey';
import type { Passkey } from '@/types';
import { when } from '@/lib/when';
import { errorText } from '@/lib/use-action';
import { useQuery, useQueryClient } from '@tanstack/react-query';

// Datum und Uhrzeit stehen im Haus an EINER Stelle (`lib/when`, Testnotiz #992).
const formatDate = (iso: string | null) => when(iso);

export function PasskeysCard() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ['me', 'passkeys'],
    queryFn: () => api.listPasskeys(),
    meta: { what: 'Passkeys' },
  });
  const passkeys: Passkey[] = query.data ?? [];
  const loading = query.isPending;
  const setPasskeys = (next: Passkey[] | ((rows: Passkey[]) => Passkey[])) =>
    qc.setQueryData<Passkey[]>(['me', 'passkeys'], (rows = []) =>
      typeof next === 'function' ? next(rows) : next);
  const [supported, setSupported] = useState(true);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { setSupported(passkeySupported()); }, []);

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
        setError(errorText(err, 'Passkey konnte nicht hinzugefügt werden.'));
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
      setError(errorText(err, 'Passkey konnte nicht entfernt werden.'));
    }
  }

  const empty = !loading && passkeys.length === 0;

  // Jeder Passkey eine graue Karte wie die Adressen; darunter der eine Knopf zum Hinzufügen.
  return (
    <>
      {error && <p className="kt-note is-error">{error}</p>}
      {loading ? (
        <p className="kt-note">Passkeys werden geladen…</p>
      ) : empty ? (
        <div className="kt-card">
          <span className="kt-card-ic is-red"><Fingerprint aria-hidden /></span>
          <div className="kt-card-text" style={{ flex: 1 }}>
            Noch kein Passkey
            <small>Melden Sie sich mit Face&nbsp;ID, Touch&nbsp;ID oder Windows&nbsp;Hello an – ohne E-Mail-Link. Ein Passkey verlässt Ihr Gerät nie.</small>
          </div>
        </div>
      ) : passkeys.map((pk) => (
        <div key={pk.id} className="kt-card">
          <span className="kt-card-ic is-red"><Fingerprint aria-hidden /></span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <span className="kt-card-tag">Passkey{pk.backed_up ? ' · synchronisiert' : ''}</span>
            <div className="kt-card-text">
              {pk.device_name || 'Passkey'}
              <small>Hinzugefügt {formatDate(pk.created_at)}{pk.last_used_at ? ` · zuletzt ${formatDate(pk.last_used_at)}` : ''}</small>
            </div>
          </div>
          <button type="button" className="kt-round" onClick={() => handleDelete(pk.id)} aria-label="Passkey entfernen" title="Passkey entfernen">
            <Trash2 size={16} />
          </button>
        </div>
      ))}
      {!supported ? (
        <p className="kt-note">Dieser Browser unterstützt keine Passkeys. Bitte einen aktuellen Browser verwenden.</p>
      ) : empty ? (
        /* Erster Passkey: der eine laute Akzent. */
        <button type="button" className="kt-pill" onClick={handleAdd} disabled={adding} style={{ alignSelf: 'flex-start' }}>
          <Fingerprint size={16} aria-hidden />{adding ? 'Wird erstellt…' : 'Passkey einrichten'}
        </button>
      ) : !loading && (
        <button type="button" className="kt-add" onClick={handleAdd} disabled={adding}>
          <Plus size={16} aria-hidden />{adding ? 'Wird erstellt…' : 'Passkey hinzufügen'}
        </button>
      )}
    </>
  );
}
