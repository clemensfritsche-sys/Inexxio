'use client';

/**
 * **Sicherheit** – der letzte Abschnitt der Konto-Seite: die Anmelde-E-Mail, die Passkeys und
 * das Abmelden.
 *
 * **Die Anmelde-E-Mail ändern** (für jede Anmeldeart, auch Google): zuerst fragt der Server,
 * ob die Adresse frei ist (`api.checkMyEmail`, dieselbe Regel wie beim Übernehmen), dann
 * schickt Firebase den Bestätigungslink an die NEUE Adresse – erst der Klick ändert sie.
 * Verlangt Firebase eine frische Anmeldung, geht das mit Google im Pop-up; sonst meldet man
 * sich kurz neu an und kommt mit der gemerkten Adresse hierher zurück.
 */

import { useEffect, useState } from 'react';
import { LogOut, Mail, Pencil } from 'lucide-react';
import type { UserProfile } from '@/types';
import { api } from '@/lib/api';
import { logout, reauthenticate, updateEmailAddress } from '@/lib/firebase';
import { KtField, KtSection } from '@/components/form/kt-section';
import { PasskeysCard } from './passkeys-card';

/** Die neue Adresse über eine Neuanmeldung hinweg (der Magic Link öffnet oft einen neuen Tab). */
const PENDING = 'inexxio_new_email';

type Step = 'idle' | 'form' | 'reauth' | 'sent';

function reason(e: unknown): string {
  const code = (e as { code?: string }).code;
  if (code === 'auth/email-already-in-use') return 'Diese Adresse gehört bereits zu einem anderen Konto.';
  if (code === 'auth/invalid-email' || code === 'auth/invalid-new-email') return 'Das ist keine gültige E-Mail-Adresse.';
  if (code === 'auth/too-many-requests') return 'Zu viele Versuche – bitte in ein paar Minuten noch einmal.';
  if (code === 'auth/popup-closed-by-user' || code === 'auth/cancelled-popup-request') return 'Die Anmeldung wurde abgebrochen.';
  return e instanceof Error ? e.message : 'Das hat nicht geklappt.';
}

export function SecuritySection({ profile }: { profile: UserProfile }) {
  const [step, setStep] = useState<Step>('idle');
  const [email, setEmail] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  // Zurück von der Neuanmeldung: die gemerkte Adresse steht wieder im Feld.
  useEffect(() => {
    const pending = localStorage.getItem(PENDING);
    if (pending) { localStorage.removeItem(PENDING); setEmail(pending); setStep('form'); }
  }, []);

  function cancel() { setStep('idle'); setError(''); setEmail(''); }

  async function send(retried = false): Promise<void> {
    try {
      await updateEmailAddress(email.trim());
      setStep('sent');
    } catch (e) {
      if ((e as { code?: string }).code !== 'auth/requires-recent-login' || retried) throw e;
      if (await reauthenticate() === 'done') return send(true);
      setStep('reauth');
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (busy || !email.trim()) return;
    setBusy(true); setError('');
    try {
      await api.checkMyEmail(email.trim());
      await send();
    } catch (err) {
      setError(reason(err));
    } finally {
      setBusy(false);
    }
  }

  async function signInAgain() {
    localStorage.setItem(PENDING, email.trim());
    await logout();
    // Hart navigiert, wie jeder Weg zur Anmeldung (frontend/CLAUDE.md «Anmelden»): nach dem
    // Abmelden soll kein Zustand der alten Sitzung im Speicher bleiben.
    // eslint-disable-next-line @next/next/no-location-assign-relative-destination
    window.location.assign(`/login?from=${encodeURIComponent('/konto#sicherheit')}`);
  }

  return (
    <KtSection id="sicherheit" title="Sicherheit"
      text="Ohne Passwort. Sie melden sich per E-Mail-Link, mit Passkey oder mit Google an.">
      <div className="kt-card">
        <span className="kt-card-ic"><Mail aria-hidden /></span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span className="kt-card-tag">Anmelde-E-Mail</span>
          <div className="kt-card-text">{profile.email}</div>

          {step === 'form' && (
            <form onSubmit={submit} style={{ display: 'grid', gap: 12, marginTop: 16 }}>
              <KtField id="kt-new-mail" label="Neue E-Mail-Adresse" type="email" value={email}
                onChange={setEmail} placeholder="name@beispiel.ch" autoComplete="email" />
              <p className="kt-note">
                Wir schicken einen Bestätigungslink an die <strong>neue</strong> Adresse. Erst
                mit dem Klick gilt sie – danach melden Sie sich mit ihr an.
              </p>
              {error && <p className="kt-note is-error">{error}</p>}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="submit" className="kt-pill" disabled={busy || !email.trim()}>
                  {busy ? 'Wird gesendet …' : 'Link senden'}
                </button>
                <button type="button" className="kt-pill kt-pill--ghost" onClick={cancel}>Abbrechen</button>
              </div>
            </form>
          )}

          {step === 'reauth' && (
            <div style={{ display: 'grid', gap: 12, marginTop: 16 }}>
              <p className="kt-note">
                Zur Sicherheit braucht es eine frische Anmeldung. Danach kommen Sie hierher
                zurück, «{email.trim()}» steht schon im Feld.
              </p>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" className="kt-pill" onClick={() => void signInAgain()}>Neu anmelden</button>
                <button type="button" className="kt-pill kt-pill--ghost" onClick={cancel}>Abbrechen</button>
              </div>
            </div>
          )}

          {step === 'sent' && (
            <p className="kt-note is-ok" style={{ marginTop: 10 }}>
              Link an «{email.trim()}» gesendet. Bis Sie ihn anklicken, gilt «{profile.email}».
            </p>
          )}
        </div>
        {step === 'idle' && (
          <button type="button" className="kt-round" title="Ändern" aria-label="E-Mail-Adresse ändern"
            onClick={() => setStep('form')}>
            <Pencil size={16} />
          </button>
        )}
      </div>

      <PasskeysCard />

      <a className="kt-out" href="/abmelden"><LogOut size={18} aria-hidden />Abmelden</a>
    </KtSection>
  );
}
