'use client';

import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Plus, Search, Wrench, Loader2, AlertCircle, X, ChevronRight, CheckCircle2, Clock
} from 'lucide-react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { WorkPlan, WorkPlanStatus } from '@/types';

const queryClient = new QueryClient({ defaultOptions: { queries: { retry: 1, staleTime: 30_000 } } });

const STATUS_CONFIG: Record<WorkPlanStatus, { color: string }> = {
  Entwurf: { color: 'bg-slate-100 text-slate-600' },
  Aktiv: { color: 'bg-green-50 text-green-700' },
  Archiviert: { color: 'bg-slate-50 text-slate-400' },
};

const MOCK_WORKPLANS: WorkPlan[] = [
  {
    id: 1, number: '300000001', name: 'Montage HZ-200 Komplett', status: 'Aktiv',
    description: 'Kompletter Montagearbeitsplan für Hydraulikzylinder HZ-200 inklusive Funktionsprüfung.',
    item_id: 1, version: 2,
    steps: [
      { id: 1, work_plan_id: 1, step_number: 10, name: 'Vorreinigung Gehäuse', description: 'Gehäuse mit Druckluft und Lösungsmittel reinigen.', work_center: 'Montage', machine: null, setup_time_min: 5, run_time_min: 10, tools: ['Druckluftpistole', 'Reinigungstuch'], notes: null },
      { id: 2, work_plan_id: 1, step_number: 20, name: 'Dichtungen einsetzen', description: 'O-Ring und Abstreifer gemäss Dichtungsset DS-10 einsetzen.', work_center: 'Montage', machine: null, setup_time_min: 5, run_time_min: 20, tools: ['Montagewerkzeug', 'Montagefett'], notes: 'Dichtungen vor Montage mit Fett benetzen.' },
      { id: 3, work_plan_id: 1, step_number: 30, name: 'Kolbenstange einführen', description: 'Kolbenstange KS-150 sorgfältig einführen, auf Parallelität achten.', work_center: 'Montage', machine: null, setup_time_min: 10, run_time_min: 15, tools: ['Montagedorn'], notes: null },
      { id: 4, work_plan_id: 1, step_number: 40, name: 'Druckprüfung', description: 'Zylinder auf 1.5-fachen Betriebsdruck (375 bar) prüfen, 30 Minuten halten.', work_center: 'Prüfstand', machine: 'Hydraulikprüfstand HP-1', setup_time_min: 15, run_time_min: 30, tools: ['Manometer', 'Protokoll'], notes: 'Bei Leckage: Dichtungen ersetzen und erneut prüfen.' },
      { id: 5, work_plan_id: 1, step_number: 50, name: 'Endkontrolle und Protokoll', description: 'Sichtprüfung, Messung, Prüfprotokoll ausfüllen und unterzeichnen.', work_center: 'QM', machine: null, setup_time_min: 5, run_time_min: 15, tools: ['Schieblehre', 'Prüfprotokoll'], notes: null },
    ],
    created_at: '2026-01-11T12:00:00Z', updated_at: '2026-05-15T16:00:00Z', created_by: 'admin@inexxio.com',
  },
  {
    id: 2, number: '300000002', name: 'Wartung HZ-200 jährlich', status: 'Aktiv',
    description: 'Jährlicher Wartungsplan für Hydraulikzylinder HZ-200.',
    item_id: 1, version: 1,
    steps: [
      { id: 6, work_plan_id: 2, step_number: 10, name: 'Ausbau und Reinigung', description: null, work_center: 'Montage', machine: null, setup_time_min: 20, run_time_min: 30, tools: [], notes: null },
      { id: 7, work_plan_id: 2, step_number: 20, name: 'Dichtungsersatz', description: null, work_center: 'Montage', machine: null, setup_time_min: 10, run_time_min: 25, tools: [], notes: null },
      { id: 8, work_plan_id: 2, step_number: 30, name: 'Einbau und Prüfung', description: null, work_center: 'Prüfstand', machine: 'Hydraulikprüfstand HP-1', setup_time_min: 15, run_time_min: 30, tools: [], notes: null },
    ],
    created_at: '2026-02-01T10:00:00Z', updated_at: '2026-04-10T09:00:00Z', created_by: 'admin@inexxio.com',
  },
  {
    id: 3, number: '300000003', name: 'Drehen Kolbenstange KS-150', status: 'Entwurf',
    description: 'Fertigungsarbeitsplan für Kolbenstange KS-150.',
    item_id: 2, version: 1,
    steps: [
      { id: 9, work_plan_id: 3, step_number: 10, name: 'Rohling einspannen', description: null, work_center: 'CNC-Drehen', machine: 'DMG NLX 2500', setup_time_min: 20, run_time_min: 5, tools: ['Dreibackenfutter'], notes: null },
      { id: 10, work_plan_id: 3, step_number: 20, name: 'Schruppen', description: null, work_center: 'CNC-Drehen', machine: 'DMG NLX 2500', setup_time_min: 5, run_time_min: 45, tools: ['Wendeplatte CNMG'], notes: null },
      { id: 11, work_plan_id: 3, step_number: 30, name: 'Schlichten auf Mass', description: null, work_center: 'CNC-Drehen', machine: 'DMG NLX 2500', setup_time_min: 5, run_time_min: 30, tools: ['Wendeplatte DCGT'], notes: 'Toleranz h6 einhalten.' },
    ],
    created_at: '2026-04-05T14:00:00Z', updated_at: '2026-05-28T10:00:00Z', created_by: 'admin@inexxio.com',
  },
];

