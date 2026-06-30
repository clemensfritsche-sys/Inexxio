'use client';

import { useEffect, useState } from 'react';
import { ShoppingBag, Settings, Loader2 } from 'lucide-react';
import { api } from '@/lib/api';
import { OrdersList } from '@/components/orders-list';
import type { CustomerOrder } from '@/types';

export function OrdersSection() {
  const [orders, setOrders] = useState<CustomerOrder[] | null>(null);
  const [portalBusy, setPortalBusy] = useState(false);

  useEffect(() => {
    api.getMyOrders().then(setOrders).catch(() => setOrders([]));
  }, []);

  const hasSubscription = (orders ?? []).some((o) => o.has_subscription_management);

  async function openPortal() {
    setPortalBusy(true);
    try {
      const { url } = await api.openCustomerPortal();
      window.location.href = url;
    } catch { setPortalBusy(false); }
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #E2E8F0', borderRadius: 12, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '18px 24px', borderBottom: '1px solid #F1F5F9' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ShoppingBag style={{ width: 16, height: 16, color: '#64748b' }} />
          <h2 style={{ fontSize: 15, fontWeight: 600, color: '#0F172A', margin: 0 }}>Bestellungen &amp; Abos</h2>
        </div>
        {hasSubscription && (
          <button onClick={openPortal} disabled={portalBusy}
            className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 text-slate-700 text-sm font-semibold py-1.5 px-3 hover:bg-slate-50 disabled:opacity-60">
            {portalBusy ? <Loader2 size={14} className="animate-spin" /> : <Settings size={14} />}
            Abos verwalten
          </button>
        )}
      </div>
      <div style={{ padding: 24 }}>
        {orders === null ? (
          <div className="flex items-center justify-center py-10 text-slate-400"><Loader2 className="animate-spin" /></div>
        ) : (
          <OrdersList orders={orders} />
        )}
        {orders !== null && orders.length > 0 && !hasSubscription && (
          <p className="mt-4 text-xs text-slate-400">Zahlungsmittel &amp; Abos verwaltest du über das Stripe-Kundenportal, sobald ein Abo besteht.</p>
        )}
      </div>
    </div>
  );
}
