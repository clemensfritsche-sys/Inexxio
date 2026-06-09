'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Plus, Trash2, Loader2, Layers } from 'lucide-react';
import { api } from '@/lib/api';

export function ObjekttypenSection() {
  const qc = useQueryClient();
  const [newName, setNewName] = useState('');

  const { data: typen, isLoading } = useQuery({
    queryKey: ['objekttypen'],
    queryFn: () => api.listObjektTypen(),
    staleTime: 30_000,
  });

  const { mutate: create, isPending: creating } = useMutation({
    mutationFn: () => api.createObjektTyp({ name: newName.trim() }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['objekttypen'] });
      setNewName('');
    },
  });

  const { mutate: remove } = useMutation({
    mutationFn: (id: number) => api.deleteObjektTyp(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['objekttypen'] }),
  });

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
      <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-50 text-orange-600">
          <Layers className="h-4 w-4" />
        </div>
        <div>
          <h2 className="text-sm font-semibold text-slate-900">Objekttypen</h2>
          <p className="text-xs text-slate-500">Namen für Objekte im ERP — werden als Vorschläge beim Erstellen angezeigt</p>
        </div>
      </div>

      <div className="px-6 py-4 space-y-3">
        {isLoading && <div className="flex justify-center py-4"><Loader2 className="h-5 w-5 animate-spin text-slate-400" /></div>}

        {!isLoading && !typen?.length && (
          <p className="text-sm text-slate-400 italic py-2 text-center">Noch keine Objekttypen definiert.</p>
        )}

        <div className="space-y-1.5">
          {(typen ?? []).map(t => (
            <div key={t.id} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2">
              <span className="text-sm text-slate-800">{t.name}</span>
              <button
                type="button"
                onClick={() => remove(t.id)}
                className="p-1 text-slate-400 hover:text-red-600 transition-colors rounded"
                title="Löschen"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
        </div>

        <div className="flex gap-2 pt-1">
          <input
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && newName.trim()) create(); }}
            placeholder="Neuer Objekttyp z.B. Produktionsauftrag…"
            className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            type="button"
            disabled={!newName.trim() || creating}
            onClick={() => create()}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            Hinzufügen
          </button>
        </div>
      </div>
    </div>
  );
}
