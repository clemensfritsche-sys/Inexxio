import type { Metadata, Viewport } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "Inexxio – Enterprise Central System",
    template: "%s | Inexxio",
  },
  description: "Zentrales Unternehmenssystem für produzierendes KMU – Website, Shop & ERP in einem.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL ?? "https://inexxio.web.app"),
  robots: { index: true, follow: true },
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  themeColor: "#0d8de6",
  width: "device-width",
  initialScale: 1,
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body className="antialiased">{children}</body>
    </html>
  );
}
