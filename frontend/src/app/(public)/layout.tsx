import { Navbar } from '@/components/layout/navbar';
import { Footer } from '@/components/layout/footer';
import { CartProvider } from '@/lib/cart-context';
import { AiAssistant } from '@/components/ai/assistant';

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <CartProvider>
      <Navbar />
      <main className="min-h-screen">{children}</main>
      <Footer />
      {/* KI überall verfügbar – auch auf der öffentlichen Website/im Shop. Das Widget
          rendert nur für angemeldete Nutzer (rechte-gescopt) und blendet sich sonst aus. */}
      <AiAssistant context="Website" />
    </CartProvider>
  );
}
