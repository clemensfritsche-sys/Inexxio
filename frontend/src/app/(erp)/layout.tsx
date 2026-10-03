'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { isStaff } from '@/lib/record-status';
import { Navbar } from '@/components/layout/navbar';
import { Footer } from '@/components/layout/footer';
import { ScanProvider } from '@/components/scan/scan-provider';
import { FeedbackPin } from '@/components/feedback/feedback-pin';

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
        // ►►► **Ins ERP darf, wer im Haus arbeitet** (Testnotiz #1043). ◄◄◄ Vorher
        // stand hier «ausser Kunden dürfen alle» – also liess die Sperre jeden Wert
        // durch, den sie nicht kannte, und ein «Lieferant» landete auf einer Oberfläche,
        // die ihm der Server danach leer beantwortet. Gefragt wird jetzt dasselbe wie im
        // Backend (`people.STAFF_ROLES`): zwei Rollen, nicht «nicht diese eine».
        // Wer nicht hinein darf, landet in seinem **Konto**, nicht auf «/»: dort steht die
        // Website, und die kennt keine Anmeldung (`lib/login-target`).
        if (!isStaff(profile.role)) {
          router.replace('/konto');
          return;
        }
      } catch {
        // Ohne Antwort gilt der letzte bekannte Stand – und ein unbekannter ist keiner.
        if (!isStaff(localStorage.getItem(ROLE_KEY))) {
          router.replace('/konto');
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
    <ScanProvider>
      <Navbar />
      <main style={{ minHeight: 'calc(100vh - 72px - 280px)', background: '#FAFAF8' }}>
        {children}
      </main>
      <Footer />

      <FeedbackPin />
    </ScanProvider>
  );
}
