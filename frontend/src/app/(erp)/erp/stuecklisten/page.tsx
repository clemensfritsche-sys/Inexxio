'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Search, Layers, Loader2, AlertCircle, X, ChevronRight, CheckCircle2
} from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { BOM, BOMStatus } from '@/types';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

const STATUS_CONFIG: Record<BOMStatus, { color: string }> = {
  Entwurf: { color: 'bg-slate-100 text-slate-600' },
  Freigegeben: { color: 'bg-green-50 text-green-700' },
  Archiviert: { color: 'bg-slate-50 text-slate-400' },
};

const MOCK_BOMS: BOM[] = [
  {
    id: 1, number: '200000001', name: 'Hydraulikzylinder HZ-200 komplett', status: 'Freigegeben',
    description: 'Vollständige Stückliste für Hydraulikzylinder HZ-200 inkl. aller Kleinteile.',
    parent_item_id: 1, version: 2, valid_from: '2026-01-01', valid_until: null,
    lines: [
      { id: 1, bom_id: 1, position: 10, item_id: 2, quantity: '1', unit: 'Stk', notes: null },
      { id: 2, bom_id: 1, position: 20, item_id: 3, quantity: '1', unit: 'Set', notes: 'Dichtungsset' },
      { id: 3, bom_id: 1, position: 30, item_id: 4, quantity: '2', unit: 'Stk', notes: null },
    ],
    created_at: '2026-01-15T10:00:00Z', updated_at: '2026-05-20T14:32:00Z', created_by: 'admin@inexxio.com',
  },
  {
    id: 2, number: '200000002', name: 'Wartungsset HZ-200', status: 'Entwurf',
    description: 'Stückliste für jährliches Wartungsset Hydraulikzylinder HZ-200.',
    parent_item_id: null, version: 1, valid_from: null, valid_until: null,
    lines: [
      { id: 4, bom_id: 2, position: 10, item_id: 3, quantity: '2', unit: 'Set', notes: null },
      { id: 5, bom_id: 2, position: 20, item_id: 4, quantity: '4', unit: 'Stk', notes: null },
    ],
    created_at: '2026-03-10T08:00:00Z', updated_at: '2026-05-15T11:00:00Z', created_by: 'admin@inexxio.com',
  },
];

