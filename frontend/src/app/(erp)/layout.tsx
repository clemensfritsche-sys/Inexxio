'use client';

import { AuthGate, MAIN_H } from '@/components/auth/auth-gate';
import { FeedbackPin } from '@/components/feedback/feedback-pin';

/** Das ERP – nur für Personal (`AuthGate staffOnly`). */
export default function ERPLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate staffOnly>
      <main style={{ minHeight: MAIN_H, background: 'var(--bg-2)' }}>
        {children}
      </main>

      <FeedbackPin />
    </AuthGate>
  );
}
