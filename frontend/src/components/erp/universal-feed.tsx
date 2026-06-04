'use client';

import { useState, useMemo, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, Plus, Loader2, InboxIcon } from 'lucide-react';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { ObjectRow } from './object-row';
import { DetailPanel } from './detail-panel';
import type { UniversalObject, ObjectType, UserProfile, UserPlatformRole } from '@/types';

const ROLE_KEY = 'inexxio_user_role';

// Mock data used as fallback when API is unavailable
const MOCK_OBJECTS: UniversalObject[] = [
  {
    id: 100000001,
    object_type: 'item',
    title: 'Hydraulikzylinder HZ-200',
    subtitle: 'Eigen · kg',
    status: 'Freigegeben',
    number: '100000001',
    created_at: '2026-01-15T10:00:00Z',
    updated_at: '2026-05-20T14:32:00Z',
    data: {
      id: 1,
      number: '100000001',
      name: 'Hydraulikzylinder HZ-200',
      description: 'Doppeltwirkender Hydraulikzylinder für industrielle Anwendungen. Hub 200mm, Kolbendurchmesser 80mm, Betriebsdruck max. 250 bar.',
      unit: 'Stk',
      item_type: 'Eigen',
      status: 'Freigegeben',
      weight_kg: 4.8,
      dimensions: '320 × 90 × 90 mm',
      material: 'Stahl S355 / Chrom-Stahl',
      surface_finish: 'Hartchrom',
      tolerance_class: 'H7',
      drawing_number: 'IX-HZ200-001',
      manufacturer: null,
      manufacturer_part_number: null,
      lead_time_days: 14,
      cost_price: '285.00',
      sales_price: '420.00',
      currency: 'CHF',
      tags: ['hydraulik', 'zylinder'],
      created_at: '2026-01-15T10:00:00Z',
      updated_at: '2026-05-20T14:32:00Z',
      created_by: 'admin@inexxio.com',
    },
  },
  {
    id: 100000002,
    object_type: 'item',
    title: 'Kolbenstange KS-150',
    subtitle: 'Eigen · Stk',
    status: 'Entwurf',
    number: '100000002',
    created_at: '2026-01-14T09:00:00Z',
    updated_at: '2026-05-18T11:00:00Z',
    data: {
      id: 2,
      number: '100000002',
      name: 'Kolbenstange KS-150',
      description: 'Präzisionskolbenstange aus Chrom-Stahl, geschliffen und hartverchromt.',
      unit: 'Stk',
      item_type: 'Eigen',
      status: 'Entwurf',
      weight_kg: 1.2,
      dimensions: '200 × 40 mm',
      material: 'Chrom-Stahl 42CrMo4',
      surface_finish: 'Hartchrom 20µm',
      tolerance_class: 'h6',
      drawing_number: 'IX-KS150-001',
      manufacturer: null,
      manufacturer_part_number: null,
      lead_time_days: 7,
      cost_price: '95.00',
      sales_price: '145.00',
      currency: 'CHF',
      tags: ['kolbenstange'],
      created_at: '2026-01-14T09:00:00Z',
      updated_at: '2026-05-18T11:00:00Z',
      created_by: 'admin@inexxio.com',
    },
  },
  {
    id: 100000004,
    object_type: 'company',
    title: 'Hydraulik AG Zürich',
    subtitle: 'Lieferant',
    status: 'Lieferant',
    number: '100000004',
    created_at: '2026-01-12T14:00:00Z',
    updated_at: '2026-04-02T10:00:00Z',
    data: {
      id: 4,
      number: '100000004',
      name: 'Hydraulik AG Zürich',
      legal_form: 'AG',
      role: 'Lieferant',
      is_active: true,
      address: {
        street: 'Industriestrasse',
        street_number: '45',
        zip: '8152',
        city: 'Glattbrugg',
        country: 'Schweiz',
        country_code: 'CH',
      },
      uid: 'CHE-123.456.789',
      vat_number: 'CHE-123.456.789 MWST',
      website: 'https://www.hydraulik-ag.ch',
      email: 'info@hydraulik-ag.ch',
      phone: '+41 44 800 10 20',
      notes: 'Hauptlieferant für Hydraulikkomponenten',
      payment_terms_days: 30,
      discount_percent: '2.00',
      created_at: '2026-01-12T14:00:00Z',
      updated_at: '2026-04-02T10:00:00Z',
    },
  },
  {
    id: 100000005,
    object_type: 'work_plan',
    title: 'Montage HZ-200 Komplett',
    subtitle: '5 Schritte',
    status: 'Aktiv',
    number: '100000005',
    created_at: '2026-01-11T12:00:00Z',
    updated_at: '2026-05-15T16:00:00Z',
    data: {
      id: 5,
      number: '100000005',
      name: 'Montage HZ-200 Komplett',
      description: 'Kompletter Montagearbeitsplan für Hydraulikzylinder HZ-200 inklusive Funktionsprüfung.',
      status: 'Aktiv',
      item_id: 1,
      steps: [],
      version: 2,
      created_at: '2026-01-11T12:00:00Z',
      updated_at: '2026-05-15T16:00:00Z',
      created_by: 'admin@inexxio.com',
    },
  },
];

