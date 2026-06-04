'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { AccountShell } from '@/components/account/account-shell';

export default function KontoPage() {
  const queryClient = useQueryClient();
  const { data: profile, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: () => api.getMe(),
    staleTime: 60_000,
  });

  async function handleSave(data: Record<string, unknown>) {
    await api.updateMe(data);
    await queryClient.invalidateQueries({ queryKey: ['me'] });
  }

  return <AccountShell profile={profile ?? null} isLoading={isLoading} onSave={handleSave} />;
}
