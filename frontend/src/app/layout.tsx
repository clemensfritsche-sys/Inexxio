import type { Metadata } from 'next';
// Inexxio Design System — single source of truth for all design tokens (color,
// type, spacing, radii, shadows). Loaded BEFORE globals.css so every token and
// utility resolves against the canonical values. Do not fork these tokens; the
// file is the vendored export from Claude Design (see docs/design-system/).
import '@/styles/design-system/colors_and_type.css';
import './globals.css';
import { ChunkReloadGuard } from '@/components/chunk-reload-guard';
import meta from '@/lib/site-meta.json';
import { SiteFooter, SiteHeader, SiteShellHead } from '@/components/layout/site-shell';
import { AccountSync } from '@/components/layout/account-sync';
import { ScanProvider } from '@/components/scan/scan-provider';

const isDev = process.env.NEXT_PUBLIC_ENVIRONMENT === 'development';

// Der Konto-/ERP-Bereich trägt den Namen und den Satz der Website (`lib/site-meta.json`,
// aus `website/src/config/site.mjs`).
export const metadata: Metadata = {
  title: { template: `%s | ${meta.brand.legalName}`, default: meta.brand.legalName },
  description: meta.claim,
  authors: [{ name: meta.brand.legalName }],
  robots: isDev ? { index: false, follow: false } : { index: true, follow: true },
  openGraph: {
    type: 'website',
    locale: 'de_CH',
    siteName: meta.brand.legalName,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    // `suppressHydrationWarning`: early.js der Website setzt am <html> «js» und den
    // Anmeldezustand, bevor React übernimmt – gewollt, nicht verschieden.
    <html lang="de" suppressHydrationWarning>
      <head>
        <SiteShellHead />
      </head>
      <body>
        <ChunkReloadGuard />
        {/* EIN Kopf, EIN Fuss: die der Website (components/layout/site-shell.tsx). */}
        <SiteHeader />
        <AccountSync />
        {/* ►►► **Der Scanner hängt an der WURZEL, nicht am ERP.** ◄◄◄ Jedes Referenzfeld trägt
            die Kamera (`ObjectSelect` → `useScan`), und Referenzfelder stehen auch im Konto
            (die Firmenwahl). Hing der Provider nur am ERP-Layout, stürzte das Konto beim
            ersten Rendern ab. Hier gibt es ihn auf jeder Seite genau einmal – der schwere
            Dialog lädt weiterhin erst beim ersten Scan. */}
        <ScanProvider>{children}</ScanProvider>
        <SiteFooter />
      </body>
    </html>
  );
}
