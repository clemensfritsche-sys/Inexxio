'use client';

import {
  startRegistration,
  startAuthentication,
  browserSupportsWebAuthn,
  platformAuthenticatorIsAvailable,
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

/**
 * Einen neuen Passkey für den aktuell angemeldeten Nutzer registrieren.
 * Ruft die Challenge ab, führt die Browser-Zeremonie durch und speichert das Ergebnis.
 */
export async function registerPasskey(deviceName?: string): Promise<Passkey> {
  const optionsJSON = await api.passkeyRegisterOptions();
  const credential = await startRegistration({ optionsJSON });
  return api.passkeyRegisterVerify(credential, deviceName);
}

/**
 * Passwortlose Anmeldung. Nach Erfolg besteht eine reguläre Firebase-Session;
 * das zurückgegebene ID-Token spiegelt den Google-Login-Fluss (Profil laden, Redirect).
 */
export async function loginWithPasskey(): Promise<{ token: string }> {
  const optionsJSON = await api.passkeyLoginOptions();
  const credential = await startAuthentication({ optionsJSON });
  const { firebase_token } = await api.passkeyLoginVerify(credential);
  const { token } = await signInWithPasskey(firebase_token);
  return { token };
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
