'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { FeedbackPin } from '@/components/feedback/feedback-pin';

export default function AccountLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthChange(async (firebaseUser) => {
      if (!firebaseUser) {
        router.replace(`/login?from=/konto`);
        return;
      }
      const token = await firebaseUser.getIdToken();
      api.setToken(token);
      setLoading(false);
    });
    return unsubscribe;
  }, [router]);

  if (loading) {
    return (
      <>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - var(--site-header-h) - 280px)' }}>
          <div style={{ height: 32, width: 32, borderRadius: '50%', border: '4px solid #E51A14', borderTopColor: 'transparent', animation: 'spin 0.7s linear infinite' }} />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
        </div>
      </>
    );
  }

  return (
    <>
      <main style={{ minHeight: 'calc(100vh - var(--site-header-h) - 280px)', background: '#FAFAF8' }}>
        {children}
      </main>

      <FeedbackPin />
    </>
  );
}
