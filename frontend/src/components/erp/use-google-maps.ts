'use client';

/// <reference types="google.maps" />
import { useEffect, useState } from 'react';

let loadPromise: Promise<void> | null = null;

function isReady(): boolean {
  return typeof google !== 'undefined' && !!google.maps;
}

function loadScript(apiKey: string): Promise<void> {
  if (typeof window === 'undefined') return Promise.reject(new Error('no window'));
  if (isReady()) return Promise.resolve();
  if (loadPromise) return loadPromise;

  loadPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script');
    script.id = 'google-maps-js';
    script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}&v=weekly`;
    script.async = true;
    script.defer = true;
    script.onload = () => (isReady() ? resolve() : reject(new Error('Google Maps nicht verfügbar')));
    script.onerror = () => { loadPromise = null; reject(new Error('Google Maps konnte nicht geladen werden')); };
    document.head.appendChild(script);
  });
  return loadPromise;
}

/** Lädt die Google-Maps-JS-API einmalig. error === 'no-key', wenn kein Key gesetzt ist. */
export function useGoogleMaps(apiKey: string | null | undefined): { loaded: boolean; error: string | null } {
  const [loaded, setLoaded] = useState(isReady());
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!apiKey) { setError('no-key'); return; }
    let cancelled = false;
    setError(null);
    loadScript(apiKey)
      .then(() => { if (!cancelled) setLoaded(true); })
      .catch((e: Error) => { if (!cancelled) setError(e.message); });
    return () => { cancelled = true; };
  }, [apiKey]);

  return { loaded, error };
}
