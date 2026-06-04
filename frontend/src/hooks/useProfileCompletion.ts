import { useMemo } from 'react';
import type { UserProfile } from '@/types';

type SectionId = 'profile' | 'contact' | 'company' | 'shipping' | 'invoice';

interface RequiredField {
  section: SectionId;
  field: keyof UserProfile;
  condition?: (p: UserProfile) => boolean;
}

const REQUIRED: RequiredField[] = [
  // Mein Profil
  { section: 'profile', field: 'first_name' },
  { section: 'profile', field: 'last_name' },
  // Kontakt & Adresse
  { section: 'contact', field: 'phone' },
  { section: 'contact', field: 'address_line1' },
  { section: 'contact', field: 'city' },
  { section: 'contact', field: 'postal_code' },
  // Firmendaten (B2B / Lieferant)
  { section: 'company', field: 'company_name', condition: (p) => p.is_business || p.role === 'supplier' },
  { section: 'company', field: 'company_legal_form', condition: (p) => p.is_business || p.role === 'supplier' },
  { section: 'company', field: 'uid_number', condition: (p) => p.is_business || p.role === 'supplier' },
  // Lieferadresse B2C
  { section: 'shipping', field: 'ship_b2c_first_name', condition: (p) => !p.is_business && p.role === 'customer' },
  { section: 'shipping', field: 'ship_b2c_last_name', condition: (p) => !p.is_business && p.role === 'customer' },
  { section: 'shipping', field: 'ship_b2c_address_line1', condition: (p) => !p.is_business && p.role === 'customer' },
  { section: 'shipping', field: 'ship_b2c_city', condition: (p) => !p.is_business && p.role === 'customer' },
  { section: 'shipping', field: 'ship_b2c_postal_code', condition: (p) => !p.is_business && p.role === 'customer' },
  // Lieferadresse B2B
  { section: 'shipping', field: 'ship_b2b_company', condition: (p) => p.is_business || p.role === 'supplier' },
  { section: 'shipping', field: 'ship_b2b_address_line1', condition: (p) => p.is_business || p.role === 'supplier' },
  { section: 'shipping', field: 'ship_b2b_city', condition: (p) => p.is_business || p.role === 'supplier' },
  { section: 'shipping', field: 'ship_b2b_postal_code', condition: (p) => p.is_business || p.role === 'supplier' },
  // Rechnungsadresse (wenn nicht = Lieferadresse)
  { section: 'invoice', field: 'invoice_first_name', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !p.invoice_same_as_shipping },
  { section: 'invoice', field: 'invoice_last_name', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !p.invoice_same_as_shipping },
  { section: 'invoice', field: 'invoice_address_line1', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !p.invoice_same_as_shipping },
  { section: 'invoice', field: 'invoice_city', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !p.invoice_same_as_shipping },
  { section: 'invoice', field: 'invoice_postal_code', condition: (p) => (p.role === 'customer' || p.role === 'supplier') && !p.invoice_same_as_shipping },
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

export function useProfileCompletion(profile: UserProfile | null): ProfileCompletion {
  return useMemo(() => {
    if (!profile) return { percentage: 0, completedCount: 0, totalCount: 0, missingBySection: {} };

    const applicable = REQUIRED.filter((r) => !r.condition || r.condition(profile));
    const totalCount = applicable.length;
    const completedCount = applicable.filter((r) => isFilled(profile, r.field)).length;
    const percentage = totalCount === 0 ? 100 : Math.round((completedCount / totalCount) * 100);

    const missingBySection: Partial<Record<SectionId, number>> = {};
    for (const r of applicable) {
      if (!isFilled(profile, r.field)) {
        missingBySection[r.section] = (missingBySection[r.section] ?? 0) + 1;
      }
    }

    return { percentage, completedCount, totalCount, missingBySection };
  }, [profile]);
}
