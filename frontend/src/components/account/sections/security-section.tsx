'use client';

import { useState } from 'react';
import { Mail, AlertCircle, CheckCircle2, Info } from 'lucide-react';
import type { UserProfile } from '@/types';
import { Field } from '@/components/form/field';
import { Card } from '@/components/erp/fields';
import { auth, updateEmailAddress } from '@/lib/firebase';
import { PasskeysCard } from './passkeys-card';

interface Props {
  profile: UserProfile;
}

/** Der Rahmen einer Hinweisfläche: ihre Ampelfarbe, aufgehellt – kein eigener Ton. */
const TINT = (token: string) => `color-mix(in srgb, var(${token}) 35%, transparent)`;

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
      const code = (e as { code?: string }).code;
      if (code === 'auth/requires-recent-login') {
        setError('Aus Sicherheitsgründen ist eine erneute Anmeldung erforderlich. Bitte melde dich ab und anschliessend erneut an.');
      } else if (code === 'auth/email-already-in-use') {
        setError('Diese E-Mail-Adresse ist bereits mit einem anderen Konto verknüpft.');
      } else {
        setError(e instanceof Error ? e.message : 'Fehler beim Senden');
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {/* Email */}
      <Card icon={Mail} title="Anmelde-E-Mail">
        {sent && (
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 16px', background: 'var(--success-bg)', border: `1px solid ${TINT('--success')}`, borderRadius: 8 }}>
            <CheckCircle2 style={{ width: 16, height: 16, color: 'var(--success)', flexShrink: 0, marginTop: 1 }} />
            <div>
              <p style={{ fontSize: 13, color: 'var(--success)', margin: 0, fontWeight: 600 }}>
                Bestätigungslink gesendet
              </p>
              <p style={{ fontSize: 13, color: 'var(--success)', margin: '4px 0 0' }}>
                Bitte überprüfe deine neue E-Mail-Adresse und klicke auf den Bestätigungslink.
                Danach kannst du dich mit der neuen Adresse anmelden.
              </p>
            </div>
          </div>
        )}

        <Field label="Aktuelle E-Mail-Adresse" value={profile.email} readOnly />

        {isGoogleUser ? (
          <p style={{ fontSize: 12, color: 'var(--fg-4)', margin: 0 }}>
            Wird über dein Google-Konto verwaltet.
          </p>
        ) : (
          <>
            {!showEmailForm ? (
              <button
                onClick={() => setShowEmailForm(true)}
                style={{
                  alignSelf: 'flex-start', padding: '8px 16px', borderRadius: 8,
                  border: '1px solid var(--border-1)', background: 'var(--bg-1)', fontSize: 13,
                  fontWeight: 500, color: 'var(--fg-2)', cursor: 'pointer',
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
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 14px', background: 'var(--danger-bg)', borderRadius: 8, border: `1px solid ${TINT('--danger')}` }}>
                    <AlertCircle style={{ width: 14, height: 14, color: 'var(--danger)', flexShrink: 0, marginTop: 1 }} />
                    <p style={{ fontSize: 13, color: 'var(--danger)', margin: 0 }}>{error}</p>
                  </div>
                )}
                <div style={{ display: 'flex', gap: 10 }}>
                  <button
                    type="submit"
                    disabled={sending || !newEmail}
                    style={{
                      padding: '8px 18px', borderRadius: 8, border: 'none',
                      background: 'var(--inexxio-red)', color: 'var(--fg-on-red)', fontSize: 13,
                      fontWeight: 600, cursor: sending ? 'wait' : 'pointer',
                      opacity: sending || !newEmail ? 0.6 : 1,
                    }}
                  >
                    {sending ? 'Wird gesendet…' : 'Bestätigungslink senden'}
                  </button>
                  <button
                    type="button"
                    onClick={() => { setShowEmailForm(false); setError(''); setNewEmail(''); setConfirmEmail(''); }}
                    style={{ padding: '8px 16px', borderRadius: 8, border: '1px solid var(--border-1)', background: 'var(--bg-1)', fontSize: 13, color: 'var(--fg-2)', cursor: 'pointer' }}
                  >
                    Abbrechen
                  </button>
                </div>
                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 14px', background: 'var(--info-bg)', borderRadius: 8, border: `1px solid ${TINT('--info')}` }}>
                  <Info style={{ width: 14, height: 14, color: 'var(--info)', flexShrink: 0, marginTop: 1 }} />
                  <p style={{ fontSize: 12, color: 'var(--accent-ink)', margin: 0 }}>
                    Es wird ein Bestätigungslink an die <strong>neue</strong> Adresse gesendet.
                    Nach dem Klick auf den Link und erneutem Anmelden ist die Änderung aktiv.
                  </p>
                </div>
              </form>
            )}
          </>
        )}
      </Card>

      {/* Passkeys */}
      <PasskeysCard />

    </div>
  );
}
