'use client';

import { useState } from 'react';
import { Shield, Mail, AlertCircle, CheckCircle2 } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field } from '../field';
import { auth, updateEmailAddress } from '@/lib/firebase';

interface Props {
  profile: UserProfile;
}

export function SecuritySection({ profile }: Props) {
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [confirmEmail, setConfirmEmail] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const isGoogleUser = auth?.currentUser?.providerData?.some((p) => p.providerId === 'google.com');

  async function handleEmailChange(e: React.FormEvent) {
    e.preventDefault();
    if (newEmail !== confirmEmail) {
      setError('Die E-Mail-Adressen stimmen nicht überein.');
      return;
    }
    if (newEmail === profile.email) {
      setError('Die neue Adresse ist identisch mit der aktuellen.');
      return;
    }
    setSending(true);
    setError('');
    try {
      await updateEmailAddress(newEmail);
      setSent(true);
      setShowEmailForm(false);
      setNewEmail('');
      setConfirmEmail('');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Fehler beim Senden');
    } finally {
      setSending(false);
    }
  }

  const lastLogin = profile.last_login_at
    ? new Date(profile.last_login_at).toLocaleString('de-CH')
    : '—';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Email */}
      <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
          <Mail style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Anmelde-E-Mail</h2>
        </div>

        <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 16 }}>
          {sent && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px', background: '#F0FDF4', border: '1px solid #BBF7D0', borderRadius: 8 }}>
              <CheckCircle2 style={{ width: 16, height: 16, color: '#16a34a', flexShrink: 0 }} />
              <p style={{ fontSize: 13, color: '#15803d', margin: 0 }}>
                Bestätigungslink gesendet. Klicke den Link in der neuen Adresse — danach melde dich erneut an.
              </p>
            </div>
          )}

          <Field label="Aktuelle E-Mail-Adresse" value={profile.email} readOnly />

          {isGoogleUser ? (
            <div style={{ padding: '12px 16px', background: '#F8FAFC', borderRadius: 8, border: '1px solid #E2E8F0' }}>
              <p style={{ fontSize: 13, color: '#64748b', margin: 0 }}>
                Deine E-Mail-Adresse wird über dein Google-Konto verwaltet und kann hier nicht geändert werden.
              </p>
            </div>
          ) : (
            <>
              {!showEmailForm ? (
                <button
                  onClick={() => setShowEmailForm(true)}
                  style={{
                    alignSelf: 'flex-start', padding: '8px 16px', borderRadius: 8,
                    border: '1px solid #E2E8F0', background: '#fff', fontSize: 13,
                    fontWeight: 500, color: '#374151', cursor: 'pointer',
                  }}
                >
                  E-Mail-Adresse ändern
                </button>
              ) : (
                <form onSubmit={handleEmailChange} style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                  <Field
                    label="Neue E-Mail-Adresse"
                    value={newEmail}
                    onChange={setNewEmail}
                    type="email"
                    placeholder="neue@email.ch"
                  />
                  <Field
                    label="Neue E-Mail bestätigen"
                    value={confirmEmail}
                    onChange={setConfirmEmail}
                    type="email"
                    placeholder="neue@email.ch"
                  />
                  {error && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 14px', background: '#FEF2F2', borderRadius: 8, border: '1px solid #FCA5A5' }}>
                      <AlertCircle style={{ width: 14, height: 14, color: '#dc2626', flexShrink: 0 }} />
                      <p style={{ fontSize: 13, color: '#dc2626', margin: 0 }}>{error}</p>
                    </div>
                  )}
                  <div style={{ display: 'flex', gap: 10 }}>
                    <button
                      type="submit"
                      disabled={sending || !newEmail}
                      style={{
                        padding: '8px 18px', borderRadius: 8, border: 'none',
                        background: '#E51A14', color: '#fff', fontSize: 13,
                        fontWeight: 600, cursor: sending ? 'wait' : 'pointer',
                        opacity: sending || !newEmail ? 0.6 : 1,
                      }}
                    >
                      {sending ? 'Wird gesendet…' : 'Bestätigungslink senden'}
                    </button>
                    <button
                      type="button"
                      onClick={() => { setShowEmailForm(false); setError(''); setNewEmail(''); setConfirmEmail(''); }}
                      style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid #E2E8F0', background: '#fff', fontSize: 13, color: '#374151', cursor: 'pointer' }}
                    >
                      Abbrechen
                    </button>
                  </div>
                  <p style={{ fontSize: 12, color: '#94a3b8', margin: 0 }}>
                    Es wird ein Bestätigungslink an die neue Adresse gesendet. Die Änderung wird nach Klick auf den Link und erneutem Anmelden wirksam.
                  </p>
                </form>
              )}
            </>
          )}
        </div>
      </div>

      {/* Session info */}
      <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
          <Shield style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Sitzungsinformationen</h2>
        </div>
        <div style={{ padding: 24, display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #F1F5F9' }}>
            <span style={{ fontSize: 14, color: '#374151' }}>Letzte Anmeldung</span>
            <span style={{ fontSize: 14, color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>{lastLogin}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 0' }}>
            <span style={{ fontSize: 14, color: '#374151' }}>Konto erstellt</span>
            <span style={{ fontSize: 14, color: '#64748b', fontVariantNumeric: 'tabular-nums' }}>
              {profile.created_at ? new Date(profile.created_at).toLocaleDateString('de-CH') : '—'}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