function StuecklistenPageInner() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<BOMStatus | 'all'>('all');
  const [showCreate, setShowCreate] = useState(false);
  const [selectedBOM, setSelectedBOM] = useState<BOM | null>(null);
  const [error, setError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['boms'],
    queryFn: () => api.getBOMs(1, 100),
  });

  const boms: BOM[] = isError || !data ? MOCK_BOMS : data.items;

  const filtered = boms.filter((bom) => {
    const q = search.toLowerCase();
    const matchesSearch = !q || bom.name.toLowerCase().includes(q) || bom.number.includes(q);
    const matchesStatus = statusFilter === 'all' || bom.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<BOM>) => api.createBOM(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['boms'] });
      setShowCreate(false);
    },
    onError: () => setError('Fehler beim Erstellen der Stückliste.'),
  });

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
            <Layers className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Stücklisten</h1>
            <p className="text-sm text-slate-500">{boms.length} Stücklisten</p>
          </div>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary">
          <Plus className="h-4 w-4" />
          Stückliste erstellen
        </button>
      </div>

      {error && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-red-500 shrink-0" />
          <p className="text-sm text-red-700">{error}</p>
          <button onClick={() => setError('')} className="ml-auto"><X className="h-4 w-4 text-red-400" /></button>
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
            placeholder="Stücklisten suchen…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="form-input pl-10"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as BOMStatus | 'all')}
          className="form-input"
        >
          <option value="all">Alle Status</option>
          <option value="Entwurf">Entwurf</option>
          <option value="Freigegeben">Freigegeben</option>
          <option value="Archiviert">Archiviert</option>
        </select>
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
                <th className="px-4 py-3 text-center font-medium text-slate-600 hidden sm:table-cell w-20">Pos.</th>
                <th className="px-4 py-3 text-center font-medium text-slate-600 hidden md:table-cell w-24">Version</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 hidden md:table-cell">Gültig ab</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 w-28">Status</th>
                <th className="px-4 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-500">
                    <Layers className="mx-auto mb-3 h-8 w-8 text-slate-300" />
                    <p className="font-medium">Keine Stücklisten gefunden</p>
                    <p className="text-xs mt-1">Erstellen Sie Ihre erste Stückliste.</p>
                  </td>
                </tr>
              ) : (
                filtered.map((bom) => {
                  const sc = STATUS_CONFIG[bom.status] || STATUS_CONFIG.Entwurf;
                  return (
                    <tr
                      key={bom.id}
                      onClick={() => setSelectedBOM(bom)}
                      className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{bom.number}</td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-900">{bom.name}</p>
                        {bom.description && (
                          <p className="text-xs text-slate-500 mt-0.5 truncate max-w-xs">{bom.description}</p>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell text-center text-slate-600">{bom.lines.length}</td>
                      <td className="px-4 py-3 hidden md:table-cell text-center text-slate-600">v{bom.version}</td>
                      <td className="px-4 py-3 hidden md:table-cell text-slate-600">
                        {bom.valid_from ? new Date(bom.valid_from).toLocaleDateString('de-CH') : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${sc.color}`}>
                          {bom.status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <ChevronRight className="h-4 w-4 text-slate-300" />
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
      {selectedBOM && (
        <BOMDetailModal bom={selectedBOM} onClose={() => setSelectedBOM(null)} />
      )}

      {/* Create Modal */}
      {showCreate && (
        <CreateBOMModal
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          saving={createMutation.isPending}
        />
      )}
    </div>
  );
}

function BOMDetailModal({ bom, onClose }: { bom: BOM; onClose: () => void }) {
  const sc = STATUS_CONFIG[bom.status] || STATUS_CONFIG.Entwurf;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-2xl rounded-xl bg-white shadow-xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <div>
            <p className="text-xs font-mono text-slate-500 mb-0.5">{bom.number} · v{bom.version}</p>
            <h2 className="text-xl font-bold text-slate-900">{bom.name}</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 space-y-5">
          <div className="flex items-center gap-2">
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${sc.color}`}>
              {bom.status}
            </span>
            {bom.valid_from && (
              <span className="text-xs text-slate-500">
                Gültig ab: {new Date(bom.valid_from).toLocaleDateString('de-CH')}
              </span>
            )}
          </div>

          {bom.description && (
            <p className="text-sm text-slate-700">{bom.description}</p>
          )}

          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">
              Positionen ({bom.lines.length})
            </h3>
            <div className="rounded-lg border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200">
                    <th className="px-3 py-2 text-left font-medium text-slate-600 w-12">Pos.</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Artikel-ID</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600 w-20">Menge</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600 w-16">Einheit</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Notiz</th>
                  </tr>
                </thead>
                <tbody>
                  {bom.lines.map((line) => (
                    <tr key={line.id} className="border-b border-slate-100 last:border-0">
                      <td className="px-3 py-2 font-mono text-xs text-slate-500">{line.position}</td>
                      <td className="px-3 py-2 text-slate-700">{line.item_id}</td>
                      <td className="px-3 py-2 text-right font-medium text-slate-900">{line.quantity}</td>
                      <td className="px-3 py-2 text-slate-600">{line.unit}</td>
                      <td className="px-3 py-2 text-slate-500 text-xs">{line.notes || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <p className="text-xs text-slate-400">
            Erstellt: {new Date(bom.created_at).toLocaleDateString('de-CH')} ·
            Zuletzt geändert: {new Date(bom.updated_at).toLocaleDateString('de-CH')}
          </p>
        </div>
      </div>
    </div>
  );
}

function CreateBOMModal({
  onClose,
  onSubmit,
  saving,
}: {
  onClose: () => void;
  onSubmit: (data: Partial<BOM>) => void;
  saving: boolean;
}) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSubmit({
      name,
      description: description || null,
      status: 'Entwurf',
      version: 1,
      lines: [],
    });
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-md rounded-xl bg-white shadow-xl mx-4"
        onClick={(e) => e.stopPropagation()}
      >
        <form onSubmit={handleSubmit}>
          <div className="flex items-center justify-between border-b border-slate-200 p-6">
            <h2 className="text-lg font-bold text-slate-900">Neue Stückliste</h2>
            <button type="button" onClick={onClose} className="text-slate-400 hover:text-slate-700">
              <X className="h-5 w-5" />
            </button>
          </div>
          <div className="p-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Bezeichnung *</label>
              <input
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="form-input"
                placeholder="z.B. Hydraulikzylinder HZ-300 komplett"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Beschreibung</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="form-input resize-none"
                rows={3}
                placeholder="Beschreibung der Stückliste…"
              />
            </div>
            <p className="text-xs text-slate-500">
              Die Stückliste wird als Entwurf erstellt. Positionen können anschliessend hinzugefügt werden.
            </p>
          </div>
          <div className="flex justify-end gap-3 border-t border-slate-100 px-6 py-4">
            <button type="button" onClick={onClose} className="btn-secondary">Abbrechen</button>
            <button type="submit" disabled={saving || !name} className="btn-primary disabled:opacity-50">
              {saving ? <><Loader2 className="h-4 w-4 animate-spin" /> Speichert…</> : <><CheckCircle2 className="h-4 w-4" /> Erstellen</>}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function StuecklistenPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <StuecklistenPageInner />
    </QueryClientProvider>
  );
}
