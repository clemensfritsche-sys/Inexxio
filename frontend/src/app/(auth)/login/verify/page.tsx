'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { completeMagicLink } from '@/lib/firebase';
import { api } from '@/lib/api';

const REDIRECT_KEY = 'inexxio_login_redirect';
const ROLE_KEY = 'inexxio_user_role';

function getRedirectTarget(): string {
  const saved = localStorage.getItem(REDIRECT_KEY);
  localStorage.removeItem(REDIRECT_KEY);
  return saved || '/';
}

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
        try {
          const profile = await api.getMe();
          localStorage.setItem(ROLE_KEY, profile.role);
        } catch {
          // role fetch failed — will be retried on next page load
        }
        setStatus('success');
        const target = getRedirectTarget();
        setTimeout(() => router.replace(target), 1500);
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
        try {
          const profile = await api.getMe();
          localStorage.setItem(ROLE_KEY, profile.role);
        } catch {
          // role fetch failed — will be retried on next page load
        }
        setStatus('success');
        const target = getRedirectTarget();
        setTimeout(() => router.replace(target), 1500);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Anmeldung fehlgeschlagen.');
      setStatus('error');
    }
  }

  return (
    <>
      <div className="ix-login-bg" />
      <div className="ix-login-lightbox">
        <div className="ix-login-card" style={{ textAlign: 'center' }}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="Inexxio" style={{ height: 28, margin: '0 auto 28px', display: 'block' }} />

          {status === 'loading' && (
            <>
              <Loader2 style={{ width: 36, height: 36, color: 'var(--inexxio-red)', margin: '0 auto 16px', animation: 'ix-spin 0.7s linear infinite' }} />
              <h1 style={vTitle}>Anmeldung wird verarbeitet…</h1>
              <p style={vMuted}>Bitte einen Moment warten.</p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle2 style={{ width: 36, height: 36, color: 'var(--success)', margin: '0 auto 16px' }} />
              <h1 style={vTitle}>Erfolgreich angemeldet!</h1>
              <p style={vMuted}>Sie werden weitergeleitet…</p>
            </>
          )}

          {status === 'error' && (
            <>
              <AlertCircle style={{ width: 36, height: 36, color: 'var(--inexxio-red)', margin: '0 auto 16px' }} />
              <h1 style={vTitle}>Anmeldung fehlgeschlagen</h1>
              <p style={{ ...vMuted, color: 'var(--inexxio-red)' }}>{error}</p>
              <a href="/login" style={{ fontSize: 13, color: 'var(--inexxio-red)', textDecoration: 'none', fontWeight: 500 }}>
                ← Zurück zur Anmeldung
              </a>
            </>
          )}

          {status === 'needs-email' && (
            <>
              <h1 style={vTitle}>E-Mail bestätigen</h1>
              <p style={vMuted}>
                Bitte geben Sie Ihre E-Mail-Adresse ein, um die Anmeldung abzuschliessen.
              </p>
              <form onSubmit={handleEmailSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12, textAlign: 'left', marginTop: 4 }}>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ihre@email.ch"
                  autoComplete="email"
                  autoFocus
                  className="ix-email-input"
                />
                <button type="submit" className="ix-submit-btn">Anmelden</button>
              </form>
            </>
          )}
        </div>
      </div>
    </>
  );
}

const vTitle: React.CSSProperties = {
  font: '700 18px/1.3 var(--font-display)', letterSpacing: '-0.02em',
  color: 'var(--fg-1)', margin: '0 0 8px',
};
const vMuted: React.CSSProperties = {
  font: '400 14px/1.6 var(--font-body)', color: 'var(--fg-3)', margin: '0 0 20px',
};
