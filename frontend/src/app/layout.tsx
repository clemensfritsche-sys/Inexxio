import type { Metadata } from 'next';
// Inexxio Design System — single source of truth for all design tokens (color,
// type, spacing, radii, shadows). Loaded BEFORE globals.css so every token and
// utility resolves against the canonical values. Do not fork these tokens; the
// file is the vendored export from Claude Design (see docs/design-system/).
import '@/styles/design-system/colors_and_type.css';
import './globals.css';
import { ChunkReloadGuard } from '@/components/chunk-reload-guard';
import { CookieConsent } from '@/components/consent/cookie-consent';
import { PlausibleAnalytics } from '@/components/analytics/plausible';

const isDev = process.env.NEXT_PUBLIC_ENVIRONMENT === 'development';

export const metadata: Metadata = {
  title: { template: '%s | Inexxio AG', default: 'Inexxio AG – Präzisionsfertigung' },
  description:
    'Inexxio AG – Ihr Schweizer Spezialist für Präzisionsfertigung und Maschinenbau. Qualität made in Switzerland.',
  keywords: 'Präzisionsfertigung, Maschinenbau, Schweiz, Swiss Made, CNC, Qualität',
  authors: [{ name: 'Inexxio AG' }],
  robots: isDev ? { index: false, follow: false } : { index: true, follow: true },
  openGraph: {
    type: 'website',
    locale: 'de_CH',
    siteName: 'Inexxio AG',
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>
        <ChunkReloadGuard />
        {children}
        <CookieConsent />
        <PlausibleAnalytics />
      </body>
    </html>
  );
}
