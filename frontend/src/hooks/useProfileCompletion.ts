import { useMemo } from 'react';
import type { UserProfile } from '@/types';

// Adresse + Rechnungsadresse liegen gemeinsam im Reiter «Mein Profil» – darum zählen
// ihre Pflichtfelder auf denselben Abschnitt (das Badge erscheint am Profil-Reiter).
type SectionId = 'profile';

interface RequiredField {
  section: SectionId;
  field: keyof UserProfile;
  condition?: (p: UserProfile) => boolean;
}

const REQUIRED: RequiredField[] = [
  // Mein Profil – Person
  { section: 'profile', field: 'first_name' },
  { section: 'profile', field: 'last_name' },
  // Mein Profil – Adresse
  { section: 'profile', field: 'phone' },
  { section: 'profile', field: 'address_line1' },
  { section: 'profile', field: 'city' },
  { section: 'profile', field: 'postal_code' },
  // Mein Profil – Firmendaten (Lieferant)
  { section: 'profile', field: 'company_name', condition: (p) => p.role === 'supplier' },
  { section: 'profile', field: 'uid_number', condition: (p) => p.role === 'supplier' },
  // Mein Profil – Rechnungsadresse (wenn nicht = Lieferadresse)
  { section: 'profile', field: 'invoice_first_name', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !(p.invoice_same_as_shipping ?? true) },
  { section: 'profile', field: 'invoice_last_name', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !(p.invoice_same_as_shipping ?? true) },
  { section: 'profile', field: 'invoice_address_line1', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !(p.invoice_same_as_shipping ?? true) },
  { section: 'profile', field: 'invoice_city', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !(p.invoice_same_as_shipping ?? true) },
  { section: 'profile', field: 'invoice_postal_code', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !(p.invoice_same_as_shipping ?? true) },
];

function isFilled(profile: UserProfile, field: keyof UserProfile): boolean {
  const val = profile[field];
  if (val === null || val === undefined) return false;
  if (typeof val === 'string') return val.trim().length > 0;
  return true;
}

export interface ProfileCompletion {
  percentage: number;
  completedCount: number;
  totalCount: number;
  missingBySection: Partial<Record<SectionId, number>>;
}

/** Wie weit ist das Profil ausgefüllt? Gezählt werden **nur** die Pflichtangaben, die
 *  für diese Rolle gelten – ein Feld, das für einen Kunden gar nicht erscheint, fehlt ihm
 *  auch nicht. */
export function useProfileCompletion(profile: UserProfile | null): ProfileCompletion {
  return useMemo(() => {
    if (!profile) return { percentage: 0, completedCount: 0, totalCount: 0, missingBySection: {} };

    const applicable = REQUIRED.filter((r) => !r.condition || r.condition(profile));
    const completedCount = applicable.filter((r) => isFilled(profile, r.field)).length;
    const percentage = applicable.length === 0 ? 100
      : Math.round((completedCount / applicable.length) * 100);

    const missingBySection: Partial<Record<SectionId, number>> = {};
    for (const r of applicable) {
      if (!isFilled(profile, r.field)) {
        missingBySection[r.section] = (missingBySection[r.section] ?? 0) + 1;
      }
    }
    return { percentage, completedCount, totalCount: applicable.length, missingBySection };
  }, [profile]);
}
