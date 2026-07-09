'use client';

/// <reference types="google.maps" />
import { useEffect, useState } from 'react';

let loadPromise: Promise<void> | null = null;
let authFailed = false;
const authListeners = new Set<() => void>();

function isReady(): boolean {
  return typeof google !== 'undefined' && !!google.maps;
}

// Google ruft diese globale Funktion bei einem Authentifizierungsfehler auf (ungültiger Key,
// nicht freigeschaltete »Places API«, Referrer-/API-Restriktion). Ist sie definiert,
// UNTERDRÜCKT Google das aufdringliche Overlay »Diese Seite kann Google Maps nicht richtig
// laden« – wir schalten die betroffenen Felder still auf den reinen Text-/Karten-Fallback.
function installAuthHandler() {
  if (typeof window === 'undefined') return;
  const w = window as unknown as { gm_authFailure?: () => void };
  if (w.gm_authFailure) return;
  w.gm_authFailure = () => {
    authFailed = true;
    authListeners.forEach((fn) => fn());
  };
}

function loadScript(apiKey: string): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'));
  installAuthHandler();
  if (isReady()) return Promise.resolve();
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.id = 'google-maps-js';
    // ``places`` für die Adress-Autovervollständigung (AddressAutocomplete); ``weekly`` = aktuell.
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&v=weekly&libraries=places`;
    script.async = true;
    script.defer = true;
    script.onload = () => (isReady() ? resolve() : reject(new Error('Google Maps nicht verfügbar')));
    script.onerror = () => { loadPromise = null; reject(new Error('Google Maps konnte nicht geladen werden')); };
    document.head.appendChild(script);
  });
  return loadPromise;
}

/**
 * Lädt die Google-Maps-JS-API einmalig. ``error === 'no-key'`` ohne Key, ``'auth'`` bei
 * Authentifizierungs-/Freischaltungsfehler (z. B. Places API nicht aktiviert oder der Key
 * per API-Restriktion auf »Maps JavaScript API« beschränkt). Bei ``'auth'`` fallen die
 * Adressfelder auf reine Texteingabe zurück – nie kaputt.
 */
export function useGoogleMaps(apiKey: string | null | undefined): { loaded: boolean; error: string | null } {
  const [loaded, setLoaded] = useState(isReady());
  const [error, setError] = useState<string | null>(authFailed ? 'auth' : null);

  useEffect(() => {
    if (!apiKey) { setError('no-key'); return; }
    let cancelled = false;
    setError(authFailed ? 'auth' : null);
    const onAuth = () => { if (!cancelled) setError('auth'); };
    authListeners.add(onAuth);
    loadScript(apiKey)
      .then(() => { if (!cancelled) setLoaded(true); })
      .catch((e: Error) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; authListeners.delete(onAuth); };
  }, [apiKey]);

  return { loaded, error };
}
