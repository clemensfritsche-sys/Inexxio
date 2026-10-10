'use client';

import { useEffect, useState } from 'react';
import Script from 'next/script';
import { api } from '@/lib/api';
import { useConsent } from '@/lib/consent';

/**
 * Lädt Plausible Analytics – ausschliesslich mit erteilter Statistik-Einwilligung.
 *
 * Plausible ist cookielos und erhebt keine personenbezogenen Daten; das Skript wird
 * dennoch erst nach Zustimmung eingebunden (Privacy-by-Design, Einwilligung als eine
 * Wahrheit). Die Domain kommt aus der Firmenkonfiguration (`plausible_domain`); ohne
 * hinterlegte Domain passiert nichts.
 */
export function PlausibleAnalytics() {
  const consent = useConsent();
  const analyticsAllowed = consent?.analytics === true;
  const [domain, setDomain] = useState<string | null>(null);

  useEffect(() => {
    if (!analyticsAllowed) {
      setDomain(null);
      return;
    }
    let cancelled = false;
    api.getPublicSettings()
      .then((s) => { if (!cancelled) setDomain((s.plausible_domain as string | null) || null); })
      .catch(() => { /* ohne Domain kein Tracking */ });
    return () => { cancelled = true; };
  }, [analyticsAllowed]);

  if (!analyticsAllowed || !domain) return null;

  return (
    <Script
      strategy="afterInteractive"
      data-domain={domain}
      src="https://plausible.io/js/script.js"
    />
  );
}
