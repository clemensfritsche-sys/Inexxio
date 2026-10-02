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

// ►►► **Pflicht ist, was wirklich fehlt** (Testnotiz #1043). ◄◄◄ Hier standen sieben
// weitere Zeilen, und jede fragte die **Rolle**: Firmenname und UID «für einen
// Lieferanten», die fünf Felder der Rechnungsadresse «für Kunden und Lieferanten».
// Beides ist weg, und zwar aus demselben Grund wie im Formular darunter:
//
// * Die **Firmenangaben** hängen am Firmennamen, nicht an einer Rolle – und er ist
//   freiwillig (eine Privatperson hat keinen). Was folgt, ist die **Rechtsform**: ohne
//   sie weist der Server ab (`people.assert_company`), also ist sie hier eine Pflicht –
//   aber nur, wenn ein Name dasteht.
// * Die **Rechnungsadresse** ist freiwillig: leer gilt die Lieferadresse. Ein Pflichtfeld
//   in einem Block, den man gar nicht ausfüllen muss, zählte Lücken, die keine sind.
const REQUIRED: RequiredField[] = [
  // Mein Profil – Person
  { section: 'profile', field: 'first_name' },
  { section: 'profile', field: 'last_name' },
  // Mein Profil – Adresse
  { section: 'profile', field: 'phone' },
  { section: 'profile', field: 'address_line1' },
  { section: 'profile', field: 'city' },
  { section: 'profile', field: 'postal_code' },
  // Mein Profil – Firmendaten: der Name ist die Erklärung, die Rechtsform seine Folge.
  {
    section: 'profile', field: 'legal_form',
    condition: (p) => !!(p.company_name ?? '').trim(),
  },
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
 *  für diesen Datensatz gelten – ein Feld, das gar nicht erscheint, fehlt auch nicht. */
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
