'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import { AuthGate, MAIN_H } from '@/components/auth/auth-gate';
import { useFeedClient } from '@/lib/use-feed';
import { AssistantClient } from '@/lib/assistant';

/** Das ERP – nur für Personal (`AuthGate staffOnly`). Die Listen des Feeds hält React Query
 *  (`lib/use-feed.ts`); nur hier fragt der Assistent (`lib/assistant`). */
export default function ERPLayout({ children }: { children: React.ReactNode }) {
  const client = useFeedClient();
  return (
    <QueryClientProvider client={client}>
      <AssistantClient.Provider value={client}>
        <AuthGate staffOnly>
          <main style={{ minHeight: MAIN_H, background: 'var(--bg-2)' }}>
            {children}
          </main>
        </AuthGate>
      </AssistantClient.Provider>
    </QueryClientProvider>
  );
}
