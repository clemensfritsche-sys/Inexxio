'use client';

import { AuthProvider } from '@/lib/auth-context';

// Der Shop ist öffentlich (Listing/Detail), Checkout/Zahlung erfordern Login.
// AuthProvider stellt den Firebase-Token bereit; der Warenkorb (CartProvider) und das
// Warenkorb-Symbol leben global in der Navbar (siehe (public)/layout.tsx).
// Die Inexxio KI (Kaufberatung) wird global im (public)/layout gemountet – hier NICHT
// erneut, sonst erschiene das Widget doppelt (der Shop liegt unter dem Public-Layout).
export default function ShopLayout({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
