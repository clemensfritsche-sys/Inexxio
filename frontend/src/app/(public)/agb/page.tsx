import type { Metadata } from 'next';
import { AgbPage } from '@/components/beleg/agb-page';

/**
 * **Die AGB** (`/agb`) – als A4-Dokument in der Vorlage aller Belege. Der Anmeldedialog und der
 * Fuss der Website verweisen hierher.
 */
export const metadata: Metadata = {
  title: 'Allgemeine Geschäftsbedingungen',
};

export default function Page() {
  return <AgbPage />;
}
