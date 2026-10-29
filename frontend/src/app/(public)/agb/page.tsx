import type { Metadata } from 'next';
import { LegalPage } from '@/components/beleg/legal-page';

/** **Die AGB** (`/agb`) – als A4-Dokument in der Vorlage aller Belege. */
export const metadata: Metadata = {
  title: 'Allgemeine Geschäftsbedingungen',
};

export default function Page() {
  return <LegalPage kind="agb" />;
}
