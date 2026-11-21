import type { Metadata } from 'next';
import { DocumentPage } from '@/components/beleg/document-page';

/**
 * **Die Seite eines Dokuments** (`/dokument?t=…`) – ein Vertrag, eine Bestätigung über ihren
 * unerratbaren Link, ohne Anmeldung: ansehen, unterschreiben oder ablehnen. Nie im Index.
 */
export const metadata: Metadata = {
  title: 'Dokument',
  robots: { index: false, follow: false },
};

export default function Page() {
  return <DocumentPage />;
}
