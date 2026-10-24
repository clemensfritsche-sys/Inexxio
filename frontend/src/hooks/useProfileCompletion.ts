import { useMemo } from 'react';
import type { UserProfile } from '@/types';

/** Ein fehlender Pflichtwert: wie er heisst und wo auf der Konto-Seite er steht. */
export interface MissingField { label: string; anchor: 'person' | 'adressen' }

export interface ProfileCompletion {
  percentage: number;
  /** Was fehlt, in der Reihenfolge der Seite – die Konto-Seite nennt das erste. */
  missing: MissingField[];
}

/**
 * Wie weit ist das Profil ausgefüllt?
 *
 * ►►► **Die Regel steht im Backend** (`people.required_fields` / `missing_fields`) – das ERP
 * ist die Wahrheit, das Konto ist ihr Spiegel. Hier wird nur gezählt, was der Server meldet;
 * dieselbe Liste trägt im ERP die Zahl «zu tun» am Symbol.
 */
export function useProfileCompletion(profile: UserProfile | null): ProfileCompletion {
  return useMemo(() => {
    if (!profile) return { percentage: 0, missing: [] };
    const required = profile.required_fields?.length ?? 0;
    const missing = (profile.missing_fields ?? []).map((m) => ({
      label: m.label, anchor: (m.section === 'adressen' ? 'adressen' : 'person') as MissingField['anchor'],
    }));
    const percentage = required ? Math.round(((required - missing.length) / required) * 100) : 100;
    return { percentage, missing };
  }, [profile]);
}
