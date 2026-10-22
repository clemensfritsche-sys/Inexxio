import { useMemo } from 'react';
import type { UserProfile } from '@/types';

/** Ein fehlender Pflichtwert: wie er heisst und wo auf der Konto-Seite er steht. */
export interface MissingField { label: string; anchor: 'person' | 'adressen' }

interface RequiredField extends MissingField { field: keyof UserProfile }

// **Pflicht ist, was wirklich fehlt** (#1043): keine Angabe hängt an der Rolle. Die Firma
// ist eine Zuordnung zu einem Firmen-Datensatz und freiwillig; die Rechnungsadresse ebenso
// (leer gilt die Lieferadresse).
const REQUIRED: RequiredField[] = [
  { field: 'first_name', label: 'Vorname', anchor: 'person' },
  { field: 'last_name', label: 'Nachname', anchor: 'person' },
  { field: 'phone', label: 'Telefon', anchor: 'person' },
  // **Mindestens eine Anschrift** – sie steht im Adressbuch; Strasse, PLZ und Ort prüft
  // schon der Dienst beim Anlegen (`address_book._assert_complete`).
  { field: 'addresses', label: 'Adresse', anchor: 'adressen' },
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
  /** Was fehlt, in der Reihenfolge der Seite – die Konto-Seite nennt das erste. */
  missing: MissingField[];
}

/** Wie weit ist das Profil ausgefüllt? Gezählt werden die Pflichtangaben (`REQUIRED`). */
export function useProfileCompletion(profile: UserProfile | null): ProfileCompletion {
  return useMemo(() => {
    if (!profile) return { percentage: 0, missing: [] };
    const missing = REQUIRED.filter((r) => !isFilled(profile, r.field)).map(({ label, anchor }) => ({ label, anchor }));
    const percentage = Math.round(((REQUIRED.length - missing.length) / REQUIRED.length) * 100);
    return { percentage, missing };
  }, [profile]);
}