const ROLE_SUBTITLES: Record<UserPlatformRole, string> = {
  admin: 'Administrator',
  employee: 'Mitarbeiter',
  supplier: 'Lieferant',
  customer: 'Kunde',
};

function profileToObject(p: UserProfile): UniversalObject {
  const fullName = [p.first_name, p.last_name].filter(Boolean).join(' ') || p.display_name || p.email;
  return {
    id: p.object_id ?? p.id,
    object_type: 'user',
    title: fullName,
    subtitle: ROLE_SUBTITLES[p.role] ?? p.role,
    status: p.is_active ? 'Aktiv' : 'Inaktiv',
    number: String(p.object_id ?? p.id),
    created_at: p.created_at,
    updated_at: p.updated_at,
    data: p,
  };
}

type FilterType = 'all' | ObjectType;

const filterTabs: { value: FilterType; label: string }[] = [
  { value: 'all', label: 'Alle' },
  { value: 'item', label: 'Artikel' },
  { value: 'company', label: 'Firmen' },
  { value: 'work_plan', label: 'Arbeitspläne' },
  { value: 'user', label: 'Benutzer' },
];

export function UniversalFeed() {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterType>('all');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const queryClient = useQueryClient();

  const currentUserRole = typeof window !== 'undefined' ? localStorage.getItem(ROLE_KEY) ?? undefined : undefined;

  const isUserFilter = filter === 'user';

  const { data: objectsData, isLoading: objectsLoading, isError: objectsError } = useQuery({
    queryKey: ['objects', { q: search, type: filter }],
    queryFn: () =>
      api.getObjects({
        q: search || undefined,
        object_type: filter === 'all' || filter === 'user' ? undefined : filter,
        page_size: 50,
      }),
    enabled: !isUserFilter,
    retry: 1,
    staleTime: 30_000,
  });

  const { data: usersData, isLoading: usersLoading, isError: usersError } = useQuery({
    queryKey: ['users'],
    queryFn: () => api.getUsers(),
    enabled: isUserFilter,
    retry: 1,
    staleTime: 30_000,
  });

  const isLoading = isUserFilter ? usersLoading : objectsLoading;
  const isError = isUserFilter ? usersError : objectsError;

  const objects: UniversalObject[] = useMemo(() => {
    if (isUserFilter) {
      const users = usersError || !usersData ? [] : usersData;
      return users.map(profileToObject);
    }
    return objectsError || !objectsData ? MOCK_OBJECTS : objectsData.items;
  }, [isUserFilter, usersData, usersError, objectsData, objectsError]);

  const filtered = useMemo(() => {
    let list = objects;
    if (!isUserFilter && filter !== 'all') {
      list = list.filter((o) => o.object_type === filter);
    }
    if (search.trim()) {
      const q = search.toLowerCase();
      list = list.filter(
        (o) =>
          o.title.toLowerCase().includes(q) ||
          o.number.includes(q) ||
          o.id.toString().includes(q),
      );
    }
    return list;
  }, [objects, filter, search, isUserFilter]);

  const selectedObject = filtered.find((o) => o.id === selectedId) ?? null;

  const handleRefresh = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['users'] });
  }, [queryClient]);

  return (
    <div className="flex overflow-hidden" style={{ height: 'calc(100vh - 72px - 280px)', minHeight: 500 }}>
      {/* Left panel */}
      <div className="w-96 flex flex-col border-r border-slate-200 bg-white shrink-0">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
          <h1 className="text-lg font-bold text-slate-900">ERP</h1>
          <button
            type="button"
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-red-600 text-white hover:bg-red-700 transition-colors"
            style={{ background: '#E51A14' }}
            aria-label="Neues Objekt erstellen"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        {/* Search */}
        <div className="px-4 py-3 border-b border-slate-100">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
            <input
              type="search"
              placeholder="Suchen…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm border border-slate-200 rounded-lg bg-slate-50 focus:bg-white focus:ring-2 focus:ring-red-500 focus:border-transparent outline-none transition-all"
            />
          </div>
        </div>

        {/* Filter tabs */}
        <div className="flex px-4 gap-1 py-2 border-b border-slate-100 overflow-x-auto">
          {filterTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => { setFilter(tab.value); setSelectedId(null); }}
              className={cn(
                'px-3 py-1 rounded-full text-xs font-medium whitespace-nowrap transition-colors',
                filter === tab.value
                  ? 'text-white'
                  : 'bg-slate-100 text-slate-600 hover:bg-slate-200',
              )}
              style={filter === tab.value ? { background: '#E51A14' } : {}}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {/* List */}
        <div className="flex-1 overflow-y-auto">
          {isLoading && (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin" style={{ color: '#E51A14' }} />
            </div>
          )}

          {!isLoading && filtered.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 px-6 text-center">
              <InboxIcon className="h-10 w-10 text-slate-300 mb-3" />
              <p className="text-sm font-medium text-slate-700">Keine Objekte gefunden</p>
              <p className="text-xs text-slate-500 mt-1">
                {search ? 'Versuchen Sie einen anderen Suchbegriff.' : 'Erstellen Sie Ihr erstes Objekt mit dem + Button.'}
              </p>
            </div>
          )}

          {!isLoading &&
            filtered.map((obj) => (
              <ObjectRow
                key={obj.id}
                object={obj}
                selected={obj.id === selectedId}
                onClick={() => setSelectedId(obj.id === selectedId ? null : obj.id)}
              />
            ))}

          {isError && !isUserFilter && (
            <div className="px-4 py-2 bg-amber-50 border-b border-amber-200">
              <p className="text-xs text-amber-700">Demo-Modus: API nicht erreichbar. Demodaten werden angezeigt.</p>
            </div>
          )}
          {isError && isUserFilter && (
            <div className="px-4 py-2 bg-red-50 border-b border-red-100">
              <p className="text-xs text-red-600">Benutzer konnten nicht geladen werden.</p>
            </div>
          )}
        </div>

        {/* Footer: count */}
        <div className="px-4 py-2 border-t border-slate-100 bg-slate-50">
          <p className="text-xs text-slate-500">
            {filtered.length} Objekt{filtered.length !== 1 ? 'e' : ''}
            {!isUserFilter && objectsData && ` · ${objectsData.total} gesamt`}
          </p>
        </div>
      </div>

      {/* Detail panel */}
      <div className="flex-1 flex flex-col overflow-hidden bg-white">
        <DetailPanel
          object={selectedObject}
          currentUserRole={currentUserRole}
          onRefresh={handleRefresh}
        />
      </div>
    </div>
  );
}
