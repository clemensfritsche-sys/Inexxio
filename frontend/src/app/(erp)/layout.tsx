'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { Navbar } from '@/components/layout/navbar';
import { Footer } from '@/components/layout/footer';

const ROLE_KEY = 'inexxio_user_role';

export default function ERPLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsubscribe = onAuthChange(async (firebaseUser) => {
      if (!firebaseUser) {
        router.replace(`/login?from=${window.location.pathname}`);
        return;
      }

      const token = await firebaseUser.getIdToken();
      api.setToken(token);

      try {
        const profile = await api.getMe();
        localStorage.setItem(ROLE_KEY, profile.role);
        if (profile.role === 'customer' || profile.role === 'supplier') {
          router.replace('/');
          return;
        }
      } catch {
        const cached = localStorage.getItem(ROLE_KEY);
        if (cached === 'customer' || cached === 'supplier') {
          router.replace('/');
          return;
        }
      }

      setLoading(false);
    });
    return unsubscribe;
  }, [router]);

  if (loading) {
    return (
      <>
        <Navbar />
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: 'calc(100vh - 72px - 280px)' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ display: 'inline-block', height: 32, width: 32, borderRadius: '50%', border: '4px solid #E51A14', borderTopColor: 'transparent', animation: 'spin 0.7s linear infinite' }} />
            <p style={{ marginTop: 8, fontSize: 14, color: '#64748b' }}>Wird geladen…</p>
          </div>
        </div>
        <Footer />
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </>
    );
  }

  return (
    <>
      <Navbar />
      <main style={{ minHeight: 'calc(100vh - 72px - 280px)', background: '#FAFAF8' }}>
        {children}
      </main>
      <Footer />
    </>
  );
}
