'use client';

import { AuthProvider } from '@/lib/auth-context';

// Der Shop ist öffentlich (Listing/Detail), Checkout/Zahlung erfordern Login.
// AuthProvider stellt den Firebase-Token bereit (für den eingeloggten Kunden).
export default function ShopLayout({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
