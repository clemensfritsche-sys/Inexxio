'use client';

import { useEffect, useState } from 'react';

// ─── Cookie-/Einwilligungs-Verwaltung (erstanbieter, versioniert) ───────────────
//
// Inexxio ist bewusst «cookie-arm»: für Anmeldung, Warenkorb und die Speicherung
// dieser Einwilligung braucht es KEINE Zustimmung (technisch notwendig). Die EINZIGE
// optionale Kategorie ist **Statistik** (Plausible – cookielos, aber wir geben die
// Wahl). Diese Datei ist die eine Wahrheit über den Einwilligungs-Status; sie liegt
// in einem Erstanbieter-Cookie (+ localStorage-Spiegel) und meldet Änderungen per Event.

export type ConsentCategory = 'necessary' | 'analytics';

export interface ConsentState {
  /** Schema-Version – erhöht sich, wenn neue Kategorien dazukommen (erneute Abfrage). */
  v: number;
  /** ISO-Zeitstempel der Entscheidung (Nachweis). */
  ts: string;
  /** Statistik/Analytics erlaubt? `necessary` ist immer true und nicht abwählbar. */
  analytics: boolean;
}

export const CONSENT_VERSION = 1;
const COOKIE_NAME = 'inexxio_consent';
const MAX_AGE_DAYS = 180;

export const CONSENT_CHANGED_EVENT = 'inexxio:consent-changed';
export const OPEN_SETTINGS_EVENT = 'inexxio:open-cookie-settings';

// ─── Lesen ──────────────────────────────────────────────────────────────────────

function readRaw(): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.split('; ').find((c) => c.startsWith(`${COOKIE_NAME}=`));
  if (match) return decodeURIComponent(match.slice(COOKIE_NAME.length + 1));
  try {
    return localStorage.getItem(COOKIE_NAME);
  } catch {
    return null;
  }
}

export function getConsent(): ConsentState | null {
  const raw = readRaw();
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as Partial<ConsentState>;
    if (typeof parsed.analytics !== 'boolean' || parsed.v !== CONSENT_VERSION) return null;
    return { v: CONSENT_VERSION, ts: parsed.ts ?? '', analytics: parsed.analytics };
  } catch {
    return null;
  }
}

export function hasDecided(): boolean {
  return getConsent() !== null;
}

export function hasConsent(category: ConsentCategory): boolean {
  if (category === 'necessary') return true;
  return getConsent()?.analytics === true;
}

// ─── Schreiben ────────────────────────────────────────────────────────────────

function persist(state: ConsentState): void {
  const value = encodeURIComponent(JSON.stringify(state));
  if (typeof document !== 'undefined') {
    const secure = typeof location !== 'undefined' && location.protocol === 'https:' ? '; Secure' : '';
    const maxAge = MAX_AGE_DAYS * 24 * 60 * 60;
    document.cookie = `${COOKIE_NAME}=${value}; Path=/; Max-Age=${maxAge}; SameSite=Lax${secure}`;
  }
  try {
    localStorage.setItem(COOKIE_NAME, JSON.stringify(state));
  } catch {
    /* localStorage nicht verfügbar – Cookie genügt */
  }
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(CONSENT_CHANGED_EVENT));
  }
}

function decision(analytics: boolean): ConsentState {
  return { v: CONSENT_VERSION, ts: new Date().toISOString(), analytics };
}

export function acceptAll(): void {
  persist(decision(true));
}

export function acceptNecessaryOnly(): void {
  persist(decision(false));
}

export function saveConsent(analytics: boolean): void {
  persist(decision(analytics));
}

/** Öffnet den Einstellungs-Dialog (z. B. vom Footer aus). */
export function openCookieSettings(): void {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(OPEN_SETTINGS_EVENT));
  }
}

// ─── React-Hook (abonniert Änderungen) ──────────────────────────────────────────

export function useConsent(): ConsentState | null {
  const [state, setState] = useState<ConsentState | null>(null);

  useEffect(() => {
    const sync = () => setState(getConsent());
    sync(); // Erst nach Mount lesen → deterministisches SSR (keine Hydration-Mismatches)
    window.addEventListener(CONSENT_CHANGED_EVENT, sync);
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(CONSENT_CHANGED_EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  return state;
}
