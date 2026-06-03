'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Search, Package, Loader2, AlertCircle, CheckCircle2,
  ChevronDown, X, Tag, Filter
} from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Item, ItemStatus } from '@/types';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

const STATUS_CONFIG: Record<ItemStatus, { color: string; label: string }> = {
  Entwurf: { color: 'bg-slate-100 text-slate-600', label: 'Entwurf' },
  Freigegeben: { color: 'bg-green-50 text-green-700', label: 'Freigegeben' },
  Ersetzt: { color: 'bg-amber-50 text-amber-700', label: 'Ersetzt' },
  Gesperrt: { color: 'bg-red-50 text-red-700', label: 'Gesperrt' },
};

const TYPE_CONFIG = {
  Eigen: { color: 'bg-blue-50 text-blue-700', label: 'Eigen' },
  Kauf: { color: 'bg-purple-50 text-purple-700', label: 'Kauf' },
  Phantom: { color: 'bg-slate-50 text-slate-500', label: 'Phantom' },
};

const MOCK_ITEMS: Item[] = [
  {
    id: 1, number: '100000001', name: 'Hydraulikzylinder HZ-200', description: 'Doppeltwirkender Hydraulikzylinder, Hub 200mm, max. 250 bar.',
    unit: 'Stk', item_type: 'Eigen', status: 'Freigegeben', weight_kg: 4.8, dimensions: '320 × 90 mm',
    material: 'Stahl S355', surface_finish: 'Hartchrom', tolerance_class: 'H7', drawing_number: 'IX-HZ200-001',
    manufacturer: null, manufacturer_part_number: null, lead_time_days: 14,
    cost_price: '285.00', sales_price: '420.00', currency: 'CHF',
    tags: ['hydraulik', 'zylinder'], created_at: '2026-01-15T10:00:00Z', updated_at: '2026-05-20T14:32:00Z', created_by: 'admin@inexxio.com',
  },
  {
    id: 2, number: '100000002', name: 'Kolbenstange KS-150', description: 'Präzisionskolbenstange, geschliffen und hartverchromt.',
    unit: 'Stk', item_type: 'Eigen', status: 'Entwurf', weight_kg: 1.2, dimensions: '200 × 40 mm',
    material: 'Chrom-Stahl 42CrMo4', surface_finish: 'Hartchrom 20µm', tolerance_class: 'h6', drawing_number: 'IX-KS150-001',
    manufacturer: null, manufacturer_part_number: null, lead_time_days: 7,
    cost_price: '95.00', sales_price: '145.00', currency: 'CHF',
    tags: ['kolbenstange'], created_at: '2026-01-14T09:00:00Z', updated_at: '2026-05-18T11:00:00Z', created_by: 'admin@inexxio.com',
  },
  {
    id: 3, number: '100000003', name: 'Dichtungsset DS-10', description: 'Komplettes Dichtungsset für Hydraulikzylinder HZ-200.',
    unit: 'Set', item_type: 'Kauf', status: 'Freigegeben', weight_kg: 0.08, dimensions: null,
    material: 'NBR / PTFE', surface_finish: null, tolerance_class: null, drawing_number: null,
    manufacturer: 'Parker Hannifin', manufacturer_part_number: 'PH-DS-80-200', lead_time_days: 5,
    cost_price: '28.50', sales_price: '48.00', currency: 'CHF',
    tags: ['dichtung', 'kauf'], created_at: '2026-01-13T08:30:00Z', updated_at: '2026-05-10T09:00:00Z', created_by: 'admin@inexxio.com',
  },
  {
    id: 4, number: '100000004', name: 'Führungsring FR-80', description: 'Führungsring für Kolbenstange, PTFE-gefüllt.',
    unit: 'Stk', item_type: 'Kauf', status: 'Freigegeben', weight_kg: 0.02, dimensions: '80 × 5 mm',
    material: 'PTFE', surface_finish: null, tolerance_class: 'H8', drawing_number: null,
    manufacturer: 'Trelleborg', manufacturer_part_number: 'TR-GW-80-5', lead_time_days: 10,
    cost_price: '4.50', sales_price: '8.00', currency: 'CHF',
    tags: ['dichtung'], created_at: '2026-01-12T11:00:00Z', updated_at: '2026-04-20T09:00:00Z', created_by: 'admin@inexxio.com',
  },
];

