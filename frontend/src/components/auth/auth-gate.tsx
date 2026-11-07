'use client';

/**
 * **Der Schutz von `/erp` und `/konto` – EIN Bauteil** (vorher zwei fast gleiche Layouts).
 *
 * Ohne Anmeldung geht es zur Anmeldung (`/login?from=…`, zurück hierher danach). Mit
 * `staffOnly` darf nur Personal hinein (`isStaff`, Spiegel von `people.STAFF_ROLES`) – wer
 * nicht darf, landet in seinem **Konto**, nicht auf «/»: dort steht die Website, und die
 * kennt keine Anmeldung (`lib/login-target`). Den Token setzt hier niemand: der API-Client
 * holt ihn je Anfrage (`lib/firebase.ts`).
 */
import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { onAuthChange } from '@/lib/firebase';
import { api } from '@/lib/api';
import { isStaff } from '@/lib/record-status';
import { cachedRole, rememberRole } from '@/lib/account-cache';

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
      <div className="flex items-center justify-center" style={{ minHeight: MAIN_H }}>
        <div className="text-center">
          <div className="inline-block h-8 w-8 rounded-full border-4 border-inexxio border-t-transparent animate-spin" />
          <p className="mt-2 text-sm text-fg-3">Wird geladen…</p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}

/**
 * ►►► **Ins ERP darf, wer im Haus arbeitet** (Testnotiz #1043) – gefragt wird dasselbe wie
 * im Backend: zwei Rollen, nicht «nicht diese eine». Ohne Antwort gilt der letzte bekannte
 * Stand – und ein unbekannter ist keiner.
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
