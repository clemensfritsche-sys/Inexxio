import type { Metadata } from 'next';
// Inexxio Design System — single source of truth for all design tokens (color,
// type, spacing, radii, shadows). Loaded BEFORE globals.css so every token and
// utility resolves against the canonical values. Do not fork these tokens; the
// file is the vendored export from Claude Design (see docs/design-system/).
import '@/styles/design-system/colors_and_type.css';
import './globals.css';
import { ChunkReloadGuard } from '@/components/chunk-reload-guard';
import { PlausibleAnalytics } from '@/components/analytics/plausible';
import { CookieConsent } from '@/components/consent/cookie-consent';
import shell from '@/lib/site-shell.json';

const isDev = process.env.NEXT_PUBLIC_ENVIRONMENT === 'development';

// Der Konto-/ERP-Bereich trägt den Namen und den Satz der Website (`lib/site-shell.json`,
// aus `website/src/config/site.mjs`). Hier stand der Text eines anderen Geschäfts
// («Präzisionsfertigung», «CNC») – ein Spiegel kann das nicht mehr.
export const metadata: Metadata = {
  title: { template: `%s | ${shell.brand.legalName}`, default: shell.brand.legalName },
  description: shell.claim,
  authors: [{ name: shell.brand.legalName }],
  robots: isDev ? { index: false, follow: false } : { index: true, follow: true },
  openGraph: {
    type: 'website',
    locale: 'de_CH',
    siteName: shell.brand.legalName,
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
