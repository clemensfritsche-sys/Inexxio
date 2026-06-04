'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Settings2, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { completeMagicLink } from '@/lib/firebase';
import { api } from '@/lib/api';

export default function VerifyPage() {
  const router = useRouter();
  const [status, setStatus] = useState<'loading' | 'success' | 'error' | 'needs-email'>('loading');
  const [error, setError] = useState('');
  const [email, setEmail] = useState('');

  useEffect(() => {
    async function verify() {
      try {
        const result = await completeMagicLink();
        if (!result) {
          router.replace('/login');
          return;
        }
        api.setToken(result.token);
        localStorage.setItem('inexxio_token', result.token);
        setStatus('success');
        setTimeout(() => router.replace('/erp'), 1500);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : '';
        if (msg.includes('E-Mail-Adresse nicht gefunden')) {
          setStatus('needs-email');
        } else {
          setError(msg || 'Anmeldung fehlgeschlagen. Bitte erneut versuchen.');
          setStatus('error');
        }
      }
    }
    verify();
  }, [router]);

  async function handleEmailSubmit(e: React.FormEvent) {
    e.preventDefault();
    setStatus('loading');
    try {
      localStorage.setItem('emailForSignIn', email);
      const result = await completeMagicLink();
      if (result) {
        api.setToken(result.token);
        localStorage.setItem('inexxio_token', result.token);
        setStatus('success');
        setTimeout(() => router.replace('/erp'), 1500);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Anmeldung fehlgeschlagen.');
      setStatus('error');
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8 text-center">
          <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-blue-600 text-white mx-auto mb-6">
            <Settings2 className="h-6 w-6" />
          </div>

          {status === 'loading' && (
            <>
              <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-4" />
              <h1 className="text-lg font-semibold text-slate-900">Anmeldung wird verarbeitet…</h1>
              <p className="text-sm text-slate-500 mt-2">Bitte einen Moment warten.</p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle2 className="h-8 w-8 text-green-500 mx-auto mb-4" />
              <h1 className="text-lg font-semibold text-slate-900">Erfolgreich angemeldet!</h1>
              <p className="text-sm text-slate-500 mt-2">Sie werden weitergeleitet…</p>
            </>
          )}

          {status === 'error' && (
            <>
              <AlertCircle className="h-8 w-8 text-red-500 mx-auto mb-4" />
              <h1 className="text-lg font-semibold text-slate-900">Anmeldung fehlgeschlagen</h1>
              <p className="text-sm text-red-600 mt-2">{error}</p>
              <a href="/login" className="mt-4 inline-block text-sm text-blue-600 hover:underline">
                Zurück zur Anmeldung
              </a>
            </>
          )}

          {status === 'needs-email' && (
            <>
              <h1 className="text-lg font-semibold text-slate-900 mb-2">E-Mail bestätigen</h1>
              <p className="text-sm text-slate-600 mb-4">
                Bitte geben Sie Ihre E-Mail-Adresse ein, um die Anmeldung abzuschliessen.
              </p>
              <form onSubmit={handleEmailSubmit} className="text-left space-y-3">
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ihre@email.com"
                  className="form-input"
                  autoFocus
                />
                <button type="submit" className="btn-primary w-full justify-center">
                  Anmelden
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
