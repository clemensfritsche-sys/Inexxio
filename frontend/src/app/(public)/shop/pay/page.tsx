'use client';

import { Suspense, useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { CheckCircle2, XCircle, Loader2, CreditCard } from 'lucide-react';
import { api } from '@/lib/api';
import { useAuth } from '@/lib/auth-context';
import type { PaymentStatus } from '@/types';

function fmt(amount: number | string | null | undefined, currency: string): string {
  if (amount == null) return '—';
  return `${currency} ${Number(amount).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function PayView() {
  const search = useSearchParams();
  const token = search.get('token') || '';
  const { user, loading: authLoading } = useAuth();
  const [status, setStatus] = useState<PaymentStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function load() {
    try {
      setStatus(await api.getPaymentStatus(token));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Zahlung nicht gefunden');
    }
  }

  useEffect(() => {
    if (authLoading || !token) return;
    if (user) load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user, token]);

  async function simulate(result: 'paid' | 'cancelled') {
    setBusy(true);
    setError(null);
    try {
      await api.simulatePayment(token, result);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Aktion fehlgeschlagen');
    } finally {
      setBusy(false);
    }
  }

  if (authLoading) return <div className="max-w-md mx-auto px-6 py-16 text-slate-400 text-sm">Lädt…</div>;
  if (!user) return (
    <div className="max-w-md mx-auto px-6 py-16 text-center">
      <p className="text-slate-600">Bitte zuerst anmelden, um die Zahlung abzuschliessen.</p>
      <Link href="/login" className="mt-4 inline-block text-blue-600 font-semibold">Zur Anmeldung</Link>
    </div>
  );

  const done = status?.status === 'paid';
  const cancelled = status?.status === 'cancelled';

  return (
    <div className="max-w-md mx-auto px-6 py-16">
      <div className="rounded-xl border border-slate-200 bg-white shadow-sm p-8 text-center">
        {done ? (
          <>
            <CheckCircle2 size={48} className="mx-auto text-green-600" />
            <h1 className="mt-4 text-xl font-bold text-slate-900">Zahlung erfolgreich</h1>
            <p className="mt-2 text-sm text-slate-500">Vielen Dank! Ihr Auftrag {status?.order_object_id} wird bearbeitet.</p>
          </>
        ) : cancelled ? (
          <>
            <XCircle size={48} className="mx-auto text-red-600" />
            <h1 className="mt-4 text-xl font-bold text-slate-900">Zahlung abgebrochen</h1>
            <p className="mt-2 text-sm text-slate-500">Der Auftrag wurde storniert.</p>
          </>
        ) : (
          <>
            <CreditCard size={48} className="mx-auto text-blue-600" />
            <h1 className="mt-4 text-xl font-bold text-slate-900">Zahlung</h1>
            {status && (
              <p className="mt-2 text-2xl font-bold text-slate-900">{fmt(status.gross_total, status.currency)}</p>
            )}
            <p className="mt-1 text-xs text-slate-400">
              Auftrag {status?.order_object_id} · Provider: {status?.provider}
            </p>
            <p className="mt-4 text-xs text-slate-400">
              Testmodus (kein echter Zahlungsdienst): Zahlung simulieren.
            </p>
            <div className="mt-5 flex flex-col gap-2">
              <button onClick={() => simulate('paid')} disabled={busy || !status}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-green-600 text-white font-semibold py-3 hover:bg-green-700 disabled:opacity-60">
                {busy ? <Loader2 size={18} className="animate-spin" /> : <CheckCircle2 size={18} />} Zahlung simulieren (Erfolg)
              </button>
              <button onClick={() => simulate('cancelled')} disabled={busy || !status}
                className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-200 text-slate-600 font-semibold py-3 hover:bg-slate-50 disabled:opacity-60">
                <XCircle size={18} /> Abbrechen
              </button>
            </div>
          </>
        )}
        {error && <p className="mt-4 text-sm text-red-600">{error}</p>}
        <Link href="/shop" className="mt-6 inline-block text-blue-600 text-sm">Zurück zum Shop</Link>
      </div>
    </div>
  );
}

export default function PayPage() {
  return (
    <Suspense fallback={<div className="max-w-md mx-auto px-6 py-16 text-slate-400 text-sm">Lädt…</div>}>
      <PayView />
    </Suspense>
  );
}
