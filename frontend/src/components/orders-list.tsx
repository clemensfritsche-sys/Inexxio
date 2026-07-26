'use client';

import { useState } from 'react';
import { Package, RefreshCw, Loader2, Undo2, CheckCircle2 } from 'lucide-react';
import type { CustomerOrder } from '@/types';
import { formatMoney as fmtMoney } from '@/lib/utils';

// Dieselbe Ampel + dieselben Worte wie im ERP: offen/laufend = GELB, erledigt = GRÜN,
// storniert = ROT. Tokens statt Hex.
const STATUS: Record<string, { label: string; color: string; bg: string }> = {
  requested:  { label: 'Offen',         color: 'var(--warning)', bg: 'var(--warning-bg)' },
  processing: { label: 'In Arbeit',     color: 'var(--warning)', bg: 'var(--warning-bg)' },
  completed:  { label: 'Abgeschlossen', color: 'var(--success)', bg: 'var(--success-bg)' },
  cancelled:  { label: 'Storniert',     color: 'var(--danger)',  bg: 'var(--danger-bg)' },
};


function fmtDate(iso: string | null | undefined): string {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('de-CH');
}

function subLabel(o: CustomerOrder): string {
  const base = o.sub_type === 'product' ? 'Produktabo' : 'Nutzungsabo';
  const iv = o.interval === 'year' ? 'jährlich' : 'monatlich';
  return `${base} · ${iv}`;
}

// Mindestbindung eines Produktabos (Backend: ``sales.earliest_cancellation_date`` – nur
// bei ``sub_type='product'``, ein Nutzungsabo hat keine). ``null`` = bereits kündbar.
function lockedUntil(o: CustomerOrder): string | null {
  if (!o.cancellable_from) return null;
  return new Date(o.cancellable_from) > new Date() ? o.cancellable_from : null;
}

export function OrdersList({ orders, onCancel, onReturn }: {
  orders: CustomerOrder[];
  onCancel?: (orderObjectId: number) => Promise<void>;
  onReturn?: (orderObjectId: number, reason: string | null) => Promise<void>;
}) {
  const [busyId, setBusyId] = useState<number | null>(null);

  async function cancel(o: CustomerOrder) {
    if (!onCancel || !o.order_object_id) return;
    if (!window.confirm('Abo wirklich kündigen? Es wird sofort beendet.')) return;
    setBusyId(o.order_object_id);
    try { await onCancel(o.order_object_id); } finally { setBusyId(null); }
  }

  async function requestReturn(o: CustomerOrder) {
    if (!onReturn || !o.order_object_id) return;
    const reason = window.prompt('Retoure anfragen – Grund (optional):', '');
    if (reason === null) return;   // abgebrochen
    setBusyId(o.order_object_id);
    try { await onReturn(o.order_object_id, reason.trim() || null); } finally { setBusyId(null); }
  }

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
            {o.is_subscription && o.subscription_active && onCancel && (() => {
              const locked = lockedUntil(o);
              return (
                <div className="mt-2 flex justify-end">
                  <button onClick={() => cancel(o)} disabled={busyId === o.order_object_id || !!locked}
                    title={locked ? `Mindestlaufzeit – kündbar ab ${fmtDate(locked)}` : undefined}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 text-red-600 text-xs font-semibold py-1.5 px-3 hover:bg-red-50 disabled:opacity-60 disabled:hover:bg-transparent disabled:cursor-not-allowed">
                    {busyId === o.order_object_id ? <Loader2 size={13} className="animate-spin" /> : null}
                    {locked ? `Kündbar ab ${fmtDate(locked)}` : 'Abo kündigen'}
                  </button>
                </div>
              );
            })()}
            {o.is_subscription && !o.subscription_active && (
              <div className="mt-2 text-[11px] text-slate-400">Abo gekündigt / nicht aktiv.</div>
            )}
            {/* Retoure/Rückgabe (Online-Shop-Logik) – nur für abgeschlossene, retournierbare
                Bestellungen im Rückgabefenster. Nach der Anfrage: Bestätigung + Frist-Hinweis. */}
            {!o.is_subscription && o.return_requested && (
              <div className="mt-2 inline-flex items-center gap-1.5 text-[11px] text-cyan-700">
                <CheckCircle2 size={12} /> Retoure angefragt – wird bearbeitet.
              </div>
            )}
            {!o.is_subscription && o.returnable && onReturn && (
              <div className="mt-2 flex items-center justify-between gap-2">
                {o.return_deadline && (
                  <span className="text-[11px] text-slate-400">Rückgabe bis {fmtDate(o.return_deadline)}</span>
                )}
                <button onClick={() => requestReturn(o)} disabled={busyId === o.order_object_id}
                  className="ml-auto inline-flex items-center gap-1.5 rounded-lg border border-cyan-200 text-cyan-700 text-xs font-semibold py-1.5 px-3 hover:bg-cyan-50 disabled:opacity-60 disabled:cursor-not-allowed">
                  {busyId === o.order_object_id ? <Loader2 size={13} className="animate-spin" /> : <Undo2 size={13} />}
                  Retoure anfragen
                </button>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
