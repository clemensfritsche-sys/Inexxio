'use client';

import { AuthProvider } from '@/lib/auth-context';
import { AiAssistant } from '@/components/ai/assistant';

// Der Shop ist öffentlich (Listing/Detail), Checkout/Zahlung erfordern Login.
// AuthProvider stellt den Firebase-Token bereit; der Warenkorb (CartProvider) und das
// Warenkorb-Symbol leben global in der Navbar (siehe (public)/layout.tsx).
// Die Inexxio KI (Kaufberatung) erscheint nur für eingeloggte Besucher – das Widget
// prüft Login + KI-Verfügbarkeit selbst und rendert sonst nichts.
export default function ShopLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      {children}
      <AiAssistant context="Shop" />
    </AuthProvider>
  );
}
