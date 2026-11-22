'use client';

/**
 * **Sicherheit** – der letzte Abschnitt der Konto-Seite: die Anmelde-E-Mail, die Passkeys, für
 * Personal die Verbindungen mit Claude (`components/erp/person-access` – dasselbe Bauteil wie die
 * Karte «Zugang» am ERP-Datensatz) und das Abmelden.
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
import { ClaudeList, PasskeyList } from '@/components/erp/person-access';
import { isStaff } from '@/lib/record-status';
import { errorText, useAction } from '@/lib/use-action';
import { t as tr, useT, withLang } from '@/lib/lang';

/** Die neue Adresse über eine Neuanmeldung hinweg (der Magic Link öffnet oft einen neuen Tab). */
const PENDING = 'inexxio_new_email';

type Step = 'idle' | 'form' | 'reauth' | 'sent';

function reason(e: unknown): string {
  const code = (e as { code?: string }).code;
  if (code === 'auth/email-already-in-use') return tr('Diese Adresse gehört bereits zu einem anderen Konto.');
  if (code === 'auth/invalid-email' || code === 'auth/invalid-new-email') return tr('Das ist keine gültige E-Mail-Adresse.');
  if (code === 'auth/too-many-requests') return tr('Zu viele Versuche – bitte in ein paar Minuten noch einmal.');
  if (code === 'auth/popup-closed-by-user' || code === 'auth/cancelled-popup-request') return tr('Die Anmeldung wurde abgebrochen.');
  return errorText(e, tr('Das hat nicht geklappt.'));
}

export function SecuritySection({ profile }: { profile: UserProfile }) {
  const [step, setStep] = useState<Step>('idle');
  const [email, setEmail] = useState('');
  const { busy, error, setError, run } = useAction();
  const t = useT();

  // Zurück von der Neuanmeldung: die gemerkte Adresse steht wieder im Feld.
  useEffect(() => {
    const pending = localStorage.getItem(PENDING);
    if (pending) { localStorage.removeItem(PENDING); setEmail(pending); setStep('form'); }
  }, []);

  function cancel() { setStep('idle'); setError(null); setEmail(''); }

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
    await run(async () => {
      await api.checkMyEmail(email.trim());
      await send();
    }, (err) => setError(reason(err)));
  }

  async function signInAgain() {
    localStorage.setItem(PENDING, email.trim());
    await logout();
    // Hart navigiert, wie jeder Weg zur Anmeldung (frontend/CLAUDE.md «Anmelden»): nach dem
    // Abmelden soll kein Zustand der alten Sitzung im Speicher bleiben.
    window.location.assign(withLang(`/login?from=${encodeURIComponent(withLang('/konto#sicherheit'))}`));
  }

  return (
    <KtSection id="sicherheit" title={t('Sicherheit')}
      text={t('Ohne Passwort. Sie melden sich per E-Mail-Link, mit Passkey oder mit Google an.')}>
      <div className="kt-card">
        <span className="kt-card-ic"><Mail aria-hidden /></span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <span className="kt-card-tag">{t('Anmelde-E-Mail')}</span>
          <div className="kt-card-text">{profile.email}</div>

          {step === 'form' && (
            <form onSubmit={submit} style={{ display: 'grid', gap: 12, marginTop: 16 }}>
              <KtField id="kt-new-mail" name="email" label={t('Neue E-Mail-Adresse')} type="email" value={email}
                onChange={setEmail} placeholder={t('name@beispiel.ch')} autoComplete="email" />
              <p className="kt-note">
                {t('Wir schicken einen Bestätigungslink an die neue Adresse. Erst mit dem Klick gilt sie – danach melden Sie sich mit ihr an.')}
              </p>
              {error && <p className="kt-note is-error">{error}</p>}
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="submit" className="kt-pill" disabled={busy || !email.trim()}>
                  {busy ? t('Wird gesendet …') : t('Link senden')}
                </button>
                <button type="button" className="kt-pill kt-pill--ghost" onClick={cancel}>{t('Abbrechen')}</button>
              </div>
            </form>
          )}

          {step === 'reauth' && (
            <div style={{ display: 'grid', gap: 12, marginTop: 16 }}>
              <p className="kt-note">
                {t('Zur Sicherheit braucht es eine frische Anmeldung. Danach kommen Sie hierher zurück, «{mail}» steht schon im Feld.', { mail: email.trim() })}
              </p>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button type="button" className="kt-pill" onClick={() => void signInAgain()}>{t('Neu anmelden')}</button>
                <button type="button" className="kt-pill kt-pill--ghost" onClick={cancel}>{t('Abbrechen')}</button>
              </div>
            </div>
          )}

          {step === 'sent' && (
            <p className="kt-note is-ok" style={{ marginTop: 10 }}>
              {t('Link an «{neu}» gesendet. Bis Sie ihn anklicken, gilt «{alt}».', { neu: email.trim(), alt: profile.email })}
            </p>
          )}
        </div>
        {step === 'idle' && (
          <button type="button" className="kt-round" data-tip={t('Ändern')} aria-label={t('E-Mail-Adresse ändern')}
            onClick={() => setStep('form')}>
            <Pencil size={16} />
          </button>
        )}
      </div>

      {/* Dasselbe Bauteil wie am ERP-Datensatz («Zugang») – hier mit dem Einrichten. */}
      <PasskeyList owner={null} cards />

      {isStaff(profile.role) && <ClaudeList owner={null} cards />}

      <a className="kt-out" href={withLang('/abmelden')}><LogOut size={18} aria-hidden />{t('Abmelden')}</a>
    </KtSection>
  );
}
