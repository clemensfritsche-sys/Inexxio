'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Package, ArrowLeft, ShoppingCart, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import type { ShopProduct } from '@/types';

function fmt(amount: number | string | null | undefined, currency: string): string {
  if (amount == null) return '—';
  return `${currency} ${Number(amount).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function ProductView() {
  const search = useSearchParams();
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const objectId = Number(search.get('id'));

  const [product, setProduct] = useState<ShopProduct | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const [buying, setBuying] = useState(false);

  useEffect(() => {
    if (!objectId) { setLoading(false); return; }
    setLoading(true);
    api.getShopProduct(objectId)
      .then(setProduct)
      .catch((e) => setError(e instanceof Error ? e.message : 'Produkt nicht gefunden'))
      .finally(() => setLoading(false));
  }, [objectId]);

  async function buy() {
    if (!user) { router.push('/login'); return; }
    setBuying(true);
    setError(null);
    try {
      const result = await api.shopCheckout(objectId, qty);
      window.location.href = result.payment_url;   // → Stripe Checkout (bzw. manuelle Test-Seite)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Kauf fehlgeschlagen');
      setBuying(false);
    }
  }

  if (loading) return <div className="max-w-4xl mx-auto px-6 py-12 text-slate-400 text-sm">Lädt…</div>;
  if (!product) return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <p className="text-slate-500">{error ?? 'Produkt nicht gefunden.'}</p>
      <Link href="/shop" className="text-blue-600 text-sm mt-3 inline-flex items-center gap-1"><ArrowLeft size={14} /> Zum Shop</Link>
    </div>
  );

  const price = product.price;

  return (
    <div className="max-w-4xl mx-auto px-6 py-10">
      <Link href="/shop" className="text-blue-600 text-sm mb-6 inline-flex items-center gap-1"><ArrowLeft size={14} /> Zum Shop</Link>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mt-2">
        <div className="aspect-square rounded-xl bg-slate-100 flex items-center justify-center overflow-hidden border border-slate-200">
          {product.images?.[0] ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={product.images[0]} alt={product.title} className="w-full h-full object-cover" />
          ) : (
            <Package size={64} strokeWidth={1} className="text-slate-300" />
          )}
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">{product.title}</h1>
          {product.subtitle && <p className="text-slate-500 mt-1">{product.subtitle}</p>}

          <div className="mt-5 flex items-baseline gap-3">
            <span className="text-3xl font-bold text-slate-900">{fmt(price?.gross, price?.currency ?? 'CHF')}</span>
            {price?.compare_at != null && (
              <span className="text-lg text-slate-400 line-through">{fmt(price.compare_at, price.currency)}</span>
            )}
            {price?.interval && (
              <span className="text-sm text-slate-500">/ {price.interval === 'year' ? 'Jahr' : 'Monat'}</span>
            )}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            inkl. MWST · Landeswährung &amp; finale Steuer werden an der Kasse berechnet.
          </div>
          <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
            {product.fulfillment === 'stock' ? 'Ab Lager – solange Vorrat reicht' : 'Auf Bestellung gefertigt'}
          </div>

          {product.description && (
            <p className="mt-5 text-sm text-slate-600 whitespace-pre-line leading-relaxed">{product.description}</p>
          )}

          <div className="mt-6 flex items-center gap-3">
            <label className="text-sm text-slate-500">Menge</label>
            <input type="number" min={1} value={qty}
              onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
              className="w-20 px-2.5 py-1.5 text-sm rounded-md border border-slate-200 outline-none focus:ring-2 focus:ring-blue-500" />
          </div>

          <button onClick={buy} disabled={buying || !price}
            className="mt-6 w-full inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 text-white font-semibold py-3 hover:bg-blue-700 transition-colors disabled:opacity-60">
            {buying ? <Loader2 size={18} className="animate-spin" /> : <ShoppingCart size={18} />}
            {user ? 'Kaufen' : 'Zum Kauf anmelden'}
          </button>
          {!authLoading && !user && (
            <p className="mt-2 text-xs text-slate-400 text-center">Für den Kauf ist eine Anmeldung erforderlich.</p>
          )}
          {error && <p className="mt-3 text-sm text-red-600">{error}</p>}
        </div>
      </div>
    </div>
  );
}

export default function ProductPage() {
  return (
    <Suspense fallback={<div className="max-w-4xl mx-auto px-6 py-12 text-slate-400 text-sm">Lädt…</div>}>
      <ProductView />
    </Suspense>
  );
}
