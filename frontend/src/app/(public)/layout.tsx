import { Navbar } from '@/components/layout/navbar';
import { Footer } from '@/components/layout/footer';
import { CartProvider } from '@/lib/cart-context';

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <CartProvider>
      <Navbar />
      <main className="min-h-screen">{children}</main>
      <Footer />
    </CartProvider>
  );
}
