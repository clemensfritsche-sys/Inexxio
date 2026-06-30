'use client';

import Link from 'next/link';
import { ShoppingCart, ShoppingBag } from 'lucide-react';
import { AuthProvider } from '@/lib/auth-context';
import { CartProvider, useCart } from '@/lib/cart-context';

// Der Shop ist öffentlich (Listing/Detail), Checkout/Zahlung erfordern Login.
// AuthProvider stellt den Firebase-Token bereit; CartProvider den Warenkorb.
export default function ShopLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      <CartProvider>
        <ShopHeader />
        {children}
      </CartProvider>
    </AuthProvider>
  );
}

function ShopHeader() {
  const { count } = useCart();
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
        <Link href="/shop" className="flex items-center gap-2 font-bold text-slate-900">
          <ShoppingBag size={20} className="text-blue-600" /> Shop
        </Link>
        <Link href="/shop/cart" className="relative inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900">
          <ShoppingCart size={20} />
          {count > 0 && (
            <span className="absolute -top-2 -right-3 min-w-[18px] h-[18px] px-1 rounded-full bg-blue-600 text-white text-[11px] font-bold flex items-center justify-center">
              {count}
            </span>
          )}
        </Link>
      </div>
    </header>
  );
}
