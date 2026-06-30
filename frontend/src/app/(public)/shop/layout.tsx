'use client';

import { AuthProvider } from '@/lib/auth-context';

// Der Shop ist öffentlich (Listing/Detail), Checkout/Zahlung erfordern Login.
// AuthProvider stellt den Firebase-Token bereit; der Warenkorb (CartProvider) und das
// Warenkorb-Symbol leben global in der Navbar (siehe (public)/layout.tsx).
export default function ShopLayout({ children }: { children: React.ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}
