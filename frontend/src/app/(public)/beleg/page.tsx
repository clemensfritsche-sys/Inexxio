import type { Metadata } from 'next';
import { BelegPage } from '@/components/beleg/beleg-page';

/**
 * **Die Seite eines Belegs** (`/beleg?t=…`) – Offerte, Auftragsbestätigung, Rechnung, Quittung
 * über ihren unerratbaren Link, ohne Anmeldung. Privat je Link: nie im Index
 * (`site.erpPaths` sperrt sie zudem in robots.txt).
 */
export const metadata: Metadata = {
  title: 'Beleg',
  robots: { index: false, follow: false },
};

export default function Page() {
  return <BelegPage />;
}
