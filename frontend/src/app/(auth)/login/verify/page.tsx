'use client';

import { useEffect, useState } from 'react';
import { AlertCircle, ArrowRight, CheckCircle2, Loader2 } from 'lucide-react';
import { completeMagicLink } from '@/lib/firebase';
import { api } from '@/lib/api';
import { goTo, loginTarget } from '@/lib/login-target';
import { cachedRole, rememberRole } from '@/lib/account-cache';
import { errorText } from '@/lib/use-action';
import { useDialog } from '@/lib/use-dialog';

/** Rolle holen und das Ziel bestimmen – dieselbe Antwort wie Dialog und Route. */
async function finish(): Promise<string> {
  let role: string | null = null;
  try {
    role = (await api.getMe()).role;
    rememberRole(role);
  } catch {
    role = cachedRole(); // wird beim nächsten Laden nachgeholt
  }
  return loginTarget(role);
}

export default function VerifyPage() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error' | 'needs-email'>('loading');
  const [error, setError] = useState('');
  const [email, setEmail] = useState('');
  // Fokus hinein, Tab im Kreis – das eine Verhalten (`lib/use-dialog`); schliessen gibt es hier nicht.
  const dialog = useDialog(null);

  useEffect(() => {
    async function verify() {
      try {
        const user = await completeMagicLink();
        if (!user) {
          goTo('/login');
          return;
        }
        const target = await finish();
        setStatus('success');
        setTimeout(() => goTo(target), 1500);
      } catch (err: unknown) {
        const msg = errorText(err, '');
        if (msg.includes('E-Mail-Adresse nicht gefunden')) {
          setStatus('needs-email');
        } else {
          setError(msg || 'Anmeldung fehlgeschlagen. Bitte erneut versuchen.');
          setStatus('error');
        }
      }
    }
    verify();
  }, []);

  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('loading');
    try {
      localStorage.setItem('emailForSignIn', email);
      if (await completeMagicLink()) {
        const target = await finish();
        setStatus('success');
        setTimeout(() => goTo(target), 1500);
      }
    } catch (err: unknown) {
      setError(errorText(err, 'Anmeldung fehlgeschlagen.'));
      setStatus('error');
    }
  }

  // ►►► **Dieselbe Lightbox wie der Anmeldedialog** (`.ix-login-scrim` + `.ix-login-card`,
  // `components/auth/login-dialog.tsx`) – die Rückkehr vom Link ist derselbe Vorgang. ◄◄◄
  return (
    <div ref={dialog.ref} onKeyDown={dialog.onKeyDown}
      className="ix-login-scrim" role="dialog" aria-modal="true" aria-labelledby="ix-verify-title">
      <div className="ix-login-card">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src="/brand/inexxio-ehemals-hs-steiner.svg" alt="INEXXIO (ehemals HS Steiner)" className="ix-verify-logo" />

        {status === 'loading' && (
          <>
            <Loader2 className="animate-spin ix-verify-icon" style={{ color: 'var(--inexxio-red)' }} aria-hidden />
            <h1 id="ix-verify-title">Einen Moment</h1>
            <p className="ix-login-sub">Die Anmeldung wird verarbeitet.</p>
          </>
        )}

        {status === 'success' && (
          <>
            <CheckCircle2 className="ix-verify-icon" style={{ color: 'var(--success)' }} aria-hidden />
            <h1 id="ix-verify-title">Angemeldet.</h1>
            <p className="ix-login-sub">Sie werden weitergeleitet …</p>
          </>
        )}

        {status === 'error' && (
          <>
            <AlertCircle className="ix-verify-icon" style={{ color: 'var(--inexxio-red)' }} aria-hidden />
            <h1 id="ix-verify-title">Anmeldung fehlgeschlagen</h1>
            <p className="ix-login-sub" role="alert">{error}</p>
            <a href="/login" className="ix-login-link">Zurück zur Anmeldung</a>
          </>
        )}

        {status === 'needs-email' && (
          <>
            <h1 id="ix-verify-title">E-Mail bestätigen</h1>
            <p className="ix-login-sub">
              Bitte geben Sie Ihre E-Mail-Adresse ein, um die Anmeldung abzuschliessen.
            </p>
            <form onSubmit={handleEmailSubmit} className="ix-login-field">
              <label htmlFor="verify-email" className="sr-only">E-Mail-Adresse</label>
              <input
                id="verify-email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="E-Mail-Adresse"
                autoComplete="email"
                autoFocus
              />
              <button type="submit" className="ix-login-go" disabled={!email.trim()} aria-label="Anmelden">
                <ArrowRight aria-hidden />
              </button>
            </form>
          </>
        )}
      </div>
    </div>
  );
}
