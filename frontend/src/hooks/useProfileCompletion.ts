import { useMemo } from 'react';
import type { UserProfile } from '@/types';

// Person und Adressbuch liegen gemeinsam im Reiter «Mein Profil» – darum zählen ihre
// Pflichtangaben auf denselben Abschnitt (das Badge erscheint am Profil-Reiter).
type SectionId = 'profile';

interface RequiredField {
  section: SectionId;
  field: keyof UserProfile;
}

// **Pflicht ist, was wirklich fehlt** (#1043): keine Angabe hängt an der Rolle. Die Firma
// ist eine Zuordnung zu einem Firmen-Datensatz und freiwillig; die Rechnungsadresse ebenso
// (leer gilt die Lieferadresse).
const REQUIRED: RequiredField[] = [
  // Mein Profil – Person
  { section: 'profile', field: 'first_name' },
  { section: 'profile', field: 'last_name' },
  { section: 'profile', field: 'phone' },
  // **Mindestens eine Anschrift** – sie steht im Adressbuch; Strasse, PLZ und Ort prüft
  // schon der Dienst beim Anlegen (`address_book._assert_complete`).
  { section: 'profile', field: 'addresses' },
];

function isFilled(profile: UserProfile, field: keyof UserProfile): boolean {
  const val = profile[field];
  if (val === null || val === undefined) return false;
  if (typeof val === 'string') return val.trim().length > 0;
  if (Array.isArray(val)) return val.length > 0;
  return true;
}

export interface ProfileCompletion {
  percentage: number;
  completedCount: number;
  totalCount: number;
  missingBySection: Partial<Record<SectionId, number>>;
}

/** Wie weit ist das Profil ausgefüllt? Gezählt werden die Pflichtangaben (`REQUIRED`). */
export function useProfileCompletion(profile: UserProfile | null): ProfileCompletion {
  return useMemo(() => {
    if (!profile) return { percentage: 0, completedCount: 0, totalCount: 0, missingBySection: {} };

    const completedCount = REQUIRED.filter((r) => isFilled(profile, r.field)).length;
    const percentage = REQUIRED.length === 0 ? 100
      : Math.round((completedCount / REQUIRED.length) * 100);

    const missingBySection: Partial<Record<SectionId, number>> = {};
    for (const r of REQUIRED) {
      if (!isFilled(profile, r.field)) {
        missingBySection[r.section] = (missingBySection[r.section] ?? 0) + 1;
      }
    }
    return { percentage, completedCount, totalCount: REQUIRED.length, missingBySection };
  }, [profile]);
}
