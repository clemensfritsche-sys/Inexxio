import type { Metadata } from 'next';
import { LegalPage } from '@/components/beleg/legal-page';

/** **Die Datenschutzerklärung** (`/datenschutz`) – als A4-Dokument, wie die AGB. */
export const metadata: Metadata = {
  title: 'Datenschutzerklärung',
};

export default function Page() {
  return <LegalPage kind="datenschutz" />;
}
