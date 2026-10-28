'use client';

import { QueryClientProvider } from '@tanstack/react-query';
import { AuthGate, MAIN_H } from '@/components/auth/auth-gate';
import { FeedbackPin } from '@/components/feedback/feedback-pin';
import { useFeedClient } from '@/lib/use-feed';

/** Das ERP – nur für Personal (`AuthGate staffOnly`). Die Listen des Feeds hält React Query
 *  (`lib/use-feed.ts`). */
export default function ERPLayout({ children }: { children: React.ReactNode }) {
  const client = useFeedClient();
  return (
    <QueryClientProvider client={client}>
      <AuthGate staffOnly>
        <main style={{ minHeight: MAIN_H, background: 'var(--bg-2)' }}>
          {children}
        </main>

        <FeedbackPin />
      </AuthGate>
    </QueryClientProvider>
  );
}
