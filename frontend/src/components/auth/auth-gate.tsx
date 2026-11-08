'use client';

/**
 * **Der Schutz von `/erp` und `/konto` – EIN Bauteil.** Ohne Anmeldung zur Anmeldung
 * (`/login?from=…`). Mit `staffOnly` darf nur Personal hinein (`isStaff`); wer nicht darf, landet
 * im Konto, nie auf «/» (`lib/login-target`). Den Token holt der API-Client je Anfrage.
 */
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { isStaff } from '@/lib/record-status';
import { cachedRole, rememberRole } from '@/lib/account-cache';
import { Skeleton } from '@/components/erp/skeleton';

export function AuthGate({ staffOnly = false, children }: {
  /** Nur Personal (admin, employee) – sonst ins Konto. */
  staffOnly?: boolean;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let checked: string | null = null;   // je Person EINMAL – der Token erneuert sich stündlich
    return onAuthChange(async (user) => {
      if (!user) {
        checked = null;
        router.replace(`/login?from=${window.location.pathname}`);
        return;
      }
      if (checked === user.uid) return;
      checked = user.uid;
      if (staffOnly && !(await mayEnter())) {
        router.replace('/konto');
        return;
      }
      setLoading(false);
    });
  }, [router, staffOnly]);

  if (loading) {
    return (
      <div style={{ minHeight: MAIN_H, maxWidth: 880, margin: '0 auto', padding: 24 }}>
        <Skeleton rows={6} label="Anmeldung wird geprüft" />
      </div>
    );
  }
  return <>{children}</>;
}

/**
 * ►►► **Ins ERP darf, wer im Haus arbeitet** – zwei Rollen, wie im Backend. Ohne Antwort gilt
 * der letzte bekannte Stand; ein unbekannter ist keiner.
 */
async function mayEnter(): Promise<boolean> {
  try {
    const { role } = await api.getMe();
    rememberRole(role);
    return isStaff(role);
  } catch {
    return isStaff(cachedRole());
  }
}

/** Die Höhe der Fläche zwischen Kopf und Fuss – Ladeanzeige und Inhalt gleich. */
export const MAIN_H = 'calc(100vh - var(--site-header-h) - 280px)';
