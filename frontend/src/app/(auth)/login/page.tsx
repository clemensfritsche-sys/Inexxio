'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Settings2, Mail, ArrowRight, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import type { FirebaseError } from 'firebase/app';
import { sendMagicLink, signInWithGoogle, getGoogleSignInResult } from '@/lib/firebase';
import { api } from '@/lib/api';

type Step = 'input' | 'sent' | 'loading';

function getGoogleErrorMessage(code: string): string {
  switch (code) {
    case 'auth/popup-closed-by-user':
    case 'auth/cancelled-popup-request':
      return '';
    case 'auth/operation-not-allowed':
      return 'Google-Anmeldung ist nicht aktiviert. Bitte wenden Sie sich an den Administrator.';
    case 'auth/unauthorized-domain':
      return 'Diese Domain ist nicht für die Anmeldung autorisiert.';
    case 'auth/network-request-failed':
      return 'Netzwerkfehler. Bitte prüfen Sie Ihre Internetverbindung.';
    case 'auth/web-storage-unavailable':
      return 'Browser-Speicher nicht verfügbar. Bitte prüfen Sie Ihre Cookie-Einstellungen.';
    case 'auth/user-disabled':
      return 'Dieses Konto wurde deaktiviert.';
    default:
      return `Anmeldung fehlgeschlagen${code ? ` (${code})` : ''}. Bitte versuchen Sie es erneut.`;
  }
}

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [step, setStep] = useState<Step>('input');
  const [error, setError] = useState('');
  const [googleLoading, setGoogleLoading] = useState(false);

  useEffect(() => {
    const hasPendingRedirect = sessionStorage.getItem('google_redirect') === '1';
    if (hasPendingRedirect) setGoogleLoading(true);

    void (async () => {
      try {
        const result = await getGoogleSignInResult();
        sessionStorage.removeItem('google_redirect');
        if (result) {
          api.setToken(result.token);
          localStorage.setItem('inexxio_token', result.token);
          router.push('/erp');
        } else {
          setGoogleLoading(false);
        }
      } catch (err: unknown) {
        sessionStorage.removeItem('google_redirect');
        setGoogleLoading(false);
        const code = (err as FirebaseError).code ?? '';
        const msg = getGoogleErrorMessage(code);
        if (msg) setError(msg);
      }
    })();
  }, [router]);

  async function handleMagicLink(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setError('');
    setStep('loading');
    try {
      await sendMagicLink(email.trim());
      setStep('sent');
    } catch {
      setError('Fehler beim Senden des Links. Bitte versuchen Sie es erneut.');
      setStep('input');
    }
  }

  async function handleGoogleLogin() {
    setError('');
    setGoogleLoading(true);
    try {
      await signInWithGoogle();
    } catch (err: unknown) {
      sessionStorage.removeItem('google_redirect');
      setGoogleLoading(false);
      const code = (err as FirebaseError).code ?? '';
      const msg = getGoogleErrorMessage(code);
      if (msg) setError(msg);
    }
  }

  return (
    <div className="w-full max-w-md">
      {/* Card */}
      <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
        {/* Logo */}
        <div className="flex flex-col items-center mb-8">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white mb-4">
            <Settings2 className="h-6 w-6" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Willkommen zurück</h1>
          <p className="mt-1 text-sm text-slate-500">Melden Sie sich bei Inexxio an</p>
        </div>

        {/* Error */}
        {error && (
          <div className="mb-4 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0 text-red-500" />
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Sent state */}
        {step === 'sent' ? (
          <div className="text-center">
            <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-50">
              <CheckCircle2 className="h-8 w-8 text-green-600" />
            </div>
            <h2 className="text-lg font-semibold text-slate-900">Link gesendet!</h2>
            <p className="mt-2 text-sm text-slate-600">
              Wir haben einen Anmeldelink an{' '}
              <span className="font-medium text-slate-900">{email}</span> gesendet.
              Bitte prüfen Sie Ihren Posteingang.
            </p>
            <p className="mt-2 text-xs text-slate-500">
              Kein E-Mail erhalten? Prüfen Sie auch den Spam-Ordner.
            </p>
            <button
              onClick={() => { setStep('input'); setEmail(''); }}
              className="mt-4 text-sm text-blue-600 hover:underline"
            >
              Andere E-Mail verwenden
            </button>
          </div>
        ) : (
          <>
            {/* Magic Link Form */}
            <form onSubmit={handleMagicLink} className="space-y-4">
              <div>
                <label htmlFor="email" className="block text-sm font-medium text-slate-700 mb-1.5">
                  E-Mail-Adresse
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
                  <input
                    id="email"
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="ihre@email.com"
                    className="form-input pl-10"
                    disabled={step === 'loading'}
                    autoComplete="email"
                    autoFocus
                  />
                </div>
              </div>
              <button
                type="submit"
                disabled={step === 'loading' || !email.trim()}
                className="btn-primary w-full justify-center disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {step === 'loading' ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Wird gesendet…
                  </>
                ) : (
                  <>
                    Magic Link senden
                    <ArrowRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </form>

            {/* Divider */}
            <div className="my-6 flex items-center gap-3">
              <div className="flex-1 border-t border-slate-200" />
              <span className="text-xs text-slate-400 font-medium">oder</span>
              <div className="flex-1 border-t border-slate-200" />
            </div>

            {/* Google Sign-In */}
            <button
              onClick={handleGoogleLogin}
              disabled={googleLoading}
              className="btn-secondary w-full justify-center disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {googleLoading ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <svg className="h-4 w-4" viewBox="0 0 24 24">
                  <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                  <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                  <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                  <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                </svg>
              )}
              Mit Google anmelden
            </button>
          </>
        )}
      </div>

      {/* Terms notice */}
      <p className="mt-4 text-center text-xs text-slate-500">
        Mit der Anmeldung stimmen Sie unseren{' '}
        <Link href="/agb" className="text-blue-600 hover:underline">
          AGB
        </Link>{' '}
        und der{' '}
        <Link href="/datenschutz" className="text-blue-600 hover:underline">
          Datenschutzerklärung
        </Link>{' '}
        zu.
      </p>
      <p className="mt-2 text-center text-xs text-slate-500">
        <Link href="/" className="text-slate-600 hover:text-slate-900 hover:underline">
          ← Zurück zur Startseite
        </Link>
      </p>
    </div>
  );
}
