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
    <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
      <div style={{ width: '100%', maxWidth: 360 }}>
        <div style={{ background: '#fff', borderRadius: 20, border: '1px solid #E2E8F0', boxShadow: '0 4px 24px rgba(0,0,0,0.06)', padding: 40, textAlign: 'center' }}>
          {/* Logo */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo.png" alt="Inexxio" style={{ height: 28, margin: '0 auto 28px', display: 'block' }} />

          {status === 'loading' && (
            <>
              <Loader2 style={{ width: 36, height: 36, color: '#E51A14', margin: '0 auto 16px', animation: 'spin 0.7s linear infinite' }} />
              <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
              <h1 style={{ fontSize: 17, fontWeight: 700, color: '#0F172A', margin: '0 0 6px' }}>Anmeldung wird verarbeitet…</h1>
              <p style={{ fontSize: 14, color: '#94a3b8', margin: 0 }}>Bitte einen Moment warten.</p>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle2 style={{ width: 36, height: 36, color: '#16a34a', margin: '0 auto 16px' }} />
              <h1 style={{ fontSize: 17, fontWeight: 700, color: '#0F172A', margin: '0 0 6px' }}>Erfolgreich angemeldet!</h1>
              <p style={{ fontSize: 14, color: '#94a3b8', margin: 0 }}>Sie werden weitergeleitet…</p>
            </>
          )}

          {status === 'error' && (
            <>
              <AlertCircle style={{ width: 36, height: 36, color: '#E51A14', margin: '0 auto 16px' }} />
              <h1 style={{ fontSize: 17, fontWeight: 700, color: '#0F172A', margin: '0 0 6px' }}>Anmeldung fehlgeschlagen</h1>
              <p style={{ fontSize: 14, color: '#E51A14', margin: '0 0 20px' }}>{error}</p>
              <a href="/login" style={{ fontSize: 13, color: '#E51A14', textDecoration: 'none', fontWeight: 500 }}>
                ← Zurück zur Anmeldung
              </a>
            </>
          )}

          {status === 'needs-email' && (
            <>
              <h1 style={{ fontSize: 17, fontWeight: 700, color: '#0F172A', margin: '0 0 8px' }}>E-Mail bestätigen</h1>
              <p style={{ fontSize: 14, color: '#64748b', margin: '0 0 20px' }}>
                Bitte geben Sie Ihre E-Mail-Adresse ein, um die Anmeldung abzuschliessen.
              </p>
              <form onSubmit={handleEmailSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12, textAlign: 'left' }}>
                <input
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="ihre@email.ch"
                  autoFocus
                  style={{
                    padding: '10px 14px', borderRadius: 8, border: '1px solid #E2E8F0',
                    fontSize: 14, color: '#0F172A', outline: 'none', width: '100%',
                    boxSizing: 'border-box',
                  }}
                />
                <button
                  type="submit"
                  style={{
                    padding: '11px 20px', borderRadius: 8, border: 'none',
                    background: '#E51A14', color: '#fff', fontSize: 14,
                    fontWeight: 600, cursor: 'pointer', width: '100%',
                  }}
                >
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
