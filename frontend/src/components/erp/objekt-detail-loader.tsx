'use client';

import { useQuery } from '@tanstack/react-query';
import { Loader2, AlertTriangle } from 'lucide-react';
import { api } from '@/lib/api';
import { ObjektStammdatenForm } from './objekt-stammdaten-form';
import { ObjektProzessPanel } from './objekt-prozess-panel';

interface Props {
  id: number;
  currentUserRole?: string;
  onRefresh?: () => void;
  onNavigate?: (id: number) => void;
}

export function ObjektDetailLoader({ id, currentUserRole, onRefresh, onNavigate }: Props) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['uni-objekt', id],
    queryFn: () => api.getUniObjekt(id),
    retry: 1,
    staleTime: 10_000,
  });

  const handleRefresh = () => {
    refetch();
    onRefresh?.();
  };

  if (isLoading) {
    return (
      <div className="flex flex-1 items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center py-20 px-6 text-center">
        <AlertTriangle className="h-8 w-8 text-red-400 mb-3" />
        <p className="text-sm font-medium text-slate-700">Objekt konnte nicht geladen werden</p>
      </div>
    );
  }

  if (data.stamm_id === null) {
    return (
      <ObjektStammdatenForm
        key={data.id}
        objekt={data}
        currentUserRole={currentUserRole}
        onRefresh={handleRefresh}
        onNavigate={onNavigate}
      />
    );
  }

  return (
    <ObjektProzessPanel
      key={data.id}
      objekt={data}
      onRefresh={handleRefresh}
      onNavigate={onNavigate}
    />
  );
}
