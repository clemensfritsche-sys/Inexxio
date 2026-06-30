'use client';

import { Package, RefreshCw } from 'lucide-react';
import type { CustomerOrder } from '@/types';

const STATUS: Record<string, { label: string; color: string; bg: string }> = {
  requested:  { label: 'Offen',          color: '#b45309', bg: '#fffbeb' },
  processing: { label: 'In Bearbeitung', color: '#2563eb', bg: '#eff6ff' },
  completed:  { label: 'Abgeschlossen',  color: '#16a34a', bg: '#f0fdf4' },
  cancelled:  { label: 'Storniert',      color: '#64748b', bg: '#f1f5f9' },
};

function fmtMoney(amount: number | string | null | undefined, currency: string): string {
  if (amount == null) return '—';
  return `${currency} ${Number(amount).toLocaleString('de-CH', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('de-CH');
}

function subLabel(o: CustomerOrder): string {
  const base = o.sub_type === 'product' ? 'Produktabo' : 'Nutzungsabo';
  const iv = o.interval === 'year' ? 'jährlich' : 'monatlich';
  return `${base} · ${iv}`;
}

export function OrdersList({ orders }: { orders: CustomerOrder[] }) {
  if (orders.length === 0) {
    return (
      <div className="text-center py-10 text-slate-400">
        <Package size={32} strokeWidth={1} className="mx-auto mb-2" />
        <p className="text-sm">Noch keine Bestellungen.</p>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2.5">
      {orders.map((o, idx) => {
        const st = STATUS[o.status] ?? STATUS.requested;
        return (
          <div key={`${o.order_object_id ?? idx}`} className="rounded-xl border border-slate-200 bg-white p-3.5">
            <div className="flex items-center gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="font-semibold text-slate-900 truncate">{o.title ?? 'Bestellung'}</span>
                  {o.is_subscription && (
                    <span className="inline-flex items-center gap-1 rounded-full bg-violet-50 text-violet-700 text-[11px] font-semibold px-2 py-0.5">
                      <RefreshCw size={11} /> {subLabel(o)}
                    </span>
                  )}
                </div>
                <div className="text-xs text-slate-400 mt-0.5">
                  {o.order_object_id ? `Auftrag ${o.order_object_id}` : ''}{o.created_at ? ` · ${fmtDate(o.created_at)}` : ''}
                  {o.quantity > 1 ? ` · ${o.quantity}×` : ''}
                </div>
              </div>
              <div className="text-right shrink-0">
                <div className="text-sm font-bold text-slate-900">{fmtMoney(o.gross_total, o.currency)}</div>
                <span className="inline-block mt-1 rounded-full px-2 py-0.5 text-[11px] font-semibold"
                  style={{ color: st.color, background: st.bg }}>{st.label}</span>
              </div>
            </div>
            {o.is_subscription && !o.subscription_active && (
              <div className="mt-2 text-[11px] text-slate-400">Abo gekündigt / nicht aktiv.</div>
            )}
          </div>
        );
      })}
    </div>
  );
}
