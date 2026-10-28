'use client';

/**
 * **Die Anmeldung ist ein Pop-up, keine Seite.**
 *
 * Gestaltung: Glas-Karte ohne ✕ (Klick daneben/`Esc`), auf dem Handy ein Blatt von unten –
 * Stile in `app/globals.css` («Anmeldung»).
 *
 * Vorher war `/login` eine Route mit deckendem, animiertem Farbverlauf: wer sich anmelden
 * wollte, verliess die Seite, auf der er war, und fand nur über einen eigenen Link
 * («Zurück zur Startseite») zurück. Jetzt ist es ein Dialog über dem, was man ansieht –
 * halbtransparenter Scrim, Klick daneben und `Esc` schliessen.
 *
 * **Zwei Orte, EINE Komponente.** Der Knopf in der Navigation öffnet sie an Ort und
 * Stelle (keine Navigation); die **Route** bleibt der Weg, auf dem ein geschützter
 * Bereich umleitet und auf dem ein Lesezeichen landet – sie rendert denselben Dialog,
 * nur heisst «daneben klicken» dort «zur Startseite», weil hinter ihr nichts steht.
 *
 * Damit ist **«Zurück zur Startseite» entfallen**: nicht gestrichen, sondern in die
 * Geste aufgegangen, die ein Pop-up ohnehin hat.
 */

import { useState, useEffect } from 'react';
import { ArrowRight, Fingerprint, Mail } from 'lucide-react';
import type { FirebaseError } from 'firebase/app';
import { sendMagicLink, signInWithGoogle } from '@/lib/firebase';
import {
  loginWithPasskey, loginWithPasskeyAutofill, cancelPasskeyAutofill,
  passkeySupported, passkeyAutofillSupported, isPasskeyCancellation,
} from '@/lib/passkey';
import { api } from '@/lib/api';
import { goTo, loginTarget, rememberFrom } from '@/lib/login-target';
import { cachedRole, rememberName, rememberRole } from '@/lib/account-cache';

type Step = 'input' | 'loading' | 'sent';

function getMailUrl(email: string): string {
  const domain = email.split('@')[1]?.toLowerCase() ?? '';
  if (['gmail.com', 'googlemail.com'].includes(domain)) return 'https://mail.google.com';
  if (['outlook.com', 'hotmail.com', 'live.com', 'hotmail.de', 'outlook.de', 'msn.com'].includes(domain)) return 'https://outlook.live.com';
  if (domain.startsWith('yahoo.')) return 'https://mail.yahoo.com';
  if (['icloud.com', 'me.com', 'mac.com'].includes(domain)) return 'https://www.icloud.com/mail';
  if (domain === 'bluewin.ch') return 'https://mail.bluewin.ch';
  return `mailto:${email}`;
}

function getGoogleErrorMessage(code: string): string {
  switch (code) {
    case 'auth/operation-not-allowed':
      return 'Google-Anmeldung ist nicht aktiviert.';
    case 'auth/unauthorized-domain':
      return 'Diese Domain ist nicht autorisiert.';
    case 'auth/network-request-failed':
      return 'Netzwerkfehler. Bitte Internetverbindung prüfen.';
    case 'auth/web-storage-unavailable':
      return 'Browser-Speicher nicht verfügbar. Cookie-Einstellungen prüfen.';
    default:
      return `Anmeldung fehlgeschlagen (${code || 'unbekannt'}). Bitte erneut versuchen.`;
  }
}

