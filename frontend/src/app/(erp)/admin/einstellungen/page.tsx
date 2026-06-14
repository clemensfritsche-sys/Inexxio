'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { SystemConfigSection } from '@/components/account/sections/system-config-section';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, staleTime: 60_000 } },
});

export default function EinstellungenPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="p-4 sm:p-6 max-w-3xl mx-auto">
        <SystemConfigSection />
      </div>
    </QueryClientProvider>
  );
}
