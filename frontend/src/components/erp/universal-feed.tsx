'use client';

import { useState, useMemo, useCallback, useRef, useEffect } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Search, Plus, Loader2, InboxIcon, ArrowLeft, Package, Building2, Wrench, GitBranch } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { cn } from '@/lib/utils';
import { api } from '@/lib/api';
import { ObjectRow } from './object-row';
import { DetailPanel } from './detail-panel';
import { useIsMobile } from '@/hooks/useIsMobile';
import type { UniversalObject, ObjectType, UserProfile, UserPlatformRole } from '@/types';

const ROLE_KEY = 'inexxio_user_role';

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
  { value: 'user', label: 'Benutzer' },
];

const CREATE_MENU = [
  { label: 'Artikel erstellen', href: '/erp/artikel', icon: Package },
  { label: 'Firma erstellen', href: '/erp/firmen', icon: Building2 },
  { label: 'Stückliste erstellen', href: '/erp/stuecklisten', icon: GitBranch },
  { label: 'Arbeitsplan erstellen', href: '/erp/arbeitspläne', icon: Wrench },
];

export function UniversalFeed() {
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<FilterType>('all');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [showCreateMenu, setShowCreateMenu] = useState(false);
  const createMenuRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();
  const router = useRouter();
  const isMobile = useIsMobile(768);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (createMenuRef.current && !createMenuRef.current.contains(e.target as Node)) {
        setShowCreateMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const currentUserRole = typeof window !== 'undefined' ? localStorage.getItem(ROLE_KEY) ?? undefined : undefined;

  const isUserFilter = filter === 'user';
  const needsUsers = filter === 'all' || filter === 'user';

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
    enabled: needsUsers,
    retry: 1,
    staleTime: 30_000,
  });

  const isLoading = isUserFilter ? usersLoading : (objectsLoading || (filter === 'all' && usersLoading));
  const isError = isUserFilter ? usersError : objectsError;

  const objects: UniversalObject[] = useMemo(() => {
    if (isUserFilter) {
      return (usersData ?? []).map(profileToObject);
    }
    const objs = objectsData?.items ?? [];
    if (filter === 'all') {
      const users = (usersData ?? []).map(profileToObject);
      return [...objs, ...users];
    }
    return objs;
  }, [isUserFilter, filter, usersData, objectsData]);

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
    queryClient.invalidateQueries({ queryKey: ['objects'] });
  }, [queryClient]);

  // Mobile: show list when nothing selected, detail when selected
  const showList = !isMobile || selectedId === null;
  const showDetail = !isMobile || selectedId !== null;

  const listPanel = (
    <div className={cn('flex flex-col border-r border-slate-200 bg-white shrink-0', isMobile ? 'w-full' : 'w-96')}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
        <h1 className="text-lg font-bold text-slate-900">ERP</h1>
        <div className="relative" ref={createMenuRef}>
          <button
            type="button"
            onClick={() => setShowCreateMenu((v) => !v)}
            className="flex h-8 w-8 items-center justify-center rounded-lg text-white hover:bg-red-700 transition-colors"
            style={{ background: '#E51A14' }}
            aria-label="Neues Objekt erstellen"
          >
            <Plus className="h-4 w-4" />
          </button>
          {showCreateMenu && (
            <div className="absolute right-0 top-10 z-50 w-52 rounded-xl border border-slate-200 bg-white shadow-lg py-1">
              {CREATE_MENU.map(({ label, href, icon: Icon }) => (
                <button
                  key={href}
                  type="button"
                  onClick={() => { setShowCreateMenu(false); router.push(href); }}
                  className="flex w-full items-center gap-3 px-4 py-2.5 text-sm text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  <Icon className="h-4 w-4 text-slate-400" />
                  {label}
                </button>
              ))}
            </div>
          )}
        </div>
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

        {isError && (
          <div className="px-4 py-2 bg-red-50 border-b border-red-100">
            <p className="text-xs text-red-600">Daten konnten nicht geladen werden. Bitte Seite neu laden.</p>
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-4 py-2 border-t border-slate-100 bg-slate-50">
        <p className="text-xs text-slate-500">
          {filtered.length} Objekt{filtered.length !== 1 ? 'e' : ''}
          {!isUserFilter && objectsData && ` · ${objectsData.total} gesamt`}
        </p>
      </div>
    </div>
  );

  const detailPanel = (
    <div className={cn('flex flex-col overflow-hidden bg-white', isMobile ? 'w-full' : 'flex-1')}>
      {isMobile && selectedId !== null && (
        <button
          onClick={() => setSelectedId(null)}
          className="flex items-center gap-2 px-4 py-3 border-b border-slate-200 text-sm font-medium text-slate-600 hover:text-slate-900 bg-white"
          style={{ background: 'none', border: 'none', borderBottom: '1px solid #E2E8F0', cursor: 'pointer', textAlign: 'left' }}
        >
          <ArrowLeft className="h-4 w-4" />
          Zurück zur Liste
        </button>
      )}
      <DetailPanel
        object={selectedObject}
        currentUserRole={currentUserRole}
        onRefresh={handleRefresh}
      />
    </div>
  );

  return (
    <div
      className="flex overflow-hidden"
      style={{ height: isMobile ? 'calc(100vh - 72px)' : 'calc(100vh - 72px - 280px)', minHeight: isMobile ? 0 : 500 }}
    >
      {showList && listPanel}
      {showDetail && detailPanel}
    </div>
  );
}
