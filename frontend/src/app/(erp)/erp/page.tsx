'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { UniversalFeed } from '@/components/erp/universal-feed';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30_000,
    },
  },
});

export default function ERPPage() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="h-full">
        <UniversalFeed />
      </div>
    </QueryClientProvider>
  );
}
