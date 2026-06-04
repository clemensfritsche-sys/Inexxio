'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import type { FirebaseError } from 'firebase/app';
import { sendMagicLink, signInWithGoogle } from '@/lib/firebase';
import { api } from '@/lib/api';

type Step = 'input' | 'loading' | 'sent';

const REDIRECT_KEY = 'inexxio_login_redirect';
const ROLE_KEY = 'inexxio_user_role';

function getGoogleErrorMessage(code: string): string {
  switch (code) {
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request':
      return '';
    case 'auth/popup-blocked':
      return 'Popup wurde blockiert. Bitte erlauben Sie Popups für diese Seite und versuchen Sie es erneut.';
    case 'auth/operation-not-allowed':
      return 'Google-Anmeldung ist nicht aktiviert.';
    case 'auth/unauthorized-domain':
      return 'Diese Domain ist nicht autorisiert.';
    case 'auth/network-request-failed':
      return 'Netzwerkfehler. Bitte Internetverbindung prüfen.';
    case 'auth/web-storage-unavailable':
      return 'Browser-Speicher nicht verfügbar. Cookie-Einstellungen prüfen.';
    default:
      return code
        ? `Anmeldung fehlgeschlagen (${code}). Bitte erneut versuchen.`
        : 'Anmeldung fehlgeschlagen. Bitte erneut versuchen.';
  }
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [step, setStep] = useState<Step>('input');
  const [error, setError] = useState('');
  const [googleLoading, setGoogleLoading] = useState(false);
  const [sentEmail, setSentEmail] = useState('');
  const [variation, setVariation] = useState(1);

  useEffect(() => {
    setVariation(Math.floor(Math.random() * 3) + 1);
    // Store the ?from= param so verify page and Google login can redirect back
    const params = new URLSearchParams(window.location.search);
    const from = params.get('from');
    if (from && from !== '/login' && !from.startsWith('/login/')) {
      localStorage.setItem(REDIRECT_KEY, from);
    }
  }, []);

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setError('');
    setStep('loading');
    try {
      await sendMagicLink(email.trim());
      setSentEmail(email.trim());
      setStep('sent');
    } catch {
      setError('Fehler beim Senden. Bitte versuchen Sie es erneut.');
      setStep('input');
    }
  }

  async function handleGoogleLogin() {
    setError('');
    setGoogleLoading(true);
    try {
      const { token } = await signInWithGoogle();
      api.setToken(token);
      localStorage.setItem('inexxio_token', token);
      try {
        const profile = await api.getMe();
        localStorage.setItem(ROLE_KEY, profile.role);
      } catch {
        // role fetch failed — will be retried on next page load
      }
      const redirect = localStorage.getItem(REDIRECT_KEY) || '/';
      localStorage.removeItem(REDIRECT_KEY);
      router.push(redirect);
    } catch (err: unknown) {
      setGoogleLoading(false);
      const code = (err as FirebaseError).code ?? '';
      const msg = getGoogleErrorMessage(code);
      if (msg) setError(msg);
    }
  }

  return (
    <>
      <div className="ix-login-bg" />

      <div className="ix-login-lightbox">
        <div className={`ix-login-card ix-var-${variation}`}>

          {step === 'sent' ? (
            /* ── Success State ── */
            <div className="ix-success">
              <div className="ix-success-icon">
                <svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
                  <circle
                    className="ix-success-circle"
                    cx="60" cy="60" r="58"
                    fill="none" stroke="#E51A14" strokeWidth="1.5" opacity="0.2"
                  />
                  <polyline
                    className="ix-success-line-1"
                    points="38,65 52,78"
                    fill="none" stroke="#E51A14" strokeWidth="5"
                    strokeLinecap="round" strokeLinejoin="round"
                  />
                  <polyline
                    className="ix-success-line-2"
                    points="52,78 88,42"
                    fill="none" stroke="#E51A14" strokeWidth="5"
                    strokeLinecap="round" strokeLinejoin="round"
                  />
                </svg>
              </div>
              <h2>Überprüfen Sie Ihre E-Mail!</h2>
              <p>
                Wir haben einen Anmeldungslink an{' '}
                <strong style={{ color: 'var(--fg-2)' }}>{sentEmail}</strong>{' '}
                gesendet. Bitte prüfen Sie Ihren Posteingang.
              </p>
              <button
                className="ix-success-reset"
                onClick={() => { setStep('input'); setEmail(''); }}
              >
                Andere E-Mail verwenden
              </button>
            </div>
          ) : (
            <>
              {/* ── Header ── */}
              <div className="ix-login-header">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/logo.png" alt="Inexxio" className="ix-login-logo" />
                <h1>Anmelden</h1>
                <p>Geben Sie Ihre E-Mail-Adresse ein</p>
              </div>

              {/* ── Error ── */}
              {error && (
                <div key={error} className="ix-login-error" style={{ marginBottom: 16 }}>
                  {error}
                </div>
              )}

              {/* ── Magic Link Form ── */}
              <form onSubmit={handleMagicLink} className="ix-login-form">
                <div className="ix-form-group">
                  <label className="ix-form-label" htmlFor="email">
                    E-Mail-Adresse
                  </label>
                  <input
                    id="email"
                    type="email"
                    className="ix-email-input"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="sie@unternehmen.ch"
                    required
                    autoComplete="email"
                    autoFocus
                    disabled={step === 'loading'}
                  />
                </div>

                <button
                  type="submit"
                  className="ix-submit-btn"
                  disabled={step === 'loading' || !email.trim()}
                >
                  {step === 'loading' ? (
                    <>
                      <span className="ix-spinner" />
                      Wird gesendet…
                    </>
                  ) : (
                    'Magic Link senden'
                  )}
                </button>
              </form>

              {/* ── Google Divider ── */}
              <div className="ix-divider" style={{ marginTop: 20, marginBottom: 12 }}>
                <span>oder</span>
              </div>

              {/* ── Google Button ── */}
              <button
                onClick={handleGoogleLogin}
                disabled={googleLoading}
                className="ix-google-btn"
              >
                {googleLoading ? (
                  <span
                    className="ix-spinner"
                    style={{ borderColor: 'rgba(0,0,0,0.15)', borderTopColor: '#555' }}
                  />
                ) : (
                  <svg className="w-4 h-4" viewBox="0 0 24 24" aria-hidden>
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                )}
                Mit Google anmelden
              </button>

              {/* ── Footer ── */}
              <p className="ix-login-footer">
                Mit der Anmeldung stimmen Sie unseren{' '}
                <Link href="/agb">AGB</Link>{' '}
                und der{' '}
                <Link href="/datenschutz">Datenschutzerklärung</Link>{' '}
                zu.
                <br />
                <Link href="/" style={{ display: 'inline-block', marginTop: 6 }}>
                  ← Zurück zur Startseite
                </Link>
              </p>
            </>
          )}
        </div>
      </div>
    </>
  );
}
