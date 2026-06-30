'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { Package, ShoppingBag } from 'lucide-react';
import { api } from '@/lib/api';
import type { ShopProduct } from '@/types';

function fmt(amount: number | string | null | undefined, currency: string): string {
  if (amount == null) return '—';
  return `${currency} ${Number(amount).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function ShopPage() {
  const [products, setProducts] = useState<ShopProduct[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getShopProducts().then(setProducts).catch(() => setProducts([])).finally(() => setLoading(false));
  }, []);

  return (
    <div className="max-w-6xl mx-auto px-6 py-12">
      <div className="flex items-center justify-between flex-wrap gap-4 mb-8">
        <div className="flex items-center gap-3">
          <ShoppingBag className="text-blue-600" size={26} />
          <h1 className="text-2xl font-bold text-slate-900">Shop</h1>
        </div>
        <p className="text-xs text-slate-400 max-w-xs text-right">
          Preise in CHF. Deine Landeswährung &amp; die Steuer werden an der Kasse automatisch berechnet.
        </p>
      </div>

      {loading ? (
        <div className="text-slate-400 text-sm">Lädt…</div>
      ) : products.length === 0 ? (
        <div className="text-center py-20 text-slate-400">
          <Package size={40} strokeWidth={1} className="mx-auto mb-3" />
          <p className="font-semibold text-slate-600">Noch keine Produkte</p>
          <p className="text-sm">Im Shop sind aktuell keine Produkte verfügbar.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {products.map((p) => (
            <Link key={p.object_id} href={`/shop/product?id=${p.object_id}`}
              className="group rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden hover:shadow-md transition-shadow">
              <div className="aspect-[4/3] bg-slate-100 flex items-center justify-center overflow-hidden">
                {p.images?.[0] ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={p.images[0]} alt={p.title} className="w-full h-full object-cover" />
                ) : (
                  <Package size={48} strokeWidth={1} className="text-slate-300" />
                )}
              </div>
              <div className="p-4">
                <h2 className="font-semibold text-slate-900 truncate">{p.title}</h2>
                {p.subtitle && <p className="text-sm text-slate-500 truncate">{p.subtitle}</p>}
                <div className="mt-3 flex items-baseline gap-2">
                  <span className="text-lg font-bold text-slate-900">{fmt(p.price?.gross, p.price?.currency ?? 'CHF')}</span>
                  {p.price?.compare_at != null && (
                    <span className="text-sm text-slate-400 line-through">{fmt(p.price.compare_at, p.price.currency)}</span>
                  )}
                </div>
                {p.price?.interval && (
                  <span className="text-xs text-slate-400">pro {p.price.interval === 'year' ? 'Jahr' : 'Monat'}</span>
                )}
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