function ArtikelPageInner() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<ItemStatus | 'all'>('all');
  const [typeFilter, setTypeFilter] = useState<Item['item_type'] | 'all'>('all');
  const [showCreate, setShowCreate] = useState(false);
  const [selectedItem, setSelectedItem] = useState<Item | null>(null);
  const [error, setError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['items'],
    queryFn: () => api.getItems(1, 100),
  });

  const items: Item[] = isError || !data ? MOCK_ITEMS : data.items;

  const filtered = items.filter((item) => {
    const q = search.toLowerCase();
    const matchesSearch =
      !q ||
      item.name.toLowerCase().includes(q) ||
      item.number.includes(q) ||
      (item.drawing_number || '').toLowerCase().includes(q) ||
      item.tags.some((t) => t.includes(q));
    const matchesStatus = statusFilter === 'all' || item.status === statusFilter;
    const matchesType = typeFilter === 'all' || item.item_type === typeFilter;
    return matchesSearch && matchesStatus && matchesType;
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<Item>) => api.createItem(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['items'] });
      setShowCreate(false);
    },
    onError: () => setError('Fehler beim Erstellen des Artikels.'),
  });

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
            <Package className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Artikel</h1>
            <p className="text-sm text-slate-500">
              {isError ? `${MOCK_ITEMS.length} Demo-Artikel` : `${items.length} Artikel`}
            </p>
          </div>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="btn-primary"
        >
          <Plus className="h-4 w-4" />
          Artikel erstellen
        </button>
      </div>

      {/* Errors */}
      {error && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={() => setError('')} className="ml-auto text-red-400 hover:text-red-600">
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {isError && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />
          <p className="text-sm text-amber-700">Demo-Modus: API nicht erreichbar. Demodaten werden angezeigt.</p>
        </div>
      )}

      {/* Filters */}
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
            <option value="Entwurf">Entwurf</option>
            <option value="Freigegeben">Freigegeben</option>
            <option value="Ersetzt">Ersetzt</option>
            <option value="Gesperrt">Gesperrt</option>
          </select>
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
        </div>
        <div className="relative">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value as Item['item_type'] | 'all')}
            className="form-input pr-8 appearance-none"
          >
            <option value="all">Alle Typen</option>
            <option value="Eigen">Eigen</option>
            <option value="Kauf">Kauf</option>
            <option value="Phantom">Phantom</option>
          </select>
          <ChevronDown className="absolute right-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
        </div>
      </div>

      {/* Table */}
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
                <th className="px-4 py-3 text-left font-medium text-slate-600 hidden sm:table-cell w-24">Typ</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 hidden md:table-cell w-24">Einheit</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 hidden lg:table-cell">Zeichnungs-Nr.</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600 hidden md:table-cell w-28">VK-Preis</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 w-28">Status</th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-500">
                    <Package className="mx-auto mb-3 h-8 w-8 text-slate-300" />
                    <p className="font-medium">Keine Artikel gefunden</p>
                    <p className="text-xs mt-1">
                      {search || statusFilter !== 'all' || typeFilter !== 'all'
                        ? 'Versuchen Sie andere Filterkriterien.'
                        : 'Erstellen Sie Ihren ersten Artikel.'}
                    </p>
                  </td>
                </tr>
              ) : (
                filtered.map((item) => {
                  const sc = STATUS_CONFIG[item.status] || STATUS_CONFIG.Entwurf;
                  const tc = TYPE_CONFIG[item.item_type] || TYPE_CONFIG.Eigen;
                  return (
                    <tr
                      key={item.id}
                      onClick={() => setSelectedItem(item)}
                      className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{item.number}</td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="font-medium text-slate-900">{item.name}</p>
                          {item.tags.length > 0 && (
                            <div className="mt-0.5 flex items-center gap-1">
                              <Tag className="h-3 w-3 text-slate-400" />
                              <span className="text-xs text-slate-400">{item.tags.join(', ')}</span>
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${tc.color}`}>
                          {tc.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-slate-600">{item.unit}</td>
                      <td className="px-4 py-3 hidden lg:table-cell font-mono text-xs text-slate-500">
                        {item.drawing_number || '—'}
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell text-right text-slate-700">
                        {item.sales_price
                          ? `${item.currency} ${parseFloat(item.sales_price).toLocaleString('de-CH', { minimumFractionDigits: 2 })}`
                          : '—'}
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

      {/* Detail Modal */}
      {selectedItem && (
        <ItemDetailModal item={selectedItem} onClose={() => setSelectedItem(null)} />
      )}

      {/* Create Modal */}
      {showCreate && (
        <CreateItemModal
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          saving={createMutation.isPending}
        />
      )}
    </div>
  );
}

function ItemDetailModal({ item, onClose }: { item: Item; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-2xl rounded-xl bg-white shadow-xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <div>
            <p className="text-xs font-mono text-slate-500 mb-0.5">{item.number}</p>
            <h2 className="text-xl font-bold text-slate-900">{item.name}</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-6">
          {/* Badges */}
          <div className="flex flex-wrap gap-2">
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_CONFIG[item.status]?.color}`}>
              {item.status}
            </span>
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${TYPE_CONFIG[item.item_type]?.color}`}>
              {item.item_type}
            </span>
            <span className="inline-flex items-center rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">
              {item.unit}
            </span>
          </div>

          {item.description && (
            <p className="text-sm text-slate-700 leading-relaxed">{item.description}</p>
          )}

          <div className="grid gap-x-6 gap-y-4 sm:grid-cols-2">
            <Detail label="Zeichnungs-Nr." value={item.drawing_number} />
            <Detail label="Material" value={item.material} />
            <Detail label="Oberfläche" value={item.surface_finish} />
            <Detail label="Toleranzklasse" value={item.tolerance_class} />
            <Detail label="Abmessungen" value={item.dimensions} />
            <Detail label="Gewicht" value={item.weight_kg ? `${item.weight_kg} kg` : null} />
            {item.manufacturer && <Detail label="Hersteller" value={item.manufacturer} />}
            {item.manufacturer_part_number && <Detail label="Hersteller-Artikelnr." value={item.manufacturer_part_number} />}
            <Detail label="Lieferzeit" value={item.lead_time_days ? `${item.lead_time_days} Tage` : null} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2 rounded-lg border border-slate-200 p-4">
            <div>
              <p className="text-xs text-slate-500 mb-0.5">Einkaufspreis</p>
              <p className="text-lg font-semibold text-slate-900">
                {item.cost_price
                  ? `${item.currency} ${parseFloat(item.cost_price).toLocaleString('de-CH', { minimumFractionDigits: 2 })}`
                  : '—'}
              </p>
            </div>
            <div>
              <p className="text-xs text-slate-500 mb-0.5">Verkaufspreis</p>
              <p className="text-lg font-semibold text-blue-700">
                {item.sales_price
                  ? `${item.currency} ${parseFloat(item.sales_price).toLocaleString('de-CH', { minimumFractionDigits: 2 })}`
                  : '—'}
              </p>
            </div>
          </div>

          {item.tags.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {item.tags.map((tag) => (
                <span key={tag} className="flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600">
                  <Tag className="h-3 w-3" />
                  {tag}
                </span>
              ))}
            </div>
          )}

          <p className="text-xs text-slate-400">
            Erstellt: {new Date(item.created_at).toLocaleDateString('de-CH')} ·
            Zuletzt geändert: {new Date(item.updated_at).toLocaleDateString('de-CH')}
          </p>
        </div>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string | number | null | undefined }) {
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
  const [form, setForm] = useState({
    name: '',
    unit: 'Stk',
    item_type: 'Eigen' as Item['item_type'],
    description: '',
    drawing_number: '',
    material: '',
    cost_price: '',
    sales_price: '',
  });

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      name: form.name,
      unit: form.unit,
      item_type: form.item_type,
      description: form.description || null,
      drawing_number: form.drawing_number || null,
      material: form.material || null,
      cost_price: form.cost_price || null,
      sales_price: form.sales_price || null,
      currency: 'CHF',
      tags: [],
      status: 'Entwurf',
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-lg rounded-xl bg-white shadow-xl mx-4"
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
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Typ *</label>
                <select
                  value={form.item_type}
                  onChange={(e) => setForm({ ...form, item_type: e.target.value as Item['item_type'] })}
                  className="form-input"
                >
                  <option value="Eigen">Eigen</option>
                  <option value="Kauf">Kauf</option>
                  <option value="Phantom">Phantom</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Einheit *</label>
                <select
                  value={form.unit}
                  onChange={(e) => setForm({ ...form, unit: e.target.value })}
                  className="form-input"
                >
                  <option value="Stk">Stk</option>
                  <option value="m">m</option>
                  <option value="kg">kg</option>
                  <option value="Set">Set</option>
                  <option value="l">l</option>
                </select>
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Zeichnungs-Nr.</label>
                <input
                  value={form.drawing_number}
                  onChange={(e) => setForm({ ...form, drawing_number: e.target.value })}
                  className="form-input"
                  placeholder="IX-HZ300-001"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">Material</label>
                <input
                  value={form.material}
                  onChange={(e) => setForm({ ...form, material: e.target.value })}
                  className="form-input"
                  placeholder="z.B. Stahl S355"
                />
              </div>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">EK-Preis (CHF)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.cost_price}
                  onChange={(e) => setForm({ ...form, cost_price: e.target.value })}
                  className="form-input"
                  placeholder="0.00"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">VK-Preis (CHF)</label>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  value={form.sales_price}
                  onChange={(e) => setForm({ ...form, sales_price: e.target.value })}
                  className="form-input"
                  placeholder="0.00"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Beschreibung</label>
              <textarea
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="form-input resize-none"
                rows={3}
                placeholder="Technische Beschreibung des Artikels…"
              />
            </div>
          </div>

          <div className="flex justify-end gap-3 border-t border-slate-100 px-6 py-4">
            <button type="button" onClick={onClose} className="btn-secondary">
              Abbrechen
            </button>
            <button type="submit" disabled={saving || !form.name} className="btn-primary disabled:opacity-50">
              {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Speichert…</> : <><CheckCircle2 className="h-4 w-4" /> Erstellen</>}
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
