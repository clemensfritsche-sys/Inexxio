'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Search, Package, Loader2, AlertCircle,
  ChevronDown, X, Filter, CheckCircle2, Send,
  RefreshCw, Ban, Trash2, ExternalLink, Layers,
} from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Item, ItemStatus } from '@/types';
import { ITEM_STATUS_CONFIG } from '@/types';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 30_000 } },
});

type CreateForm = {
  name: string;
  unit: string;
  batch_allowed: boolean;
  order_number: string;
  purchase_price: string;
  purchase_currency: string;
  is_sales_product: boolean;
  sales_price: string;
  weight_g: string;
  dim_1_mm: string;
  dim_2_mm: string;
  dim_3_mm: string;
  hs_code: string;
};

function ArtikelPageInner() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<ItemStatus | 'all'>('all');
  const [showCreate, setShowCreate] = useState(false);
  const [selected, setSelected] = useState<Item | null>(null);
  const [actionError, setActionError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['items', statusFilter, search],
    queryFn: () =>
      api.getItems({
        q: search || undefined,
        status: statusFilter === 'all' ? undefined : statusFilter,
        pageSize: 100,
      }),
  });

  const items: Item[] = data?.items ?? [];

  function mutationOpts(successMsg?: string) {
    return {
      onSuccess: (updated: Item) => {
        qc.invalidateQueries({ queryKey: ['items'] });
        if (selected?.id === updated.id) setSelected(updated);
        if (successMsg) setActionError('');
      },
      onError: (e: Error) => setActionError(e.message),
    };
  }

  const submitMut = useMutation({ mutationFn: (id: number) => api.submitItem(id), ...mutationOpts() });
  const approveMut = useMutation({ mutationFn: (id: number) => api.approveItem(id), ...mutationOpts() });
  const replaceMut = useMutation({ mutationFn: (id: number) => api.replaceItem(id), ...mutationOpts() });
  const invalidateMut = useMutation({ mutationFn: (id: number) => api.invalidateItem(id), ...mutationOpts() });
  const deleteMut = useMutation({
    mutationFn: (id: number) => api.deleteItem(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['items'] });
      setSelected(null);
    },
    onError: (e: Error) => setActionError(e.message),
  });
  const createMut = useMutation({
    mutationFn: (d: Partial<Item>) => api.createItem(d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['items'] });
      setShowCreate(false);
    },
    onError: (e: Error) => setActionError(e.message),
  });

  const isPending =
    submitMut.isPending || approveMut.isPending || replaceMut.isPending ||
    invalidateMut.isPending || deleteMut.isPending;

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
            <Package className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Artikel</h1>
            <p className="text-sm text-slate-500">{isLoading ? '…' : `${items.length} Artikel`}</p>
          </div>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary">
          <Plus className="h-4 w-4" />
          Artikel erstellen
        </button>
      </div>

      {actionError && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
          <p className="text-sm text-red-700">{actionError}</p>
          <button onClick={() => setActionError('')} className="ml-auto text-red-400 hover:text-red-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {isError && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />
          <p className="text-sm text-amber-700">API nicht erreichbar.</p>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Artikel suchen…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="form-input pl-10"
          />
        </div>
        <div className="relative">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400" />
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as ItemStatus | 'all')}
            className="form-input pl-9 pr-8 appearance-none"
          >
            <option value="all">Alle Status</option>
            {(Object.keys(ITEM_STATUS_CONFIG) as ItemStatus[]).map((s) => (
              <option key={s} value={s}>{ITEM_STATUS_CONFIG[s].label}</option>
            ))}
          </select>
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
        </div>
      </div>

      <div className="card overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-3 text-left font-medium text-slate-600 w-32">Nr.</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Bezeichnung</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 hidden md:table-cell w-20">Einheit</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600 hidden md:table-cell w-32">EK-Preis</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600 hidden md:table-cell w-28">Lager</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 w-32">Status</th>
              </tr>
            </thead>
            <tbody>
              {items.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-slate-500">
                    <Package className="mx-auto mb-3 h-8 w-8 text-slate-300" />
                    <p className="font-medium">Keine Artikel gefunden</p>
                    <p className="text-xs mt-1">Erstellen Sie Ihren ersten Artikel.</p>
                  </td>
                </tr>
              ) : (
                items.map((item) => {
                  const sc = ITEM_STATUS_CONFIG[item.status as ItemStatus] ?? ITEM_STATUS_CONFIG.ENTWURF;
                  return (
                    <tr
                      key={item.id}
                      onClick={() => setSelected(item)}
                      className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">
                        {String(item.id).padStart(9, '0')}
                      </td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-900">{item.name}</p>
                        {item.batch_allowed && (
                          <span className="text-xs text-blue-600 flex items-center gap-0.5 mt-0.5">
                            <Layers className="h-3 w-3" /> Batch
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-slate-600">{item.unit}</td>
                      <td className="px-4 py-3 hidden md:table-cell text-right text-slate-700">
                        {item.purchase_price
                          ? `${item.purchase_currency} ${parseFloat(item.purchase_price).toLocaleString('de-CH', { minimumFractionDigits: 2 })}`
                          : '—'}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-right text-slate-700">
                        {parseFloat(item.stock_total).toLocaleString('de-CH', { maximumFractionDigits: 1 })}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${sc.color}`}>
                          {sc.label}
                        </span>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        )}
      </div>

      {selected && (
        <ItemDetailPanel
          item={selected}
          onClose={() => setSelected(null)}
          onSubmit={() => submitMut.mutate(selected.id)}
          onApprove={() => approveMut.mutate(selected.id)}
          onReplace={() => replaceMut.mutate(selected.id)}
          onInvalidate={() => invalidateMut.mutate(selected.id)}
          onDelete={() => {
            if (confirm('Artikel wirklich löschen?')) deleteMut.mutate(selected.id);
          }}
          isPending={isPending}
        />
      )}

      {showCreate && (
        <CreateItemModal
          onClose={() => setShowCreate(false)}
          onSubmit={(d) => createMut.mutate(d)}
          saving={createMut.isPending}
        />
      )}
    </div>
  );
}

interface DetailProps {
  item: Item;
  onClose: () => void;
  onSubmit: () => void;
  onApprove: () => void;
  onReplace: () => void;
  onInvalidate: () => void;
  onDelete: () => void;
  isPending: boolean;
}

function ItemDetailPanel({ item, onClose, onSubmit, onApprove, onReplace, onInvalidate, onDelete, isPending }: DetailProps) {
  const sc = ITEM_STATUS_CONFIG[item.status as ItemStatus] ?? ITEM_STATUS_CONFIG.ENTWURF;
  const isEntwurf = item.status === 'ENTWURF';
  const isInFreigabe = item.status === 'IN_FREIGABE';
  const isFreigegeben = item.status === 'FREIGEGEBEN';
  const isTerminal = item.status === 'ERSETZT' || item.status === 'UNGUELTIG';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-2xl rounded-xl bg-white shadow-xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <div>
            <p className="text-xs font-mono text-slate-500 mb-0.5">{String(item.id).padStart(9, '0')}</p>
            <h2 className="text-xl font-bold text-slate-900">{item.name}</h2>
          </div>
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${sc.color}`}>
              {sc.label}
            </span>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" />
            </button>
          </div>
        </div>

        <div className="p-6 space-y-5">
          <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            <Field label="Einheit" value={item.unit} />
            <Field label="Batch erlaubt" value={item.batch_allowed ? 'Ja' : 'Nein'} />
            {item.order_number && <Field label="Bestellnummer" value={item.order_number} />}
            {item.lead_time_days && <Field label="Lieferzeit" value={`${item.lead_time_days} Tage`} />}
            {item.weight_g && <Field label="Gewicht" value={`${item.weight_g} g`} />}
            {(item.dim_1_mm || item.dim_2_mm || item.dim_3_mm) && (
              <Field
                label="Abmessungen (mm)"
                value={[item.dim_1_mm, item.dim_2_mm, item.dim_3_mm].filter(Boolean).join(' × ')}
              />
            )}
          </div>

          <div className="grid gap-4 sm:grid-cols-2 rounded-lg border border-slate-200 p-4">
            <div>
              <p className="text-xs text-slate-500 mb-0.5">Einkaufspreis</p>
              <p className="text-lg font-semibold text-slate-900">
                {item.purchase_price
                  ? `${item.purchase_currency} ${parseFloat(item.purchase_price).toLocaleString('de-CH', { minimumFractionDigits: 2 })}`
                  : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500 mb-0.5">Verkaufspreis</p>
              <p className="text-lg font-semibold text-blue-700">
                {item.is_sales_product && item.sales_price
                  ? `${item.sales_currency} ${parseFloat(item.sales_price).toLocaleString('de-CH', { minimumFractionDigits: 2 })}`
                  : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500 mb-0.5">Lagerbestand</p>
              <p className="text-base font-semibold text-slate-900">
                {parseFloat(item.stock_total).toLocaleString('de-CH', { maximumFractionDigits: 3 })} {item.unit}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500 mb-0.5">Reserviert</p>
              <p className="text-base font-semibold text-slate-600">
                {parseFloat(item.stock_reserved).toLocaleString('de-CH', { maximumFractionDigits: 3 })} {item.unit}
              </p>
            </div>
          </div>

          {(item.order_link || item.onshape_link) && (
            <div className="flex gap-3">
              {item.order_link && (
                <a href={item.order_link} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                  <ExternalLink className="h-3.5 w-3.5" /> Bestelllink
                </a>
              )}
              {item.onshape_link && (
                <a href={item.onshape_link} target="_blank" rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-sm text-blue-600 hover:underline">
                  <ExternalLink className="h-3.5 w-3.5" /> Onshape
                </a>
              )}
            </div>
          )}

          {item.signatures.length > 0 && (
            <div>
              <p className="text-xs text-slate-500 mb-2">Freigabe-Signaturen</p>
              {item.signatures.map((sig) => (
                <p key={sig.id} className="text-xs text-slate-600">
                  Benutzer #{sig.signed_by} · {new Date(sig.signed_at).toLocaleString('de-CH')}
                </p>
              ))}
            </div>
          )}

          <p className="text-xs text-slate-400">
            Erstellt: {new Date(item.created_at).toLocaleDateString('de-CH')} ·
            Geändert: {new Date(item.updated_at).toLocaleDateString('de-CH')}
          </p>

          {!isTerminal && (
            <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
              {isEntwurf && (
                <>
                  <button
                    disabled={isPending}
                    onClick={onSubmit}
                    className="btn-primary disabled:opacity-50 text-sm"
                  >
                    <Send className="h-3.5 w-3.5" /> Zur Freigabe einreichen
                  </button>
                  <button
                    disabled={isPending}
                    onClick={onDelete}
                    className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
                  >
                    <Trash2 className="h-3.5 w-3.5" /> Löschen
                  </button>
                </>
              )}
              {isInFreigabe && (
                <button
                  disabled={isPending}
                  onClick={onApprove}
                  className="flex items-center gap-1.5 rounded-lg bg-green-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
                >
                  <CheckCircle2 className="h-3.5 w-3.5" /> Freigeben
                </button>
              )}
              {isFreigegeben && (
                <>
                  <button
                    disabled={isPending}
                    onClick={onReplace}
                    className="flex items-center gap-1.5 rounded-lg border border-blue-200 bg-blue-50 px-3 py-1.5 text-sm font-medium text-blue-600 hover:bg-blue-100 disabled:opacity-50"
                  >
                    <RefreshCw className="h-3.5 w-3.5" /> Als ersetzt markieren
                  </button>
                  <button
                    disabled={isPending}
                    onClick={onInvalidate}
                    className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-sm font-medium text-red-600 hover:bg-red-100 disabled:opacity-50"
                  >
                    <Ban className="h-3.5 w-3.5" /> Ungültig erklären
                  </button>
                </>
              )}
              {isPending && <Loader2 className="h-4 w-4 animate-spin text-slate-400 self-center" />}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (!value) return null;
  return (
    <div>
      <p className="text-xs text-slate-500">{label}</p>
      <p className="text-sm font-medium text-slate-800 mt-0.5">{value}</p>
    </div>
  );
}

function CreateItemModal({
  onClose,
  onSubmit,
  saving,
}: {
  onClose: () => void;
  onSubmit: (data: Partial<Item>) => void;
  saving: boolean;
}) {
  const [form, setForm] = useState<CreateForm>({
    name: '',
    unit: 'Stk',
    batch_allowed: false,
    order_number: '',
    purchase_price: '',
    purchase_currency: 'CHF',
    is_sales_product: false,
    sales_price: '',
    weight_g: '',
    dim_1_mm: '',
    dim_2_mm: '',
    dim_3_mm: '',
    hs_code: '',
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const payload: Partial<Item> = {
      name: form.name,
      unit: form.unit,
      batch_allowed: form.batch_allowed,
      order_number: form.order_number || null,
      purchase_price: form.purchase_price || null,
      purchase_currency: form.purchase_currency,
      is_sales_product: form.is_sales_product,
      sales_price: form.is_sales_product && form.sales_price ? form.sales_price : null,
      weight_g: form.weight_g || null,
      dim_1_mm: form.dim_1_mm || null,
      dim_2_mm: form.dim_2_mm || null,
      dim_3_mm: form.dim_3_mm || null,
      hs_code: form.hs_code || null,
    };
    onSubmit(payload);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-lg rounded-xl bg-white shadow-xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <form onSubmit={handleSubmit}>
          <div className="flex items-center justify-between border-b border-slate-200 p-6">
            <h2 className="text-lg font-bold text-slate-900">Neuer Artikel</h2>
            <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Bezeichnung *</label>
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="form-input"
                placeholder="z.B. Hydraulikzylinder HZ-300"
              />
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Einheit</label>
                <select
                  value={form.unit}
                  onChange={(e) => setForm({ ...form, unit: e.target.value })}
                  className="form-input"
                >
                  <option value="Stk">Stk</option>
                  <option value="mm">mm</option>
                  <option value="g">g</option>
                  <option value="mm²">mm²</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Bestellnummer</label>
                <input
                  value={form.order_number}
                  onChange={(e) => setForm({ ...form, order_number: e.target.value })}
                  className="form-input"
                  placeholder="AB-12345"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">EK-Preis</label>
                <input
                  type="number" step="0.01" min="0"
                  value={form.purchase_price}
                  onChange={(e) => setForm({ ...form, purchase_price: e.target.value })}
                  className="form-input"
                  placeholder="0.00"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Gewicht (g)</label>
                <input
                  type="number" step="0.01" min="0"
                  value={form.weight_g}
                  onChange={(e) => setForm({ ...form, weight_g: e.target.value })}
                  className="form-input"
                  placeholder="0.00"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              {(['dim_1_mm', 'dim_2_mm', 'dim_3_mm'] as const).map((k, i) => (
                <div key={k}>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">Dim. {i + 1} (mm)</label>
                  <input
                    type="number" step="0.01" min="0"
                    value={form[k]}
                    onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                    className="form-input"
                    placeholder="0.00"
                  />
                </div>
              ))}
            </div>

            <div className="flex items-center gap-3">
              <input
                type="checkbox" id="batch"
                checked={form.batch_allowed}
                onChange={(e) => setForm({ ...form, batch_allowed: e.target.checked })}
                className="rounded border-slate-300"
              />
              <label htmlFor="batch" className="text-sm text-slate-700">Batch-Fertigung erlaubt</label>
            </div>

            <div className="flex items-center gap-3">
              <input
                type="checkbox" id="sales"
                checked={form.is_sales_product}
                onChange={(e) => setForm({ ...form, is_sales_product: e.target.checked })}
                className="rounded border-slate-300"
              />
              <label htmlFor="sales" className="text-sm text-slate-700">Verkaufsartikel</label>
            </div>

            {form.is_sales_product && (
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">VK-Preis *</label>
                <input
                  required
                  type="number" step="0.01" min="0"
                  value={form.sales_price}
                  onChange={(e) => setForm({ ...form, sales_price: e.target.value })}
                  className="form-input"
                  placeholder="0.00"
                />
              </div>
            )}
          </div>

          <div className="flex justify-end gap-3 border-t border-slate-100 px-6 py-4">
            <button type="button" onClick={onClose} className="btn-secondary">Abbrechen</button>
            <button type="submit" disabled={saving || !form.name} className="btn-primary disabled:opacity-50">
              {saving
                ? <><Loader2 className="h-4 w-4 animate-spin" /> Speichert…</>
                : <><CheckCircle2 className="h-4 w-4" /> Erstellen</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function ArtikelPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <ArtikelPageInner />
    </QueryClientProvider>
  );
}
