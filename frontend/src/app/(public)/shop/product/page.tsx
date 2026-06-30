'use client';

import { Suspense, useEffect, useMemo, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { Package, ArrowLeft, ShoppingCart, Check } from 'lucide-react';
import { api } from '@/lib/api';
import { useCart } from '@/lib/cart-context';
import type { ShopProduct, ShopPriceOption, CartItem } from '@/types';

function fmt(amount: number | string | null | undefined, currency: string): string {
  if (amount == null) return '—';
  return `${currency} ${Number(amount).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function optionLabel(o: ShopPriceOption): string {
  if (o.kind !== 'subscription') return 'Einmalkauf';
  const base = o.sub_type === 'product' ? 'Produktabo' : 'Nutzungsabo';
  const iv = o.interval === 'year' ? 'jährlich' : 'monatlich';
  return `${base} · ${iv}`;
}

function ProductView() {
  const search = useSearchParams();
  const router = useRouter();
  const cart = useCart();
  const objectId = Number(search.get('id'));

  const [product, setProduct] = useState<ShopProduct | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [qty, setQty] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [added, setAdded] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!objectId) { setLoading(false); return; }
    setLoading(true);
    api.getShopProduct(objectId)
      .then((p) => {
        setProduct(p);
        // Oberste Option vorselektieren (Backend liefert abo-first: Produktabo → Nutzungsabo → Einmalkauf).
        setSelectedId((p.prices ?? [])[0]?.price_id ?? null);
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Produkt nicht gefunden'))
      .finally(() => setLoading(false));
  }, [objectId]);

  const options = useMemo<ShopPriceOption[]>(() => product?.prices ?? [], [product]);
  const selected = useMemo<ShopPriceOption | undefined>(
    () => options.find((o) => o.price_id === selectedId) ?? options[0],
    [options, selectedId],
  );
  const isSub = selected?.kind === 'subscription';
  const view = selected?.view ?? product?.price ?? null;

  function addToCart(goToCart = false) {
    if (!product || !selected || !view) return;
    const item: CartItem = {
      article_object_id: product.object_id,
      price_id: selected.price_id,
      quantity: isSub ? 1 : qty,
      title: product.title,
      unit: product.unit,
      fulfillment: (product.fulfillment as CartItem['fulfillment']) ?? 'make',
      kind: selected.kind as CartItem['kind'],
      interval: (selected.interval as CartItem['interval']) ?? null,
      sub_type: (selected.sub_type as CartItem['sub_type']) ?? null,
      currency: view.currency,
      gross: Number(view.gross),
      image: product.images?.[0] ?? null,
    };
    const res = cart.add(item);
    if (!res.ok) { setNotice(res.reason ?? 'Konnte nicht hinzugefügt werden'); return; }
    setNotice(null);
    if (goToCart) { router.push('/shop/cart'); return; }
    setAdded(true);
    setTimeout(() => setAdded(false), 1800);
  }

  if (loading) return <div className="max-w-4xl mx-auto px-6 py-12 text-slate-400 text-sm">Lädt…</div>;
  if (!product) return (
    <div className="max-w-4xl mx-auto px-6 py-12">
      <p className="text-slate-500">{error ?? 'Produkt nicht gefunden.'}</p>
      <Link href="/shop" className="text-blue-600 text-sm mt-3 inline-flex items-center gap-1"><ArrowLeft size={14} /> Zum Shop</Link>
    </div>
  );

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
            <span className="text-3xl font-bold text-slate-900">{fmt(view?.gross, view?.currency ?? 'CHF')}</span>
            {view?.compare_at != null && (
              <span className="text-lg text-slate-400 line-through">{fmt(view.compare_at, view.currency)}</span>
            )}
            {isSub && (
              <span className="text-sm text-slate-500">/ {selected?.interval === 'year' ? 'Jahr' : 'Monat'}</span>
            )}
          </div>
          <div className="mt-1 text-xs text-slate-400">
            inkl. MWST · Landeswährung &amp; finale Steuer werden an der Kasse berechnet.
          </div>
          <div className="mt-2 inline-flex items-center gap-1.5 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
            {product.fulfillment === 'stock' ? 'Ab Lager – solange Vorrat reicht' : 'Auf Bestellung gefertigt'}
          </div>

          {/* Preis-Optionen (Einmalkauf / Nutzungsabo / Produktabo) */}
          {options.length > 1 && (
            <div className="mt-5 flex flex-col gap-2">
              <span className="text-sm font-semibold text-slate-700">Option wählen</span>
              {options.map((o) => {
                const active = o.price_id === selected?.price_id;
                return (
                  <button key={o.price_id} type="button" onClick={() => setSelectedId(o.price_id)}
                    className={`flex items-center justify-between rounded-lg border px-3.5 py-2.5 text-left transition-colors ${active ? 'border-blue-600 bg-blue-50' : 'border-slate-200 hover:border-slate-300'}`}>
                    <span className="text-sm font-medium text-slate-800">{optionLabel(o)}</span>
                    <span className="text-sm font-bold text-slate-900">
                      {fmt(o.view?.gross, o.view?.currency ?? 'CHF')}
                      {o.kind === 'subscription' && <span className="text-xs font-normal text-slate-500"> / {o.interval === 'year' ? 'Jahr' : 'Mt.'}</span>}
                    </span>
                  </button>
                );
              })}
            </div>
          )}
          {isSub && (
            <p className="mt-3 text-xs text-slate-500">
              {selected?.sub_type === 'product'
                ? 'Produktabo: wiederkehrende Lieferung – jederzeit kündbar, kein Enddatum.'
                : 'Nutzungsabo: laufender Zugang/Nutzung – jederzeit kündbar, kein Enddatum.'}
            </p>
          )}

          {product.description && (
            <p className="mt-5 text-sm text-slate-600 whitespace-pre-line leading-relaxed">{product.description}</p>
          )}

          {!isSub && (
            <div className="mt-6 flex items-center gap-3">
              <label className="text-sm text-slate-500">Menge</label>
              <input type="number" min={1} value={qty}
                onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
                className="w-20 px-2.5 py-1.5 text-sm rounded-md border border-slate-200 outline-none focus:ring-2 focus:ring-blue-500" />
            </div>
          )}

          <div className="mt-6 flex flex-col gap-2">
            <button onClick={() => addToCart(false)} disabled={!view}
              className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-blue-600 text-white font-semibold py-3 hover:bg-blue-700 transition-colors disabled:opacity-60">
              {added ? <Check size={18} /> : <ShoppingCart size={18} />}
              {added ? 'Hinzugefügt' : 'In den Warenkorb'}
            </button>
            <button onClick={() => addToCart(true)} disabled={!view}
              className="w-full inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 text-slate-700 font-semibold py-2.5 hover:bg-slate-50 disabled:opacity-60">
              Sofort zur Kasse
            </button>
          </div>
          {notice && <p className="mt-3 text-sm text-amber-600">{notice}</p>}
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
