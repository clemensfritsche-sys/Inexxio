'use client';

import { AuthGate, MAIN_H } from '@/components/auth/auth-gate';

/** Das Konto – für jede angemeldete Person (`AuthGate`). */
export default function AccountLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthGate>
      <main style={{ minHeight: MAIN_H, background: 'var(--bg-1)' }}>
        {children}
      </main>
    </AuthGate>
  );
}
