import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: { template: '%s | Inexxio AG', default: 'Inexxio AG – Präzisionsfertigung' },
  description:
    'Inexxio AG – Ihr Schweizer Spezialist für Präzisionsfertigung und Maschinenbau. Qualität made in Switzerland.',
  keywords: 'Präzisionsfertigung, Maschinenbau, Schweiz, Swiss Made, CNC, Qualität',
  authors: [{ name: 'Inexxio AG' }],
  robots: { index: true, follow: true },
  openGraph: {
    type: 'website',
    locale: 'de_CH',
    siteName: 'Inexxio AG',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>{children}</body>
    </html>
  );
}
