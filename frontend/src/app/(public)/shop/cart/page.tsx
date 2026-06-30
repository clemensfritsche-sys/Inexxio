'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Package, Trash2, ShoppingCart, ArrowLeft } from 'lucide-react';
import { useCart } from '@/lib/cart-context';
import type { CartItem } from '@/types';

function fmt(amount: number | string | null | undefined, currency: string): string {
  if (amount == null) return '—';
  return `${currency} ${Number(amount).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function itemLabel(i: CartItem): string {
  if (i.kind !== 'subscription') return 'Einmalkauf';
  const base = i.sub_type === 'product' ? 'Produktabo' : 'Nutzungsabo';
  return `${base} · ${i.interval === 'year' ? 'jährlich' : 'monatlich'}`;
}

export default function CartPage() {
  const router = useRouter();
  const { items, subtotal, currency, hydrated, setQuantity, remove, keyOf } = useCart();

  if (!hydrated) {
    return <div className="max-w-3xl mx-auto px-6 py-16 text-center text-slate-400 text-sm">Lädt…</div>;
  }
  if (items.length === 0) {
    return (
      <div className="max-w-3xl mx-auto px-6 py-16 text-center">
        <Package size={40} strokeWidth={1} className="mx-auto mb-3 text-slate-300" />
        <p className="font-semibold text-slate-600">Dein Warenkorb ist leer</p>
        <Link href="/shop" className="mt-4 inline-flex items-center gap-1 text-blue-600 text-sm"><ArrowLeft size={14} /> Zum Shop</Link>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto px-6 py-10">
      <h1 className="text-2xl font-bold text-slate-900 mb-6">Warenkorb</h1>
      <div className="flex flex-col gap-3">
        {items.map((i) => {
          const k = keyOf(i);
          const isSub = i.kind === 'subscription';
          return (
            <div key={k} className="flex items-center gap-4 rounded-xl border border-slate-200 bg-white p-3.5 shadow-sm">
              <div className="w-16 h-16 rounded-lg bg-slate-100 flex items-center justify-center overflow-hidden shrink-0">
                {i.image ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={i.image} alt={i.title} className="w-full h-full object-cover" />
                ) : <Package size={28} strokeWidth={1} className="text-slate-300" />}
              </div>
              <div className="flex-1 min-w-0">
                <Link href={`/shop/product?id=${i.article_object_id}`} className="font-semibold text-slate-900 truncate block hover:text-blue-600">{i.title}</Link>
                <div className="text-xs text-slate-500">{itemLabel(i)}</div>
                <div className="text-sm text-slate-700 mt-0.5">{fmt(i.gross, i.currency)}{isSub && <span className="text-xs text-slate-400"> / {i.interval === 'year' ? 'Jahr' : 'Monat'}</span>}</div>
              </div>
              {!isSub ? (
                <input type="number" min={1} value={i.quantity}
                  onChange={(e) => setQuantity(k, Number(e.target.value) || 1)}
                  className="w-16 px-2 py-1.5 text-sm rounded-md border border-slate-200 outline-none focus:ring-2 focus:ring-blue-500" />
              ) : <span className="text-sm text-slate-400 w-16 text-center">1×</span>}
              <div className="w-24 text-right text-sm font-bold text-slate-900">{fmt(i.gross * i.quantity, i.currency)}</div>
              <button onClick={() => remove(k)} title="Entfernen" className="text-slate-400 hover:text-red-600">
                <Trash2 size={16} />
              </button>
            </div>
          );
        })}
      </div>

      <div className="mt-6 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <span className="text-sm text-slate-600">Zwischensumme (indikativ)</span>
          <span className="text-lg font-bold text-slate-900">{fmt(subtotal, currency)}</span>
        </div>
        <p className="mt-1 text-xs text-slate-400">
          Landeswährung &amp; finale Steuer werden an der Kasse (Stripe) berechnet.
        </p>
        <button onClick={() => router.push('/shop/checkout')}
          className="mt-4 w-full inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 text-white font-semibold py-3 hover:bg-blue-700">
          <ShoppingCart size={18} /> Zur Kasse
        </button>
        <Link href="/shop" className="mt-3 block text-center text-blue-600 text-sm">Weiter einkaufen</Link>
      </div>
    </div>
  );
}
