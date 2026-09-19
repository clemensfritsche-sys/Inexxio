'use client';

import {
  startRegistration,
  startAuthentication,
  browserSupportsWebAuthn,
  browserSupportsWebAuthnAutofill,
  platformAuthenticatorIsAvailable,
  WebAuthnAbortService,
} from '@simplewebauthn/browser';
import { api } from './api';
import { signInWithPasskey } from './firebase';
import type { Passkey } from '@/types';

/** Unterstützt der Browser WebAuthn (Passkeys) überhaupt? */
export function passkeySupported(): boolean {
  return typeof window !== 'undefined' && browserSupportsWebAuthn();
}

/** Ist ein plattformeigener Authenticator (Face/Touch ID, Windows Hello) verfügbar? */
export async function platformPasskeyAvailable(): Promise<boolean> {
  if (!passkeySupported()) return false;
  try {
    return await platformAuthenticatorIsAvailable();
  } catch {
    return false;
  }
}

/** Unterstützt der Browser Passkey-**Autofill** (Conditional UI)? Nur dann kann der
 *  Passkey direkt im Autofill-Dropdown des E-Mail-Feldes angeboten werden. */
export async function passkeyAutofillSupported(): Promise<boolean> {
  if (!passkeySupported()) return false;
  try {
    return await browserSupportsWebAuthnAutofill();
  } catch {
    return false;
  }
}

/**
 * Einen neuen Passkey für den aktuell angemeldeten Nutzer registrieren.
 * Ruft die Challenge ab, führt die Browser-Zeremonie durch und speichert das Ergebnis.
 * Ohne expliziten Namen wird ein freundlicher Gerätename aus dem Browser abgeleitet
 * (statt eines nichtssagenden «Passkey 1»).
 */
export async function registerPasskey(deviceName?: string): Promise<Passkey> {
  const optionsJSON = await api.passkeyRegisterOptions();
  const credential = await startRegistration({ optionsJSON });
  return api.passkeyRegisterVerify(credential, deviceName?.trim() || friendlyDeviceName());
}

/**
 * Passwortlose Anmeldung (modaler Dialog – expliziter «Mit Passkey anmelden»-Knopf).
 * Nach Erfolg besteht eine reguläre Firebase-Session; das zurückgegebene ID-Token
 * spiegelt den Google-Login-Fluss (Profil laden, Redirect).
 */
export async function loginWithPasskey(): Promise<{ token: string }> {
  const optionsJSON = await api.passkeyLoginOptions();
  const credential = await startAuthentication({ optionsJSON });
  const { firebase_token } = await api.passkeyLoginVerify(credential);
  const { token } = await signInWithPasskey(firebase_token);
  return { token };
}

/**
 * Passkey-Autofill (Conditional UI): läuft **still im Hintergrund** und bietet den
 * Passkey direkt im Autofill-Dropdown des E-Mail-Feldes an (`autocomplete="… webauthn"`).
 * Der Promise löst erst auf, wenn der Nutzer im Autofill einen Passkey wählt – bis dahin
 * bleibt er offen (per {@link cancelPasskeyAutofill} abbrechbar). Kein Knopfdruck nötig –
 * genau das reibungslose «es erscheint einfach»-Erlebnis.
 */
export async function loginWithPasskeyAutofill(): Promise<{ token: string }> {
  const optionsJSON = await api.passkeyLoginOptions();
  const credential = await startAuthentication({ optionsJSON, useBrowserAutofill: true });
  const { firebase_token } = await api.passkeyLoginVerify(credential);
  const { token } = await signInWithPasskey(firebase_token);
  return { token };
}

/** Eine laufende Autofill-/WebAuthn-Zeremonie abbrechen (z. B. beim Verlassen der Seite). */
export function cancelPasskeyAutofill(): void {
  try {
    WebAuthnAbortService.cancelCeremony();
  } catch {
    // keine laufende Zeremonie – ignorieren
  }
}

/** Freundlicher Default-Gerätename aus dem User-Agent (z. B. «iPhone», «Mac», «Windows»,
 *  «Android») – damit die Passkey-Liste lesbar ist, ohne den Nutzer zu fragen. */
export function friendlyDeviceName(): string {
  if (typeof navigator === 'undefined') return 'Dieses Gerät';
  const ua = navigator.userAgent || '';
  if (/iPhone/.test(ua)) return 'iPhone';
  if (/iPad/.test(ua)) return 'iPad';
  if (/Android/.test(ua)) return 'Android-Gerät';
  if (/Macintosh|Mac OS X/.test(ua)) return 'Mac';
  if (/Windows/.test(ua)) return 'Windows-PC';
  if (/CrOS/.test(ua)) return 'Chromebook';
  if (/Linux/.test(ua)) return 'Linux-Gerät';
  return 'Dieses Gerät';
}

/**
 * WebAuthn-Zeremonien, die der Nutzer abbricht (Dialog geschlossen, kein Passkey
 * gewählt), werfen einen NotAllowedError/AbortError – kein echter Fehler, der Aufrufer
 * soll dann still bleiben.
 */
export function isPasskeyCancellation(err: unknown): boolean {
  const name = (err as { name?: string })?.name ?? '';
  return name === 'NotAllowedError' || name === 'AbortError';
}
