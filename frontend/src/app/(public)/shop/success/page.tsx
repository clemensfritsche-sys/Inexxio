'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { CheckCircle2, Loader2, Settings } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import { useCart } from '@/lib/cart-context';
import type { SaleStatus } from '@/types';

function SuccessView() {
  const search = useSearchParams();
  const sessionId = search.get('session_id') || '';
  const { user, loading: authLoading } = useAuth();
  const { clear } = useCart();
  const [status, setStatus] = useState<SaleStatus | null>(null);
  const [orderId, setOrderId] = useState<number | null>(null);
  const [tries, setTries] = useState(0);
  const [portalBusy, setPortalBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const s = await api.getCheckoutSession(sessionId);
      setStatus(s.status);
      setOrderId(s.order_object_id ?? (s.order_object_ids?.[0] ?? null));
    } catch { /* still processing */ }
  }, [sessionId]);

  // Der Webhook setzt den Status asynchron – kurz nachpollen, bis «paid».
  useEffect(() => {
    if (authLoading || !user || !sessionId) return;
    if (status === 'paid') { clear(); return; }   // bezahlt → Warenkorb leeren
    if (tries > 10) return;
    const t = setTimeout(() => { load(); setTries((n) => n + 1); }, tries === 0 ? 0 : 1500);
    return () => clearTimeout(t);
  }, [authLoading, user, sessionId, status, tries, load, clear]);

  async function openPortal() {
    setPortalBusy(true);
    try {
      const { url } = await api.openCustomerPortal();
      window.location.href = url;
    } catch { setPortalBusy(false); }
  }

  if (authLoading) return <div className="max-w-md mx-auto px-6 py-16 text-slate-400 text-sm">Lädt…</div>;
  if (!user) return (
    <div className="max-w-md mx-auto px-6 py-16 text-center">
      <p className="text-slate-600">Bitte anmelden, um den Bestellstatus zu sehen.</p>
      <Link href="/login" className="mt-4 inline-block text-blue-600 font-semibold">Zur Anmeldung</Link>
    </div>
  );

  const paid = status === 'paid';
  return (
    <div className="max-w-md mx-auto px-6 py-16">
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-8 text-center">
        {paid ? <CheckCircle2 size={48} className="mx-auto text-green-600" />
              : <Loader2 size={48} className="mx-auto text-blue-600 animate-spin" />}
        <h1 className="mt-4 text-xl font-bold text-slate-900">
          {paid ? 'Vielen Dank für deinen Kauf!' : 'Zahlung wird verarbeitet…'}
        </h1>
        <p className="mt-2 text-sm text-slate-500">
          {paid
            ? `Deine Bestellung ${orderId ?? ''} ist bestätigt und wird bearbeitet.`
            : 'Einen Moment – wir bestätigen deine Zahlung.'}
        </p>
        <button onClick={openPortal} disabled={portalBusy}
          className="mt-6 w-full inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 text-slate-700 font-semibold py-2.5 hover:bg-slate-50 disabled:opacity-60">
          {portalBusy ? <Loader2 size={16} className="animate-spin" /> : <Settings size={16} />}
          Zahlungen &amp; Abos verwalten
        </button>
        <Link href="/shop" className="mt-4 inline-block text-blue-600 text-sm">Weiter einkaufen</Link>
      </div>
    </div>
  );
}

export default function ShopSuccessPage() {
  return (
    <Suspense fallback={<div className="max-w-md mx-auto px-6 py-16 text-slate-400 text-sm">Lädt…</div>}>
      <SuccessView />
    </Suspense>
  );
}
