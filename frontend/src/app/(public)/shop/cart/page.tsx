'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Package, Trash2, ShoppingCart, ArrowLeft } from 'lucide-react';
import { useCart } from '@/lib/cart-context';
import type { CartItem } from '@/types';
import { formatMoney as fmt } from '@/lib/utils';


function itemLabel(i: CartItem): string {
  if (i.kind !== 'subscription') return 'Einmalkauf';
  const base = i.sub_type === 'product' ? 'Produktabo' : 'Nutzungsabo';
  return `${base} · ${i.interval === 'year' ? 'jährlich' : 'monatlich'}`;
}

export default function CartPage() {
  const router = useRouter();
  const { items, subtotal, currency, hydrated, setQuantity, remove, keyOf } = useCart();

  if (!hydrated) {
    return <div className="max-w-3xl mx-auto px-6 py-16 text-center text-fg-4 text-sm">Lädt…</div>;
  }
  if (items.length === 0) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-16 text-center">
        <Package size={40} strokeWidth={1} className="mx-auto mb-3 text-fg-4" />
        <p className="font-semibold text-fg-3">Dein Warenkorb ist leer</p>
        <Link href="/shop" className="mt-4 inline-flex items-center gap-1 text-accent text-sm"><ArrowLeft size={14} /> Zum Shop</Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-4 sm:px-6 py-10 pb-24">
      <h1 className="text-2xl font-bold font-display text-fg-1 mb-6">Warenkorb</h1>
      <div className="flex flex-col gap-3">
        {items.map((i) => {
          const k = keyOf(i);
          const isSub = i.kind === 'subscription';
          // flex-wrap: auf schmalen Viewports rutschen Menge/Preis/Entfernen in eine
          // zweite Zeile, statt den Titel auf 0 Breite zu quetschen.
          return (
            <div key={k} className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-ds-lg border border-border-1 bg-bg-1 p-3.5">
              <div className="w-16 h-16 rounded-ds-sm bg-bg-2 flex items-center justify-center overflow-hidden shrink-0">
                {i.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={i.image} alt={i.title} className="w-full h-full object-cover" />
                ) : <Package size={28} strokeWidth={1} className="text-fg-4" />}
              </div>
              <div className="flex-1 min-w-[45%]">
                <Link href={`/shop/product?id=${i.article_object_id}`} className="font-semibold text-fg-1 truncate block hover:text-accent">{i.title}</Link>
                <div className="text-xs text-fg-3">{itemLabel(i)}</div>
                <div className="text-sm text-fg-2 mt-0.5 ix-tnum">{fmt(i.gross, i.currency)}{isSub && <span className="text-xs text-fg-4"> / {i.interval === 'year' ? 'Jahr' : 'Monat'}</span>}</div>
              </div>
              {!isSub ? (
                <input type="number" min={1} value={i.quantity}
                  onChange={(e) => setQuantity(k, Number(e.target.value) || 1)}
                  className="w-16 px-2 py-2 text-sm rounded-ds-sm border border-border-1 outline-none focus:ring-2 focus:ring-accent ix-tnum" />
              ) : <span className="text-sm text-fg-4 w-16 text-center">1×</span>}
              <div className="w-24 text-right text-sm font-bold text-fg-1 ix-tnum">{fmt(i.gross * i.quantity, i.currency)}</div>
              <button onClick={() => remove(k)} title="Entfernen"
                className="min-w-[44px] min-h-[44px] -my-2 flex items-center justify-center rounded-ds-sm text-fg-4 hover:text-danger hover:bg-bg-2">
                <Trash2 size={17} />
              </button>
            </div>
          );
        })}
      </div>

      <div className="mt-6 rounded-ds-lg border border-border-1 bg-bg-1 p-4">
        <div className="flex items-center justify-between">
          <span className="text-sm text-fg-3">Zwischensumme (indikativ)</span>
          <span className="text-lg font-bold text-fg-1 ix-tnum">{fmt(subtotal, currency)}</span>
        </div>
        <p className="mt-1 text-xs text-fg-4">
          Landeswährung &amp; finale Steuer werden an der Kasse (Stripe) berechnet.
        </p>
        <button onClick={() => router.push('/shop/checkout')}
          className="mt-4 w-full min-h-[44px] inline-flex items-center justify-center gap-2 rounded-ds-md bg-inexxio text-white font-semibold py-3 hover:bg-inexxio-deep">
          <ShoppingCart size={18} /> Zur Kasse
        </button>
        <Link href="/shop" className="mt-3 block text-center text-accent text-sm py-2">Weiter einkaufen</Link>
      </div>
    </div>
  );
}
