'use client';

/**
 * **Sicherheit** – der letzte Abschnitt der Konto-Seite: die Anmelde-E-Mail (ändern per
 * Bestätigungslink an die NEUE Adresse; bei Google verwaltet Google sie), die Passkeys und
 * das Abmelden.
 */

import { useState } from 'react';
import { LogOut, Mail, Pencil } from 'lucide-react';
import type { UserProfile } from '@/types';
import { auth, updateEmailAddress } from '@/lib/firebase';
import { KtField, KtSection } from '../kt-section';
import { PasskeysCard } from './passkeys-card';

export function SecuritySection({ profile }: { profile: UserProfile }) {
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [newEmail, setNewEmail] = useState('');
  const [confirmEmail, setConfirmEmail] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const isGoogleUser = auth?.currentUser?.providerData?.some((p) => p.providerId === 'google.com');

  function cancel() {
    setShowEmailForm(false); setError(''); setNewEmail(''); setConfirmEmail('');
  }

  async function handleEmailChange(e: React.FormEvent) {
    e.preventDefault();
    if (newEmail !== confirmEmail) { setError('Die E-Mail-Adressen stimmen nicht überein.'); return; }
    if (newEmail === profile.email) { setError('Die neue Adresse ist identisch mit der aktuellen.'); return; }
    setSending(true);
    setError('');
    try {
      await updateEmailAddress(newEmail);
      setSent(true);
      cancel();
    } catch (e: unknown) {
      const code = (e as { code?: string }).code;
      if (code === 'auth/requires-recent-login') {
        setError('Aus Sicherheitsgründen ist eine erneute Anmeldung nötig. Bitte abmelden und wieder anmelden.');
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
    <KtSection id="sicherheit" title="Sicherheit"
      text="Ohne Passwort. Sie melden sich per E-Mail-Link, mit Passkey oder mit Google an.">
      <div className="kt-card">
        <span className="kt-card-ic"><Mail aria-hidden /></span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span className="kt-card-tag">Anmelde-E-Mail</span>
          <div className="kt-card-text">
            {profile.email}
            {isGoogleUser && <small>Wird über Ihr Google-Konto verwaltet.</small>}
          </div>
          {showEmailForm && (
            <form onSubmit={handleEmailChange} style={{ display: 'grid', gap: 12, marginTop: 16 }}>
              <KtField id="kt-new-mail" label="Neue E-Mail-Adresse" type="email" value={newEmail} onChange={setNewEmail} placeholder="neue@email.ch" />
              <KtField id="kt-new-mail2" label="Neue E-Mail bestätigen" type="email" value={confirmEmail} onChange={setConfirmEmail} placeholder="neue@email.ch" />
              <p className="kt-note">Der Bestätigungslink geht an die <strong>neue</strong> Adresse. Nach dem Klick und erneutem Anmelden gilt sie.</p>
              {error && <p className="kt-note is-error">{error}</p>}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="submit" className="kt-pill" disabled={sending || !newEmail}>
                  {sending ? 'Wird gesendet…' : 'Bestätigungslink senden'}
                </button>
                <button type="button" className="kt-pill kt-pill--ghost" onClick={cancel}>Abbrechen</button>
              </div>
            </form>
          )}
          {sent && <p className="kt-note is-ok" style={{ marginTop: 10 }}>Bestätigungslink gesendet – bitte die neue Adresse prüfen.</p>}
        </div>
        {!isGoogleUser && !showEmailForm && (
          <button type="button" className="kt-round" title="Ändern" aria-label="E-Mail-Adresse ändern"
            onClick={() => { setShowEmailForm(true); setSent(false); }}>
            <Pencil size={16} />
          </button>
        )}
      </div>

      <PasskeysCard />

      <a className="kt-out" href="/abmelden"><LogOut size={18} aria-hidden />Abmelden</a>
    </KtSection>
  );
}