export function LoginDialog({ onClose, fallback }: {
  /** Was «daneben klicken» bedeutet: schliessen (Pop-up) bzw. zur Startseite (Route). */
  onClose: () => void;
  /**
   * Wohin nach der Anmeldung, wenn kein `?from=` gemerkt ist. Ohne Angabe: der Startplatz
   * der Rolle (`login-target.startPage`) – nie «/», dort steht die Website.
   */
  fallback?: string;
}) {
  const [email, setEmail] = useState('');
  const [step, setStep] = useState<Step>('input');
  const [error, setError] = useState('');
  const [googleLoading, setGoogleLoading] = useState(false);
  const [passkeyLoading, setPasskeyLoading] = useState(false);
  const [showPasskey, setShowPasskey] = useState(false);
  const [sentEmail, setSentEmail] = useState('');

  useEffect(() => {
    setShowPasskey(passkeySupported());
    // `?from=` merken: der Magic Link kommt oft in einem neuen Tab zurück, ohne Parameter.
    rememberFrom();
  }, []);

  // **Esc schliesst** – dieselbe Aussage wie der Klick daneben, nur mit der Tastatur.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  // Passkey-Autofill (Conditional UI): still im Hintergrund starten, sobald der Browser es
  // unterstützt. Der Passkey erscheint dann direkt im Autofill-Dropdown des E-Mail-Feldes –
  // ein Tap auf den Vorschlag (+ Face/Touch ID) meldet an, ganz ohne Knopfdruck. Der Promise
  // bleibt offen, bis der Nutzer im Autofill wählt; beim Verlassen der Seite wird abgebrochen.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!(await passkeyAutofillSupported())) return;
      try {
        await loginWithPasskeyAutofill();
        if (!cancelled) await finishLogin();
      } catch (err: unknown) {
        if (!cancelled && !isPasskeyCancellation(err)) {
          setError(err instanceof Error ? err.message : 'Passkey-Anmeldung fehlgeschlagen.');
        }
      }
    })();
    return () => { cancelled = true; cancelPasskeyAutofill(); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Gemeinsamer Abschluss für Logins mit sofortiger Sitzung (Google, Passkey): Profil
  // (Rolle/Name) cachen und **hart** weiter (`login-target`). Den Token holt der API-Client
  // selbst (`lib/firebase.ts`). Bewusst ohne
  // `onClose()`: an der Route heisst «schliessen» «zur Website», und diese Navigation
  // überholte die Weiterleitung – der Login landete auf der Startseite statt im ERP.
  async function finishLogin() {
    let role: string | null = null;
    try {
      const profile = await api.getMe();
      role = profile.role;
      rememberRole(profile.role);
      rememberName([profile.first_name, profile.last_name].filter(Boolean).join(' '));
    } catch {
      // Rolle unbekannt – dann führt der Startplatz ins Konto; das ERP prüft selbst.
      role = cachedRole();
    }
    goTo(loginTarget(role, fallback));
  }

  async function handlePasskeyLogin() {
    if (passkeyLoading) return;
    setError('');
    setPasskeyLoading(true);
    try {
      await loginWithPasskey();
      await finishLogin();
    } catch (err: unknown) {
      if (!isPasskeyCancellation(err)) {
        setError(err instanceof Error ? err.message : 'Passkey-Anmeldung fehlgeschlagen.');
      }
      setPasskeyLoading(false);
    }
  }

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
    if (googleLoading) return;
    setError('');
    setGoogleLoading(true);

    // Watchdog: Schliesst der Nutzer das Popup (X), meldet Firebase das nicht in
    // allen Browsern zuverlässig zurück – der Button bliebe sonst ewig im
    // Ladezustand. Kehrt der Fokus ins Hauptfenster zurück und ist nach kurzer
    // Frist nichts passiert, den Ladezustand wieder freigeben.
    let settled = false;
    const onFocus = () => {
      window.setTimeout(() => { if (!settled) setGoogleLoading(false); }, 1500);
    };
    window.addEventListener('focus', onFocus, { once: true });

    try {
      await signInWithGoogle();
      settled = true;
      await finishLogin();
    } catch (err: unknown) {
      settled = true;
      setGoogleLoading(false);
      const code = (err as FirebaseError).code ?? '';
      // Vom Nutzer bewusst abgebrochen (Popup geschlossen) → keine Fehlermeldung
      if (code !== 'auth/popup-closed-by-user' && code !== 'auth/cancelled-popup-request') {
        setError(getGoogleErrorMessage(code));
      }
    } finally {
      window.removeEventListener('focus', onFocus);
    }
  }

  return (
    <div
      className="ix-login-scrim"
      role="dialog"
      aria-modal="true"
      aria-label="Anmelden"
      /* **Klick daneben schliesst** – es gibt kein ✕: ein Pop-up hat diese Geste ohnehin, und
         `Esc` sagt dasselbe. Nur der Scrim selbst zählt: ein Klick, der in der Karte begann,
         schliesst nicht (Textauswahl über den Rand hinaus). */
      onMouseDown={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="ix-login-card" onMouseDown={(e) => e.stopPropagation()}>
        {step === 'sent' ? (
          <>
            <div className="ix-success-icon" aria-hidden>
              <svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg">
                <circle className="ix-success-circle" cx="60" cy="60" r="56" fill="#fff" stroke="rgba(229,26,20,.18)" strokeWidth="2" />
                <polyline className="ix-success-line" points="38,62 53,77 84,44" fill="none" stroke="var(--inexxio-red)" strokeWidth="7" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </div>
            <h2>Schauen Sie in Ihr Postfach.</h2>
            <p className="ix-login-sub">Ein Klick auf den Link – und Sie sind angemeldet.</p>
            <span className="ix-login-mail"><Mail aria-hidden />{sentEmail}</span>
            <a
              href={getMailUrl(sentEmail)}
              target={getMailUrl(sentEmail).startsWith('mailto:') ? undefined : '_blank'}
              rel="noopener noreferrer"
              className="ix-submit-btn"
            >
              Posteingang öffnen
            </a>
            <button type="button" className="ix-login-link" onClick={() => { setStep('input'); setEmail(''); }}>
              Andere E-Mail verwenden
            </button>
          </>
        ) : (
          <>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src="/brand/anmelden.svg" alt="" className="ix-login-art" />
            <h1>Anmelden</h1>
            <p className="ix-login-sub">Ohne Passwort. Wir schicken Ihnen einen Link.</p>

            {/* Das Feld und der rote Pfeil sind EIN Formular. Ein Passkey erscheint direkt im
                Autofill des Feldes (`webauthn`) – darum braucht es keinen Hinweis mehr. */}
            <form onSubmit={handleMagicLink} className="ix-login-field">
              <label htmlFor="email" className="sr-only">E-Mail-Adresse</label>
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="E-Mail-Adresse"
                required
                autoComplete="email webauthn"
                autoFocus
                disabled={step === 'loading'}
              />
              <button
                type="submit"
                className="ix-login-go"
                disabled={step === 'loading' || !email.trim()}
                aria-label={step === 'loading' ? 'Wird gesendet' : 'Anmeldelink senden'}
              >
                {step === 'loading' ? <span className="ix-spinner" /> : <ArrowRight aria-hidden />}
              </button>
            </form>

            {error && <p key={error} className="ix-login-error" role="alert">{error}</p>}

            <div className="ix-login-alt">
              {showPasskey && (
                <button type="button" className="ix-login-pill" onClick={handlePasskeyLogin} disabled={passkeyLoading}>
                  {passkeyLoading ? <span className="ix-spinner ix-spinner--ink" /> : <Fingerprint className="ix-fp" aria-hidden />}
                  Passkey
                </button>
              )}
              <button type="button" className="ix-login-pill" onClick={handleGoogleLogin} disabled={googleLoading}>
                {googleLoading ? <span className="ix-spinner ix-spinner--ink" /> : (
                  <svg viewBox="0 0 24 24" aria-hidden>
                    <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" />
                    <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
                    <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
                    <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
                  </svg>
                )}
                Google
              </button>
            </div>

            <p className="ix-login-legal">
              Mit der Anmeldung gelten <a href="/agb">AGB</a> und <a href="/datenschutz">Datenschutz</a>.
            </p>
          </>
        )}
      </div>
    </div>
  );
}
