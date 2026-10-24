'use client';

import { useEffect } from 'react';
import { logout } from '@/lib/firebase';

/**
 * ►►► `/abmelden` – der Abmelde-Weg für die Website (WEBSITE_PLAN §7.5, Schnittstelle S3).
 * ◄◄◄
 *
 * Die öffentliche Website hat kein Firebase-SDK und kann darum nicht selbst abmelden. Ihr
 * Menüpunkt «Abmelden» führt hierher: die Seite ruft das **bestehende** `logout()` (das
 * dabei auch den Anzeige-Cache räumt) und kehrt zur Startseite zurück. Es ist kein zweiter
 * Abmelde-Mechanismus, nur eine Adresse für den einen.
 *
 * Auch wenn das Abmelden scheitert (kein Netz, Firebase nicht eingerichtet), geht es zur
 * Startseite – stehenzubleiben hilft niemandem, und der Anzeige-Cache ist dann schon leer.
 */
export default function LogoutPage() {
  useEffect(() => {
    logout()
      .catch(() => undefined)
      .finally(() => window.location.replace('/'));
  }, []);

  return (
    <main style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 24 }}>
      <p role="status" style={{ font: '500 15px var(--font-body)', color: 'var(--fg-2)' }}>
        Sie werden abgemeldet …
      </p>
    </main>
  );
}
