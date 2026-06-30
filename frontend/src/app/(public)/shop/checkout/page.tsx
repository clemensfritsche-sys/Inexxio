'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2, ArrowLeft } from 'lucide-react';
import { loadStripe, type Stripe } from '@stripe/stripe-js';
import { EmbeddedCheckoutProvider, EmbeddedCheckout } from '@stripe/react-stripe-js';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { useCart } from '@/lib/cart-context';

function CheckoutView() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { items } = useCart();
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [pubKey, setPubKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const started = useRef(false);

  useEffect(() => {
    if (authLoading) return;
    if (!user) { setBusy(false); return; }
    if (items.length === 0) { router.replace('/shop'); return; }
    if (started.current) return;
    started.current = true;

    (async () => {
      try {
        const cfg = await api.getShopConfig();
        setPubKey(cfg.stripe_publishable_key);
        const payload = items.map((i) => ({
          article_object_id: i.article_object_id, price_id: i.price_id, quantity: i.quantity,
        }));
        const res = await api.shopCheckout(payload);
        if (res.payment_url) { window.location.href = res.payment_url; return; }  // manual
        if (res.client_secret) { setClientSecret(res.client_secret); }
        else setError('Die Kasse konnte nicht gestartet werden.');
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Checkout fehlgeschlagen');
      } finally {
        setBusy(false);
      }
    })();
  }, [authLoading, user, items, router]);

  const stripePromise = useMemo<Promise<Stripe | null> | null>(
    () => (pubKey ? loadStripe(pubKey) : null), [pubKey]);

  if (authLoading || (busy && !clientSecret)) {
    return <div className="max-w-2xl mx-auto px-6 py-20 text-center text-slate-400"><Loader2 className="mx-auto animate-spin" /> <span className="text-sm">Kasse wird geladen…</span></div>;
  }
  if (!user) return (
    <div className="max-w-md mx-auto px-6 py-16 text-center">
      <p className="text-slate-600">Bitte zuerst anmelden, um zur Kasse zu gehen.</p>
      <Link href="/login" className="mt-4 inline-block text-blue-600 font-semibold">Zur Anmeldung</Link>
    </div>
  );
  if (error || (clientSecret && !stripePromise)) return (
    <div className="max-w-md mx-auto px-6 py-16 text-center">
      <p className="text-red-600">{error ?? 'Stripe Publishable Key fehlt – bitte in Admin → Systemkonfiguration hinterlegen.'}</p>
      <Link href="/shop/cart" className="mt-4 inline-flex items-center gap-1 text-blue-600 text-sm"><ArrowLeft size={14} /> Zurück zum Warenkorb</Link>
    </div>
  );

  return (
    <div className="max-w-2xl mx-auto px-6 py-8">
      <Link href="/shop/cart" className="text-blue-600 text-sm mb-4 inline-flex items-center gap-1"><ArrowLeft size={14} /> Warenkorb</Link>
      {clientSecret && stripePromise && (
        <EmbeddedCheckoutProvider stripe={stripePromise} options={{ clientSecret }}>
          <EmbeddedCheckout />
        </EmbeddedCheckoutProvider>
      )}
    </div>
  );
}

export default function CheckoutPage() {
  return <CheckoutView />;
}
