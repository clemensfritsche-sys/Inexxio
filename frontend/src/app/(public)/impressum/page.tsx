import type { Metadata } from 'next';
import { LegalPage } from '@/components/beleg/legal-page';

/** **Das Impressum** (`/impressum`) – als A4-Dokument, wie die AGB. */
export const metadata: Metadata = {
  title: 'Impressum',
};

export default function Page() {
  return <LegalPage kind="impressum" />;
}