function sumTime(steps: WorkPlan['steps']) {
  return steps.reduce((acc, s) => acc + (s.setup_time_min || 0) + (s.run_time_min || 0), 0);
}

function ArbeitsplaenePageInner() {
  const qc = useQueryClient();
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<WorkPlanStatus | 'all'>('all');
  const [showCreate, setShowCreate] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<WorkPlan | null>(null);
  const [error, setError] = useState('');

  const { data, isLoading, isError } = useQuery({
    queryKey: ['work-plans'],
    queryFn: () => api.getWorkPlans(1, 100),
  });

  const plans: WorkPlan[] = isError || !data ? MOCK_WORKPLANS : data.items;

  const filtered = plans.filter((p) => {
    const q = search.toLowerCase();
    const matchesSearch = !q || p.name.toLowerCase().includes(q) || p.number.includes(q);
    const matchesStatus = statusFilter === 'all' || p.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const createMutation = useMutation({
    mutationFn: (data: Partial<WorkPlan>) => api.createWorkPlan(data),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['work-plans'] });
      setShowCreate(false);
    },
    onError: () => setError('Fehler beim Erstellen des Arbeitsplans.'),
  });

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-blue-50">
            <Wrench className="h-5 w-5 text-blue-600" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-slate-900">Arbeitspläne</h1>
            <p className="text-sm text-slate-500">{plans.length} Arbeitspläne</p>
          </div>
        </div>
        <button onClick={() => setShowCreate(true)} className="btn-primary">
          <Plus className="h-4 w-4" />
          Arbeitsplan erstellen
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
          <p className="text-sm text-amber-700">Demo-Modus: API nicht erreichbar.</p>
        </div>
      )}

      <div className="mb-4 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-48 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400" />
          <input
            type="text"
            placeholder="Arbeitspläne suchen…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="form-input pl-10"
          />
        </div>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value as WorkPlanStatus | 'all')}
          className="form-input"
        >
          <option value="all">Alle Status</option>
          <option value="Entwurf">Entwurf</option>
          <option value="Aktiv">Aktiv</option>
          <option value="Archiviert">Archiviert</option>
        </select>
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
                <th className="px-4 py-3 text-center font-medium text-slate-600 hidden sm:table-cell w-20">Schritte</th>
                <th className="px-4 py-3 text-center font-medium text-slate-600 hidden md:table-cell w-24">Version</th>
                <th className="px-4 py-3 text-right font-medium text-slate-600 hidden md:table-cell w-28">Zeit (min)</th>
                <th className="px-4 py-3 text-left font-medium text-slate-600 w-28">Status</th>
                <th className="px-4 py-3 w-8"></th>
              </tr>
            </thead>
            <tbody>
              {filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-500">
                    <Wrench className="mx-auto mb-3 h-8 w-8 text-slate-300" />
                    <p className="font-medium">Keine Arbeitspläne gefunden</p>
                  </td>
                </tr>
              ) : (
                filtered.map((plan) => {
                  const sc = STATUS_CONFIG[plan.status] || STATUS_CONFIG.Entwurf;
                  const totalMin = sumTime(plan.steps);
                  return (
                    <tr
                      key={plan.id}
                      onClick={() => setSelectedPlan(plan)}
                      className="border-b border-slate-100 last:border-0 hover:bg-slate-50 cursor-pointer transition-colors"
                    >
                      <td className="px-4 py-3 font-mono text-xs text-slate-500">{plan.number}</td>
                      <td className="px-4 py-3">
                        <p className="font-medium text-slate-900">{plan.name}</p>
                        {plan.description && (
                          <p className="text-xs text-slate-500 mt-0.5 truncate max-w-xs">{plan.description}</p>
                        )}
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell text-center text-slate-600">{plan.steps.length}</td>
                      <td className="px-4 py-3 hidden md:table-cell text-center text-slate-600">v{plan.version}</td>
                      <td className="px-4 py-3 hidden md:table-cell text-right">
                        {totalMin > 0 ? (
                          <span className="flex items-center justify-end gap-1 text-slate-600">
                            <Clock className="h-3 w-3" />
                            {totalMin}
                          </span>
                        ) : '—'}
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${sc.color}`}>
                          {plan.status}
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

      {selectedPlan && (
        <WorkPlanDetailModal plan={selectedPlan} onClose={() => setSelectedPlan(null)} />
      )}

      {showCreate && (
        <CreateWorkPlanModal
          onClose={() => setShowCreate(false)}
          onSubmit={(data) => createMutation.mutate(data)}
          saving={createMutation.isPending}
        />
      )}
    </div>
  );
}

function WorkPlanDetailModal({ plan, onClose }: { plan: WorkPlan; onClose: () => void }) {
  const sc = STATUS_CONFIG[plan.status] || STATUS_CONFIG.Entwurf;
  const totalMin = sumTime(plan.steps);
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="relative w-full max-w-3xl rounded-xl bg-white shadow-xl mx-4 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <div>
            <p className="text-xs font-mono text-slate-500 mb-0.5">{plan.number} · v{plan.version}</p>
            <h2 className="text-xl font-bold text-slate-900">{plan.name}</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700">
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-6 space-y-5">
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${sc.color}`}>
              {plan.status}
            </span>
            {totalMin > 0 && (
              <span className="flex items-center gap-1 text-xs text-slate-500">
                <Clock className="h-3.5 w-3.5" />
                Gesamtzeit: {totalMin} min ({Math.round(totalMin / 60 * 10) / 10} h)
              </span>
            )}
          </div>

          {plan.description && (
            <p className="text-sm text-slate-700">{plan.description}</p>
          )}

          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">
              Arbeitsschritte ({plan.steps.length})
            </h3>
            <div className="space-y-3">
              {plan.steps.map((step) => (
                <div key={step.id} className="rounded-lg border border-slate-200 p-4">
                  <div className="flex items-start gap-3">
                    <span className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-600 text-[10px] font-bold text-white shrink-0 mt-0.5">
                      {step.step_number / 10}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-900">{step.name}</p>
                      {step.description && (
                        <p className="text-sm text-slate-600 mt-0.5">{step.description}</p>
                      )}
                      <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-500">
                        {step.work_center && <span>Arbeitsplatz: <strong className="text-slate-700">{step.work_center}</strong></span>}
                        {step.machine && <span>Maschine: <strong className="text-slate-700">{step.machine}</strong></span>}
                        {step.setup_time_min != null && <span>Rüsten: <strong className="text-slate-700">{step.setup_time_min} min</strong></span>}
                        {step.run_time_min != null && <span>Laufzeit: <strong className="text-slate-700">{step.run_time_min} min</strong></span>}
                      </div>
                      {step.tools.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {step.tools.map((tool) => (
                            <span key={tool} className="rounded bg-slate-100 px-1.5 py-0.5 text-xs text-slate-600">{tool}</span>
                          ))}
                        </div>
                      )}
                      {step.notes && (
                        <p className="mt-1.5 text-xs text-amber-700 bg-amber-50 rounded px-2 py-1">
                          Hinweis: {step.notes}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <p className="text-xs text-slate-400">
            Erstellt: {new Date(plan.created_at).toLocaleDateString('de-CH')} ·
            Zuletzt geändert: {new Date(plan.updated_at).toLocaleDateString('de-CH')}
          </p>
        </div>
      </div>
    </div>
  );
}

function CreateWorkPlanModal({
  onClose,
  onSubmit,
  saving,
}: {
  onClose: () => void;
  onSubmit: (data: Partial<WorkPlan>) => void;
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
      steps: [],
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
            <h2 className="text-lg font-bold text-slate-900">Neuer Arbeitsplan</h2>
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
                placeholder="z.B. Montage HZ-300 komplett"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1.5">Beschreibung</label>
              <textarea
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                className="form-input resize-none"
                rows={3}
                placeholder="Beschreibung des Arbeitsplans…"
              />
            </div>
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

export default function ArbeitsplaenePage() {
  return (
    <QueryClientProvider client={queryClient}>
      <ArbeitsplaenePageInner />
    </QueryClientProvider>
  );
}
