'use client';

import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Search, Layers, Loader2, AlertCircle, X, ChevronRight,
} from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { formatObjectId, formatDate } from '@/lib/utils';
import type { BOM } from '@/types';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

function StuecklistenPageInner() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [selectedBOM, setSelectedBOM] = useState<BOM | null>(null);

  const { data: boms = [], isLoading, isError } = useQuery({
    queryKey: ['boms'],
    queryFn: () => api.getBOMs(1, 100),
  });

  const filtered = (boms as BOM[]).filter((bom) => {
    if (!search.trim()) return true;
    const q = search.toLowerCase();
    return String(bom.id).includes(q) || String(bom.parent_item_id).includes(q) || (bom.note ?? '').toLowerCase().includes(q);
  });

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
            <Layers className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Stücklisten</h1>
            <p className="text-sm text-slate-500">{filtered.length} Stücklisten</p>
          </div>
        </div>
        <p className="text-sm text-slate-500">Stücklisten werden im Artikelstamm (ERP-Tab) verwaltet.</p>
      </div>

      {isError && (
        <div className="mb-4 flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <AlertCircle className="h-4 w-4 text-amber-500 shrink-0" />
          <p className="text-sm text-amber-700">Stücklisten konnten nicht geladen werden.</p>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Suchen…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 text-sm border border-slate-200 rounded-lg bg-white focus:ring-2 focus:ring-blue-500 outline-none"
          />
        </div>
      </div>

      <div className="border border-slate-200 rounded-xl overflow-hidden bg-white shadow-sm">
        {isLoading ? (
          <div className="flex items-center justify-center py-16">
            <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-slate-50">
                <th className="px-4 py-3 text-left font-medium text-slate-600">ID</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Artikel-ID</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600">Notiz</th>
                <th className="px-4 py-3 text-center font-medium text-slate-600 w-20">Pos.</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 hidden md:table-cell">Zuletzt geändert</th>
                <th className="px-4 py-3 w-8" />
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center text-slate-500">
                    <Layers className="mx-auto mb-3 h-8 w-8 text-slate-300" />
                    <p className="font-medium">Keine Stücklisten gefunden</p>
                    <p className="text-xs mt-1">Stücklisten werden im ERP-Tab eines Artikels erstellt.</p>
                  </td>
                </tr>
              ) : (
                filtered.map((bom) => (
                  <tr
                    key={bom.id}
                    onClick={() => setSelectedBOM(bom)}
                    className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 font-mono text-xs text-slate-500">{formatObjectId(bom.id)}</td>
                    <td className="px-4 py-3 font-mono text-xs text-slate-700">{formatObjectId(bom.parent_item_id)}</td>
                    <td className="px-4 py-3 text-slate-700 truncate max-w-xs">{bom.note || <span className="text-slate-400 italic">—</span>}</td>
                    <td className="px-4 py-3 text-center text-slate-600">{bom.lines.length}</td>
                    <td className="px-4 py-3 hidden md:table-cell text-slate-500 text-xs">{formatDate(bom.updated_at)}</td>
                    <td className="px-4 py-3">
                      <ChevronRight className="h-4 w-4 text-slate-300" />
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        )}
      </div>

      {selectedBOM && (
        <BOMDetailModal bom={selectedBOM} onClose={() => setSelectedBOM(null)} onRefresh={() => qc.invalidateQueries({ queryKey: ['boms'] })} />
      )}
    </div>
  );
}

function BOMDetailModal({ bom, onClose }: { bom: BOM; onClose: () => void; onRefresh: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-2xl rounded-xl bg-white shadow-xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <div>
            <p className="text-xs font-mono text-slate-500 mb-0.5">{formatObjectId(bom.id)}</p>
            <h2 className="text-xl font-bold text-slate-900">Stückliste</h2>
            <p className="text-sm text-slate-500 mt-0.5">Artikel-ID: {formatObjectId(bom.parent_item_id)}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 space-y-5">
          {bom.note && <p className="text-sm text-slate-700">{bom.note}</p>}

          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">Positionen ({bom.lines.length})</h3>
            <div className="rounded-lg border border-slate-200 overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200">
                    <th className="px-3 py-2 text-left font-medium text-slate-600 w-12">Pos.</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Komponente</th>
                    <th className="px-3 py-2 text-right font-medium text-slate-600 w-20">Menge</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600 w-16">Einheit</th>
                    <th className="px-3 py-2 text-left font-medium text-slate-600">Notiz</th>
                  </tr>
                </thead>
                <tbody>
                  {bom.lines.length === 0 ? (
                    <tr><td colSpan={5} className="px-3 py-6 text-center text-sm text-slate-400">Keine Positionen</td></tr>
                  ) : (
                    bom.lines.map((line) => (
                      <tr key={line.id} className="border-b border-slate-100 last:border-0">
                        <td className="px-3 py-2 font-mono text-xs text-slate-500">{line.position}</td>
                        <td className="px-3 py-2 font-mono text-xs text-slate-700">{formatObjectId(line.component_item_id)}</td>
                        <td className="px-3 py-2 text-right font-medium text-slate-900">{line.quantity}</td>
                        <td className="px-3 py-2 text-slate-600">{line.unit}</td>
                        <td className="px-3 py-2 text-slate-500 text-xs">{line.note || '—'}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          <p className="text-xs text-slate-400">
            Erstellt: {formatDate(bom.created_at)} · Zuletzt geändert: {formatDate(bom.updated_at)}
          </p>
        </div>
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
