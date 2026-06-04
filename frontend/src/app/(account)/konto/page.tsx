'use client';

import { QueryClient, QueryClientProvider, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { AccountShell } from '@/components/account/account-shell';
import type { UserProfile } from '@/types';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 60_000 } },
});

function KontoInner() {
  const qc = useQueryClient();
  const { data: profile, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.getMe(),
  });

  async function handleSave(data: Partial<UserProfile>) {
    await api.updateMe(data);
    await qc.invalidateQueries({ queryKey: ['me'] });
  }

  return <AccountShell profile={profile ?? null} isLoading={isLoading} onSave={handleSave} />;
}

export default function KontoPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <KontoInner />
    </QueryClientProvider>
  );
}
