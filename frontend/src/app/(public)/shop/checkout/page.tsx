'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Loader2, ArrowLeft, CheckCircle2 } from 'lucide-react';
import { loadStripe, type Stripe } from '@stripe/stripe-js';
import { EmbeddedCheckoutProvider, EmbeddedCheckout } from '@stripe/react-stripe-js';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { useCart } from '@/lib/cart-context';

function CheckoutView() {
  const router = useRouter();
  const { user, loading: authLoading } = useAuth();
  const { items, hydrated, clear, currency } = useCart();
  const [clientSecret, setClientSecret] = useState<string | null>(null);
  const [pubKey, setPubKey] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(true);
  const [done, setDone] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    if (authLoading || !hydrated) return;     // erst handeln, wenn Auth + Warenkorb geladen sind
    if (!user) { setBusy(false); return; }
    // FIX: Nach dem Bezahlen leert onComplete den Warenkorb → dieser Effekt lief erneut und
    // der Leerer-Warenkorb-Redirect ersetzte die soeben angezeigte Danke-Ansicht sofort durch
    // «Dein Warenkorb ist leer». Nur umleiten, wenn die Kasse noch gar nicht gestartet wurde.
    if (items.length === 0) {
      if (!done && !started.current) router.replace('/shop/cart');
      return;
    }
    if (started.current) return;
    started.current = true;

    (async () => {
      try {
        const cfg = await api.getShopConfig();
        setPubKey(cfg.stripe_publishable_key);
        const payload = items.map((i) => ({
          article_object_id: i.article_object_id, price_id: i.price_id, quantity: i.quantity,
        }));
        const res = await api.shopCheckout(payload, currency);
        if (res.payment_url) { window.location.href = res.payment_url; return; }  // manual
        if (res.client_secret) { setClientSecret(res.client_secret); }
        else setError('Die Kasse konnte nicht gestartet werden.');
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Checkout fehlgeschlagen');
      } finally {
        setBusy(false);
      }
    })();
  }, [authLoading, hydrated, user, items, router, done, currency]);

  const stripePromise = useMemo<Promise<Stripe | null> | null>(
    () => (pubKey ? loadStripe(pubKey) : null), [pubKey]);

  // Lädt Stripe.js nicht (z. B. CSP/Netz), wird die eingebettete Kasse nie sichtbar →
  // statt endlosem Spinner einen klaren Fehler zeigen.
  useEffect(() => {
    if (!stripePromise) return;
    let alive = true;
    stripePromise
      .then((s) => { if (alive && !s) setError('Die Stripe-Kasse konnte nicht geladen werden.'); })
      .catch(() => { if (alive) setError('Die Stripe-Kasse konnte nicht geladen werden.'); });
    return () => { alive = false; };
  }, [stripePromise]);

  // Abschluss wird inline angezeigt (redirect_on_completion='never') – kein Erfolgs-Fenster.
  const onComplete = useCallback(() => { clear(); setDone(true); }, [clear]);
  const options = useMemo(() => (clientSecret ? { clientSecret, onComplete } : null), [clientSecret, onComplete]);

  if (done) {
    return (
      <div className="max-w-md mx-auto px-6 py-16 text-center">
        <CheckCircle2 size={48} className="mx-auto text-green-600" />
        <h1 className="mt-4 text-xl font-bold text-slate-900">Vielen Dank für deinen Kauf!</h1>
        <p className="mt-2 text-sm text-slate-500">Deine Bestellung ist bestätigt und wird bearbeitet.</p>
        <Link href="/konto" className="mt-6 inline-block rounded-lg bg-blue-600 text-white font-semibold py-2.5 px-5 hover:bg-blue-700">
          Meine Bestellungen
        </Link>
        <Link href="/shop" className="mt-4 block text-blue-600 text-sm">Weiter einkaufen</Link>
      </div>
    );
  }
  if (authLoading || (busy && !clientSecret && !error)) {
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
      {options && stripePromise && (
        <EmbeddedCheckoutProvider stripe={stripePromise} options={options}>
          <EmbeddedCheckout />
        </EmbeddedCheckoutProvider>
      )}
    </div>
  );
}

export default function CheckoutPage() {
  return <CheckoutView />;
}
